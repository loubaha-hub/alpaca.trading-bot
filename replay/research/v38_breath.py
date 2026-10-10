"""The owner's breather (10-10): "the big runners run for very few minutes,
they slow down a little bit to catch their breath, then they run again - if you
enter during that period where it slows down, you can have a really good
entry". Beside the speed buy, never instead of it ("sometimes the first minute
runs 50, 70%" - catching 20% of it and keeping 10% after the pullback is fine).

The breather is the playbook's pattern (rules.md 4: after the rip, the first
red; 1c over the red's open as the next candle goes green; the stop at the
red's low): over the last N closed 1-minute candles the price ran X% or more
(lowest low to highest high, $250k a minute on average), the last closed candle
is red and gave back no more than a share of the run, and the price is now 1c
over that red candle's open with the new candle green. The floor: the red
candle's low (at most 10% under the fill). One breather buy per red candle; no
re-entry level for it (it buys under the high by design). Everything else as
v38 proposed: the re-entry over the last sale's price for the speed buys, a
limit at the ask + 2%, the bot's buy checks, the trailing thirds, $7,500 full.

python3 v38_breath.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
import v38_gaps as G
from speedsim_giveback import run_of
from speedsim_study import session, SESSIONS

BIG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"), ("2026-10-09", "WFF"))
BASE = dict(level="exit", checks=True, limit="2%")
VARIANTS = (
    ("v38 proposed (speed only)", dict()),
    ("+ breather: 10 min run 20%+, back <= half", dict(breath=(10, 0.20, 0.5))),
    ("+ breather: 10 min run 30%+, back <= half", dict(breath=(10, 0.30, 0.5))),
    ("+ breather: 10 min run 50%+, back <= half", dict(breath=(10, 0.50, 0.5))),
    ("+ breather: 20 min run 30%+, back <= half", dict(breath=(20, 0.30, 0.5))),
    ("+ breather: 10 min run 30%+, back <= a third", dict(breath=(10, 0.30, 1 / 3))),
    ("+ breather: 5 min run 20%+, back <= half", dict(breath=(5, 0.20, 0.5))),
)
SHOW = (0, 2)                                      # the runs table: the base and the 10 min / 30% breather


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    print("THE OWNER'S BREATHER beside the speed buy (v38 proposed: re-entry over the last sale's price,")
    print("a limit at the ask + 2%, the bot's buy checks, trailing thirds, $7,500 full)")
    print("%-46s %4s %3s " % ("", "n", "won") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %6s %7s %6s %6s" % ("TOTAL", "PRE", "RTH", "AFTER", "FRGT", "BIYA", "SBFM", "WFF"))
    allx = []
    for name, kw in VARIANTS:
        xs = [x for k in sorted(by) for x in G.play(by[k], bars, **BASE, **kw)]
        allx.append(xs)
        per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        big = [sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) == b) for b in BIG]
        print("%-46s %4d %3d " % (name, len(xs), sum(x[2] > 0 for x in xs)) + " ".join("%+7.0f" % v for v in per) +
              " %+8.0f | %+7.0f %+7.0f %+7.0f | %+6.0f %+7.0f %+6.0f %+6.0f" % (sum(per), *ses, *big))
        b = [x for x in xs if x[3] == "breath"]
        if kw:
            print("%-46s      the breather buys: %d, %d won, %+.0f - PRE %+.0f / RTH %+.0f / AFTER %+.0f%s" % (
                "", len(b), sum(x[2] > 0 for x in b), sum(x[2] for x in b),
                *(sum(x[2] for x in b if session(x[1]) == s) for s in SESSIONS),
                ("; best: " + ", ".join("%s %s %s %+.0f" % (x[0]["day"][5:], x[0]["sym"],
                 datetime.fromtimestamp(x[1], S.ET).strftime("%H:%M"), x[2])
                 for x in sorted(b, key=lambda x: -x[2])[:4] if x[2] > 100)) if b else ""))
    print("\nEACH RUN OF 40%+ IN A WINDOW: the share of the run kept per share (sold parts included), P/L (trades)")
    print("  %-5s %-5s %-5s %-17s %-17s %6s | %-24s | %-24s" % ("day", "sym", "sess", "low", "high", "run",
                                                             VARIANTS[SHOW[0]][0][:24], VARIANTS[SHOW[1]][0][:24]))
    hm = lambda t: datetime.fromtimestamp(t, S.ET).strftime("%H:%M:%S")
    for k in sorted(by):
        for r in by[k]:
            rn = run_of(r)
            if not rn or rn[0] - 1 < 0.40:
                continue
            cells = []
            for i in SHOW:
                xs = [x for x in allx[i] if x[0] is r]
                kept = 0.0
                for x in xs:                        # P/L per share of the full position bought
                    fill = S.Path(r).ask_at(x[1]) or 1
                    kept += x[2] / max(1.0, F.FULL / fill)
                kept /= (rn[4] - rn[2])
                cells.append("%5.0f%% %+8.0f (%2d)" % (100 * kept, sum(x[2] for x in xs), len(xs)))
            print("  %-5s %-5s %-5s %-17s %-17s %5.0f%% | %-24s | %-24s" % (
                r["day"][5:], r["sym"], session(rn[1]), "$%.2f %s" % (rn[2], hm(rn[1])),
                "$%.2f %s" % (rn[4], hm(rn[3])), 100 * (rn[0] - 1), cells[0], cells[1]))


if __name__ == "__main__":
    main()
