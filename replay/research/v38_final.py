"""v38 on everything read (the 10-08 read: the bots' moments 10-06..10-08; the
10-09 read: each day's top runners 10-06..10-09, BIYA 10-07 8:20, the bots'
10-09 moments), against the three bots live, by day and by session (the owner,
10-09 night). Second by second; every table PRE / RTH / AFTER.

python3 v38_final.py <new windows> <old windows> <old minute bars> <roundtrips 10-06..10-08> <roundtrips 10-09>

Windows of one stock-day that overlap: the longer, newer read is kept, the
older dropped. v38's first buy of a stock-day needs no new high; every later
one (any window that day) needs speed AND a new high of the day. Variants:
  v38      - as decided: A (3c stop, half-back once up 10c), adds at any price,
             a quarter at +100% and one at +200% of the full position's average
  arm 10%  - the half-back line arms once up 10% of the average (not 10c)
  bid line - the line's best and its trigger on the bid
  ratchet  - after +100% sold the stop is the average, after +200% it is +100%
  A then B - B's leash (10% stop, half-back from +10%) for later entries once
             the stock has proven itself (a trade closed 20%+ over its average)
  each window fresh - v38 with a window's first buy free of the new-high rule
             (as the tables before 10-09 night): what the rule costs or saves
  trailing tiers - the owner's exit (10-09 ~7:45pm): nothing sold on the way up;
             once full, a third at 20% off the peak, a third at 40%, the rest at
             50% - or everything at the floor (the full position's average less
             3c), whichever first
The full position: V38_FULL dollars (default $7,500 = 50% of a $15,000 account)."""
import json, os, sys
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
from speedsim_study import session, SESSIONS
from speedsim_reentry import hod_before
from speedsim_giveback import run_of

SC = ((1.0, 0.25), (2.0, 0.25))
BASE = dict(scale=SC, scale_full=True)
TIERS = ((0.20, 1 / 3), (0.40, 1 / 3), (0.50, 1.0))   # the owner's trailing exit, 10-09 ~7:45pm
FULL = float(os.environ.get("V38_FULL", "7500"))     # 50% of a $15,000 account (the owner, 10-09)
VARIANTS = [
    ("v38", "A", dict(BASE)),
    ("arm 10%", "A", dict(BASE, arm_pct=0.10)),
    ("bid line", "A", dict(BASE, line_bid=True)),
    ("ratchet", "A", dict(BASE, ratchet=True)),
    ("arm 10% + bid + ratchet", "A", dict(BASE, arm_pct=0.10, line_bid=True, ratchet=True)),
    ("A then B", "AB", dict(BASE)),
    ("v38, each window fresh", "FRESH", dict(BASE)),   # the earlier tables: a window's first buy free
    ("trailing tiers", "A", dict(tiers=TIERS)),
    ("tiers, each window fresh", "FRESH", dict(tiers=TIERS)),
]


SHOW = ("v38", "trailing tiers", "v38, each window fresh", "tiers, each window fresh")


def load(new_dir, old_dir, bars_dir):
    new = [r for l in S.load_windows(new_dir).values() for r in l]
    old = [r for l in S.load_windows(old_dir).values() for r in l]
    bars = {f[:-5]: json.load(open(os.path.join(bars_dir, f))) for f in os.listdir(bars_dir) if f.endswith(".json")}
    keep = list(new)
    for r in old:
        if any(n["day"] == r["day"] and n["sym"] == r["sym"] and n["start"] < r["end"] and r["start"] < n["end"]
               for n in new):
            continue                               # read again, longer, tonight
        if r.get("hod_before") is None:
            r["hod_before"] = hod_before(bars, r)
        keep.append(r)
    by = defaultdict(list)
    for r in keep:
        by[(r["day"], r["sym"])].append(r)
    for k in by:
        by[k].sort(key=lambda r: r["start"])
    return by


def play_day(recs, mode, kw):
    """[(rec, t_in, P/L, shares, average, leash)] - first buy of the day free,
    later ones at speed on a new high of the day, across the day's windows."""
    out, first, proven = [], True, False
    for r in recs:
        p, st = S.Path(r), Q.speed_state(r)
        hi = {x[0]: x[2] for x in r["S"] if x[2]}
        after, top = -1.0, r.get("hod_before")
        if mode == "FRESH":
            first = True
        for k in sorted(st):
            on, _ = st[k]
            h = hi.get(k)
            prev = top
            if h is not None:
                top = h if top is None else max(top, h)
            t = r["start"] + k + 0.99
            if t <= after or not on:
                continue
            if not first and (h is None or prev is None or h <= prev + 1e-9):
                continue
            t_in = t + S.BUY_LAG
            if t_in >= p.end - 5:
                break
            fill = p.ask_at(t_in)
            if not fill or fill <= 0:
                continue
            if mode == "AB" and proven:
                res = Q.run_ladder(p, t_in, fill, FULL, 0.0, 0.10 * fill, mid_stop=False, stop_pct=0.10, **kw)
                leash = "B"
            else:
                res = Q.run_ladder(p, t_in, fill, FULL, 0.03, 0.10, **kw)
                leash = "A"
            te, pl, why, best, sh, avg, adds = res
            out.append((r, t_in, pl, sh, avg, leash, te))
            if sh and pl / sh >= 0.20 * avg:
                proven = True
            after, first = te + S.SELL_LAG, False
    return out


def bots(rt_files):
    res = defaultdict(list)                        # (bot, day, session) -> [P/L]
    for f in rt_files:
        rts = json.load(open(f))
        for bot, days in rts.items():
            for day, lst in days.items():
                for rt in lst:
                    if rt["pl"] is not None:
                        res[(bot, day, session(S.ts(day, rt["open"])))].append(rt["pl"])
    return res


def cell(xs):
    return "%4d %3d %3d %+9.0f" % (len(xs), sum(x > 0 for x in xs), sum(x <= 0 for x in xs), sum(xs))


def main():
    by = load(sys.argv[1], sys.argv[2], sys.argv[3])
    live = bots(sys.argv[4:6])
    days = sorted({d for d, _ in by})
    allt = {}
    for name, mode, kw in VARIANTS:
        allt[name] = [x for k in sorted(by) for x in play_day(by[k], mode, kw)]
    names = ("v36", "v36b", "v37", "v38", "trailing tiers")
    print("THE THREE BOTS LIVE vs v38 (second by second) - %d windows, %s" % (
        sum(len(v) for v in by.values()), ", ".join(d[5:] for d in days)))
    print("a cell: trades, wins, losses, P/L. v38's moments: the bots' buys and each day's top runners;")
    print("v38 full position $%.0f (the bots as they really bought)\n" % FULL)
    for sess in SESSIONS + ("ALL",):
        print("== %s ==" % {"PRE": "PREMARKET 4:00-9:30", "RTH": "REGULAR HOURS 9:30-4:00",
                             "AFTER": "AFTER HOURS 4:00-8:00pm", "ALL": "THE WHOLE DAY"}[sess])
        print("%-7s " % "day" + " ".join("%22s" % n for n in names))
        ss = SESSIONS if sess == "ALL" else (sess,)
        for d in days + [None]:
            row = []
            for n in names:
                if n in allt:
                    xs = [x[2] for x in allt[n] if (d is None or x[0]["day"] == d) and session(x[1]) in ss]
                else:
                    xs = [v for (b, dd, s), l in live.items() if b == n and (d is None or dd == d) and s in ss for v in l]
                row.append(cell(xs))
            print("%-7s " % (d[5:] if d else "TOTAL") + " ".join("%22s" % c for c in row))
        print()
    print("v38's EXIT, PRICE-BASED CANDIDATES (all windows; P/L by session; the runs of 40%+ apart)")
    print("%-26s %20s %20s %20s %20s %10s %10s" % ("variant", "PRE", "RTH", "AFTER", "ALL", "runs", "rest"))
    for name, _, _ in VARIANTS:
        xs = allt[name]
        isrun = lambda x: (lambda rn: bool(rn) and rn[0] - 1 >= 0.40)(run_of(x[0]))
        print("%-26s %s %s %10.0f %10.0f" % (name, " ".join("%20s" % cell([x[2] for x in xs if session(x[1]) == s]) for s in SESSIONS),
              "%20s" % cell([x[2] for x in xs]), sum(x[2] for x in xs if isrun(x)), sum(x[2] for x in xs if not isrun(x))))
    print("\nEACH RUN OF 40%+ IN A WINDOW: the share of the run v38 kept (sold parts included), and its P/L")
    print("  %-5s %-5s %-5s %-17s %-17s %6s | %s" % ("day", "sym", "sess", "low", "high", "run",
                                                   " | ".join("%-22s" % n for n in SHOW)))
    hm = lambda t: datetime.fromtimestamp(t, S.ET).strftime("%H:%M:%S")
    for k in sorted(by):
        for r in by[k]:
            rn = run_of(r)
            if not rn or rn[0] - 1 < 0.40:
                continue
            cells = []
            for name in SHOW:
                xs = [x for x in allt[name] if x[0] is r]
                kept = sum(x[2] / x[3] for x in xs if x[3]) / (rn[4] - rn[2])
                cells.append("%5.0f%% %+8.0f (%2d)" % (100 * kept, sum(x[2] for x in xs), len(xs)))
            print("  %-5s %-5s %-5s %-17s %-17s %5.0f%% | %s" % (
                r["day"][5:], r["sym"], session(rn[1]), "$%.2f %s" % (rn[2], hm(rn[1])),
                "$%.2f %s" % (rn[4], hm(rn[3])), 100 * (rn[0] - 1), " | ".join("%-22s" % c for c in cells)))


if __name__ == "__main__":
    main()
