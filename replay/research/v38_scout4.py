"""The scout as the owner meant it (10-10: "you already have a scout ... speed
happens - that's exactly where you should add"). The first scout test skipped
a speed signal while a scout was open (wrong); the second and third added on
speed but kept v38's 3c floor on the added shares, so the adds were shaken
out within seconds and the scout's head start counted for nothing. Here the
scout's price is the anchor.

  the scout     1% of the account, a stock running (up 20% from its low so
                far, within 10% of its high, $250k a minute over 10 minutes);
                no floor - it floats to the end of the read's window
  speed adds    the full speed test on a held scout, the price at or over the
                scout's: the added shares to 10% of the account (11% with the
                scout), at +10c over that add's price to 30% (31%), at +20c to
                50% (51%). The first add a limit at the ask + the owner's speed
                scale; the later ones at any price (decided)
  warm add      (option) the speed just under the bar (0.15): the added shares
                to 2% (3% with the scout)
  chug adds     (option) no speed, the price up another 10% within 20
                minutes: +5% each, the added shares at most 19% (20% with the
                scout)
  the floor     of the ADDED shares - "avg": 3c under their average (as v38);
                "scout": 3c under the scout's price (they can ride back down to
                where we came in); "candle": the last 1-minute candle's low at
                the add (at most 10% under it). At the floor only the added
                shares are sold; the scout stays, and the next signal adds again
  once at 51%   the trailing thirds on the added shares
A stock with no scout: v38's own speed buy (the ask + the scale), as proposed.
THE READ IS CHOSEN BY WHAT HAPPENED; the bots' buy windows are the fairer half.

python3 v38_scout4.py <new windows> <old windows> <old minute bars>"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS

ACCOUNT = 15000.0
TOP3 = (("2026-10-07", "BIYA"), ("2026-10-06", "FRGT"), ("2026-10-07", "SBFM"))
BIG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"), ("2026-10-08", "FLYE"), ("2026-10-09", "WFF"))
SPEED_LOT = {1: 0.10, 2: 0.30, 3: 0.50}


def minute_lows(rec):
    m = {}
    for x in rec["S"]:
        if x[1]:
            mm = (rec["start"] + x[0]) // 60
            m[mm] = min(m.get(mm, x[3]), x[3])
    return m


def float_scout(p, rec, sp, warm, sv, t_in, scout, floor_mode, use_warm, use_chug):
    """[(kind, t in, P/L, t out)] - the scout and every lot of added shares."""
    out = []
    s_px = p.ask_at(t_in)
    s_sh = int(scout * ACCOUNT / s_px)
    if s_sh <= 0:
        return out
    mlow = minute_lows(rec)
    lot, pending = None, None                      # pending: (fill time, the limit or None, kind, stage)
    chug_over = s_px * 1.10
    nk = int(t_in - rec["start"]) + 1

    def low20(t):
        m = int(t // 60)
        lows = [mlow[i] for i in range(m - 20, m + 1) if i in mlow]
        return min(lows) if lows else 0.0

    def add(kind, stage, px, t):
        nonlocal lot
        if lot is None:
            lot = dict(kind=kind, stage=0, sh=0, cost=0.0, floor=None, base=None, best=px, last=px,
                       banked=0.0, sold=0, j=0, t0=t)
        if kind == "speed" and lot["kind"] != "speed":
            lot["kind"] = "speed"                  # a warm or chug lot joins the speed path
            lot["stage"] = 0
        if kind == "speed":
            tgt = SPEED_LOT[stage]
        elif kind == "warm":
            tgt = 0.02
        else:
            tgt = min(0.05 * stage, 0.19)
        n = int((tgt * ACCOUNT - lot["cost"]) / px)
        if n > 0:
            lot["sh"] += n
            lot["cost"] += n * px
        lot["stage"] = stage
        if kind == "speed" and stage == 1:
            lot["base"] = px
        if not lot["sh"]:
            lot = None
            return
        avg = lot["cost"] / lot["sh"]
        if floor_mode == "avg":
            f = avg - 0.03
        elif floor_mode == "scout":
            f = s_px - 0.03
        else:
            lo = mlow.get(int(t // 60) - 1)
            f = max(lo if lo else px * 0.90, px * 0.90)
            f = min(f, px - 0.03)
        lot["floor"] = f if lot["floor"] is None else max(lot["floor"], f)
        lot["best"] = max(lot["best"], px)
        lot["last"] = px

    def close(t):
        nonlocal lot, chug_over
        if lot["kind"] == "chug":
            chug_over = max(chug_over, lot["best"])
        xp = p.bid_at(t + S.SELL_LAG)
        avg = lot["cost"] / lot["sh"]
        out.append((lot["kind"], lot["t0"], (xp - avg) * lot["sh"] + lot["banked"], t))
        lot = None

    for t, px, b, a in p.ev[p.at(t_in):]:
        if pending and t >= pending[0]:
            tf, cap, kind, stage = pending
            pending = None
            ax = p.ask_at(tf)
            if ax and (cap is None or ax <= cap + 1e-9) and (lot is not None or stage == 1 or kind != "speed"):
                add(kind, stage, ax, tf)
        while pending is None and rec["start"] + nk + 0.99 <= t:
            td = rec["start"] + nk + 0.99
            k = nk
            nk += 1
            if td + S.BUY_LAG < t:
                continue
            if (lot is None or lot["kind"] != "speed") and sp.get(k, (False,))[0] and px >= s_px - 1e-9:
                a0 = p.ask_at(td)
                pending = (td + S.BUY_LAG, a0 + G.cushion(sv.get(k, 0.0), a0), "speed", 1)
            elif use_warm and lot is None and warm.get(k, (False,))[0] and px >= s_px - 1e-9:
                a0 = p.ask_at(td)
                pending = (td + S.BUY_LAG, a0 + 0.02, "warm", 1)
        if b and a:
            tol = max(S.PRINT_TOL_CENTS, S.PRINT_TOL_PCT * px)
            if px > a + tol or px < b - tol:
                continue
        if pending is None:
            if lot is not None and lot["kind"] == "speed" and lot["stage"] in (1, 2):
                if px >= lot["base"] + (0.10 if lot["stage"] == 1 else 0.20) - 1e-9:
                    pending = (t + S.BUY_LAG, None, "speed", lot["stage"] + 1)
            elif use_chug and (lot is None or lot["kind"] == "chug"):
                ref = lot["last"] if lot is not None else chug_over / 1.10
                room = lot is None or 0.05 * lot["stage"] < 0.19 - 1e-9
                if room and px >= max(ref * 1.10, chug_over if lot is None else 0.0) - 1e-9 \
                        and px >= low20(t) * 1.10 - 1e-9:
                    pending = (t + S.BUY_LAG, None, "chug", (lot["stage"] + 1) if lot is not None else 1)
        if lot is None:
            continue
        lot["best"] = max(lot["best"], px)
        if px <= lot["floor"] + 1e-9 or (b and a and (b + a) / 2 <= lot["floor"] + 1e-9):
            close(t)
            pending = None
            continue
        if lot["kind"] == "speed" and lot["stage"] == 3 and pending is None:
            avg = lot["cost"] / lot["sh"]
            full_sh = lot["sh"] + lot["sold"]
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
        avg = lot["cost"] / lot["sh"]
        out.append((lot["kind"], lot["t0"], (end_bid - avg) * lot["sh"] + lot["banked"], p.end))
    out.append(("scout", t_in, (end_bid - s_px) * s_sh, p.end))
    return out


def play(recs, scout=None, floor_mode="scout", use_warm=False, use_chug=False):
    out = []
    for r in recs:
        p = S.Path(r)
        sp = G.signals(r, checks=True)
        sv = G.speed_values(r)
        warm = {}
        if scout and use_warm:
            s0 = Q.SPEED
            Q.SPEED = 0.15
            warm = G.signals(r, checks=True)
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
            is_scout = bool(scout and x and low and top and k >= 600 and x[4] >= low * 1.20
                            and x[4] >= top * 0.90 and dol[k + 1] - dol[k - 599] >= 10 * Q.DOLLARS_MIN)
            if not (sp[k][0] or is_scout):
                continue
            t_in = t + S.BUY_LAG
            if t_in >= p.end - 5:
                break
            a0 = p.ask_at(t)
            fill = p.ask_at(t_in)
            cap = a0 + (G.cushion(sv.get(k, 0.0), a0) if sp[k][0] else 0.02)
            if not fill or fill <= 0 or fill > cap + 1e-9:
                continue
            if is_scout and not sp[k][0]:          # the scout floats to the window's end
                for kind, t0, pl, te in float_scout(p, r, sp, warm, sv, t_in, scout, floor_mode, use_warm, use_chug):
                    out.append((r, t0, pl, kind, te))
                break
            res = Q.run_ladder(p, t_in, fill, F.FULL, 0.03, 0.10, tiers=F.TIERS)
            out.append((r, t_in, res[1], "v38", res[0]))
            after = res[0] + S.SELL_LAG
    return out


VARIANTS = (
    ("v38 speed only (no scout)", dict()),
    ("scout 1% + speed adds, floor 3c under their average", dict(scout=0.01, floor_mode="avg")),
    ("scout 1% + speed adds, floor 3c under the SCOUT's price", dict(scout=0.01, floor_mode="scout")),
    ("scout 1% + speed adds, floor the last candle's low", dict(scout=0.01, floor_mode="candle")),
    ("  the scout's floor + the warm add", dict(scout=0.01, floor_mode="scout", use_warm=True)),
    ("  the scout's floor + the chug adds", dict(scout=0.01, floor_mode="scout", use_chug=True)),
    ("  the scout's floor + warm + chug", dict(scout=0.01, floor_mode="scout", use_warm=True, use_chug=True)),
)


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    F.FULL = 7500.0
    print("THE SCOUT AS THE OWNER MEANT IT - the speed adds on the scout, anchored on its price ($15,000 account)")
    print("%-56s %4s %8s %8s %8s | %7s %7s %7s | %8s %8s | %s" % (
        "", "n", "TOTAL", "no BIYA", "no top3", "PRE", "RTH", "AFTER", "PRE noB", "PRE no3",
        "  ".join("%-5s" % b[1] for b in BIG)))
    for name, kw in VARIANTS:
        xs = [x for k in sorted(by) for x in play(by[k], **kw)]
        nob = [x for x in xs if (x[0]["day"], x[0]["sym"]) != TOP3[0]]
        no3 = [x for x in xs if (x[0]["day"], x[0]["sym"]) not in TOP3]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        big = [sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) == b) for b in BIG]
        print("%-56s %4d %+8.0f %+8.0f %+8.0f | %+7.0f %+7.0f %+7.0f | %+8.0f %+8.0f | %s" % (
            name, len(xs), sum(x[2] for x in xs), sum(x[2] for x in nob), sum(x[2] for x in no3), *ses,
            sum(x[2] for x in nob if session(x[1]) == "PRE"), sum(x[2] for x in no3 if session(x[1]) == "PRE"),
            " ".join("%+6.0f" % v for v in big)))
        if not kw:
            continue
        for kind in ("scout", "speed", "warm", "chug", "v38"):
            ys = [x for x in xs if x[3] == kind]
            if ys:
                fair = [x for x in ys if x[0].get("buys")]
                print("%-56s      %-6s %3d (%3d won) %+8.0f - PRE %+.0f / RTH %+.0f / AFTER %+.0f | bots' windows %d %+.0f" % (
                    "", kind, len(ys), sum(x[2] > 0 for x in ys), sum(x[2] for x in ys),
                    *(sum(x[2] for x in ys if session(x[1]) == s) for s in SESSIONS), len(fair), sum(x[2] for x in fair)))


if __name__ == "__main__":
    main()
