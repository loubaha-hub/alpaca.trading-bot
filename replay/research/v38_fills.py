"""How v38 gets into the big runners - the buy's fill (the owner, 10-10).

The replay so far filled every buy (and every add) at the ask ONE second after
its signal - as if each order always got filled at the ask of that moment: it
never missed a runner. Live, a limit at the ask can miss when the ask runs
away, and the bot tries again (V37_KEEP_TRYING: each try works 0.5s, its
cancel confirmed, the next try 0.5s later or more) - each miss is a delay.
Paying over the ask fills at once, at the offers there are.

  DELAY: the fill 1 (as tested) / 2 / 3 / 5 seconds after the signal, at the
         ask of that moment - the cost of one, two or four missed tries.
  PAYING UP: the fill 1c / 2c / 5c / 1% over the ask (offers swept), with
         the floor 3c under OUR FILL (as tested) or 3c under THE MARKET (the
         ask we bought into) - the floor not pulled up by what we paid.

v38 with the trailing thirds, $7,500 full, the bot's buy checks; the re-entry
level the day's high (as decided) and the last sale's price (proposed).

python3 v38_fills.py <new windows> <old windows> <old minute bars>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import speedsim as Q
import v38_final as F
import v38_gaps as G
from speedsim_study import session, SESSIONS

BIG = (("2026-10-06", "FRGT"), ("2026-10-07", "BIYA"), ("2026-10-07", "SBFM"))


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    bars = {f[:-5]: json.load(open(os.path.join(sys.argv[3], f))) for f in os.listdir(sys.argv[3]) if f.endswith(".json")}
    F.FULL = 7500.0
    days = sorted({k[0] for k in by})
    ask0, rl0, lag0 = S.Path.ask_at, Q.run_ladder, S.BUY_LAG
    print("v38 - HOW THE BUY FILLS (trailing thirds, $7,500 full, the bot's buy checks)")
    print("%-50s %4s %3s " % ("", "n", "won") + " ".join("%7s" % d[5:] for d in days) +
          " %8s | %7s %7s %7s | %7s %7s %7s" % ("TOTAL", "PRE", "RTH", "AFTER", "FRGT", "BIYA", "SBFM"))

    def row(name, lvl):
        xs = [x for k in sorted(by) for x in G.play(by[k], bars, level=lvl, checks=True)]
        per = [sum(x[2] for x in xs if x[0]["day"] == d) for d in days]
        ses = [sum(x[2] for x in xs if session(x[1]) == s) for s in SESSIONS]
        big = [sum(x[2] for x in xs if (x[0]["day"], x[0]["sym"]) == b) for b in BIG]
        print("%-50s %4d %3d " % (name, len(xs), sum(x[2] > 0 for x in xs)) + " ".join("%+7.0f" % v for v in per) +
              " %+8.0f | %+7.0f %+7.0f %+7.0f | %+7.0f %+7.0f %+7.0f" % (sum(per), *ses, *big))

    for lvl, lname in (("day", "re-entry over the day's high"), ("exit", "re-entry over the last sale's price")):
        print("\n== %s ==" % lname)
        for lag in (1.0, 2.0, 3.0, 5.0):
            S.BUY_LAG = lag
            row("DELAY: filled %.0fs after the signal%s" % (lag, " (as tested)" if lag == 1.0 else ""), lvl)
        S.BUY_LAG = lag0
        for slip, sname in ((0.01, "1c"), (0.02, "2c"), (0.05, "5c"), ("1%", "1%")):
            sl = (lambda a: 0.01 * a) if slip == "1%" else (lambda a, s=slip: s)
            S.Path.ask_at = lambda self, t, sl=sl: (lambda a: a + sl(a) if a else a)(ask0(self, t))
            for market in (False, True):
                if market:                         # the floor 3c under the ask we bought into
                    Q.run_ladder = lambda p, t0, f0, full, under, arm, sl=sl, **kw: rl0(
                        p, t0, f0, full, under + sl(f0), arm, **kw)
                row("PAYING UP %s over the ask, floor under %s" % (sname, "THE MARKET" if market else "our fill"), lvl)
                Q.run_ladder = rl0
            S.Path.ask_at = ask0


if __name__ == "__main__":
    main()
