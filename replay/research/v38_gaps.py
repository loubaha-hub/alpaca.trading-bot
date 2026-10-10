"""The owner's four points on v38's speed test (10-09 night), on the full read.

  1. the red candle: the last closed 1-minute candle not red - "a bad omen; a
     pickup after it is rare, but it happens". Test: the check on (as tested)
     and off - the losers it removes and the good moves it blocks.
  2. the stock waking up: no shares in the minute before means no volume
     ratio, so no signal today. Test: no volume the minute before counts as
     the full ratio (the cap, 30); the move (3%+) and $250k still needed.
  3. the re-entry level - "you have to have a level before it", not a clock:
     a buy after v38 sold the stock needs a price over the highest price
     SINCE V38'S LAST SALE of it (instead of over the day's high). Between two
     windows of the read the gap's high comes from the minute bars where saved,
     else the day's high before the later window (the stricter level).
  4. the chug - "check, check, check, going slowly": a climb that never makes a
     3% minute on rising volume. A second signal: over the last N closed
     1-minute candles the price up X% or more, every one of them $250k+, the
     last one not red, and the price now over all their highs (a new high of
     the climb). Its floor: 3c (as speed buys), or the low of the last closed
     candle (at most 10% under the fill).
  Also: the checks the bot's furious buy already has and a v38 built on it
  would inherit - no buy with a spread over 10c, none unless up over 5 seconds.

Everything else as v38 with the trailing thirds ($7,500 full). Each variant
against v38 as tested, both sides: the trades it adds (and their P/L) and the
trades it drops (and theirs). Every table by session.

python3 v38_gaps.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
import v38_final as F
from speedsim_study import session, SESSIONS

GANG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"))


def minutes(rec):
    """{minute: [open, high, low, close, dollars]} from the read's second rows."""
    m = {}
    for r in rec["S"]:
        if not r[1]:
            continue
        mm = (rec["start"] + r[0]) // 60
        x = m.get(mm)
        if x is None:
            m[mm] = [r[1], r[2], r[3], r[4], r[4] * r[5]]
        else:
            x[1], x[2], x[3], x[4] = max(x[1], r[2]), min(x[2], r[3]), r[4], x[4] + r[4] * r[5]
    return m


def signals(rec, red=True, wake=False, chug=None, checks=False, breath=None):
    """{second: (speed?, chug?, last closed candle's low, the breather's floor or None)}"""
    rows = {r[0]: r for r in rec["S"] if r[1]}
    if not rows:
        return {}
    last = max(rows)
    close, spread = {}, {}
    vol, dol = [0] * (last + 2), [0.0] * (last + 2)
    px, sp = None, None
    for k in range(last + 1):
        r = rows.get(k)
        if r:
            px = r[4]
        q = r if r else None
        if q and q[7] and q[8]:
            sp = q[8] - q[7]
        close[k], spread[k] = px, sp
        vol[k + 1] = vol[k] + (r[5] if r else 0)
        dol[k + 1] = dol[k] + ((r[4] * r[5]) if r else 0.0)
    mins = minutes(rec)
    out = {}
    for k in range(last + 1):
        m = (rec["start"] + k) // 60
        bar = mins.get(m - 1)
        is_red = bar is not None and bar[3] < bar[0]
        low = bar[2] if bar else None
        sp_on = False
        if k >= 120:
            p2, p1 = close[k], close[k - 60]
            if p2 and p1:
                v2 = vol[k + 1] - vol[k - 59]
                v1 = vol[k - 59] - vol[k - 119]
                move = p2 / p1 - 1
                ratio = (v2 / v1) if v1 > 0 else (Q.VOL_CAP if wake and v2 > 0 else 0.0)
                if move >= Q.MOVE_MIN and ratio > 0:
                    sp_on = (move * min(ratio, Q.VOL_CAP) >= Q.SPEED
                             and dol[k + 1] - dol[k - 59] >= Q.DOLLARS_MIN and not (red and is_red))
        ch_on = False
        if chug and close[k]:
            n, x = chug[0], chug[1]
            bars = [mins.get(m - i) for i in range(n, 0, -1)]
            if len(chug) > 2:                      # the owner's (10-10): N minutes, an average of
                had = [b for b in bars if b]       # $250k a minute (a quiet minute allowed)
                ch_on = (k >= 60 * n and len(had) >= 2 and not is_red and bars[-1] is not None
                         and bars[-1][3] >= had[0][0] * (1 + x)
                         and sum(b[4] for b in had) >= n * Q.DOLLARS_MIN
                         and close[k] > max(b[1] for b in had) + 1e-9)
            elif all(bars) and not is_red:
                ch_on = (bars[-1][3] >= bars[0][0] * (1 + x)
                         and all(b[4] >= Q.DOLLARS_MIN for b in bars)
                         and close[k] > max(b[1] for b in bars) + 1e-9)
        br_low = None
        if breath and close[k] and bar is not None and is_red and mins.get(m):
            n, run_min, back = breath                # the owner's breather (10-10): after a run,
            had = [b for b in (mins.get(m - 1 - i) for i in range(n, 0, -1)) if b]
            if had:                                  # the first red candle (the breath), then
                lo = min(b[2] for b in had)          # 1c over its open as the next one goes green
                hi = max(max(b[1] for b in had), bar[1])
                if (hi >= lo * (1 + run_min) and hi - bar[2] <= back * (hi - lo)
                        and sum(b[4] for b in had) >= n * Q.DOLLARS_MIN
                        and close[k] >= bar[0] + 0.01 - 1e-9 and close[k] > mins[m][0] + 1e-9):
                    br_low = bar[2]
        if checks and (sp_on or ch_on or br_low):
            up5 = k >= 5 and close[k - 5] and close[k] > close[k - 5]
            if not up5 or spread[k] is None or spread[k] > 0.10 + 1e-9:
                sp_on = ch_on = False
                br_low = None
        out[k] = (sp_on, ch_on, low, br_low)
    return out


def gap_high(bars, day, sym, t0, t1):
    rows = bars.get(day, {}).get(sym)
    if not rows:
        return None
    hs = [r[2] for r in rows if t0 <= datetime.fromisoformat(r[0].replace("Z", "+00:00")).timestamp() < t1]
    return max(hs) if hs else 0.0


def play(recs, bars, level="day", red=True, wake=False, chug=None, chug_floor="3c", checks=False, gaps=None,
         limit=None, misses=None, breath=None):
    """[(rec, t_in, P/L, kind, t_out)] - one stock's day, the first buy free."""
    out, first = [], True
    sold_at, since, known_to = None, None, None    # v38's last sale, the high since it, read up to
    exit_px = None                                 # the price v38 last sold it at (level="exit")
    for r in recs:
        p, st = S.Path(r), signals(r, red, wake, chug, checks, breath)
        used = set()                               # one breather buy per red candle
        hi = {x[0]: x[2] for x in r["S"] if x[2]}
        after, top = -1.0, r.get("hod_before")
        if since is not None and known_to is not None and known_to < r["start"]:
            gh = gap_high(bars, r["day"], r["sym"], known_to, r["start"])
            if gh is None:                         # the gap's high not saved: the day's high
                gh = r.get("hod_before") or 0.0    # before this window (the stricter level)
                if gaps is not None:
                    gaps.append((r["day"], r["sym"]))
            since = max(since, gh)
        for k in sorted(st):
            sp, ch, low, br = st[k]
            h = hi.get(k)
            t = r["start"] + k + 0.99
            prev, prev_since = top, since
            if h is not None:
                top = h if top is None else max(top, h)
                if since is not None and t > sold_at:
                    since = max(since, h)
            if t <= after or not (sp or ch or br):
                continue
            only_br = br and not (sp or ch)        # the breather has its own level: the run and
            mm = (r["start"] + k) // 60            # its pause - no re-entry level
            if only_br and mm in used:
                continue
            if not first and not only_br:
                if h is None:
                    continue
                if level == "day" and (prev is None or h <= prev + 1e-9):
                    continue
                if level == "sale" and (prev_since is None or h <= prev_since + 1e-9):
                    continue
                if level == "exit" and (exit_px is None or h <= exit_px + 1e-9):
                    continue
            t_in = t + S.BUY_LAG
            if t_in >= p.end - 5:
                break
            fill = p.ask_at(t_in)
            if not fill or fill <= 0:
                continue
            if limit is not None:                  # a real limit: the ask at the decision + `limit`;
                a0 = p.ask_at(t)                   # the ask a second later past it - no fill, the
                cap = a0 * (1 + float(limit[:-1]) / 100) if isinstance(limit, str) else a0 + limit
                if fill > cap + 1e-9:              # next signal tries again
                    if misses is not None:
                        misses.append((r["day"], r["sym"], t))
                    continue
            under = 0.03
            if not sp and ch and chug_floor == "candle" and low:
                under = min(max(fill - low, 0.03), 0.10 * fill)
            if only_br:                            # the floor: the red candle's low (at most 10%)
                under = min(max(fill - br, 0.03), 0.10 * fill)
                used.add(mm)
            te, pl, why, best, sh, avg, adds = Q.run_ladder(p, t_in, fill, F.FULL, under, 0.10, tiers=F.TIERS)
            out.append((r, t_in, pl, "speed" if sp else "chug" if ch else "breath", te))
            after, first = te + S.SELL_LAG, False
            sold_at, since = te, 0.0               # the high since this sale starts now
            exit_px = p.bid_at(te + S.SELL_LAG)
        known_to = r["end"]
    return out


VARIANTS = (
    ("v38 as tested", dict()),
    ("+ the bot's buy checks (spread 10c, up 5s)", dict(checks=True)),
    ("1. red-candle check OFF", dict(red=False)),
    ("2. waking up (no volume before = full ratio)", dict(wake=True)),
    ("3. re-entry over the high since the last sale", dict(level="sale")),
    ("   re-entry over the last sale's price", dict(level="exit")),
    ("   re-entry with no level (speed alone)", dict(level="none")),
    ("4. chug 5 min +10%, 3c floor", dict(chug=(5, 0.10))),
    ("4. chug 5 min +10%, candle-low floor", dict(chug=(5, 0.10), chug_floor="candle")),
    ("4. chug 3 min +6%, candle-low floor", dict(chug=(3, 0.06), chug_floor="candle")),
    ("4. chug 5 min +15%, candle-low floor", dict(chug=(5, 0.15), chug_floor="candle")),
    ("4. chug 10 min +20%, candle-low floor", dict(chug=(10, 0.20), chug_floor="candle")),
    ("2+3 waking up + the since-sale level", dict(wake=True, level="sale")),
)


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: {s: v for s, v in json.load(open(os.path.join(sys.argv[3], f))).items()}
            for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    print("v38's SPEED TEST - THE OWNER'S FOUR POINTS (full read, trailing thirds, $7,500 full)")
    print("a cell: trades, won, P/L; 'adds' / 'drops' = the trades a variant takes that v38 as tested does not, and the reverse\n")
    print("%-46s %4s %3s " % ("", "n", "won") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %8s | %16s %16s" % ("TOTAL", "PRE", "RTH", "AFTER", "gangbstr", "adds", "drops"))
    base_keys = None
    for name, kw in VARIANTS:
        gaps = []
        xs = [x for k in sorted(by) for x in play(by[k], bars, gaps=gaps, **kw)]
        keys = {(x[0]["day"], x[0]["sym"], round(x[1])): x for x in xs}
        if base_keys is None:
            base_keys = keys
        add = [x for kk, x in keys.items() if kk not in base_keys]
        drop = [x for kk, x in base_keys.items() if kk not in keys]
        per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        gang = sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) in GANG and x[2] > 0)
        print("%-46s %4d %3d " % (name, len(xs), sum(x[2] > 0 for x in xs)) +
              " ".join("%+7.0f" % v for v in per) +
              " %+8.0f | %+7.0f %+7.0f %+7.0f | %+8.0f | %3d %3d %+8.0f %3d %3d %+8.0f" % (
                  sum(per), *ses, gang, len(add), sum(x[2] > 0 for x in add), sum(x[2] for x in add),
                  len(drop), sum(x[2] > 0 for x in drop), sum(x[2] for x in drop)))
        if kw.get("chug"):
            c = [x for x in xs if x[3] == "chug"]
            print("%-46s %4d %3d  chug buys: %+.0f; by session %s" % (
                "", len(c), sum(x[2] > 0 for x in c), sum(x[2] for x in c),
                " ".join("%s %+.0f" % (s, sum(x[2] for x in c if session(x[1]) == s)) for s in SESSIONS)))
        if gaps and kw.get("level") == "sale":
            print("%-46s      (%d window gaps with no saved bars: the day's high used - the stricter level)" % ("", len(gaps)))
        big = sorted(add, key=lambda x: -x[2])[:3]
        if big and big[0][2] > 300:
            print("%-46s      biggest adds: %s" % ("", ", ".join(
                "%s %s %s %+.0f" % (x[0]["day"][5:], x[0]["sym"], datetime.fromtimestamp(x[1], S.ET).strftime("%H:%M"), x[2])
                for x in big if x[2] > 300)))


if __name__ == "__main__":
    main()
