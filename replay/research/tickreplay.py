"""v37's exit on today's real prints and quotes, through the bot's own code.

python3 tickreplay.py <TICKDUMP lines file, .gz ok> <setting ...>
    a setting is "3" (half the gain armed from 3c) or "t5" (out 5c under the
    best since the buy, V37_TRAIL_CENTS, with half the gain set aside)

Each trade starts at its real fill (the ENTER line): price, shares, stop, speed.
The prints and quotes before it are fed in (no buying); from the fill on, every
print goes through V37.evaluate, as the tick worker does. When the bot decides
to sell, the sale is priced at the real bid SELL_LAG seconds later. Adds are
off (as live today: no v37 add filled), each trade stands alone."""
import asyncio, glob, gzip, json, os, re, sys
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "tests"))
import importlib.util
spec = importlib.util.spec_from_file_location("bot", os.path.join(REPO, "r34.py"))
bot = importlib.util.module_from_spec(spec); sys.modules["bot"] = bot; spec.loader.exec_module(bot)
from helpers import FakeBroker, FakeData
from conftest import Clock

ET = bot.ET
SELL_LAG = 0.5
DAY = "2026-10-08"
# v37's 19 buys on 10-08 (the ENTER lines, ET): time, symbol, shares, fill, print, stop, speed (0 = a tenth)
BUYS = [("04:02:31.123","AIXI",210,2.4320,2.4600,2.2374,0),("04:10:18.277","IPW",1370,1.78,1.77,1.7044,0.46),
        ("04:10:50.635","IPW",2229,1.85,1.83,1.7743,0.36),("04:13:38.820","DKI",1107,2.50,2.50,2.4750,3.97),
        ("04:13:45.701","DKI",198,2.60,2.57,2.50,7.03),("04:16:26.974","DKI",11,2.98,2.99,2.8266,0),
        ("05:00:47.903","DKI",833,3.90,3.82,3.80,0.52),("05:21:17.564","SBFM",1783,1.22,1.21,1.1625,0.78),
        ("05:21:26.767","SBFM",744,1.24,1.2306,1.178,0.97),("05:21:36.515","SBFM",1419,1.29,1.26,1.2319,0.59),
        ("05:43:51.451","MEDS",84,4.13,4.1399,3.99,0),("06:57:36.405","DKI",69,7.38,7.2996,6.99,0),
        ("07:01:49.343","MOBX",1371,1.46,1.4599,1.4162,1.77),("07:23:30.474","FLYE",2130,1.90,1.9015,1.80,0.45),
        ("07:25:56.835","FLYE",647,2.91,2.94,2.81,0.40),("08:02:18.670","CHR",1983,2.06,2.02,1.99,0.54),
        ("08:09:41.610","BIAF",566,7.99,7.99,7.89,0.34),("08:09:51.259","BIAF",61,8.19,8.07,7.99,0),
        ("11:46:40.296","NCT",234,2.17,2.159,2.0714,0)]
LIVE = {  # what really happened: exit time, why, price, P/L
 0:("04:02:42","giveback",2.4176,-3.02),1:("04:10:19","giveback",1.75,-41.10),2:("04:10:57","giveback",1.83,-44.58),
 3:("04:13:41","stop",2.4307,-76.77),4:("04:13:52","giveback",2.5362,-12.63),5:("04:16:33","giveback",2.96,-0.22),
 6:("05:00:52","giveback",3.8843,-13.11),7:("05:21:23","giveback",1.22,0.0),8:("05:21:35","giveback",1.24,0.0),
 9:("05:21:38","giveback",1.28,-14.19),10:("05:43:53","giveback",4.07,-5.04),11:("06:57:48","giveback",6.947,-29.88),
 12:("07:01:53","giveback",1.46,0.0),13:("07:23:37","giveback",1.8832,-35.86),14:("07:26:01","stop",2.5065,-261.07),
 15:("08:02:22","stop",1.99,-138.81),16:("08:09:48","giveback",7.9075,-46.67),17:("08:09:54","stop",7.9113,-17.0),
 18:("11:46:44","giveback",2.1603,-2.26)}

def ts(hms):
    return datetime.fromisoformat(f"{DAY}T{hms}").replace(tzinfo=ET).timestamp()

def load(path):
    """{(sym, window start): {"T": rows, "Q": rows}} from the saved TICKDUMP lines."""
    win = {}
    opener = gzip.open if path.endswith(".gz") else open
    for line in opener(path, "rt"):
        i = line.find("TICKDUMP ")
        if i < 0:
            continue
        parts = line[i:].rstrip("\n").split(" ", 6)
        if len(parts) < 7 or parts[4] not in ("T", "Q") or "/" not in parts[5]:
            continue
        _, day, sym, a, kind, frac, rows = parts
        k = int(frac.split("/")[0])
        win.setdefault((sym, a), {}).setdefault(kind, {})[k] = json.loads(rows)
    return {key: {kind: [r for k in sorted(p) for r in p[k]] for kind, p in v.items()}
            for key, v in win.items()}

def events_for(data, sym, t_fill):
    best = None
    for (s, a), v in data.items():
        if s == sym and ts(a) <= t_fill and (best is None or ts(a) > ts(best[0])):
            best = (a, v)
    if not best:
        return None
    a, v = best
    t0 = ts(a)
    ev = [(t0 + r[0] / 1000, 1, r) for r in v.get("Q", [])] + [(t0 + r[0] / 1000, 2, r) for r in v.get("T", [])]
    ev.sort(key=lambda x: (x[0], x[1]))
    return ev

async def one(k, buy, ev, arm):
    t_fill_s, sym, sh, fill, prt, stop, speed = buy
    t_fill = ts(t_fill_s)
    clock = Clock(datetime.fromtimestamp(t_fill, ET))
    now = [t_fill]
    bot.time.time = lambda: now[0]
    bot.datetime = clock.cls
    bot.V37_GIVEBACK_ARM_CENTS = arm
    strat = bot.V37(FakeBroker(equity=14248.96), FakeData())
    strat.day_start_equity = 14248.96
    s = strat.st(sym)
    out = {}
    async def fake_exit(st, why, *a, **kw):
        if not out:
            out.update(t=now[0], why=why)
        st.shares = 0
    strat.exit = fake_exit
    async def no_add(*a, **kw):
        return None
    strat.v37_add = no_add
    bid = [None]
    pos = False
    for t, kind, r in ev:
        now[0] = t
        clock.now = datetime.fromtimestamp(t, ET)
        if not pos and t >= t_fill:              # the fill, as v37_buy left it
            pos = True
            s.shares, s.entry, s.v36_first = sh, fill, fill
            s.v37_stop_pct = (fill - stop) / fill
            s.v37_accel, s.v37_accel_added = speed, False
            strat.set_line(s, prt)
            s.stop = stop
            s.v37_pace_at_buy = strat.pace(s)
            s.v37_peak_after, s.v37_bid_over = 0.0, False
            s.peak, s.trail_stop, s.armed, s.adopted = fill, 0.0, False, False
            s.entry_kind = "accel" if speed else "rip"
            s.entry_at = t_fill
        if kind == 1:
            bid[0] = r[1]
            strat.offer_quote(sym, r[1], r[2])
            if out and "px" not in out and t >= out["t"] + SELL_LAG:
                out["px"] = r[1]
            continue
        px, size, conds = r[1], r[2], list(r[3])
        if out:
            if "px" not in out and t >= out["t"] + SELL_LAG and bid[0]:
                out["px"] = bid[0]
            if "px" in out:
                break
            continue
        if not bot.qualifies(conds):
            strat.note_skipped(s, px, conds)
            continue
        s.last_price, s.last_conds, s.last_size, s.last_print_ts, s.last_tick_at = px, conds, size, t, t
        strat.note_trade(s, px, size)
        if pos:
            await strat.evaluate(s, px)
        s.day_high = max(s.day_high, px)
    if out and "px" not in out:
        out["px"] = bid[0]
    if not out:
        out = dict(t=now[0], why="open at the end", px=bid[0])
    out["pl"] = (out["px"] - fill) * sh
    return out

def main():
    data = load(sys.argv[1])
    sets = sys.argv[2:] or ["1"]
    conf = [(0.01, float(x[1:]) / 100) if x.startswith("t") else (float(x) / 100, 0.0)
            for x in sets]
    name = lambda c: ("drop %dc" % round(c[1] * 100)) if c[1] else ("half %dc" % round(c[0] * 100))
    print(f"{'#':>2} {'trade':16} {'live':>8} | " + " | ".join(f"{name(c):>16}" for c in conf))
    tot = {c: 0.0 for c in conf}; won = {c: 0 for c in conf}; tl = 0.0
    for k, buy in enumerate(BUYS):
        ev = events_for(data, buy[1], ts(buy[0]))
        tl += LIVE[k][3]
        row = f"{k+1:>2} {buy[1]:5} {buy[0][:8]} {LIVE[k][3]:+8.2f}"
        if not ev:
            print(row + "  (no tick data)"); continue
        for c in conf:
            bot.V37_TRAIL_CENTS = c[1]
            r = asyncio.run(one(k, buy, ev, c[0]))
            tot[c] += r["pl"]; won[c] += r["pl"] > 0
            row += f" | {r['why'][:6]:>6} {r['pl']:+9.2f}"
        print(row)
    bot.V37_TRAIL_CENTS = 0.0
    print(f"TOTAL live {tl:+.2f} (0 won) | " + " | ".join(f"{name(c)} {tot[c]:+.2f} ({won[c]} won)" for c in conf))

main()
