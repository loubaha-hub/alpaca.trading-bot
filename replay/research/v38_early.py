"""Does the speed test pick up the big runners too late? (the owner, 10-10:
"early on the volume is not there yet ... it would not have picked it up until
too late, and when it's too late it's running fast").

For each run of 40%+ in the read (lowest price to the highest after it): the
first second the speed test is on after the run's low (with the bot's buy
checks), the price then, how much of the run was already done, the minutes
from the low, and the ask 1 and 2 seconds later. Then the same for the first
second the price is also over the day's high, and over v38's last sale's
price (the level that lets it in). By session.

python3 v38_early.py <new windows> <old windows> <old minute bars>"""
import os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secsim as S
import v38_final as F
import v38_gaps as G
from speedsim_giveback import run_of
from speedsim_study import session


def main():
    by = F.load(sys.argv[1], sys.argv[2], sys.argv[3])
    hm = lambda t: datetime.fromtimestamp(t, S.ET).strftime("%H:%M:%S")
    print("THE FIRST SPEED SIGNAL IN EACH 40%+ RUN (the bot's buy checks on): price, the share of the run already done")
    print("  %-5s %-5s %-5s %-16s %-16s %6s | %-34s | %-26s" % ("day", "sym", "sess", "low", "high", "run",
          "first speed: time, price, done, min", "the ask 1s / 2s later"))
    rows = []
    for k in sorted(by):
        for r in by[k]:
            rn = run_of(r)
            if not rn or rn[0] - 1 < 0.40:
                continue
            st = G.signals(r, checks=True)
            p = S.Path(r)
            px = {x[0]: x[4] for x in r["S"] if x[4]}
            t_lo, lo, t_hi, hi = rn[1], rn[2], rn[3], rn[4]
            first = None
            for kk in sorted(st):
                t = r["start"] + kk
                if t < t_lo or t > t_hi:
                    continue
                if st[kk][0] and px.get(kk):
                    first = (t, px[kk])
                    break
            if first:
                done = (first[1] - lo) / (hi - lo)
                cell = "%s $%6.2f %4.0f%% %5.1f" % (hm(first[0]), first[1], 100 * done, (first[0] - t_lo) / 60)
                asks = "$%.2f / $%.2f" % (p.ask_at(first[0] + 1.99), p.ask_at(first[0] + 2.99))
            else:
                done, cell, asks = None, "never on the way up", ""
            rows.append((r, rn, done))
            print("  %-5s %-5s %-5s %-16s %-16s %5.0f%% | %-34s | %-26s" % (
                r["day"][5:], r["sym"], session(t_lo), "$%.2f %s" % (lo, hm(t_lo)), "$%.2f %s" % (hi, hm(t_hi)),
                100 * (rn[0] - 1), cell, asks))
    for s in ("PRE", "RTH", "AFTER", None):
        xs = [x for x in rows if s is None or session(x[1][1]) == s]
        got = [x[2] for x in xs if x[2] is not None]
        early = sum(d <= 0.25 for d in got)
        print("%-6s %2d runs: the speed fired on the way up in %d; within the first quarter of the run in %d; never in %d" % (
            s or "ALL", len(xs), len(got), early, len(xs) - len(got)))


if __name__ == "__main__":
    main()
