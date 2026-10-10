"""The owner's formula after the daily limit (10-09 ~8:45pm), on the full read:

  before the day is down $500: v38 as built - a starter of 10% of the account,
      to 25% at +10c, to 50% at +20c (full = $7,500 of a $15,000 account)
  once the day is down $500 (closed trades, plus running winners): a starter of
      5% of the account, to 10% at +10c, to 25% at +20c - and when the stock
      proves itself (up +50% over its average, or +30% / +100%), it is taken to
      50% at once: the top-up, a separate lot at the ask with its own floor 10%
      under its price; no limit on how many a day
  every lot: the trailing exit (a third at 20% off the peak, a third at 40%,
      the rest at 50%) and everything sold at its floor if it falls back there.

Each trade keeps the moment of its buy from the run without a limit (a trade
taken smaller may end at another time - a small difference). Every table by day
and by session.

python3 v38_owner_limit.py <new windows> <old windows> <old minute bars>"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
import v38_final as F
from speedsim_study import session, SESSIONS
from v38_topup import topup_lot

ACCOUNT = 15000.0
FULL = 0.50 * ACCOUNT
SMALL = 0.25 * ACCOUNT
SMALL_STEPS = ((0.10, 0.4), (0.20, 1.0))         # 5% -> 10% -> 25% of the account


def small_trade(p, t_in, trigger):
    fill = p.ask_at(t_in)
    res = Q.run_ladder(p, t_in, fill, SMALL, 0.03, 0.10, steps=SMALL_STEPS, start=0.2, tiers=F.TIERS)
    te, pl, why, best, sh, avg, adds = res
    add = 0.0
    if trigger:
        global FULL
        import v38_topup
        v38_topup.FULL = FULL                     # the top-up takes it to 50% of the account
        add, _ = topup_lot(p, t_in, te, avg, trigger, 0.0, 0.10)
        add *= (FULL - SMALL) / (FULL - FULL / 4)  # topup_lot buys FULL - FULL/4; here FULL - SMALL
    return pl + add, te


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    F.FULL = FULL
    base = [x for k in sorted(by) for x in F.play_day(by[k], "A", dict(tiers=F.TIERS))]
    days = sorted({x[0]["day"] for x in base})
    paths = {}
    print("THE OWNER'S FORMULA AFTER -$500 A DAY - full read, $15,000 account (full position $%.0f)" % FULL)
    print("%-58s " % "" + " ".join("%9s" % d[5:] for d in days) + " %9s %9s | %8s %8s %8s" % ("TOTAL", "worst", "PRE", "RTH", "AFTER"))
    for label, trig, pre_only, limit in (
            ("all day, no limit", None, False, None),
            ("all day, after -$500: 5/10/25%, no top-up", 0, False, 500),
            ("all day, after -$500: 5/10/25%, to 50% at +30%", 0.30, False, 500),
            ("all day, after -$500: 5/10/25%, to 50% at +50%", 0.50, False, 500),
            ("all day, after -$500: 5/10/25%, to 50% at +100%", 1.00, False, 500),
            ("premarket only, no limit", None, True, None),
            ("premarket only, after -$500: 5/10/25%, to 50% at +50%", 0.50, True, 500)):
        out = []
        for d in days:
            xs = sorted([x for x in base if x[0]["day"] == d and (not pre_only or session(x[1]) == "PRE")],
                        key=lambda x: x[1])
            done = []                              # (entry, exit, P/L)
            for x in xs:
                day_pl = sum(pl for t0, te, pl in done if te <= x[1]) + \
                    sum(pl for t0, te, pl in done if te > x[1] and pl > 0)
                if limit and day_pl <= -limit:
                    r = x[0]
                    p = paths.get(id(r)) or paths.setdefault(id(r), S.Path(r))
                    pl, te = small_trade(p, x[1], trig)
                else:
                    pl, te = x[2], x[6]
                out.append((d, session(x[1]), pl))
                done.append((x[1], te, pl))
        per = [sum(v for dd, s, v in out if dd == d) for d in days]
        ses = [sum(v for dd, s, v in out if s == ss) for ss in SESSIONS]
        print("%-58s " % label + " ".join("%+9.0f" % v for v in per) + " %+9.0f %+9.0f | %+8.0f %+8.0f %+8.0f" % (
            sum(per), min(per), *ses))
    print("\nTHE WORST CASE FOR A GANGBUSTER - every trade as if after the limit (the formula on all of them):")
    for trig in (0, 0.30, 0.50, 1.00):
        tot, g = 0.0, {}
        for x in base:
            r = x[0]
            p = paths.get(id(r)) or paths.setdefault(id(r), S.Path(r))
            pl, te = small_trade(p, x[1], trig)
            tot += pl
            key = (x[0]["day"], x[0]["sym"])
            if key in (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM")) and x[2] > 1000:
                g[key[1]] = pl
        print("  %-28s FRGT %+7.0f  BIYA %+7.0f  SBFM %+7.0f  | all trades %+8.0f   (full size, no limit: FRGT +2,874 BIYA +11,446 SBFM +2,504, all +8,930)" % (
            "no top-up" if not trig else "to 50%% at +%.0f%%" % (100 * trig), g.get("FRGT", 0), g.get("BIYA", 0), g.get("SBFM", 0), tot))


if __name__ == "__main__":
    main()
