"""The owner's scout, third version (10-10): "the scout is there and you see
the appreciation right away ... at 1% ... the speed picks up and the stock goes
up with it, then you add 10%, then 20%, the rest 20% ... if the speed does not
pick up, we leave the scout there, we don't even close it, no lower limit ...
a lot more open positions with very little money in them ... if the scout
becomes a chug, you add five percent when it goes up 10% (now 6%); if it keeps
going, another 10% - all in all about 20%".

  the scout     1% of the account (2% tried too) when a stock is running (up 20%
                from its low so far, within 10% of its high, $250k a minute
                over 10 minutes). No floor: it floats to the end of the read's
                window (live it would float to the session's end - the read
                cannot show that far).
  speed path    the full speed test fires and the price is over the scout's:
                a lot of 10% of the account at the ask (+2% limit), to 30% at
                +10c over that lot's first price, 50% at +20c (any price); its
                floor the average less 3c; once at 50% the trailing thirds. At
                its floor the lot is sold - the scout stays, and a later speed
                signal can build a new lot.
  chug path     no speed, the price 10% over the scout's: a lot of 5%; another
                10% over that lot's price: to 15%. Its floor: the last closed
                candle's low (at most 10% under). A speed signal while a chug
                lot is held turns it into the speed path.
A stock with no scout yet: v38's own speed buy, as proposed.

THE READ IS CHOSEN BY WHAT HAPPENED; the bots' buy windows are the fairer half.

python3 v38_scout3.py <new windows> <old windows> <old minute bars>"""
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
SPEED_LOT = {1: 0.10, 2: 0.30, 3: 0.50}            # the speed path's lot, of the account
CHUG_LOT = {1: 0.05, 2: 0.15}                      # the chug path's lot


def minutes_low(rec):
    m = {}
    for x in rec["S"]:
        if x[1]:
            mm = (rec["start"] + x[0]) // 60
            m[mm] = min(m.get(mm, x[3]), x[3])
    return m


def float_scout(p, rec, sp, t_in, scout=0.01, chug=True, chug_rth=False):
    """The scout from t_in to the window's end, with the lots built on it.
    Returns [(kind, t in, P/L, t out)] - the scout itself and every lot."""
    out = []
    s_px = p.ask_at(t_in)
    s_sh = int(scout * ACCOUNT / s_px)
    if s_sh <= 0:
        return out
    mlow = minutes_low(rec)
    lot = None                                     # dict(path, stage, sh, cost, floor, base, best, banked, sold, j, t0)
    pending = None                                 # (fill time, the ask at the decision or None, path, stage)
    nk = int(t_in - rec["start"]) + 1
    chug_over = s_px * 1.10                        # a new chug lot only over this (the last one's best)

    def add(path, stage, px, t):
        nonlocal lot
        tgt = (SPEED_LOT if path == "speed" else CHUG_LOT)[stage] * ACCOUNT
        if lot is None:
            lot = dict(path=path, stage=0, sh=0, cost=0.0, floor=0.0, base=None, best=px,
                       banked=0.0, sold=0, j=0, t0=t)
        if path == "speed" and lot["path"] == "chug":
            lot["path"] = "speed"                  # the chug lot joins the speed path
        n = int((tgt - lot["cost"]) / px)
        if n > 0:
            lot["sh"] += n
            lot["cost"] += n * px
        lot["stage"] = stage
        avg = lot["cost"] / lot["sh"] if lot["sh"] else px
        if path == "speed":
            if stage == 1:
                lot["base"] = px
            lot["floor"] = max(lot["floor"], avg - 0.03) if stage > 1 else avg - 0.03
        else:
            lo = mlow.get(int(t // 60) - 1)
            fl = max(lo if lo else px * 0.90, px * 0.90)
            lot["floor"] = max(lot["floor"], min(fl, px - 0.03))
            if stage == 1:
                lot["base"] = px
        lot["best"] = px

    def close(t, why):
        nonlocal lot, chug_over
        if lot["path"] == "chug":
            chug_over = max(chug_over, lot["best"])
        xp = p.bid_at(t + S.SELL_LAG)
        avg = lot["cost"] / lot["sh"] if lot["sh"] else 0.0
        out.append((lot["path"], lot["t0"], (xp - avg) * lot["sh"] + lot["banked"], t))
        lot = None

    for t, px, b, a in p.ev[p.at(t_in):]:
        if pending and t >= pending[0]:
            tf, a0, path, stage = pending
            pending = None
            ax = p.ask_at(tf)
            if ax and (a0 is None or ax <= a0 * 1.02 + 1e-9) and (lot is not None or stage == 1):
                add(path, stage, ax, tf)
        while pending is None and rec["start"] + nk + 0.99 <= t:
            td = rec["start"] + nk + 0.99
            nk += 1
            if td + S.BUY_LAG < t:
                continue
            on = sp.get(nk - 1, (False,))[0]
            if on and (lot is None or lot["path"] == "chug") and px >= s_px:
                pending = (td + S.BUY_LAG, p.ask_at(td), "speed", 1)
        if b and a:
            tol = max(S.PRINT_TOL_CENTS, S.PRINT_TOL_PCT * px)
            if px > a + tol or px < b - tol:
                continue
        if pending is None:
            if lot is None and chug and (not chug_rth or session(t) == "RTH") and px >= chug_over - 1e-9:
                pending = (t + S.BUY_LAG, None, "chug", 1)
            elif lot is not None and lot["path"] == "speed" and lot["stage"] in (1, 2):
                if px >= lot["base"] + (0.10 if lot["stage"] == 1 else 0.20) - 1e-9:
                    pending = (t + S.BUY_LAG, None, "speed", lot["stage"] + 1)
            elif lot is not None and lot["path"] == "chug" and lot["stage"] == 1:
                if px >= lot["base"] * 1.10 - 1e-9:
                    pending = (t + S.BUY_LAG, None, "chug", 2)
        if lot is None:
            continue
        lot["best"] = max(lot["best"], px)
        if px <= lot["floor"] + 1e-9 or (b and a and (b + a) / 2 <= lot["floor"] + 1e-9):
            close(t, "floor")
            pending = None                         # an add sent for the closed lot is dropped
            continue
        if lot["path"] == "speed" and lot["stage"] == 3 and pending is None:
            sh = lot["sh"]
            avg = lot["cost"] / sh
            full_sh = sh + lot["sold"]
            while lot["j"] < len(F.TIERS) and px <= lot["best"] * (1 - F.TIERS[lot["j"]][0]) + 1e-9:
                xp = p.bid_at(t + S.SELL_LAG)
                last = lot["j"] == len(F.TIERS) - 1
                q = lot["sh"] if last else min(lot["sh"], int(round(F.TIERS[lot["j"]][1] * full_sh)))
                lot["banked"] += (xp - avg) * q
                lot["sh"] -= q
                lot["cost"] -= avg * q
                lot["sold"] += q
                lot["j"] += 1
                if lot["sh"] <= 0:
                    out.append(("speed", lot["t0"], lot["banked"], t))
                    lot = None
                    break
    end_bid = p.bid_at(p.end)
    if lot is not None:
        avg = lot["cost"] / lot["sh"] if lot["sh"] else 0.0
        out.append((lot["path"], lot["t0"], (end_bid - avg) * lot["sh"] + lot["banked"], p.end))
    out.append(("scout", t_in, (end_bid - s_px) * s_sh, p.end))
    return out


def play(recs, scout=None, chug=True, chug_rth=False, run=0.20, near=0.10):
    """[(rec, t, P/L, kind, t out)] - one stock's day."""
    out = []
    for r in recs:
        p = S.Path(r)
        sp = G.signals(r, checks=True)
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
            is_scout = (scout and x and low and top and k >= 600 and x[4] >= low * (1 + run)
                        and x[4] >= top * (1 - near) and dol[k + 1] - dol[k - 599] >= 10 * Q.DOLLARS_MIN)
            if not (sp[k][0] or is_scout):
                continue
            t_in = t + S.BUY_LAG
            if t_in >= p.end - 5:
                break
            fill = p.ask_at(t_in)
            if not fill or fill <= 0 or fill > p.ask_at(t) * 1.02 + 1e-9:
                continue
            if is_scout:                           # the scout floats to the window's end
                for kind, t0, pl, te in float_scout(p, r, sp, t_in, scout, chug, chug_rth):
                    out.append((r, t0, pl, kind, te))
                break
            res = Q.run_ladder(p, t_in, fill, F.FULL, 0.03, 0.10, tiers=F.TIERS)
            out.append((r, t_in, res[1], "v38", res[0]))
            after = res[0] + S.SELL_LAG
    return out


VARIANTS = (
    ("v38 speed only (no scout)", dict()),
    ("scout 1% floating + speed path + chug path", dict(scout=0.01)),
    ("scout 1% floating + speed path only", dict(scout=0.01, chug=False)),
    ("scout 1% floating + speed + chug in RTH only", dict(scout=0.01, chug_rth=True)),
    ("scout 2% floating + speed path + chug path", dict(scout=0.02)),
)


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    print("THE OWNER'S FLOATING SCOUT - 1%, no floor; a speed path 10/30/50%; a chug path 5/15% ($15,000 account)")
    print("%-46s %4s " % ("", "n") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %s" % ("TOTAL", "PRE", "RTH", "AFTER", "  ".join("%-5s" % b[1] for b in BIG)))
    for name, kw in VARIANTS:
        xs = [x for k in sorted(by) for x in play(by[k], **kw)]
        per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        big = [sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) == b) for b in BIG]
        print("%-46s %4d " % (name, len(xs)) + " ".join("%+7.0f" % v for v in per) +
              " %+8.0f | %+7.0f %+7.0f %+7.0f | %s" % (sum(per), *ses, " ".join("%+6.0f" % v for v in big)))
        if not kw:
            continue
        for kind in ("scout", "speed", "chug", "v38"):
            ys = [x for x in xs if x[3] == kind]
            if not ys:
                continue
            fair = [x for x in ys if x[0].get("buys")]
            print("%-46s      %-6s %3d (%d won) %+8.0f - PRE %+.0f / RTH %+.0f / AFTER %+.0f | in the bots' windows %d %+.0f" % (
                "", kind, len(ys), sum(x[2] > 0 for x in ys), sum(x[2] for x in ys),
                *(sum(x[2] for x in ys if session(x[1]) == s) for s in SESSIONS), len(fair), sum(x[2] for x in fair)))
        sc = sorted([x for x in xs if x[3] == "scout"], key=lambda x: x[2])
        if sc:
            print("%-46s      the scouts' worst %s, best %s" % ("", ", ".join("%s %s %+.0f" % (x[0]["day"][5:], x[0]["sym"], x[2]) for x in sc[:3]),
                  ", ".join("%s %s %+.0f" % (x[0]["day"][5:], x[0]["sym"], x[2]) for x in sc[-3:])))


if __name__ == "__main__":
    main()
