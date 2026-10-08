"""Exit rules replayed on the second-by-second read (SEC_DUMP, r34.34): every
live buy of v36, v36b and v37 on 10-06/07/08, the same entry for every rule.

The price path: every print (and bid / ask change) from 30 seconds before a buy
to a minute after it; one row a second for the rest (open, high, low, close, the
bid and ask as the second ended). A sale is priced at the bid SELL_LAG seconds
after the decision; a buy at the ask BUY_LAG seconds after its signal, never
more than the signal's ask + 20c (the fast buy's limit) - else no fill.

A rule is a stop under the fill plus a sell line from the best price since the
buy (the line only rises). Each entry is one position (the live adds are not
replayed); "live" is the round trip's real P/L, adds included."""
import glob, gzip, json, os
from bisect import bisect_left
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SELL_LAG = 0.5
PRINT_TOL_CENTS, PRINT_TOL_PCT = 0.02, 0.005   # as V37_PRINT_CHECK: a print off the market decides nothing
BUY_LAG = 1.0
import importlib.util, sys
_spec = importlib.util.spec_from_file_location(
    "r34bot", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "r34.py"))
_bot = importlib.util.module_from_spec(_spec)
sys.modules["r34bot"] = _bot
_spec.loader.exec_module(_bot)
qualifies = _bot.qualifies                    # the bot's own: which prints count


def ts(day, hms):
    return datetime.fromisoformat(f"{day}T{hms}").replace(tzinfo=ET).timestamp()


class Path:
    """One window's prices in time order: [(t, price, bid, ask)]; prints where
    the read has them, else four synthetic prints a second from the row."""

    def __init__(self, rec):
        self.day, self.sym, self.start = rec["day"], rec["sym"], rec["start"]
        self.end = rec["end"]
        if rec.get("missing"):                    # a gap in the read: the path ends there
            self.end = min(self.end, self.start + min(rec["missing"]))
            cut = min(rec["missing"])
            rec = dict(rec, T=[r for r in rec["T"] if r[0] < cut * 1000],
                       Q=[r for r in rec["Q"] if r[0] < cut * 1000],
                       S=[r for r in rec["S"] if r[0] < cut])
        a = self.start
        tick_secs = {int(r[0] // 1000) for r in rec["T"]}
        ev = []
        for r in rec["Q"]:
            ev.append((a + r[0] / 1000, 0, None, r[1], r[2]))
        for r in rec["T"]:
            if qualifies(r[3]):
                ev.append((a + r[0] / 1000, 1, r[1], None, None))
        bid = ask = None
        for r in rec["S"]:
            k = r[0]
            if r[7] and r[8]:
                bid, ask = r[7], r[8]
            if k in tick_secs or not r[1]:
                if not r[1] and r[7] and k not in tick_secs:
                    ev.append((a + k + 0.99, 0, None, r[7], r[8]))
                continue
            o, h, l, c = r[1], r[2], r[3], r[4]
            mid = (h, l) if c < o else (l, h)            # a down second: the high first
            for i, p in enumerate((o, mid[0], mid[1], c)):
                ev.append((a + k + 0.2 * i + 0.01, 1, p, None, None))
            if r[7] and r[8]:
                ev.append((a + k + 0.99, 0, None, r[7], r[8]))
        ev.sort(key=lambda e: (e[0], e[1]))
        out, bid, ask = [], None, None
        for t, kind, p, b, k in ev:
            if kind == 0:
                if b and k:
                    bid, ask = b, k
                continue
            out.append((t, p, bid, ask))
        self.ev = out
        self.times = [e[0] for e in out]

    def at(self, t):
        return bisect_left(self.times, t)

    def bid_at(self, t):
        """The bid at time t (the last one known), else the last price."""
        i = max(0, self.at(t + 1e-6) - 1)
        e = self.ev[min(i, len(self.ev) - 1)]
        return e[2] or e[1]

    def ask_at(self, t):
        i = max(0, self.at(t + 1e-6) - 1)
        e = self.ev[min(i, len(self.ev) - 1)]
        return e[3] or e[1]


def cut(c):
    return lambda fill, best: best - c


def tiers(lead=0.05, k=1.0, top="fifth"):
    def line(fill, best):
        g = best - fill
        if g < lead * k:
            return best - lead
        if g < 0.20 * k:
            return fill
        if g < 0.50 * k:
            return fill + g / 2
        if g < 1.00 * k:
            return fill + g * 2 / 3
        return best - (g / 5 if top == "fifth" else top)
    return line


def cut_then_tiers(intro=0.05, until=0.10):
    """The owner's ladder on top of the cents cut: `intro` under the best until
    the gain reaches `until`; then never under the buy price up to +20c, half
    the gain kept from +20c, two thirds from +50c, all but a fifth from +$1.
    The line never comes down (run() keeps the highest)."""
    def line(fill, best):
        g = best - fill
        if g < until - 1e-9:
            return best - intro
        if g < 0.20:
            return fill
        if g < 0.50:
            return fill + g / 2
        if g < 1.00:
            return fill + g * 2 / 3
        return best - g / 5
    return line


def furious(even_at=0.30, back=0.30):
    """v36's furious exit: nothing until up 30c, then the buy price or 30% of
    the gain back, whichever is higher."""
    def line(fill, best):
        if best - fill < even_at - 1e-9:
            return -1.0
        return max(fill, fill + (1 - back) * (best - fill))
    return line


def stop_cents(c):
    return lambda fill: fill - c


def stop_pct(p):
    return lambda fill: fill * (1 - p)


def run(path, t0, fill, shares, stop_fn, line_fn):
    """One position from t0 at `fill`: (exit time, exit price, why, best)."""
    stop = stop_fn(fill)
    best, line = fill, -1.0
    i = path.at(t0)
    for t, p, b, a in path.ev[i:]:
        if b and a:
            tol = max(PRINT_TOL_CENTS, PRINT_TOL_PCT * p)
            if p > a + tol or p < b - tol:
                continue                          # not the market (V37_PRINT_CHECK)
        best = max(best, p)
        line = max(line, line_fn(fill, best))
        if p <= stop + 1e-9 or (b and a and (b + a) / 2 <= stop + 1e-9):   # BID_STOP: the middle too
            return t, path.bid_at(t + SELL_LAG), "stop", best
        if p <= line + 1e-9 and not (b and b > line + 1e-9):              # the bid agrees
            return t, path.bid_at(t + SELL_LAG), "line", best
    last = path.ev[-1]
    return last[0], last[2] or last[1], "open", best


def rebuy_signal(path, after, hod, plus=0.05):
    """The first print at the day's high (as the path has it) + plus after
    `after`: (signal time, fill at the ask BUY_LAG later) or None."""
    i = path.at(after)
    high = hod
    for t, p, b, a in path.ev[i:]:
        if p >= high + plus - 1e-9 and a:
            fill = path.ask_at(t + BUY_LAG)
            if fill <= a + 0.20 + 1e-9:
                return t + BUY_LAG, max(fill, 0.01)
        high = max(high, p)
    return None


def load_windows(d):
    out = {}
    for f in sorted(glob.glob(os.path.join(d, "*.json.gz"))):
        rec = json.load(gzip.open(f, "rt"))
        out.setdefault((rec["day"], rec["sym"]), []).append(rec)
    return out


def path_for(windows, paths, day, sym, t):
    for rec in windows.get((day, sym), []):
        end = rec["start"] + min(rec["missing"]) if rec.get("missing") else rec["end"]
        if rec["start"] <= t <= end - 60:      # at least a minute of data after the buy
            key = (day, sym, rec["start"])
            if key not in paths:
                paths[key] = Path(rec)
            return paths[key]
    return None
