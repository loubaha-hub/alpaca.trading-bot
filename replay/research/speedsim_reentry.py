"""Re-entries (the owner, 10-09 ~4:10pm: "too many jumps in and out eat the
gains of the big runners ... the re-entry respects our entries from before:
above the high of the day"). Variant A with the scale-out, every window; a
re-entry needs speed AND a second whose high clears the high of the day so
far by `clear` - the day's high from the minute bars before the window
(secdump/bars/<day>.json, or the read's own SECDUMP HOD line from r34.40) and
the window's prints after. Split PRE / RTH / AFTER; first buys and re-entries
apart.

python3 speedsim_reentry.py <windows dir> [bars dir]"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
from speedsim_study import session, SESSIONS

SC = ((1.0, 0.25), (2.0, 0.25))


def hod_before(bars, r):
    rows = bars.get(r["day"], {}).get(r["sym"], [])
    hs = [float(x[2]) for x in rows
          if datetime.fromisoformat(x[0].replace("Z", "+00:00")).timestamp() < r["start"] - 59]
    return max(hs) if hs else None


def play(r, p, st, clear=0.0, max_re=None, wait=0):
    hi = {x[0]: x[2] for x in r["S"] if x[2]}
    out, after, first, n_re = [], -1.0, True, 0
    top = r.get("hod_before")
    for k in sorted(st):
        on, _ = st[k]
        h = hi.get(k)
        prev_top = top
        if h is not None:
            top = h if top is None else max(top, h)
        t = r["start"] + k + 0.99
        if t <= after + wait or not on:
            continue
        if not first:
            if h is None or prev_top is None or h <= prev_top + 1e-9 or h < prev_top + clear - 1e-9:
                continue
            if max_re is not None and n_re >= max_re:
                continue
        t_in = t + S.BUY_LAG
        if t_in >= p.end - 5:
            break
        fill = p.ask_at(t_in)
        if not fill or fill <= 0:
            continue
        res = Q.run_ladder(p, t_in, fill, 4000, 0.03, 0.10, scale=SC)
        out.append((t_in, res[1], first, res[4] * res[5]))   # the last: dollars bought
        n_re += not first
        after, first = res[0] + S.SELL_LAG, False
    return out


def main():
    W = S.load_windows(sys.argv[1])
    bdir = sys.argv[2] if len(sys.argv) > 2 else None
    bars = {}
    if bdir:
        for f in os.listdir(bdir):
            if f.endswith(".json"):
                bars[f[:-5]] = json.load(open(os.path.join(bdir, f)))
    recs = [r for l in W.values() for r in l]
    seeded = 0
    for r in recs:
        if r.get("hod_before") is None and bars:
            r["hod_before"] = hod_before(bars, r)
        seeded += r.get("hod_before") is not None
    data = [(r, S.Path(r), Q.speed_state(r)) for r in recs]
    print("RE-ENTRIES - variant A with the scale-out, %d windows (%d with the day's high before the window)" % (len(recs), seeded))
    print("a cell: trades, P/L\n")
    print("%-44s " % "re-entry rule" + " ".join("%15s" % s for s in SESSIONS + ("ALL",)) + "   first buys    re-entries")
    for name, kw in (("speed + a new high of the day", {}),
                     ("speed + over the day's high + 2c", dict(clear=0.02)),
                     ("speed + over the day's high + 5c (v36)", dict(clear=0.05)),
                     ("speed + over the day's high + 10c", dict(clear=0.10)),
                     ("new high, at most 2 re-entries", dict(max_re=2)),
                     ("new high, 60s after the last sale", dict(wait=60)),
                     ("no re-entries", dict(max_re=0))):
        agg = {s: [0, 0.0] for s in SESSIONS}; fb = [0, 0.0]; re = [0, 0.0]
        for r, p, st in data:
            for t_in, pl, first, _ in play(r, p, st, **kw):
                agg[session(t_in)][0] += 1; agg[session(t_in)][1] += pl
                x = fb if first else re
                x[0] += 1; x[1] += pl
        tot = [sum(agg[s][i] for s in SESSIONS) for i in range(2)]
        print("%-44s " % name + " ".join("%15s" % ("%3d %+8.0f" % tuple(agg[s])) for s in SESSIONS)
              + " %15s" % ("%3d %+8.0f" % tuple(tot)) + "   %3d %+7.0f   %3d %+7.0f" % (fb[0], fb[1], re[0], re[1]))


if __name__ == "__main__":
    main()
