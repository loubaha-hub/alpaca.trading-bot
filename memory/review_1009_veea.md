# VEEA 10-09, blow by blow (from the bot's own log)

The owner, 10-09 ~8am: "why did we miss it? ... it may have acted as designed ...
get the exact entry by seconds for every one ... what the bot did and what it
should have done instead."

Source: Render log lines (WHY-NOT, FURIOUS, FAST BUY, BUY SHORT, ENTER, SELL,
EXIT, SKIP). Prices between decisions are the bot's once-a-minute WHY-NOT
snapshots, NOT the full tape. The exact second-by-second tape comes from the
read-only read (r34.39, SEC_DUMP_DAYS = 10-09) after 8pm; the "what if" lines
below are to be redone on it.

## The run-up (v36 / v36b - same lines for both)
| ET | VEEA | crowd (money, 5 min) | gainer | why no buy |
|---|---|---|---|---|
| 6:40-6:46 | $5.07-5.17 | #3, $150-350k | #2 | no crowd: not top 2 for 2 min |
| 6:47:43 | $5.20 | #2, $353k, held 0.7m | #2 | no crowd yet (2-min hold) |
| 6:49:46 | $5.22 | #2, $611k, held 2.8m | #2 | crowd OK; no pattern (no rip) |
| 6:50-6:55 | $5.16-5.29 | #1-#2, $400-640k | #2 | no pattern; red candles, volume 0.4-1.9x |
| 6:56:56 | $5.35 | #1, $763k | #2 | no pattern (GG, 3.3x - not over the day's high) |
| 6:59:56 | $5.44 | #1, $1.55M | #2 | no pattern (last candle red) |

## The buy and the stop
| ET | what |
|---|---|
| 7:00:12.596 | FURIOUS at $5.5326 (speed 0.35; the last 5s +0.6% on $134k); bid $5.51 ask $5.55; both v36 and v36b |
| 7:00:13.836 | v36b: 238 of 270 wanted @ $5.55 (at the ask) - 22% of the account |
| 7:00:14.601 | v36: 629 of 740 wanted @ $5.5473 avg (limit ask + 20c = $5.75) - 21% |
| | stop for both $5.49 = the $5.50 line - 1c (tighter than the 10c leash, $5.45); add planned at ~$5.75 on a new high |
| 7:00:14-24 | best fresh print $5.56 |
| 7:00:24.669 | the bid at $5.49 = the stop: sell (premarket: limit 10% under the bid) |
| 7:00:26.601 | v36b out 238 @ $5.49: -$14.28, held 13s |
| 7:00:24-34 | v36 out in 8 pieces as the bid fell $5.49 -> $5.45: 628 @ $5.4847 avg, -$39.33 |
| 7:00:34 | market $5.41 x $5.42 (the dip's low, ~15c under the buys) |
| 7:00:35 | v36's last share @ $5.40 (-$0.15; the "STILL HOLDING 1 share" CRITICAL) |

v37: no line at 7:00:12. Its quiet checks before a buy are: a fresh print over
the day's high by 2c or 0.5% (~2.8c here), confirmation, and for the furious
route the last 1-minute candle not red (the 6:58 candle was red). Which one
stopped it - from the tape tonight.

## After the stop - every chance to get back in
| ET | VEEA | v36 / v36b | v37 | what came next (minute snapshots) |
|---|---|---|---|---|
| 7:04:33-54 | $5.65-5.66 (day high + 5c) | NO SPEED for a re-entry: 0.04-0.06 under 0.10 | - | $5.57 at 7:08:54, $5.79 at 7:10 |
| 7:10:36-56 | $5.79-5.88 | NO SPEED: 0.00-0.06 | SKIP: score 9/15 (speed 0, lows 0) | $5.77 7:11, $5.69 7:13, $5.59 7:15 |
| 7:24:08 | $5.95 | NO SPEED: 0.00 | SKIP: last two candles not both green | $5.82 at 7:25 |
| 7:26:49-59 | $6.03-6.04 | at the $6.00 line - wait till it holds 5c past | - | high ~$6.11 7:27, ~$6.13 ~7:31; $5.98 7:30, $5.86 7:36 |
| 7:48 | $5.63 | | | crowd #2, faded |

## Reading it (to confirm on the tape)
- Each bot did what its rules say. Nothing ran against the code.
- Each later point to get back in ($5.65, $5.79, $5.95, $6.03) was followed by a
  pullback of 10c or more within minutes. On these snapshots a 10c stop would
  have caught 3 of the 4 (5.79, 5.95, 6.03) and $5.65 is unclear (the 7:05-7:09
  low is not in the log). The speed rule and the $6 line wait most likely saved
  losses - the owner's read.
- The money in VEEA was in the FIRST buy, held through a 15c dip: from $5.55
  to ~$6.13 (+58c). Only a stop 15c+ under the buy (about 3%, v36b's regular
  stop, $5.38) held; the 10c leash ($5.45) and the line stop ($5.49) did not.
- A question for the owner (rules meeting, not a change): the buy was 5c over
  the $5.50 line, so the line stop ($5.49) was tighter than the furious 10c
  leash - 6c of room. Which should win right after a furious buy just over a
  line? On 10-08's 40 furious buys the 3% stop was as good or better than 10c
  (v36 -$1,269 vs -$1,605; v36b -$586 vs -$606) - one more case for that table.
- v36 (pays up) vs v36b (at the ask): the same price here ($5.5473 vs $5.55);
  both filled 85-88% of the shares wanted.

## The owner's chart (Webull 1-minute, 6:55-8:09 ET; read by eye, +-2c)
- 7:00 candle: green ~$5.29 -> ~$5.46, top wick to ~$5.53-5.56 - our buys at
  $5.55 were at the top of that wick. 7:01: red to ~$5.37 (the stop-out).
- 7:02-7:06: five greens, ~$5.40 -> ~$5.63, over EMA9.
- 7:07-7:08: two reds, pullback to ~$5.55-5.58, over EMA20. 7:09-7:11:
  green again, ~$5.84-5.88 at 7:11.
- 7:13-7:17: pullback to ~$5.58-5.60 (EMA20). 7:18-7:29: climb to the $6.13
  high (~7:29). Then $5.70 by 7:41, $5.84 at 7:53, ~$5.52 at 8:04, $5.67 at 8:09.
- Two of the playbook's green-red-green pullbacks on the #1 leader: buy back
  over the red's open ~$5.67 at ~7:09-7:10 (stop under the red ~$5.55) and
  ~$5.77 at ~7:19-7:20 (stop ~$5.58). Both ran to $5.88 / $6.13.
- Why no bot took them: the furious buy at 7:00:12 was VEEA's first buy, and
  V36_SETUP_BUYS = 1 (the owner, 10-07, SPAI / LPCN: "a re-entry has to go
  past the high of the day") - after one buy, no candle setups; only the
  day's high + 5c, at speed 0.10 (V36_REENTRY_SPEED). The code's own comment
  quotes the owner (10-06): the setups are "for the first and second buys".
- Question for the owner (words, not code): should a furious buy stopped out
  within seconds use up the leader's setup buy? Touches V36_SETUP_BUYS and the
  10-07 SPAI decision (SPAI's 2nd buy was under the high, on a red candle, no
  speed). Ties to candidate 7 in now.md (the #1 leader's first pullbacks,
  LPCN 10-07 4 of 4 to +2R). Needs the tape and more days before any change.
