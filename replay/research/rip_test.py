"""The owner's "ripping" rule, tested on the saved 1-minute bars.

THE RIP (the owner, 2026-10-05): two green 1-minute candles in a row that
together add RIP_PCT or more, each on RIP_VOL_MULT times the volume of the
minutes before them, the second on more volume than the first - "the bars are
three, four, five times the size of the bars before them".

THE ENTRY (the owner's pattern): after the rip, the first red candle (or
reds); buy 1c over the last red's open when a later candle reaches it; stop
at the reds' low.

THE OUTCOME: a win if the price reaches the entry plus TARGET_R times the
risk before it touches the stop; a loss if the stop comes first (or both in
the same minute - a 1-minute bar cannot say which came first). Neither within
MAX_HOLD minutes: out at that minute's close.

What 1-minute bars cannot show: the 10-second chart, the tape, Level 2,
spoofed orders. Fills are at the trigger and the stop exactly unless --slip
is given. So this measures the screen and the candles alone.

  python replay/research/rip_test.py [--rip 5] [--vol 3] [--slip 0.5]
"""
import argparse
import csv
import glob
import json
import os
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

ROOT = os.path.join(os.path.dirname(__file__), "..", "data")


def load_day(day):
    out = {}
    for f in glob.glob(os.path.join(ROOT, day, "*.csv")):
        sym = os.path.basename(f)[:-4]
        bars = []
        for r in csv.DictReader(open(f)):
            bars.append((datetime.strptime(r["time"][:16], "%Y-%m-%dT%H:%M"),
                         float(r["open"]), float(r["high"]), float(r["low"]),
                         float(r["close"]), float(r["volume"])))
        out[sym] = sorted(bars)
    return out


def consecutive(bars, i, n):
    """bars[i-n+1 .. i] are n minutes in a row, with no gap."""
    return all(bars[k][0] - bars[k - 1][0] == timedelta(minutes=1)
               for k in range(i - n + 2, i + 1))


def trades_for(sym, bars, a):
    out = []
    i = a.before + 1
    entries = 0
    while i < len(bars) and entries < a.max_entries:
        t, o, h, l, c, v = bars[i]
        t1, o1, h1, l1, c1, v1 = bars[i - 1]
        base = [b[5] for b in bars[i - 1 - a.before:i - 1]]
        avg = sum(base) / len(base) if base else 0
        rip = (c1 > o1 and c > o and consecutive(bars, i, 2)
               and c / o1 - 1 >= a.rip / 100
               and avg > 0 and v1 >= a.vol * avg and v >= a.vol * avg and v > v1
               and min(v, v1) >= a.min_shares
               and min(v * c, v1 * c1) >= a.min_dollars
               and a.pmin <= c <= a.pmax)
        if not rip:
            i += 1
            continue
        # the pullback: the first red within PULLBACK_WAIT minutes, and any reds
        # straight after it
        j = next((k for k in range(i + 1, min(i + 1 + a.wait, len(bars)))
                  if bars[k][4] < bars[k][1]), None)
        if j is None:
            i += 1
            continue
        last_red = j
        while last_red + 1 < len(bars) and bars[last_red + 1][4] < bars[last_red + 1][1]:
            last_red += 1
        trigger = bars[last_red][1] + 0.01
        stop = min(b[3] for b in bars[j:last_red + 1])
        # the break: a later candle reaching the trigger within WAIT minutes
        k = next((m for m in range(last_red + 1, min(last_red + 1 + a.wait, len(bars)))
                  if bars[m][2] >= trigger), None)
        if k is None or trigger <= stop:
            i = last_red + 1
            continue
        entry = max(trigger, bars[k][1]) * (1 + a.slip / 100)
        risk = entry - stop
        target = entry + a.target * risk
        result, exit_px, m = None, None, k
        for m in range(k, min(k + a.hold, len(bars))):
            _, mo, mh, ml, mc, _ = bars[m]
            if ml <= stop:
                result, exit_px = "loss", stop * (1 - a.slip / 100)
                break
            if mh >= target and m > k:
                result, exit_px = "win", target
                break
        if result is None:
            result, exit_px = "time", bars[m][4] * (1 - a.slip / 100)
        out.append(dict(sym=sym, at=bars[k][0], entry=entry, stop=stop,
                        risk_pct=100 * risk / entry, result=result,
                        pct=100 * (exit_px / entry - 1), r=(exit_px - entry) / risk,
                        nth=entries + 1))
        entries += 1
        i = m + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rip", type=float, default=5.0, help="two greens add this %%")
    ap.add_argument("--vol", type=float, default=3.0, help="volume x the minutes before")
    ap.add_argument("--before", type=int, default=5, help="minutes the volume is compared to")
    ap.add_argument("--min-shares", type=float, default=30_000)
    ap.add_argument("--min-dollars", type=float, default=0,
                    help="each rip minute traded at least this many dollars - "
                         "the owner stays away from a thin stock, however fast")
    ap.add_argument("--wait", type=int, default=5, help="minutes to wait for the red, then the break")
    ap.add_argument("--target", type=float, default=2.0, help="win at this many times the risk")
    ap.add_argument("--hold", type=int, default=30, help="minutes before giving up")
    ap.add_argument("--slip", type=float, default=0.0, help="%% worse on every fill")
    ap.add_argument("--max-entries", type=int, default=2, help="per name per day")
    ap.add_argument("--max-float", type=float, default=0, help="shares; 0 = any")
    ap.add_argument("--pmin", type=float, default=1.0)
    ap.add_argument("--pmax", type=float, default=20.0)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    floats = {}
    fpath = os.path.join(os.path.dirname(__file__), "..", "..", "floats.csv")
    if a.max_float and os.path.exists(fpath):
        for r in csv.DictReader(open(fpath)):
            try:
                floats[r["symbol"]] = float(r["float_shares"])
            except (KeyError, ValueError):
                pass

    days = sorted(os.path.basename(d) for d in glob.glob(os.path.join(ROOT, "2026-*")))
    allt = []
    for day in days:
        data = load_day(day)
        dt_ = []
        for sym, bars in data.items():
            if a.max_float and floats.get(sym, 0) > a.max_float:
                continue
            dt_ += trades_for(sym, bars, a)
        allt += dt_
        w = sum(1 for t in dt_ if t["pct"] > 0)
        print("%s  %3d trades  %3d won  %+7.2f%% summed" % (
            day, len(dt_), w, sum(t["pct"] for t in dt_)))
        if a.list:
            for t in sorted(dt_, key=lambda t: t["at"]):
                print("   %s %-5s #%d entry %7.4f stop %7.4f (%.1f%% risk) %-4s %+6.2f%%" % (
                    (t["at"] - timedelta(hours=4)).strftime("%H:%M"), t["sym"], t["nth"],
                    t["entry"], t["stop"], t["risk_pct"], t["result"], t["pct"]))
    if not allt:
        print("no trades")
        return
    wins = [t for t in allt if t["pct"] > 0]
    loss = [t for t in allt if t["pct"] <= 0]
    print("ALL: %d trades, %d won (%.0f%%); average win %+.2f%%, average loss %+.2f%%; "
          "average trade %+.2f%% (%.2fR)" % (
              len(allt), len(wins), 100 * len(wins) / len(allt),
              statistics.mean(t["pct"] for t in wins) if wins else 0,
              statistics.mean(t["pct"] for t in loss) if loss else 0,
              statistics.mean(t["pct"] for t in allt),
              statistics.mean(t["r"] for t in allt)))
    by = defaultdict(list)
    for t in allt:
        by[t["nth"]].append(t)
    for n, ts in sorted(by.items()):
        print("  entry #%d: %d trades, %.0f%% won, average %+.2f%%" % (
            n, len(ts), 100 * sum(1 for t in ts if t["pct"] > 0) / len(ts),
            statistics.mean(t["pct"] for t in ts)))


if __name__ == "__main__":
    main()
