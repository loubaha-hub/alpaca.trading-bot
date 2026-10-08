"""10-08: the buys of all three bots within 3c under to 5c over a whole / half dollar (the
V36_LEVELS band), from the audit; writes them for levels_wait.py.
python3 levels_near.py <out.json>"""
import sys
import json
t = json.load(open('replay/live/2026-10-08_audit/trades.json'))['trades']
W = {"AIXI":[("04:02:00","04:08:00")],"IPW":[("04:09:48","04:16:00")],"DKI":[("04:13:08","04:22:00"),("05:00:17","05:06:00"),("06:57:06","07:03:00")],
     "SBFM":[("05:20:47","05:28:00")],"MEDS":[("05:43:21","05:49:00")],"MOBX":[("07:01:19","07:07:00")],"FLYE":[("07:23:00","07:31:00")],
     "CHR":[("08:01:49","08:07:00")],"BIAF":[("08:09:11","08:15:00")],"NCT":[("11:46:10","11:52:00")]}
def band(p, below=0.03, past=0.05):
    lvl = int((p + below) * 2 + 1e-9) / 2.0
    if p < lvl - 1e-9: return 'under', lvl
    if p < lvl + past - 1e-9: return 'past', lvl
    return 'clear', lvl
out = []
for x in t:
    d, o, e = x['decision'], x['order'], x['exit']
    px = d.get('enter_print') or d.get('print'); fill = o['fill_price']
    b1, l1 = band(px); b2, l2 = band(fill)
    if b1 == 'clear' and b2 == 'clear': continue
    tf = o['fill_time_et'][:12]
    cov = any(a <= tf <= z for a, z in W.get(x['symbol'], []))
    out.append(dict(id=x['id'], strat=x['strategy'], sym=x['symbol'], t=tf, px=px, fill=fill, lvl=l1 if b1!='clear' else l2,
                    band=b1+'/'+b2, furious=x['furious'], sh=o['got'], stop=x['stop']['final_at_entry'], pl=x['pl'], why=e.get('why'), peak=e.get('peak'), ticks=cov))
for r in out: print(r)
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else 'near.json', 'w'))
print(len(out), sum(r['pl'] for r in out))
