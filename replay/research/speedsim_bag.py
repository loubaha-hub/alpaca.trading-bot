"""How much of each run the speed strategy bagged, and why it lost (the owner,
10-09 ~2pm: "does the strategy catch those and does it keep them? ... by
stocks, how much of the run we kept").

python3 speedsim_bag.py <windows dir> [min run %, default 40] [why SYM,SYM...]

Per window (the read has gaps between windows), the run = the biggest rise in
it: a low to the highest price after it. A trade's share of the run = its exit minus its
average buy over (high - low), in cents a share, whatever the size. "net" =
all the stock's trades added that way (the losers too); "best" = the best
one alone. Sessions by the run's low (PRE 4:00-9:30, RTH 9:30-16:00, AFTER).
Settings: A = 3c stop, half from +10c (the table so far); B = 10% stop, half
from +10% of the price (the best mix found, speedsim_stops.py)."""
import os, sys
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
from speedsim_study import session, SESSIONS

hm = lambda t: datetime.fromtimestamp(t, S.ET).strftime("%H:%M:%S")


def trades(r, p, st, setting):
    if setting == "A":
        return Q.play_ladder_hod(p, r, st, 4000, 0.03, 0.10)
    px = next((x[4] for x in r["S"] if x[4]), 1.0)
    return Q.play_ladder_hod(p, r, st, 4000, 0.0, 0.10 * px, mid_stop=False, stop_pct=0.10)


def price_after(p, t, secs):
    """(max, last) of the prints from t to t + secs."""
    i = p.at(t)
    seg = [e[1] for e in p.ev[i:] if e[0] <= t + secs]
    return (max(seg), seg[-1]) if seg else (None, None)


def main():
    W = S.load_windows(sys.argv[1])
    min_run = float(sys.argv[2]) / 100 if len(sys.argv) > 2 else 0.40
    why = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else set()
    by = defaultdict(list)                     # one window at a time: the read has gaps between them
    for r in (r for l in W.values() for r in l):
        by[(r["day"], r["sym"], r["start"])].append(r)
    rows = []
    for (day, sym, _), recs in sorted(by.items()):
        px = sorted((r["start"] + x[0], x[4]) for r in recs for x in r["S"] if x[4])
        if not px:
            continue
        lo_i = min(range(len(px)), key=lambda i: px[i][1])
        lo_t, lo = px[lo_i]
        hi_t, hi = max(px[lo_i:], key=lambda x: x[1])
        # the biggest rise may start after an earlier, lower low: take the best pair
        best = (hi / lo, lo_t, lo, hi_t, hi)
        run_lo = px[0]
        for t, v in px:
            if v < run_lo[1]:
                run_lo = (t, v)
            if v / run_lo[1] > best[0]:
                best = (v / run_lo[1], run_lo[0], run_lo[1], t, v)
        rise, lo_t, lo, hi_t, hi = best
        if rise - 1 < min_run:
            continue
        out = {}
        for setting in ("A", "B"):
            trs = []
            for r in recs:
                p, st = S.Path(r), Q.speed_state(r)
                for tr in trades(r, p, st, setting):
                    t_in, fill, w, bst, pl, sh, avg, adds, te = tr
                    xp = avg + pl / sh if sh else fill
                    trs.append(dict(t_in=t_in, fill=fill, avg=avg, xp=xp, why=w, best=bst, pl=pl, te=te,
                                    adds=adds, p=p))
            inrun = [x for x in trs if lo_t - 60 <= x["t_in"] <= hi_t]
            net = sum(x["xp"] - x["avg"] for x in trs)
            bestt = max(trs, key=lambda x: x["xp"] - x["avg"]) if trs else None
            out[setting] = (trs, inrun, net, bestt)
        rows.append((day, sym, session(lo_t), lo_t, lo, hi_t, hi, rise, out, recs))
    span = lambda recs: " ".join("%s-%s" % (hm(r["start"])[:5], hm(r["end"])[:5]) for r in sorted(recs, key=lambda r: r["start"]))
    print("HOW MUCH OF EACH RUN WAS BAGGED - runs of %.0f%%+ inside the read (only the windows read around the" % (100 * min_run))
    print("bots' buys, 10-06..10-08: slices of the runs). Kept = cents a share over the run's cents.")
    print("A = 3c stop, half from +10c   B = 10% stop, half from +10%\n")
    for sess in SESSIONS:
        part = [x for x in rows if x[2] == sess]
        if not part:
            continue
        print("== %s ==" % {"PRE": "PREMARKET 4:00-9:30", "RTH": "REGULAR HOURS 9:30-4:00", "AFTER": "AFTER HOURS 4:00-8:00pm"}[sess])
        print("  %-5s %-5s %-17s %-17s %5s | %-3s %5s %6s %-27s %6s %8s" % (
            "day", "sym", "run low", "run high", "run%", "set", "trades", "in run", "best trade (in -> out)", "kept", "P/L"))
        for day, sym, _, lo_t, lo, hi_t, hi, rise, out, recs in part:
            for setting in ("A", "B"):
                trs, inrun, net, bt = out[setting]
                best_s = ("%s %.2f -> %.2f %4.0f%%" % (hm(bt["t_in"])[:5], bt["avg"], bt["xp"],
                                                       100 * (bt["xp"] - bt["avg"]) / (hi - lo))) if bt else "-"
                print("  %-5s %-5s %-17s %-17s %4.0f%% | %-3s %5d %6d %-27s %5.0f%% %+8.0f" % (
                    day[5:] if setting == "A" else "", sym if setting == "A" else "",
                    ("$%.2f %s" % (lo, hm(lo_t))) if setting == "A" else "",
                    ("$%.2f %s" % (hi, hm(hi_t))) if setting == "A" else "",
                    100 * (rise - 1) if setting == "A" else 0, setting, len(trs), len(inrun), best_s,
                    100 * net / (hi - lo), sum(x["pl"] for x in trs)))
            print("  %43s read: %s" % ("", span(recs)))
        print()
    if not why:
        return
    print("WHY IT LOST - every trade, setting A (3c stop, half from +10c)")
    print("  paid = the fill over the last print at the signal; spread at the fill; out after s seconds;")
    print("  then: the highest print in the 5 minutes after the sale, and where it was 5 minutes later\n")
    for day, sym, _, lo_t, lo, hi_t, hi, rise, out, recs in rows:
        if sym not in why:
            continue
        trs = out["A"][0]
        print("%s %s  run $%.2f %s -> $%.2f %s (+%.0f%%), %d trades, P/L %+.0f" % (
            day, sym, lo, hm(lo_t), hi, hm(hi_t), 100 * (rise - 1), len(trs), sum(x["pl"] for x in trs)))
        kinds = defaultdict(int)
        for x in trs:
            p = x["p"]
            sig_px = p.ev[max(0, p.at(x["t_in"] - S.BUY_LAG) - 1)][1]
            bid, ask = p.bid_at(x["t_in"]), p.ask_at(x["t_in"])
            mx, last = price_after(p, x["te"], 300)
            held = x["te"] - x["t_in"]
            k = ("top of the burst (never over the fill)" if x["best"] <= x["fill"] + 1e-9 else
                 "won" if x["pl"] > 0 else "rose, then fell back to the stop")
            if x["why"] == "stop" and mx and mx > x["fill"] * 1.10:
                k += "; the run went on (+10% over the fill within 5 min)"
            kinds[k] += 1
            print("  %s sig %.3f fill %.3f paid %+.3f spread %.3f | best %.3f out %s %.3f after %4.0fs %+7.1f | 5 min: high %s now %s" % (
                hm(x["t_in"]), sig_px, x["fill"], x["fill"] - sig_px, (ask - bid) if bid and ask else 0,
                x["best"], x["why"], x["xp"], held, x["pl"],
                "%.2f" % mx if mx else "-", "%.2f" % last if last else "-"))
        for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
            print("    %2d x %s" % (n, k))
        print()


if __name__ == "__main__":
    main()
