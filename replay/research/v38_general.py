"""The general picture, not BIYA's (the owner, 10-10: "the results are skewed
because of BIYA alone ... our modeling works around the two main stocks ... we
have to have a more general picture, to see if we can capture all of the ones
that are starting to move").

For each version of v38: the total, without BIYA 10-07, without the top three
(BIYA, FRGT 10-06, SBFM 10-07); by day and by session without BIYA; the P/L a
trade without BIYA; and over ALL 39 runs of 40%+ in the read - how many v38
made money on, and the share of each run it kept a share (median and mean) -
a measure no one stock can carry. Plus the fills 2 / 3 / 5 seconds late.

python3 v38_general.py <new windows> <old windows> <old minute bars>"""
import json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
import v38_gaps as G
from speedsim_giveback import run_of
from speedsim_study import session, SESSIONS

TOP3 = (("2026-10-07", "BIYA"), ("2026-10-06", "FRGT"), ("2026-10-07", "SBFM"))
VERS = (
    ("as decided 10-09: the day's high, no ceiling", dict(level="day", checks=True), 1.0),
    ("the day's high, the ask + the scale", dict(level="day", checks=True, limit="scale"), 1.0),
    ("the last sale's price, the ask + the scale", dict(level="exit", checks=True, limit="scale"), 1.0),
    ("PROPOSED: no level, the ask + the scale", dict(level="none", checks=True, limit="scale"), 1.0),
    ("  the same, filled 2s late", dict(level="none", checks=True, limit="scale"), 2.0),
    ("  the same, filled 3s late", dict(level="none", checks=True, limit="scale"), 3.0),
    ("  the same, filled 5s late", dict(level="none", checks=True, limit="scale"), 5.0),
    ("  the same, paying the scale in full", dict(level="none", checks=True, limit="scale", pay_all=True), 1.0),
)


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    runs = [(r, rn) for k in by for r in by[k] for rn in [run_of(r)] if rn and rn[0] - 1 >= 0.40]
    lag0 = S.BUY_LAG
    print("THE GENERAL PICTURE - v38 without its one big winner ($7,500 full, trailing thirds)")
    print("%-46s %4s %8s %8s %8s | %s | %s | %6s | %s" % (
        "", "n", "TOTAL", "no BIYA", "no top3", "no BIYA by day: " + " ".join("%6s" % d[5:] for d in days),
        "no BIYA: PRE / RTH / AFTER", "a trade", "39 runs: made money / share kept median, mean"))
    for name, kw, lag in VERS:
        S.BUY_LAG = lag
        xs = [x for k in sorted(by) for x in G.play(by[k], bars, **kw)]
        S.BUY_LAG = lag0
        nob = [x for x in xs if (x[0]["day"], x[0]["sym"]) != TOP3[0]]
        no3 = [x for x in xs if (x[0]["day"], x[0]["sym"]) not in TOP3]
        per = [sum(x[2] for x in nob if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in nob if session(x[1]) == s) for s in SESSIONS]
        made, kept = 0, []
        for r, rn in runs:
            ys = [x for x in xs if x[0] is r]
            pl = sum(x[2] for x in ys)
            made += pl > 0
            kept.append(sum(x[2] / x[5] for x in ys if x[5]) / (rn[4] - rn[2]))
        print("%-46s %4d %+8.0f %+8.0f %+8.0f | %s | %+7.0f %+7.0f %+7.0f | %+6.1f | %2d of %d / %+4.0f%% %+4.0f%%" % (
            name, len(xs), sum(x[2] for x in xs), sum(x[2] for x in nob), sum(x[2] for x in no3),
            "                " + " ".join("%+6.0f" % v for v in per), *ses,
            sum(x[2] for x in nob) / max(1, len(nob)), made, len(runs), 100 * st.median(kept), 100 * st.mean(kept)))


if __name__ == "__main__":
    main()
