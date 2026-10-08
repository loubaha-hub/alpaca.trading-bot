import logging, bisect, sys
from collections import deque, defaultdict
logging.disable(logging.CRITICAL)
src=open('tickreplay.py').read(); ns={'__name__':'x','__file__':'tickreplay.py'}
exec(src[:src.index('def main')], ns)
bot=ns['bot']; d=ns['load']('../live/2026-10-08_ticks/tickdump_v37.txt.gz'); ts=ns['ts']
WS=(2,5,10); HS=(1,5,30)
def bucket(g):
    return None if g is None else ("green >=70%" if g>=0.70 else ("mixed 30-70%" if g>0.30 else "red <=30%"))
stats={W:defaultdict(lambda: defaultdict(list)) for W in WS}
green_at={}            # (sym, t) -> {W: green share} for the buy check later
for (sym,a),v in d.items():
    t0=ts(a)
    Q=[(t0+r[0]/1000, r[1], r[2]) for r in v['Q'] if r[1]>0 and r[2]>=r[1]]
    qt=[q[0] for q in Q]
    T=[(t0+r[0]/1000, r[1], r[2]) for r in v['T'] if bot.qualifies(list(r[3]))]
    side=[]
    k=-1
    for t,p,sz in T:
        while k+1<len(Q) and Q[k+1][0]<=t: k+=1
        if k<0: side.append(0); continue
        _,b,a_=Q[k]
        side.append(1 if p>=a_-1e-9 else (-1 if p<=b+1e-9 else 0))
    win={W:deque() for W in WS}; agg={W:[0.0,0.0] for W in WS}
    for i,(t,p,sz) in enumerate(T):
        for W in WS:
            dq=win[W]; dq.append((t,sz,side[i]))
            if side[i]==1: agg[W][0]+=sz
            elif side[i]==-1: agg[W][1]+=sz
            while dq and dq[0][0]<t-W:
                _,s0,sd=dq.popleft()
                if sd==1: agg[W][0]-=s0
                elif sd==-1: agg[W][1]-=s0
        k=bisect.bisect_right(qt,t)-1
        if k<0: continue
        m0=(Q[k][1]+Q[k][2])/2
        g={W:(agg[W][0]/(agg[W][0]+agg[W][1]) if agg[W][0]+agg[W][1]>0 else None) for W in WS}
        green_at[(sym,round(t,3))]=g
        if i%3: continue                     # every 3rd print, to keep cases apart
        for W in WS:
            bk=bucket(g[W])
            if bk is None: continue
            for h in HS:
                k2=bisect.bisect_right(qt,t+h)-1
                if Q[k2][0] < t+h-max(5,h):   # no quote near: skip
                    continue
                stats[W][bk][h].append((Q[k2][1]+Q[k2][2])/2-m0)
for W in WS:
    print(f"\nTape over the last {W}s (share of shares that traded at the ask):")
    print(f"  {'':14} {'cases':>8} | " + " | ".join(f"mid {h:>2}s later" for h in HS))
    for bk in ("green >=70%","mixed 30-70%","red <=30%"):
        row=stats[W][bk]
        n=len(row[HS[0]])
        print(f"  {bk:14} {n:>8,} | " + " | ".join(f"{100*sum(row[h])/len(row[h]):>+12.2f}c" for h in HS))
import pickle; pickle.dump(green_at, open('/tmp/claude-0/-home-user-alpaca-trading-bot/72589a32-e8e5-5a5d-a568-d8be4862391d/scratchpad/tick/green_at.pkl','wb'))
