"""
Replay one trading day through one strategy, on a simulated account.

    python3 replay/replay.py --bot r24.py --strategy v31 --day 2026-10-02

WHAT IS REAL
  The strategy. The bot file is loaded as it is, and its own offer_bar,
  evaluate, periodic, exit, halt and self-check code makes every decision.
  The market. Friday's 1-minute bars, 4am-8pm ET, from replay/data/<day>/.

WHAT IS SIMULATED - read every result with these in mind
  * Prints. Live, the bot reacts to every trade; this data is 1-minute bars.
    Each bar becomes a path of prints - open, low, high, close for a green
    bar; open, high, low, close for a red one - more prints in busier minutes.
    Entries and stops trigger on that path, so a stop inside a bar is hit at
    the stop's price or the next print below it, never better.
  * Fills. A buy fills in full at the ask once its limit reaches the ask, a
    sell at the bid; ask and bid sit half a spread either side of the last
    print. No partial fills, rejections or broker outages, so the order-
    plumbing bugs fixed in r24 cannot show up here. Sizing, entries, exits
    and P/L do.
  * The scanner. Only the symbols in the data folder exist. One is picked up
    when it is $1-$20 and 10% above its reference (Thursday's close before
    9:30, Friday's 9:30 open after), as Engine.scan() decides, and its data
    reaches the strategy from the next 30-second subscription batch.
  * The engine's clocks (periodic and risk 5s, scanner 8s, close 20s, dead
    tape 30s, reconcile 60s) fire in time order between prints instead of
    running concurrently.
"""

import argparse
import asyncio
import csv
import importlib.util
import json
import logging
import sys
import time as _time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
REPO = Path(__file__).resolve().parent.parent
CLASSES = {"v31": "V31", "v32": "V32", "v33": "V33", "v34": "V34", "v35": "V35"}


# ---- the simulated world -----------------------------------------------------

class Clock:
    def __init__(self, t: datetime):
        self.t = t

    def ts(self) -> float:
        return self.t.timestamp()


class Market:
    """The last print per symbol, and a spread around it."""

    def __init__(self):
        self.last = {}
        self.session = {}

    def spread(self, sym):
        p = self.last[sym]
        if self.session.get(sym) == "RTH":
            return max(0.01, 0.001 * p)
        return max(0.02, 0.002 * p)               # thinner books outside 9:30-4

    def ask(self, sym):
        return self.last[sym] + self.spread(sym) / 2

    def bid(self, sym):
        return max(0.01, self.last[sym] - self.spread(sym) / 2)


class SimBroker:
    """One account, with the same async methods the bot's Broker has."""

    def __init__(self, bot, market, clock, equity, label, slip=0.0):
        self.bot, self.market, self.clock = bot, market, clock
        self.slip = slip         # stress test: fills this much worse
        self.start = equity
        self.cash = equity
        self.held = defaultdict(float)
        self.cost = defaultdict(float)
        self.label = label
        self.fills = []          # (time, sym, side, qty, price, reason)
        self.fill_log = {}       # symbol -> [(qty, price)] since take_fill_price
        self.reason = ""
        self.settled = True      # every simulated order closes at once
        self.max_pos_pct = (0.0, "", None)
        self.max_exposure_pct = (0.0, None)

    def _equity(self):
        return self.cash + sum(q * self.market.last.get(s, 0.0)
                               for s, q in self.held.items())

    async def equity(self, fallback=0.0):
        return self._equity()

    async def day_baseline(self, fallback=0.0):
        return self.start

    async def account(self):
        return SimpleNamespace(equity=self._equity(), last_equity=self.start,
                               account_number="SIM-" + self.label)

    async def positions(self):
        return {s: {"qty": q, "entry": self.cost[s] / q,
                    "price": self.market.last.get(s, 0.0)}
                for s, q in self.held.items() if q > 0}

    async def qty(self, symbol):
        return self.held.get(symbol, 0.0)

    async def avg_entry(self, symbol):
        q = self.held.get(symbol, 0.0)
        return self.cost[symbol] / q if q else None

    def take_fill_price(self, symbol):
        rows = self.fill_log.pop(symbol, [])
        qty = sum(q for q, _ in rows)
        return sum(q * p for q, p in rows) / qty if qty else 0.0

    async def cancel_open(self, symbol):
        return 0

    async def send(self, symbol, qty, side, limit, wait=None):
        if qty <= 0 or symbol not in self.market.last:
            return 0
        if side == self.bot.OrderSide.BUY:
            px = self.market.ask(symbol)
            if limit + 1e-9 < px:
                return 0
            px = min(limit, px * (1 + self.slip))
            self.cash -= qty * px
            self.held[symbol] += qty
            self.cost[symbol] += qty * px
        else:
            px = self.market.bid(symbol)
            if limit - 1e-9 > px:
                return 0
            # uncapped: an exit chases the bid down until it is filled
            px = px * (1 - self.slip)
            qty = min(qty, int(self.held.get(symbol, 0.0)))
            if qty <= 0:
                return -1                         # "not allowed to short"
            avg = self.cost[symbol] / self.held[symbol]
            self.cash += qty * px
            self.held[symbol] -= qty
            self.cost[symbol] = avg * self.held[symbol]
        self.fills.append((self.clock.t, symbol, side, qty, px, self.reason))
        self.fill_log.setdefault(symbol, []).append((qty, px))   # as Broker.send
        eq = self._equity()
        if side == self.bot.OrderSide.BUY and eq > 0:
            pct = self.held[symbol] * px / eq
            if pct > self.max_pos_pct[0]:
                self.max_pos_pct = (pct, symbol, self.clock.t)
            expo = sum(q * self.market.last.get(s, 0.0)
                       for s, q in self.held.items()) / eq
            if expo > self.max_exposure_pct[0]:
                self.max_exposure_pct = (expo, self.clock.t)
        return qty


class SimData:
    def __init__(self, market, bars=None, with_volume=True):
        self.market = market
        self.bars = bars or {}
        self.with_volume = with_volume        # r28 takes (start, close), r29+ adds volume

    async def bars_between(self, symbol, start, end):
        """What the data API would return: bars that opened in [start, end]."""
        rows = [b for b in self.bars.get(symbol, []) if start <= b.t <= end]
        if self.with_volume:                  # r30 reads the high too
            return [(b.t, b.c, b.v, b.h) for b in rows]
        return [(b.t, b.c) for b in rows]

    async def quote(self, symbol, side):
        if symbol not in self.market.last:
            return None
        return self.market.ask(symbol) if side == "ask" else self.market.bid(symbol)

    async def subscribe(self, symbols, force=False):
        return None


# ---- the data ----------------------------------------------------------------

def load_bars(folder: Path, only=None):
    bars = {}
    for f in sorted(folder.glob("*.csv")):
        sym = f.stem
        if only and sym not in only:
            continue
        rows = []
        for r in csv.DictReader(open(f)):
            t = datetime.fromisoformat(r["time"].replace("+0000", "+00:00"))
            rows.append(SimpleNamespace(
                t=t, session=r["session"], o=float(r["open"]), h=float(r["high"]),
                l=float(r["low"]), c=float(r["close"]), v=float(r["volume"])))
        rows.sort(key=lambda b: b.t)
        bars[sym] = rows
    return bars


def prints_for(bar):
    """The bar as a path of (time, price, size) prints."""
    k = int(min(120, max(4, round(bar.v / 1000))))
    path = [bar.o, bar.h, bar.l, bar.c] if bar.c < bar.o else [bar.o, bar.l, bar.h, bar.c]
    legs = [abs(path[i + 1] - path[i]) for i in range(3)]
    total = sum(legs)
    out = []
    for i in range(k):
        frac = i / (k - 1)
        if total == 0:
            price = bar.o
        else:
            d = frac * total
            for j in range(3):
                if d <= legs[j] or j == 2:
                    seg = legs[j] or 1.0
                    price = path[j] + (path[j + 1] - path[j]) * min(1.0, d / seg)
                    break
                d -= legs[j]
        t = bar.t + timedelta(seconds=(i + 0.5) * 60.0 / k)
        out.append((t, round(price, 4), bar.v / k))
    return out


# ---- running it --------------------------------------------------------------

def load_bot(path: Path):
    spec = importlib.util.spec_from_file_location("bot", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bot"] = module
    spec.loader.exec_module(module)
    return module


def install_clock(bot, clock):
    class SimDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.t.astimezone(tz) if tz else clock.t.replace(tzinfo=None)

    bot.datetime = SimDatetime
    _time.time = clock.ts                     # entry_at, hold times, log stamps
    real_sleep = asyncio.sleep

    async def no_wait(_delay=0, result=None):
        return await real_sleep(0, result)

    asyncio.sleep = no_wait                   # chases do not wait in a replay


async def tick(strat, s, price, size, now):
    """Strategy.tick_worker's body for one qualifying print (no conditions)."""
    s.last_price = price
    s.last_conds = ()
    s.last_size = size
    s.last_tick_at = now
    strat.note_trade(s, price, size)
    await strat.evaluate(s, price)
    s.day_high = max(s.day_high, price)


async def run(args):
    bot = load_bot(REPO / args.bot)
    if hasattr(bot, "load_floats"):               # r28+: float sizing
        bot.FLOATS = bot.load_floats(REPO / args.floats) if args.floats else {}
    for item in args.set:                     # what-if: override a setting
        name, value = item.split("=", 1)
        if not hasattr(bot, name):
            sys.exit("%s has no setting %s" % (args.bot, name))
        setattr(bot, name, type(getattr(bot, name))(float(value)))
    day = datetime.strptime(args.day, "%Y-%m-%d").date()
    folder = REPO / "replay" / "data" / args.day
    meta = json.load(open(folder / "meta.json"))
    daily = REPO / "replay" / "data" / "daily_bars.json"
    prev_high = {}                            # the prior session's high (v35)
    for sym, days in (json.load(open(daily)) if daily.exists() else {}).items():
        before = [d for d in days if d < args.day]
        if before:
            prev_high[sym] = days[max(before)][1]
    bars = load_bars(folder, set(args.symbols.split(",")) if args.symbols else None)
    if not bars:
        sys.exit("no bar files in %s" % folder)

    out = REPO / "replay" / "out"
    out.mkdir(exist_ok=True)
    stem = "%s_%s_%s" % (args.day, Path(args.bot).stem, args.strategy)
    if args.tag:
        stem += "_" + args.tag
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = logging.FileHandler(out / (stem + ".log"), mode="w")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    fmt.converter = lambda secs: datetime.fromtimestamp(secs, ET).timetuple()
    fh.setFormatter(fmt)
    root.addHandler(fh)
    root.setLevel(logging.INFO)
    violations = []

    class Count(logging.Handler):
        def emit(self, record):
            if "SELF-CHECK VIOLATION" in record.getMessage():
                violations.append(record.getMessage())

    root.addHandler(Count())

    start = datetime(day.year, day.month, day.day, 4, 0, tzinfo=ET)
    end = datetime(day.year, day.month, day.day, 20, 0, tzinfo=ET)
    rth_open = datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET)
    clock = Clock(start.astimezone(timezone.utc))
    install_clock(bot, clock)

    market = Market()
    broker = SimBroker(bot, market, clock, args.equity, args.strategy,
                       args.slip_pct / 100)
    strat = getattr(bot, CLASSES[args.strategy])(broker, SimData(
        market, bars, with_volume=hasattr(getattr(bot, "V31", object), "volume_ratio")))

    orig_exit = strat.exit

    async def booked_exit(s, why):
        prev, broker.reason = broker.reason, why
        try:
            await orig_exit(s, why)
        finally:
            broker.reason = prev

    strat.exit = booked_exit

    await strat.roll_day()
    strat.needs_reconcile = False
    await strat.reconcile("startup")

    # Every print of the day, in order, plus each bar's close a minute after
    # it opens. Prints update the market for the scanner whether or not the
    # strategy is subscribed yet; the strategy only sees subscribed names.
    events = []
    for sym, rows in bars.items():
        for b in rows:
            for t, p, sz in prints_for(b):
                events.append((t, 1, sym, (p, sz, b.session)))
            events.append((b.t + timedelta(seconds=60), 0, sym, b))
    events.sort(key=lambda e: (e[0], e[1]))

    rth_open_px, rth_high = {}, {}
    subscribed, pending = {}, set()
    last_flush = None
    timers = {"periodic": 5, "risk": 5, "scan": 8, "close": 20, "dead": 30,
              "reconcile": 60, "subscribe": 2}
    due = {k: start for k in timers}

    async def fire_timers(upto):
        nonlocal last_flush
        while True:
            name = min(due, key=due.get)
            when = due[name]
            if when > upto:
                return
            clock.t = when.astimezone(timezone.utc)
            due[name] = when + timedelta(seconds=timers[name])
            now = clock.ts()
            if name == "scan":                                 # Engine.scanner_loop
                await strat.roll_day()
                if strat.stopped or strat.halted_today:
                    continue
                for sym, last in market.last.items():
                    if when < rth_open:
                        ref = meta.get(sym, {}).get("pre_close", 0)
                        seed = 0.0
                    else:
                        ref = rth_open_px.get(sym, 0)
                        seed = rth_high.get(sym, 0.0)
                    if not ref or not (bot.PRICE_MIN <= last <= bot.PRICE_MAX):
                        continue
                    if last < ref * (1 + bot.GAIN_FROM_OPEN):
                        continue
                    strat.qualified.add(sym)
                    st = strat.st(sym)
                    st.ref_price = meta.get(sym, {}).get("pre_close", 0.0)   # for strategies that read it
                    if hasattr(st, "prev_high"):
                        st.prev_high = prev_high.get(sym, 0.0)
                    st.day_high = max(st.day_high, max(seed, last))
                    if sym not in subscribed:
                        pending.add(sym)
            elif name == "subscribe":                          # MarketData.subscribe_loop
                if pending and (not subscribed or last_flush is None or
                                (when - last_flush).total_seconds()
                                >= bot.SUBSCRIBE_INTERVAL):
                    for sym in pending:
                        subscribed[sym] = when
                    pending.clear()
                    last_flush = when
            elif name == "periodic":                           # Engine.periodic_loop
                if args.no_rebalance:
                    continue
                if not strat.stopped and not strat.halted_today:
                    broker.reason = "rebalance"
                    await strat.periodic()
                    broker.reason = ""
            elif name == "risk":                               # Engine.risk_loop
                if strat.stopped or not strat.day_start_equity:
                    continue
                await strat.self_check()
                if strat.halt_threshold() <= 0:
                    continue
                eq = await broker.equity()
                limit = strat.day_start_equity * (1 - strat.halt_threshold())
                if eq <= limit and not strat.halted_today:
                    logging.getLogger("engine").critical(
                        "[%s] DAILY HALT at equity %.2f", strat.name, eq)
                    strat.halted_today = True
                if strat.halted_today and strat.open_positions():
                    await strat.flatten_all("halted")
            elif name == "dead":                               # Engine.dead_loop
                if not bot.market_is_open() or strat.stopped or strat.halted_today:
                    continue
                for s in list(strat.open_positions()):
                    if not s.last_tick_at:
                        s.last_tick_at = now
                        continue
                    if now - s.last_tick_at >= bot.DEAD_MINUTES * 60:
                        await strat.exit(s, "dead-tape")
            elif name == "close":                              # Engine.close_loop
                hm = (when.astimezone(ET).hour, when.astimezone(ET).minute)
                if hm >= bot.FLATTEN_AT and strat.open_positions():
                    await strat.flatten_all("end-of-day")
            elif name == "reconcile":                          # Engine.reconcile_loop
                await strat.reconcile("periodic")

    for t, kind, sym, payload in events:
        if t >= end:
            break
        await fire_timers(t)
        clock.t = t
        if kind == 1:
            price, size, session = payload
            market.last[sym] = price
            market.session[sym] = session
            if t >= rth_open:
                rth_open_px.setdefault(sym, price)
                rth_high[sym] = max(rth_high.get(sym, 0.0), price)
            if sym in subscribed and t >= subscribed[sym]:
                await tick(strat, strat.st(sym), price, size, clock.ts())
        else:
            if sym in subscribed and t > subscribed[sym]:
                strat.offer_bar(SimpleNamespace(
                    symbol=sym, timestamp=payload.t, open=payload.o,
                    high=payload.h, low=payload.l, close=payload.c,
                    volume=payload.v))
    await fire_timers(end)

    return report(bot, args, broker, strat, subscribed, violations, out, stem,
                  len(bars))


def report(bot, args, broker, strat, subscribed, violations, out, stem,
           n_symbols):
    end_eq = broker._equity()
    pl = end_eq - broker.start
    trips, pos, cur = [], defaultdict(float), {}
    for t, sym, side, q, px, why in broker.fills:
        buy = side == bot.OrderSide.BUY
        if buy and pos[sym] == 0:
            cur[sym] = {"sym": sym, "in": t, "bq": 0, "bc": 0.0, "sq": 0,
                        "sc": 0.0, "adds": -1, "why": []}
        c = cur[sym]
        if buy:
            c["bq"] += q
            c["bc"] += q * px
            c["adds"] += 1
            pos[sym] += q
        else:
            c["sq"] += q
            c["sc"] += q * px
            c["why"].append(why or "?")
            pos[sym] -= q
            if pos[sym] <= 0:
                c["out"] = t
                trips.append(c)
                del cur[sym]

    lines = []
    w = lines.append
    w("")
    w("=" * 92)
    w("%s  %s  replay of %s  (%d symbols in the data, %d subscribed during the day)"
      % (args.strategy, bot.VERSION, args.day, n_symbols, len(subscribed)))
    if args.set or args.no_rebalance:
        w("settings changed: " + ", ".join(
            args.set + (["no rebalance"] if args.no_rebalance else [])))
    w("start $%s  ->  end $%s   P/L %+.2f (%+.2f%%)"
      % (f"{broker.start:,.2f}", f"{end_eq:,.2f}", pl, 100 * pl / broker.start))
    wins = sum(1 for c in trips if c["sc"] - c["bc"] > 0)
    w("%d round trips: %d up / %d down%s"
      % (len(trips), wins, len(trips) - wins,
         ("  (still open: %s)" % ", ".join(cur)) if cur else ""))
    w("-" * 92)
    w("  %-5s %-8s %-8s %7s %5s %9s %9s %10s %7s  %s"
      % ("SYM", "in", "out", "shares", "adds", "avg in", "avg out", "P/L $", "P/L %", "exit"))
    for c in trips:
        bi, so = c["bc"] / c["bq"], c["sc"] / c["sq"]
        w("  %-5s %-8s %-8s %7d %5d %9.4f %9.4f %+10.2f %+6.1f%%  %s"
          % (c["sym"], c["in"].astimezone(ET).strftime("%H:%M:%S"),
             c["out"].astimezone(ET).strftime("%H:%M:%S"), c["bq"], c["adds"],
             bi, so, c["sc"] - c["bc"], 100 * (so / bi - 1),
             ",".join(dict.fromkeys(c["why"]))))
    w("-" * 92)
    mp, msym, mt = broker.max_pos_pct
    w("largest position after a buy: %.1f%% of equity%s"
      % (100 * mp, (" (%s at %s)" % (msym, mt.astimezone(ET).strftime("%H:%M:%S"))) if mt else ""))
    me, met = broker.max_exposure_pct
    w("largest total exposure after a buy: %.1f%% of equity" % (100 * me))
    w("self-check violations logged: %d" % len(violations))
    w("halted: %s" % ("yes" if strat.halted_today else "no"))
    w("full log: replay/out/%s.log" % stem)
    w("=" * 92)
    text = "\n".join(lines)
    (out / (stem + ".txt")).write_text(text + "\n")
    with open(out / (stem + "_fills.csv"), "w", newline="") as f:
        cw = csv.writer(f)
        cw.writerow(["time_et", "symbol", "side", "qty", "price", "reason"])
        for t, sym, side, q, px, why in broker.fills:
            cw.writerow([t.astimezone(ET).strftime("%H:%M:%S"), sym,
                         "BUY" if side == bot.OrderSide.BUY else "SELL", q,
                         round(px, 4), why])
    print(text)
    return pl


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--bot", default="r24.py")
    ap.add_argument("--strategy", default="v31", choices=sorted(CLASSES))
    ap.add_argument("--day", default="2026-10-02")
    ap.add_argument("--equity", type=float, default=30_000.0)
    ap.add_argument("--symbols", default="", help="comma list; default all files")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="override one of the bot's settings for this run, e.g. "
                         "--set V31_FLUSH_DROP_PCT=0.06 (repeatable)")
    ap.add_argument("--tag", default="", help="suffix for the output file names")
    ap.add_argument("--floats", default="replay/data/float.csv",
                    help="float file for bots that size by float ('' = none)")
    ap.add_argument("--slip-pct", type=float, default=0.0,
                    help="stress test: every fill this many %% worse than the "
                         "quote (a buy never past its limit) - a runner's "
                         "real book is far wider than the simulated 0.2%%")
    ap.add_argument("--no-rebalance", action="store_true",
                    help="what-if: never run the strategy's periodic() rebalance")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
