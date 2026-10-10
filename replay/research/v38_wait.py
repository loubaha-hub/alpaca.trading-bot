"""Wait before buying? (the owner, 10-10: "if the speed picks up, the stock
starts to go up ... in two seconds 80 or 90 percent of the stocks with speed
will have increased in price" - so a wait may work against us).

1. For every first buy of v38 proposed (no re-entry level, the ask + the
   speed's scale, the bot's buy checks): the ask 2 / 3 / 5 seconds after the
   signal against the ask it bought at (1 second after) - how often higher,
   how often lower, by how much; for the trades that won and those that lost.
2. A plain wait (the buy goes out 2 / 3 s after the signal, whatever happened)
   against a confirmation (the speed still on 1 / 2 / 3 s later and the price
   no lower than at the signal - else no buy). All day and premarket only;
   without BIYA, without the top three; the 39 (22) runs of 40%+.

python3 v38_wait.py <new windows> <old windows> <old minute bars>"""
import json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
import v38_gaps as G
from speedsim_giveback import run_of
from speedsim_study import session, SESSIONS

TOP3 = (("2026-10-07", "BIYA"), ("2026-10-06", "FRGT"), ("2026-10-07", "SBFM"))
BASE = dict(level="none", checks=True, limit="scale")


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    xs = [x for k in sorted(by) for x in G.play(by[k], bars, **BASE)]
    print("1. THE ASK AFTER THE SIGNAL - v38 proposed's %d first buys (bought at the ask 1s after the signal)" % len(xs))
    for label, sel in (("all buys", lambda x: True), ("the buys that won $100+", lambda x: x[2] >= 100),
                       ("the buys that lost", lambda x: x[2] <= 0)):
        ys = [x for x in xs if sel(x)]
        cells = []
        for d in (2, 3, 5):
            ch = []
            for x in ys:
                p = S.Path(x[0])
                a1, ad = p.ask_at(x[1]), p.ask_at(x[1] + d - 1)
                if a1 and ad:
                    ch.append(ad / a1 - 1)
            up = sum(c > 1e-9 for c in ch)
            dn = sum(c < -1e-9 for c in ch)
            cells.append("%ds: higher %3.0f%% lower %3.0f%% same %3.0f%%, median %+.2f%% mean %+.2f%%" % (
                d, 100 * up / len(ch), 100 * dn / len(ch), 100 * (len(ch) - up - dn) / len(ch),
                100 * st.median(ch), 100 * st.mean(ch)))
        print("  %-26s %3d | %s" % (label, len(ys), " | ".join(cells)))
    lag0 = S.BUY_LAG
    cache = {}
    runs_all = [(r, rn) for k in by for r in by[k] for rn in [run_of(r)] if rn and rn[0] - 1 >= 0.40]
    for only in (None, "PRE"):
        runs = [(r, rn) for r, rn in runs_all if not only or session(rn[1]) == only]
        print("\n2. WAIT OR CONFIRM - %s" % ("ALL DAY" if not only else "PREMARKET ONLY"))
        print("  %-52s %4s %8s %8s %8s | %7s %7s %7s | %6s | %s" % ("", "n", "TOTAL", "no BIYA", "no top3",
              "PRE", "RTH", "AFTER", "a trade", "%d runs: made money / kept median" % len(runs)))
        for name, kw, lag in (("buy 1s after the signal (proposed)", dict(), 1.0),
                              ("a plain wait: the buy 2s after", dict(), 2.0),
                              ("a plain wait: the buy 3s after", dict(), 3.0),
                              ("confirm: the speed still on 1s later, price no lower", dict(confirm=1), 1.0),
                              ("confirm: the speed still on 2s later, price no lower", dict(confirm=2), 1.0),
                              ("confirm: the speed still on 3s later, price no lower", dict(confirm=3), 1.0)):
            if name not in cache:                  # the premarket trades are the same as the day's
                S.BUY_LAG = lag
                cache[name] = [x for k in sorted(by) for x in G.play(by[k], bars, **BASE, **kw)]
                S.BUY_LAG = lag0
            ys = cache[name]
            if only:
                ys = [x for x in ys if session(x[1]) == only]
            nob = [x for x in ys if (x[0]["day"], x[0]["sym"]) != TOP3[0]]
            no3 = [x for x in ys if (x[0]["day"], x[0]["sym"]) not in TOP3]
            ses = [sum(x[2] for x in ys if session(x[1]) == s) for s in SESSIONS]
            made, kept = 0, []
            for r, rn in runs:
                zs = [x for x in ys if x[0] is r]
                made += sum(x[2] for x in zs) > 0
                kept.append(sum(x[2] / x[5] for x in zs if x[5]) / (rn[4] - rn[2]))
            print("  %-52s %4d %+8.0f %+8.0f %+8.0f | %+7.0f %+7.0f %+7.0f | %+6.1f | %2d / %+4.0f%%" % (
                name, len(ys), sum(x[2] for x in ys), sum(x[2] for x in nob), sum(x[2] for x in no3), *ses,
                sum(x[2] for x in nob) / max(1, len(nob)), made, 100 * st.median(kept)))


if __name__ == "__main__":
    main()
