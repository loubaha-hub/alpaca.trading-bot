"""v37's 19 buys on 10-08: the owner's full tiers (5c / 20c / 50c / $1) with and
without "a buy at a whole / half dollar waits for the line + 5c", next to the
5c cut. Per trade: the best gain it reached and the tier that sold it.
A waited buy fills at the ask BUY_LAG after the print over the line + 5c (live
fills take ~1.3s) and keeps v37's stop rule: its stop % from the real buy, never
under 1c below the line it just crossed (at most 1% under the fill)."""
import asyncio, os, sys
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "tiers_1008.py")).read().split('\nif __name__ == "__main__"', 1)[0]
ns = {"__file__": os.path.join(HERE, "tiers_1008.py"), "__name__": "t"}
exec(compile(src, "tiers_1008", "exec"), ns)
bot, events_for, ts, BUYS, LIVE, run_one, data, hms = (ns[k] for k in (
    "bot", "events_for", "ts", "BUYS", "LIVE", "run_one", "data", "hms"))
BUY_LAG = 1.0
TIERS = dict(k=1.0, top="fifth")
BEST = {}
inner = bot.V37.evaluate
async def spy(self, s, price):                  # the best price since the buy, for the table
    BEST["b"] = max(BEST.get("b", s.entry), price)
    return await inner(self, s, price)
bot.V37.evaluate = spy

def tier_of(g):
    return "1 (0-5c)" if g < 0.05 else "2 (5-20c)" if g < 0.20 else "3 (20-50c)" if g < 0.50 else "4 (50c-$1)" if g < 1 else "5 ($1+)"

def waited(buy, ev, band):
    """None when the buy is not within `band` under a line (or under 5c past it);
    else the buy at the ask BUY_LAG after the first print at the line + 5c, or
    "never" in the data we have."""
    t0, sym, sh, fill, prt, stop, speed = buy
    line = int((prt + band) * 2 + 1e-9) / 2.0
    if not (line - band - 1e-9 <= prt < line + 0.05 - 1e-9):
        return None
    trig, ask, hit = line + 0.05, None, None
    for t, kind, x in ev:
        if kind == 1:
            ask = x[2]
            if hit and t > hit + BUY_LAG: break
            continue
        if hit is None and t >= ts(t0) - 1.0 and bot.qualifies(list(x[3])) and x[1] >= trig - 1e-9:
            hit = t
    if hit is None or not ask:
        return "never"
    f = max(ask, trig)
    pct = (fill - stop) / fill
    st = max(f * (1 - pct), min(line - 0.01, f * 0.99))
    return (hms(hit + BUY_LAG), sym, int(sh * fill / f), round(f, 4), trig, min(st, f - 0.01), speed)

def run(buy, ev, cfg):
    BEST.clear()
    r = run_one(buy, ev, cfg)
    r["best"] = BEST.get("b", buy[3]) - buy[3]
    return r

cols = ["5c cut", "tiers", "tiers + wait 3c", "tiers + wait 5c", "tiers + wait 10c", "5c cut + wait 3c"]
tot = {c: 0.0 for c in cols}; won = {c: 0 for c in cols}; n = {c: 0 for c in cols}; live = 0.0
print("%2s %-15s %8s | %-26s | %-30s | %s" % ("#", "buy", "live", "5c cut", "tiers: best gain, tier, P/L", " | ".join(cols[2:])))
for k, b in enumerate(BUYS):
    ev = events_for(data, b[1], ts(b[0])); live += LIVE[k][3]
    cells = {}
    for c in cols:
        cfg = "5c" if c.startswith("5c") else TIERS
        buy = b
        if "wait" in c:
            w = waited(b, ev, float(c.split()[-1][:-1]) / 100)
            if w == "never":
                cells[c] = "never crossed: 0"; n[c] += 0; continue
            if w:
                buy = w
        r = run(buy, ev, cfg)
        tot[c] += r["pl"]; won[c] += r["pl"] > 0; n[c] += 1
        tag = ("@%.2f " % buy[3]) if buy is not b else ""
        cells[c] = "%s%s %+.2f" % (tag, r["why"][:5], r["pl"]) if c != "tiers" else \
            "+%2.0fc  T%s  %-5s %+8.2f" % (100 * r["best"], tier_of(r["best"])[0], r["why"][:5], r["pl"])
    print("%2d %-5s %s %+8.2f | %-26s | %-30s | %s" % (k + 1, b[1], b[0][:8], LIVE[k][3], cells["5c cut"],
          cells["tiers"], " | ".join(cells[c] for c in cols[2:])))
print("TOTAL live %+.2f (0 of 19 won)" % live)
for c in cols:
    print("  %-18s %+9.2f  %d won of %d buys" % (c, tot[c], won[c], n[c]))
