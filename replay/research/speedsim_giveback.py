"""The whole picture of the speed strategy on the read (the owner, 10-09
~2:30pm): every window - the runs AND the rest of the bots' entries, the
losers included - and, on each run, how much it was up at its best and how
much it gave back. Every table split PRE / RTH / AFTER.

python3 speedsim_giveback.py <windows dir> [min run %, default 40]"""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
from speedsim_study import session, SESSIONS
from speedsim_bag import trades


def run_of(r):
    px = [(r["start"] + x[0], x[4]) for x in r["S"] if x[4]]
    if not px:
        return None
    lo = px[0]; best = (1.0, px[0][0], px[0][1], px[0][0], px[0][1])
    for t, v in px:
        if v < lo[1]:
            lo = (t, v)
        if v / lo[1] > best[0]:
            best = (v / lo[1], lo[0], lo[1], t, v)
    return best


def main():
    W = S.load_windows(sys.argv[1])
    min_run = float(sys.argv[2]) / 100 if len(sys.argv) > 2 else 0.40
    recs = [r for l in W.values() for r in l]
    agg = defaultdict(lambda: [0, 0, 0.0])          # (setting, group, session) -> trades, won, P/L
    gb = []
    for r in sorted(recs, key=lambda r: (r["day"], r["start"])):
        rn = run_of(r)
        if not rn:
            continue
        group = "run 40%+" if rn[0] - 1 >= min_run else "the rest"
        p, st = S.Path(r), Q.speed_state(r)
        row = {}
        for setting in ("A", "B"):
            peak = kept = 0.0
            for tr in trades(r, p, st, setting):
                t_in, fill, w, bst, pl, sh, avg, adds, te = tr
                a = agg[(setting, group, session(t_in))]
                a[0] += 1; a[1] += pl > 0; a[2] += pl
                xp = avg + pl / sh if sh else fill
                peak += max(0.0, bst - avg)
                kept += xp - avg
            row[setting] = (peak, kept)
        if group == "run 40%+":
            gb.append((r, rn, row))
    print("EVERY WINDOW READ (72: every stock-moment the three bots bought 10-06..10-08, winners and losers)")
    print("the speed strategy's own trades in them; A = 3c stop, half from +10c; B = 10% stop, half from +10%")
    print("a cell: trades, won, P/L\n")
    print("%-3s %-10s " % ("set", "windows") + " ".join("%20s" % s for s in SESSIONS + ("ALL",)))
    for setting in ("A", "B"):
        for group in ("run 40%+", "the rest", "all"):
            cells, tot = [], [0, 0, 0.0]
            for s in SESSIONS:
                if group == "all":
                    v = [sum(agg[(setting, g, s)][i] for g in ("run 40%+", "the rest")) for i in range(3)]
                else:
                    v = agg[(setting, group, s)]
                tot = [tot[i] + v[i] for i in range(3)]
                cells.append("%4d %3d %+9.0f" % tuple(v))
            print("%-3s %-10s " % (setting if group == "run 40%+" else "", group) + " ".join("%20s" % c for c in cells)
                  + " %20s" % ("%4d %3d %+9.0f" % tuple(tot)))
        print()
    print("ON EACH RUN: up at its best (the trades' peaks over their buys, added, cents a share), kept, given back")
    print("- each as a share of the run (its high minus its low)")
    for s in SESSIONS:
        part = [x for x in gb if session(x[1][1]) == s]
        if not part:
            continue
        print("== %s ==" % s)
        print("  %-5s %-5s %6s | %-24s | %-24s" % ("day", "sym", "run", "A: best / kept / gave back", "B: best / kept / gave back"))
        tot = defaultdict(float)
        for r, rn, row in part:
            span = rn[4] - rn[2]
            cells = []
            for setting in ("A", "B"):
                peak, kept = row[setting]
                tot[setting + "p"] += peak / span; tot[setting + "k"] += kept / span
                cells.append("%5.0f%% %5.0f%% %6.0f%%" % (100 * peak / span, 100 * kept / span, 100 * (peak - kept) / span))
            print("  %-5s %-5s %5.0f%% | %-24s | %-24s" % (r["day"][5:], r["sym"], 100 * (rn[0] - 1), cells[0], cells[1]))
        n = len(part)
        print("  %-18s | %5.0f%% %5.0f%% %6.0f%% | %5.0f%% %5.0f%% %6.0f%%   (averages, %d runs)" % (
            "average", 100 * tot["Ap"] / n, 100 * tot["Ak"] / n, 100 * (tot["Ap"] - tot["Ak"]) / n,
            100 * tot["Bp"] / n, 100 * tot["Bk"] / n, 100 * (tot["Bp"] - tot["Bk"]) / n, n))


if __name__ == "__main__":
    main()
