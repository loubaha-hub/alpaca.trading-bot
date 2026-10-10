"""v38's first buy as a REAL LIMIT (the owner, 10-10: "willing to go ten, twenty
cents above the ask not to lose the big runners" - but in a thin premarket the
many quick losers pay it too).

The replay so far filled every first buy at the ask one second after the
signal, whatever it was - a limit with no ceiling. Here the limit is the ask the
bot reads at the decision plus 0 / 2c / 5c / 10c / 20c; when the ask one second
later is past it, no fill - the next speed signal tries again at its own ask.
The fill, when it comes, is at the ask (the offers there, enough of them -
kind: a real one can sweep up to the limit; the cost of that is the "paying
up" rows of v38_fills.txt). The adds stay at any price (decided). So this
measures what each limit MISSES, not what it costs on the fills.

python3 v38_limits.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS

BIG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"))


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    print("v38's FIRST BUY AS A REAL LIMIT - what it misses (trailing thirds, $7,500 full, the bot's buy checks)")
    print("%-34s %4s %3s %5s " % ("", "n", "won", "miss") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %7s %7s %7s" % ("TOTAL", "PRE", "RTH", "AFTER", "FRGT", "BIYA", "SBFM"))
    for lvl, lname in (("day", "re-entry over the day's high"), ("exit", "re-entry over the last sale's price")):
        print("\n== %s ==" % lname)
        for name, lim in (("no ceiling (as tested)", None), ("a limit at the ask", 0.0), ("the ask + 2c", 0.02),
                          ("the ask + 5c", 0.05), ("the ask + 10c", 0.10), ("the ask + 20c", 0.20),
                          ("the ask + 1%", "1%"), ("the ask + 2%", "2%")):
            miss = []
            xs = [x for k in sorted(by) for x in G.play(by[k], bars, level=lvl, checks=True, limit=lim, misses=miss)]
            per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
            ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
            big = [sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) == b) for b in BIG]
            print("%-34s %4d %3d %5d " % (name, len(xs), sum(x[2] > 0 for x in xs), len(miss)) +
                  " ".join("%+7.0f" % v for v in per) +
                  " %+8.0f | %+7.0f %+7.0f %+7.0f | %+7.0f %+7.0f %+7.0f" % (sum(per), *ses, *big))


if __name__ == "__main__":
    main()
