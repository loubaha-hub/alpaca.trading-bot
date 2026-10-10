"""Fire earlier? (the owner, 10-10: "early on the volume is not there yet and
the speed parameters have not been met"). v38 proposed (the re-entry over the
last sale's price, a limit at the ask + 2%, the bot's buy checks, trailing
thirds, $7,500 full) with the speed test's numbers lowered: the speed 0.30 ->
0.25 / 0.20 / 0.15, the move 3% -> 2%, the money $250k -> $150k in 60s.
What firing earlier catches and what it costs - by day, by session, the big
runners, and the speed's first signal in the 40%+ runs.

python3 v38_thresholds.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speedsim as Q
import v38_final as F
import v38_gaps as G
from speedsim_giveback import run_of
from speedsim_study import session, SESSIONS

BIG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"), ("2026-10-08", "FLYE"))
BASE = dict(level="exit", checks=True, limit="2%")
SETS = (("as now: 3%, speed 0.30, $250k", 0.03, 0.30, 250000),
        ("speed 0.25", 0.03, 0.25, 250000),
        ("speed 0.20", 0.03, 0.20, 250000),
        ("speed 0.15", 0.03, 0.15, 250000),
        ("move 2%, speed 0.30", 0.02, 0.30, 250000),
        ("move 2%, speed 0.20", 0.02, 0.20, 250000),
        ("$150k, speed 0.30", 0.03, 0.30, 150000),
        ("$150k, move 2%, speed 0.20", 0.02, 0.20, 150000),
        ("stricter: speed 0.40", 0.03, 0.40, 250000))


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    runs = [(r, run_of(r)) for k in by for r in by[k]]
    runs = [(r, rn) for r, rn in runs if rn and rn[0] - 1 >= 0.40]
    m0, s0, d0 = Q.MOVE_MIN, Q.SPEED, Q.DOLLARS_MIN
    print("FIRING EARLIER - the speed test's numbers (v38 proposed)")
    print("%-30s %4s %3s " % ("", "n", "won") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %6s %7s %6s %6s | %s" % ("TOTAL", "PRE", "RTH", "AFTER", "FRGT", "BIYA", "SBFM", "FLYE",
                                                         "40%+ runs: fired / in the first quarter"))
    for name, mv, sp, dl in SETS:
        Q.MOVE_MIN, Q.SPEED, Q.DOLLARS_MIN = mv, sp, dl
        xs = [x for k in sorted(by) for x in G.play(by[k], bars, **BASE)]
        per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        big = [sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) == b) for b in BIG]
        fired = q1 = 0
        for r, rn in runs:
            st = G.signals(r, checks=True)
            px = {x[0]: x[4] for x in r["S"] if x[4]}
            for kk in sorted(st):
                t = r["start"] + kk
                if rn[1] <= t <= rn[3] and st[kk][0] and px.get(kk):
                    fired += 1
                    q1 += (px[kk] - rn[2]) / (rn[4] - rn[2]) <= 0.25
                    break
        print("%-30s %4d %3d " % (name, len(xs), sum(x[2] > 0 for x in xs)) + " ".join("%+7.0f" % v for v in per) +
              " %+8.0f | %+7.0f %+7.0f %+7.0f | %+6.0f %+7.0f %+6.0f %+6.0f | %d / %d of %d" % (
                  sum(per), *ses, *big, fired, q1, len(runs)))
    Q.MOVE_MIN, Q.SPEED, Q.DOLLARS_MIN = m0, s0, d0


if __name__ == "__main__":
    main()
