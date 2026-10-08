"""v37's 19 buys on 10-08: the owner's tiered exit vs live vs the 5c cut, print
by print through v37's own code (the stop and its other exits stay; the tier
line replaces "half the gain" and the 5c cut). Sold at the real bid 0.5s later.
Part B: re-entries, unlimited, when a print clears the day's high + 5c."""
import asyncio, os, sys
from datetime import datetime
REPO = "/home/user/alpaca.trading-bot"
src = open(os.path.join(REPO, "replay/research/tickreplay.py")).read().rsplit("\nmain()", 1)[0]
ns = {"__file__": os.path.join(REPO, "replay/research/tickreplay.py"), "__name__": "tr"}
exec(compile(src, "tickreplay", "exec"), ns)
bot, load, events_for, one, ts, BUYS, LIVE = (ns[k] for k in ("bot", "load", "events_for", "one", "ts", "BUYS", "LIVE"))
data = load(os.path.join(REPO, "replay/live/2026-10-08_ticks/tickdump_v37.txt.gz"))

def tier_line(e, best, k, top, lead=0.05):
    """k scales the tier edges (5c, 20c, 50c, $1); top: 'fifth' or a flat amount;
    lead: the first tier's leash (sell this far under the best until up this much)."""
    g = best - e
    if g < max(lead, 0.05 * k): return best - max(lead, 0.05 * k)
    if g < 0.20 * k: return e
    if g < 0.50 * k: return e + g / 2
    if g < 1.00 * k: return e + g * 2 / 3
    return best - (g / 5 if top == "fifth" else top)

CFG = {}
orig_eval = bot.V37.evaluate
async def evaluate(self, s, price):
    if CFG and s.shares > 0:
        best = max(getattr(s, "_tb", s.entry), price); s._tb = best
        line = max(getattr(s, "_tl", -1.0), tier_line(s.entry, best, CFG["k"], CFG["top"], CFG.get("lead", 0.05))); s._tl = line
        if price <= line + 1e-9:
            q = self.live_quote(s)
            if not (q and q[0] > line):
                await self.exit(s, "tier"); return
    return await orig_eval(self, s, price)
bot.V37.evaluate = evaluate

def run_one(buy, ev, cfg):
    CFG.clear()
    if cfg == "5c":
        bot.V37_TRAIL_CENTS = 0.05; arm = 0.01
    elif cfg == "half1c":
        bot.V37_TRAIL_CENTS = 0.0; arm = 0.01
    else:
        CFG.update(cfg); bot.V37_TRAIL_CENTS = 0.0; arm = 99.0   # half the gain never arms
    return asyncio.run(one(0, buy, ev, arm))

SETS = [("5c cut (r34.33)", "5c"), ("tiers", dict(k=1.0, top="fifth")), ("tiers, top 20c flat", dict(k=1.0, top=0.20)),
        ("tiers x0.75", dict(k=0.75, top="fifth")), ("tiers x1.5", dict(k=1.5, top="fifth"))]

def part_a():
    tot = [0.0] * len(SETS); won = [0] * len(SETS); tl = 0.0
    print("A. each live buy alone, the same entry; only the exit differs")
    print("%2s %-15s %9s | " % ("#", "buy", "live") + " | ".join("%-20s" % n for n, _ in SETS))
    for k, b in enumerate(BUYS):
        ev = events_for(data, b[1], ts(b[0])); tl += LIVE[k][3]
        row = "%2d %-5s %s %+9.2f | " % (k + 1, b[1], b[0][:8], LIVE[k][3])
        cells = []
        for i, (n, c) in enumerate(SETS):
            r = run_one(b, ev, c); tot[i] += r["pl"]; won[i] += r["pl"] > 0
            cells.append("%-6s %+9.2f     " % (r["why"][:6], r["pl"]))
        print(row + " | ".join(cells))
    print("TOTAL live %+.2f (0 won of 19) | " % tl + " | ".join("%s %+.2f (%d won)" % (n, tot[i], won[i]) for i, (n, _) in enumerate(SETS)))

BUY_LAG = 1.0

def hms(t):
    return datetime.fromtimestamp(t, bot.ET).strftime("%H:%M:%S.%f")[:12]

def part_b(cfg, lines=False):
    """Per window: the first live buy, then the rule's own re-entries (a print over
    the day's high + 5c - and with lines=True, over $x.00/$x.50 + 5c when that
    trigger sits at a line); the live re-buys in the window are not used."""
    firsts, seen = [], set()
    for k, b in enumerate(BUYS):
        ev = events_for(data, b[1], ts(b[0]))
        key = (b[1], id(ev) if ev is None else ev[0][0])
        if key in seen: continue
        seen.add(key); firsts.append((k, b, ev))
    total, n_tr, n_won, live_tot, rows = 0.0, 0, 0, 0.0, []
    for k, b, ev in firsts:
        wl = [j for j, bb in enumerate(BUYS) if bb[1] == b[1] and events_for(data, bb[1], ts(bb[0]))[0][0] == ev[0][0]]
        live_w = sum(LIVE[j][3] for j in wl); live_tot += live_w
        dist = b[3] - b[5]; dollars = b[2] * b[3]
        buy, trades = b, []
        while True:
            r = run_one(buy, ev, cfg)
            trades.append((buy[0][:8], buy[3], r["why"][:5], r["pl"]))
            if r["why"] == "open at the end": break
            hod = max(e[2][1] for e in ev if e[1] == 2 and e[0] <= r["t"] and bot.qualifies(list(e[2][3])))
            trig = hod + 0.05
            if lines:
                lvl = int((trig + 0.03) * 2 + 1e-9) / 2.0
                if lvl - 0.03 <= trig < lvl + 0.05: trig = lvl + 0.05
            ask, nxt, after = None, None, r["t"] + 0.5
            while True:                       # the trigger, then the ask BUY_LAG later
                trig_at = None
                for t, kind, x in ev:
                    if kind == 1:
                        ask = x[2]; continue
                    if t < after or not bot.qualifies(list(x[3])): continue
                    if x[1] >= trig - 1e-9 and ask:
                        trig_at = (t, x[1], ask); break
                if not trig_at: break
                t, p, a0 = trig_at
                a1 = None
                for tt, kind, x in ev:
                    if kind == 1 and tt <= t + BUY_LAG: a1 = x[2]
                    if tt > t + BUY_LAG: break
                a1 = a1 or a0
                if a1 <= a0 + 0.20 + 1e-9:    # the sweep's limit: the ask + 20c at the decision
                    nxt = (t + BUY_LAG, p, max(a1, p) if a1 >= p else a1); break
                after = t + BUY_LAG           # ran past the limit: no fill, wait for the next
            if not nxt: break
            t, p, fill = nxt
            stop = max(fill * (1 - 0.04), min(int(fill * 2 + 1e-9) / 2.0 - 0.01, fill * 0.99))
            if stop >= fill: stop = fill * 0.99
            buy = (hms(t), b[1], int(dollars / fill), fill, p, stop, b[6])
        pl = sum(x[3] for x in trades); total += pl; n_tr += len(trades); n_won += sum(x[3] > 0 for x in trades)
        rows.append("%-5s %s live %+8.2f (%d buys) | rule %+8.2f (%d buys): %s" % (
            b[1], b[0][:8], live_w, len(wl), pl, len(trades),
            ", ".join("%s@%.2f %s %+.0f" % x for x in trades)))
    return total, n_tr, n_won, live_tot, rows

if __name__ == "__main__" and "lead" in sys.argv:
    SETS[:] = [("5c cut", "5c"), ("tiers 5c lead", dict(k=1.0, top="fifth")), ("tiers 10c lead", dict(k=1.0, top="fifth", lead=0.10)),
               ("tiers 15c lead", dict(k=1.0, top="fifth", lead=0.15))]
    part_a()
    for name, cfg in SETS:
        total, n, w, lt, rows = part_b(cfg, False)
        print("B %-16s %+9.2f on %d entries (%d won) vs live %+.2f" % (name, total, n, w, lt))
    sys.exit()
if __name__ == "__main__":
    if 'b' not in sys.argv: part_a()
    print("\nB. per window (6-8 minutes of data): the first live buy, then re-entries over the day's high + 5c")
    for name, cfg, lines in [("5c cut", "5c", False), ("tiers", dict(k=1.0, top="fifth"), False),
                             ("tiers + lines", dict(k=1.0, top="fifth"), True), ("5c cut + lines", "5c", True)]:
        total, n, w, lt, rows = part_b(cfg, lines)
        print("\n-- %s: %+.2f on %d entries (%d won) vs live %+.2f" % (name, total, n, w, lt))
        for r in rows: print("   " + r)
