"""The three-day test: every live entry of v36, v36b and v37 on 10-06/07/08,
replayed second by second (secsim) under each exit rule - the same entry, the
same size, only the exit differs. Optional: re-entries over the day's high + 5c.

python3 secsim_run.py <windows dir (secread.py output)> <roundtrips.json> [rebuy]

An entry is the first buy of a round trip plus the buys within ENTRY_SECONDS of
it (v37 buys in pieces), at their average price. Adds later in the trade are
not replayed; "live" is the whole round trip's real P/L."""
import json, sys, os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S

ENTRY_SECONDS = 3

STOPS = {
    "10c": lambda f: max(f - 0.10, f * 0.92),       # v36's furious stop (10c, at most 8%)
    "3%": S.stop_pct(0.03),                         # v36b's first stop, about
    "15c": lambda f: max(f - 0.15, f * 0.90),
}
LINES = {
    "5c cut": S.cut(0.05),
    "10c cut": S.cut(0.10),
    "tiers": S.tiers(),
    "tiers 10c lead": S.tiers(lead=0.10),
    "furious 30c/30%": S.furious(),
    "stop only": lambda f, b: -1.0,
}


def entries(rt, day):
    """(t0, avg fill, shares) of the entry, the live P/L."""
    t0 = S.ts(day, rt["open"])
    first = [(q, p) for t, q, p in rt["buys"] if S.ts(day, t) - t0 <= ENTRY_SECONDS]
    sh = sum(q for q, _ in first)
    px = sum(q * p for q, p in first) / sh
    return t0, px, sh


def line_wait(path, t0, px, below=0.03, past=0.05):
    """An entry within `below` under a whole / half dollar (or under `past` over
    it) waits for a print at the line + past: (t, fill) at the ask BUY_LAG
    later, None if it never comes; the entry as it was when not at a line."""
    lvl = int((px + below) * 2 + 1e-9) / 2.0
    if not (lvl - below - 1e-9 <= px < lvl + past - 1e-9):
        return t0, px
    sig = S.rebuy_signal(path, t0 - 1.0, lvl - past, plus=2 * past)   # a print at lvl + past
    return sig


def simulate(path, t0, px, sh, stop, line, rebuy=False, end=None):
    """P/L of one entry (and, with rebuy, of every re-entry after it in the
    window: over the high so far + 5c, same dollars, same rule)."""
    out = []
    dollars = px * sh
    t, fill, n = t0, px, sh
    while True:
        te, xp, why, best = S.run(path, t, fill, n, stop, line)
        out.append(((xp - fill) * n, why, fill, xp, best))
        if not rebuy or why == "open" or (end and te >= end):
            break
        hod = max([e[1] for e in path.ev[:path.at(te + 1e-6)]] or [best])
        sig = S.rebuy_signal(path, te + S.SELL_LAG, hod)
        if not sig or (end and sig[0] >= end):
            break
        t, fill = sig
        n = int(dollars / fill)
    return out


def main():
    windows = S.load_windows(sys.argv[1])
    rts = json.load(open(sys.argv[2]))
    rebuy = "rebuy" in sys.argv[3:]
    paths = {}
    combos = [(s, l) for s in STOPS for l in LINES]
    for bot in sorted(rts):
        res = {c: [] for c in combos}
        live, missing, n = [], 0, 0
        per_day = defaultdict(lambda: defaultdict(float))
        runners = []                           # (entry, the move after it, P/L by rule)
        solo = defaultdict(float); solo_n = [0, 0]   # trades with no adds: live vs rules, like for like
        for day in sorted(rts[bot]):
            done_windows = set()
            for rt in rts[bot][day]:
                if rt["pl"] is None:
                    continue
                t0, px, sh = entries(rt, day)
                path = S.path_for(windows, paths, day, rt["sym"], t0)
                if not path:
                    missing += 1
                    continue
                if rebuy:                      # the rule's own re-entries replace the live ones
                    key = (day, rt["sym"], path.start)
                    if key in done_windows:
                        continue
                    done_windows.add(key)
                n += 1
                live.append(rt["pl"])
                per_day[day]["live"] += rt["pl"]
                after = [e[1] for e in path.ev[path.at(t0):]]
                move = (max(after) - px) if after else 0.0
                got = {}
                for c in combos:
                    r = simulate(path, t0, px, sh, STOPS[c[0]], LINES[c[1]], rebuy)
                    res[c].extend(x[0] for x in r)
                    per_day[day][c] += sum(x[0] for x in r)
                    got[c] = sum(x[0] for x in r)
                adds = [b for b in rt["buys"] if S.ts(day, b[0]) - t0 > ENTRY_SECONDS]
                if not adds and not rebuy:
                    solo_n[0] += 1; solo_n[1] += rt["pl"] > 0
                    solo["live"] += rt["pl"]
                    for c in combos:
                        solo[c] += got[c]
                if move >= 0.50 or move >= 0.20 * px:
                    runners.append((day, rt["open"], rt["sym"], px, sh, move, rt["pl"], got))
        print("\n=== %s: %d entries%s (%d without data) - live %+.2f, %d won ===" % (
            bot, n, " (first per window, then the rule's re-entries)" if rebuy else "", missing,
            sum(live), sum(x > 0 for x in live)))
        print("  %-5s %-17s %10s %8s %6s %9s   %s" % ("stop", "sell line", "P/L", "entries", "won", "per entry",
                                                     "  ".join(sorted(per_day))))
        for c in combos:
            v = res[c]
            print("  %-5s %-17s %+10.2f %8d %6d %+9.2f   %s" % (
                c[0], c[1], sum(v), len(v), sum(x > 0 for x in v), sum(v) / max(1, len(v)),
                "  ".join("%+9.2f" % per_day[d][c] for d in sorted(per_day))))
        print("  %-23s %+10.2f %8d %6d %+9.2f   %s" % (
            "live", sum(live), len(live), sum(x > 0 for x in live), sum(live) / max(1, len(live)),
            "  ".join("%+9.2f" % per_day[d]["live"] for d in sorted(per_day))))
        if solo_n[0]:
            print("  LIKE FOR LIKE - the %d trades with no adds (live won %d): live %+.2f | %s" % (
                solo_n[0], solo_n[1], solo["live"], " | ".join("%s %s %+.2f" % (c[0], c[1], solo[c]) for c in combos
                                                         if c[0] in ("10c", "3%"))))
        show = [("10c", "5c cut"), ("10c", "tiers"), ("10c", "furious 30c/30%"), ("3%", "furious 30c/30%"), ("15c", "tiers 10c lead")]
        print("  RUNNERS (up 50c or 20%% after the buy, within the window): %d entries; the move x shares = $%.0f" % (
            len(runners), sum(r[5] * r[4] for r in runners)))
        print("    %-10s %-8s %-5s %7s %6s %9s | %s" % ("day", "time", "sym", "buy", "move", "live", " | ".join("%s %s" % c for c in show)))
        for r in runners:
            print("    %-10s %-8s %-5s %7.3f %+6.2f %+9.2f | %s" % (r[0], r[1], r[2], r[3], r[5], r[6],
                  " | ".join("%+9.2f" % r[7][c] for c in show)))


if __name__ == "__main__":
    main()
