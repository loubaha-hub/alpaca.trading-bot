"""v24 ("buy everything, tight stop, reclaim to re-enter", droplet 09-15)
replayed on recorded 1-minute bars. Written from v24's rules, not its code.

usage: python3 -I v24sim.py DAY_DIR MODE COST
  MODE  A = as built: fills at the decision price (bar close / the exact
            reclaim level), pooled equal split re-done on every buy/sell,
            no halt
        B = honest fills: each decision fills at the next minute's open,
            fills COST worse (e.g. 0.002), 10% halt; rules as built
        C = B with no re-splitting: each buy takes 10% of the account
Prints one JSON line: the day's numbers.
"""
import csv
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
CAPITAL = 30000.0
GAP = 0.10              # on the gap list: up 10%+ on the prior close
PMIN, PMAX = 1.0, 20.0
GIVEBACK = 0.10         # stage 2: sell on giving back 10% of the gain
HALT = 0.10
SLOT = 0.10             # mode C: each buy takes 10% of the account


def load(day_dir):
    meta = json.load(open(os.path.join(day_dir, "meta.json")))
    bars = {}
    for f in sorted(os.listdir(day_dir)):
        if not f.endswith(".csv"):
            continue
        sym = f[:-4]
        rows = []
        for r in csv.DictReader(open(os.path.join(day_dir, f))):
            t = datetime.strptime(r["time"], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(ET)
            if not (4 <= t.hour < 20):
                continue
            rows.append((t, float(r["open"]), float(r["high"]), float(r["low"]),
                         float(r["close"])))
        if rows and meta.get(sym, {}).get("pre_close"):
            bars[sym] = rows
    return meta, bars


class Sym:
    def __init__(self, name):
        self.name = name
        self.popped = False
        self.held = False
        self.shares = 0
        self.cost = 0.0          # average cost of the shares held
        self.stage_entry = None  # this cycle's entry price (the stop reference)
        self.peak = None
        self.watch = None        # stopped out: re-buy above this
        self.last = None         # last known price
        self.cycle_pnl = 0.0
        self.pending = None      # mode B/C: "buy" or "sell" at the next open


def run(day_dir, mode, cost):
    meta, bars = load(day_dir)
    honest = mode in ("B", "C", "N")       # N = honest fills, no costs, no halt
    c = cost if honest else 0.0
    syms = {s: Sym(s) for s in bars}
    events = sorted((row[0], s, i) for s, rows in bars.items() for i, row in enumerate(rows))
    cash = CAPITAL
    st = {"trades": [], "orders": 0, "traded": 0.0, "halted": False}

    def buy(s, n, px):
        nonlocal cash
        if n <= 0:
            return
        fill = px * (1 + c)
        s.cost = (s.cost * s.shares + fill * n) / (s.shares + n)
        s.shares += n
        cash -= fill * n
        st["orders"] += 1
        st["traded"] += fill * n

    def sell(s, n, px):
        nonlocal cash
        n = min(n, s.shares)
        if n <= 0:
            return
        fill = px * (1 - c)
        s.cycle_pnl += (fill - s.cost) * n
        s.shares -= n
        cash += fill * n
        st["orders"] += 1
        st["traded"] += fill * n

    def end_cycle(s):
        st["trades"].append(round(s.cycle_pnl, 2))
        st.setdefault("by", []).append((round(s.cycle_pnl, 2), s.name, s.stage_entry))
        s.cycle_pnl = 0.0
        s.held = False
        s.shares = 0
        s.cost = 0.0

    def rebalance():
        """As built: every held name trimmed or topped up to an equal split."""
        held = [x for x in syms.values() if x.held]
        if not held:
            return
        target = CAPITAL / len(held)
        for x in held:
            if not x.last or x.last <= 0:
                continue
            want = int(target // x.last)
            if want < x.shares:
                sell(x, x.shares - want, x.last)
                if x.shares == 0:
                    end_cycle(x)          # trimmed to nothing: out, no re-buy level
            elif want > x.shares:
                buy(x, want - x.shares, x.last)

    def enter(s, px):
        s.held = True
        s.stage_entry = px
        s.peak = px
        s.watch = None
        s.cycle_pnl = 0.0
        s.last = px
        if mode == "C":
            n = int(min(CAPITAL * SLOT, max(cash, 0.0)) // (px * (1 + c)))
            if n <= 0:
                s.held = False
                return
            buy(s, n, px)
        else:
            rebalance()
            if s.held and s.shares == 0:   # the split gave it nothing
                s.held = False

    def exit_(s, px, watch):
        sell(s, s.shares, px)
        end_cycle(s)
        s.watch = watch
        if mode != "C":
            rebalance()

    def equity():
        return cash + sum(x.shares * (x.last or 0) for x in syms.values() if x.held)

    def flatten():
        for x in syms.values():
            if x.held:
                sell(x, x.shares, x.last)
                end_cycle(x)
                x.watch = None

    for t, name, i in events:
        s = syms[name]
        o, h, l, cl = bars[name][i][1:]
        pre = meta[name]["pre_close"]
        if st["halted"]:
            continue
        # mode B/C: what was decided on the last bar fills at this bar's open
        if s.pending:
            kind, watch = s.pending
            s.pending = None
            if kind == "buy" and not s.held:
                enter(s, o)
            elif kind == "sell" and s.held:
                s.last = o
                exit_(s, o, watch)
        s.last = cl
        if not s.held:
            if not s.popped:
                if PMIN <= cl <= PMAX and cl >= pre * (1 + GAP):
                    s.popped = True
                    if honest:
                        s.pending = ("buy", None)
                    else:
                        enter(s, cl)
            elif s.watch is not None and h > s.watch:
                if honest:
                    s.pending = ("buy", None)
                else:
                    w = s.watch
                    enter(s, w)               # as built: filled AT the reclaim level
                    s.last = cl
            continue
        s.peak = max(s.peak, h)
        gained = s.peak > s.stage_entry
        stop, watch = False, None
        if not gained and cl < s.stage_entry:
            stop, watch = True, s.stage_entry
        elif gained and cl < s.peak - (s.peak - s.stage_entry) * GIVEBACK:
            stop, watch = True, s.peak
        if stop:
            if honest:
                s.pending = ("sell", watch)
            else:
                exit_(s, cl, watch)
        if mode in ("B", "C") and equity() <= CAPITAL * (1 - HALT):
            flatten()
            st["halted"] = True
    flatten()                                  # 8pm: nothing carried overnight
    tr = st["trades"]
    return {"day": os.path.basename(day_dir.rstrip("/")), "mode": mode, "cost": cost,
            "trades": len(tr), "wins": sum(1 for x in tr if x > 0),
            "losses": sum(1 for x in tr if x <= 0), "pnl": round(cash - CAPITAL, 2),
            "orders": st["orders"], "traded": round(st["traded"]),
            "best": max(tr) if tr else 0, "worst": min(tr) if tr else 0,
            "halted": st["halted"],
            "top": sorted(st.get("by", []))[-3:], "bottom": sorted(st.get("by", []))[:2]}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], sys.argv[2], float(sys.argv[3]))))
