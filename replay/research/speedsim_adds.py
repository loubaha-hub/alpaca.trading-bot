"""The adds (the owner, 10-09 ~2:50pm, IPDN / XHG / FRGT / BIYA in detail): when
the price jumps past +10c and +20c in one second, both adds fill at once at the
top of the jump - most of the position bought at the top. Every window, every
trade: the trades with adds vs without, and the same with no add past the
step + 5c (add_cap). Split by session.

python3 speedsim_adds.py <windows dir>"""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
from speedsim_study import session, SESSIONS
from speedsim_giveback import run_of


def main():
    W = S.load_windows(sys.argv[1])
    recs = [r for l in W.values() for r in l]
    data = [(r, S.Path(r), Q.speed_state(r), run_of(r)) for r in recs]
    print("%-3s %-22s " % ("set", "adds") + " ".join("%20s" % s for s in SESSIONS + ("ALL",)) + "   runs 40%+   the rest")
    for setting in ("A", "B"):
        for label, cap in (("as the owner's plan", None), ("none past step + 5c", 0.05), ("no adds at all", -99)):
            agg = defaultdict(lambda: [0, 0, 0.0]); grp = defaultdict(float)
            withadds = [0, 0.0]
            for r, p, st, rn in data:
                px0 = next((x[4] for x in r["S"] if x[4]), 1.0)
                kw = dict(mid_stop=False, stop_pct=0.10) if setting == "B" else {}
                su, arm = (0.0, 0.10 * px0) if setting == "B" else (0.03, 0.10)
                if cap == -99:
                    kw["steps"] = ()
                elif cap is not None:
                    kw["add_cap"] = cap
                for tr in Q.play_ladder_hod(p, r, st, 4000, su, arm, **kw):
                    a = agg[session(tr[0])]
                    a[0] += 1; a[1] += tr[4] > 0; a[2] += tr[4]
                    grp["run" if rn and rn[0] - 1 >= 0.40 else "rest"] += tr[4]
                    if tr[7]:
                        withadds[0] += 1; withadds[1] += tr[4]
            tot = [sum(agg[s][i] for s in SESSIONS) for i in range(3)]
            print("%-3s %-22s " % (setting if cap is None else "", label) +
                  " ".join("%20s" % ("%4d %3d %+9.0f" % tuple(agg[s])) for s in SESSIONS) +
                  " %20s" % ("%4d %3d %+9.0f" % tuple(tot)) + "   %+9.0f  %+9.0f" % (grp["run"], grp["rest"]) +
                  ("   (trades with adds: %d, %+.0f)" % tuple(withadds) if cap is None else ""))
        print()


if __name__ == "__main__":
    main()
