import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))  # run from this folder
"""v37's furious-sized buys (a big share of the account at once), 10-06/07/08:
the 5c cut vs the 10c leash with the furious exit (30c then 30% back)."""
import json, sys
sys.path.insert(0, REPO + "/replay/research")
import secsim as S, secsim_run as R
D = REPO + "/replay/live/2026-10-08_secdump"
W_ = S.load_windows(D + "/windows"); rts = json.load(open(D + "/roundtrips.json")); paths = {}
EQ = 14000
tot = {}; n = 0; live = 0
rows = []
for day in sorted(rts["v37"]):
    for rt in rts["v37"][day]:
        if rt["pl"] is None: continue
        t0, px, sh = R.entries(rt, day)
        if px * sh < 0.15 * EQ: continue
        path = S.path_for(W_, paths, day, rt["sym"], t0)
        if not path: continue
        n += 1; live += rt["pl"]; row = [day[5:], rt["open"], rt["sym"], px, rt["pl"]]
        for st, ln in (("3%", "5c cut"), ("10c", "5c cut"), ("10c", "furious 30c/30%"), ("3%", "furious 30c/30%")):
            te, xp, why, best = S.run(path, t0, px, sh, R.STOPS[st], R.LINES[ln])
            v = (xp - px) * sh; tot[(st, ln)] = tot.get((st, ln), 0) + v; row.append("%+.0f %.0fs" % (v, te - t0))
        rows.append(row)
print("v37 furious-sized buys with data: %d, live %+.0f" % (n, live))
for k, v in tot.items(): print("  %s / %s: %+.0f" % (k[0], k[1], v))
for r in rows: print("   ", *r)
