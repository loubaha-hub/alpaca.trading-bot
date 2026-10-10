"""The clean A/B (the owner, 10-10): speed entries WITH scouts against speed
entries WITHOUT scouts - nothing else different. Both: the speed buy to 10%,
25% at +10c, 50% at +20c (v38's ladder), a limit at the ask + the speed's
scale, the same floor, the trailing thirds, no re-entry level. A: a 1% (or 2%)
scout floats under a running stock (up 20% from its low, near its high,
$250k a minute) and the speed buys go on top of it, at any price. Done twice:
the 3c floor everywhere, and the last candle's low everywhere. Every 40%+ run
where A and B differ is listed.

python3 v38_scout_ab.py <new windows> <old windows> <old minute bars>"""
import os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
import v38_scout4 as V
from speedsim_giveback import run_of
from speedsim_study import session, SESSIONS

TOP3 = (("2026-10-07", "BIYA"), ("2026-10-06", "FRGT"), ("2026-10-07", "SBFM"))


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    F.FULL = 7500.0
    V.SPEED_LOT = {1: 0.10, 2: 0.25, 3: 0.50}      # exactly v38's ladder
    V.SPEED_NEEDS_ABOVE = False                    # the speed adds whenever the speed fires, as v38
    drop = os.environ.get("V38_DROP")              # e.g. 2026-10-07:BIYA - that stock-day left out
    if drop:
        by = {k: v for k, v in by.items() if k != tuple(drop.split(":"))}
    runs = [(r, rn) for k in by for r in by[k] for rn in [run_of(r)] if rn and rn[0] - 1 >= 0.40]
    print("THE CLEAN A/B - speed entries with scouts vs without, nothing else different%s" % (
        " - WITHOUT %s" % drop if drop else ""))
    print("%-44s %4s %8s %8s %8s | %7s %7s %7s | %s" % ("", "n", "TOTAL", "no BIYA", "no top3", "PRE", "RTH", "AFTER",
          "the scouts' own P/L / the 39 runs made money on"))
    for floor, fname in (("3c", "the 3c floor everywhere"), ("candle", "the last candle's low everywhere")):
        V.SPEED_FLOOR = floor
        fm = "avg" if floor == "3c" else "candle"
        print("\n== %s ==" % fname)
        res = {}
        for name, kw in (("B: speed entries, no scouts", dict()),
                         ("A: speed entries + a 1% scout under them", dict(scout=0.01, floor_mode=fm)),
                         ("A: speed entries + a 2% scout under them", dict(scout=0.02, floor_mode=fm))):
            xs = [x for k in sorted(by) for x in V.play(by[k], **kw)]
            res[name] = xs
            nob = [x for x in xs if (x[0]["day"], x[0]["sym"]) != TOP3[0]]
            no3 = [x for x in xs if (x[0]["day"], x[0]["sym"]) not in TOP3]
            ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
            made = sum(sum(x[2] for x in xs if x[0] is r) > 0 for r, rn in runs)
            sc = [x for x in xs if x[3] == "scout"]
            print("%-44s %4d %+8.0f %+8.0f %+8.0f | %+7.0f %+7.0f %+7.0f | %s %d of %d" % (
                name, len(xs), sum(x[2] for x in xs), sum(x[2] for x in nob), sum(x[2] for x in no3), *ses,
                ("%3d scouts %+6.0f |" % (len(sc), sum(x[2] for x in sc))) if sc else "                 |",
                made, len(runs)))
        a, b = res["A: speed entries + a 1% scout under them"], res["B: speed entries, no scouts"]
        print("  the 40%+ runs where A (1% scout) and B differ by $25 or more:")
        n = 0
        for r, rn in runs:
            pa = sum(x[2] for x in a if x[0] is r)
            pb = sum(x[2] for x in b if x[0] is r)
            psc = sum(x[2] for x in a if x[0] is r and x[3] == "scout")
            if abs(pa - pb) >= 25:
                n += 1
                print("    %s %-5s %-5s run %4.0f%%: without scouts %+7.0f, with %+7.0f (the scout itself %+5.0f)" % (
                    r["day"][5:], r["sym"], session(rn[1]), 100 * (rn[0] - 1), pb, pa, psc))
        if not n:
            print("    none")


if __name__ == "__main__":
    main()
