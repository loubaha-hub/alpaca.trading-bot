"""The owner's simple speed strategy (10-09, ~12pm), replayed second by second.

  - Buy only on speed: the owner's speed (the price up 3%+ over the last 60s,
    times the volume of the last 60s over the 60s before, capped at 30) at
    0.30+, on $250k+ traded in the last 60s, the last closed minute not red -
    the bots' furious test. A buy at the ask BUY_LAG after the signal.
  - Out when it comes back to the buy (STOP_UNDER under the fill: a print or
    the middle of the bid and ask), or once up ARM, on giving back half the
    gain since the buy - "the longer it runs, the longer the leash".
  - Shaken out: back in at once on the next speed signal (a new rising edge),
    same dollars - "you enter immediately, and you stay in there".
  - No spread, liquidity or pattern checks. No adds.

The windows are SEC_DUMP's (secread.py): 5 minutes before the bots' buys to 30
minutes after, so only the stocks the bots traded, around those moments.

python3 speedsim.py <windows dir> [dollars]"""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S

SPEED, MOVE_MIN, VOL_CAP, DOLLARS_MIN = 0.30, 0.03, 30.0, 250_000


def signals(rec):
    """Rising edges of the speed test, from the one-row-a-second read:
    [(epoch time, price)]."""
    rows = {r[0]: r for r in rec["S"] if r[1]}
    if not rows:
        return []
    last = max(rows)
    close, vol, dol = {}, {}, {}
    px = None
    for k in range(0, last + 1):
        r = rows.get(k)
        if r:
            px = r[4]
        close[k] = px
        vol[k] = r[5] if r else 0
        dol[k] = (r[4] * r[5]) if r else 0.0
    minute = {}                                   # minute index -> (open, close)
    for k in sorted(rows):
        m = (rec["start"] + k) // 60
        o, c = minute.get(m, (rows[k][1], rows[k][4]))
        minute[m] = (o, rows[k][4])
    out, was = [], False
    v = [0] * (last + 2)
    d = [0.0] * (last + 2)
    for k in range(last + 1):                     # running sums
        v[k + 1] = v[k] + vol[k]
        d[k + 1] = d[k] + dol[k]
    for k in range(120, last + 1):
        p2, p1 = close[k], close[k - 60]
        on = False
        if p2 and p1:
            v2 = v[k + 1] - v[k - 59]
            v1 = v[k - 59] - v[k - 119]
            move = p2 / p1 - 1
            if move >= MOVE_MIN and v1 > 0:
                speed = move * min(v2 / v1, VOL_CAP)
                m = (rec["start"] + k) // 60 - 1
                bar = minute.get(m)
                red = bar is not None and bar[1] < bar[0]
                on = speed >= SPEED and d[k + 1] - d[k - 59] >= DOLLARS_MIN and not red
        if on and not was:
            out.append((rec["start"] + k + 0.99, p2))
        was = on
    return out


def half_line(arm):
    def line(fill, best):
        if best - fill < arm - 1e-9:
            return -1.0
        return fill + 0.5 * (best - fill)
    return line


def play(path, sigs, dollars, stop_under, arm, rebuy=True):
    """Every trade in one window: [(entry t, fill, exit, why, best, P/L)]."""
    out, busy_until = [], -1.0
    for t_sig, _ in sigs:
        if t_sig <= busy_until:
            continue
        if out and not rebuy:
            break
        t_in = t_sig + S.BUY_LAG
        if t_in >= path.end - 5:
            break
        fill = path.ask_at(t_in)
        if not fill or fill <= 0:
            continue
        sh = int(dollars / fill)
        if sh <= 0:
            continue
        te, xp, why, best = S.run(path, t_in, fill, sh, lambda f: f - stop_under, half_line(arm))
        out.append((t_in, fill, xp, why, best, (xp - fill) * sh))
        busy_until = te + S.SELL_LAG
    return out


def main():
    windows = S.load_windows(sys.argv[1])
    dollars = float(sys.argv[2]) if len(sys.argv) > 2 else 4000.0
    variants = [(su, arm, rb) for su in (0.00, 0.02, 0.05, 0.10) for arm in (0.01, 0.05, 0.10)
                for rb in (True,)] + [(0.02, 0.05, False)]
    recs = [r for lst in windows.values() for r in lst]
    paths, sigs = {}, {}
    for r in recs:
        key = (r["day"], r["sym"], r["start"])
        paths[key] = S.Path(r)
        sigs[key] = signals(r)
    nsig = sum(len(v) for v in sigs.values())
    print("windows %d (%s), speed signals %d, $%.0f a trade, buy at the ask %.1fs after, sell at the bid %.1fs after"
          % (len(recs), ", ".join(sorted({r["day"] for r in recs})), nsig, dollars, S.BUY_LAG, S.SELL_LAG))
    print("%-24s %7s %5s %6s %10s %8s %8s %8s  %s" % ("stop / half from / rebuy", "trades", "won", "won%", "P/L",
                                                  "avg win", "avg loss", "best", "by day"))
    best_detail = None
    for su, arm, rb in variants:
        trades, per_day = [], defaultdict(float)
        for key, path in paths.items():
            for tr in play(path, sigs[key], dollars, su, arm, rb):
                trades.append((key, tr))
                per_day[key[0]] += tr[5]
        pl = [tr[5] for _, tr in trades]
        wins = [x for x in pl if x > 0]
        loss = [x for x in pl if x <= 0]
        print("%-24s %7d %5d %5.0f%% %+10.2f %+8.2f %+8.2f %+8.2f  %s" % (
            "%2.0fc under / %2.0fc / %s" % (100 * su, 100 * arm, "yes" if rb else "no"),
            len(pl), len(wins), 100 * len(wins) / max(1, len(pl)), sum(pl),
            sum(wins) / max(1, len(wins)), sum(loss) / max(1, len(loss)), max(pl or [0]),
            "  ".join("%s %+.0f" % (d[5:], per_day[d]) for d in sorted(per_day))))
        if (su, arm, rb) == (0.02, 0.05, True):
            best_detail = trades
    if best_detail:
        print("\nThe biggest trades, 2c under / half from 5c / rebuy:")
        for key, tr in sorted(best_detail, key=lambda x: -abs(x[1][5]))[:15]:
            from datetime import datetime
            hm = datetime.fromtimestamp(tr[0], S.ET).strftime("%H:%M:%S")
            print("  %s %-5s %s buy %.3f out %.3f (%s) best %.3f  %+8.2f" % (
                key[0], key[1], hm, tr[1], tr[2], tr[3], tr[4], tr[5]))


if __name__ == "__main__":
    main()
