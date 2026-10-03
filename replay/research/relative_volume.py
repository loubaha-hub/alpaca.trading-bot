"""Does relative volume pick the runners? Sample every 5 minutes, only names the
bot could buy then (up >=10%, $1-$20, last 3 bars each >=30k sh and >=100k
together), only data known at that minute. Outcome: buy the next bar's open;
within 60 min, does +15% come before -7.5%? (both in one bar = loss)."""
import json, sys, statistics as st
from collections import defaultdict
from pathlib import Path
from common import load, DAYS, hm, REPO
SP = REPO / "replay" / "data"
daily = json.loads((SP/"daily_bars.json").read_text())
flt = {}
if (SP/"float.csv").exists():
    import csv
    for r in csv.DictReader(open(SP/"float.csv")):
        try: flt[r["symbol"]] = float(r["float_shares"])
        except (ValueError, TypeError): pass

def adv(sym, day, n=30):
    d = daily.get(sym, {})
    prev = sorted(k for k in d if k < day)[-n:]
    vols = [d[k][4] for k in prev]
    return (sum(vols)/len(vols) if len(vols) >= 10 else None), (d[prev[-1]][1] if prev else None)

samples = []
for day in DAYS:
    syms = load(day)
    info = {s: adv(s, day) for s in syms}
    for t in range(4*60+15, 15*60+30, 5):
        cand = []
        for s, (pc, rows) in syms.items():
            before = [r for r in rows if hm(r[0]) < t]
            if len(before) < 35: continue
            p = before[-1][4]
            if not (1 <= p <= 20) or p < pc*1.10: continue
            l3 = before[-3:]
            if any(r[5] < 30_000 for r in l3) or sum(r[5] for r in l3) < 100_000: continue
            if hm(l3[0][0]) < t - 5: continue                     # bars must be recent
            after = [r for r in rows if t <= hm(r[0]) < t + 60]
            if len(after) < 5: continue
            a, pdh = info[s]
            cum = sum(r[5] for r in before)
            v5 = sum(r[5] for r in before[-5:]); v30 = sum(r[5] for r in before[-35:-5]) / 6
            e = after[0][1]; out = 0
            for r in after:
                if r[3] <= e*0.925: out = -1; break
                if r[2] >= e*1.15: out = 1; break
            cand.append(dict(day=day, t=t, s=s, rvol=cum/a if a else None, accel=v5/max(v30, 1),
                             dv=sum(r[4]*r[5] for r in before), gap=p/pc-1, float=flt.get(s),
                             move15=p/before[-16][4]-1, out=out,
                             mfe=max(r[2] for r in after)/e-1, pdh=pdh, p=p))
        for key in ("dv", "rvol"):
            ranked = sorted([c for c in cand if c[key] is not None], key=lambda c: c[key], reverse=True)
            for i, c in enumerate(ranked): c[key+"_rank"] = i + 1
        samples += cand

def show(title, groups):
    print(title)
    for lab, v in groups:
        if not v: continue
        w = sum(c["out"] == 1 for c in v); l = sum(c["out"] == -1 for c in v)
        # 2:1 payoff: +2 per win, -1 per loss, 0 if neither in 60 min
        print("   %-22s n=%5d  +15%% first %4.0f%%  -7.5%% first %4.0f%%  neither %4.0f%%  edge/trade %+.2fR"
              % (lab, len(v), 100*w/len(v), 100*l/len(v), 100*(len(v)-w-l)/len(v), (2*w - l)/len(v)))
S = samples
print("samples: %d  (name x 5-minute checks the bot could have bought)" % len(S))
show("\nALL", [("all", S)])
show("\nRELATIVE VOLUME (today's volume so far / 30-day average day)",
     [(lab, [c for c in S if c["rvol"] is not None and lo <= c["rvol"] < hi]) for lab, lo, hi in
      (("< 1x", 0, 1), ("1-3x", 1, 3), ("3-10x", 3, 10), ("10-30x", 10, 30), ("30x+", 30, 1e9))])
show("\nRVOL RANK at that minute (among names the bot could buy)",
     [(lab, [c for c in S if c.get("rvol_rank") and lo <= c["rvol_rank"] <= hi]) for lab, lo, hi in
      (("#1", 1, 1), ("#2-3", 2, 3), ("#4-6", 4, 6), ("#7+", 7, 999))])
show("\nDOLLAR-VOLUME RANK at that minute",
     [(lab, [c for c in S if lo <= c["dv_rank"] <= hi]) for lab, lo, hi in
      (("#1", 1, 1), ("#2-3", 2, 3), ("#4-6", 4, 6), ("#7+", 7, 999))])
show("\nVOLUME INCREASE (last 5 min vs the 30 before, per minute)",
     [(lab, [c for c in S if lo <= c["accel"] < hi]) for lab, lo, hi in
      (("< 0.5x (drying up)", 0, .5), ("0.5-1x", .5, 1), ("1-2x", 1, 2), ("2-4x", 2, 4), ("4x+", 4, 1e9))])
show("\nPRICE MOVE LAST 15 MIN",
     [(lab, [c for c in S if lo <= c["move15"] < hi]) for lab, lo, hi in
      (("down", -1, 0), ("0-5%", 0, .05), ("5-15%", .05, .15), ("15%+", .15, 9))])
if flt:
    show("\nFLOAT (shares, Webull today - not as of each day)",
         [(lab, [c for c in S if c["float"] is not None and lo <= c["float"] < hi]) for lab, lo, hi in
          (("< 2M", 0, 2e6), ("2-5M", 2e6, 5e6), ("5-10M", 5e6, 10e6), ("10-30M", 10e6, 30e6), ("30M+", 30e6, 1e12))])
    show("\nVOLUME TODAY / FLOAT (float rotation)",
         [(lab, [c for c in S if c["float"] and c["rvol"] is not None and lo <= (c["rvol"]*adv(c["s"], c["day"])[0])/c["float"] < hi])
          for lab, lo, hi in (("< 0.5x", 0, .5), ("0.5-1x", .5, 1), ("1-3x", 1, 3), ("3x+", 3, 1e9))])
show("\nTIME OF DAY",
     [(lab, [c for c in S if lo <= c["t"] < hi]) for lab, lo, hi in
      (("4:00-7:00", 240, 420), ("7:00-9:30", 420, 570), ("9:30-10:30", 570, 630), ("10:30-12:00", 630, 720), ("12:00-15:30", 720, 930))])
show("\nCOMBINED: rvol rank #1-3 AND volume rising (>=1x)",
     [("yes", [c for c in S if c.get("rvol_rank", 99) <= 3 and c["accel"] >= 1]),
      ("no", [c for c in S if not (c.get("rvol_rank", 99) <= 3 and c["accel"] >= 1)])])
show("\nPRIOR DAY HIGH: price just under it (within 3%) vs already above",
     [("0-3% under prior-day high", [c for c in S if c["pdh"] and c["pdh"]*0.97 <= c["p"] < c["pdh"]]),
      ("above prior-day high", [c for c in S if c["pdh"] and c["p"] >= c["pdh"]]),
      ("more than 3% under", [c for c in S if c["pdh"] and c["p"] < c["pdh"]*0.97])])
json.dump(S, open(REPO/"replay"/"out"/"rvol_samples.json", "w"))
