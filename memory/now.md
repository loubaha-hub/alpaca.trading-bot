# Where things stand

Updated 2026-10-08, ~4pm ET.

## Now (10-08)
- Working branch: `claude/happy-ride-o56nlz` (this session). The memory
  files came over from `claude/zealous-ramanujan-br3gay`. Nothing goes to
  `main` without the owner's OK; a push to `main` restarts the bot.
- Live: **VERSION v31-r34.32** (pushed 3:25:13pm): r34.31 + a one-off
  read-only TICK_DUMP of v37's 10-08 trades (set TICK_DUMP = () in the next
  release). r34.31 (2:17pm): v37's 60s re-buy needs 20c over the sale (no 10%). r34.30 (1:26pm): no limit on buys of a stock a
  day (v36, v36b; v37 had none). r34.29 (1:08:58pm): no
  fast buy unless the price is up over the last 5 seconds; no fast buy when
  the ask is more than 10c over the bid. Everything else as r34.28.
- Judge rules per entry, added up over days (the owner, 10-08).
- **Waiting for after 8pm 10-08:** r34.33 (branch c08b67b) - v37 sells 5c
  under its best since the buy, in place of half the gain (a trial); the
  one-off TICK_DUMP off. Built off on the branch, not chosen: the 10c-under-$2
  re-buy, fix 3 (gain from the bid), V37_TRAIL_KEEPS_HALF.
- The owner chose at ~3:40am: v36, v36b and v37 on the full schedule
  (4am-8pm), not premarket only.
- The day at 1:05pm: v36 +$288, v36b -$326 ($312 above its halt), v37 -$743.
- **Still to do, in words first (the checklist), then the owner reads:**
  1. the stop set after the fill, from what was paid: 10c under it or 1c
     under the whole / half dollar beneath it - never from the decision print
     (v36b's 3% cap and the 1% floor today);
  2. protect a furious gain sooner than +30c (replay 10c / 15c / 20c);
  3. v37's gain counted from the bid, not a 1c print;
  4. premarket sells left working instead of cancel-and-resend each second;
  5. the recorder (every print and quote around each trade, every bot action
     to the ms) and the nightly audit from it;
  6. the adds on big runs (BIAF 10:07, INHD 10:31 rode with starters).
- The audit of today's trades: scratchpad audit1008 (parse.py, trades.json,
  summary.md) - rebuildable from the Render log.

## Earlier (10-07 night)


## Code
- Working branch: `claude/zealous-ramanujan-br3gay`. New work goes here;
  nothing goes to `main` without the owner's OK.
- **The day, final (7pm summary):**
  - v36 -$1,722 (-9.45%, $16,491), $99 above its halt;
  - v36b -$602 (-8.62%, $6,385), $96 above its halt;
  - v37 -$293 (-2.01%, $14,249).

  The 4:10pm figures were not final. After hours, 4:22-5:00pm, v36/v36b made
  8 furious full-size buys and lost them all (-$289 / -$204). r34.28's block
  is 9:30-4 only.
- **Tonight, done:**
  - the 10-07 bars (replay/data/2026-10-07, 132 names, aa15f03);
  - the logs (replay/live/2026-10-07_roster / _trades / _whynot, f8e23bf);
  - the review in words, memory/review_1007.md: the live rules, the
    checklist answered (H1-H29), contradictions (C1-C8), every loss tagged,
    the v37 SXTC bite, sale timing, the replay of 10-07, the scorecard
    proposal. The page: https://claude.ai/artifact/8YT1dAn77Nt346gUUUDgT7
- **WAITING ON THE OWNER BEFORE 4AM 10-08:** V36_NO_RTH_BUYS_ON covers 10-07
  only. From 9:30 on 10-08, v36/v36b furious full-size buys come back, and
  after hours was never blocked. Options in the review, section 10:
  - (a) v36/v36b premarket only, every day (recommended);
  - (b) a starter + adds outside premarket;
  - (c) as is.

  Any choice needs a release while flat after 8pm.
- **Other open decisions:**
  - releases after 8pm only, plus D (no buys 60s after a start);
  - furious size from a dollar risk, with the stop sized to the stock's
    swing;
  - C (buy-back waits);
  - S1-S4 (faster sales);
  - cents to percent on cheap stocks;
  - the scorecard;
  - a halt rule.
- Live on `main` (Render): VERSION v31-r34.28 (pushed 3:32:22pm ET 10-07 on
  the owner's "stop v36/v36b buys until 4pm"; flat since 2:55): no new
  v36/v36b buys 9:30-4 on 2026-10-07 only (V36_NO_RTH_BUYS_ON); v37,
  premarket and after hours unchanged. The day: v36 -7.9% ($16,780), v36b
  -5.7% ($6,588), v37 -2.0% ($14,247). By session: premarket v36 -$280,
  v36b -$156, v37 +$64; 9:30-4 v36 -$1,153, v36b -$243, v37 -$358. The
  furious full-size buys after 1:35 cost v36 -$932 in 6 trades; the deploy
  overlaps ~-$508. The 7-day replay's gains are premarket too (r34.23, fills
  0.2% / 1%: v36 premarket +$11,183 / +$9,190, 9:30-4 +$1,072 / -$121).
  Proposed to the owner (not chosen yet): furious full size premarket only,
  9:30-4 back to a starter + adds until a regular-hours design is built and
  tested; releases after 8pm only + 60s no-buy start. To analyze tonight.
- r34.27 (2:18pm) (pushed 2:17:50pm ET 10-07 on
  the owner's "Push r34.27 now"; all three flat at the broker): a sale that
  finds the broker holding none closes the position here, nothing booked.
  CPHI 2:11-2:17pm: during the r34.26 deploy the OLD process bought CPHI
  furiously (v36 3,552 @ $1.0654, v36b 1,487 @ $1.06; both sold, -$259 /
  -$70); the new process had adopted v36's CPHI 2s before the old one sold
  it, then tried to sell 0 shares on every print - v36's tick queue filled
  (19,999) and dropped ticks until r34.27. DEPLOY OVERLAP IS REAL: the old
  process keeps trading ~20-45s after the new one starts (1:56, 2:07, 2:11).
  Option D (no buys for 60s after a start) not chosen yet - raise again.
- r34.26 (2:12pm) (pushed 2:11:19pm ET 10-07 on
  the owner's choice "A"; flat at 2:10:28): v36/v36b furious buys use v37's
  fast buy (V36_FURIOUS_SWEEP, entry_buy) - one order at the ask + 20c (30c
  from $10), filled or dropped in 0.5s, the next furious print tries again
  0.5s after a miss. Worktree release22. The owner did NOT choose (open):
  B the furious stop as the larger of 10c and 2%; C a buy-back after a
  furious stop waits for the new high to hold 2s, at most 2 per stock per
  10 min; D no buys for 60s after a deploy (the old instance keeps trading
  ~20-40s after the new one starts - it did, 1:56pm).
- r34.25 (2:07pm, pushed 2:06:40 on the owner's "sell at market 9:30-4, as
  fast as possible"): the first sell goes straight out when nothing of ours
  was working; each sell logs "SELL n at MARKET" or "at a limit". Sells
  9:30-4 have been market orders since r34.17; premarket stays limits.
- SXTC 1:40-1:59pm, furious full positions: 8 trades, -$959 (v36 3 more after
  r34.24, -$377): fills above the print from v36's 6-second loop, the 10c stop
  inside SXTC's 20-50c swings, buy-backs 4s apart. Day at 2:10pm: v36 -5.9%
  ($747 above its halt), v37 -2.0%, v36b -4.3%.
- r34.24 (1:56pm) (pushed 1:55:20pm ET 10-07 on
  the owner's "Push r34.24 when flat"; flat at 1:54:45): exits, from SXTC
  1:40pm (v37 bought 625 @ $7.75, the top tick of a $7.15 -> $7.74 -> $7.17
  wick; stop $7.65 decided on a $7.49 print 6s later; the sale took 7.5s
  and three market orders, out at $7.29, -$290). A market sell is left to
  fill - Broker.follow(market=True) no longer cancels it after a partial
  fill and sends it again (send_market waits up to 6s); BID_STOP - the stop
  also fires when the middle of the live bid and ask is at or under it; a
  furious v36 buy's gain counts from the fill (v36b sold on a 37c "gain"
  measured from a stale $7.72 print). Worktree release20.
- r34.23 (1:36pm) (pushed 1:34:55pm ET 10-07 on
  the owner's "Push r34.23 when flat", after the owner saw the replay table;
  flat at 1:34:32): the owner's furious exit (~1pm, decisions) - a furious
  buy's stop 10c under what it paid, not 8% (V36_FURIOUS_STOP_CENTS; 8%
  stays the outer limit under $1.25); back in at once on a new high of the
  day while still furious (furious_new_high: one buy a minute and v37's
  60-second re-buy wait lifted for that); once up 30c, never back under the
  buy, and out on giving back 30% of the gain from the high
  (V36_FURIOUS_EVEN_AT, V36_FURIOUS_GIVEBACK; v36/v36b and v37's furious
  buys, V37_FURIOUS_EXIT); the 10-second leash kept. The whole / half dollar
  stop 1c under the level (V36_LEVEL_GIVE; the owner: "5.98 or 5.99"; 7 days
  replayed, 1c beat 2c and 5c for all three). Worktree release19.
  Replay, 7 days, $15k, fills 0.2% / 1% worse (r34.22 -> r34.23):
  v36 +$8,583 -> +$12,487 / +$5,410 -> +$9,016; v36b +$10,466 -> +$13,377 /
  +$7,244 -> +$9,826; v37 +$31,263 -> +$34,693 / +$19,122 -> +$20,019. MI
  10-05 is the biggest trade in every one. scratchpad sidebyside.py builds
  the table (names d0base_*, d1new_*, h1r23_*, c9split).
- To look at: v37's keep-trying buy at 12:25 (FFR) sent one order 20c over
  the $1.93 ask and nothing filled in its 0.5s (paper fills seem slower);
  proposed to the owner: 1 second a try on paper (V37_SWEEP_WAIT).
- r34.22 (12:36pm) (pushed 12:35:41pm ET 10-07 on
  the owner's "push them in right away, as soon as they are flat"; flat at
  12:34:45): the owner's stop and furious rules (12:20pm, decisions):
  "B" - a v36/v36b starter is sized so its first stop costs at most 3% of a
  normal starter (V36_STARTER_RISK; DKI 11:37's 16.6% stop lost $71); the
  stop sits 5c under the whole / half dollar under the buy and moves up to
  each level the price clears by 5c and holds 3s (V36_LEVEL_STOP,
  V36_LEVEL_GIVE; v36, v36b and v37); furious (speeding): the FULL position
  on the first hit (V36_FURIOUS_FULL), every entry check set aside -
  levels, wick, re-entry speed, score, 5% over the trigger, no candle
  pattern needed (V36_FURIOUS_ALL) - the stop within 8%
  (V36_FURIOUS_STOP_MAX), the 10-second leash at once, out on giving back a
  third once up 30% (V36_FURIOUS_SPIKE), deep premarket exits; the scanner's
  list in the log (ROSTER lines, all of it every 15 min) for the replay.
  Worktree release18. The 7-day replay of all three is running (fix1007
  jobs10.txt, names d0base_* / d1new_* / d2nolevel_v37).
- r34.21 (12:05pm) (pushed 12:04:59pm ET 10-07,
  the owner's "Push r34.21 when flat"; flat at 12:03:51; engine up 12:05:45):
  v37 keeps trying on FURIOUS movers only (keeps_trying = V37_KEEP_TRYING and
  speeding): one order a try at the ask + 20c (30c from $10), no price cap and
  no time limit, every print over the old high tries again, paced 0.5s a
  symbol (V37_RETRY_GAP) and 35 orders a minute an account (ORDER_BUDGET).
  Every other fast buy keeps the 20% safety net and the 6-second, 12-try loop
  (the owner: "only for furious movers... the rest keep it, a nice safety
  net"). The 7-day replay is unchanged by this (+$28,133 / +$16,539): 1-minute
  bars cannot show a 5-second chase - only live trading will. Worktree
  release17.
- r34.20 (11:58am) (pushed 11:57:59am ET 10-07, the owner's "Push r34.20 when flat"):
  the big moves - v37 fast buys from the
  breakout level (V37_ACCEL_FROM_HIGH) at the ask + 20c (30c from $10), retried
  for 6s within a 20% net (V37_SWEEP*), sized on the likely fill; a fast buy's
  premarket exit is a limit 10% under the bid (SELL_DEEP); trend checks with
  the live price (V36_TREND_LIVE); speed (V37_FURIOUS_SPEED on $250k) counts as
  the crowd, lifts the 6-buy cap and sets trend/tape/room aside for v36/v36b
  (V36_FURIOUS, V36_FURIOUS_SKIPS); the crowd counts trading minutes 9:30-4 only
  (V36_CROWD_TRADING; the owner: no halts premarket); a 5-second move logged;
  the r34.18 bug fixed (V37_HOD_CLEAR measured from the closed-candle high -
  v37 could not buy since 10:29); an add needs a NEW high that holds 2s (r34.19
  added on the way down, DKI 11:36); a sizing crash fixed. Worktree release16.
- r34.19 (10:56am): (pushed 10:55:42am ET 10-07 on
  the owner's standing instruction - agreed fixes go in at the next flat
  moment): an add waits for the price to hold at or over its level 2s
  (V36_ADD_HOLD_SEC); the floor still moves to the new average after an add
  and the sizes are unchanged (the owner's decisions). Worktree release14.
- r34.18 (10:29am): (pushed 10:28:34am ET 10-07,
  the owner's choice "Push r34.18 when flat", flat from 10:25:42): v37 needs
  the price over the old high by 2c or 0.5% (V37_HOD_CLEAR); a buy never
  reloads once the ask falls back to the old high (buy(floor=)); a fast buy
  needs the owner's speed >= ACCEL_SPEED and the 60/40 tape (WETO 9:52).
  Release worktree: scratchpad release13.
- Proposed to the owner (10:30, not decided): one gate of never-rules every
  buy passes whatever its route; a rule checklist logged with every buy
  and an automatic hourly/nightly audit; record prints and quotes so the
  replay sees seconds; fewer, slower releases; simplify to one entry
  pattern and one exit.
- r34.17 (10:16am): (pushed 10:15:54am ET 10-07
  at the owner's OK - "Push r34.17 now" - all three flat at 10:14:54): the
  exit. 9:30-4:00 every sell goes out at market (SELL_MARKET_RTH; a refused
  market order falls back to a limit); a sell never goes out on top of our
  own working order (Broker.wait_clear, CANCEL_WAIT 10s; settle waits 10s);
  no new buys 9:29-9:31 (OPEN_PAUSE). Release worktree: scratchpad
  release12. Still to build (tonight): an exit must not block the bot's
  data (the per-strategy tick worker awaits the chase); book every fill.
- r34.16 (10:07am): (pushed 10:07am ET 10-07 at
  the owner's OK - "Push with the 20% cap" - all three flat at 10:06): r34.15
  + no v37 fast buy more than 20% over the last closed minute's high
  (V37_ACCEL_CHASE, the BIYA 8:20 spike) + v36 remembers the real high of
  the day after a restart (seed_high; SXTC 9:29:39 bought $3.23 as a "new
  high" under $7.12). Release worktree: scratchpad release11.
- The owner wants every trade audited (right / wrong / fix), with a table by
  strategy: https://claude.ai/artifact/RXffPBQE7ZStZJo8JakA66 (after the
  fixes, updated through the day; data in scratchpad
  audit_1007/scripts/after_data.py) and the premarket audit
  https://claude.ai/artifact/9ZEU642xnxLiY5tQtCPUy4 .
- Live on `main` (Render): VERSION v31-r34.15 (pushed 9:20am ET 10-07 at
  the owner's OK - "the fixes we agreed on have to be implemented right
  away" - all three accounts flat at 9:19). The 10-07 fixes from the owner's
  live review: v37 - ripping skips the score only at speed 0.3+ and never
  over a red last candle; "half the gain" only after a 1c+ gain and with the
  bid agreeing; a buy needs the ask over the old high; prints outside the
  live bid/ask decide nothing. v36/v36b - re-entries only over HOD + 5c and
  at speed 0.1+; the #1/#2 leader making new highs is not held by the 6-buy
  cap; a red under the rip candle's open, or heavier than the rip, is no
  pullback; $x.00/$x.50: wait 5c past, held ~3s; no buy 5%+ over the
  trigger; the 3% stop from the price paid. Acceleration (SXTC): counts as
  the crowd for v36/v36b; v37 buys it at 4/10/35% of the account by speed
  (0.15/0.20/0.30), adds to 65% on a new high 2%+ up at speed 0.3+, a spike
  (+30%) sells on giving back a third. HISTORY_DUMP off. Left out: the
  runner "rides to half" (lost in the replay). Release worktree:
  scratchpad release10.
- r34.14 (00:14am 10-07): r34.13 + each account's September fills in the
  log at start-up (read; off in r34.15).
- r34.13: v36b = v36 with the 60% wick veto, the 3% first-stop cap and
  fresh exits, on AUES in place of v35 (the owner: v36 on two accounts side
  by side). T6HH's v36 unchanged - the three settings are per strategy now
  (V36.own). Logs say [v36b]; SLOT_V35=v35 brings v35 back.
- r34.12: v36's adds go right after a runner (a miss retries on the next new
  high, the limit from the ask, may pay half the minute's move when
  ripping). v36's score / first-two-buys / wick veto / stop cap / fresh
  exits: built, OFF.
- r34.11: v37 buys only at a score of 12 of 15 (speed 1/2/4 at 0.1/0.2/0.3
  with the price itself up 3%; candle, volume, trend, wicks, bodies, lows,
  MACD, room; red last candle or a huge wick = no buy; ripping skips it);
  each v37 buy logs its speed and score; at start-up v36 and v37 read
  today's fills back (buys per stock, v37's last sale) - worked at the
  3:46pm restart (v37: APUS 6 buys, IPDN 36, ...). Small fix pending: the
  "restored" log line lacks the [v36]/[v37] tag.
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

## Tomorrow (10-07), from 4am - each strategy on its own rules
- v37 (P28T), r34.11/r34.12: scanner name ($1-$20, up 10%+) in the top 2 by
  money in 5 min ($1M+) or the top gainer; above the real high of the day
  on a fresh print; up 3% in a minute on $250k+; volume 2x normal and 70%
  of the busiest of the last 5; confirmation 0/0/1/2 candles; 60s re-buy
  wait unless 30c up; SCORE 12 of 15 (speed 1/2/4 at 0.1/0.2/0.3 with the
  price up 3%; red last candle or a 60%+ wick = no buy; ripping skips it).
  A tenth to start, half at +10c, full at +20c (40% alone, 25% each of two).
  Out: stop a third of the last minute's move (3-8%); half the gain from
  the first cent; fresh prints only. Logs speed and score on every buy,
  SKIP lines with the reason.
- v36 (T6HH): as it ran 10-06 afternoon + the APUS add fix (r34.12, once
  released): crowd top 2 held 2 min / ripping / top-2 gainer $1M+; float
  20M or less; rip then pullback (1c over the last red's open) or a high-of-
  day break; over VWAP, 9 EMA over 20, MACD positive; tape 60/40; room; one
  buy a minute, 6 a stock, 2 stocks. A tenth to start, half at +15c, full
  at +20c (25%); a missed add retries from the ask, may pay half the
  minute's move when ripping. Out: stop under the pullback/breakout low; the
  average after an add, 10s short leash; trail after +10%. Score and
  first-two-buys rule OFF.
- v36b (AUES), r34.13: v36 exactly as above, plus no buy under a candle
  that is 60%+ top wick, the first stop no more than 3% under the trigger,
  and stops / the trail only on prints under 2s old.
- Watch: v37's scores vs results, its couple of runs paying for the cuts;
  v36's adds filling on a rip, and its share of stop-outs (93% in replay).

## Next (the owner, 10-07 morning: leave the bots alone today; fine-tune entries)
- After the close, on the branch, replayed on every day (today included),
  a range of settings, fills 0.2%/1% worse, against what is live:
  1. v36 + v36b: $x.00/$x.50 levels - add/start only ~5c past and held a
     moment; out when it hesitates at one; stay when it bolts through.
  2. v36 + v36b: once running (from the first add), out only on giving
     back half the gain - in place of the floor at the average.
  3. v37: the ripping exception only at speed 0.3+.
  4. v37: "half the gain" confirmed by the bid.
  5. v36 + v36b: the 6-buys-a-stock cap not for the #1/#2 name while it
     makes new highs (LPCN 7:21-7:35: "NO: 6 buys today" through $3.99).
  6. v37: the ripping exception never overrides the red-candle no-buy.
  7. v36 + v36b: a red "pullback" under the green's open on heavy volume
     is a failed rip - no buy (SPAI 8:09).
  8. v36 + v36b: re-entries (2nd buy on) only above the high of the day
     + 5c (built, off - V36_SETUP_BUYS/V36_HOD_PLUS; retest).
  9. v36 + v36b: re-entries need real speed (price up on volume).
  10. v37: "half the gain" arms only after a real gain (>= a full cent;
      test 1c/3c/1%) - SPAI 8:10 sold on a half-cent "gain".
  11. v37: skip a buy whose price re-read just before sending is well
      under the trigger (SPAI filled $4.81 on a $5.05 decision).
- The root cause (the owner, 10-07 ~8:40am: "on the surface it executed;
  dig and none of it was respected - fix that"): decisions on single
  prints taken as the live price. Plan, all three strategies:
  A. a price check before every buy/add/stop/"half the gain": drop prints
     outside the live bid-ask by more than a few cents, older than one
     already seen, or not regular sales; buy only if the ask still holds
     the trigger, sell on giveback/stop only if the bid confirms; re-check
     just before sending.
  B. the 11 rule fixes above.
  C. a daily execution report: decision price, bid/ask then, fill, exit
     reason; flag any trade where they disagree by ~1%+ or an exit whose
     rule was not met.
  Today's live cases (SPAI 8:09:58, BIYA 4:13:55, LPCN 7:00, ...) become
  permanent tests from the real prints - pull Alpaca's trade-by-trade for
  those moments into the log (read-only) at tonight's restart.
  Then the owner decides; release only with the OK, flat or after 8pm.
- End of day: v36 vs v36b by % of account; v37's exits vs what each stock
  did 5/15/30 min later.

## Waiting on the owner
0. v37 speed rule (0.1+): held off by the owner until "up 3%" has a big
   enough live sample; the branch logs the speed on every buy (not live yet).
0a. v36 (T6HH) vs v36b (AUES) side by side from 10-07: compare in % of
   the account (AUES ~$7,000, T6HH ~$18,200), trade counts, starters that
   never add, stop sizes. Replay: v36b +$2,272 / -$78 at fills 0.2% / 1%
   worse vs v36's +$1,540 / -$985. Live outranks it.
0b. Watch v37 on score 12 live: trades, win rate, the score and speed of
   each buy (ENTER lines); compare with the replay (75% won at 0.2%).
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
- Multi-day runners (the owner, 10-06: biotech on news, up to 1000%): no
  buys over $20 (PRICE_MAX); V31_FOLLOW_ABOVE_MAX (off) would let a name
  already on the day's list be followed above it - the owner's call.
- Round-trip runners, 90 days (Webull daily bars, 10-06): 247 stocks, page
  https://claude.ai/artifact/1Qv2hYjpmxZurmTUMPYABD (see journal).
- Later: the 3-month runs list (Massive data), fill-quality measurement,
  sell into strength, Level 2 via Webull, news, Chinese-stock early exit,
  half-dollar levels.
