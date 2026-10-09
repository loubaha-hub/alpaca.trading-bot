"""The speed strategy with the ease-in, filtered by the day's top names (10-09).

python3 speedsim_ranked.py <folder> - the folder holds replay/data/2026-10-06,
2026-10-07 and daily_listed_2026-07-01_10-05.json from claude/zealous-ramanujan-br3gay
(git archive origin/claude/zealous-ramanujan-br3gay replay/data/... | tar -x -C <folder>).
94 of 206 signals have no previous close in this data (names not recorded the day
before): the up-10% and gainer filters drop them; the crowd filter does not need it."""
import sys, os
sys.path.insert(0, "/home/user/alpaca.trading-bot/replay/research")
import speedsim as Q, secsim as S
from ranks import Ranks
SP = sys.argv[1]
R = Ranks(SP + "/bars1006/replay/data", "/home/user/alpaca.trading-bot/replay/live/2026-10-08_secdump/bars",
          SP + "/bars1006/replay/data/daily_listed_2026-07-01_10-05.json", ["2026-10-06", "2026-10-07", "2026-10-08"])
W = S.load_windows("/home/user/alpaca.trading-bot/replay/live/2026-10-08_secdump/windows")
data = [(r, S.Path(r), Q.signals(r)) for l in W.values() for r in l]
nsig = sum(len(s) for _, _, s in data)
FILTERS = {
    "no filter": lambda c, g, x: True,
    "up 10%+": lambda c, g, x: x >= 0.10,
    "crowd top 3 + up 10%": lambda c, g, x: c <= 3 and x >= 0.10,
    "gainer top 3": lambda c, g, x: g <= 3,
    "crowd OR gainer top 3": lambda c, g, x: (c <= 3 and x >= 0.10) or g <= 3,
    "crowd AND gainer top 3": lambda c, g, x: c <= 3 and g <= 3,
}
print("speed signals %d; ranks: 10-06 %d names, 10-07 %d, 10-08 %d (traded names only)" % (
    nsig, len({s for m in R.by_day['2026-10-06'].values() for s in m}),
    len({s for m in R.by_day['2026-10-07'].values() for s in m}),
    len({s for m in R.by_day['2026-10-08'].values() for s in m})))
print("%-24s %-14s %6s %6s %4s %10s %11s  %s" % ("filter", "stop / half", "signals", "trades", "won", "P/L", "w/o SXTC", "by day"))
for fname, f in FILTERS.items():
    for su, arm in ((0.0, 0.01), (0.03, 0.10), (0.05, 0.10), (0.05, 0.05), (0.10, 0.10)):
        rows, kept = [], 0
        per = {}
        for r, p, sg in data:
            keep = [x for x in sg if f(*R.at(r["day"], r["sym"], x[0]))]
            kept += len(keep)
            for tr in Q.play_ladder(p, keep, 4000, su, arm, True):
                rows.append((r["day"], r["sym"], tr))
                per[r["day"]] = per.get(r["day"], 0.0) + tr[4]
        tot = sum(x[2][4] for x in rows)
        sx = sum(x[2][4] for x in rows if x[1] == "SXTC" and x[0] == "2026-10-07")
        won = sum(x[2][4] > 0 for x in rows)
        print("%-24s %2.0fc / %2.0fc     %6d %6d %4d %+10.2f %+11.2f  %s" % (
            fname, 100*su, 100*arm, kept, len(rows), won, tot, tot - sx,
            "  ".join("%s %+.0f" % (d[5:], per[d]) for d in sorted(per))))
    print()
