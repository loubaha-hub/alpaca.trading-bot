import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))  # run from this folder
import sys; sys.argv=["x"]
exec(open("payup2.py").read().split("for DEC in")[0])
from collections import defaultdict
for DEC in (0.3, 0.6, 1.0):
    st, ln = EXIT["v37"]
    res = defaultdict(float); paid = defaultdict(float); cnt = defaultdict(int)
    for day in sorted(rts["v37"]):
        for rt in rts["v37"][day]:
            if rt["pl"] is None: continue
            t0, px, sh = R.entries(rt, day)
            if [b for b in rt["buys"] if S.ts(day, b[0]) - t0 > R.ENTRY_SECONDS]: continue
            path = S.path_for(W_, paths, day, rt["sym"], t0); rec = rec_for(day, rt["sym"], t0)
            if not path or not rec or not rec["Q"]: continue
            te, xp, why, best = S.run(path, t0, px, sh, R.STOPS[st], R.LINES[ln])
            res[("as paid", day)] += (xp - px) * sh; cnt[day] += 1
            ask = path.ask_at(t0 - DEC); paid[day] += (px - ask) * sh
            for wait in (1, 3, 10):
                k = ("ask %ds" % wait, day)
                lim = round(ask, 4)
                if lim >= px - 1e-9:
                    res[k] += (xp - px) * sh; continue
                got, tf = fill(rec, t0 - DEC, lim, sh, wait)
                if got <= 0: continue
                te2, xp2, *_ = S.run(path, tf, lim, got, R.STOPS[st], R.LINES[ln])
                res[k] += (xp2 - lim) * got
    days = sorted(cnt)
    print("decision %.1fs before: trades %s | paid over that ask %s" % (DEC, " ".join("%s:%d" % (d[5:], cnt[d]) for d in days),
          " ".join("%+.0f" % paid[d] for d in days)))
    for k in ("as paid", "ask 1s", "ask 3s", "ask 10s"):
        print("   %-8s %s  total %+.0f" % (k, " ".join("%+7.0f" % res[(k, d)] for d in days), sum(res[(k, d)] for d in days)))
