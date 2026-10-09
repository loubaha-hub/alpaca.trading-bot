"""The speed strategy (SPEED only, new-high re-entries, ease-in) under different
stops - in cents or sized to the price, on the mid or prints only - split by
session (10-09). python3 speedsim_stops.py <windows dir>"""
import sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import secsim as S, speedsim as Q
from speedsim_study import session, SESSIONS, cell
W = S.load_windows(sys.argv[1])
data = [(r, S.Path(r), Q.speed_state(r)) for l in W.values() for r in l]
V = [("3c, mid or print", dict(su=0.03, arm=0.10)),
     ("3c, prints only", dict(su=0.03, arm=0.10, mid_stop=False)),
     ("5c, prints only", dict(su=0.05, arm=0.10, mid_stop=False)),
     ("10c, prints only", dict(su=0.10, arm=0.10, mid_stop=False)),
     ("5%, prints only", dict(su=0, arm=0.10, mid_stop=False, stop_pct=0.05)),
     ("10%, prints only", dict(su=0, arm=0.10, mid_stop=False, stop_pct=0.10)),
     ("15%, prints only", dict(su=0, arm=0.10, mid_stop=False, stop_pct=0.15)),
     ("10%, prints, half from 20c", dict(su=0, arm=0.20, mid_stop=False, stop_pct=0.10)),
     ("10%, prints, half from 10%", dict(su=0, arm="pct", mid_stop=False, stop_pct=0.10))]
print("%-28s " % "stop (half from 10c)" + " ".join("%22s" % s for s in SESSIONS + ("ALL",)) + "  in<5s  big runs")
BIG = {("2026-10-06","AIXI"),("2026-10-06","IPDN"),("2026-10-06","XHG"),("2026-10-07","SXTC"),("2026-10-06","FRGT")}
for name, v in V:
    by = {s: [] for s in SESSIONS}; quick = n = 0; big = {}
    for r, p, st in data:
        arm = v["arm"]
        kw = {k: v[k] for k in ("mid_stop", "stop_pct") if k in v}
        if arm == "pct":
            # half from +10% of the price: arm in cents per window from its first price
            px = next((x[4] for x in r["S"] if x[4]), 1.0); arm = 0.10 * px
        for tr in Q.play_ladder_hod(p, r, st, 4000, v["su"], arm, **kw):
            by[session(tr[0])].append(tr[4]); n += 1
            quick += (tr[8] - tr[0]) < 5
            if (r["day"], r["sym"]) in BIG:
                big[r["sym"]] = big.get(r["sym"], 0) + tr[4]
    allpl = [x for s in SESSIONS for x in by[s]]
    print("%-28s " % name + " ".join(cell(by[s]) for s in SESSIONS) + " " + cell(allpl) +
          "  %3.0f%%  " % (100 * quick / max(1, n)) + " ".join("%s %+.0f" % kv for kv in sorted(big.items())))
