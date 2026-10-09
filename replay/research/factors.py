"""The owner's factors at the moment of each live buy (v36, v36b, 10-06/07/08),
from Webull's 1-minute bars (4am-8pm, the closed minutes before the buy), and
how the trades with and without each factor did. Live P/L per round trip.

python3 factors.py [bot]"""
import json, os, sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(os.path.dirname(HERE), "live", "2026-10-08_secdump")

def ema(vals, n):
    k, e, out = 2 / (n + 1), None, []
    for v in vals:
        e = v if e is None else e + k * (v - e)
        out.append(e)
    return out

def bars_for(day, sym, cache={}):
    if day not in cache:
        cache[day] = json.load(open(os.path.join(D, "bars", day + ".json")))
    rows = cache[day].get(sym, [])
    out = []
    for t, o, h, l, c, v, sess in rows:
        ts = datetime.fromisoformat(t.replace("+0000", "+00:00")).timestamp()
        out.append((ts, o, h, l, c, v))
    return out

def factors(day, sym, t_buy, px):
    bars = [b for b in bars_for(day, sym) if b[0] + 60 <= t_buy]       # closed before the buy
    if len(bars) < 30:
        return None
    closes = [b[4] for b in bars]
    e9, e20, e12, e26 = ema(closes, 9), ema(closes, 20), ema(closes, 12), ema(closes, 26)
    macd = [a - b for a, b in zip(e12, e26)]
    sig = ema(macd, 9)
    hist = [m - s for m, s in zip(macd, sig)]
    gap = [(a - b) / c for a, b, c in zip(e9, e20, closes)]
    pv = sum(b[4] * b[5] for b in bars); vv = sum(b[5] for b in bars)
    vwap = pv / vv if vv else closes[-1]
    last = bars[-1]
    rng = last[2] - last[3]
    wick = (last[2] - max(last[1], last[4])) / rng if rng > 0 else 0.0
    greens = [b for b in bars[-4:] if b[4] > b[1]]
    bodies = [b[4] - b[1] for b in greens]
    shrinking = len(bodies) >= 2 and bodies[-1] < bodies[-2]
    vol10 = sum(b[5] for b in bars[-11:-1]) / 10 or 1
    hod = max(b[2] for b in bars)
    first = bars[0][1]
    nxt_line = int(px * 2 + 1e-9) / 2.0 + 0.5
    return dict(
        ema_above=e9[-1] > e20[-1],
        ema_widening=gap[-1] > gap[-2] > gap[-3],
        macd_pos=macd[-1] > 0,
        macd_bars_growing=hist[-1] > hist[-2] > hist[-3] and hist[-1] > 0,
        above_vwap=px > vwap,
        small_wick=wick <= 0.25,
        bodies_not_shrinking=not shrinking,
        vol_picking_up=last[5] >= 2 * vol10,
        new_high=px > hod,
        under_hod_within_5pct=px <= hod and px >= hod * 0.95,
        extended_20pct_over_vwap=px > vwap * 1.20,
        up_50pct_on_day=px >= first * 1.5,
        line_room_10c=nxt_line - px >= 0.10,
        premarket=datetime.fromtimestamp(t_buy, ET).hour < 9 or (datetime.fromtimestamp(t_buy, ET).hour == 9 and datetime.fromtimestamp(t_buy, ET).minute < 30),
        first_hour=datetime.fromtimestamp(t_buy, ET).hour < 5,
    )

def main(bot):
    rts = json.load(open(os.path.join(D, "roundtrips.json")))
    rows = []
    for day in sorted(rts[bot]):
        for rt in rts[bot][day]:
            if rt["pl"] is None:
                continue
            t = datetime.fromisoformat("%sT%s" % (day, rt["open"])).replace(tzinfo=ET).timestamp()
            f = factors(day, rt["sym"], t, rt["first_px"])
            if f:
                rows.append((f, rt["pl"]))
    n = len(rows); tot = sum(p for _, p in rows); w = sum(p > 0 for _, p in rows)
    print("%s: %d trades with bars, %d won (%.0f%%), P/L %+.0f (%+.1f a trade)" % (bot, n, w, 100 * w / n, tot, tot / n))
    print("   %-26s | %-34s | %-34s" % ("factor", "with it", "without it"))
    for k in rows[0][0]:
        a = [p for f, p in rows if f[k]]; b = [p for f, p in rows if not f[k]]
        fmt = lambda g: "%3d trades, %3.0f%% won, %+7.0f (%+6.1f/tr)" % (len(g), 100 * sum(x > 0 for x in g) / len(g), sum(g), sum(g) / len(g)) if g else "-"
        print("   %-26s | %-34s | %-34s" % (k, fmt(a), fmt(b)))
    return rows

if __name__ == "__main__":
    for bot in (sys.argv[1:] or ["v36", "v36b"]):
        main(bot)
        print()
