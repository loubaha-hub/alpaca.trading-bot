"""Check secsim against tickreplay (the bot's own v37 exit code) on v37's 19 buys of
10-08: python3 secsim_check.py [secs|ticks]. 10-08: 5c -$260 ticks / -$297 seconds vs
-$290 tickreplay; 10c -$637 / -$661 vs -$632."""
import sys, os, json
sys.path.insert(0, "/home/user/alpaca.trading-bot/replay/research")
import secsim
REPO = "/home/user/alpaca.trading-bot"
src = open(os.path.join(REPO, "replay/research/tickreplay.py")).read().rsplit("\nmain()", 1)[0]
ns = {"__file__": os.path.join(REPO, "replay/research/tickreplay.py"), "__name__": "tr"}
exec(compile(src, "t", "exec"), ns)
data = ns["load"](os.path.join(REPO, "replay/live/2026-10-08_ticks/tickdump_v37.txt.gz"))
def to_rec(sym, a, v):
    start = ns["ts"](a)
    T = v.get("T", []); Q = v.get("Q", [])
    S = {}
    for r in T:
        if not secsim.qualifies(list(r[3])): continue
        k = int(r[0] // 1000); p, sz = r[1], r[2]
        x = S.get(k)
        if x is None: S[k] = [k, p, p, p, p, sz, 1, 0, 0, 0]
        else: x[2] = max(x[2], p); x[3] = min(x[3], p); x[4] = p; x[5] += sz; x[6] += 1
    for r in Q:
        k = int(r[0] // 1000); x = S.get(k)
        if x is None: x = S[k] = [k, 0, 0, 0, 0, 0, 0, 0, 0, r[1]]
        x[7], x[8] = r[1], r[2]; x[9] = min(x[9], r[1]) if x[9] else r[1]
    return dict(day="2026-10-08", sym=sym, start=start, end=start + 600, T=[], Q=[], S=[S[k] for k in sorted(S)])
mode = sys.argv[1] if len(sys.argv) > 1 else "secs"
for c in (0.05, 0.10):
    tot = 0; rows = []
    for k, b in enumerate(ns["BUYS"]):
        tf = ns["ts"](b[0]); best = None
        for (sym, a), v in data.items():
            if sym == b[1] and ns["ts"](a) <= tf and (best is None or ns["ts"](a) > ns["ts"](best[0])): best = (a, v)
        a, v = best
        rec = to_rec(b[1], a, v)
        if mode == "ticks":
            rec["T"], rec["Q"] = v.get("T", []), v.get("Q", [])
        path = secsim.Path(rec)
        t, px, why, hi = secsim.run(path, tf, b[3], b[2], secsim.stop_cents(b[3] - b[5]), secsim.cut(c))
        pl = (px - b[3]) * b[2]; tot += pl; rows.append("%s %s %+.2f" % (b[1], why, pl))
    print("cut %dc (%s): %+.2f" % (c * 100, mode, tot))
