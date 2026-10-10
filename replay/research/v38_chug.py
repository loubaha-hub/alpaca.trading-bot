"""The owner's chug (10-10): "five minutes is too short ... 20 minutes: if it
goes up 10% in the first twenty minutes, then we can get into that" (30% an
hour). A second signal beside the speed test: over the last N closed 1-minute
candles the price up X% or more (the last close over the first open), an
average of $250k a minute, the last candle not red, and the price now over all
their highs (a new high of the climb). The buy and everything after it as v38
(trailing thirds, $7,500 full, the bot's buy checks). The owner's 20 min / 10%,
and around it 15 / 30 minutes and 15%, to see it holds across settings; the
re-entry level the day's high (as decided) and the last sale's price (proposed).
A chug needs N minutes of the read before it: windows that start later than
that are not seen (the runner windows start 10 minutes before the low).

python3 v38_chug.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS

BIG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"))


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    print("THE OWNER'S CHUG - N minutes up X%, $250k a minute on average (trailing thirds, $7,500 full, the bot's buy checks)")
    print("%-44s %4s %3s " % ("", "n", "won") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %s" % ("TOTAL", "PRE", "RTH", "AFTER", "the chug buys: n, won, P/L, PRE / RTH / AFTER"))
    for lvl, lname in (("day", "re-entry over the day's high"), ("exit", "re-entry over the last sale's price")):
        print("\n== %s ==" % lname)
        for name, kw in (("speed alone (no chug)", dict()),
                         ("chug 20 min +10% (the owner's), 3c floor", dict(chug=(20, 0.10, "avg"))),
                         ("chug 20 min +10%, candle-low floor", dict(chug=(20, 0.10, "avg"), chug_floor="candle")),
                         ("chug 15 min +10%, 3c floor", dict(chug=(15, 0.10, "avg"))),
                         ("chug 30 min +10%, 3c floor", dict(chug=(30, 0.10, "avg"))),
                         ("chug 20 min +15%, 3c floor", dict(chug=(20, 0.15, "avg"))),
                         ("chug 30 min +15%, 3c floor", dict(chug=(30, 0.15, "avg"))),
                         ("chug 15 min +10%, candle-low floor", dict(chug=(15, 0.10, "avg"), chug_floor="candle")),
                         ("chug 30 min +10%, candle-low floor", dict(chug=(30, 0.10, "avg"), chug_floor="candle")),
                         ("chug 20 min +15%, candle-low floor", dict(chug=(20, 0.15, "avg"), chug_floor="candle")),
                         ("chug 30 min +15%, candle-low floor", dict(chug=(30, 0.15, "avg"), chug_floor="candle"))):
            xs = [x for k in sorted(by) for x in G.play(by[k], bars, level=lvl, checks=True, **kw)]
            per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
            ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
            c = [x for x in xs if x[3] == "chug"]
            extra = ""
            if kw:
                extra = "%3d %2d %+7.0f  %s" % (len(c), sum(x[2] > 0 for x in c), sum(x[2] for x in c),
                                              " / ".join("%+.0f" % sum(x[2] for x in c if session(x[1]) == s) for s in SESSIONS))
            print("%-44s %4d %3d " % (name, len(xs), sum(x[2] > 0 for x in xs)) + " ".join("%+7.0f" % v for v in per) +
                  " %+8.0f | %+7.0f %+7.0f %+7.0f | %s" % (sum(per), *ses, extra))
            if c:
                nw = [x for x in c if not (x[0]["sym"] == "WFF" and x[0]["day"] == "2026-10-09")]
                print("%-44s      the chug buys without WFF 10-09: %d, %+.0f" % ("", len(nw), sum(x[2] for x in nw)))
            best = sorted(c, key=lambda x: -x[2])[:4]
            if best and best[0][2] > 100:
                print("%-44s      best chug buys: %s" % ("", ", ".join("%s %s %s %+.0f" % (
                    x[0]["day"][5:], x[0]["sym"], datetime.fromtimestamp(x[1], S.ET).strftime("%H:%M"), x[2]) for x in best if x[2] > 100)))


if __name__ == "__main__":
    main()
