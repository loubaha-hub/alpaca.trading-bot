"""The minute-wide floor everywhere? (the owner, 10-10: "it wins hands down ...
the swing is not even bigger - why don't we adopt that?"). The one place the
3c floor did better is premarket - but it trades four times as often, and the
replay's fills are kind. Both floors with the sales filled 0 / 1c / 2c under
the bid, by session, with and without BIYA; the worst day.

python3 v38_floor_friction.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    bid0 = S.Path.bid_at
    print("THE TWO FLOORS WITH WORSE SALES (v38 speed only, no level, the ask + the scale)")
    print("%-34s %4s %8s %8s | %8s %8s %8s | %8s | %s" % ("", "n", "TOTAL", "no BIYA", "PRE", "RTH", "AFTER",
          "PRE noB", "the days"))
    for c in (0.0, 0.01, 0.02):
        S.Path.bid_at = lambda self, t, c=c: (lambda b: b - c if b else b)(bid0(self, t))
        for fl, name in (("3c", "3c floor"), ("candle", "minute-wide floor")):
            xs = [x for k in sorted(by) for x in G.play(by[k], bars, level="none", checks=True, limit="scale", speed_floor=fl)]
            nob = [x for x in xs if (x[0]["day"], x[0]["sym"]) != ("2026-10-07", "BIYA")]
            ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
            per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
            print("%-34s %4d %+8.0f %+8.0f | %+8.0f %+8.0f %+8.0f | %+8.0f | %s" % (
                "sales %dc under the bid, %s" % (round(100 * c), name), len(xs), sum(x[2] for x in xs),
                sum(x[2] for x in nob), *ses, sum(x[2] for x in nob if session(x[1]) == "PRE"),
                " ".join("%+7.0f" % v for v in per)))
    S.Path.bid_at = bid0


if __name__ == "__main__":
    main()
