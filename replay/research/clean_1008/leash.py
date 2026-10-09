import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))  # run from this folder
"""v36's furious exit as the bot runs it, second by second: the first stop (v36:
the tighter of 10c under the fill and 1c under the whole/half dollar under it;
v36b: also 3% under), the stop raised to 1c under each line held 3s past +5c,
the 10-second leash (a 10s candle opened 10s+ after the buy closing red under
the lows of the two before), out on 30% back of a 30c+ gain, a trail of 2 ABR
(2%-25%) from +10%. Every furious entry of v36 and v36b with data; the same
entry under each first stop."""
import json, sys
from collections import defaultdict
sys.path.insert(0, REPO + "/replay/research")
import secsim as S, secsim_run as R
D = REPO + "/replay/live/2026-10-08_secdump"
W_ = S.load_windows(D + "/windows"); rts = json.load(open(D + "/roundtrips.json")); paths = {}
EQ = {"v36": 17000, "v36b": 6500}

def half_under(p): return int(p * 2 + 1e-9) / 2.0

def abr(path, t0):
    """Average 1-minute range over the 5 minutes before t0 (from the path)."""
    mins = defaultdict(list)
    for t, p, b, a in path.ev[:path.at(t0)]:
        if t >= t0 - 300: mins[int(t // 60)].append(p)
    r = [max(v) - min(v) for v in mins.values() if v]
    return sum(r) / len(r) if r else 0.0

def run(path, t0, fill, shares, first_stop, leash=True, line_rule=True):
    stop = first_stop
    line = half_under(fill); since = None
    peak = fill; ten = None; tens = []; armed = False; trail = 0.0
    dist_abr = 2 * abr(path, t0)
    for t, p, b, a in path.ev[path.at(t0):]:
        if b and a:
            tol = max(S.PRINT_TOL_CENTS, S.PRINT_TOL_PCT * p)
            if p > a + tol or p < b - tol: continue
        # 10s candles
        k = int(t // 10)
        if ten and ten[0] == k:
            ten = (k, ten[1], max(ten[2], p), min(ten[3], p), p)
        else:
            if ten:
                tens.append(ten)
                if leash and len(tens) >= 3 and tens[-1][0] * 10 >= t0 + 10:
                    _, o, _, _, c = tens[-1]
                    if c < o and c < min(tens[-2][3], tens[-3][3]):
                        return t, path.bid_at(t + S.SELL_LAG), "10s", peak
            ten = (k, p, p, p, p)
        peak = max(peak, p)
        if line_rule:                                   # raise_line
            nxt = line + 0.5
            if p >= nxt + 0.05 - 1e-9:
                if since is None: since = t
                elif t - since >= 3.0:
                    line = nxt; since = t; stop = max(stop, nxt - 0.01)
            else:
                since = None
        if peak >= fill * 1.10: armed = True
        if p <= stop + 1e-9 or (b and a and (b + a) / 2 <= stop + 1e-9):
            return t, path.bid_at(t + S.SELL_LAG), "stop", peak
        if peak >= fill + 0.30 - 1e-9:
            fl = max(fill, fill + 0.7 * (peak - fill))
            if p <= fl + 1e-9 and not (b and b > fl + 1e-9):
                return t, path.bid_at(t + S.SELL_LAG), "giveback", peak
        if armed:
            d = min(max(dist_abr, 0.02 * peak), 0.25 * peak)
            trail = max(trail, peak - d)
            if p <= trail + 1e-9:
                return t, path.bid_at(t + S.SELL_LAG), "trail", peak
    last = path.ev[-1]
    return last[0], last[2] or last[1], "open", peak

STOPS = {
    "v36: 10c": lambda f: max(f - 0.10, half_under(f) - 0.01, f * 0.92),
    "v36b: 10c + 3%": lambda f: max(f - 0.10, half_under(f) - 0.01, f * 0.97),
    "15c": lambda f: max(f - 0.15, half_under(f) - 0.01, f * 0.92),
    "10c, no line stop": lambda f: max(f - 0.10, f * 0.92),
}
for bot in ("v36", "v36b"):
    tot = defaultdict(float); won = defaultdict(int); byday = defaultdict(float); n = 0; live = 0.0
    why = defaultdict(lambda: defaultdict(int)); rows = []
    for day in sorted(rts[bot]):
        for rt in rts[bot][day]:
            if rt["pl"] is None: continue
            t0, px, sh = R.entries(rt, day)
            if px * sh < 0.15 * EQ[bot]: continue           # furious = a full position at once
            path = S.path_for(W_, paths, day, rt["sym"], t0)
            if not path: continue
            n += 1; live += rt["pl"]; row = []
            for name, f in STOPS.items():
                te, xp, w, best = run(path, t0, px, sh, f(px))
                v = (xp - px) * sh
                tot[name] += v; won[name] += v > 0; byday[(name, day)] += v; why[name][w] += 1
                row.append((v, te - t0, w))
            rows.append((day[5:], rt["open"], rt["sym"], px, rt["pl"], row))
    print("=== %s: %d furious entries with data, live %+.0f (adds included)" % (bot, n, live))
    for name in STOPS:
        print("  %-18s %+7.0f  %2d won  by day %s  exits %s" % (name, tot[name], won[name],
              " ".join("%+.0f" % byday[(name, d)] for d in sorted(rts[bot])), dict(why[name])))
    for d, o, sym, px, pl, row in rows:
        print("    %s %s %-5s %.3f live %+5.0f | %s" % (d, o, sym, px, pl, " | ".join(
            "%+5.0f %4.0fs %s" % r for r in row[:2])))
