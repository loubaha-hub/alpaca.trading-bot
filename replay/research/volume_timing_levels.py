"""Volume concentration, when runs start, and half-dollar levels - from the
replay/data minute bars. Run: python3 replay/research/volume_timing_levels.py"""
import csv, statistics as st
from collections import Counter, defaultdict
from common import DAYS, OUT, load, hm

print("=== 1. VOLUME CONCENTRATION ===")
top_hits = Counter(); runners_all = []
share_top2 = []
for day in DAYS:
    syms = load(day)
    gain = {s: max(r[2] for r in rows)/pc - 1 for s, (pc, rows) in syms.items()}
    dv_day = {s: sum(r[4]*r[5] for r in rows) for s, (pc, rows) in syms.items()}
    tot = sum(dv_day.values()); top = sorted(dv_day, key=dv_day.get, reverse=True)
    share_top2.append(sum(dv_day[s] for s in top[:2])/tot)
    pm_cut = {"07:00": 7*60, "08:00": 8*60, "09:30": 9*60+30}
    best = sorted(gain, key=gain.get, reverse=True)[:5]
    runners = [s for s in gain if gain[s] >= 0.5]
    print("\n%s  %d names, %d ran >=50%%. Top 2 names = %.0f%% of the day's dollar volume"
          % (day, len(syms), len(runners), 100*share_top2[-1]))
    print("  top gainers: " + ", ".join("%s +%.0f%%" % (s, 100*gain[s]) for s in best))
    for lab, cut in pm_cut.items():
        dv = {s: sum(r[4]*r[5] for r in rows if hm(r[0]) < cut and r[0].hour >= 4) for s, (pc, rows) in syms.items()}
        rank = sorted(dv, key=dv.get, reverse=True)
        top3 = rank[:3]
        hits = [s for s in top3 if gain[s] >= 0.5]
        # where do the runners rank by $vol at that cut?
        rr = sorted(rank.index(s)+1 for s in runners)
        print("  by %s: top-3 $vol %-28s -> runners among them: %d/3 | runner ranks %s"
              % (lab, ",".join(top3), len(hits), rr[:12]))
        top_hits[lab] += len(hits)
print("\ntop-2 share of $vol, by day: " + " ".join("%.0f%%" % (100*x) for x in share_top2))

print("\n=== 1b. WHEN DO RUNS START? (first 1-min bar with vol >= 8x the prior-30 median and >= 50k sh, before first +20%) ===")
by_hour = Counter(); by_min = Counter(); n = 0; first20 = Counter()
for day in DAYS:
    for s, (pc, rows) in load(day).items():
        if max(r[2] for r in rows)/pc - 1 < 0.5: continue
        i20 = next((i for i, r in enumerate(rows) if r[2] >= pc*1.2), None)
        if i20 is None: continue
        first20[rows[i20][0].hour] += 1
        ign = None
        for i in range(0, i20+1):
            prior = [r[5] for r in rows[max(0, i-30):i]] or [0]
            med = st.median(prior)
            if rows[i][5] >= 50_000 and rows[i][5] >= 8*max(med, 1):
                ign = rows[i][0]; break
        if ign is None: ign = rows[i20][0]
        n += 1; by_hour[ign.hour] += 1
        mm = ign.minute
        by_min["top of hour :00-:02" if mm <= 2 else "half hour :30-:32" if 30 <= mm <= 32 else "other 54 min"] += 1
print("runners:", n)
print("ignition hour (ET):", sorted(by_hour.items()))
print("first +20% hour (ET):", sorted(first20.items()))
print("minute of hour:", dict(by_min), "(base rate if random: 5%% / 5%% / 90%%)")

print("\n=== 3. HALF-DOLLAR RESISTANCE: pivot tops vs all bar highs ===")
def near(p, step, tol): 
    r = round(p/step)*step
    return abs(p - r) <= tol + 1e-9 and r > 0
ctl = Counter(); piv = Counter(); nctl = npiv = 0
hold = Counter()
for day in DAYS:
    for s, (pc, rows) in load(day).items():
        rows_ = [r for r in rows if 1 <= r[2] <= 20]
        if len(rows_) < 30: continue
        for i in range(5, len(rows_)-10):
            h = rows_[i][2]; v = rows_[i][5]
            if v < 20_000: continue
            nctl += 1
            for k, step in (("$0.50", 0.5), ("$1.00", 1.0)):
                if near(h, step, 0.02): ctl[k] += 1
            win = rows_[i-5:i+6]
            later_low = min(r[3] for r in rows_[i+1:i+11])
            if h >= max(r[2] for r in win) and later_low <= h*0.95:
                npiv += 1
                for k, step in (("$0.50", 0.5), ("$1.00", 1.0)):
                    if near(h, step, 0.02): piv[k] += 1
print("bars (>=20k sh) %d, tops that then fell >=5%% in 10 min %d" % (nctl, npiv))
for k in ("$0.50", "$1.00"):
    print("  high within 2c of a %s level: all bars %.1f%%  tops %.1f%%  (lift x%.2f)"
          % (k, 100*ctl[k]/nctl, 100*piv[k]/npiv, (piv[k]/npiv)/(ctl[k]/nctl)))

print("\n=== 3b. Does a break of a half-dollar level hold? ===")
# when a 1-min close first goes above level L (prev close below), is the close 5 bars later still >= L?
res = Counter()
for day in DAYS:
    for s, (pc, rows) in load(day).items():
        for i in range(1, len(rows)-5):
            a, b = rows[i-1][4], rows[i][4]
            if not (1 <= b <= 20) or rows[i][5] < 20_000: continue
            for step, k in ((1.0, "whole $"), (0.5, "half $ only")):
                L = int(b/step)*step
                if k == "half $ only" and abs(L - round(L)) < 1e-9: continue
                if a < L <= b:
                    res[(k, "n")] += 1
                    res[(k, "held")] += rows[i+5][4] >= L
                    res[(k, "wick")] += min(r[3] for r in rows[i+1:i+6]) < L - 0.01
for k in ("whole $", "half $ only"):
    n_ = res[(k, "n")]
    print("  %-11s breaks %4d: still above 5 min later %.0f%%, dipped back under within 5 min %.0f%%"
          % (k, n_, 100*res[(k,"held")]/n_, 100*res[(k,"wick")]/n_))
# control: any level, e.g. x.23
ctlres = Counter()
for day in DAYS:
    for s, (pc, rows) in load(day).items():
        for i in range(1, len(rows)-5):
            a, b = rows[i-1][4], rows[i][4]
            if not (1 <= b <= 20) or rows[i][5] < 20_000: continue
            L = int(b - 0.23) + 0.23 if b - int(b) >= 0.23 else int(b) - 1 + 0.23
            if a < L <= b:
                ctlres["n"] += 1; ctlres["held"] += rows[i+5][4] >= L
                ctlres["wick"] += min(r[3] for r in rows[i+1:i+6]) < L - 0.01
print("  control x.23 breaks %4d: still above %.0f%%, dipped back %.0f%%"
      % (ctlres["n"], 100*ctlres["held"]/ctlres["n"], 100*ctlres["wick"]/ctlres["n"]))

print("\n=== 2/4. WHERE DID r26 PUT ITS MONEY? ===")
for day in DAYS:
    syms = load(day)
    gain = {s: max(r[2] for r in rows)/pc - 1 for s, (pc, rows) in syms.items()}
    rank = {s: i+1 for i, s in enumerate(sorted(gain, key=gain.get, reverse=True))}
    f = OUT / ("%s_r26_v31_full_fills.csv" % day)
    if not f.exists(): continue
    buys = defaultdict(float); pnl = defaultdict(float)
    for r in csv.DictReader(open(f)):
        q, p = float(r["qty"]), float(r["price"])
        if r["side"] == "BUY": buys[r["symbol"]] += q*p; pnl[r["symbol"]] -= q*p
        else: pnl[r["symbol"]] += q*p
    tot = sum(buys.values())
    top5 = sum(v for s, v in buys.items() if rank.get(s, 999) <= 5)
    print("%s: bought $%.0fk in %d names; %.0f%% of it in the day's top-5 gainers. "
          "P/L top-5 %+.0f, rest %+.0f" % (day, tot/1000, len(buys), 100*top5/tot,
          sum(v for s, v in pnl.items() if rank.get(s, 999) <= 5),
          sum(v for s, v in pnl.items() if rank.get(s, 999) > 5)))
