"""Does the scout get us in EARLY, and keep us IN the big runners? (the owner,
10-10: "the whole idea of scouts is to keep the big runners under the tent ...
get in before it flies ... is this really true or not?").

For each run of 40%+ in the read: the first second the scout would be bought
(up 20% from its low so far, within 10% of its high, $250k a minute over 10
minutes) and the first second of the speed test, after the run's low - the
time, the price, the share of the run already done - which came first; and
the P/L on that run: v38 speed only (3c floor) against the scout with speed
adds (v38_scout4: the added shares' floor 3c under their average, or the last
candle's low).

python3 v38_scout_runs.py <new windows> <old windows> <old minute bars>"""
import os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
import v38_final as F
import v38_gaps as G
import v38_scout4 as V
from speedsim_giveback import run_of
from speedsim_study import session


def firsts(r, rn):
    sp = G.signals(r, checks=True)
    rows = {x[0]: x for x in r["S"] if x[1]}
    last = max(rows) if rows else -1
    dol = [0.0] * (last + 2)
    for k in range(last + 1):
        x = rows.get(k)
        dol[k + 1] = dol[k] + ((x[4] * x[5]) if x else 0.0)
    top, low = r.get("hod_before"), None
    fs = fsc = None
    for k in sorted(sp):
        x = rows.get(k)
        if x:
            top = x[2] if top is None else max(top, x[2])
            low = x[3] if low is None else min(low, x[3])
        t = r["start"] + k
        if t < rn[1] or t > rn[3] or not x:
            continue
        if fs is None and sp[k][0]:
            fs = (t, x[4])
        if fsc is None and low and top and k >= 600 and x[4] >= low * 1.20 and x[4] >= top * 0.90 \
                and dol[k + 1] - dol[k - 599] >= 10 * Q.DOLLARS_MIN:
            fsc = (t, x[4])
        if fs and fsc:
            break
    return fs, fsc


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    F.FULL = 7500.0
    base = [x for k in sorted(by) for x in V.play(by[k])]
    s_avg = [x for k in sorted(by) for x in V.play(by[k], scout=0.01, floor_mode="avg")]
    s_cdl = [x for k in sorted(by) for x in V.play(by[k], scout=0.01, floor_mode="candle")]
    hm = lambda t: datetime.fromtimestamp(t, S.ET).strftime("%H:%M:%S")
    print("EACH RUN OF 40%+: the scout's first moment vs the speed's first moment, and the P/L on the run")
    print("  %-5s %-5s %-5s %-15s %-15s %5s | %-24s | %-24s | %-6s | %8s %8s %8s" % (
        "day", "sym", "sess", "low", "high", "run", "first speed: time $ done", "first scout: time $ done",
        "first", "speed", "scout+3c", "scout+cdl"))
    tally = {"speed": 0, "scout": 0, "same": 0, "speed only": 0, "scout only": 0, "neither": 0}
    early = []
    for k in sorted(by):
        for r in by[k]:
            rn = run_of(r)
            if not rn or rn[0] - 1 < 0.40:
                continue
            fs, fsc = firsts(r, rn)
            done = lambda px: (px - rn[2]) / (rn[4] - rn[2])
            cell = lambda f: "%s $%6.2f %4.0f%%" % (hm(f[0]), f[1], 100 * done(f[1])) if f else "never"
            if fs and fsc:
                who = "speed" if fs[0] < fsc[0] else "scout" if fsc[0] < fs[0] else "same"
                if who == "scout":
                    early.append((r, fs, fsc, rn))
            else:
                who = "speed only" if fs else "scout only" if fsc else "neither"
            tally[who] += 1
            pl = [sum(x[2] for x in xs if x[0] is r) for xs in (base, s_avg, s_cdl)]
            print("  %-5s %-5s %-5s %-15s %-15s %4.0f%% | %-24s | %-24s | %-6s | %+8.0f %+8.0f %+8.0f" % (
                r["day"][5:], r["sym"], session(rn[1]), "$%.2f %s" % (rn[2], hm(rn[1])[:5]),
                "$%.2f %s" % (rn[4], hm(rn[3])[:5]), 100 * (rn[0] - 1), cell(fs), cell(fsc), who[:6], *pl))
    print("\nwhich came first on the way up:", ", ".join("%s %d" % (k, v) for k, v in tally.items()))
    if early:
        print("where the scout came first - how much earlier, and the price difference:")
        for r, fs, fsc, rn in early:
            print("  %s %-5s scout %s at $%.2f, speed %s at $%.2f: %.1f minutes earlier, %+.1f%% cheaper" % (
                r["day"][5:], r["sym"], hm(fsc[0]), fsc[1], hm(fs[0]), fs[1], (fs[0] - fsc[0]) / 60,
                100 * (fs[1] / fsc[1] - 1)))


if __name__ == "__main__":
    main()
