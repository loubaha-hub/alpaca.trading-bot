# Journal

Decisions, instructions and results worth keeping. Newest first. Dates are ET.
Each entry: what was decided or found, the numbers, why, and where it lives.

## 2026-10-07

### The owner, ~11:20am: slow down - first, why the bots miss the runners
- "We were writing code against the things we already had." First
  priority: examine very closely why the programs do not pick up the
  runners and what blocks them - "that's where the money is; if we miss
  these runs we will not advance". Second: reduce the common small losses.
  To sit down together after the owner's break; no new code before that.
- On v37 exits: once a stock runs, the gain is not in danger; the higher
  the gain the more likely it stays (a 50% retracement of a big gain is
  huge). The owner likes the "give back a third of a big gain -> close"
  rule (V37_SPIKE_GIVEBACK, r34.15).
- Blockers found in the bots' own logs (to examine together): NO TREND
  (EMA9<EMA20 / MACD<0 lag at the start of a run - BIYA 4:10-4:14 +51%),
  NO CROWD (top 2 held 2m; $0k after LULD halts - DKI), NO PATTERN (high
  break needs 2x volume - LPCN climb, DKI reopen candles), 6 buys today
  (BIYA 8:20, LPCN 7:20-7:35), NO ROOM (yesterday's high - APUS 7:14),
  NO TAPE (between-prints - APUS), v37 spike-only gates, and the r34.16 20%
  ceiling from the last candle (conflicts with the HOD rule; halt gaps).

### Standing instruction, ~11:00am: agreed fixes go in when flat
- The owner: "all of our fixes have to go in as we put them in - when all
  the positions are flat, push them in". Added to CLAUDE.md's standing
  rules. r34.19 (the add waits for the new high to hold 2s) pushed 10:55:42,
  all three flat since 10:29.

### The owner's decisions, ~11:00am: the adds
- An add waits for the new high to hold about 2 seconds (V36_ADD_HOLD_SEC
  = 2.0, built as r34.19 on the branch; release timing not yet given).
- The sizes STAY: ease in with a small starter, bigger adds as the stock
  keeps moving up - "that reduces the losses from the jittery entry that
  can be shaken off; a sensible strategy, keep it in place". The
  proposal "bigger starter, smaller adds" is rejected.
- The owner's principle: new rules must not destroy the base built so far;
  change a rule only where the existing rules do not cover a situation.

### The owner's decision, ~10:55am: after an add, the floor moves to the new average
- Proposal "keep the floor at what the starter paid" REJECTED by the owner:
  "when you buy higher the position is bigger - if we don't get out before
  that floor is breached we incur big losses. The floor should be adjusted
  to the add-on." So V36_FLOOR_AVG stays True (as live). The add problem
  (sold seconds after the add) is to be solved another way: the add waits
  for the new high to hold, and/or smaller adds - to discuss.

### The owner, ~10:45am: the rules must be re-checked while the order works
- On WETO (the high-of-day rule checked once, at the decision, never while
  the buy reloaded for 6s): "once you put the order, that has to be
  checked - if the situation changes in front of me I cancel the order or
  move it up; those things have to be in the code". And: a fix must not
  open another can of worms.
- To build (tonight, shown before release): every reload of a buy (and
  every add) re-runs the strategy's entry rules on the current quote and
  stops the moment one fails, logging which; a fill under the old high is
  sold at once and logged as a rule break; each with tests from today's
  live cases.

### The owner, ~10:35am: make the code airtight
- Two kinds of problems, in the owner's words: the market is more complex
  than the rules ("you and I can deal with that"), and rules given "black
  and white" that the bots do not follow - "where the rubber meets the
  road: the code has to be as precise as possible, airtight". The entry
  has improved ("I applaud you for that"); the forward test on the live
  market is the judge; "we still have work ahead of us".
- Plan agreed in principle (to show the owner before anything goes live):
  the rule sheet as the contract (each rule one precise line, with its
  number, its code and its test); one gate every buy passes; a checklist
  logged with every buy and an automatic audit; a walk through every way
  the code can buy or sell, listing the holes; record prints and quotes.

### WETO: v37 should not have bought it, and kept reloading (r34.18)
- The owner, ~10:20: "v37 entered WETO and WETO did not go above the high
  of the day - this should not happen"; "it keeps loading after the stock
  has gone down"; "almost every one I touch strays from the rules".
- Found: the high was $1.32 (premarket 8:27); one $1.33 print a cent over;
  the fast-buy route then reloaded the buy at the falling ask for 6s and
  filled $1.26. Fixed on the branch (9428727): V37_HOD_CLEAR (2c or 0.5%
  over the old high), buy(floor=old high) - no reload under it,
  V37_ACCEL_REAL (the owner's speed >= ACCEL_SPEED) and V37_ACCEL_TAPE
  (60/40) for fast buys. The owner chose "Push r34.18 when flat".
- Pattern told to the owner: each special route (rip exception, fast buy)
  skipped some basic rule; the fix is that every buy passes the same
  never-rules.

### r34.17 released 10:15am: the exit
- The owner: "we really need to fix the fast exit - six minutes is not
  acceptable"; "push them in"; asked to confirm, chose "Push r34.17 now".
  Pushed bd4a229 at 10:15:54, all three flat. Market sells 9:30-4:00, no
  sell on top of our own working order, no buys 9:29-9:31. Deferred, said
  so: keeping the data flowing during an exit (a concurrency change, too
  risky mid-day).
- WETO (v37 9:52:38): ran $1.16 -> $1.33 9:51-9:52 on ~1.7M shares, the
  9:52 candle closed $1.22 with a long top wick; v37 decided on the $1.33
  top print and filled $1.26; faded to $1.13 by 10:14.

### r34.16 released 10:07am; the first trades after the fixes
- The owner agreed the 20% ceiling on v37's fast buy ("when the stock is
  way too stretched and you buy near the top you're a sitting duck";
  "the exit is the key - get out very quick, at any price"). Asked to
  confirm, the owner chose "Push with the 20% cap"; pushed 3e24d61 at
  10:07 with v36's restart high-of-day fix, all three flat.
- After the fixes, 9:20-10:07 (from the accounts' equity): v36 SXTC
  9:29:39 -$58.49 (a "new high" under the $7.12 morning high after the
  restart; the stop sell stuck 5.7 minutes at the open - cancels not
  confirmed, 8 refused re-sends in 4s, "unprotected", v36's data queue
  dropped 30,278 messages; booked only 8 of 133 shares); v37 WETO 9:52:38
  -$68.26 (fast buy, 10% of the account, on a $1.33 print 5% over the
  market - crowd #6, no live quote; tape 49/51); v36 APUS 9:58:36 -$43.17
  (4c under $9.00, stop 9.2% away, rode $8.98 -> $8.08); v36b APUS
  9:58:42 -$1.80 (a stale $8.96 print, filled $8.77, sold at once).
- Proposals to the owner (not decided): stops sell at market 9:30-4:00
  and wait for cancels premarket; no buys 9:29-9:31; an exit must not
  block the data; book every fill; buys need the live quote; fast buys
  need a fresh quote, the owner's speed and the 60/40 tape; the level band
  scales with price; v36's 3% cap (the owner's call).

### Premarket audit (4:00-9:20am, r34.14): every trade, one by one
- The owner: check every order this morning, find the flaws, fix them -
  "that is what gives us an edge". 51 round trips: v36 22 (5 won,
  -$221.76), v36b 22 (1 won, -$155.80), v37 7 (3 won, +$63.71). Page:
  https://claude.ai/artifact/9ZEU642xnxLiY5tQtCPUy4 ; the log lines are in
  replay/live/2026-10-07_premarket_*.log.
- r34.15's rules, checked on the minute chart, would most likely have
  blocked 40 of the 44 v36/v36b buys (they lost $320 together).
- Still open (proposals, the owner to decide one by one): (1) v37's fast
  buy has no ceiling - a fix (no fast buy 20%+ over the last closed
  minute's high, V37_ACCEL_CHASE) is on the branch, NOT released; (2) the
  adds: 14 of 16 trades with adds sold within 10s of the add (the floor
  jumps to the average) - starters +$201, adds -$199; (3) the 6-buy cap
  still blocks a non-leader that accelerates (BIYA 8:20); (4) v37 has no
  steady-runner entry (LPCN 7:07-7:29 +32% on ~$20M); (5) v37's giveback
  arms at 1c - all 7 v37 trades held 1-4s; (6) first buys 15%+ under the
  HOD; (7) 2+ reds = a lower-high trigger; (8) v36's stops 5-10% (the
  side-by-side test, the owner's call); (9) the crowd ranking lags a
  minute in a spike; (10) log labels.
- BIYA 8:20-8:21: $2.54 -> $33.96 -> $8.20 in under a minute (the bots
  saw $2.62 at 8:20:37 and $9.24 at 8:21:26); v36s "6 buys today", v37
  never looked (crowd #4). SXTC 8:16: v37 in 1s, +$75, then $7.12.
- Replay round 2 (7 days, $15k, 0.2% / 1% fills, without re-entry
  speed): v36b with the fixes +$1,107 / -$611; without the HOD+5c rule
  +$1,524 / -$63; without the leader no-cap +$1,387 / -$161. v37 with the
  earlier acceleration +$3,495 / +$484 vs without +$3,454 / +$1,205.
  To re-run with speed 0.1 and the live sizing.

### r34.15 released 9:20am ET (the owner's OK)
- The owner, ~9:15am: do not wait for the end of the day - "the fixes we
  agreed on have to be implemented right away"; then "push to main".
  All three accounts flat (pos=0) at 9:19; pushed a4b3008 at 9:20.
- In it: every fix agreed in the morning review (see below and now.md),
  the acceleration entry at the owner's sizing, re-entry speed 0.1
  (replayed on v36b, 7 days, $15k: +$1,779 / +$519 at 0.2% / 1% fills vs
  +$1,037 / -$692 without). Not in it: the runner "rides to half" (lost:
  -$368 / -$1,603). 542 tests, the live cases among them.
- The owner asked whether the bots will learn from their mistakes. Told:
  no - they repeat a mistake until the code changes; it streamlines
  because each live mistake becomes a fix plus a test that keeps it fixed.
- The owner: keep the re-entry and chase rules - "these run, come back and
  run" - and fine-tune them (with the 10-07 bars, after 8pm).

### Morning review with the owner (4-7am ET)
- First side by side: v36 (T6HH) -0.74%, v36b (AUES) -0.49% at ~7am (the
  owner's screens); 13 closed trades each, same names (MI, BIYA, SXTC,
  LPCN) within seconds. v36b's losers -2.7% of the trade on average vs
  v36's -4.3% - the 3% first-stop cap. Wick veto blocked SXTC 5:35am.
- v37: 3 trades, held 1-4s, all "half the gain": BIYA +$11.88, MI +$0.94,
  LPCN -$6.39. The owner: selective, small cuts - "light at the end of the
  tunnel"; a big runner will tell.
- The owner on BIYA (v36, 4:20am: added 685 @ $2.51 on a new high, the
  floor moved to the average ~$2.46, all sold @ $2.43 one second later):
  "I would have done that too" - $2.50 is resistance; trading clusters at
  the whole and half dollar; reaching one, be diligent jumping out. Let
  the bots know. This is the playbook's Levels section and rules.md 6
  "at a resistance / half-dollar level - to build" (not built yet).
- To build on the branch and replay after the close (the owner liked
  them; release only with the owner's OK): (1) the half-dollar levels for
  v36/v36b - add or start only once past the level, out when it hesitates
  at one, stay when it bolts through; (2) v37's ripping exception only
  with speed 0.3+ (LPCN 6:33am got in at score 9, speed 0.07); (3) v37's
  "half the gain" confirmed by the bid (BIYA sold on a 1.1s-old $2.64
  print while trading at $2.73).
- The owner, ~7:15am, for v36 AND v36b: be mindful of $x.00 and $x.50 -
  natural resistance. Wait for the price to cross the level and hold a
  moment, about 5c past it, before adding (BIYA: the starter bought low
  would have been kept). And once a position runs, do not cut it until it
  has given back half of its gain - "that is where we will see positive
  results". To build and replay (with a range of settings), then the
  owner decides.
- LPCN 7:18am (the owner's chart): v36/v36b bought $3.42 on a pullback
  setup while it stalled under $3.50; stopped 7:20 (-$8.89 / -$2.40). It
  was their 6th LPCN buy, so from 7:21 to 7:35 - LPCN through $3.50 to
  $3.99 (+20%), #1 name with $8-16M per 5 min - both logged "NO: 6 buys
  today" every minute. The 6 buys went on whipsaws (mostly add-then-stop).
  v37 bought 7:00 @ $3.35 with "score None (the last candle closed red)" -
  the ripping exception overrode the red-candle no-buy; out in 3s.
  Added to tonight's build: the 6-buys cap not to apply to the #1/#2 name
  while it makes new highs of the day (the owner's "leaders first, never
  banned for ripping"); v37's ripping exception never overrides the red
  candle.
- SPAI 8:09am: both v36s bought $4.91 on "rip then red pullback" - but the
  8:08 red candle fell $4.92 -> $4.41 (-10%), under the 8:07 green's open
  ($4.58), on 267k vs the rip's 304k: a reversal, not a light pullback.
  v36b's 3% cap: out at $4.74 in 48s (-$5.51); v36: stop at the red low
  $4.41 (10% away), still holding at 8:10. v37 skipped at 8:09:09 (red
  candle), then bought 8:09:58 via the ripping exception, -$12.45 in 1s.
  The owner: "this one shouldn't have bought it". To build: a red candle
  that falls under the green's open (erases the rip) on heavy volume = a
  failed rip, no buy; the pullback must be light and hold the rip.
- SPAI 8:12-8:13am: v36 added @ $5.08 (at the $5.00 level), stopped 2s
  later (-$14.23); both v36s re-entered 8:13:37 @ ~$4.99 (buy 2) after an
  8:12 red ($5.00 -> $5.10 high -> $4.89, 274k vs the green's 236k) -
  under the high of the day ($5.10), at $5.00, no speed check. The owner:
  a re-entry must go past the high of the day; it bought on a red candle;
  speed not respected; small candles, everything coming down - "quite a
  few things broken". The HOD rule for later buys is built (V36_SETUP_BUYS
  / V36_HOD_PLUS) but OFF since 10-06 (the owner kept v36 simple; replay
  said it hurt). To retest with today's live cases: (8) re-entries only
  above the HOD + 5c; (9) re-entries need real speed (price up on volume).
- v37 SPAI 8:09:58 (the owner: "it sold at 9:59... the stop is at the
  bottom of the red candle - there's a problem"): bought 108 @ $4.8053,
  decided on a $5.05 print (filled 24c lower, falling); best price after
  $4.81 (half a cent up); 8:10:00 sold @ $4.69 by "half the gain" on a
  2.0s-old $4.80 print; stop $4.59 never reached. -$12.45. Entry had
  "score None (last candle red)" - in via the ripping exception.
  To build: (10) "half the gain" arms only after a real gain - at least a
  full cent (V37_GIVEBACK_ARM is 0 = any fraction); test 1c/3c/1%;
  (11) skip a buy whose price, re-read just before sending, is already
  well under the trigger (the burst reversed).
- Webull's 1-minute bars (8:08 red 4.93/4.93/4.41/4.52; 8:09 green
  4.52/5.02/4.51/4.72; 8:10 green 4.71/5.02/4.68/4.93; 8:11 close 5.00):
  v37's buy trigger was a $5.05 print the market never traded at (Webull's
  8:09 high $5.02, earlier in the minute); it filled at the real ~$4.80
  one second before the 8:09 candle closed at $4.72, and sold at $4.69 -
  the 8:10 candle's exact low - which then closed $4.93; SPAI made $5.10
  at 8:12. With the stop only and a real "half the gain": about +$15
  instead of -$12.45. Widened fixes 4 and 11: act on a print only when
  the live quote agrees (buy if the ask is near the trigger; sell if the
  bid confirms).
- The owner on it: the entry was probably OK; the exit was not respected
  - the exit is the stop under the red candle's body (8:08 red's body
  bottom $4.52; v37's stop $4.59 was right), not "half the gain" one
  second in on the first print of the next candle (8:10:00.03, a 2s-old
  $4.80, half-cent "gain"). Rule to build (fix 10, exact): right after a
  buy only the stop under the red body sells; "half the gain" only once
  there is a real gain. (10-06 the owner rejected a time-based grace;
  this one waits for a gain, not a clock - replay both.)
- Second by second from our own logs: 8:09:57.8 v36b's stop fired on a
  $4.78 trade (the market then); 8:09:58.9 v37 bought "above the high" on
  a $5.05 print - stale/out of sequence - filled $4.81 (12c under the red
  candle's top $4.93; two partial fills, which Alpaca shows as a buy and
  an "add"); 8:10:00.0 sold $4.69. The owner suspected the bot "messed
  up" the timing - right: the buy signal was false. Fix 11 tightened:
  just before buying, the live ask must still be at/above the trigger.
  Exact ticks: Webull's tick feed no longer reaches 8:09; Alpaca has
  them (a read-only dump at the next restart, if the owner wants).

### SXTC 8:16 - the move the owner has been describing (proposal, not built)
- Webull 1-min: 8:13 2.05->2.11 38k; 8:14 2.11->2.25 114k (3x); 8:15
  2.25->2.43 261k (2.3x), each closing at its high, the #1 gainer; 8:16
  2.44 -> 7.12 high -> 4.81 close, 788k; 8:17 red to 3.96; ~2.30 by 8:55.
  The owner's speed: 8:14 0.20, 8:15 0.18. v36/v36b: "NO CROWD" (#1 gainer
  but $800k < $1M); v37: #4 by money until 8:16; bought $2.87 (score 15)
  and sold 1.5s later on a stale print (+$75); v36/v36b bought $4.83/$4.78
  after the spike (v36b -$74). The owner: "this is where the money is";
  bigger size at high speed; watch it come down; "a move like that should
  not be missed - how do we set the metrics?"
- Claude's proposal (12): an "acceleration" entry for v36 and v37 - any
  scanner name; 2-3 green minutes, each closing in its top third and
  higher; volume rising, the last >= 2x the one before and >= 3x normal;
  the owner's speed >= 0.15 on >= $250k in the minute; buy the first
  fresh print over the last candle's high (SXTC ~$2.46 at 8:16:00); size
  1x/2x/3x the starter at speed 0.15/0.2/0.3; once up 30%+ sell on giving
  back a third of the gain. Replay on all days incl. 10-07 at several
  thresholds, counting the accelerations that fail, before deciding.

### The owner on furious moves (10-07 ~9:40am) - decisions for the build
- "The position has to get bigger, faster - more than half of the account
  in the next few seconds, 60-70%; I would have used the whole account.
  You see this once a month or two; it pays for the months." Exit: Claude's
  proposal - a spike sells on giving back a third (keep two thirds). "The
  speed should override everything pretty much."
- Built (off, V37_ACCEL): speed 0.3+ -> 35% of the account at once, +30% to
  65% on the next new high 2%+ over the buy while still 0.3+ (0.15 -> 4%,
  0.2 -> 10%); speed 0.3+ on $250k+ in the minute buys whatever the crowd /
  money / score rules say. Kept (Claude's call, to confirm with the owner):
  never over a red last candle, never on a print the quote does not back.

### The fixes, first replay (09-28..10-06, $15,000, fills 0.2% / 1% worse)
- Built on the branch (tests from each live case, 539 pass): v37 - rip
  exception at speed 0.3+, red candle never overridden, ask above the old
  high, prints outside the bid-ask ignored, giveback from a full cent and
  only if the bid agrees. v36/v36b - re-entries past HOD+5c (SETUP_BUYS 1),
  leader not capped, failed rip, heavy red, $x.00/$x.50 levels, no buy 5%+
  over the trigger, the 3% stop from the price paid. Proposed, off:
  RUNNER_HALF, REENTRY_SPEED, ACCEL (v36/v37).
- v37: live +$3,563 / +$366 (85 trades) -> fixed +$3,454 / +$1,205 (49).
  v36: +$1,540 / -$985 (185) -> +$1,746 / -$176 (131).
  v36b: +$2,272 / -$78 (181) -> +$1,037 / -$692 (151) - WORSE; finding
  which rule. v36b + RUNNER_HALF -$368 / -$1,603 (drop it). v36b +
  REENTRY_SPEED 0.1 +$1,779 / +$519 (95 trades).
- The replay has no quotes: the print checks are proven by the tests,
  not by these numbers.

## 2026-10-06

### v24 replayed with its holes fixed (10-07 ~1am; replay/research/v24sim.py)
- The owner: "what would v24 really have done after fixing the holes".
  Written from v24's rules (not the droplet code), recorded days
  09-28..10-06, $30,000 a day, a stock joins when up 10%+ on the prior
  close, $1-$20. A = as built (fills at the decision price / the exact
  reclaim level, re-split on every buy/sell, no halt); B = fills at the
  next minute's open, 0.2%/1% worse, 10% halt; C = B without re-splitting
  (each buy 10% of the account).
- 7 days: A -$28,321 (09-28 +$21,698, 10-01 -$29,125; 31,266 orders,
  $111M traded, 44% won); B -$27,627 / -$29,216 (halted every day);
  C -$14,722 / -$22,638 (33% / 12% won, 1 up-day, halted 6-7 days).
  Honest fills alone turn 09-28's +$21,698 into +$3,077 (no costs).
- Verdict (Claude's): the gains were the simulator's perfect fills and
  churn; not worth reviving. The owner (10-07 ~1am): v24 is set aside -
  it was only to see its problems; 10-07 runs v36 (T6HH), v36b (AUES) and
  v37 (P28T) as planned.

### September on Alpaca, from the accounts' own fills (r34.14, 10-07 0:14am)
- r34.14 (the owner's OK, accounts flat, 00:14 ET 10-07): at start-up each
  account logs its fills 09-24..09-30, read-only, in the background
  (HISTORY_DUMP; trading unchanged). Fills: T6HH 641, AUES 1,319, P28T 2,193.
- Day totals, sold minus bought (the accounts were mostly flat at night):
  P28T (v30, $100,000): 09-25 -$45,258, 09-28 +$7,856, 09-29 -$7,534,
  09-30 -$8,862 - matches $54,947 on 09-30 4am. AUES ($30,000 on 09-28;
  v24, v32 on 09-30): -$6,143, -$2,591, -$5,099 - matches $21,250. T6HH
  (v31 from 09-28): -$616 (the owner's "about $615"), -$3,406, -$3,299.
- Correction (FIFO-matched, 10-07 1am): realized 09-25..09-30 = -$74,951
  (T6HH -$7,320, AUES -$13,834, P28T -$53,797), 876 round trips, 11.6%
  won, $17.7M traded. P28T's 09-25 "-$45,258" was mostly stock carried
  over the weekend: realized -$8,610 that day, -$8,059 when sold on 09-28.
  Holes the fills prove: 210 P28T trades held under 10s lost -$34,538
  (exits 1c under, inside the spread); doubled buys (same qty again within
  10s) -$20,418 on P28T, v24's 50% slot doubled to ~100% on AUES; MSGY on
  T6HH 7 buys in 37s to 152% of the account, -$3,167; one oversell (VBIO,
  short 4,475 for 4 min); leftover shares (LANV 5,733); 877 re-buys within
  60s of a sale; BKYI 129 orders in 9 min. No single $9,375 loss in the
  fills - that is v30's top-up size. Data: scratchpad sept_history/.
- No fills at all on T6HH and AUES before 09-28 (reset over the weekend, or
  v27/v24 traded elsewhere 09-24..26). Volume: P28T bought $3.08 million on
  09-28, AUES $323k on 09-28 - churn. No Alpaca account "ran high"; the
  big gains remembered were the bots' own reports (droplet v24).

### The droplet's v24, retrieved (10-06 night)
- The owner copied it off the DigitalOcean droplet (keys none, account
  numbers masked): `v24_files (3).tgz` on the working branch. On the
  droplet the crontab line for launch_live_v24_real.sh was switched off
  (backup /root/crontab_backup.txt); Webull showed no orders since 09-25.
- v24 (09-15, "buy everything, tight stop, reclaim to re-enter"): buys
  every scanned symbol on its first bar; equal split of the pot, re-split
  on every buy/sell; sell the first close under entry, or on giving back
  10% of the gain; re-buy when a bar's HIGH tops the exit level, filled AT
  that level. Positions were simulated in the bot; orders went to Webull's
  OpenAPI (dry run, then real). Not Alpaca. Base $5,000 / $4,046.80.
- 09-17 (simulated): +$2,023.55 on $4,046.80, 501 closed trades, 54% won
  - fills at exact levels, no costs, thousands of re-split orders (5,110
  trims). 09-18 real: 968 orders accepted, 2,769 rejected as duplicates,
  1,941 skipped by TRADING_HALT. The $507,574.92 (Sep 16) is not in these
  files (they start 09-16 night).

### The first strategies on Alpaca (found 10-06 night)
- Before Render: a DigitalOcean "droplet" ran v21, v22, v24 and v27 (the
  09-21 Claude Doc: "confirmed on the droplet"; all but v27 on a shared
  live_cycle_common.py). Not reachable from here; its code and logs are on
  the droplet if it still exists. v21 = compounding, 10%/50% giveback
  stop, volume-signal re-entry; only result: 09-18 same-day backtest on
  $5,000, 440 trades, 51.6% won, +$1,742.88 (simulated; "churning").
  v12 is not in the repo, Render or any artifact.
- On Render (this repo, from 09-24 4:35pm ET): v27 (main.py, "v27 logic,
  rebuilt clean"; Alpaca movers list, up 10%+, $1-$20, green-then-red
  pullback, 2 stocks at half the cash each, ladder 2%/10% under the peak,
  then keep 80%/90% of the gain) on the main service's keys (T6HH,
  "v27-30k") until main.py became v31 on 09-28; v24 09-25 on AUES; v30
  09-25 on P28T ("V30-100k": buy at +10%, 4 by speed, $25k/$12.5k/$6.25k/
  $3.125k caps, 0.5% trail under +5%). 09-30 4am balances: T6HH $28,776,
  AUES $21,250, P28T $54,947.

### Where v24 ran, and what is left of it (found 10-06 night)
- Code: every version is in git history (the clone was shallow; fetch
  --unshallow). main_v24.py 09-25 (first), 09-26 ("final revision"), 09-28
  (rebuilt: green-then-red bars, red open +1c, 12 ranked positions); on
  09-30 4:18am ET the file was overwritten with v32. Render services
  v24-trading-bot and v30-trading-bot (created 09-25) are suspended since
  09-30. Nothing on Render or in the artifacts is from August.
- Account: AUES (the owner's "v24-30k"). v24's last line, 09-30 4:00am:
  baseline equity $21,250.22; the same keys ran v32 that morning, and the
  main bot's v32 on AUES showed $18,452 that evening. v30's service ran on
  P28T. Render's logs from before 09-30 are gone (about 7 days kept); the
  trades are only in AUES's order history at Alpaca (09-25..09-29).

### v36 on two accounts: r34.13 released (v36b on AUES)
- The owner, ~10pm: run v36 on two accounts side by side - T6HH as it is
  (r34.12), the ~$7,000 account (AUES) with r34.13's three changes - and
  stop what ran there (v35: 10-06 5 trades, 0 won, -$74, -1.0%). "Release
  r34.13 so they can run in parallel and see how they stack up."
- Built as v36b (V36B in r34.py): wick veto 60%, first stop capped at 3%,
  fresh exits. The settings were module globals shared by every strategy;
  now read per strategy (V36.own), so T6HH's v36 does not change. Replayed
  09-28..10-06 with the new code: v36b = the r34.13 numbers to the dollar,
  v36 = r34.12's (+$2,272 / -$78 vs +$1,540 / -$985 at fills 0.2% / 1%).
- Released 10:18pm ET (the owner's OK), all three accounts flat; up
  10:19pm, v36b on AUES, no errors. Compare
  the two by % of the account: AUES ~$7,000, T6HH ~$18,200.

### v36 retest: what helps it (7 days incl. 10-06, tape check off)
- Where v36 loses (replay): 84 of 153 trades never reached the first add,
  -$1,718, stopped at a median -4.6% (the pullback's low, up to 9% away);
  the 69 that added made +$3,635 (scratches at the average -0.5%, 9 trail
  winners +$4,492) - the add/floor works, the failed starters cost.
- Fills 0.2% / 1% worse: tomorrow's v36 (r34.12) +$1,540 / -$985;
  first stop capped at 3%: +$2,186 / -$279 (worst trade -$39 vs -$102);
  at 4%: +$2,000 / -$462; wick veto 60%: +$1,618 / -$781; 50%: worse
  (+$1,137 / -$1,055); 60% + 3% cap: +$2,272 / -$78 (best; 10-06 alone
  -$347 -> -$160); fresh exits: identical (the replay has no lag) - no harm.
- The cap holds across 3% and 4%; the wick veto only at 60% (fragile).
  Proposal: cap 3% + fresh exits for v36, wick veto 60% optional.
- r34.12 released 8:07pm ET (the owner's OK at 5:14pm), accounts flat;
  up 8:08pm, the restore lines tagged [v36]/[v37]. The day roll clears
  each stock's state at the new day, so 10-06's counts do not carry over.

### v36 replayed, 6 days (tape check off - the replay has no real tape)
- Live v36 as it is: 153 trades, 7% won; +$1,917 at fills 0.2% worse
  (+$1,989 of it on 10-05, SAIQ +$2,521), -$70 at 1% worse. 143 trades
  ended on the stop (median -2.7%, -$2,583 in all); 10 on the trail, all
  winners (+$4,500). A home-run strategy: small losses, rare big runs.
- The add fixes: no change in the replay (+$1,886 / -$65) - its prices move
  smoothly inside a minute, so the 1:49 APUS miss cannot happen there.
  They fix a plain bug; judge them live.
- The score at v36's entries made it worse: 10 -> -$125 / -$1,315; 12 ->
  -$198 / -$691 (30 trades); the owner's first-two-buys rule with score 11
  or 12 -> -$555 / -$232 at 0.2%. They block the runners (SAIQ) and the
  stop-outs stay. Proposal: keep both off for v36; look at v36's EXIT next
  (93% of its trades end on the stop).
- Owner decision (~4:45pm): v36 stays simple, as it ran this afternoon -
  the score and the first-two-buys rule stay OFF (built, branch only); only
  the APUS add fix goes in. v37 keeps all of today's improvements (score
  12). Both run tomorrow from the open. Release r34.12 built (worktree
  release9, 467 tests): r34.11 + the v36 add fix; waits on the owner's OK.
- The owner: for v36, only what benefits it. Benefits / no harm: the APUS
  add fix (r34.12), the restart restore (r34.11). Hurt in replay, stay off:
  the score, the first-two-buys rule. Not yet tested for v36 (candidates):
  fresh prices for its exits (today's v36 stops acted on prints 2.5-7s
  old: APUS 11:32, AVBP 12:19, DLXY 10:46), a huge-wick veto on the
  pullback candle alone, and its exit (93% of replayed trades on the stop).

### Real money: where it is, and the day-trading rule
- The owner: the money for live trading is at Webull, not Alpaca. The bot
  trades only through Alpaca (orders, fills, positions, reconcile), so it
  cannot use that money where it sits: either move it to an Alpaca live
  account (bank transfer or an ACATS transfer started from Alpaca), or build
  a Webull order connection (Webull trading API, the owner's API access).
  Not decided. ALPACA_PAPER switches the whole bot; one strategy live while
  the others stay on paper needs a per-account switch or a second service.
- The owner, confirmed: the $25,000 pattern-day-trader minimum is gone. The
  SEC approved FINRA's Rule 4210 change on 2026-04-14, effective 2026-06-04;
  unlimited day trades at any size, real-time intraday margin instead. The
  usual $2,000 margin-account minimum still stands. Check each broker's own
  rollout before funding.

### Today replayed, 4am-4pm, v37 with today's fixes (the owner asked)
- Recorded today: replay/data/2026-10-06 (77 symbols, Webull 1-minute).
- Live v37 today: 114 trades, -$734 (r34.6 to r34.11 through the day).
- Replay, fills 0.2% / 1% worse than the chart:
  r34.6 (the version at 4am): 71 trades +$1,201 / 99 trades -$1,243;
  r34.10 (the morning fixes): 25 trades +$428 / -$236;
  r34.11 (score 12, live since 3:46pm): 13 trades +$431 / +$57 - the only
  one positive at 1%. Most of it AIXI 4:17 and 4:26 (+$270, +$164), the
  rip that cost -$256 live with 10 buys on old prices; the rest small.
- The replay is kinder than live (r34.6: replay +$1,201 at 0.2%, live
  about -$734): live fills cost somewhere near 0.5-1% this morning.
- Live, first r34.11 buy: VCIG 4:03pm at score 14 (speed 0.84), +$8; a
  minute later "SKIP VCIG - score 9/15" (no speed, wicks growing).

### v37: buy only while the stock is RUNNING - from pass/fail to a score
- Why: all 9 v37 buys 9:02am-2:25pm came at the top of a one-minute burst
  out of quiet (already up 7-28% in 2 minutes; the bot paid up to 2% over
  the print) and lost. The owner: "I would not have taken any of those."
- The owner's signs: price up, volume up (the confirmation), the candle
  before green and full to the top (two thirds up can still do), wicks not
  growing candle after candle, green bodies not shrinking noticeably (a
  little, irregularly, is fine), lows stepping up, over VWAP, 9 EMA over 20,
  MACD positive, no resistance in the way; a huge wick on the last candle
  is almost a stop; a red last candle is no buy (until the bots learn
  bounces off solid support like the 200 EMA); pay well over the price only
  when ripping. "The world is not black and white - trading is messy."
  And: "the speed is everything", backed by volume - the biggest weight.
- Strict pass/fail (V37_MOMENTUM) replayed 6 days, fills 0.2% worse: 71
  trades instead of 112, 72% won instead of 62%, but +$2,211 instead of
  +$4,002 - it skipped 26 losers (-$251) and 31 winners (+$2,243, SAIQ
  +$1,079 among them). Each check alone also cost: red -$118, wick -$388,
  lows -$437, bodies -$734 (SAIQ), volume 2 minutes -$1,529 (72% won).
- So a score (V37_SCORE_MIN, of 14): speed 3 (a point at 0.1, 0.2, 0.3),
  last candle 2, volume 2 (2 of the last 3 minutes at 2x), trend 2, wicks
  1, bodies 1, lows 1, MACD 1, room 1; red or a huge wick = no buy; a stock
  ripping (busiest minute of its day) skips it; V37_SCORE_FURIOUS tests
  "speed 0.3+ buys whatever the score". All off on the branch; every v37
  buy now logs its speed and score.
- Also built: V37_STEADY_PAY (pay at most 0.5% over unless ripping), and a
  restart reads today's buys back from the broker (APUS 11:33/11:36 had
  skipped their confirmation candles after the 10:21 release).
- Fill cost decides (6 days): today's rules +$4,002 at fills 0.2% worse,
  +$2,110 at 0.5%, -$48 at 1% (about live today: sales 0.4-1.9% under the
  trigger). The median trade is +0.15%; 102 of 112 make under 2%; ~10 big
  runs carry it.
- Score at 15 points (speed 1/2/4, price-move guard 3%): minimum 7-10
  barely filters (most buys score 9+). Minimum 12: 72 trades, 75% won,
  +$3,132, worst day +0.6% at 0.2%; +$308, worst day -1.9%, worst trade
  -$135 at 1% (today's rules -$48, -3.1%, -$246) - the only version
  profitable at live-like costs. 13 about the same; furious override +1
  trade. Exits: "half the gain" only after +2%/+3% is far worse at both
  costs (-$2,821 / -$4,788 at 1%), the 15s grace too - the owner's tight
  exits are right. Next lever: what each fill costs (measure live).
- Owner decision (~3:40pm): switch v37 to score 12. Exits stay as they are
  for now (small cuts; a shaken-out runner is re-bought when it scores).
  Released r34.11 at 3:46pm ET with the owner's OK ("release r34.11 on
  that timing"), all three accounts flat at 3:45pm. Live 3:46:27; the
  restore read today's fills (v37: APUS 6 buys, IPDN 36, JAGX 14...).
- The owner, next: premarket is all limit orders - when a buy misses,
  go right after it, fast, but never lose track of (or pile up) its own
  orders. And v36 misbehaved today (screenshot coming).

### Round-trip runners, 90 days (the owner's request)
- The owner: which stocks ran up and came back down to about where they
  started, in the last 90 days; runs on successive days count as one, at
  least 2 days apart; how many times, the dates, the spacing.
- Counted: a day's high 50%+ over the day before's close; round trip = a
  close back within 20% of that start (same day counts); base $1+, $5M+
  traded on the run day; exchange-listed, today <= $30 and <= $3B; Webull
  daily bars, regular hours, July 8 - October 5.
- Result: 3,230 small caps scanned, 247 made a round trip, 330 trips; 183
  once, 50 twice, 9 three times, 5 four times (BIYA, LGHL, MSS, TRUG, VBIO).
  Repeat gap median 20 days (33 within 2 weeks, 24 in 2-4, 26 over 4).
  111 trips came back the same day; median run +83%. 70 runs not back yet.
  At +30%: 381 stocks; at +100%: 102.
- The owner: too many - show the ones that at least doubled. Doubled =
  the run's top at least 2x its starting price (multi-day runs count):
  112 stocks, 130 trips; 95 once, 16 twice, OMH 3 times; median run
  +158%; repeat gap median ~16 days. The page opens on doubled, with
  +50% as a switch.
- How often, 90 days (stocks by number of round trips, +30% / +50% /
  doubled): 1: 266/183/95; 2: 74/50/16; 3: 27/9/1; 4: 7/5/0; 5: 5/0/0;
  6: 2/0/0; none 7+. Most repetitive (+30%): LGHL, SKYQ 6; BIYA, ELPW,
  LBGJ, TRUG, VBIO 5. BIYA, LGHL, TRUG, VBIO lead at every size and
  each doubled at least once - a possible repeat-runner watch list.
- Not counted: delisted/OTC names (the owner: ignore them), premarket-only
  spikes. Page: https://claude.ai/artifact/1Qv2hYjpmxZurmTUMPYABD. Data:
  replay/data/daily_listed_2026-07-01_10-05.json; finder and results:
  replay/research/roundtrips.py, roundtrips_2026-10-05.json.

### v37 grace after the buy: built (off), replay says no, the replay can't see noise
- The owner liked the idea: for N seconds after a buy only the 3-8% stop
  sells, so the noise up front can't shake it out. Built as
  V37_GRACE_SECONDS / V37_GRACE_FORGET (off), commit de24d2f.
- Replay, 6 days, fills 0.2% worse: no grace +$4,002 (62% won); 10s
  +$3,915; 15s +$3,632; 20s +$2,984; 30s +$1,539 (one red day); 15s
  forgetting the spike inside the grace +$3,096, worst trade -$321. Trade
  by trade, 15s made 0 trades better and 35 worse (-$346): the winners
  were already held; losers moved from ~1% cuts to the stop.
- But the replay draws each minute as straight lines (open-low-high-close)
  - no back-and-forth in the first seconds - so it cannot show the noise
  the grace is for. Live check, the 6 trades 9:02-11:40am: 5 fell through
  their stops within a minute (a grace would have cost ~$75 more); XHG ran
  +10% to +29% after its 4-second exit. Roughly a wash.
- Owner decision: leave it off; keep "half the gain" from the first cent -
  it cuts often but keeps the down moves small, and the runs pay for it.
  "Hope in this business is not the way to go - numbers, and let the
  probabilities work." The number that tests it live: the replay had about
  2 trades a day of $100+ (11 of 112) making 83% of the profit - do those
  show up live? (A shadow log of what a grace would have done was offered,
  not asked for.)
- The owner's projection (to check against live results): winners of $200+
  - one run is often $400-500; even cut in half it pays for the many small
  cuts. Since the fixes v37 is "a lot more stable" (9:02-11:40am: 6 trades,
  -$25, against -$700 before). Replay: 4 trades of $200+ in 6 days (SAIQ
  +$1,079, LABT +$848, APUS +$230, NXL +$203) made $2,360, about 6x all 42
  losers (-$405). A full v37 position is 40% of the account (~$6,000), so
  $400-500 is about +8% at full size, after both adds.

### v37 exits stay as they are for now - the owner accepts the trade-off
- The owner: the stops and "half the gain" cause the churn and kick v37
  out of stocks that keep going, but the downside must be controlled.
  Stocks don't rise in a straight line; when one goes exponential the bot
  stays in, and that run pays for the small cuts on entries and exits.
- The numbers: replay (6 days, fills 0.2% worse) agrees - 11 of 112 trades
  (each $100+) made $3,316 of the $4,002; the 42 losers cost $405 in all.
  Live 10-06 morning it did not work yet: 79 losers -$916, 23 winners
  +$216, the biggest +$92; 74 of 106 sales were followed by a 3%+ run
  within 15 minutes (most buys were made under the pre-fix code).
- What to watch: does a big live winner show up to pay for the cuts? If
  live winners stay small while stocks run after the sale, revisit exits.
- Live after the fixes, 9:02am-2:25pm 10-06: 9 v37 trades, all small
  losers, -$52 in all (day -$485 on the owner's dashboard, nearly all
  before the fixes). Every one sold by "half the gain" 4-13s after the
  buy. The fills cost more than the moves: buys up to 2% over the price
  seen (APUS 1:49pm 8.05 vs 7.89), sales ~1-2% under it. The owner: it
  no longer buys lawlessly; holding steady like this, one big runner can
  carry it.

### v37 speed rule: tested, held off by the owner - "up 3%" stays
- The owner's formula: speed = (P2 - P1) / P1 x (V2 / V1), rolling 60s
  windows (P1, V1 the minute before, P2, V2 the last minute). "Anything
  above 0.1 is good", no top limit; falling (negative) is never a buy;
  higher = more selective; huge volume with a small move counts (1% x 20x
  = 0.2). V2/V1 capped at 30.
- Replay, 6 recorded days, fills 0.2% worse: up 3% in 60s (the rule now)
  112 trades, 62% won, +$4,002, worst trade -$99; speed 0.1+ 69, 68%,
  +$3,529, -$24; speed 0.2+ 36, 78%, +$3,222, -$13. Every day up in all.
- Today's 106 live v37 buys: 37 at speed 0.1+ (-$338), 69 below (-$362).
  Speed does not pick winners on its own - 84 of the 106 were made before
  the morning's fixes (old prices, under the high). 0.3+ swings hardest
  both ways (next 5 min: +6.5% / -14.3% medians).
- Claude proposed 0.1 (0.2 if it still churns). Owner decision (~11am):
  hold off; keep "up 3% in a minute" and see how v37 does with it first.
  Why: cutting the trades that much leaves a sample too small to draw
  conclusions from - "you need an adequate sample". Confirmed after: being
  very selective is the human trader's edge (it cuts the losses), but first
  learn what the 3% rule does. The speed may come back "under different
  angles". V37_SPEED_MIN = 0.0 (off); every v37 buy now
  logs its speed ("| speed 0.12" on the ENTER line, speed= in the decision
  log) so live data builds up for judging it later.

### v37 rebuilt from watching it live with the owner (r34.7-r34.9)
- Live 4:00-8:10am: 83 trades, 17 won, -$701 (-4.6%). AIXI 4:17: 10 buys in
  100s, -$256. The causes were bugs, not the owner's design: prints queued
  while an order worked and were acted on oldest first (up to 58s old; a
  "new high" at 3.30 filled at 3.06); touching the high counted as a new
  high; a restart forgot the day's high (IPDN 5.64 bought under 5.83); odd
  lots were kept out of the high (IPDN chart highs 6.97/7.10); the 2c stop
  shook out every buy within seconds; the 10-buy limit locked v37 out of
  AIXI's and SDEV's second legs.
- Owner decisions: no daily buy limit (r34.7, 7:37am); every buy ABOVE the
  real high of the day, odd lots counted, the high read from today's bars
  so a restart keeps it; flying means volume up - at least 70% of the
  busiest recent minute ("we should not go below that"); confirmation by
  buy of the day 0/0/1/2 one-minute candles ("the first one and the second
  one, no way - that's where the money is"), sideways = 5 minutes.
- Released with the owner's OK: r34.8 8:10am (fresh prints), r34.9 9:02am
  (everything above, volume 2x normal, stop a third of the last minute's
  move 3-8%). Code: r34.py V37_* settings; tests/test_v37.py.

### Replays behind r34.9 (6 days, 09-28..10-05, fills 0.2% worse)
- This morning's rules: 686 trades, 24% won, +$6,406. r34.9's rule set:
  125 trades, 63% won (the owner's hand-trading 60-65%), every day up,
  +$3,924. The replay scores every junk trade a small win (smooth fills, no
  spread) - live today those lost; read it as "which is better", not money.
- Stop sized to speed (a): better than 2c in both fill tests. "Half the
  gain" only after +3% (b): worse in every test - off.

### Stale-price audit of v31/v34/v35 (09-30..10-06)
- Their buys need the live ask at the trigger (quote check), so a stale
  "new high" never became a buy: 0 of 44 buys, 0 of 37 measured sells.
- Their losses: 09-30..10-02 share counts broken (sold far more than bought,
  overfills; v31 -$6,103 on 09-30); 10-05 ordinary stop-outs (-$986). Their
  price queue overflowed at the open (10-05 9:33: 20,000 waiting, 41,007
  dropped) - not fixed for them. Files: scratchpad audit (not kept).

### Why v36 made no trades (10-06) - proposals
- The tape gate: 60% of shares at the ask never happened (26-54%); prints
  between bid and ask (27-42%) count against it. The playbook says "green
  outweighing red is what matters" - proposed: green/(green+red) >= 60%.
- The 2-minute crowd hold blocked the best two first entries (AIXI 4:17 at
  2.85, ran to 4.47; IPDN 7:29). Proposed: no hold for a stock already
  ripping. The 7:37/8:10 restarts wiped its candles and crowd timing.
- Proposed: a "why not" log line once a minute for the top crowd names.
  Waiting on the owner.

### The scored checklist (proposal)
- The owner: a human weighs many variables by priority; the bot checks a
  few, each pass/fail. Proposed: must-haves plus weighted signals, the
  weights set from the owner marking logged moments "I'd take it / I
  wouldn't".

## 2026-10-05

### The tape at the bot's buys (10-05)
- The owner: no Level 2 yet, but time and sales plus the bid/ask (Level 1)
  is "half of the battle": green = at the ask, red = at the bid, white =
  between, and how far each print is from the offer.
- At almost every buy the bot's tape read "0% by quote": quotes stream only
  for names it HOLDS (TAPE_QUOTES="positions"), so a name it was about to buy
  was marked by up/down ticks, not by the bid/ask.
- Even so, v31's 22 buys by the last minute's share at the ask: under 45%
  (mostly selling): 7 buys, 0 won, -$287 (SAIQ, NU x2, WDCX, ITUB, NVAX x2);
  45-59%: 7, 1 won, -$193; 60%+: 8, 2 won, -$241. One day, small numbers:
  the tape kept out of losers more than it found winners.
- Proposed: stream quotes for the top few names on the list so every print is
  marked against the real bid/ask before a buy; then a tape rule (item 14).

### Float rotation (shares traded / float), 10-05
- Regular hours: MI 413x (0.4M float), SAIQ 25x, SDEV 16x, JAGX 10x, QTEX
  1.8x, ALEC 0.9x; the bot's large caps NU, CLF, PAGS, STNE, RXRX 0.0-0.1x.
  Premarket 1x or more: MI 28x, APUS 16x, AMOD 10x, VEEA 10x, SAIQ 5x, SDEV
  2x - the morning's runners exactly. It finds where everybody is.
- As a buy condition in rip_test (rotation 1x+ at the rip, liquid, first
  entry): 23 trades, 22% won, -1.39% a trade - worse than float under 20M
  (28 trades, 36%, +1.33%). Likely late: by the time the float has turned,
  the minute-candle entries come late. Floats are as of 10-03, so a reverse
  split earlier in the week distorts older days. Use it to choose the
  stocks, not as the trigger - to be tested again with tick data.

### How the bot buys a fast stock (10-05)
- buy(): a limit at the ask + 0.2%, never over the trigger + 2%
  (BUY_CHASE_CAP); each try waits about 2s for a fill (send() polls 10 x
  0.2s), then cancels and re-prices; at most 8 tries. A buy that fills
  nothing is not logged - misses cannot be counted from the logs.
- Before any order, the quote check (CONFIRM_ENTRY_WITH_QUOTE) refuses when
  the ask is under the trigger - by half a cent: RETO 4:06am (ask 1.99 vs
  1.9993, 9 refusals in 4s - RETO was a top-2 "ripping now" at 4:07), BBD
  9:36am (4.30 vs 4.305, ~20 refusals), NVAX 1:48pm (11.79 vs 11.795).
- The owner: on a real runner, buy at once, even 50c over; in premarket a
  limit is passed and must be reloaded fast - the bot should do this better
  than hot keys. Proposed: price the limit from the stock's speed, re-price
  every few hundred ms, cap from the playbook, log every miss.

### The ripping rule on 1-minute bars (replay/research/rip_test.py)
- Rule: two greens adding 5%+, each on 3x+ the volume of the 5 minutes
  before, the second bigger; then the first red(s); buy 1c over the last red's
  open; stop at the reds' low; win at 2x the risk; 6 days 09-28..10-05
  (10-05 premarket only).
- Candles alone: 74 trades, 26% won, -0.39% a trade. Float under 20M and the
  first entry only: 46 trades, 33% won, +0.42%. Plus at least $500k traded
  in each rip minute (the owner's "stay away from thin"): 19 trades, 37% won,
  average win +13.2%, loss -4.7%, +1.88% a trade; with fills 0.5% worse,
  -0.14%. $250k: 28 trades, 36%, +1.33%.
- vs the live bot (under 1 in 10 won): about 3x the win rate, near break-even
  after costs - not the owner's 60-65%. What 1-minute bars cannot show (the
  tape, Level 2, the 10-second exit, news) is where the rest has to be.
  19 trades is thin evidence. On 10-05 it bought MI at 2.93 (9:19am) and was
  stopped at 2.80.

### The owner's screen vs the bot's scanner
- The bot's scanner checks only price $1-$20 and up 10% on the day. No float,
  relative volume, news, reverse split, short interest or shelf check. v35
  alone has a float cap (20M); v31 HALVES its size on floats under 5M.
- Data found: float - floats.csv (Webull). Filings, country - Webull (MI on
  10-05: a Hong Kong company that filed a 6-K that morning). Easy-to-borrow -
  Alpaca's asset list, which the scanner already downloads.

### "Ripping now" on the 10-05 premarket (first look)
- Ranked by the last 5 minutes' % move (only names with $250k+ traded in
  them), MI first showed as a top-2 "ripping now" at 8:12am ET - 3 minutes
  after the no-chase rule banned it. Also VEEA 7:00 (+8% in 5 min), ALEC
  7:05, APUS 8:00 (+57% in 5 min).
- The raw 5-minute ranking also picks noise (NU and SDEV at +0-1%); it needs
  the volume side the owner describes. To be tuned with the owner's numbers.

### The owner on the leaders and the no-chase ban
- Decided by the owner: trading the day's #1 and #2 leaders comes before
  anything else, and the bot must not ban a stock for ripping ("how could we
  make any money if we ban something that rips"). This replaces the earlier
  standing rule "the no-chase rule stays". How the ban is replaced is being
  worked out point by point.
- History: the all-day ban came in r28 (Saturday 10-03), because the five-day
  replay went from -$439 to +$1,825 with it - the same five days it was
  designed on. The leader switch (r30, by dollar volume, extra breakout buys)
  was left off because the replay made $187 less with it. v31 has never been
  limited to the leaders; only v35 is (top 2 by dollar volume).
- Level 2: Webull's API returns it (10 levels pulled for MI on 10-05). The
  bot could read it with a Webull API key; Alpaca has no Level 2 for stocks.

### The four filters: v35 only, and they do not separate v31's winners
- The owner's filters (MACD over zero, above VWAP and EMA9, EMA9 over EMA20)
  and the top-2 leaders were built into v35 only (c1a9fb4, Saturday 10-03;
  +$2,016 replayed over 09-28..10-02, but -$41 without its 2 best trades).
  v31 and v34 never had them. The owner thought all three did.
- v35's first live day (10-05): 6 trades, 0 winners, about -$98. It bought
  the right names - SAIQ twice, MI at 5.22 (10:18am ET) and 5.19 (11:36am) -
  and was out within about a minute each time (5s once). MI reached 10.42 at
  1:38pm.
- The filters on v31's live trades: 10-05, 16 of 22 pass and lost -$476 (all
  22: -$721). 09-30..10-02, 15 of 24 pass, all 15 lost (average -1.99%); the
  9 that fail averaged -1.40%. The filters pick trending stocks; v31 already
  buys trending stocks. Its losses come from the entry moment and the exits.

### The bot against the owner's playbook (10-05)
- The owner described their manual method (now in `memory/playbook.md`).
- v31 checks none of its filters (MACD, VWAP, EMA9, EMA20 - only v35 does);
  its leader setting is off (`V31_LEADER_TOP = 0`); the tape is logged, never
  used to decide; the spread is checked only by the earn rule; no wick check,
  no half-dollar levels, no 10-second chart. Alpaca's data has no Level 2.
- The no-chase rule shut out the day's two biggest runners for the rest of
  the day: MI at 8:09am ET (+16% from 0.91; it reached 10.42) and SAIQ at
  4:16am (it reached 18.37). The playbook buys exactly that: the leader while
  it rips.
- v31 instead traded ITUB, BBD, NU, PAGS, STNE (Brazilian large caps up 13-20%
  together that day), CLF, NVAX and others; 22 trades, 2 winners.
- Proposed (not decided): a new strategy written only from the playbook, on
  one account; the no-chase rule replaced there by the playbook's own checks
  for the top two leaders. The no-chase rule is the owner's standing decision.

### The owner's track record, and the after-sale check on every saved day
- The owner traded by hand February to about June 2026 at $5-10k a month,
  with 1-3 down days a month - not in Webull. Since then they have tried
  building algorithms on several platforms (Webull included); none worked.
  Their Webull history will not show the profitable months.
- Same check as 10-05 on the saved live logs, 09-30..10-02 (r13-r23): 24 v31
  trades, 0 winners, median hold 36s. 15 of 24 went 3%+ above entry within
  an hour of the sale (GOW +54%, VEEA +38% and +31%, NXL +32%, SSM +27%, MSGY
  +23%, SDEV +19%). From the entry, 15 of 24 fell 3% before rising 3%.
- With 10-05: 46 trades, 2 winners; 24 of 46 went 3%+ above entry within an
  hour of the sale. The scanner finds movers; the bot buys at a short-term
  top and sells on the dip.

### What v31's stocks did after it sold them (10-05)
- v31 made 22 trades on 10-05 and won 2 (STNE, SPCH). Webull 1-minute bars
  after each sale: 9 of the 22 went 3% or more above the entry price within
  an hour of the sale.
- The big ones were sold fast: SAIQ bought 6.50 at 4:05am, sold 3s later
  (crash guard), high 18.37 within the hour (after a dip to -9%). ALEC sold
  after 14s, then +29%. NVAX sold after 41s and 125s, then +8% within the
  hour and +13% within two. QTEX 4:06am, then +17%.
- But it is not only the exits: from each entry, 10 of 22 fell 3% before
  they rose 3% (6 rose first, 6 did neither). SAIQ dipped 9% and ALEC 4% before
  running. The entry moment and the size are part of it too.
- Reading: the scanner finds the right stocks (the owner says it is close to
  the one they trade by hand); the bot loses on entry timing, size, and
  patience. One day only - to be checked on every saved day.
- Script: scratchpad after_exit.py (not kept); bars from Webull get_stock_bars.

### Execution bugs found in the live logs (evening)
- Buys still overfill in r34: NU at 9:35am ET was sized to 300 shares (25%
  cap) and ended at 394 (32%). On 10-02 (r23) AMOD was sized to 1,869 and
  ended at 3,634 (49%). The order is polled, partly filled, cancelled, and the
  chase re-sends before the broker's count catches up. Not fixed yet.
- A position the broker no longer holds is retried on every print until the
  60s reconcile clears it: 150 zero-share AHG exits in one minute on 09-30
  (r16); 81 zero-share exits on 10-01 and 44 on 10-02.
- "STILL HOLDING" (an exit that did not complete): 839 on 10-01 and 492 on
  10-02, nearly all v33 and v32 - both off now.
- Restarts during trading hours: 46 on 09-30, 5 between 7:13 and 8:00am ET on
  10-02, 3 on 10-05. Old and new copies overlap for about a minute.
- The owner's screenshots, 10-05 close: T6HH (v31) -3.79% (-$724), P28T
  (v34) -1.41% (-$218), each a staircase of separate small losses.

### The bot does not record every trade print
- Checked the live code (r34.3). The "tape" reads every print and labels it
  buyer/seller, but keeps only the last 5 minutes in memory and writes a
  one-line summary to the log at each buy and sell. The prints are not saved.
- The decision file sits on Render's disk, which every restart wipes.
- Render's log keeps every ENTER/EXIT with the fill price (and, since r34.1 at
  4:34am, the print that triggered each sale) for about 7 days only.
- The past week's live log lines are being saved into `replay/live/`.

### Proposed: tick-by-tick data from Alpaca (waiting on the owner)
- Alpaca keeps every print and quote for past days. With it, a replay feeds
  the bot the real prints in order with the real bid/ask, close to live, and
  each trade can be split into "the bot executed badly" vs "the market
  reversed".
- Needs two settings in this cloud environment: network access to
  `data.alpaca.markets`, and environment variables `ALPACA_DATA_KEY_ID` /
  `ALPACA_DATA_SECRET_KEY` - ideally from a separate, empty paper account,
  since an Alpaca key can also trade. A new session picks them up.
- If the history is downloadable every evening, the bot does not need to
  record prints itself.

### Live today: 32 trades, 1 winner
- Across the three accounts: v31 1 winner in 15 (STNE +$122), v34 0 of 11,
  v35 0 of 6. v31 about -3.2% on the day (the owner's figure).
- Not caused by today's changes: the earn rule made no live buys, and the
  9:30 cutoff was not shipped. The losses are ordinary entries stopped out,
  most within about 2 minutes, at positions of 17-25% of the account.
- Live vs the replay of the same morning (v31): QTEX crash exit sold at $1.27
  with its stop at $1.36 (live -$312, replay -$119); ALEC bought 7:24 live
  (-$126) vs 7:04 in the replay (+$147).
- Real fills: regular hours within about 0-0.2% of the print; premarket buys
  averaged 0.5% over it, SAIQ at 4:04-4:05am 1-2% over.
- The owner's concern: before the recent changes, v31's days were under 1%
  either way. Proposed (not decided): freeze rule changes, compare daily live
  results against the dates of each change, half position size, run the older
  version on one account side by side.

### The 1-minute replay is too kind
- It invents the spread (0.2% premarket, 0.1% regular hours) and sees 4
  prices a minute, so it cannot see second-by-second shakeouts or bad fills.
- Stress test: with every fill 1% worse (`replay.py --slip-pct 1`, buys capped
  at their limit), every version of v31 and v34 loses over the six days, even
  with no earn rule (v31 +$2,881 -> -$887). The strategies make well under 1%
  a trade, so fill quality decides whether they make money.

### Earn-your-way-back-in: six-day replay (09-28 .. 10-05)
- Live rule since r34.2 (9:59am) / r34.3 (10:24am): top 1 leader by dollar
  volume, day high +5c, the breakout minute's volume 2x the 5 minutes before,
  spread at most 1%, one earned buy per new candle high.
- The owner's changes are built as switches, all off (branch commit 425d458):
  `V31_EARN_VOL_MODE` (volume vs the day's average minute), `V31_EARN_SPREAD_ABR`
  / `_CAP` (spread allowed grows with speed), `V31_FOLLOW_ABOVE_MAX` (keep a
  listed name buyable above $20), `V31_EARN_SKIP_VOL_RISING`,
  `V31_EARN_UNTIL_MIN` (570 = earned buys stop at 9:30). 14 tests.
- Earned buys before 9:30 made money in every variant; after 9:30 they lost
  in every variant (v31 live rule: +$782 on 2 before, -$212 on 4 after).
- Replay totals (normal fills / fills 1% worse), six days:

  | | v31 | v34 |
  |---|---|---|
  | No earn rule | $2,881 / -$887 | $235 / -$548 |
  | Live rule | $3,344 / -$612 | $546 / -$300 |
  | Live rule, before 9:30 only | $3,670 / -$164 | $697 / -$98 |
  | Top 1, day-average volume, before 9:30 | $3,630 / -$296 | $448 / -$463 |
  | Top 2, day-average volume, before 9:30 | $4,026 / -$255 | $516 / -$556 |
  | Top 3, day-average volume, before 9:30 | $3,686 / -$709 | $398 / -$719 |

- Without 10-05 (the day the changes were designed on), v31: live rule before
  9:30 $3,468, top 1 $3,284, top 2 $3,115, top 3 $2,911. Top 2's lead comes
  from 10-05 alone - overfitting. Widening top 1 -> 2 -> 3 adds losers.
- Following past $20: no case in the six days. Spread by speed: cannot be
  judged on the replay (its spreads are invented).
- Recommended: earned buys before 9:30 only; keep top 1 and the stricter
  volume test. Not shipped - caught up in the question of whether the replay
  can be trusted at all.
