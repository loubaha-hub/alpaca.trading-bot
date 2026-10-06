# Where things stand

Updated 2026-10-06, 10:25am ET.

## Code
- Working branch: `claude/zealous-ramanujan-br3gay`. New work goes here;
  nothing goes to `main` without the owner's OK.
- Live on `main` (Render): VERSION v31-r34.10 (released 10:21am ET 10-06 at
  the owner's request, all three accounts flat; r34.9 was 9:02am).
  Accounts: T6HH runs v36, P28T ("V30-100k") runs v37, AUES runs v35.
- r34.10 adds, for v37: no re-buy within 60s of a sale unless 30c up (10%
  of the sale price on a cheap stock, whichever is smaller); sells, stops
  and adds only on prints under 2s old. For v36: the 60/40 tape over ask vs
  bid shares (between-prints set aside); no crowd hold for a stock ripping
  in its last 2 minutes; a WHY-NOT log line for the top crowd names.
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
0. v37 speed rule (0.1+): held off by the owner until "up 3%" has a big
   enough live sample; the branch logs the speed on every buy (not live yet).
1. "Half the gain" on tiny gains (25 of today's exits under 1%): the owner
   keeps the exits as they are for now (10-06) - small cuts, the big runs
   pay for them; watch whether big live winners show up. A grace after the
   buy (only the stop sells for N seconds) is built, off: the replay says it
   hurts at every length, but cannot see the noise it is for (see journal). Replay: arming it later hurts (+$4,002 from the first cent vs
   +$2,332 from 1%, fills 0.2% worse) - the wide stop and the early exit work
   as a pair. Untested option: a 15-20s grace after a buy, the stop only.
2. The scored checklist (proposal): must-haves plus weighted signals, the
   weights set from the owner marking real moments "I'd take it / I wouldn't".
3. Environment settings for Massive (Polygon) data for the 3-month runs
   list (network + key, typed by the owner into Render/Claude settings).

## Next steps
- The trade review page (private artifact, owner's marks saved in its db
  collection `verdicts`): https://claude.ai/artifact/TiBC6Qtoca1SHZU27AhVWG -
  fill it each day; read the owner's marks back with ArtifactData.
- Small fix: set v37's stop BEFORE the buy goes out (a partial fill raised
  "SELF-CHECK VIOLATION ... stop=0.0" for an instant: RUBI 5:58, JAGX 10:15).
- Mid-day releases restart the bot and wipe v36/v35 state (candles, EMAs,
  crowd timing): avoid them; or restore that state on start-up as the day
  high now is.
- v31/v34/v35 audit (10-06): their price queue overflowed at the open
  (20,000 waiting, 41,007 dropped on 10-05 at 9:33) - not fixed for them.
- Later: the 3-month runs list (Massive data), fill-quality measurement,
  sell into strength, Level 2 via Webull, news, Chinese-stock early exit,
  half-dollar levels.
