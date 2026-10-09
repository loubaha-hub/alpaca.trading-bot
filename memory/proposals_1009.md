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

## 3. Room to TODAY's high on a pullback (the playbook's 2:1)
- Rule: a pullback buy under the day's high needs the day's high at least
  twice the risk (buy to stop) above the buy - as it already does for
  yesterday's high (V35_ROOM_RR 2.0 on prev_high).
- Why: the owner's playbook ("the next resistance must be at least double
  the risk away"); the owner on NTCL 10-09.
- Touches: the room check (adds today's high as a wall); furious buys keep
  room set aside. CONFLICT with #2: VEEA's first pullback (~7:09: buy ~$5.68,
  stop ~$5.55, the high ~$5.73) would fail it - ~5c of room against ~13c of
  risk; the second (~7:18, risk ~5c, the high $5.90) would pass. Chart
  estimates - the tape decides.
- My call: test #2 and #3 together on the tape; if both, #3 filters #2.

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
