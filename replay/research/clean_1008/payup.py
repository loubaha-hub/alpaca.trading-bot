import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))  # run from this folder
"""Stop paying up: each live entry again with a limit at the ask seen DEC seconds
before the fill (about when the bot decided), working W seconds; no fill = no
trade. Same exit as the live rule (approx.), from the new fill. Trades with no
adds only (like for like)."""
import json, sys
from collections import defaultdict
sys.path.insert(0, REPO + "/replay/research")
import secsim as S, secsim_run as R
D = REPO + "/replay/live/2026-10-08_secdump"
W_ = S.load_windows(D + "/windows"); rts = json.load(open(D + "/roundtrips.json")); paths = {}
DEC = 1.0
EXIT = {"v36": ("10c", "furious 30c/30%"), "v36b": ("3%", "furious 30c/30%"), "v37": ("3%", "5c cut")}
EXIT2 = {"v36": ("10c", "5c cut"), "v36b": ("3%", "5c cut"), "v37": ("10c", "5c cut")}

def limit_fill(path, td, lim, wait):
    """First print or ask at or under lim from td + 0.3s to td + wait."""
    i = path.at(td + 0.3)
    for t, p, b, a in path.ev[i:]:
        if t > td + wait:
            return None
        if (a and a <= lim + 1e-9) or p <= lim - 0.0001:
            return t, min(lim, a) if a else lim
    return None

for bot in ("v36", "v36b", "v37"):
    n = 0; over = 0.0; over_d = 0.0; dollars = 0.0
    res = defaultdict(float); fills = defaultdict(int); won = defaultdict(int)
    for day in sorted(rts[bot]):
        for rt in rts[bot][day]:
            if rt["pl"] is None: continue
            t0, px, sh = R.entries(rt, day)
            if [b for b in rt["buys"] if S.ts(day, b[0]) - t0 > R.ENTRY_SECONDS]:
                continue                                   # adds: not like for like
            path = S.path_for(W_, paths, day, rt["sym"], t0)
            if not path: continue
            n += 1
            ask = path.ask_at(t0 - DEC)
            over += (px - ask) * sh; dollars += px * sh
            res["live"] += rt["pl"]; won["live"] += rt["pl"] > 0; fills["live"] += 1
            for ex in (EXIT, EXIT2):
                st, ln = ex[bot]
                tag = "%s/%s" % (st, ln)
                te, xp, why, best = S.run(path, t0, px, sh, R.STOPS[st], R.LINES[ln])
                v = (xp - px) * sh
                res[("as paid", tag)] += v; won[("as paid", tag)] += v > 0; fills[("as paid", tag)] += 1
                for plus in (0.0, 0.02, 0.05):
                    for wait in (2, 5, 15):
                        f = limit_fill(path, t0 - DEC, ask + plus, wait)
                        k = ("ask+%dc, %ds" % (plus * 100, wait), tag)
                        if not f: continue
                        tf, fp = f
                        q = int(px * sh / fp)
                        te, xp, why, best = S.run(path, tf, fp, q, R.STOPS[st], R.LINES[ln])
                        v = (xp - fp) * q
                        res[k] += v; won[k] += v > 0; fills[k] += 1
    print("=== %s: %d entries with no adds; paid over the ask seen %.0fs before the fill: $%.0f total (%.2f%% of $%.0f bought)" % (
        bot, n, DEC, over, 100 * over / dollars, dollars))
    print("    live %+.0f (%d won)" % (res["live"], won["live"]))
    for ex in (EXIT, EXIT2):
        st, ln = ex[bot]; tag = "%s/%s" % (st, ln)
        print("  exit %s:" % tag)
        print("    %-16s %+8.0f  %3d trades %3d won" % ("as paid", res[("as paid", tag)], fills[("as paid", tag)], won[("as paid", tag)]))
        for plus in (0.0, 0.02, 0.05):
            for wait in (2, 5, 15):
                k = ("ask+%dc, %ds" % (plus * 100, wait), tag)
                print("    %-16s %+8.0f  %3d trades %3d won" % (k[0], res[k], fills[k], won[k]))
