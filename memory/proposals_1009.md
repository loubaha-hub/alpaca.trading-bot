# Proposals from 10-09, distilled (to discuss - nothing decided, nothing coded)

The owner, 10-09 ~8:50am: "distill those, make them as simple as possible ...
we'll discuss them, see if it's worth adding them or we're over-fitting."
Each one that the owner wants goes through memory/checklist.md before code.

Settled today by the owner (no change):
- The $5.50 line stop at $5.49 stays, even when it is tighter than the 10c
  leash right after a furious buy just over the line.
- v37's $250k-in-a-minute money bar stays. Revisit only if it keeps missing
  the start of real moves ("the speed is what counts more ... people are just
  moving in"); count those cases, no rush.

## 1. Buy at the ask - all three
- Rule: every buy is a limit at the ask. No paying 20c over (v36 today).
- Why: in a spike the ask jumps for a second or two; paying over it buys the
  top of that burst.
- Evidence: 10-08 three-day read - the spread plus paying over the ask was
  ~70-80% of v36/v36b's losses. Live 10-09: MI 4:33 v36 paid up -$156, v36b
  at the ask $0 (no fill); VEEA 7:00 the same price either way.
- Cost: fewer fills on the fastest spikes.
- Touches: v36's buy price only (v36 is the control in the side-by-side).
- My call: not yet. Let v36 vs v36b run to ~30 furious buys, then decide.

## 2. A quick stop-out does not use up the leader's pattern buy
- Rule: on the day's #1 or #2 leader only, if a furious buy is stopped out
  within a minute, the next green-red-green pullback (buy 1c over the red's
  open, stop under the red's low) is still allowed - once.
- Why: the leader's first pullbacks are where the playbook makes money ("the
  first and second entries"); a stop-out on a spike's wick says nothing about
  the trend.
- Evidence: VEEA 10-09 (pullbacks at ~7:09 and ~7:19 ran to $5.88 / $6.13);
  LPCN 10-07 (4 of 4 to +2R). Against: the pattern on ALL stocks 10-06/07,
  34 trades, about break-even before costs - it only looks good on the leader.
  Two stocks - small.
- Touches: V36_SETUP_BUYS = 1 and the owner's 10-07 SPAI rule ("a re-entry
  has to go past the high of the day"). The conflict, in words: this allows
  one buy under the high. SPAI's 8:13 buy (on a red candle, no speed) would
  still be refused - this needs the full pattern.
- Over-fitting risk: medium. My call: test it on the second-by-second data
  for 10-06..10-09, every leader pullback after a quick stop-out, before
  deciding.

## 3. The three-candle 2:1 (the owner's rule, defined 10-09 ~9:10am)
- The owner's words: green, red, green. Enter when the third candle reaches
  the top of the red's body (the red's open). Risk = from there to the
  bottom of the red's WHOLE wick (its low). Gain = from there to the top of
  the WICK of the green before the red (its high). The gain must be at least
  twice the risk, or no buy. "It's a good rule to have."
- Is it in the bot? NO. The pattern buy has the entry (1c over the red's
  open) and the stop (the reds' low) right, but its only room check
  (V35_ROOM_RR 2.0) measures to the stock's high of the PREVIOUS trading day
  (a daily bar, an old wall overhead) - not to the green candle's high.
- In numbers: buy at B, stop at L (the red's low), first green's high H.
  Buy only if H - B >= 2 x (B - L). If H is at or under B, no buy.
  NTCL 8:34 (chart estimate): B ~$2.45, L ~$2.17-2.20, H $2.65 -> gain ~20c,
  risk ~25-28c: under 1:1 - no buy.
- Holes to settle in words before code:
  a. Two or more reds: risk to the LOWEST low of the reds, gain to the high
     of the green before the first red? (the bot's pattern already takes
     the lowest low and the last red's open)
  b. Entry at the red's open exactly, or 1c over (the bot buys 1c over)?
  c. Furious buys: stay outside it (room is set aside when furious).
  d. ANSWERED: keep yesterday's high; the nearer of the two walls decides.
  e. v37 does not buy the pattern (it buys over the day's high) - v36/v36b only.
- Touches #2: it filters #2's pullbacks (VEEA's estimates to redo with this
  definition on the tape).
- The owner (~9:20am): yesterday's high IS a wall to keep - "a very important
  point". Take the NEARER wall above the buy - the green's wick top or
  yesterday's high - and if that one is not 2x the risk away, no buy.
  Today's high is not a separate wall (the other buys are over it). And:
  "I don't want tons and tons of rules ... it will paralyze the bots ... when
  you have a very good move the bot will be blocked" - discuss before adding.
- So it is ONE rule, not a new one: the existing room check (V35_ROOM_RR 2.0)
  gets a second wall - room = the buy to the nearer of (the green's wick
  top, yesterday's high), at least 2x the risk. Furious buys stay outside
  it, so a very good move is never stopped by it. Holes a and b still open.
- My call: worth building - it is the owner's own rule from the playbook
  ("Room: the next resistance must be at least double the risk away"), it
  removes buys rather than adding them, and it is one comparison. Test it on
  10-06..10-09 first: how many pattern buys it removes, and what they made.

## Not rules - measuring
- A. A daily scorecard, per trade: kind of buy, price seen vs paid, share of
  the order filled, why it sold, the stock 5 and 15 minutes after the sale.
- B. The second-by-second read of each day's trades (r34.39 for 10-09), saved
  each night; Render keeps 7 days.
- C. Name the failed check in the "NO PATTERN" line (heavy red, failed rip,
  no green before the red) - information only.

## Looked at and dropped (keep as is)
- The +10% trail on furious buys (it sold MI at $1.46 before the furious exit
  could act): one case for, 50 trades against (10-08: v36 furious rule alone
  -$3,095 vs live -$1,550).
- A wider first stop to hold the first dip: the 10c leash was the owner's
  call on 10-08 with the data in hand; VEEA alone does not reopen it.

## The stack today - what a v36 pattern buy must pass (from the code, 10-09)
Basics: buying hours; on the scanner's list (up 10%+); $1-$20; under 2
positions; one buy a minute a stock; float 20M or less.
Who: the crowd (#1/#2 by money held 2 min, ripping, or the top gainer $1M+).
Pattern: a rip, still alive; green-red after it; the red not under the rip's
open; the red lighter than the green; the pattern on the stock's first buy
only (after that, the high + 5c).
Timing: over the trigger; no more than 5% over it; not at a $x.00 / $x.50
line (5c past, held 3s); a re-entry at speed 0.10+; v36b: no 60% top wick.
Filters: over VWAP, EMA9 over EMA20, MACD over 0; tape 60/40; room 2:1 to
yesterday's high.
= about 20 checks (v36b 21). A FURIOUS buy skips the crowd, pattern, chase,
lines, re-entry speed, wick, trend, tape and room - it keeps the basics, the
speed 0.30 on $250k, the last candle not red, and the 5-second / spread check.
#3 adds no check: it gives the room check a second wall.
Proposed (information only): a nightly count of which check said no on the
#1/#2 leaders, and what the stock did in the next 15 minutes - which rules
block good moves, by the numbers, before adding or removing any.
