"""The owner's scout WITH the speed (10-10): "a scout combined with the speed
signal ... we start adding as the speed picks up ... a little bit lower than the
threshold, as long as it picks up, it will start to add up a little bit ... and
it will be progressive, not adding the whole 50% - that's where our big losses
come from ... if the speed picks up you increase faster".

The position, step by step (shares of the account):
  the scout       1-2%, when a stock is running (up 20% from its low so far,
                  within 10% of its high so far, $250k a minute over 10 min)
  the warm add    to 3-5% when the speed is warm (the speed test with its bar
                  lowered to 0.15 / 0.20 - the move 3%, $250k, the candle as now)
  the speed add   to 10% when the full speed test fires (0.30) - v38's first buy
  the ease-in     to 25% at +10c over the speed add's price, 50% at +20c
No add ever comes from price alone before the speed. A first buy, the warm
add and the speed add are limits at the ask + 2% (missed: the next signal
tries again); the ease-in adds at any price (decided). The floor: the scout's
own (10% or 5% under its fill), kept that wide through the warm add (under the
average); from the speed add on, the average less 3c (as v38 after an add).
Once full (50%): the trailing thirds. A stock v38 does not hold, with the
full speed on, gets v38's own speed buy (10%, then the ease-in).

THE READ IS CHOSEN BY WHAT HAPPENED (the runner windows start 10 minutes before
a big run's low) - the bots' buy windows are the fairer half, shown apart.

python3 v38_scout2.py <new windows> <old windows> <old minute bars>"""
import os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS

ACCOUNT = 15000.0
BIG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"), ("2026-10-08", "FLYE"), ("2026-10-09", "WFF"))
TARGET = {0: None, 1: None, 2: 0.10, 3: 0.25, 4: 0.50}


def manage(p, rec, sp, warm, t_in, kind, scout=0.02, warm_to=0.05, scout_floor=0.10):
    """One position from t_in: (exit time, P/L, why, the stage reached, shares)."""
    tgt = {0: scout, 1: warm_to, 2: 0.10, 3: 0.25, 4: 0.50}
    fill = p.ask_at(t_in)
    st = {"sh": 0, "cost": 0.0}

    def buy(stage, px):
        n = int((tgt[stage] * ACCOUNT - st["cost"]) / px)
        if n > 0:
            st["sh"] += n
            st["cost"] += n * px

    if kind == "scout":
        buy(0, fill)
        stage, base, floor = 0, None, fill * (1 - scout_floor)
    else:
        buy(2, fill)
        stage, base, floor = 2, fill, fill - 0.03
    if not st["sh"]:
        return t_in, 0.0, "nothing", stage, 0
    best, banked, sold, j = fill, 0.0, 0, 0
    pending = None                                 # (fill time, the ask at the decision, stage)
    nk = int(t_in - rec["start"]) + 1              # the next second whose signal is read
    for t, px, b, a in p.ev[p.at(t_in):]:
        if pending and t >= pending[0]:
            tf, a0, sg = pending
            pending = None
            ax = p.ask_at(tf)
            if ax and (sg >= 3 or ax <= a0 * 1.02 + 1e-9):
                buy(sg, ax)
                stage = sg
                avg = st["cost"] / st["sh"]
                if sg == 1:
                    floor = max(floor, avg * (1 - scout_floor))
                else:
                    if sg == 2:
                        base = ax
                    floor = max(floor, avg - 0.03)
                best = max(ax, px)
        while pending is None and rec["start"] + nk + 0.99 <= t:   # the signals, second by second
            td = rec["start"] + nk + 0.99
            if td + S.BUY_LAG < t:                 # a second already past: no buying at its old ask
                nk += 1
                continue
            if stage <= 1 and sp.get(nk, (False,))[0]:
                pending = (td + S.BUY_LAG, p.ask_at(td), 2)
            elif stage == 0 and warm.get(nk, (False,))[0]:
                pending = (td + S.BUY_LAG, p.ask_at(td), 1)
            nk += 1
        if b and a:
            tol = max(S.PRINT_TOL_CENTS, S.PRINT_TOL_PCT * px)
            if px > a + tol or px < b - tol:
                continue
        best = max(best, px)
        if pending is None and base is not None and stage in (2, 3):
            if px >= base + (0.10 if stage == 2 else 0.20) - 1e-9:
                pending = (t + S.BUY_LAG, None, stage + 1)
        avg = st["cost"] / st["sh"]
        sh = st["sh"]
        if px <= floor + 1e-9 or (b and a and (b + a) / 2 <= floor + 1e-9):
            xp = p.bid_at(t + S.SELL_LAG)
            return t, (xp - avg) * sh + banked, "floor", stage, sh + sold
        if stage == 4 and pending is None:         # all in: the trailing thirds
            full_sh = sh + sold
            while j < len(F.TIERS) and px <= best * (1 - F.TIERS[j][0]) + 1e-9:
                xp = p.bid_at(t + S.SELL_LAG)
                q = sh if j == len(F.TIERS) - 1 else min(sh, int(round(F.TIERS[j][1] * full_sh)))
                banked += (xp - avg) * q
                st["sh"] -= q
                st["cost"] -= avg * q
                sold += q
                sh = st["sh"]
                j += 1
                if sh <= 0:
                    return t, banked, "thirds", stage, sold
    xp = p.bid_at(p.end)
    sh = st["sh"]
    avg = st["cost"] / sh if sh else 0.0
    return p.end, (xp - avg) * sh + banked, "open", stage, sh + sold


def play(recs, scout=None, warm_to=0.05, warm_speed=0.15, scout_floor=0.10, run=0.20, near=0.10):
    out = []
    for r in recs:
        p = S.Path(r)
        sp = G.signals(r, checks=True)
        s0 = Q.SPEED
        Q.SPEED = warm_speed
        warm = G.signals(r, checks=True) if scout else {}
        Q.SPEED = s0
        rows = {x[0]: x for x in r["S"] if x[1]}
        last = max(rows) if rows else -1
        dol = [0.0] * (last + 2)
        for k in range(last + 1):
            x = rows.get(k)
            dol[k + 1] = dol[k] + ((x[4] * x[5]) if x else 0.0)
        after, top, low = -1.0, r.get("hod_before"), None
        for k in sorted(sp):
            x = rows.get(k)
            if x:
                top = x[2] if top is None else max(top, x[2])
                low = x[3] if low is None else min(low, x[3])
            t = r["start"] + k + 0.99
            if t <= after:
                continue
            kind = "speed" if sp[k][0] else None
            if not kind and scout and x and low and top and k >= 600:
                if (x[4] >= low * (1 + run) and x[4] >= top * (1 - near)
                        and dol[k + 1] - dol[k - 599] >= 10 * Q.DOLLARS_MIN):
                    kind = "scout"
            if not kind:
                continue
            t_in = t + S.BUY_LAG
            if t_in >= p.end - 5:
                break
            fill = p.ask_at(t_in)
            if not fill or fill <= 0 or fill > p.ask_at(t) * 1.02 + 1e-9:
                continue
            te, pl, why, stage, sh = manage(p, r, sp, warm, t_in, kind, scout or 0.0, warm_to, scout_floor)
            out.append((r, t_in, pl, kind, te, stage))
            after = te + S.SELL_LAG
    return out


VARIANTS = (
    ("v38 speed only (no scout)", dict()),
    ("scout 2%, then the full speed only", dict(scout=0.02, warm_to=0.02)),
    ("scout 2%, warm 0.15 -> 5%, speed -> 10%", dict(scout=0.02, warm_to=0.05, warm_speed=0.15)),
    ("scout 2%, warm 0.20 -> 5%, speed -> 10%", dict(scout=0.02, warm_to=0.05, warm_speed=0.20)),
    ("scout 1%, warm 0.15 -> 3%, speed -> 10%", dict(scout=0.01, warm_to=0.03, warm_speed=0.15)),
    ("scout 2%, warm 0.15 -> 5%, the scout's floor 5%", dict(scout=0.02, warm_to=0.05, warm_speed=0.15, scout_floor=0.05)),
    ("scout 2%, warm 0.15 -> 5%, a looser scout (up 10%)", dict(scout=0.02, warm_to=0.05, warm_speed=0.15, run=0.10)),
)


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    print("THE OWNER'S SCOUT WITH THE SPEED - adds only as the speed picks up, step by step ($15,000 account)")
    print("%-50s %4s %3s " % ("", "n", "won") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %s" % ("TOTAL", "PRE", "RTH", "AFTER", "  ".join("%-5s" % b[1] for b in BIG)))
    for name, kw in VARIANTS:
        xs = [x for k in sorted(by) for x in play(by[k], **kw)]
        per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        big = [sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) == b) for b in BIG]
        print("%-50s %4d %3d " % (name, len(xs), sum(x[2] > 0 for x in xs)) + " ".join("%+7.0f" % v for v in per) +
              " %+8.0f | %+7.0f %+7.0f %+7.0f | %s" % (sum(per), *ses, " ".join("%+6.0f" % v for v in big)))
        sc = [x for x in xs if x[3] == "scout"]
        if not sc:
            continue
        by_stage = {s: [x for x in sc if x[5] == s] for s in range(5)}
        print("%-50s      scouts %d (%d won) %+.0f - PRE %+.0f / RTH %+.0f / AFTER %+.0f" % (
            "", len(sc), sum(x[2] > 0 for x in sc), sum(x[2] for x in sc),
            *(sum(x[2] for x in sc if session(x[1]) == s) for s in SESSIONS)))
        print("%-50s      how far they grew: %s" % ("", " | ".join(
            "%s %d %+.0f" % (n, len(by_stage[s]), sum(x[2] for x in by_stage[s]))
            for s, n in ((0, "scout only"), (1, "warm"), (2, "10%"), (3, "25%"), (4, "full")))))
        bots = [x for x in sc if x[0].get("buys")]
        print("%-50s      in the bots' buy windows %d %+.0f | runner-only windows %d %+.0f" % (
            "", len(bots), sum(x[2] for x in bots), len(sc) - len(bots), sum(x[2] for x in sc if not x[0].get("buys"))))
        best = sorted(sc, key=lambda x: -x[2])[:5]
        print("%-50s      best: %s" % ("", ", ".join("%s %s %s %+.0f" % (
            x[0]["day"][5:], x[0]["sym"], datetime.fromtimestamp(x[1], S.ET).strftime("%H:%M"), x[2]) for x in best)))


if __name__ == "__main__":
    main()
