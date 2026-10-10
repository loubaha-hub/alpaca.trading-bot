"""The re-entry level, stressed (10-09 night): v38 with the trailing thirds,
re-entries at speed over (a) the day's high (as decided), (b) the price of
v38's last sale of the stock, (c) no level - each with the sales filled 0 / 1c
/ 2c under the bid, and with the bot's own buy checks (spread 10c, up 5s).
By day, by session, the trades, the wins, and the days without BIYA 8:20.

python3 v38_levels.py <new windows> <old windows> <old minute bars>"""
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
    print("v38 RE-ENTRY LEVEL, STRESSED - trailing thirds, $7,500 full, the bot's buy checks on")
    print("%-38s %4s %3s " % ("", "n", "won") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %8s %7s" % ("TOTAL", "PRE", "RTH", "AFTER", "no BIYA", "per tr"))
    for c in (0.0, 0.01, 0.02):
        S.Path.bid_at = lambda self, t, c=c: (lambda b: b - c if b else b)(bid0(self, t))
        for name, lvl in (("the day's high", "day"), ("the last sale's price", "exit"), ("no level", "none")):
            xs = [x for k in sorted(by) for x in G.play(by[k], bars, level=lvl, checks=True)]
            per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
            ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
            nob = sum(x[2] for x in xs if not (x[0]["sym"] == "BIYA" and x[0]["day"] == "2026-10-07"))
            print("%-38s %4d %3d " % ("%dc under the bid, %s" % (round(100 * c), name), len(xs), sum(x[2] > 0 for x in xs)) +
                  " ".join("%+7.0f" % v for v in per) +
                  " %+8.0f | %+7.0f %+7.0f %+7.0f | %+8.0f %+7.1f" % (sum(per), *ses, nob, sum(per) / max(1, len(xs))))
        print()


if __name__ == "__main__":
    main()
