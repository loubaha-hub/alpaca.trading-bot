"""v38 through the bot's own code (r34.py's V38), on the second-by-second read
(SEC_DUMP, 10-06..10-09): does the code do what the research did?

python3 v38_botreplay.py <new windows> <old windows> <old minute bars> [research|live] [lag]

research - each stock alone, on a $15,000 account that never changes, no small
    sizes, no limit on positions: v38_by_day.py's terms (with BIYA: 110 trades,
    +$64,767, the minute-wide floor).
live - the bot as it will run: one account from $15,000, compounding day to
    day; all of a day's stocks in one stream in time order; two at once; the
    smaller sizes once the day is down $500, the top-up lot; the -10% halt; no
    buys from 7pm and everything sold at 7pm (the engine's FLATTEN_AT).

The market: each window's prints where the read has them, else four prints a
second from the second's row (o, h/l, l/h, c - a quarter of its volume each);
the bid and ask as read (secsim.Path, the research's own). Every print goes
through the bot's tick-worker steps and V38.evaluate. One-minute candles from
the second rows reach the strategy as each minute closes. A buy order reaches
the market `lag` seconds after it is sent (default 1.0, the research's
BUY_LAG): it fills at the ask then if its limit is at or over it, else at the
first ask at or under its limit while it works (V38_BUY_WAIT), else not. A sale
fills at the bid SELL_LAG (0.5s) after it is sent. The bot's clock moves with
its orders and pauses, and prints that arrive meanwhile are handed to it late,
as the live queue does. A position still held when a window ends is sold at
its last bid (the read stops there)."""
import asyncio, importlib.util, logging, os, sys
from collections import defaultdict
from datetime import datetime, timezone
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tests"))
spec = importlib.util.spec_from_file_location("bot", os.path.join(REPO, "r34.py"))
bot = importlib.util.module_from_spec(spec)
sys.modules["bot"] = bot
spec.loader.exec_module(bot)
import secsim as S
import v38_final as F
from helpers import FakeBroker
from conftest import Clock
from speedsim_study import session, SESSIONS

ET = bot.ET
SELL_LAG = 0.5
START = 15_000.0
NOW = [0.0]
CLOCK = Clock(datetime(2026, 10, 6, 4, 0, tzinfo=ET))
_real_time, _real_asyncio = bot.time, bot.asyncio


INLINE = SimpleNamespace(ev=[], i=0, apply=None)   # quotes, candles, window starts


def _set(t):
    NOW[0] = t
    CLOCK.now = datetime.fromtimestamp(t, ET)


def advance(t):
    """The clock to t. Quotes and candles reach the strategy as they happen -
    live they come from the stream's own callback, not the print queue, so
    they arrive on time even while the tick worker waits in an order."""
    ev = INLINE.ev
    while INLINE.i < len(ev) and ev[INLINE.i][0] <= t:
        e = ev[INLINE.i]
        INLINE.i += 1
        if e[0] > NOW[0]:
            _set(e[0])
        INLINE.apply(e)
    if t > NOW[0]:
        _set(t)


class _Proxy:
    def __init__(self, real, **over):
        self._real, self._over = real, over

    def __getattr__(self, k):
        return self._over[k] if k in self._over else getattr(self._real, k)


async def _sleep(d, *a, **kw):
    advance(NOW[0] + (d or 0))
    await _real_asyncio.sleep(0)


bot.time = _Proxy(_real_time, time=lambda: NOW[0], monotonic=lambda: NOW[0])
bot.asyncio = _Proxy(_real_asyncio, sleep=_sleep)
bot.datetime = CLOCK.cls


class Market:
    """The bid and ask of each symbol's current window, at any time."""

    def __init__(self):
        self.path = {}

    def ask(self, sym, t):
        p = self.path.get(sym)
        return p.ask_at(t) if p else None

    def bid(self, sym, t):
        p = self.path.get(sym)
        return p.bid_at(t) if p else None


class ReplayBroker(FakeBroker):
    def __init__(self, cash, mkt, lag, fixed=None):
        super().__init__(cash)
        self.cash, self.mkt, self.lag, self.fixed = cash, mkt, lag, fixed
        self.trips = []                          # (sym, t in, t out, P/L, buys, sales)
        self.open = {}                           # sym -> [t in, dollars out, dollars in, buys, sales]

    async def equity(self, fallback=0.0):
        await _real_asyncio.sleep(0)
        if self.fixed:
            return self.fixed
        return self.cash + sum(q * (self.mkt.bid(s, NOW[0]) or 0.0)
                               for s, q in self.held.items() if q)

    def _book(self, sym, side, n, px):
        if side == bot.OrderSide.BUY:
            if not self.held.get(sym):
                self.open[sym] = [NOW[0], 0.0, 0.0, 0, 0]
            self.held[sym] = self.held.get(sym, 0.0) + n
            self.cost[sym] = self.cost.get(sym, 0.0) + n * px
            self.cash -= n * px
            self.open[sym][1] += n * px
            self.open[sym][3] += 1
        else:
            avg = self.cost[sym] / self.held[sym]
            self.held[sym] -= n
            self.cost[sym] = avg * self.held[sym]
            self.cash += n * px
            self.open[sym][2] += n * px
            self.open[sym][4] += 1
            if self.held[sym] <= 0:
                o = self.open.pop(sym)
                self.trips.append((sym, o[0], NOW[0], o[2] - o[1], o[3], o[4]))
        self.fill_log.setdefault(sym, []).append((n, px))

    async def send(self, symbol, qty, side, limit, wait=None):
        await _real_asyncio.sleep(0)
        qty = int(qty)
        t = NOW[0]
        if side == bot.OrderSide.BUY:
            p = self.mkt.path[symbol]
            t1, end = t + self.lag, t + self.lag + (wait or 0.0)
            hit = None
            a = p.ask_at(t1)
            if a and a <= limit + 1e-9:
                hit = (t1, a)
            else:
                i = p.at(t1)
                while i < len(p.ev) and p.times[i] <= end:
                    a = p.ev[i][3] or p.ev[i][1]
                    if a and a <= limit + 1e-9:
                        hit = (p.times[i], a)
                        break
                    i += 1
            advance(hit[0] if hit else end)
            self.orders.append((symbol, qty, side, limit, qty if hit else 0))
            if not hit:
                return 0
            self._book(symbol, side, qty, hit[1])
            return qty
        n = min(qty, int(self.held.get(symbol, 0.0)))
        if n <= 0:
            return -1
        advance(t + SELL_LAG)
        b = self.mkt.bid(symbol, NOW[0])
        self.orders.append((symbol, qty, side, limit, n if b and b >= limit - 1e-9 else 0))
        if not b or b < limit - 1e-9:
            return 0
        self._book(symbol, side, n, b)
        return n

    async def send_market(self, symbol, qty, side, ref=0.0, wait=None):
        await _real_asyncio.sleep(0)
        n = min(int(qty), int(self.held.get(symbol, 0.0)))
        if n <= 0:
            return -1
        advance(NOW[0] + SELL_LAG)
        self._book(symbol, side, n, self.mkt.bid(symbol, NOW[0]))
        return n


class ReplayData:
    def __init__(self, mkt):
        self.mkt = mkt

    async def quote(self, symbol, side):
        return (self.mkt.ask if side == "ask" else self.mkt.bid)(symbol, NOW[0])

    async def subscribe(self, symbols, force=False):
        return None


WSTART, QUOTE, PRINT, BAR, WEND = 0, 1, 2, 3, 4


def events(rec):
    """One window's events in time order: (t, kind, sym, payload)."""
    if rec.get("missing"):                       # a gap in the read: the window ends there (as Path)
        cut = min(rec["missing"])
        rec = dict(rec, T=[r for r in rec["T"] if r[0] < cut * 1000],
                   Q=[r for r in rec["Q"] if r[0] < cut * 1000],
                   S=[r for r in rec["S"] if r[0] < cut])
    a, sym = rec["start"], rec["sym"]
    path = S.Path(rec)
    if not path.ev:
        return []
    ev = [(a, WSTART, sym, path)]
    tick_secs = {int(r[0] // 1000) for r in rec["T"]}
    for r in rec["Q"]:
        if r[1] and r[2]:
            ev.append((a + r[0] / 1000, QUOTE, sym, (r[1], r[2])))
    for r in rec["T"]:
        ev.append((a + r[0] / 1000, PRINT, sym, (r[1], r[2], list(r[3]))))
    mins = {}
    for r in rec["S"]:
        k = r[0]
        if r[1]:
            m = int((a + k) // 60)
            x = mins.get(m)
            if x is None:
                mins[m] = [r[1], r[2], r[3], r[4], r[5]]
            else:
                x[1], x[2], x[3], x[4] = max(x[1], r[2]), min(x[2], r[3]), r[4], x[4] + r[5]
        if k in tick_secs:
            continue
        if r[1]:
            o, h, l, c = r[1], r[2], r[3], r[4]
            mid = (h, l) if c < o else (l, h)
            size = max(1, int(r[5] / 4))
            for i, px in enumerate((o, mid[0], mid[1], c)):
                ev.append((a + k + 0.2 * i + 0.01, PRINT, sym, (px, size, [])))
        if r[7] and r[8]:
            ev.append((a + k + 0.99, QUOTE, sym, (r[7], r[8])))
    for m, (o, h, l, c, v) in mins.items():
        ev.append(((m + 1) * 60 + 0.05, BAR, sym, (m * 60, o, h, l, c, v)))
    end = path.times[-1]
    ev = [e for e in ev if e[0] <= end]
    ev.append((end + 0.001, WEND, sym, None))
    ev.sort(key=lambda e: (e[0], e[1]))
    return ev


def inline(strat, mkt):
    def apply(e):
        t, kind, sym, x = e
        s = strat.st(sym)
        if kind == WSTART:
            mkt.path[sym] = x
            s.bars = []
            s.v37_prints.clear()
            s.v37_speed_prints.clear()
            strat.qualified.add(sym)
        elif kind == QUOTE:
            strat.offer_quote(sym, *x)
        elif kind == BAR:
            m, o, h, l, c, v = x
            strat.offer_bar(SimpleNamespace(symbol=sym, timestamp=datetime.fromtimestamp(m, timezone.utc),
                                            open=o, high=h, low=l, close=c, volume=v))
    return apply


async def run(strat, ev, mkt, flatten=False):
    INLINE.ev = [e for e in ev if e[1] in (WSTART, QUOTE, BAR)]
    INLINE.i, INLINE.apply = 0, inline(strat, mkt)
    done_flat = False
    for t, kind, sym, x in ev:
        if kind in (WSTART, QUOTE, BAR):
            continue
        advance(t)                               # busy in an order: this one is handled late
        s = strat.st(sym)
        if kind == WEND:
            if s.in_position:
                await strat.exit(s, "window-end")
            continue
        if flatten and not done_flat and (CLOCK.now.hour, CLOCK.now.minute) >= bot.FLATTEN_AT:
            done_flat = True
            await strat.flatten_all("end-of-day")
        if True:
            px, size, conds = x
            if not bot.qualifies(conds):
                s.last_tick_at = NOW[0]
                strat.note_skipped(s, px, conds)
                continue
            s.last_price, s.last_conds, s.last_size = px, conds, size
            s.last_print_ts, s.last_tick_at = t, NOW[0]
            strat.note_trade(s, px, size)
            await strat.evaluate(s, px)
            s.day_high = max(s.day_high, px)


def new_strat(broker, data, eq, day):
    st = bot.V38(broker, data)
    st.day_start_equity = eq
    st.day = day
    return st


def table(trips, title):
    days = sorted({d for d, *_ in trips})
    print("\n" + title)
    print("%-6s | %-22s | %-22s | %-22s | %s" % ("day", "PRE 4:00-9:30", "RTH 9:30-4:00",
                                                "AFTER 4:00-8:00", "THE DAY"))
    for d in days + ["TOTAL"]:
        cells = []
        for se in list(SESSIONS) + [None]:
            ys = [x for x in trips if (d == "TOTAL" or x[0] == d) and (se is None or session(x[2]) == se)]
            cells.append("%3d %3d won %+8.0f" % (len(ys), sum(x[4] > 0 for x in ys), sum(x[4] for x in ys)))
        print("%-6s | %s | %s | %s | %s" % (d[5:] if d != "TOTAL" else d, *cells))


def main():
    mode = sys.argv[4] if len(sys.argv) > 4 else "research"
    lag = float(sys.argv[5]) if len(sys.argv) > 5 else S.BUY_LAG
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger().setLevel(logging.ERROR)
    if os.environ.get("V38_TRACE"):              # the bot's own lines, at the replay's clock
        class _T(logging.Filter):
            def filter(self, r):
                r.msg = CLOCK.now.strftime("%H:%M:%S.%f")[:12] + " " + str(r.msg)
                return True
        logging.getLogger().setLevel(logging.INFO)
        for h in logging.getLogger().handlers:
            h.addFilter(_T())
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    only = os.environ.get("V38_ONLY")            # e.g. "2026-10-07:BIYA" - one stock
    if only:
        by = {k: v for k, v in by.items() if "%s:%s" % k == only}
    if os.environ.get("V38_DAY"):                # e.g. "2026-10-07" - one day
        by = {k: v for k, v in by.items() if k[0] == os.environ["V38_DAY"]}
    trips = []                                   # (day, sym, t in, t out, P/L, buys, sales)
    if mode == "research":
        bot.V38_SHRINK_AT = 0
        bot.V38_MAX_POSITIONS = 99
        bot.V38_MAX_EXPOSURE = 99.0
        for (day, sym), recs in sorted(by.items()):
            mkt = Market()
            br = ReplayBroker(START, mkt, lag, fixed=START)
            ev = sorted((e for r in recs for e in events(r)), key=lambda e: (e[0], e[1]))
            if not ev:
                continue
            NOW[0] = 0.0
            INLINE.ev = []
            advance(ev[0][0])
            st = new_strat(br, ReplayData(mkt), START, CLOCK.now.date())
            asyncio.run(run(st, ev, mkt))
            trips += [(day, x[0], x[1], x[2], x[3], x[4], x[5]) for x in br.trips]
        title = "THE BOT'S V38 CODE, research terms: each stock alone, $15,000 fixed (lag %.1fs)" % lag
    else:
        eq, streak = START, 0
        for day in sorted({d for d, _ in by}):
            mkt = Market()
            br = ReplayBroker(eq, mkt, lag)
            ev = sorted((e for (d, _), recs in by.items() if d == day for r in recs for e in events(r)),
                        key=lambda e: (e[0], e[1]))
            NOW[0] = 0.0
            INLINE.ev = []
            advance(ev[0][0])
            st = new_strat(br, ReplayData(mkt), eq, CLOCK.now.date())
            st.halt_streak = streak                  # as roll_day: the halt ladder runs across days
            st.stopped = streak >= 3
            asyncio.run(run(st, ev, mkt, flatten=True))
            streak = streak + 1 if st.halted_today else 0
            day_trips = [(day, x[0], x[1], x[2], x[3], x[4], x[5]) for x in br.trips]
            trips += day_trips
            print("%s: start $%.0f, end $%.0f (%+.0f), %d trades, the halt at -%.1f%%%s" % (
                day, eq, br.cash, br.cash - eq, len(day_trips), 100 * st.halt_threshold(),
                ", STOPPED (three halted days)" if st.stopped else ", HALTED" if st.halted_today else ""))
            eq = START if os.environ.get("V38_NO_COMPOUND") else br.cash   # compounding: tomorrow
                                                                            # starts from tonight
        halt = os.environ.get("V38_HALT_PCT")
        title = ("THE BOT'S V38 CODE, as it will run: one account, %s, two at once, small sizes "
                 "after -$500, the halt %s (lag %.1fs)" % (
                     "EACH DAY FROM $15,000 (no compounding)" if os.environ.get("V38_NO_COMPOUND")
                     else "from $15,000 compounding",
                     "OFF" if halt == "0" else ("at -%s%%" % halt) if halt else "-10% and its ladder", lag))
    table(trips, title + " - WITH BIYA")
    table([x for x in trips if not (x[0] == "2026-10-07" and x[1] == "BIYA")], title + " - WITHOUT BIYA")
    best = defaultdict(float)
    for x in trips:
        best[(x[0], x[1])] += x[4]
    print("\nby stock, best and worst: " + ", ".join(
        "%s %s %+.0f" % (k[0][5:], k[1], v) for k, v in sorted(best.items(), key=lambda kv: -kv[1])[:6])
          + " ... " + ", ".join("%s %s %+.0f" % (k[0][5:], k[1], v)
                                for k, v in sorted(best.items(), key=lambda kv: kv[1])[:4]))


if __name__ == "__main__":
    main()
