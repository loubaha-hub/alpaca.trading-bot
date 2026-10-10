"""The owner's chug in REGULAR HOURS ONLY (10-10: not premarket - "the time is
short, the spreads wider, the trading thinner"; 9:30-4:00 has six and a half
hours, lower spreads, slower runs - "if you can spot one or two in a day, maybe
none, two or three a week, and they make a little bit of money, that's good").

v38 (a limit at the ask + 2%, the bot's buy checks, trailing thirds, $7,500
full) with the chug signal on from 9:30 to 4:00 only: the last N closed
1-minute candles up X%, $250k a minute on average, the last candle not red,
the price over all their highs; its floor the last candle's low (at most 10%;
the 3c floor never won a chug). The re-entry level for speed AND chug buys:
none (the speed alone) and the last sale's price. The chug buys alone, by day,
with and without WFF 10-09.

python3 v38_chug_rth.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS

_signals = G.signals


def rth_signals(rec, *a, **kw):
    out = _signals(rec, *a, **kw)
    for k, v in out.items():
        if v[1] and session(rec["start"] + k) != "RTH":
            out[k] = (v[0], False, v[2], v[3])
    return out


def main():
    G.signals = rth_signals
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    print("THE CHUG IN REGULAR HOURS ONLY (9:30-4:00), beside the speed buy")
    print("%-40s %4s %3s " % ("", "n", "won") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %s" % ("TOTAL", "PRE", "RTH", "AFTER", "the chug buys: n, won, P/L by day | without WFF"))
    for lvl, lname in (("none", "re-entry: no level (the speed alone)"), ("exit", "re-entry over the last sale's price")):
        print("\n== %s ==" % lname)
        for name, kw in (("speed only (no chug)", dict()),
                         ("chug 20 min +10% (the owner's)", dict(chug=(20, 0.10, "avg"), chug_floor="candle")),
                         ("chug 15 min +10%", dict(chug=(15, 0.10, "avg"), chug_floor="candle")),
                         ("chug 30 min +10%", dict(chug=(30, 0.10, "avg"), chug_floor="candle")),
                         ("chug 20 min +15%", dict(chug=(20, 0.15, "avg"), chug_floor="candle")),
                         ("chug 30 min +15%", dict(chug=(30, 0.15, "avg"), chug_floor="candle")),
                         ("chug 60 min +30% (30% an hour)", dict(chug=(60, 0.30, "avg"), chug_floor="candle"))):
            xs = [x for k in sorted(by) for x in G.play(by[k], bars, level=lvl, checks=True, limit="2%", **kw)]
            per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
            ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
            c = [x for x in xs if x[3] == "chug"]
            nw = [x for x in c if not (x[0]["sym"] == "WFF" and x[0]["day"] == "2026-10-09")]
            extra = ""
            if kw:
                extra = "%3d %2d %+7.0f  (%s) | %3d %+7.0f" % (
                    len(c), sum(x[2] > 0 for x in c), sum(x[2] for x in c),
                    " ".join("%+.0f" % sum(x[2] for x in c if x[0]["day"] == d) for d in days), len(nw), sum(x[2] for x in nw))
            print("%-40s %4d %3d " % (name, len(xs), sum(x[2] > 0 for x in xs)) + " ".join("%+7.0f" % v for v in per) +
                  " %+8.0f | %+7.0f %+7.0f %+7.0f | %s" % (sum(per), *ses, extra))
            win = sorted([x for x in c if x[2] > 100], key=lambda x: -x[2])[:5]
            if win:
                print("%-40s      the chug's winners: %s" % ("", ", ".join("%s %s %s %+.0f" % (
                    x[0]["day"][5:], x[0]["sym"], datetime.fromtimestamp(x[1], S.ET).strftime("%H:%M"), x[2]) for x in win)))


if __name__ == "__main__":
    main()
