"""The owner's cushion over the ask, scaled to the speed (10-10): "two, three,
four, five, six, ten cents even above the ask, depending on the speed of the
stock - if the speed is extreme, even 20 cents ... a scale" - so the fast ones
do not leave without us.

v38 proposed (no re-entry level, the bot's buy checks, trailing thirds, $7,500
full). The first buy's limit: the ask at the decision plus a cushion - fixed
(0 / 2c / 2%) or scaled to the speed at that second (2c under 0.5, 5c from
0.5, 10c from 1, 20c from 2; never over 5% of the price). Two ends of the
price: (a) filled at the ask whenever the ask a second later is inside the
limit (kind - the cushion only decides what is missed); (b) every fill pays
the whole cushion (unkind), the floor kept 3c under the market. Plus, for
the record, how fast the speed was at the first signal of each big runner.

python3 v38_cushion.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS

BIG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"), ("2026-10-08", "FLYE"), ("2026-10-07", "SXTC"))


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    print("THE CUSHION OVER THE ASK, SCALED TO THE SPEED (v38 proposed: no re-entry level, the bot's buy checks)")
    print("%-44s %4s %3s %5s " % ("", "n", "won", "miss") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %s" % ("TOTAL", "PRE", "RTH", "AFTER", "  ".join("%-5s" % b[1] for b in BIG)))
    for name, kw in (("no ceiling (the old replay)", dict(limit=None)),
                     ("a limit at the ask", dict(limit=0.0)),
                     ("the ask + 2c", dict(limit=0.02)),
                     ("the ask + 2%", dict(limit="2%")),
                     ("the ask + the speed's scale", dict(limit="scale")),
                     ("the ask + 2c, paying it all", dict(limit=0.02, pay_all=True)),
                     ("the ask + 2%, paying it all", dict(limit="2%", pay_all=True)),
                     ("the ask + the speed's scale, paying it all", dict(limit="scale", pay_all=True))):
        miss = []
        xs = [x for k in sorted(by) for x in G.play(by[k], bars, level="none", checks=True, misses=miss, **kw)]
        per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        big = [sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) == b) for b in BIG]
        print("%-44s %4d %3d %5d " % (name, len(xs), sum(x[2] > 0 for x in xs), len(miss)) +
              " ".join("%+7.0f" % v for v in per) +
              " %+8.0f | %+7.0f %+7.0f %+7.0f | %s" % (sum(per), *ses, " ".join("%+6.0f" % v for v in big)))
    # the speed at the first signal of the big runners' winning trades, and the cushion the scale gives
    print("\nTHE SPEED AT THE BIG RUNNERS' BUYS (the trades that won $500+, no ceiling):")
    xs = [x for k in sorted(by) for x in G.play(by[k], bars, level="none", checks=True)]
    for x in sorted(xs, key=lambda x: -x[2]):
        if x[2] < 500:
            break
        r = x[0]
        k = int(x[1] - S.BUY_LAG - r["start"])
        sv = G.speed_values(r).get(k, 0.0)
        a0 = S.Path(r).ask_at(x[1] - S.BUY_LAG)
        print("  %s %-5s %s  speed %5.2f  ask $%.2f  the scale's cushion %.2fc  P/L %+.0f" % (
            r["day"][5:], r["sym"], datetime.fromtimestamp(x[1], S.ET).strftime("%H:%M:%S"), sv, a0,
            100 * G.cushion(sv, a0), x[2]))


if __name__ == "__main__":
    main()
