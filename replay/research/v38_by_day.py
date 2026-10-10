"""v38 speed only (no scouts, no re-entry level, the ask + the speed's scale),
without BIYA 10-07: each day by session - trades, won, P/L - for the 3c floor
and the minute-wide floor (the last 1-minute candle's low, at most 10%). The
biggest single stock of each day and session named, so one stock does not hide.

python3 v38_by_day.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    by = {k: v for k, v in by.items() if k != ("2026-10-07", "BIYA")}
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    for fl, name in (("candle", "THE MINUTE-WIDE FLOOR"), ("3c", "THE 3c FLOOR")):
        xs = [x for k in sorted(by) for x in G.play(by[k], bars, level="none", checks=True, limit="scale", speed_floor=fl)]
        print("\n%s - v38 speed only, no scouts, WITHOUT BIYA ($15,000 account, $7,500 full)" % name)
        print("%-6s | %-30s | %-30s | %-30s | %s" % ("day", "PRE 4:00-9:30", "RTH 9:30-4:00", "AFTER 4:00-8:00",
                                                    "THE DAY"))
        for d in days + ["TOTAL"]:
            cells = []
            for s in list(SESSIONS) + [None]:
                ys = [x for x in xs if (d == "TOTAL" or x[0]["day"] == d) and (s is None or session(x[1]) == s)]
                top = {}
                for x in ys:
                    top[x[0]["sym"]] = top.get(x[0]["sym"], 0.0) + x[2]
                best = max(top.items(), key=lambda kv: abs(kv[1])) if top else None
                cells.append("%3d %2d %+7.0f %-12s" % (len(ys), sum(x[2] > 0 for x in ys), sum(x[2] for x in ys),
                             ("(%s %+.0f)" % (best[0], best[1])) if best and d != "TOTAL" else ""))
            print("%-6s | %s | %s | %s | %s" % (d[5:] if d != "TOTAL" else d, *cells))


if __name__ == "__main__":
    main()
