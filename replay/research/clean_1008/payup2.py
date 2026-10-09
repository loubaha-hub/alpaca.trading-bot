import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))  # run from this folder
"""Stop paying up, with sizes: a limit at (the ask seen at the decision) + plus,
arriving 0.3s after the decision (DEC s before the live fill). It takes the shares
offered at the ask then, then fills from prints at or under the limit for `wait`
seconds (as if first in line - kind). Whatever filled is traded with the live
rule's exit from that moment. Trades with no adds."""
import json, sys
from bisect import bisect_left
from collections import defaultdict
sys.path.insert(0, REPO + "/replay/research")
import secsim as S, secsim_run as R
D = REPO + "/replay/live/2026-10-08_secdump"
W_ = S.load_windows(D + "/windows"); rts = json.load(open(D + "/roundtrips.json")); paths = {}
EXIT = {"v36": ("10c", "5c cut"), "v36b": ("3%", "5c cut"), "v37": ("3%", "5c cut")}

def rec_for(day, sym, t):
    for rec in W_.get((day, sym), []):
        if rec["start"] <= t <= rec["end"]:
            return rec

def fill(rec, td, lim, want, wait):
    a = rec["start"]; ta = td + 0.3
    Q = rec["Q"]; T = rec["T"]
    qt = [a + q[0] / 1000 for q in Q]
    i = bisect_left(qt, ta) - 1
    got = 0; t_last = ta
    if i >= 0 and Q[i][2] and Q[i][2] <= lim + 1e-9:
        got = min(want, Q[i][4] or 0)
    for r in T:
        t = a + r[0] / 1000
        if t <= ta or got >= want: continue
        if t > ta + wait: break
        if S.qualifies(r[3]) and r[1] <= lim + 1e-9:
            got = min(want, got + r[2]); t_last = t
    return got, t_last

for DEC in (0.3, 0.6, 1.0):
    print("##### decision %.1fs before the live fill" % DEC)
    for bot in ("v36", "v36b", "v37"):
        st, ln = EXIT[bot]
        res = defaultdict(float); shares = defaultdict(float); won = defaultdict(int); n = 0; want_tot = 0
        for day in sorted(rts[bot]):
            for rt in rts[bot][day]:
                if rt["pl"] is None: continue
                t0, px, sh = R.entries(rt, day)
                if [b for b in rt["buys"] if S.ts(day, b[0]) - t0 > R.ENTRY_SECONDS]:
                    continue
                path = S.path_for(W_, paths, day, rt["sym"], t0)
                rec = rec_for(day, rt["sym"], t0)
                if not path or not rec or not rec["Q"]: continue
                n += 1; want_tot += sh
                te, xp, why, best = S.run(path, t0, px, sh, R.STOPS[st], R.LINES[ln])
                res["as paid"] += (xp - px) * sh; won["as paid"] += xp > px; shares["as paid"] += sh
                ask = path.ask_at(t0 - DEC)
                for plus in (0.0, 0.01, 0.02, 0.03):
                    for wait in (1, 3, 10):
                        lim = round(ask + plus, 4)
                        k = "ask+%dc %2ds" % (plus * 100, wait)
                        if lim >= px - 1e-9:                     # live paid no more than this limit
                            res[k] += (xp - px) * sh; won[k] += xp > px; shares[k] += sh
                            continue
                        got, tf = fill(rec, t0 - DEC, lim, sh, wait)
                        if got <= 0: continue
                        te2, xp2, why2, best2 = S.run(path, tf, lim, got, R.STOPS[st], R.LINES[ln])
                        res[k] += (xp2 - lim) * got; won[k] += xp2 > lim; shares[k] += got
        print("=== %s (%d trades, exit %s/%s)" % (bot, n, st, ln))
        for k in sorted(res, key=lambda x: (x != "as paid", x)):
            print("   %-14s %+8.0f  %3d won  shares %3.0f%%" % (k, res[k], won[k], 100 * shares[k] / want_tot))
