"""The control for the scout test (10-10): is it the scout, or only the
minute-wide floor? v38 proposed (no re-entry level, the ask + the speed's
scale, the bot's buy checks, the trailing thirds) - no scouts - with the speed
buy's floor: 3c under the fill (as tested); the last closed 1-minute candle's
low (at most 10% / 5% under the fill); the lower of the last two candles'
lows. After an add the floor keeps that distance under the average. By
session, without BIYA / the top three, the 39 runs, a trade.

python3 v38_candle_floor.py <new windows> <old windows> <old minute bars>"""
import json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v38_final as F
import v38_gaps as G
from speedsim_giveback import run_of
from speedsim_study import session, SESSIONS

TOP3 = (("2026-10-07", "BIYA"), ("2026-10-06", "FRGT"), ("2026-10-07", "SBFM"))
WFF = ("2026-10-09", "WFF")


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    runs = [(r, rn) for k in by for r in by[k] for rn in [run_of(r)] if rn and rn[0] - 1 >= 0.40]
    print("THE CONTROL - v38 speed only, which floor (no scouts). Per session: trades, P/L, P/L without the top 3 and WFF")
    print("%-40s %4s %8s %8s %8s %8s | %-24s %-24s %-24s | %s" % ("", "n", "TOTAL", "no BIYA", "no top3", "no 3+WFF",
          "PRE n / P/L / no 3+WFF", "RTH n / P/L / no 3+WFF", "AFTER n / P/L / no 3+WFF", "39 runs made money / kept"))
    for name, fl in (("floor 3c (proposed)", "3c"), ("the last candle's low, at most 10%", "candle"),
                     ("the last candle's low, at most 5%", "candle5"), ("the lower of the last 2 candles, 10%", "candle2")):
        xs = [x for k in sorted(by) for x in G.play(by[k], bars, level="none", checks=True, limit="scale", speed_floor=fl)]
        nob = [x for x in xs if (x[0]["day"], x[0]["sym"]) != TOP3[0]]
        no3 = [x for x in xs if (x[0]["day"], x[0]["sym"]) not in TOP3]
        no4 = [x for x in no3 if (x[0]["day"], x[0]["sym"]) != WFF]
        cells = []
        for s in SESSIONS:
            a = [x for x in xs if session(x[1]) == s]
            b = [x for x in no4 if session(x[1]) == s]
            cells.append("%3d %+8.0f %+8.0f" % (len(a), sum(x[2] for x in a), sum(x[2] for x in b)))
        made, kept = 0, []
        for r, rn in runs:
            zs = [x for x in xs if x[0] is r]
            made += sum(x[2] for x in zs) > 0
            kept.append(sum(x[2] / x[5] for x in zs if x[5]) / (rn[4] - rn[2]))
        print("%-40s %4d %+8.0f %+8.0f %+8.0f %+8.0f | %-24s %-24s %-24s | %2d / %+4.0f%%" % (
            name, len(xs), sum(x[2] for x in xs), sum(x[2] for x in nob), sum(x[2] for x in no3),
            sum(x[2] for x in no4), *cells, made, 100 * st.median(kept)))


if __name__ == "__main__":
    main()
