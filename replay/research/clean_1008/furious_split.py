import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))  # run from this folder
"""v36 / v36b entries split by size: furious (a full 25% position at once) vs
starters. 10c vs 3% first stop, each with the furious exit and the 5c cut."""
import json, os, sys
from collections import defaultdict
R_DIR = REPO + "/replay/research"
sys.path.insert(0, R_DIR)
import secsim as S, secsim_run as R
D = REPO + "/replay/live/2026-10-08_secdump"
W = S.load_windows(D + "/windows"); rts = json.load(open(D + "/roundtrips.json")); paths = {}
EQ = {"v36": 17000, "v36b": 6500, "v37": 14000}
for bot in ("v36", "v36b"):
    tot = defaultdict(float); cnt = defaultdict(int); won = defaultdict(int); live = defaultdict(float)
    miss = defaultdict(int); rows = []
    for day in sorted(rts[bot]):
        for rt in rts[bot][day]:
            if rt["pl"] is None: continue
            t0, px, sh = R.entries(rt, day)
            kind = "furious" if px * sh >= 0.15 * EQ[bot] else "starter"
            path = S.path_for(W, paths, day, rt["sym"], t0)
            if not path:
                miss[kind] += 1; live[(kind, "missing")] += rt["pl"]; continue
            cnt[kind] += 1; live[kind] += rt["pl"]
            for st in ("10c", "3%"):
                for ln in ("furious 30c/30%", "5c cut"):
                    te, xp, why, best = S.run(path, t0, px, sh, R.STOPS[st], R.LINES[ln])
                    v = (xp - px) * sh
                    tot[(kind, st, ln, day)] += v; tot[(kind, st, ln)] += v
                    won[(kind, st, ln)] += v > 0
            if kind == "furious":
                a = S.run(path, t0, px, sh, R.STOPS["10c"], R.LINES["furious 30c/30%"])
                b = S.run(path, t0, px, sh, R.STOPS["3%"], R.LINES["furious 30c/30%"])
                rows.append((day, rt["open"], rt["sym"], px, sh, rt["pl"], (a[1]-px)*sh, a[0]-t0, (b[1]-px)*sh, b[0]-t0))
    print("=== %s" % bot)
    for kind in ("furious", "starter"):
        print("  %s: %d with data (live %+.0f), %d without (live %+.0f)" % (
            kind, cnt[kind], live[kind], miss[kind], live[(kind, "missing")]))
        for ln in ("furious 30c/30%", "5c cut"):
            print("    %-16s 10c %+8.0f (%d won)  3%% %+8.0f (%d won)   by day 10c: %s | 3%%: %s" % (
                ln, tot[(kind, "10c", ln)], won[(kind, "10c", ln)], tot[(kind, "3%", ln)], won[(kind, "3%", ln)],
                " ".join("%+.0f" % tot[(kind, "10c", ln, d)] for d in sorted(rts[bot])),
                " ".join("%+.0f" % tot[(kind, "3%", ln, d)] for d in sorted(rts[bot]))))
    print("  furious entries (furious exit): day time sym buy shares live | 10c P/L held | 3% P/L held")
    for r in rows:
        print("    %s %s %-5s %.3f x%-5d live %+7.0f | 10c %+7.0f %5.0fs | 3%% %+7.0f %5.0fs" % r)
