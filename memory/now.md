# Where things stand

Updated 2026-10-06, 9:20am ET.

## Code
- Working branch: `claude/zealous-ramanujan-br3gay`. New work goes here;
  nothing goes to `main` without the owner's OK.
- Live on `main` (Render): VERSION v31-r34.9 (released 9:02am ET 10-06 at
  the owner's request, all three accounts flat). Accounts: T6HH runs v36,
  P28T ("V30-100k") runs v37, AUES runs v35.
- v37 since r34.9 (all from watching IPDN/AIXI with the owner, 10-06): every
  buy above the REAL high of the day (seeded from today's bars at start; odd
  lots raise it, never trigger); buys/adds only on prints under 2s old;
  confirmation by buy of the day 0/0/1/2 green 1-minute candles above the
  old high (sideways = 5 minutes); volume >= 2x the stock's normal minute and
  >= 70% of its busiest recent minute; stop a third of the last minute's
  move (3-8%). Off: "half the gain" after +3% (hurt in every replay), the
  faster-price exception to the 70% floor.
- On the branch only: `watchman.py` (until the real-money account).
- Release builds are made in a separate git worktree from `origin/main`.

## Waiting on the owner
1. v36 fixes (proposed 10-06, details in the journal): the tape as green vs
   red (between-prints set aside), no 2-minute crowd hold for a stock already
   ripping, a "why not" log line once a minute. Build on the branch, release
   after the close?
2. The scored checklist (proposal): must-haves plus weighted signals, the
   weights set from the owner marking real moments "I'd take it / I wouldn't".
3. Environment settings for Massive (Polygon) data for the 3-month runs
   list (network + key, typed by the owner into Render/Claude settings).

## Next steps
- 9:31am ET 10-06 check-in: v37's first trades under r34.9 at the open -
  each buy against the real high and the volume on the chart.
- Mid-day releases restart the bot and wipe v36/v35 state (candles, EMAs,
  crowd timing): avoid them; or restore that state on start-up as the day
  high now is.
- v31/v34/v35 audit (10-06): their price queue overflowed at the open
  (20,000 waiting, 41,007 dropped on 10-05 at 9:33) - not fixed for them.
- Later: the 3-month runs list (Massive data), fill-quality measurement,
  sell into strength, Level 2 via Webull, news, Chinese-stock early exit,
  half-dollar levels.
