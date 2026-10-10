"""The owner's scouts (10-10): "1% or 2% of the account, very very small ...
on all the top half a dozen stocks that are really running" - in place BEFORE
the speed test fires. The scout is the first rung of v38's ease-in: when the
price climbs from the scout's fill (+10c / +20c, or +5% / +10%), it is added
to 25%, then 50% of the account - the scout's own gain is the signal, and the
adds do not wait for the speed test. Once full: the trailing thirds; after an
add the floor is the average less 3c (as v38); before any add, the scout's own
floor (10%, or 5%, under its fill - a 3c floor would shake it out at once).

When a stock is a scout's (only past prices, nothing from later): up 20% (or
10%) from its lowest price so far in the read, within 10% of its high of the
day so far, $2.5M traded in the last 10 minutes ($250k a minute). One position
a stock at a time; a new scout after a sale when it qualifies again. The speed
buys stay as v38 proposed (no re-entry level, a limit at the ask + 2%, the
bot's buy checks), whenever v38 holds nothing in the stock; a scout's buy is a
limit at the ask + 2% too.

THE READ IS CHOSEN BY WHAT HAPPENED: the runner windows start 10 minutes before
a big run's low - a scout there is near the bottom of a known run. The windows
of the bots' own buys were chosen by the bots' signals, not by the outcome.
Both are shown apart; the second is the fairer test.

python3 v38_scout.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS

BIG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"), ("2026-10-08", "FLYE"), ("2026-10-09", "WFF"))
STEPS_CENTS = ((0.10, 0.5), (0.20, 1.0))


def play(recs, size=None, run=0.20, near=0.10, floor=0.10, pct_steps=None, money=2_500_000):
    """[(rec, t_in, P/L, kind, t_out, adds made)] - one stock's day."""
    out, first = [], True
    for r in recs:
        p, st = S.Path(r), G.signals(r, checks=True)
        rows = {x[0]: x for x in r["S"] if x[1]}
        last = max(rows) if rows else -1
        dol = [0.0] * (last + 2)
        for k in range(last + 1):
            x = rows.get(k)
            dol[k + 1] = dol[k] + ((x[4] * x[5]) if x else 0.0)
        after, top, low = -1.0, r.get("hod_before"), None
        for k in sorted(st):
            x = rows.get(k)
            if x:
                top = x[2] if top is None else max(top, x[2])
                low = x[3] if low is None else min(low, x[3])
            t = r["start"] + k + 0.99
            if t <= after:
                continue
            sp = st[k][0]
            scout = False
            if size and not sp and x and low and top and k >= 600:
                px = x[4]
                scout = (px >= low * (1 + run) and px >= top * (1 - near)
                         and dol[k + 1] - dol[k - 599] >= money)
            if not (sp or scout):
                continue
            t_in = t + S.BUY_LAG
            if t_in >= p.end - 5:
                break
            fill = p.ask_at(t_in)
            if not fill or fill <= 0 or fill > p.ask_at(t) * 1.02 + 1e-9:
                continue                           # a limit at the ask + 2%: missed, try again
            if sp:
                res = Q.run_ladder(p, t_in, fill, F.FULL, 0.03, 0.10, tiers=F.TIERS)
                kind = "speed"
            else:
                steps = ((pct_steps[0] * fill, 0.5), (pct_steps[1] * fill, 1.0)) if pct_steps else STEPS_CENTS
                res = Q.run_ladder(p, t_in, fill, F.FULL, fill * floor, 0.10, steps=steps,
                                   start=size / 0.50, tiers=F.TIERS, add_floor=0.03)
                kind = "scout"
            te, pl, why, best, sh, avg, adds = res
            out.append((r, t_in, pl, kind, te, adds))
            after, first = te + S.SELL_LAG, False
    return out


VARIANTS = (
    ("v38 proposed (speed only, no level)", dict()),
    ("+ scouts 2%: run 20%, near 10%, floor 10%, +10c/+20c", dict(size=0.02)),
    ("+ scouts 1%: the same", dict(size=0.01)),
    ("+ scouts 2%, the steps +5% / +10%", dict(size=0.02, pct_steps=(0.05, 0.10))),
    ("+ scouts 2%, the steps +10% / +20%", dict(size=0.02, pct_steps=(0.10, 0.20))),
    ("+ scouts 2%, run 10% (looser)", dict(size=0.02, run=0.10)),
    ("+ scouts 2%, floor 5%", dict(size=0.02, floor=0.05)),
)


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    print("THE OWNER'S SCOUTS - the first rung of the ease-in, before the speed test ($15,000 account, $7,500 full)")
    print("%-54s %4s %3s " % ("", "n", "won") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %s" % ("TOTAL", "PRE", "RTH", "AFTER", "  ".join("%-5s" % b[1] for b in BIG)))
    for name, kw in VARIANTS:
        xs = [x for k in sorted(by) for x in play(by[k], **kw)]
        per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        big = [sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) == b) for b in BIG]
        print("%-54s %4d %3d " % (name, len(xs), sum(x[2] > 0 for x in xs)) + " ".join("%+7.0f" % v for v in per) +
              " %+8.0f | %+7.0f %+7.0f %+7.0f | %s" % (sum(per), *ses, " ".join("%+6.0f" % v for v in big)))
        sc = [x for x in xs if x[3] == "scout"]
        if not sc:
            continue
        grew = [x for x in sc if x[5] >= 1]
        full = [x for x in sc if x[5] >= 2]
        bots = [x for x in sc if x[0].get("buys")]
        runs = [x for x in sc if not x[0].get("buys")]
        print("%-54s      scouts %d (%d won) %+.0f - PRE %+.0f / RTH %+.0f / AFTER %+.0f" % (
            "", len(sc), sum(x[2] > 0 for x in sc), sum(x[2] for x in sc),
            *(sum(x[2] for x in sc if session(x[1]) == s) for s in SESSIONS)))
        print("%-54s      never added %d %+.0f | reached the first add %d %+.0f | full %d (%d won) %+.0f" % (
            "", len(sc) - len(grew), sum(x[2] for x in sc if x[5] == 0), len(grew), sum(x[2] for x in grew),
            len(full), sum(x[2] > 0 for x in full), sum(x[2] for x in full)))
        print("%-54s      in the bots' buy windows %d %+.0f | in runner-only windows %d %+.0f" % (
            "", len(bots), sum(x[2] for x in bots), len(runs), sum(x[2] for x in runs)))
        best = sorted(sc, key=lambda x: -x[2])[:5]
        print("%-54s      best scouts: %s" % ("", ", ".join("%s %s %s %+.0f" % (
            x[0]["day"][5:], x[0]["sym"], datetime.fromtimestamp(x[1], S.ET).strftime("%H:%M"), x[2]) for x in best)))
        ts = sorted([(x[1], 1) for x in sc] + [(x[4], -1) for x in sc])
        n = mx = 0
        for t, d in ts:
            n += d
            mx = max(mx, n)
        print("%-54s      the most scouts open at once: %d" % ("", mx))


if __name__ == "__main__":
    main()
