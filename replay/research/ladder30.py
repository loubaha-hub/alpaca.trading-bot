"""The owner's question (10-08 ~8:20pm): v36's furious exit as it is (nothing until
+30c, then 30% of the gain back), against the same with the owner's ladder from
+30c (half back 30-50c, a third back 50c-$1, a fifth back above $1). The 10c stop
under both. 10-08's three v36 trades that went past +30c come from the v37
TICK_DUMP (every print); the rest from the three-day read."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S, secsim_run as R

def ladder30(fill, best):
    g = best - fill
    if g < 0.30 - 1e-9:
        return -1.0
    if g < 0.50:
        return fill + g / 2
    if g < 1.00:
        return fill + g * 2 / 3
    return best - g / 5

RULES = [("now: 30% back from +30c", S.furious()), ("ladder from +30c", ladder30)]

def tick_rec(data, sym, a, ns):
    v = data[(sym, a)]
    start = ns["ts"](a)
    T, Q = v.get("T", []), v.get("Q", [])
    return dict(day="2026-10-08", sym=sym, start=start, end=start + 600, T=T, Q=Q, S=[], missing=[])

if __name__ == "__main__":
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = open(os.path.join(REPO, "replay/research/tickreplay.py")).read().rsplit("\nmain()", 1)[0]
    ns = {"__file__": os.path.join(REPO, "replay/research/tickreplay.py"), "__name__": "tr"}
    exec(compile(src, "t", "exec"), ns)
    data = ns["load"](os.path.join(REPO, "replay/live/2026-10-08_ticks/tickdump_v37.txt.gz"))
    print("10-08, the three v36 trades past +30c (prints; live in brackets):")
    for sym, a, t, fill, sh, live in (("DKI", "05:00:17", "05:00:43", 3.75, 1067, 281.32),
                                      ("DKI", "06:57:06", "06:54:38", 5.57, 471, 630.56),
                                      ("FLYE", "07:23:00", "07:22:53", 1.77, 2366, 733.46)):
        rec = tick_rec(data, sym, a, ns)
        # Path from the window's print data; a buy before the window starts is
        # followed from the window's first print (its path before is not in the data)
        rec["S"] = []
        path = S.Path(rec)
        t0 = max(ns["ts"](t), path.ev[0][0])
        cells = []
        for name, f in RULES:
            te, xp, why, best = S.run(path, t0, fill, sh, lambda p: max(p - 0.10, p * 0.92), f)
            cells.append("%s: out %.3f (best %.2f) %+.0f" % (name, xp, best, (xp - fill) * sh))
        print("  %-4s %s buy %.2f x%d [live %+.0f] | %s" % (sym, t, fill, sh, live, " | ".join(cells)))
    W = S.load_windows(sys.argv[1]); rts = json.load(open(sys.argv[2])); paths = {}
    for bot in ("v36", "v36b"):
        tot = {n: 0.0 for n, _ in RULES}; past = 0; n = 0; diff_rows = []
        for day in sorted(rts[bot]):
            for rt in rts[bot][day]:
                t0, px, sh = R.entries(rt, day)
                path = S.path_for(W, paths, day, rt["sym"], t0)
                if not path:
                    continue
                n += 1
                res = {}
                for name, f in RULES:
                    te, xp, why, best = S.run(path, t0, px, sh, R.STOPS["10c"], f)
                    res[name] = (xp - px) * sh
                    tot[name] += res[name]
                    if name.startswith("now") and best - px >= 0.30 - 1e-9:
                        past += 1
                if abs(res[RULES[0][0]] - res[RULES[1][0]]) > 0.5:
                    diff_rows.append((day, rt["open"], rt["sym"], px, res[RULES[0][0]], res[RULES[1][0]]))
        print("\n%s, three-day read (%d trades; %d went past +30c): %s" % (
            bot, n, past, " | ".join("%s %+.0f" % (k, v) for k, v in tot.items())))
        for r in diff_rows:
            print("   %s %s %-5s buy %.3f: now %+.0f, ladder %+.0f" % r)
