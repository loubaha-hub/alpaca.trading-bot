"""What v38's floor reads, and how it holds when the sales fill worse (10-09 night).

v38 as tested: the floor 3c under the fill (under the average after the adds),
hit by a print or the bid-ask midpoint at or under it. A premarket spread is
often wider than 6c, so the midpoint can sit under the floor the moment the
buy fills: 71% of v38's losers were out within 5 seconds (median 1s).

Variants of the floor (the trailing thirds, $7,500 full, unchanged otherwise):
  mid    a print or the midpoint at the floor (as tested)
  print  only a print at the floor
  bid    only the bid at the floor (what can really be sold)
  3%/5%  the floor 3% / 5% under the average (a price-based floor), on a print
and each with the sales filled 0 / 1c / 2c under the bid (a premarket sale is
a limit under the bid; the buys stay at the ask - a limit at the ask fills
there or not at all). Every table by day and by session.

python3 v38_floor.py <new windows> <old windows> <old minute bars>"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
from speedsim_study import session, SESSIONS

FLOORS = (("mid (as tested)", dict()),
          ("print", dict(mid_stop=False)),
          ("bid", dict(stop_bid=True)),
          ("3% under, print", dict(mid_stop=False, stop_pct=0.03)),
          ("5% under, print", dict(mid_stop=False, stop_pct=0.05)))


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    F.FULL = 7500.0
    bid0 = S.Path.bid_at
    days = sorted({r["day"] for k in by for r in by[k]})
    print("v38 (trailing thirds, $7,500 full) - WHAT THE FLOOR READS, and the sales filled worse")
    print("%-34s %4s %3s " % ("", "n", "won") + " ".join("%8s" % d[5:] for d in days) +
          " %9s | %8s %8s %8s | %9s %6s" % ("TOTAL", "PRE", "RTH", "AFTER", "top three", "<=5s"))
    for c in (0.0, 0.01, 0.02):
        S.Path.bid_at = lambda self, t, c=c: (lambda b: b - c if b else b)(bid0(self, t))
        for name, kw in FLOORS:
            base = [x for k in sorted(by) for x in F.play_day(by[k], "A", dict(tiers=F.TIERS, **kw))]
            per = [sum(x[2] for x in base if x[0]["day"] == d) for d in days]
            ses = [sum(x[2] for x in base if session(x[1]) == s) for s in SESSIONS]
            top = sum(sorted((x[2] for x in base), reverse=True)[:3])
            lose = [x for x in base if x[2] <= 0]
            fast = 100 * sum(x[6] - x[1] <= 5 for x in lose) / max(1, len(lose))
            print("%-34s %4d %3d " % ("sales %dc under the bid, %s" % (round(100 * c), name), len(base),
                                      sum(x[2] > 0 for x in base)) +
                  " ".join("%+8.0f" % v for v in per) +
                  " %+9.0f | %+8.0f %+8.0f %+8.0f | %+9.0f %5.0f%%" % (sum(per), *ses, top, fast))
        print()


if __name__ == "__main__":
    main()
