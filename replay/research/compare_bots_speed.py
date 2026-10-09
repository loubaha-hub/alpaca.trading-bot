"""The three bots live vs the speed strategy (variant A with the scale-out), per
day and in total, split by session (the owner, 10-09 ~4:20pm). The bots: their
real round trips (roundtrips.json, Alpaca fills, adds included). The speed
strategy: replayed second by second on the read around the bots' buys, $4,000
full position (20% / 50% / 100% ease-in), re-entries at speed on a new high
of the day; a trade's day and session by its first buy.

python3 compare_bots_speed.py <secdump dir>  (windows/, roundtrips.json, bars/)"""
import json, os, sys
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
from speedsim_study import session, SESSIONS
from speedsim_reentry import hod_before, play

NAMES = ("v36", "v36b", "v37", "speed A")


def main():
    d = sys.argv[1]
    rts = json.load(open(os.path.join(d, "roundtrips.json")))
    bars = {f[:-5]: json.load(open(os.path.join(d, "bars", f))) for f in os.listdir(os.path.join(d, "bars"))}
    res = defaultdict(lambda: [0, 0, 0, 0.0, 0.0])      # (name, day, session) -> trades, wins, losses, P/L, $ size
    for bot in ("v36", "v36b", "v37"):
        for day, lst in rts[bot].items():
            for rt in lst:
                if rt["pl"] is None:
                    continue
                t = S.ts(day, rt["open"])
                x = res[(bot, day, session(t))]
                x[0] += 1; x[1] += rt["pl"] > 0; x[2] += rt["pl"] <= 0; x[3] += rt["pl"]
                x[4] += max(sum(q * p for _, q, p in rt["buys"]), 0)
    W = S.load_windows(os.path.join(d, "windows"))
    for r in (r for l in W.values() for r in l):
        if r.get("hod_before") is None:
            r["hod_before"] = hod_before(bars, r)
        p, st = S.Path(r), Q.speed_state(r)
        for t_in, pl, first, dollars in play(r, p, st):
            x = res[("speed A", r["day"], session(t_in))]
            x[0] += 1; x[1] += pl > 0; x[2] += pl <= 0; x[3] += pl; x[4] += dollars
    days = sorted({k[1] for k in res})
    cell = lambda v: "%4d %3d %3d %+9.0f" % (v[0], v[1], v[2], v[3])
    head = " ".join("%22s" % n for n in NAMES)
    print("THE THREE BOTS LIVE vs THE SPEED STRATEGY (A + scale-out), 10-06..10-08")
    print("a cell: trades, wins, losses, P/L. Sizes differ: the bots as they really bought; the speed")
    print("strategy $4,000 full (it starts with $800 and adds only as the stock rises)\n")
    for sess in SESSIONS + ("ALL",):
        print("== %s ==" % {"PRE": "PREMARKET 4:00-9:30", "RTH": "REGULAR HOURS 9:30-4:00",
                             "AFTER": "AFTER HOURS 4:00-8:00pm", "ALL": "THE WHOLE DAY"}[sess])
        print("%-7s %s" % ("day", head))
        tot = {n: [0, 0, 0, 0.0, 0.0] for n in NAMES}
        for day in days:
            row = []
            for n in NAMES:
                v = [0, 0, 0, 0.0, 0.0]
                for s in (SESSIONS if sess == "ALL" else (sess,)):
                    v = [a + b for a, b in zip(v, res[(n, day, s)])]
                tot[n] = [a + b for a, b in zip(tot[n], v)]
                row.append(cell(v))
            print("%-7s %s" % (day[5:], " ".join("%22s" % c for c in row)))
        print("%-7s %s" % ("TOTAL", " ".join("%22s" % cell(tot[n]) for n in NAMES)))
        if sess == "ALL":
            print("%-7s %s" % ("avg $", " ".join("%22s" % ("$%.0f a trade" % (tot[n][4] / max(1, tot[n][0]))) for n in NAMES)))
            print("%-7s %s" % ("/trade", " ".join("%22s" % ("%+.0f a trade" % (tot[n][3] / max(1, tot[n][0]))) for n in NAMES)))
        print()


if __name__ == "__main__":
    main()
