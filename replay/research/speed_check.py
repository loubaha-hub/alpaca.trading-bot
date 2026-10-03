"""Does v31's speed measure light up when a stock is really ripping?

From the 1-minute bars, for every minute the bot could have bought a name
(up >=10% on the previous close, $1-$20, last 3 bars >=30k shares each and
>=100k together), 4:15am-3:30pm:

  RIPPING NOW   the 10 minutes around it (5 before, 5 after) rose >=10%
  RIPS NEXT     the next 10 minutes reach +5% before -3%

and these detectors, all from bars closed by that minute:

  bot "fast"    bar_speed >= 2x baseline (bar_speed = last bar's % change x
                its volume / the bar before's; baseline = median of the day's
                positive bar speeds) - v31's own "strong speed" test
  bot "up"      bar_speed > 0 - the closest bar version of the entry gate
                (fast_speed > 0 over the last 100 prints; the prints themselves
                are not in this data)
  5-min move    up >=5% over the last 5 minutes
  5-min + vol   that, and the last 5 minutes traded >=1.5x the pace of the 30
                before (the step-4 volume test)

Run: python3 replay/research/speed_check.py
"""
import statistics as st
from common import DAYS, load, hm

rows = []
for day in DAYS:
    for sym, (pc, bars) in load(day).items():
        pos = []
        for i in range(35, len(bars) - 10):
            a, b = bars[i - 1], bars[i]
            sp = ((b[4] - a[4]) / a[4]) * (b[5] / a[5]) if a[4] > 0 and a[5] > 0 else None
            if sp is not None and sp > 0:
                pos.append(sp)
            t = hm(b[0])
            if not (255 <= t < 930) or sp is None:
                continue
            p = b[4]
            if not (1 <= p <= 20) or p < pc * 1.10:
                continue
            l3 = bars[i - 2:i + 1]
            if any(x[5] < 30_000 for x in l3) or sum(x[5] for x in l3) < 100_000:
                continue
            base = st.median(pos) if pos else 0.0
            move5 = p / bars[i - 5][4] - 1
            v5 = sum(x[5] for x in bars[i - 4:i + 1]) / 5
            v30 = sum(x[5] for x in bars[i - 34:i - 4]) / 30
            vol = v5 / v30 if v30 > 0 else 9.9
            rip_now = bars[i + 5][4] / bars[i - 5][4] - 1 >= 0.10
            nxt, out = bars[i + 1:i + 11], 0
            for x in nxt:
                if x[3] <= p * 0.97:
                    out = -1; break
                if x[2] >= p * 1.05:
                    out = 1; break
            rows.append(dict(fast=base > 0 and sp >= 2 * base, up=sp > 0,
                             m5=move5 >= 0.05, m5v=move5 >= 0.05 and vol >= 1.5,
                             rip_now=rip_now, rips_next=out == 1, sp=sp, base=base))

n = len(rows)
rip = sum(r["rip_now"] for r in rows)
nxt = sum(r["rips_next"] for r in rows)
print("minutes the bot could have bought: %d | ripping now: %d (%.0f%%) | rips in the next 10 min: %d (%.0f%%)"
      % (n, rip, 100 * rip / n, nxt, 100 * nxt / n))
print("%-12s %8s | %22s %22s | %18s" % ("detector", "lit up", "of those, ripping now", "share of rips caught", "of those, rips next"))
for key, name in (("fast", 'bot "fast"'), ("up", 'bot "up"'), ("m5", "5-min move"), ("m5v", "5-min + vol")):
    f = [r for r in rows if r[key]]
    print("%-12s %7.0f%% | %21.0f%% %21.0f%% | %17.0f%%" % (
        name, 100 * len(f) / n, 100 * sum(r["rip_now"] for r in f) / max(1, len(f)),
        100 * sum(r["rip_now"] for r in f) / max(1, rip),
        100 * sum(r["rips_next"] for r in f) / max(1, len(f))))
# how jumpy is bar_speed: sign changes minute to minute while ripping
flips = [r for r in rows if r["rip_now"]]
print('during ripping minutes, bot "fast" was lit %.0f%% of the time and bar_speed was negative %.0f%% of the time'
      % (100 * sum(r["fast"] for r in flips) / max(1, len(flips)),
         100 * sum(r["sp"] < 0 for r in flips) / max(1, len(flips))))
