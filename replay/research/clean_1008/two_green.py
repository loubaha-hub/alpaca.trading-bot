import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))  # run from this folder
"""v37's buys, 10-06/07/08: were the two closed 1-minute candles before the buy
both green? Candles built from SEC_DUMP's one-row-a-second data. Live P/L of
the round trip, and the 5c cut replayed (trades with no adds)."""
import json, sys
from collections import defaultdict
sys.path.insert(0, REPO + "/replay/research")
import secsim as S, secsim_run as R
D = REPO + "/replay/live/2026-10-08_secdump"
W_ = S.load_windows(D + "/windows"); rts = json.load(open(D + "/roundtrips.json")); paths = {}
EQ = 14000

def candles_before(day, sym, t0):
    for rec in W_.get((day, sym), []):
        if rec["start"] <= t0 <= rec["end"]:
            m = defaultdict(list)
            for r in rec["S"]:
                if r[1]:
                    m[int((rec["start"] + r[0]) // 60)].append(r)
            bm = int(t0 // 60)
            out = []
            for k in (bm - 2, bm - 1):
                rows = sorted(m.get(k, []))
                if not rows or rows[0][0] + rec["start"] > k * 60 + 30:   # too little of the minute
                    return None
                o, c = rows[0][1], rows[-1][4]
                out.append(c > o)
            return out
    return None

g = defaultdict(lambda: [0, 0.0, 0, 0.0, 0])   # n, live, won, sim 5c, sim n
for day in sorted(rts["v37"]):
    for rt in rts["v37"][day]:
        if rt["pl"] is None: continue
        t0, px, sh = R.entries(rt, day)
        c = candles_before(day, rt["sym"], t0)
        if c is None:
            key = "no candle data"
        else:
            key = "2 green" if all(c) else ("last green only" if c[1] else "last red")
        kind = "fast (35%)" if px * sh >= 0.20 * EQ else "regular/small"
        for k in (key, (key, kind)):
            x = g[k]; x[0] += 1; x[1] += rt["pl"]; x[2] += rt["pl"] > 0
        adds = [b for b in rt["buys"] if S.ts(day, b[0]) - t0 > R.ENTRY_SECONDS]
        path = S.path_for(W_, paths, day, rt["sym"], t0)
        if path and not adds:
            te, xp, why, best = S.run(path, t0, px, sh, R.STOPS["3%"], R.LINES["5c cut"])
            for k in (key, (key, kind)):
                g[k][3] += (xp - px) * sh; g[k][4] += 1
for k in sorted(g, key=str):
    n, live, won, sim, sn = g[k]
    print("%-40s %3d trades, live %+7.0f (%d won, %+.1f a trade) | 5c cut, no adds: %3d trades %+7.0f (%+.1f a trade)" % (
        k, n, live, won, live / n, sn, sim, sim / max(1, sn)))
