"""The owner's scale-out (10-09 ~3:20pm) on every study so far: once a trade is
up 100% over its average, a resting sell takes a quarter of the position;
at 200% another quarter; the last half rides the stop and the half-back line
("you gave only 25% back"). Sold at the level itself - the chasers buy it on
the way up. Every window of the read (all the bots' entries, losers too),
split PRE / RTH / AFTER, runs of 40%+ apart; and each run's kept share.

python3 speedsim_scaleout.py <windows dir>"""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
from speedsim_study import session, SESSIONS
from speedsim_giveback import run_of

SCALES = (("none", ()), ("+100% / +200% (the owner's)", ((1.0, 0.25), (2.0, 0.25))),
          ("+50% / +100%", ((0.5, 0.25), (1.0, 0.25))), ("+200% / +400%", ((2.0, 0.25), (4.0, 0.25))),
          ("all at +100% (by hand)", ((1.0, 1.0),)))     # the owner's own habit: sell everything fast


def play(r, p, st, setting, scale):
    px0 = next((x[4] for x in r["S"] if x[4]), 1.0)
    kw = dict(mid_stop=False, stop_pct=0.10) if setting == "B" else {}
    su, arm = (0.0, 0.10 * px0) if setting == "B" else (0.03, 0.10)
    return Q.play_ladder_hod(p, r, st, 4000, su, arm, scale=scale, **kw)


def main():
    W = S.load_windows(sys.argv[1])
    recs = sorted((r for l in W.values() for r in l), key=lambda r: (r["day"], r["start"]))
    data = [(r, S.Path(r), Q.speed_state(r), run_of(r)) for r in recs]
    print("THE SCALE-OUT on all %d windows (every stock-moment the bots bought 10-06..10-08, winners and losers)" % len(recs))
    print("A = 3c stop, half from +10c; B = 10% stop, half from +10%. A cell: trades, won, P/L\n")
    print("%-3s %-28s " % ("set", "scale-out") + " ".join("%19s" % s for s in SESSIONS + ("ALL",)) + "  runs 40%+   the rest  scaled")
    kept = {}
    for setting in ("A", "B"):
        for name, scale in SCALES:
            agg = defaultdict(lambda: [0, 0, 0.0]); grp = defaultdict(float); n_scaled = 0
            for r, p, st, rn in data:
                isrun = rn and rn[0] - 1 >= 0.40
                rk = 0.0
                for tr in play(r, p, st, setting, scale):
                    a = agg[session(tr[0])]
                    a[0] += 1; a[1] += tr[4] > 0; a[2] += tr[4]
                    grp["run" if isrun else "rest"] += tr[4]
                    rk += tr[4] / tr[5] if tr[5] else 0.0          # cents a share, sold parts included
                    n_scaled += bool(scale) and tr[3] >= tr[6] * (1 + scale[0][0]) - 1e-9
                if isrun:
                    kept[(setting, name, r["day"], r["sym"], r["start"])] = rk / (rn[4] - rn[2])
            tot = [sum(agg[s][i] for s in SESSIONS) for i in range(3)]
            print("%-3s %-28s " % (setting if not scale else "", name) +
                  " ".join("%19s" % ("%4d %3d %+8.0f" % tuple(agg[s])) for s in SESSIONS) +
                  " %19s" % ("%4d %3d %+8.0f" % tuple(tot)) + "  %+9.0f  %+9.0f  %6d" % (grp["run"], grp["rest"], n_scaled))
        print()
    print("EACH RUN OF 40%+: the share of the run kept (all its trades, the parts sold included)")
    print("  %-5s %-5s %-6s %6s | %8s %8s | %8s %8s" % ("day", "sym", "sess", "run", "A none", "A owner", "B none", "B owner"))
    for r, p, st, rn in data:
        if not (rn and rn[0] - 1 >= 0.40):
            continue
        k = lambda s, n: kept[(s, n, r["day"], r["sym"], r["start"])]
        own = SCALES[1][0]
        print("  %-5s %-5s %-6s %5.0f%% | %7.0f%% %7.0f%% | %7.0f%% %7.0f%%" % (
            r["day"][5:], r["sym"], session(rn[1]), 100 * (rn[0] - 1), 100 * k("A", "none"), 100 * k("A", own),
            100 * k("B", "none"), 100 * k("B", own)))


if __name__ == "__main__":
    main()
