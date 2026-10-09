"""The runners (50c+ or 20%+ over the buy within the window): how deep did each
dip under the buy before it ran, how soon was the buy price back - what it would
take to stay in, or to get back in after a shake-out."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S, secsim_run as R

def dips(windows_dir, rts_path, bots=("v36", "v36b", "v37")):
    W = S.load_windows(windows_dir); rts = json.load(open(rts_path)); paths = {}
    out = []
    for bot in bots:
        for day in sorted(rts[bot]):
            for rt in rts[bot][day]:
                t0, px, sh = R.entries(rt, day)
                path = S.path_for(W, paths, day, rt["sym"], t0)
                if not path:
                    continue
                ev = path.ev[path.at(t0):]
                if not ev:
                    continue
                top_i = max(range(len(ev)), key=lambda i: ev[i][1])
                move = ev[top_i][1] - px
                if not (move >= 0.50 or move >= 0.20 * px):
                    continue
                low = min(e[1] for e in ev[:top_i + 1])
                low_t = next(e[0] for e in ev[:top_i + 1] if e[1] == low)
                back = next((e[0] for e in ev if e[0] > low_t and e[1] >= px), None)
                out.append(dict(bot=bot, day=day, t=rt["open"], sym=rt["sym"], px=px, sh=sh, move=move,
                                dip=px - low, dip_pct=(px - low) / px, dip_s=low_t - t0,
                                back_s=(back - low_t) if back else None, top_s=ev[top_i][0] - t0, live=rt["pl"]))
    return out

if __name__ == "__main__":
    rows = dips(sys.argv[1], sys.argv[2])
    for bot in ("v36", "v36b", "v37"):
        r = [x for x in rows if x["bot"] == bot]
        if not r:
            continue
        print("\n%s - %d runners: how far each fell under the buy before its top" % (bot, len(r)))
        buckets = [("held within 5c", lambda x: x["dip"] < 0.05), ("5-10c", lambda x: 0.05 <= x["dip"] < 0.10),
                   ("10-20c", lambda x: 0.10 <= x["dip"] < 0.20), ("20c+", lambda x: x["dip"] >= 0.20)]
        for name, f in buckets:
            g = [x for x in r if f(x)]
            backs = sorted(x["back_s"] for x in g if x["back_s"] is not None)
            print("   %-15s %3d | %3d back over the buy price, median %s s after the low | live %+.0f" % (
                name, len(g), len(backs), "%.0f" % backs[len(backs) // 2] if backs else "-", sum(x["live"] for x in g)))
    json.dump(rows, open(os.path.join(os.path.dirname(sys.argv[2]), "runner_dips.json"), "w"), indent=0)


def reclaim_signal(path, after, level, hold=3.0):
    """The first moment after `after` that the price is at or over `level` and
    stays there `hold` seconds (no print under it): (time, fill at the ask
    BUY_LAG later), the fill no more than the ask at that moment + 20c."""
    ev = path.ev
    i = path.at(after)
    while i < len(ev):
        t, p, b, a = ev[i]
        if p >= level - 1e-9:
            j, ok = i, True
            while j < len(ev) and ev[j][0] <= t + hold:
                if ev[j][1] < level - 1e-9:
                    ok = False
                    break
                j += 1
            if ok and j < len(ev):
                a0 = path.ask_at(t + hold)
                fill = path.ask_at(t + hold + S.BUY_LAG)
                if fill <= a0 + 0.20 + 1e-9:
                    return t + hold + S.BUY_LAG, fill
                i = j
                continue
            i = j if not ok else i + 1
            continue
        i += 1
    return None


def run_reclaim(path, t0, px, sh, stop, line, plus=0.02, hold=3.0, max_buys=20):
    """The buy, then after each sale: back in once the price is over the FIRST
    buy's price + plus and holds there `hold` seconds; same dollars, same rule."""
    out, dollars, t, fill, n = [], px * sh, t0, px, sh
    for _ in range(max_buys):
        te, xp, why, best = S.run(path, t, fill, n, stop, line)
        out.append((xp - fill) * n)
        if why == "open":
            break
        sig = reclaim_signal(path, te + S.SELL_LAG, px + plus, hold)
        if not sig:
            break
        t, fill = sig
        n = int(dollars / fill)
    return out


def compare(windows_dir, rts_path, bots=("v36", "v36b", "v37")):
    W = S.load_windows(windows_dir); rts = json.load(open(rts_path)); paths = {}
    rules = [("5c cut", R.STOPS["10c"], S.cut(0.05)), ("v36 now (10c, 30% from +30c)", R.STOPS["10c"], S.furious())]
    for bot in bots:
        acc = {}
        for day in sorted(rts[bot]):
            seen = set()
            for rt in rts[bot][day]:
                t0, px, sh = R.entries(rt, day)
                path = S.path_for(W, paths, day, rt["sym"], t0)
                if not path or (day, rt["sym"], path.start) in seen:
                    continue
                seen.add((day, rt["sym"], path.start))
                for name, st, ln in rules:
                    one = R.simulate(path, t0, px, sh, st, ln)
                    hod = R.simulate(path, t0, px, sh, st, ln, rebuy=True)
                    rec = run_reclaim(path, t0, px, sh, st, ln)
                    a = acc.setdefault(name, [0, 0.0, 0, 0.0, 0, 0.0, 0, 0])
                    a[0] += 1; a[1] += one[0][0]
                    a[2] += len(hod); a[3] += sum(x[0] for x in hod)
                    a[4] += len(rec); a[5] += sum(rec); a[6] += sum(x > 0 for x in rec)
        print("\n%s - the first buy of each stretch (%d):" % (bot, next(iter(acc.values()))[0]))
        for name, a in acc.items():
            print("   %-30s one buy %+7.0f | back in over the high + 5c: %3d buys %+7.0f | back in over the buy + 2c, held 3s: %3d buys (%2d won) %+7.0f" % (
                name, a[1], a[2], a[3], a[4], a[6], a[5]))
