"""The owner's speed strategy, every table split by session (the owner, 10-09
~1pm: "every table we construct from now on ... pre-market, during market hours
and after hours").

python3 speedsim_study.py <windows dir (secread.py output)> [full $, default 4000]

SPEED only (the owner's: buy at speed; ease-in 20% / 50% at +10c / full at
+20c over the first fill; stop at the buy or the floor = the average after
adds; out on giving back half the gain once it is up `arm`; back in as often
as it comes, at speed AND on a new high of the day). Second by second
(speedsim.play_ladder_hod on secsim's paths: buy at the ask 1s after the
signal, sell at the bid 0.5s after the decision).

Sessions by the entry's time, ET: PRE 4:00-9:30, RTH 9:30-16:00, AFTER
16:00-20:00. Windows with no bot buy in them (the day's top runners, the
missed names) are counted apart as well - "runner" rows."""
import os, sys
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q

SESSIONS = ("PRE", "RTH", "AFTER")
SETTINGS = ((0.00, 0.01), (0.03, 0.10), (0.05, 0.05), (0.05, 0.10), (0.10, 0.10))


def session(t):
    d = datetime.fromtimestamp(t, S.ET)
    m = d.hour * 60 + d.minute
    return "PRE" if m < 570 else "RTH" if m < 960 else "AFTER"


def cell(pl):
    if not pl:
        return "%22s" % "-"
    return "%3d %3d%% %+9.0f %+5.0f" % (len(pl), 100 * sum(x > 0 for x in pl) / len(pl), sum(pl), sum(pl) / len(pl))


def main():
    windows = S.load_windows(sys.argv[1])
    full = float(sys.argv[2]) if len(sys.argv) > 2 else 4000.0
    recs = [r for lst in windows.values() for r in lst]
    data = [(r, S.Path(r), Q.speed_state(r)) for r in recs]
    kinds = {id(r): ("bots" if r.get("buys") else "runner") for r in recs}
    days = sorted({r["day"] for r in recs})
    print("SPEED ONLY, second by second - %d windows (%d with bot buys, %d runner / missed), %s; full $%.0f"
          % (len(recs), sum(k == "bots" for k in kinds.values()), sum(k == "runner" for k in kinds.values()),
             ", ".join(d[5:] for d in days), full))
    print("a cell: trades, won %, P/L, P/L a trade\n")
    hdr = "%-14s %-7s " % ("stop / half", "windows") + " ".join("%22s" % s for s in SESSIONS + ("ALL",))
    print(hdr)
    keep = {}
    for su, arm in SETTINGS:
        for kind in ("all", "bots", "runner"):
            by = defaultdict(list)
            rows = []
            for r, p, st in data:
                if kind != "all" and kinds[id(r)] != kind:
                    continue
                for tr in Q.play_ladder_hod(p, r, st, full, su, arm):
                    by[session(tr[0])].append(tr[4])
                    rows.append((r, tr))
            allpl = [x for s in SESSIONS for x in by[s]]
            print("%-14s %-7s " % ("%2.0fc / %2.0fc" % (100 * su, 100 * arm) if kind == "all" else "", kind)
                  + " ".join(cell(by[s]) for s in SESSIONS) + " " + cell(allpl))
            keep[(su, arm, kind)] = rows
        print()
    print("BY DAY AND SESSION, 3c / 10c (P/L, trades):")
    rows = keep[(0.03, 0.10, "all")]
    for d in days:
        print("  %s  " % d[5:] + "   ".join(
            "%s %+8.0f (%d)" % (s, sum(tr[4] for r, tr in rows if r["day"] == d and session(tr[0]) == s),
                                sum(1 for r, tr in rows if r["day"] == d and session(tr[0]) == s))
            for s in SESSIONS))
    print("\nEACH WINDOW, 3c / 10c: the run seen in the window (its low to its high after it) and what the trades kept")
    print("  %-10s %-5s %-6s %-5s %8s %8s %6s %7s %9s %9s" % ("day", "sym", "kind", "sess", "low", "high", "run%",
                                                         "trades", "P/L", "best"))
    per = defaultdict(list)
    for r, tr in rows:
        per[id(r)].append(tr)
    for r, p, st in sorted(data, key=lambda x: (x[0]["day"], x[0]["start"])):
        px = [(k, x[4]) for k, x in ((x[0], x) for x in r["S"]) if x[4]]
        if not px:
            continue
        lo_k, lo = min(px, key=lambda x: x[1])
        hi = max(x[1] for x in px if x[0] >= lo_k)
        trs = per.get(id(r), [])
        print("  %-10s %-5s %-6s %-5s %8.3f %8.3f %5.0f%% %7d %+9.0f %+9.0f" % (
            r["day"], r["sym"], kinds[id(r)], session(r["start"] + lo_k), lo, hi, 100 * (hi / lo - 1), len(trs),
            sum(t[4] for t in trs), max([t[4] for t in trs] or [0])))


if __name__ == "__main__":
    main()
