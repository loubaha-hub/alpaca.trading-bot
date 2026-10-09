import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))  # run from this folder
"""v36 / v36b furious buys at the ask (no 20c over it), with v36's real exit."""
import sys
from bisect import bisect_left
exec(open("leash.py").read().split("STOPS = {")[0])
src = open("payup2.py").read()
exec(src[src.index("def rec_for"):src.index("for DEC in")])
STOP = {"v36": lambda f: max(f - 0.10, half_under(f) - 0.01, f * 0.92),
        "v36b": lambda f: max(f - 0.10, half_under(f) - 0.01, f * 0.97)}
for DEC in (0.3, 0.6, 1.0):
    for bot in ("v36", "v36b"):
        res = defaultdict(float); won = defaultdict(int); shares = defaultdict(float); n = 0; want = 0; paid = 0.0
        for day in sorted(rts[bot]):
            for rt in rts[bot][day]:
                if rt["pl"] is None: continue
                t0, px, sh = R.entries(rt, day)
                if px * sh < 0.15 * EQ[bot]: continue
                path = S.path_for(W_, paths, day, rt["sym"], t0); rec = rec_for(day, rt["sym"], t0)
                if not path or not rec or not rec["Q"]: continue
                n += 1; want += sh
                te, xp, w, best = run(path, t0, px, sh, STOP[bot](px))
                res["as paid"] += (xp - px) * sh; won["as paid"] += xp > px; shares["as paid"] += sh
                ask = path.ask_at(t0 - DEC); paid += (px - ask) * sh
                for plus in (0.0, 0.02):
                    for wait in (1, 3):
                        k = "ask+%dc %ds" % (plus * 100, wait); lim = round(ask + plus, 4)
                        if lim >= px - 1e-9:
                            res[k] += (xp - px) * sh; won[k] += xp > px; shares[k] += sh; continue
                        got, tf = fill(rec, t0 - DEC, lim, sh, wait)
                        if got <= 0: continue
                        te2, xp2, w2, b2 = run(path, tf, lim, got, STOP[bot](lim))
                        res[k] += (xp2 - lim) * got; won[k] += xp2 > lim; shares[k] += got
        print("decision %.1fs before | %s %d furious buys, paid $%.0f over that ask | %s" % (DEC, bot, n, paid,
              " | ".join("%s %+.0f (%d won, %.0f%% shares)" % (k, res[k], won[k], 100 * shares[k] / want) for k in res)))
