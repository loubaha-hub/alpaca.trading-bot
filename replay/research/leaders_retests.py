"""Buying the dollar-volume leaders with no lookahead, run start minutes, retests
of the day high, and r26 trades by volume rank at entry (needs replay/out
r26 fills). Run: python3 replay/research/leaders_retests.py"""
import csv, sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from common import load, DAYS, OUT, hm, ET
import statistics as st

print("=== A. NO LOOKAHEAD: buy the $vol leaders at a cut time, what came AFTER? ===")
for cut_lab, cut in (("07:00", 420), ("08:00", 480), ("09:30", 570), ("10:30", 630)):
    grp = defaultdict(list)
    for day in DAYS:
        syms = load(day)
        dv = {}; px = {}
        for s, (pc, rows) in syms.items():
            before = [r for r in rows if hm(r[0]) < cut]
            after = [r for r in rows if hm(r[0]) >= cut]
            if not before or not after: continue
            p = before[-1][4]
            if not (1 <= p <= 20) or p < pc*1.10: continue        # the scanner's rule
            dv[s] = sum(r[4]*r[5] for r in before)
            px[s] = (p, max(r[2] for r in after), min(r[3] for r in after), after[-1][4])
        rank = sorted(dv, key=dv.get, reverse=True)
        for i, s in enumerate(rank):
            p, hi, lo, last = px[s]
            g = "top 1-2" if i < 2 else "rank 3-5" if i < 5 else "rank 6+"
            grp[g].append((hi/p-1, lo/p-1, last/p-1))
    print(" cut %s (qualified = up >=10%%, $1-$20):" % cut_lab)
    for g in ("top 1-2", "rank 3-5", "rank 6+"):
        v = grp[g]
        if not v: continue
        print("   %-8s n=%3d  median further high %+5.0f%%  hit +30%% later: %3.0f%%  median worst %+4.0f%%  median at day end %+4.0f%%"
              % (g, len(v), 100*st.median(x[0] for x in v), 100*sum(x[0] >= .3 for x in v)/len(v),
                 100*st.median(x[1] for x in v), 100*st.median(x[2] for x in v)))

print("\n=== B. run start minute, leaving out the 4:00 and 9:30 session opens ===")
mins = Counter(); hrs = Counter(); n = 0
for day in DAYS:
    for s, (pc, rows) in load(day).items():
        if max(r[2] for r in rows)/pc - 1 < 0.5: continue
        # start of the main leg = the low before the day high
        ih = max(range(len(rows)), key=lambda i: rows[i][2])
        il = min(range(ih+1), key=lambda i: rows[i][3])
        # first bar after that low with volume >= 5x the prior-20 median
        t = None
        for i in range(il, ih+1):
            med = st.median([r[5] for r in rows[max(0, i-20):i]] or [0])
            if rows[i][5] >= max(5*med, 20_000): t = rows[i][0]; break
        t = t or rows[il][0]
        if (t.hour, t.minute) in ((4, 0), (4, 1)) or (t.hour == 9 and 30 <= t.minute <= 31): 
            hrs["session open"] += 1; continue
        n += 1; hrs[t.hour] += 1
        m = t.minute
        mins["xx:58-xx:02" if m >= 58 or m <= 2 else "xx:28-xx:32" if 28 <= m <= 32 else "rest"] += 1
print("legs:", n, "hours:", sorted(hrs.items(), key=lambda x: str(x[0])))
print("minute:", dict(mins), " random would be 8% / 8% / 84%")

print("\n=== C. retest of the day high after a >=5% pullback ===")
out = Counter()
for day in DAYS:
    for s, (pc, rows) in load(day).items():
        hod = 0; pulled = False; i = 0
        while i < len(rows) - 15:
            r = rows[i]
            if r[2] > hod: hod = r[2]; pulled = False
            elif r[3] <= hod*0.95: pulled = True
            if pulled and r[2] >= hod*0.99 and hod >= pc*1.2 and r[5] >= 20_000:
                nxt = rows[i+1:i+16]
                broke = max(x[2] for x in nxt) >= hod*1.03
                if broke:
                    j = next(k for k, x in enumerate(nxt) if x[2] >= hod*1.03)
                    held = nxt[min(j+5, len(nxt)-1)][4] >= hod
                    out["broke +3%, still above old high 5 min later" if held else "broke +3%, back under old high 5 min later"] += 1
                else:
                    out["failed (no +3% break in 15 min)"] += 1
                hod = max(hod, max(x[2] for x in nxt)); pulled = False; i += 16; continue
            i += 1
tot = sum(out.values())
for k, v in out.most_common(): print("  %-45s %3d  %3.0f%%" % (k, v, 100*v/tot))

print("\n=== D. r26 trades by the stock's $vol rank at the moment of entry ===")
res = defaultdict(lambda: [0, 0.0, 0])
for day in DAYS:
    syms = load(day)
    f = OUT / ("%s_r26_v31_full_fills.csv" % day)
    opn = {}
    for r in csv.DictReader(open(f)):
        sym, q, p = r["symbol"], float(r["qty"]), float(r["price"])
        h, m_, sec = map(int, r["time_et"].split(":")); t = h*60 + m_
        if r["side"] == "BUY":
            if sym not in opn:
                dv = {}
                for s2, (pc, rows) in syms.items():
                    dv[s2] = sum(x[4]*x[5] for x in rows if hm(x[0]) < t)
                rank = sorted(dv, key=dv.get, reverse=True).index(sym) + 1
                opn[sym] = [rank, 0.0]
            opn[sym][1] -= q*p
        else:
            opn[sym][1] += q*p
            # closed when sells equal buys: approximate - book at each sell, group by rank
            rank = opn[sym][0]
    for sym, (rank, pnl) in opn.items():
        pass
    # recompute round trips simply: per symbol per day P/L grouped by first-entry rank
    for sym, (rank, pnl) in opn.items():
        g = "top 1-2" if rank <= 2 else "rank 3-5" if rank <= 5 else "rank 6-10" if rank <= 10 else "rank 11+"
        res[g][0] += 1; res[g][1] += pnl; res[g][2] += pnl > 0
for g in ("top 1-2", "rank 3-5", "rank 6-10", "rank 11+"):
    n_, p, w = res[g]
    if n_: print("  %-9s names traded %3d  net P/L %+7.0f  per name %+5.0f  names won %3.0f%%" % (g, n_, p, p/n_, 100*w/n_))
