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


def run_ladder(path, t0, fill0, full, stop_under, arm, steps=((0.10, 0.5), (0.20, 1.0)), start=0.2,
               mid_stop=True, stop_pct=0.0, trace=None, add_cap=None, scale=()):
    """The owner's ease-in (10-09 ~12:30pm): START of the full dollars at the
    speed buy; at the first fill + each step's cents, a buy (at the ask
    BUY_LAG later) up to that share of the full position. The stop: the buy
    price (less stop_under) - after an add, the floor rises to the average
    (as the bot's V36_FLOOR_AVG). The line: half the position's gain over its
    average, once that gain is `arm`. One sale of everything at the bid
    SELL_LAG after the decision. Returns (exit time, P/L, why, best, shares,
    average, adds made). mid_stop=False: only a print at the stop sells (the
    middle of a wide spread is not "back at the buy"). stop_pct: the stop that
    far under the buy / the average instead of stop_under (a stop sized to the
    stock's swing; the steps and the line stay in cents). add_cap: an add only
    at the step's price + add_cap or less - a stock that jumped past it gets
    no add (the size planned at that price, not at the top of the jump).
    scale ((gain, share), ...): the owner's scale-out (10-09 ~3:20pm) - resting
    sells at the average x (1 + gain), each for `share` of the whole position,
    filled at that price when a print reaches it (the chasers buy them on the
    way up); after the first one, no more adds; the rest rides the stop and the
    half-back line. P/L and shares (the whole position) include the parts sold."""
    if stop_pct:
        stop_under = fill0 * stop_pct
    sh = int(full * start / fill0)
    cost = sh * fill0
    avg = fill0
    stop = fill0 - stop_under
    best, line, k = fill0, -1.0, 0
    banked, sold, j = 0.0, 0, 0
    i = path.at(t0)
    for t, p, b, a in path.ev[i:]:
        if b and a:
            tol = max(S.PRINT_TOL_CENTS, S.PRINT_TOL_PCT * p)
            if p > a + tol or p < b - tol:
                continue
        best = max(best, p)
        while j == 0 and k < len(steps) and p >= fill0 + steps[k][0] - 1e-9:
            px = path.ask_at(t + S.BUY_LAG)
            if add_cap is not None and px and px > fill0 + steps[k][0] + add_cap + 1e-9:
                px = None                          # jumped past the step: no add, no chase
            add = int((full * steps[k][1] - cost) / px) if px and px > 0 else 0
            if add > 0:
                sh += add
                cost += add * px
                avg = cost / sh
                stop = max(stop, avg - (avg * stop_pct if stop_pct else stop_under))
                if trace is not None:
                    trace.append((t + S.BUY_LAG, "add", add, px, avg, stop))
            k += 1
        while j < len(scale) and p >= avg * (1 + scale[j][0]) - 1e-9:
            lvl = avg * (1 + scale[j][0])
            q = min(sh, int(round(scale[j][1] * (sh + sold))))
            banked += (lvl - avg) * q
            sh -= q
            sold += q
            if trace is not None:
                trace.append((t, "sold", q, lvl, avg, stop))
            j += 1
        if best - avg >= arm - 1e-9:
            if trace is not None and line < 0:
                trace.append((t, "armed", best, avg))
            line = max(line, avg + 0.5 * (best - avg))
        if p <= stop + 1e-9 or (mid_stop and b and a and (b + a) / 2 <= stop + 1e-9):
            xp = path.bid_at(t + S.SELL_LAG)
            return t, (xp - avg) * sh + banked, "stop", best, sh + sold, avg, k
        if p <= line + 1e-9 and not (b and b > line + 1e-9):
            xp = path.bid_at(t + S.SELL_LAG)
            return t, (xp - avg) * sh + banked, "line", best, sh + sold, avg, k
    last = path.ev[-1]
    return last[0], ((last[2] or last[1]) - avg) * sh + banked, "open", best, sh + sold, avg, k


def play_ladder(path, sigs, full, stop_under, arm, rebuy=True):
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
        te, pl, why, best, sh, avg, k = run_ladder(path, t_in, fill, full, stop_under, arm)
        out.append((t_in, fill, why, best, pl, sh, avg, k))
        busy_until = te + S.SELL_LAG
    return out


def speed_state(rec):
    """Per second of the window: (speed on?, a new high of the window this
    second?) - the same speed test as signals(), as a state, not an edge."""
    rows = {r[0]: r for r in rec["S"] if r[1]}
    if not rows:
        return {}
    last = max(rows)
    close, vol, dol, high = {}, {}, {}, {}
    px = None
    for k in range(0, last + 1):
        r = rows.get(k)
        if r:
            px = r[4]
        close[k], vol[k] = px, (r[5] if r else 0)
        dol[k] = (r[4] * r[5]) if r else 0.0
        high[k] = r[2] if r else None
    minute = {}
    for k in sorted(rows):
        m = (rec["start"] + k) // 60
        o, c = minute.get(m, (rows[k][1], rows[k][4]))
        minute[m] = (o, rows[k][4])
    v = [0] * (last + 2)
    d = [0.0] * (last + 2)
    for k in range(last + 1):
        v[k + 1] = v[k] + vol[k]
        d[k + 1] = d[k] + dol[k]
    out, top = {}, None
    for k in range(last + 1):
        new_high = high[k] is not None and top is not None and high[k] > top + 1e-9
        if high[k] is not None:
            top = high[k] if top is None else max(top, high[k])
        on = False
        if k >= 120:
            p2, p1 = close[k], close[k - 60]
            if p2 and p1:
                v2 = v[k + 1] - v[k - 59]
                v1 = v[k - 59] - v[k - 119]
                move = p2 / p1 - 1
                if move >= MOVE_MIN and v1 > 0:
                    m = (rec["start"] + k) // 60 - 1
                    bar = minute.get(m)
                    red = bar is not None and bar[1] < bar[0]
                    on = (move * min(v2 / v1, VOL_CAP) >= SPEED
                          and d[k + 1] - d[k - 59] >= DOLLARS_MIN and not red)
        out[k] = (on, new_high)
    return out


def play_ladder_hod(path, rec, state, full, stop_under, arm, ok=lambda t: True, **kw):
    """The owner (10-09 ~1:20pm): the first buy on a speed signal; after a sale,
    back in as often as it comes - but only at speed AND on a new high of the
    day (the window's high so far: the read starts 5 minutes before the
    bots' first buy, so an earlier high of the day is not seen)."""
    out, after, first = [], -1.0, True
    for k in sorted(state):
        on, new_high = state[k]
        t = rec["start"] + k + 0.99
        if t <= after or not on or not ok(t):
            continue
        if not first and not new_high:
            continue
        t_in = t + S.BUY_LAG
        if t_in >= path.end - 5:
            break
        fill = path.ask_at(t_in)
        if not fill or fill <= 0:
            continue
        te, pl, why, best, sh, avg, adds = run_ladder(path, t_in, fill, full, stop_under, arm, **kw)
        out.append((t_in, fill, why, best, pl, sh, avg, adds, te))
        after, first = te + S.SELL_LAG, False
    return out


def play_ladder_crowd(path, rec, state, full, stop_under, arm, in_crowd, edge=False):
    """CROWD ONLY (the owner, 10-09 ~1:35pm: the crowd and the speed are two
    separate things - test each alone). No speed test. A buy when the stock
    is in the crowd (in_crowd(t): top N by money in the last 5 minutes) and
    the price makes a new high of the day; with edge=True the FIRST buy is the
    moment it joins the top N instead (no price condition). Back in, as often
    as it comes, on a new high while still in the top N."""
    out, after, first, was = [], -1.0, True, False
    for k in sorted(state):
        _, new_high = state[k]
        t = rec["start"] + k + 0.99
        inc = in_crowd(t)
        joined = inc and not was
        was = inc
        if t <= after or not inc:
            continue
        if not (new_high or (edge and first and joined)):
            continue
        t_in = t + S.BUY_LAG
        if t_in >= path.end - 5:
            break
        fill = path.ask_at(t_in)
        if not fill or fill <= 0:
            continue
        te, pl, why, best, sh, avg, adds = run_ladder(path, t_in, fill, full, stop_under, arm)
        out.append((t_in, fill, why, best, pl, sh, avg, adds))
        after, first = te + S.SELL_LAG, False
    return out


def main_ladder():
    windows = S.load_windows(sys.argv[1])
    full = float(sys.argv[3]) if len(sys.argv) > 3 else 4000.0
    recs = [r for lst in windows.values() for r in lst]
    data = [(r, S.Path(r), signals(r)) for r in recs]
    print("THE EASE-IN: 20%% at the speed buy, 50%% at +10c, full at +20c over the first fill; full = $%.0f" % full)
    print("%-26s %7s %5s %6s %10s %8s %8s %6s %6s  %s" % ("stop / half from / rebuy", "trades", "won", "won%",
                                                       "P/L", "avg win", "avg loss", "+10c", "+20c", "by day"))
    keep = {}
    for su in (0.00, 0.02, 0.05, 0.10):
        for arm in (0.01, 0.05, 0.10):
            for rb in ((True, False) if (su, arm) in ((0.0, 0.01), (0.05, 0.05), (0.10, 0.05)) else (True,)):
                rows, per_day = [], defaultdict(float)
                for r, path, sg in data:
                    for tr in play_ladder(path, sg, full, su, arm, rb):
                        rows.append((r["day"], r["sym"], tr))
                        per_day[r["day"]] += tr[4]
                pl = [x[2][4] for x in rows]
                w = [x for x in pl if x > 0]
                l = [x for x in pl if x <= 0]
                print("%-26s %7d %5d %5.0f%% %+10.2f %+8.2f %+8.2f %6d %6d  %s" % (
                    "%2.0fc under / %2.0fc / %s" % (100 * su, 100 * arm, "yes" if rb else "no"),
                    len(pl), len(w), 100 * len(w) / max(1, len(pl)), sum(pl),
                    sum(w) / max(1, len(w)), sum(l) / max(1, len(l)),
                    sum(x[2][7] >= 1 for x in rows), sum(x[2][7] >= 2 for x in rows),
                    "  ".join("%s %+.0f" % (d[5:], per_day[d]) for d in sorted(per_day))))
                keep[(su, arm, rb)] = rows
    from datetime import datetime
    for key in ((0.0, 0.01, True), (0.10, 0.05, True)):
        rows = keep[key]
        tot = sum(x[2][4] for x in rows)
        top = sorted(rows, key=lambda x: -x[2][4])
        print("\n%2.0fc under / half from %2.0fc / rebuy: total %+.2f; without the best trade %+.2f; the biggest:" % (
            100 * key[0], 100 * key[1], tot, tot - top[0][2][4]))
        for d, sym, tr in top[:5] + sorted(rows, key=lambda x: x[2][4])[:3]:
            print("  %s %-5s %s first %.3f avg %.3f shares %d adds %d best %.3f %-4s %+9.2f" % (
                d, sym, datetime.fromtimestamp(tr[0], S.ET).strftime("%H:%M:%S"), tr[1], tr[6], tr[5], tr[7],
                tr[3], tr[2], tr[4]))


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
    if len(sys.argv) > 2 and sys.argv[2] == "ladder":
        main_ladder()
    else:
        main()
