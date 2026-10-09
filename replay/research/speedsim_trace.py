"""Trade by trade, a window's speed-strategy trades with every add, the line
arming, the exit and what the stock did next (the owner, 10-09 ~2:50pm: "are
those multiple entries or a single entry? ... go into the details").

python3 speedsim_trace.py <windows dir> <A|B> DAY:SYM[:HHMM] ...   (HHMM: the window's start)"""
import os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q

hm = lambda t: datetime.fromtimestamp(t, S.ET).strftime("%H:%M:%S")


def run_hod(r, p, st, setting):
    """speedsim.play_ladder_hod with a trace per trade."""
    px0 = next((x[4] for x in r["S"] if x[4]), 1.0)
    kw = dict(mid_stop=False, stop_pct=0.10) if setting == "B" else {}
    su, arm = (0.0, 0.10 * px0) if setting == "B" else (0.03, 0.10)
    out, after, first = [], -1.0, True
    for k in sorted(st):
        on, new_high = st[k]
        t = r["start"] + k + 0.99
        if t <= after or not on or (not first and not new_high):
            continue
        t_in = t + S.BUY_LAG
        if t_in >= p.end - 5:
            break
        fill = p.ask_at(t_in)
        if not fill or fill <= 0:
            continue
        tr = []
        res = Q.run_ladder(p, t_in, fill, 4000, su, arm, trace=tr, **kw)
        out.append((t, t_in, fill, res, tr))
        after, first = res[0] + S.SELL_LAG, False
    return out, su, arm


def main():
    W = S.load_windows(sys.argv[1])
    setting = sys.argv[2]
    for want in sys.argv[3:]:
        day, sym, *start = want.split(":")
        for r in W.get((day, sym), []) if isinstance(W, dict) and (day, sym) in W else \
                [r for l in W.values() for r in l if r["day"] == day and r["sym"] == sym]:
            if start and hm(r["start"])[:5].replace(":", "") != start[0]:
                continue
            p, st = S.Path(r), Q.speed_state(r)
            trs, su, arm = run_hod(r, p, st, setting)
            px = [(r["start"] + x[0], x[4]) for x in r["S"] if x[4]]
            print("=== %s %s window %s-%s, setting %s (stop %s, half-back from +$%.2f) - %d trade(s), P/L %+.0f" % (
                day, sym, hm(r["start"]), hm(r["end"]), setting,
                "10% under the buy / average" if setting == "B" else "3c under", arm, len(trs),
                sum(x[3][1] for x in trs)))
            for n, (t_sig, t_in, fill, res, tr) in enumerate(trs, 1):
                te, pl, why, best, sh, avg, adds = res
                xp = avg + pl / sh
                start_sh = int(4000 * 0.2 / fill)
                print("  #%d signal %s -> buy %s %d sh at the ask $%.3f ($%.0f), stop $%.3f" % (
                    n, hm(t_sig), hm(t_in), start_sh, fill, start_sh * fill,
                    fill * 0.9 if setting == "B" else fill - su))
                for e in tr:
                    if e[1] == "add":
                        print("     %s add %d sh at $%.3f -> average $%.3f, stop rises to $%.3f" % (hm(e[0]), e[2], e[3], e[4], e[5]))
                    else:
                        print("     %s up %s over the average: half-back line on (best $%.3f)" % (hm(e[0]), "+$%.2f" % (e[2] - e[3]), e[2]))
                after = [v for t, v in px if te <= t <= te + 300]
                print("     %s OUT (%s) at the bid $%.3f - %d sh, average $%.3f, best $%.3f, held %ds: %+.0f"
                      "   | next 5 min: high $%s, then $%s" % (
                          hm(te), why, xp, sh, avg, best, te - t_in, pl,
                          "%.2f" % max(after) if after else "-", "%.2f" % after[-1] if after else "-"))
            print()


if __name__ == "__main__":
    main()
