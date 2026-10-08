"""10-08's runners (DKI 4:13, FLYE 7:23, DKI 5:00, AIXI 4:02, BIAF 8:09): v37's
first buy of each, held by the owner's tiers alone (v37's furious exit and "half
the gain" off), with three stops: v37's real one, 1c under the whole / half
dollar under the buy, and 10c under the buy. What the tiers keep of the run, in
the minutes of data we have (TICK_DUMP windows)."""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "tiers_1008.py")).read().split('\nif __name__ == "__main__"', 1)[0]
ns = {"__file__": os.path.join(HERE, "tiers_1008.py"), "__name__": "t"}
exec(compile(src, "tiers_1008", "exec"), ns)
bot, events_for, ts, BUYS, LIVE, run_one, data, hms = (ns[k] for k in (
    "bot", "events_for", "ts", "BUYS", "LIVE", "run_one", "data", "hms"))
from datetime import datetime
BEST = {}
inner = bot.V37.evaluate
async def spy(self, s, price):
    BEST["b"] = max(BEST.get("b", s.entry), price)
    return await inner(self, s, price)
bot.V37.evaluate = spy
RUNNERS = [3, 13, 6, 0, 16]                    # indexes into BUYS
for furious in (False, True):
    bot.V37_FURIOUS_EXIT = furious
    print("\n=== v37's furious exit %s ===" % ("ON (as live)" if furious else "OFF (tiers alone)"))
    for k in RUNNERS:
        b = BUYS[k]; ev = events_for(data, b[1], ts(b[0]))
        hi = max(x[2][1] for x in ev if x[1] == 2 and x[0] >= ts(b[0]) and bot.qualifies(list(x[2][3])))
        end = datetime.fromtimestamp(ev[-1][0], bot.ET).strftime("%H:%M")
        print("%-5s bought %s @ %.2f, the high after it %.2f (+%.0fc) by %s, live %+.2f" % (
            b[1], b[0][:8], b[3], hi, 100 * (hi - b[3]), end, LIVE[k][3]))
        line = int(b[3] * 2 + 1e-9) / 2.0
        for name, stop in (("real stop %.2f" % b[5], b[5]), ("line stop %.2f" % (line - 0.01), min(line - 0.01, b[3] - 0.01)),
                           ("10c stop %.2f" % (b[3] - 0.10), b[3] - 0.10)):
            BEST.clear()
            r = run_one((b[0], b[1], b[2], b[3], b[4], stop, b[6]), ev, dict(k=1.0, top="fifth"))
            best = BEST.get("b", b[3])
            print("   %-16s out %s %-5s @ %.2f, best %.2f (+%.0fc): %+8.2f  kept %3.0f%% of the best gain" % (
                name, datetime.fromtimestamp(r["t"], bot.ET).strftime("%H:%M:%S"), r["why"][:5], r["px"] or 0,
                best, 100 * (best - b[3]), r["pl"], 100 * (r["px"] - b[3]) / (best - b[3]) if best > b[3] and r["px"] else 0))
