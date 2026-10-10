"""The owner's top-up (10-09 ~8:30pm): after the day's $500 loss limit v38 buys
a quarter size; a stock that PROVES ITSELF gets topped up to the full position
(50% of the account) - and if it then fails, everything bought for the top-up
is sold at any price at its floor.

The test takes the worst case for a gangbuster: EVERY trade as if it came
after the limit (a quarter size), on the full read (99 windows, 10-06..10-09).
The top-up is a separate lot: bought at the ask BUY_LAG after the trade first
reaches +trigger over its average, for (full - quarter) dollars, no ease-in;
it has its own floor (its fill less 3c, or less 10%) and the same trailing
exit (a third at 20% off the peak, a third at 40%, the rest at 50%). The
quarter lot keeps its own floor and exit - if the top-up fails, only the
top-up is sold; the starter that proved itself keeps riding.

python3 v38_topup.py <new windows> <old windows> <old minute bars>"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
import v38_final as F

FULL = 7500.0
GANGBUSTERS = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"))


def topup_lot(p, t_in, te, avg, trigger, floor, floor_pct):
    """(P/L, triggered?) of the top-up lot for one quarter-size trade."""
    i = p.at(t_in)
    for t, px, b, a in p.ev[i:]:
        if t > te:
            return 0.0, False
        if px >= avg * (1 + trigger) - 1e-9:
            t0 = t + S.BUY_LAG
            fill = p.ask_at(t0)
            if not fill:
                return 0.0, False
            kw = dict(stop_pct=floor_pct) if floor_pct else {}
            res = Q.run_ladder(p, t0, fill, FULL - FULL / 4, floor, 0.10, steps=(), start=1.0,
                               tiers=F.TIERS, **kw)
            return res[1], True
    return 0.0, False


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    F.FULL = FULL
    full = [x for k in sorted(by) for x in F.play_day(by[k], "A", dict(tiers=F.TIERS))]
    F.FULL = FULL / 4
    quarter = [x for k in sorted(by) for x in F.play_day(by[k], "A", dict(tiers=F.TIERS))]
    paths = {}
    gb = lambda x: (x[0]["day"], x[0]["sym"]) in GANGBUSTERS and x[2] > 0
    print("WORST CASE FOR A GANGBUSTER: every trade as if after the day's limit (a quarter size); full = $%.0f" % FULL)
    print("%-52s %9s %9s %9s | %10s %8s | %9s" % ("", "FRGT", "BIYA", "SBFM", "the others", "top-ups", "TOTAL"))

    def show(name, pls, n_top=None):
        g = {s: sum(v for x, v in pls if x[0]["sym"] == s and (x[0]["day"], s) in GANGBUSTERS and x[2] > 0)
             for _, s in GANGBUSTERS}
        others = sum(v for x, v in pls if not gb(x))
        print("%-52s %+9.0f %+9.0f %+9.0f | %+10.0f %8s | %+9.0f" % (name, g["FRGT"], g["BIYA"], g["SBFM"], others,
              "-" if n_top is None else str(n_top), sum(v for _, v in pls)))

    show("full size all day (no limit)", [(x, x[2]) for x in full])
    show("a quarter, no top-up", [(x, x[2]) for x in quarter])
    for trigger in (0.50, 1.00):
        for floor, fpct, fname in ((0.03, 0.0, "floor 3c under its fill"), (0.0, 0.10, "floor 10% under its fill")):
            pls, n = [], 0
            for x in quarter:
                r = x[0]
                p = paths.get(id(r)) or paths.setdefault(id(r), S.Path(r))
                add, hit = topup_lot(p, x[1], x[6], x[4], trigger, floor, fpct)
                n += hit
                pls.append((x, x[2] + add))
            show("a quarter + top-up at +%.0f%%, %s" % (100 * trigger, fname), pls, n)


if __name__ == "__main__":
    main()
