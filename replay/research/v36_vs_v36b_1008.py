"""10-08: v36 (T6HH) and v36b (AUES) trade by trade, paired by symbol and time,
P/L as a share of each account - where the two differ and why."""
import json
t = json.load(open('replay/live/2026-10-08_audit/trades.json'))['trades']
EQ = {"v36": 16491.0, "v36b": 6384.0}
rows = []
for x in t:
    if x['strategy'] not in EQ: continue
    o, e, d = x['order'], x['exit'], x['decision']
    rows.append(dict(s=x['strategy'], sym=x['symbol'], t=o['fill_time_et'][:8], fill=o['fill_price'], sh=o['got'],
                     dollars=o['dollars'], pl=x['pl'], why=e.get('why'), stop0=x['stop'].get('first_in_enter'),
                     stop=x['stop'].get('final_at_entry'), peak=e.get('peak'), held=e.get('held_s'), fur=x['furious'],
                     route=x['route'][:22], exitpx=e.get('price')))
# later trades (9:47 ET on), from the EXIT lines
late = [("v36b","AMOD","09:51",2.96,-13.76),("v36","AMOD","09:51",2.96,-46.85),("v36b","BIAF","10:08",9.1081,2.14),("v36","BIAF","10:09",8.65,9.99),
        ("v36b","INHD","10:20",5.64,-14.56),("v36","INHD","10:31",5.7753,1.64),("v36b","CPHI","11:12",1.10,-51.42),("v36","CPHI","11:13",1.06,57.05),
        ("v36b","NCT","11:47",2.16,-8.14),("v36","NCT","11:47",2.15,-0.99),("v36","CRE","12:39",3.55,-90.48),("v36b","SAIQ","15:34",5.1656,-4.59),
        ("v36","SAIQ","15:34",5.17,-11.80),("v36","XRTX","16:10",2.24,-22.55),("v36b","XRTX","16:10",2.24,-2.63),("v36b","WORX","16:51",6.7268,-19.66),
        ("v36","WORX","16:51",6.74,-53.55),("v36b","WORX","16:53",7.11,-3.60),("v36","WORX","16:53",7.1152,-10.37)]
for s, sym, tm, f, pl in late:
    rows.append(dict(s=s, sym=sym, t=tm + ":00", fill=f, sh=None, dollars=None, pl=pl, why="", stop0=None, stop=None, peak=None, held=None, fur=None, route="", exitpx=None))
for s in EQ:
    r = [x for x in rows if x['s'] == s]
    print(s, len(r), "trades, P/L %+.2f = %+.2f%% of the day's start" % (sum(x['pl'] for x in r), 100 * sum(x['pl'] for x in r) / EQ[s]))
# pair: same symbol, fills within 20 s
def sec(tm): h, m, x = tm.split(":"); return int(h) * 3600 + int(m) * 60 + float(x)
a = [x for x in rows if x['s'] == 'v36']; b = [x for x in rows if x['s'] == 'v36b']
used = set(); pairs = []; only_a = []
for x in a:
    best = None
    for j, y in enumerate(b):
        if j in used or y['sym'] != x['sym']: continue
        dt = abs(sec(y['t']) - sec(x['t']))
        if dt <= 25 and (best is None or dt < best[0]): best = (dt, j)
    if best: used.add(best[1]); pairs.append((x, b[best[1]]))
    else: only_a.append(x)
only_b = [y for j, y in enumerate(b) if j not in used]
pa = lambda x: 100 * x['pl'] / EQ[x['s']]
print("\nPAIRED (both bought within 25s): %d" % len(pairs))
tot_a = tot_b = 0
for x, y in pairs:
    tot_a += pa(x); tot_b += pa(y)
    flag = " <==" if abs(pa(x) - pa(y)) >= 0.3 else ""
    print("  %-5s %s  v36 %6.3f %-5s %+8.2f (%+.2f%%) | v36b %6.3f %-5s %+8.2f (%+.2f%%)  diff %+.2f%%%s" % (
        x['sym'], x['t'], x['fill'], (x['why'] or '')[:5], x['pl'], pa(x), y['fill'], (y['why'] or '')[:5], y['pl'], pa(y), pa(y) - pa(x), flag))
print("  paired total: v36 %+.2f%%  v36b %+.2f%%" % (tot_a, tot_b))
print("\nONLY v36: %d, %+.2f%%" % (len(only_a), sum(pa(x) for x in only_a)))
for x in only_a: print("  %-5s %s %6.3f %-8s %+8.2f (%+.2f%%) %s" % (x['sym'], x['t'], x['fill'], x['why'], x['pl'], pa(x), x['route']))
print("\nONLY v36b: %d, %+.2f%%" % (len(only_b), sum(pa(y) for y in only_b)))
for y in only_b: print("  %-5s %s %6.3f %-8s %+8.2f (%+.2f%%) %s" % (y['sym'], y['t'], y['fill'], y['why'], y['pl'], pa(y), y['route']))
