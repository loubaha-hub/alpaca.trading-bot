# Where things stand

Updated 2026-10-07, 10:20am ET.

## Code
- Working branch: `claude/zealous-ramanujan-br3gay`. New work goes here;
  nothing goes to `main` without the owner's OK.
- Live on `main` (Render): VERSION v31-r34.17 (pushed 10:15:54am ET 10-07
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
