"""Round trips in daily bars: a stock that ran up and came back down.

A run starts on a day whose high is RUN_PCT or more above the day before's
close (the base). Successive up days extend it (the peak keeps rising). The
round trip is complete on the first day, from the peak day on (same day
included), whose close is back within BACK_PCT of the base - or under it.
Episodes less than GAP_DAYS trading days apart count as one. Only bases of
MIN_PRICE+ and run days with MIN_DOLLARS+ traded count.

usage: python3 -I roundtrips.py OUT.json BARS.json [BARS.json ...]
"""
import json
import sys
from datetime import date

START = "2026-07-08"            # 90 calendar days to 2026-10-05
RUN_PCT = 0.50
BACK_PCT = 0.20
GAP_DAYS = 2
MIN_PRICE = 1.00
MIN_DOLLARS = 5_000_000


def episodes(rows, run_pct=RUN_PCT, back_pct=BACK_PCT):
    """[(run_day, base, peak, peak_day, back_day or None, run_day_dollars)]"""
    out = []
    i = 1
    while i < len(rows):
        d, o, h, l, c, v = rows[i]
        base = rows[i - 1][4]
        dollars = v * (h + l) / 2
        if d < START or base < MIN_PRICE or h < base * (1 + run_pct) or dollars < MIN_DOLLARS:
            i += 1
            continue
        peak, peak_i, back_i = h, i, None
        j = i
        while j < len(rows):
            if rows[j][2] > peak:
                peak, peak_i = rows[j][2], j
            if rows[j][4] <= base * (1 + back_pct):
                back_i = j
                break
            j += 1
        out.append([i, base, peak, peak_i, back_i, dollars])
        if back_i is None:
            break                           # still up at the end of the window
        i = back_i + 1
    # merge episodes that are not GAP_DAYS apart
    merged = []
    for e in out:
        if merged and merged[-1][4] is not None and e[0] - merged[-1][4] < GAP_DAYS:
            m = merged[-1]
            if e[2] > m[2]:
                m[2], m[3] = e[2], e[3]
            m[4] = e[4]
            m[5] = max(m[5], e[5])
        else:
            merged.append(e)
    return [(rows[a][0], b, p, rows[pi][0], rows[bi][0] if bi is not None else None, dl)
            for a, b, p, pi, bi, dl in merged]


def days_between(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def main():
    out_path, paths = sys.argv[1], sys.argv[2:]
    bars = {}
    for p in paths:
        bars.update(json.load(open(p)))
    result = {}
    for sym, rows in bars.items():
        rows = sorted(rows)
        if not rows:
            continue
        eps = episodes(rows)
        n30 = sum(1 for e in episodes(rows, 0.30) if e[4])
        if eps or n30:
            result[sym] = {
                "trips": [e for e in eps if e[4]],
                "open": [e for e in eps if not e[4]],
                "last_close": rows[-1][4],
                "n30": n30,
                "n100": sum(1 for e in episodes(rows, 1.00) if e[4]),
            }
    json.dump(result, open(out_path, "w"), indent=0)
    trips = {s: r for s, r in result.items() if r["trips"]}
    print("stocks with bars: %d | with a round trip: %d | trips: %d | runs still up: %d" % (
        len(bars), len(trips), sum(len(r["trips"]) for r in trips.values()),
        sum(len(r["open"]) for r in result.values())))
    for sym, r in sorted(trips.items(), key=lambda x: (-len(x[1]["trips"]), x[0]))[:40]:
        t = r["trips"]
        gaps = [days_between(t[k - 1][0], t[k][0]) for k in range(1, len(t))]
        print("%-6s %d  %s  gaps %s" % (sym, len(t), "; ".join(
            "%s %+.0f%% back %s" % (e[0][5:], 100 * (e[2] / e[1] - 1), e[4][5:]) for e in t), gaps))


if __name__ == "__main__":
    main()
