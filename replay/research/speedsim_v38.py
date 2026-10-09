"""v38, the owner's speed strategy (named 10-09), replayed second by second -
and the owner's two variants side by side (10-09 ~2:30pm):

  A all the way : every entry with A's leash (3c stop, half-back from +10c).
  A then B      : A's leash until the stock has proven itself - a trade on it
                  closed 20%+ over its average - then every later entry on that
                  stock that day with B's leash (10% stop, half-back from +10%
                  of the price). (Within one trade the switch at +20% changes
                  nothing: past +20% the half-back line sits above both stops.)
  A then B'     : the same, B' = B with the stop 3c under the average after an add.

All: speed entry; ease-in 20% / 50% at +10c / full at +20c; re-entry at speed
on a new high of the day (the day's high before each window from its SECDUMP
HOD line or the minute bars); the scale-out - a quarter at +100%, a quarter at
+200%. $4,000 full. Tables per day and session (PRE / RTH / AFTER), and each
run's harvest: the share of the run kept, sold parts included.

python3 speedsim_v38.py <windows dir> [minute bars dir]"""
import json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
from speedsim_study import session, SESSIONS
from speedsim_reentry import hod_before
from speedsim_giveback import run_of

SC = ((1.0, 0.25), (2.0, 0.25))
FULL = 4000
PROVEN = 0.20
VARIANTS = ("A all the way", "A then B", "A then B'")


def leash(kind, fill):
    if kind == "A":
        return dict(stop_under=0.03, arm=0.10)
    kw = dict(stop_under=0.0, arm=0.10 * fill, mid_stop=False, stop_pct=0.10)
    if kind == "B'":
        kw["add_floor"] = 0.03
    return kw


def play_day(recs, variant):
    """Every trade on one stock-day, its windows in time order: [(rec, t_in,
    P/L, shares, average, kind)]. "Proven" carries across the windows."""
    out, proven = [], False
    for r in recs:
        p, st = S.Path(r), Q.speed_state(r)
        hi = {x[0]: x[2] for x in r["S"] if x[2]}
        after, first, top = -1.0, True, r.get("hod_before")
        for k in sorted(st):
            on, _ = st[k]
            h = hi.get(k)
            prev_top = top
            if h is not None:
                top = h if top is None else max(top, h)
            t = r["start"] + k + 0.99
            if t <= after or not on:
                continue
            if not first and (h is None or prev_top is None or h <= prev_top + 1e-9):
                continue
            t_in = t + S.BUY_LAG
            if t_in >= p.end - 5:
                break
            fill = p.ask_at(t_in)
            if not fill or fill <= 0:
                continue
            kind = "A" if variant == "A all the way" or not proven else variant.split()[-1]
            kw = leash(kind, fill)
            su, arm = kw.pop("stop_under"), kw.pop("arm")
            te, pl, why, best, sh, avg, adds = Q.run_ladder(p, t_in, fill, FULL, su, arm, scale=SC, **kw)
            out.append((r, t_in, pl, sh, avg, kind))
            if sh and pl / sh >= PROVEN * avg:
                proven = True
            after, first = te + S.SELL_LAG, False
    return out


def main():
    W = S.load_windows(sys.argv[1])
    bars = {}
    if len(sys.argv) > 2:
        for f in os.listdir(sys.argv[2]):
            if f.endswith(".json"):
                bars[f[:-5]] = json.load(open(os.path.join(sys.argv[2], f)))
    by = defaultdict(list)
    for r in (r for l in W.values() for r in l):
        if r.get("hod_before") is None and bars:
            r["hod_before"] = hod_before(bars, r)
        by[(r["day"], r["sym"])].append(r)
    for k in by:
        by[k].sort(key=lambda r: r["start"])
    days = sorted({d for d, _ in by})
    allt = {v: [] for v in VARIANTS}
    for v in VARIANTS:
        for k, recs in sorted(by.items()):
            allt[v] += play_day(recs, v)
    cell = lambda xs: "%4d %3d %3d %+9.0f" % (len(xs), sum(x[2] > 0 for x in xs), sum(x[2] <= 0 for x in xs),
                                             sum(x[2] for x in xs))
    print("v38 - %d windows, %s; $%d full; a cell: trades, wins, losses, P/L" % (
        sum(len(v) for v in by.values()), ", ".join(d[5:] for d in days), FULL))
    for sess in SESSIONS + ("ALL",):
        print("\n== %s ==" % {"PRE": "PREMARKET 4:00-9:30", "RTH": "REGULAR HOURS 9:30-4:00",
                               "AFTER": "AFTER HOURS 4:00-8:00pm", "ALL": "THE WHOLE DAY"}[sess])
        print("%-7s " % "day" + " ".join("%22s" % v for v in VARIANTS))
        pick = lambda xs, d: [x for x in xs if (d is None or x[0]["day"] == d) and (sess == "ALL" or session(x[1]) == sess)]
        for d in days + [None]:
            print("%-7s " % (d[5:] if d else "TOTAL") + " ".join("%22s" % cell(pick(allt[v], d)) for v in VARIANTS))
    print("\nTRADES ON B'S LEASH (after the stock proved itself):")
    for v in VARIANTS[1:]:
        xs = [x for x in allt[v] if x[5] != "A"]
        print("  %-10s %s" % (v, cell(xs)))
    print("\nEACH RUN OF 40%+ IN A WINDOW: the share of the run kept (all its trades, sold parts included)")
    print("  %-5s %-5s %-5s %-17s %-17s %5s | " % ("day", "sym", "sess", "low", "high", "run") +
          " ".join("%14s" % v for v in VARIANTS))
    for k, recs in sorted(by.items()):
        for r in recs:
            rn = run_of(r)
            if not rn or rn[0] - 1 < 0.40:
                continue
            kept = []
            for v in VARIANTS:
                xs = [x for x in allt[v] if x[0] is r]
                kept.append(sum(x[2] / x[3] for x in xs if x[3]) / (rn[4] - rn[2]))
            hm = lambda t: S.datetime.fromtimestamp(t, S.ET).strftime("%H:%M:%S")
            print("  %-5s %-5s %-5s %-17s %-17s %4.0f%% | " % (
                r["day"][5:], r["sym"], session(rn[1]), "$%.2f %s" % (rn[2], hm(rn[1])),
                "$%.2f %s" % (rn[4], hm(rn[3])), 100 * (rn[0] - 1)) + " ".join("%13.0f%%" % (100 * x) for x in kept))


if __name__ == "__main__":
    main()
