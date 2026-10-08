"""10-08: the buys at a whole / half dollar - as bought, and if each had waited
for the price to clear the line by PAST and stay there HOLD seconds. Both run
through the same exit (v37's code with the 5c cut) so only the entry differs."""
import asyncio, json, sys, os
REPO = "/home/user/alpaca.trading-bot"
src = open(os.path.join(REPO, "replay/research/tickreplay.py")).read().rsplit("\nmain()", 1)[0]
ns = {"__file__": os.path.join(REPO, "replay/research/tickreplay.py"), "__name__": "tr"}
exec(compile(src, "tickreplay", "exec"), ns)
bot, load, events_for, one, ts = ns["bot"], ns["load"], ns["events_for"], ns["one"], ns["ts"]
from datetime import datetime
near = json.load(open(sys.argv[1]))
data = load(os.path.join(REPO, "replay/live/2026-10-08_ticks/tickdump_v37.txt.gz"))
bot.V37_TRAIL_CENTS = 0.05
SPEED = {b[0][:8] + b[1]: b[6] for b in ns["BUYS"]}

def hms(t):
    return datetime.fromtimestamp(t, bot.ET).strftime("%H:%M:%S.%f")[:12]

def waited(ev, t0, lvl, past, hold):
    """The first moment after t0 that the price has been at or over lvl+past for
    `hold` seconds (no qualifying print under it): (time, ask, price)."""
    since = None; ask = None
    for t, kind, r in ev:
        if kind == 1:
            ask = r[2]
            if t >= t0 and since is not None and t - since >= hold and ask:
                return t, ask
            continue
        if t < t0 or not bot.qualifies(list(r[3])):
            continue
        if r[1] >= lvl + past - 1e-9:
            if since is None:
                since = t
            if t - since >= hold and ask:
                return t, ask
        else:
            since = None
    return None

rules = [(0.05, 3.0), (0.02, 0.0), (0.05, 0.0), (0.02, 1.0)]
tot = {"live": 0.0, "as bought": 0.0}; tot.update({r: 0.0 for r in rules})
print("%-18s %-7s %6s %6s %8s | %-9s | " % ("buy", "line", "fill", "furi", "live", "as bought") +
      " | ".join("wait %dc/%gs" % (p * 100, h) for p, h in rules))
for n in near:
    ev = events_for(data, n["sym"], ts(n["t"]))
    if not ev:
        print("%-18s no ticks (live %+.2f)" % (n["id"], n["pl"])); continue
    sp = SPEED.get(n["t"][:8] + n["sym"], 0.3)
    stop = n["stop"] if n["stop"] < n["fill"] else n["fill"] - 0.05
    a = asyncio.run(one(0, (n["t"], n["sym"], n["sh"], n["fill"], n["px"], stop, sp), ev, 0.01))
    tot["live"] += n["pl"]; tot["as bought"] += a["pl"]
    row = "%-18s $%-6.2f %6.3f %6s %+8.2f | %+9.2f | " % (n["id"], n["lvl"], n["fill"], "yes" if n["furious"] else "no", n["pl"], a["pl"])
    cells = []
    for p, h in rules:
        w = waited(ev, ts(n["t"]) - 1.0, n["lvl"], p, h)
        if not w:
            cells.append("never - 0"); continue
        t, ask = w
        sh = int(n["sh"] * n["fill"] / ask)
        st = max(stop, n["lvl"] - 0.01) if n["lvl"] - 0.01 < ask else ask - 0.05
        r = asyncio.run(one(0, (hms(t), n["sym"], sh, ask, ask, st, sp), ev, 0.01))
        tot[(p, h)] += r["pl"]
        cells.append("%s@%.2f %s %+.2f" % (hms(t)[3:8], ask, r["why"][:5], r["pl"]))
    print(row + " | ".join(cells))
print("TOTAL", " | ".join("%s %+.2f" % (k if isinstance(k, str) else "wait %dc/%gs" % (k[0] * 100, k[1]), v) for k, v in tot.items()))
