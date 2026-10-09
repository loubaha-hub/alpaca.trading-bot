"""v38's swings (the owner, 10-09 ~8pm: the trailing exit lost $1,918 on 10-08 -
"too big a loss on a small account ... keep the bottom line while reducing the
gyration"). Day by day and by session, on the same windows as v38_final.py:

  tiers               - the owner's trailing exit as built
  line, then tiers    - the half-back line banks a small gain until the position
                        is up 20% (or 10%, 30%); the tiers from there
  day limit $X        - no new v38 buy once the day's closed trades are down $X
  2 losses a stock    - no new buy on a stock after 2 losing trades on it that day
                        that did not reach +10%... (simply: 3 losers in a row)

python3 v38_swings.py <new windows> <old windows> <old minute bars>"""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
from speedsim_study import session, SESSIONS
import v38_final as F


def day_limited(trades, limit):
    """Drop the entries made after the day's closed trades were down `limit`."""
    out = []
    by = defaultdict(list)
    for x in trades:
        by[x[0]["day"]].append(x)
    for d, xs in by.items():
        xs.sort(key=lambda x: x[1])
        closed = []                                   # (exit time, P/L)
        for x in xs:
            done = sum(pl for te, pl in closed if te <= x[1])
            if done <= -limit:
                continue
            out.append(x)
            closed.append((x[6], x[2]))
    return out


def stock_limited(trades, n):
    """No new buy on a stock after n losing trades in a row on it that day."""
    out = []
    by = defaultdict(list)
    for x in trades:
        by[(x[0]["day"], x[0]["sym"])].append(x)
    for k, xs in by.items():
        xs.sort(key=lambda x: x[1])
        streak = 0
        for x in xs:
            if streak >= n:
                break
            out.append(x)
            streak = streak + 1 if x[2] <= 0 else 0
    return out


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    days = sorted({d for d, _ in by})
    T = F.TIERS
    runs = {}
    for name, kw in (("v38 as decided", dict(F.BASE)), ("tiers", dict(tiers=T)),
                     ("line, then tiers at +10%", dict(tiers=T, tiers_from=0.10)),
                     ("line, then tiers at +20%", dict(tiers=T, tiers_from=0.20)),
                     ("line, then tiers at +30%", dict(tiers=T, tiers_from=0.30))):
        runs[name] = [x for k in sorted(by) for x in F.play_day(by[k], "A", kw)]
    base = runs["tiers"]
    runs["tiers, day limit $500"] = day_limited(base, 500)
    runs["tiers, day limit $750"] = day_limited(base, 750)
    runs["tiers, day limit $1,000"] = day_limited(base, 1000)
    runs["tiers, 3 losers in a row a stock"] = stock_limited(base, 3)
    lt = runs["line, then tiers at +20%"]
    runs["line+tiers 20%, day limit $750"] = day_limited(lt, 750)
    runs["line+tiers 20%, 3 losers a stock"] = stock_limited(lt, 3)
    print("v38 SWINGS - full position $%.0f; a cell: trades, P/L" % F.FULL)
    print("%-36s " % "" + " ".join("%13s" % d[5:] for d in days) + " %13s | %10s %10s %10s | %9s %9s" % (
        "TOTAL", "PRE", "RTH", "AFTER", "worst day", "best day"))
    for name, xs in runs.items():
        per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
        cnt = [sum(1 for x in xs if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        print("%-36s " % name + " ".join("%4d %+8.0f" % (c, v) for c, v in zip(cnt, per)) +
              " %4d %+8.0f | %+10.0f %+10.0f %+10.0f | %+9.0f %+9.0f" % (len(xs), sum(per), *ses, min(per), max(per)))
    print("\n10-08 under the tiers, by stock (the day it lost):")
    agg = defaultdict(lambda: [0, 0.0])
    for x in base:
        if x[0]["day"] == "2026-10-08":
            agg[x[0]["sym"]][0] += 1; agg[x[0]["sym"]][1] += x[2]
    for sym, (n, v) in sorted(agg.items(), key=lambda kv: kv[1][1]):
        print("  %-6s %3d trades %+8.0f" % (sym, n, v))


if __name__ == "__main__":
    main()
