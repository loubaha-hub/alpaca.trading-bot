"""v37's 19 buys on 10-08 with the 5c cut, and with a 'hesitates at the line'
exit added: the best since the buy came to within NEAR under a whole / half
dollar without clearing it by 5c, then the price falls DROP from that best ->
out (at the bid SELL_LAG later), unless the buy was furious-fast (speed>=FAST)."""
import asyncio, os, sys
REPO = "/home/user/alpaca.trading-bot"
src = open(os.path.join(REPO, "replay/research/tickreplay.py")).read().rsplit("\nmain()", 1)[0]
ns = {"__file__": os.path.join(REPO, "replay/research/tickreplay.py"), "__name__": "tr"}
exec(compile(src, "tickreplay", "exec"), ns)
bot, load, events_for, one, ts, BUYS, LIVE = (ns[k] for k in ("bot", "load", "events_for", "one", "ts", "BUYS", "LIVE"))
data = load(os.path.join(REPO, "replay/live/2026-10-08_ticks/tickdump_v37.txt.gz"))
bot.V37_TRAIL_CENTS = 0.05
orig_eval = bot.V37.evaluate
CFG = {}
async def evaluate(self, s, price):
    if CFG and s.shares > 0:
        best = getattr(s, "_hb", s.entry); best = max(best, price); s._hb = best
        line = int(best * 2 + 1e-9) / 2.0 + 0.5           # the next line over the best
        at = line - CFG["near"] - 1e-9 <= best             # within NEAR under it
        prev = int(best * 2 + 1e-9) / 2.0                  # or touched a line, not cleared by 5c
        at = at or (best >= prev and best < prev + 0.05 and prev > s.entry - 1e-9)
        if at and price <= best - CFG["drop"] + 1e-9 and not (CFG["fast"] and (s.v37_accel or 0) >= CFG["fast"]):
            await self.exit(s, "hesitate"); return
    return await orig_eval(self, s, price)
bot.V37.evaluate = evaluate
sets = [None, dict(near=0.03, drop=0.02, fast=0), dict(near=0.03, drop=0.03, fast=0), dict(near=0.03, drop=0.02, fast=0.3), dict(near=0.05, drop=0.02, fast=0)]
tot = [0.0] * len(sets); won = [0] * len(sets); tl = 0
for k, b in enumerate(BUYS):
    ev = events_for(data, b[1], ts(b[0])); tl += LIVE[k][3]
    row = "%2d %-5s %s live %+8.2f" % (k + 1, b[1], b[0][:8], LIVE[k][3])
    for i, c in enumerate(sets):
        CFG.clear(); CFG.update(c or {})
        r = asyncio.run(one(k, b, ev, 0.01)); tot[i] += r["pl"]; won[i] += r["pl"] > 0
        row += " | %-8s %+8.2f" % (r["why"][:8], r["pl"])
    print(row)
print("TOTAL live %+.2f | " % tl + " | ".join("%s %+.2f (%d won)" % ("5c cut" if not c else "+hes %dc/%dc%s" % (c["near"]*100, c["drop"]*100, " not fast" if c["fast"] else ""), tot[i], won[i]) for i, c in enumerate(sets)))
