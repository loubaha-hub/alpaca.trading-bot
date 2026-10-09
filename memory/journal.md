# Journal

Decisions, instructions and results worth keeping. Newest first. Dates are ET.
Each entry: what was decided or found, the numbers, why, and where it lives.

## 2026-10-09

### The three bots live vs the speed strategy, 10-06..10-08 (~4:25pm; finding)
- replay/research/compare_bots_speed.py -> compare_bots_speed.txt. Bots:
  real round trips. Speed A (+ scale-out, new-high re-entries): replayed on
  the read around the bots' buys, $4,000 full (about $1,090 bought a trade
  on average; v36 $1,952, v36b $771, v37 $1,060).
- Whole days (trades, wins / losses, P/L): v36 94, 20/74, -$1,718; v36b 86,
  8/78, -$1,032; v37 141, 28/113, -$1,790; speed A 118, 10/108, +$3,347
  (10-06 -$1,080, 10-07 +$4,677, 10-08 -$250). Without SXTC's one trade
  (+$5,125) speed A is -$1,778 - about where the bots are.
- Premarket: v36 +$367, v36b -$238, v37 -$1,367, speed A +$3,975.
  Regular: -$1,653 / -$549 / -$413 / -$408. After: -$433 / -$246 / -$11 /
  -$221. Live outranks a replay; the speed strategy only saw the bots'
  stocks.
- Re-entries (speedsim_reentry.py, the day's high from the minute bars):
  the first buys +$4,492 (51), the re-entries -$1,145 (67) on a new high;
  over the high + 5c -$564 (34); + 10c -$184 (15); 60s after a sale -$159
  (17). Every re-entry rule loses on these days - the owner's point: the
  jumps in and out eat the runners' gains.

### The owner's middle ground - A at the start, B's leash once it is a runner (~4pm; finding)
- The owner: keep A's leash on every new entry; once the trade has bagged
  about 20% of gain, change to B's longer leash.
- Where A's 122 trades ended (scale-out on): 67 never traded over the buy
  (-$1,070), 49 were up under 5% (-$730), 4 up 5-10%, 1 up 10-20%, ONE up
  20%+ (SXTC +$5,125). And once a trade is up 20%, A and B exit the same
  way - the half-back line sits above both stops. So the switch on the
  trade's gain changes nothing on these days.
- Read instead as "the STOCK is already up 20%+ from its low in the window
  -> that entry gets B's leash (10% stop, 3c under the average after an
  add)": worse - 20%: +$2,361 (PRE +$3,230 / RTH -$552 / AFTER -$316); 30%:
  +$2,510; 50%: +$2,879; 10%: +$1,475; vs A everywhere +$3,309. The late
  entries on an extended stock sit near the top; the wide stop loses more
  (20%: 47 trades on B's leash -$2,276).
- So A is shaken out in the first seconds, not after a gain: the lever is
  the entry price (the buy at the ask lands on the top tick of the burst),
  not the leash. A proposal for later, words first.

### DECISION (the owner, ~3:50pm): A is the variant - the 3c stop, with the scale-out
- The owner: both catch the big runners; A loses much less on its small
  losers (about -$20 vs -$174) - "A is definitely superior".
- The speed strategy's variant from now on: speed entry; ease-in 20% / 50%
  at +10c / full at +20c; stop 3c under the buy (under the average after
  adds); half-back line from +10c; re-entry at speed on a new high of the
  day; the scale-out (a quarter at +100%, a quarter at +200%).
- Noted to the owner: on runs that wiggle (AIXI, XHG 9:37, INHD) B's wider
  leash kept part while A was shaken out; tonight's read (whole runs, top
  runners, BIYA, 10-09 - none used to design it) is A's check, B and B'
  shown beside it.

### Why A beats B three to one with the scale-out (~3:40pm; finding)
- The owner: A +$3,309 vs B +$1,246 - why? Both keep the same SXTC trade
  (+$5,125); the gap is the other trades. A: 121 trades -$1,815 - 111
  losses averaging -$20, 10 wins +$38. B: 63 trades -$3,879 - 20 wins
  averaging +$180 (the wider leash keeps part of AIXI, XHG 9:37, INHD...),
  43 losses averaging -$174; 24 of them after the adds -$6,044 (-$252 each:
  the full $4,000 position with the stop 10% under the average). With A a
  loss after adds averages -$53 (the stop 3c under the average).
- B wins on the runs (+$1,153 without SXTC vs A -$1,106) and loses on the
  rest (-$5,032 vs -$709).
- Tried: B' = a 10% first stop, then after an add the stop rises to the
  average less 3c: +$1,929 (PRE +$3,036 / RTH -$725 / AFTER -$381; runs
  +$3,436, rest -$1,507). The stop AT the average after an add: -$3,192 -
  ticks hit it at once, SXTC -$647. speedsim.run_ladder(add_floor=...).

### DECISION (the owner, ~3:20pm): the scale-out - in every study from now on
- The owner: once a trade is up 100%, sell a quarter (people are still
  buying fast - sell at the ask, not the bid); at 200% another quarter; the
  last half rides the half-back line, "so you gave only 25% back ... that's a
  good strategy, period". It cuts a little from the big winners but banks
  some of the others. Use it on all the studies; "let's see if we can
  implement that" - in a bot: words first (memory/checklist.md).
- Simulator: speedsim.run_ladder(scale=...) - resting sells at the average x
  (1 + gain), filled at that price when a print reaches it; no adds after the
  first part sold. replay/research/speedsim_scaleout.py -> speedsim_scaleout.txt.
- On the three days only ONE trade reached +100%: SXTC 10-07 8:16 (bought
  $2.18, adds $2.28 / $2.37, average $2.30; sold 434 at $4.61 and 434 at
  $6.91, the last 869 at $4.75 on the line): +$4,251 -> +$5,125, kept 52% ->
  63% of the run. Nothing else changes - it never triggers on the small
  losers. All windows, A: +$2,436 -> +$3,309 (PRE +$3,964 / RTH -$426 /
  AFTER -$229); B: +$372 -> +$1,246. Settings: +50% / +100% worse (A
  +$1,810, B -$253); +200% / +400% about the same (+$3,372 / +$1,309).
- The owner by hand (~3:30pm): never bagged a 1,000%, caught about 100% a
  couple of times and sold everything very quickly - sometimes leaving money
  on the table. Measured as "all at +100%": SXTC +$3,999 (vs +$4,251 on the
  line alone, +$5,125 with the scale-out); all windows A +$2,184, B +$121.
- The owner asked again: did the returns include the bots' small losers?
  Yes - the 72 windows are every stock-moment any of the three bots bought
  10-06..10-08, losers included; the speed strategy's own trades there
  ("the rest": A -$709 / 62 trades, B -$5,032 / 34). Not in: losers where
  no bot bought.

### BIYA 10-07 8:20 reopened - "that one would be a monster" (~3:10pm)
- The owner: if the strategy can keep a run like BIYA's it would be double
  SXTC's +$4,251 - "see what has happened and if we can keep it".
- The shape (recorded minute bars): 8:19 $2.43 -> $2.54; 8:20 $2.54 -> high
  $28.54, close $28.53 (790k shares); 8:21 open $28.56, high $33.96, low
  $7.29, close $8.20; 8:23 $3.74; 9:05 $1.92. Up and down in about two
  minutes, premarket (no halt).
- Why no bot bought (Render 10-07 12:18-12:24 UTC): v36 / v36b "NO: 6 buys
  today" every minute (the cap, spent on BIYA's 4am whipsaws - removed
  10-08, V36_MAX_ENTRIES = 0); v37 did not look (crowd #4, it wanted #1/#2).
  The bots saw $2.62 at 8:20:37 and $9.24 at 8:21:26.
- Would the speed strategy keep it: its entry fires early in the 8:20
  minute; the question is the exit - the half-back line would sit near $18
  under a $33.96 peak, and in the 8:21 minute the price fell $28 -> $7. A
  rough range for the full $4,000 plan at about $2.75 (~1,450 shares): sold
  at $8 about +$7,900; at $15 about +$17,800 - IF the adds filled near the
  plan's prices. Only the seconds can say: tonight's read has BIYA 8:10-9:10
  with every trade and quote from 8:19:30 to 8:21:00 (SEC_DUMP_MISSED).
- A proposal to test (words only): resting sells above the market - a
  quarter at +100%, a quarter at +200% over the average - bought by the
  chasers on the way up; after the top the bids vanish. Touches the
  half-back line (the rest rides it) and "the longer it runs, the longer
  the leash" for that half only.

### B's big losers trade by trade - the adds bought the top of the jump (~3pm; finding)
- The owner: IPDN -47%, XHG -42%, FRGT -20%, WHLR -32% (10-06), BIYA -23%
  (10-07) - one entry or many? (The % is of the run's size, not of money:
  IPDN ran $3.89 a share, the trades lost $1.83 a share added up, -$511.)
- replay/research/speedsim_trace.py -> speedsim_trace_B_losers.txt:
  IPDN 4 entries: +$55; -$402 (bought $4.55, both adds within a second at
  $4.75 / $4.67 -> 856 shares at $4.67, stopped $4.20); -$82 and -$82
  (starters at $6.89 / $6.93, the day's top). XHG 8:32 2 entries: -$116
  (bought $3.64 in the spike, the bid fell to $3.11 in one second); -$444
  (bought $3.75, BOTH adds at $4.31 - the spike's top - 955 shares at
  $4.19, out $3.72 15s later). FRGT 3 entries: -$62 (bought $0.72, both adds
  at $0.935, +30% in one jump), +$76, -$133. WHLR 1 entry, -$80: a clean
  10% stop, the top of a 4am burst. BIYA 10-07 1 entry, -$192: bought $2.70,
  added $2.81, out $2.50 (it went to $2.31 - the exit was right, the add
  doubled the loss). BIYA's $2.54 -> $33.96 at 8:20 is NOT in this read (no
  bot bought there); it is in tonight's read - the investigation reopens
  with it, and why the bots did not buy (10-07 logs, Render keeps 7 days).
- The cause: the ease-in steps are +10c / +20c over the first fill; when the
  price jumps past both in one second, both adds fill at once at the top -
  80% of the position at the highest price, the stop under that average.
  In cents the steps mean +14% / +28% on a 70c stock, +1.4% / +2.8% on $7.
- speedsim_adds.py -> speedsim_adds.txt, all 72 windows: the adds make the
  money AND the big losses. B: as planned +$372 (PRE +$1,249 / RTH -$194 /
  AFTER -$683); no add past the step + 5c +$663 (+$2,388 / -$1,042 / -$683);
  no adds -$11. A: +$2,436 / +$2,505 / -$521. SXTC: +$4,251 with the adds,
  +$528 to +$860 without. Capping helps premarket, hurts regular hours -
  not a clean fix on three days.

### The whole picture: the runs AND the bots' losers, and the give-back (~2:40pm; finding)
- The owner's questions: did the test include all the small losers the bots
  picked? did our entry pick up the big winners? how much did A and B give
  back? And a third group not yet in: the losers NO bot picked, where the
  speed strategy would also have bought.
- replay/research/speedsim_giveback.py -> speedsim_giveback.txt. The read is
  72 windows = every stock-moment the three bots bought 10-06..10-08,
  winners and losers. The speed strategy trades in all of them (its own
  entries). A (3c stop): 122 trades +$2,436 = the runs +$3,145 (60 trades),
  the rest -$709 (62 trades, -$11 each). B (10% stop): 64 trades +$372 = the
  runs +$5,404 (30), the rest -$5,032 (34, -$148 each). By session, all:
  A PRE +$3,091 / RTH -$426 / AFTER -$229; B +$1,249 / -$194 / -$683.
- The entry: it bought inside 17 of the 20 runs of 40%+ (no trade on WORX;
  RUBI and NXAT signalled after the top). The exit: premarket, A was up at
  its best 15% of the run (averaged over 12 runs), gave back 21%, ended -7%;
  B up 26%, gave back 33%, ended -7%. Regular hours: A 3% / 13% / -10%; B
  38% / 30% / +9%.
- Not in yet: the losers no bot bought. To have them: log every speed
  signal on the whole list live (no orders) and read those seconds at night
  - or shadow-trade the strategy live. A proposal, words first.

### Does the speed strategy catch the runners and keep them? (~2:10pm; finding)
- The owner's questions: does it catch them and keep them; why it lost on
  AIXI / IPDN / XHG / FRGT 10-06; by stock, how much of each run it bagged.
  "There is more than one running almost every day ... if we are good at
  keeping that one in the bag up to near the top, it will pay for all our
  small costs."
- replay/research/speedsim_bag.py -> replay/live/2026-10-08_secdump/speedsim_bag.txt.
  The 19 runs of 40%+ inside the windows read (slices: 35 minutes around a
  bot buy), each window apart. A = 3c stop, half from +10c; B = 10% stop,
  half from +10% of the price. Kept = cents a share over the run's cents.
- CATCH: yes - it bought inside 17 of the 19 runs. KEEP: no, except SXTC
  10-07 8:14 ($2.00 -> $6.69; one trade $2.30 -> $4.75 = 52% of the run,
  +$4,251 - it jumped $3.00 -> $6.64 in 2 seconds, the stop never came
  into it). With A the rest kept -36% to +8% (net of all their trades).
- WHY IT LOST on 10-06: the stop sits inside the stock's second-to-second
  swing. AIXI: 13 trades, 8 out within 1 second, the run went on 10% higher
  within 5 minutes after 10 of the 13. IPDN: all 9 bought the top tick (it
  never traded over our fill); 7:26:52 spread 17c, sold 36c under the fill
  in the drop; the steady climb 7:33-8:04 ($4.36 -> $5.83) never gave a new
  speed signal, so no re-entry. XHG 8:32: four buys in 20 seconds of a
  one-minute spike ($2.27 -> $4.31), then $2.53 three minutes later - a
  spike and dump no stop keeps. FRGT ($0.30, under the $1 band): the adds at
  +10c / +20c (14% / 28% on a 70c stock) put the average near the top, the
  floor at the average sold the first dip (-$230). Each shake-out pays the
  spread plus the slip at the bid in a falling second, 5-36c a share.
- By session, the 40%+ runs only: A - PRE 12 runs 45 trades +$3,363; RTH
  6 runs 14 trades -$204; AFTER 2 runs 1 trade -$15. B - PRE 20 trades
  +$3,793; RTH 9 trades +$1,370; AFTER 1 trade +$241. Without SXTC: A about
  -$1,100, B about +$1,150 on the runners. But B across ALL windows was
  +$372 (speedsim_stops.py): the 10% stop costs about -$4,700 over three days
  on the windows with no runner - the runners only just pay for it.
- Kept by B (a wider leash) where A kept nothing: AIXI 10-06 18% of the run
  (+$680), XHG 9:37 35% (+$696), INHD 22%, VCIG 14%, PFAI 12%; but IPDN
  -47%, XHG 8:32 -42%, BIYA -23% 10-07.

### STANDING INSTRUCTION (the owner, ~1pm): every table split by session
- "Every table we construct from now on": three compartments - PREMARKET
  (4:00-9:30), REGULAR HOURS (9:30-4:00), AFTER HOURS (4:00-8:00pm), by the
  entry's time. The owner's reasons: premarket has the news (the catalyst
  that makes a stock fly) and no LULD halts; in regular hours a halt stops
  the runner you ride, people lock in gains on the reopen and it throws you
  out. Thinner trading and wider spreads premarket are real but the two make
  up for them, and on the big runners the spread erodes the gain less.
- Seen today: Alpaca's daily bars are regular hours only (10-01: XRTX
  premarket high $2.00, daily high $1.75) - a premarket runner (BIYA 10-07
  $1.70 -> $33.96 before 9:30) is invisible in daily gainers lists, the web's
  "closed up X%" lists included.

### The day's top runners go into tonight's read - r34.40 (~1pm)
- The owner: get the top runners (200-500%) of the last three days (later
  ten) and include them beside the bots' own entries; cherry-picking the big
  ones biases the result, "but that still gives us a very good idea"; the
  simpler and barer the strategy, the more likely it bags the big runners.
- Second by second IS available for any stock (Alpaca SIP - the read is not
  limited to what the bots bought; Webull is not needed).
- r34.40 (branch, 678 tests pass; read-only): per day 10-06..10-09 every
  listed name's hourly bars, then the 1-minute bars of the biggest rises and
  of the names found by hand (web + recorded bars: AIXI, XHG, IPDN 10-06;
  BIYA, SXTC, PFAI, DKI, LGCL 10-07; DKI, FLYE, JZ, AIXI 10-08; VIVK, VEEA,
  NTCL 10-09). A runner: x1.8+ from a low to a high within 150 minutes, $5M+
  traded, $1-$20. The six biggest a day are read from 10 minutes before the
  low to 30 after the high; every runner found is logged (SECDUMP RUNNER).
  About 2 hours of reading at 100 requests a minute. Needs the owner's OK to
  go to main after 8pm.
- From the recorded bars (10-06/07 scanner names): 10-06 AIXI $1.52 -> $4.47
  (4:01-4:27), XHG $1.90 -> $5.51 (to 9:45), IPDN $3.04 -> $7.10 (6:18-8:35),
  SDEV, APUS; 10-07 BIYA x20 (8:20), SXTC, PFAI $2.22 -> $7.02 (9:45-12:24),
  DKI $1.27 -> $3.64 (9:30-12:03), LGCL $2.22 -> $4.53 (7:44-9:42).

### The speed strategy by session, and on the big runs already in the read (~1:10pm; finding)
- replay/research/speedsim_study.py (every table PRE / RTH / AFTER) and
  speedsim_stops.py; results replay/live/2026-10-08_secdump/speedsim_sessions.txt,
  speedsim_stops.txt. Speed only, ease-in, new-high re-entries, $4,000 full.
- 3c stop / half from 10c: PRE 75 trades +$3,091; RTH 29 -$426; AFTER 18
  -$229. Regular and after hours lose in every setting tried. But PRE is
  SXTC (+$4,130): without it PRE is about -$1,000 (-$15 a trade, like RTH).
- The big runs inside the windows: AIXI 10-06 ($1.69 -> $4.42, 13 trades
  -$343), IPDN 10-06 ($3.10 -> $6.99, 9 trades -$219), XHG 10-06 ($1.95 ->
  $4.30, -$202), FRGT 10-06 (-$189); only SXTC 10-07 kept (+$4,130). Why:
  74% of the trades are out within 5 seconds, the best price the fill
  itself - the buy at the ask lands on the top of a one-second burst, and a
  few cents of stop sit inside the stock's second-to-second swing.
- Stops tried: prints only (not the mid) - no change; 5c / 10c - fewer quick
  outs, about the same; 5%, 10%, 15% of the price - quick outs 3%, but each
  loss bigger: -$540 / -$257 total. 10% stop and half from +10%: AIXI +$632,
  XHG +$136, IPDN -$511, total +$372. Nothing survives without SXTC yet.
- Tonight's read (whole runs, not 35 minutes around a bot buy) is the real
  test; this one only saw slices of the runs.

### DECISIONS (the owner, ~8:50am): the line stop stays; v37's money bar stays
- VEEA 7:00 bought 5c over $5.50; the line stop ($5.49) was tighter than the
  furious 10c leash and took it out at $5.49 before the run to ~$6.13. The
  owner: breaking $5.50 matters on any stock; out at $5.49 "is okay ... not
  something we would really change."
- MI 4:32: v37 bought late ($1.45, 19% over the $1.13 high) because both its
  doors need $250k traded in the last minute. The owner: "that's okay too" -
  lowering it would get in the way of other moves; if we keep missing the
  early start of moves, lower it a little ("the speed is what counts more").
  No rush.
- The owner on the day: the rules are being followed, "that is really key";
  modify them a little, not in a rush. Asked for the suggestions distilled
  and simple, to discuss for over-fitting: memory/proposals_1009.md (two
  proposals - buy at the ask for all three; a quick stop-out does not use up
  the leader's pattern buy - two measuring tasks, two dropped).
- The day's blow by blow (VEEA, MI): memory/review_1009.md.

### The owner's three-candle 2:1, defined (~9:10am) - not in the bot yet
- Green, red, green: entry where the third candle reaches the top of the
  red's body; risk to the bottom of the red's whole wick; gain to the top of
  the wick of the green before the red; gain at least 2x risk, or no buy.
  "It's a good rule to have." The bot's room check (V35_ROOM_RR) measures to
  the PREVIOUS day's high only. Words and holes: memory/proposals_1009.md #3.
- The owner (~9:20am): keep yesterday's high as a wall; take the nearer of
  the two (the green's wick top or yesterday's high) - under 2x the risk, no
  buy. Today's high is not a separate wall. Do not stack rules until the bots
  are paralyzed: a very good move must not be blocked - discuss before adding.

### Did the speed strategy bag SXTC's run? Yes - half of it (~1:55pm; finding)
- The owner: "didn't the one without a filter run it all the way to the top
  and take half? ... if it was able to bag the bigger one, we are in for
  something that may be useful" - keeping big runners is what the bots fail.
- SXTC 10-07, speed only, ease-in, 5c / half from 10c: buy 8:14:37 $2.18
  (20%), adds at about $2.28 and $2.38 -> 1,737 shares at $2.303 ($4,000);
  held through the climb to $3.00 (8:16:37), then $3.00 -> $6.64 in two
  seconds (8:16:39-40) and the $7.07 top at 8:16:44; sold on the way down at
  8:17:02 at the bid $4.75 (the half-gain line $4.69): +$4,251 - $2.45 of the
  $4.77 a share it rose over the average, about half, as designed.
- The data is real: 11,577 prints in 8:16:30-8:17:10, the quotes moving with
  them (bid $4.21 / ask $4.22 at 8:16:39, $6.33 / $6.38 at 8:16:40); the bots
  bought SXTC at 8:16:33-37 themselves. The whole run lasted 2.5 minutes;
  1,737 shares against 25-47k shares a second traded at the sale.
- So the exit design (small start, adds on strength, half the gain) can bag
  a big runner - the piece the bots miss. The entries (speed alone) bleed in
  between: about -$1,700 to -$1,900 in three days without SXTC. Profitable
  only if an SXTC-size run comes often enough - more days decide.

### Speed alone vs the crowd alone vs both (~1:45pm; finding)
- The owner: the crowd and the speed are two separate things - test each
  alone; the combination "is not the winner".
- speedsim.play_ladder_crowd (crowd only: a buy on a new high while in the
  top N by money, or the moment it joins the top N; re-entries on new highs
  while in the top N; no speed test). Same ease-in, $4,000, three days.
  | trigger | trades | 3-day P/L, range over 5 settings | without SXTC 10-07 |
  | speed only | 83-198 | -$1,837 .. +$2,436 (positive only via SXTC) | -$1,281 .. -$2,808 |
  | crowd only, #1 | 134-389 | -$2,678 .. -$1,494 | -$2,461 .. -$1,281 |
  | crowd only, top 2 | 201-612 | -$3,384 .. -$2,000 | -$3,239 .. -$1,805 |
  | crowd only, top 3 | 236-730 | -$4,352 .. +$1,260 (positive only via SXTC) | -$4,181 .. -$1,550 |
  | both, #1 | 30-58 | -$524 .. -$255 | -$426 .. -$150 |
  | both, top 2 | 46-106 | -$737 .. -$474 | -$597 .. -$323 |
- Reading: speed is the trigger that caught the one big run early; the
  crowd alone buys the most and loses the most (new highs while in the crowd
  = tops, again and again); both together trade the least and lose the least,
  but never made money in these three days. File:
  replay/live/2026-10-08_secdump/speedsim_speed_vs_crowd.txt.

### ... + re-entry only at speed on a new high of the day (~1:25pm; finding)
- The owner: re-entry is allowed as often as it comes, per stock - but it
  must wait for a new high of the day ("that one, it's a must").
- speedsim.play_ladder_hod: first buy on speed; after a sale, back in only
  when speed is on AND the price makes a new high (the window's high so far -
  the read starts 5 min before the bots' first buy, so an earlier high of the
  day is not seen).
  | filter | stop / half from | trades | won | P/L | without SXTC 10-07 |
  | none | 3c / 10c | 122 | 9% | +$2,436 | -$1,694 |
  | none | 5c / 10c | 103 | 9% | +$2,171 (SXTC 8:14 +$4,251) | -$1,911 |
  | crowd top 3 | 5c / 5c | 95 | 24% | -$1,273 | -$696 |
  | crowd top 2 | 5c / 5c | 75 | 27% | -$474 | -$323 |
  | crowd #1 | 3c / 10c | 44 | 11% | -$255 | -$150 |
  Same picture: positive only with SXTC's early entry (no filter); every
  crowd-filtered version loses; the new-high rule trims the churn but does
  not flip a result. The 10c steps are large on sub-$1 stocks (FRGT 10-06,
  $0.72 first fill, the add filled in a jump, -$402), and adds into a gap fill
  far above the step (SXTC 8:16:37 $3.00 -> average $4.20, -$404).
  Output: replay/live/2026-10-08_secdump/speedsim_hod_rebuy_run.txt.

### ... + the day's top names (~1:10pm; finding)
- The owner: only stocks that are moving and where the crowd is - the
  day's #1-#3 by money (and/or the top 3 gainers), up 10%+.
- replay/research/ranks.py ranks each minute: money in the last 5 closed
  minutes among the day's names (10-06: 79 names, 10-07: 132 - the recorded
  bars from claude/zealous-ramanujan-br3gay; 10-08: only the 17 traded names).
  Gainer ranks need the previous close, missing for 94 of 206 signals (SXTC
  10-07 among them) - the gainer / up-10% filters are not trustworthy here;
  the crowd filter is (every window's stock was on the up-10% list).
  | filter | stop / half from | trades | won | P/L |
  | none | 5c / 10c | 129 | 10% | +$2,323 (SXTC 10-07 +$3,967; without it -$1,644) |
  | crowd top 3 | 5c / 5c | 100 | 24% | -$625 |
  | crowd top 2 | 5c / 5c | 85 | 25% | -$425 |
  | crowd #1 | 5c / 5c | 57 | 23% | -$333 |
  Every filtered version loses (-$333 to -$1,784 in three days); losses small
  and spread out. Why: the crowd comes late - SXTC 10-07 was #6 by money when
  its run began ($2.18, 8:14:36), #3 at 8:16:32 ($2.87, shaken out -$8, the run
  to $7.07 went on without it), #1 at 1:40-1:59pm near its top (9 tries, all
  stopped, -$155). Files: speedsim_crowd_run.txt, speedsim_filters_run.txt;
  replay/research/speedsim_ranked.py.

### The speed strategy with the owner's ease-in (~12:40pm; finding)
- The owner: "I hate to add rules, but smart simpler rules might help" - 20%
  of the position at the speed buy, to 50% at +10c over the first fill, full
  at +20c (cents, not percent, so $1 stocks are not skewed). Floor at the
  average after an add; half the gain; back in on the next burst.
- speedsim.py ladder, same 72 windows, full = $4,000:
  | stop / half from / back in | trades | won | P/L | without SXTC 10-07 |
  | at the buy / 1c / yes | 202 | 8% | -$1,360 (was -$6,764 at full size) | - |
  | 3c under / 10c / yes | 154 | - | +$2,402 | -$1,625 |
  | 5c under / 10c / yes | 129 | 10% | +$2,323 | -$1,644 |
  | 5c under / 8c / yes | 137 | - | -$1,760 (SXTC cut early: -$275) | -$1,485 |
  | 10c under / 10c / yes | 118 | 22% | +$573 | -$3,340 |
- The ease-in cuts what the failures cost to about a fifth. Every positive
  version is one trade: SXTC 10-07 8:14 first $2.18, avg $2.30 after both
  adds, best $7.07, +$4,251. Without it every version loses $1,500-3,400 in
  three days; arming the half-gain exit at 8c instead of 10c turns +$2,323
  into -$1,760 - fragile. The question is how often an SXTC-size runner comes
  and whether it is ridden: needs 10-09 (VIVK, MI, VEEA, NTCL - tonight's
  read) and more days. Output: replay/live/2026-10-08_secdump/speedsim_ladder_run.txt.

### The owner's simple speed strategy, tested on the three days (~12:20pm; finding)
- The owner: a simpler strategy - buy only at speed (the furious test, no
  patterns, no spread / liquidity checks), out when it comes back to the buy
  (or the floor after adds), else on giving back half the gain ("the longer
  it runs, the longer the leash"), back in at once on the next speed burst.
  Test only on the days with second-by-second data (minute bars would paint
  it rosy - the owner).
- replay/research/speedsim.py on SEC_DUMP's 72 windows (10-06..10-08; only
  around the bots' buys): 206 speed signals; $4,000 a trade; buy at the ask
  1s after the signal, sell at the bid 0.5s after the decision.
  | stop / half the gain from / back in | trades | won | P/L |
  | at the buy / 1c / yes | 202 | 8% | -$6,764 |
  | 2c under / 5c / yes | 172 | 15% | -$5,975 |
  | 5c under / 5c / yes | 140 | 29% | -$4,374 |
  | 10c under / 1c / yes | 164 | 24% | -$2,446 (one trade, SXTC 10-07 8:16 $2.87 -> best $7.07, +$2,925; without it -$5,371) |
  | first signal only (no re-entry), 2c / 5c | 51 | 20% | -$2,229 |
  Every variant loses on every day but one (10-07 with the 10c stop, SXTC).
  The average loss is about $40-57 a trade = the spread and the sale at the
  bid (1-1.4% of $4,000); a stop at the buy price is hit at once on most
  buys - the bought print is the top of the burst. Re-entering at once
  multiplies the trades (202 vs 51) and the losses. Output:
  replay/live/2026-10-08_secdump/speedsim_run.txt.

### The owner on the research (~10am): keep our method, fine-tune it
- The research gave "the full picture of what's out there"; sources from
  people selling courses, signals or algorithms are not reliable by any
  measure - good to know. Direction: keep doing what we do and fine-tune it.
  The daily losses have shrunk with the tweaks (10-07: v36 -9.45%, v36b
  -8.62%; 10-09 at 9:16am: v36 -1.3%, v36b -0.4%, v37 -0.7%). Next: make the
  method more efficient and find a way to keep the runners and raise the
  returns on the high runners. The owner will think and bring more ideas.
  Report: reports/Small cap momentum strategy evidence.md; the map:
  https://claude.ai/artifact/PT9fPxUXei5HVJsBRoKGDG

### Standing rule (the owner, ~9:35am): don't throw the baby out with the bath water
- Too many rules stacked on each other paralyze the bots: they let a lot of
  good moves go. A check that removes a few bad trades but blocks good moves
  is not worth having. Every proposed check is judged on both sides, over
  days: the losers it removes and the good moves it would have blocked.
  Added to CLAUDE.md's standing rules (no over-fitting).

## 2026-10-08

### DECISION (the owner, ~10:35pm): furious 25% then 50% of the account; v37 fast 20% then 40%
- Corrections to r34.37: "you cannot start with that small of a position":
  v37's fast buys under furious speed 20% of the account (were 8%), built to
  the full 40% by the +20c add; v36 / v36b furious 25% of the account first
  (were 12.5%), the add (+20c over the buy, a new high) to 50% of the
  account; v37 furious 32.5% then 65% ("the 65 you have is good"). Regular
  buys unchanged (20% of a full position: v36/v36b 5%, v37 8%).
- r34.38: V36_FURIOUS_PCT 0.50 (a furious position's full size), add_step
  sizes a furious add from it, the self-check cap for v36/v36b raised to 60%
  (else a 50% position logs a false VIOLATION); V37_ACCEL_SIZE 0.20 / 0.20 /
  0.325. The owner: "Perfect. That's it."

### DECISION (the owner, ~10:20pm): ease in 20 / 50 / 100; furious 50% then 50%
- "Regular: 20%, then 50%, then all. Furious: put in 50% first; it starts to
  move and moves really nicely - the other 50%." Then: "after you have tested
  everything ... deploy, push it to main."
- Built (r34.37): V36_STARTER / V37_STARTER 0.10 -> 0.20 (the adds as before:
  v36/v36b to 50% at +15c, all at +20c; v37 +10c / +20c). v36/v36b furious:
  V36_FURIOUS_FIRST 0.50 - half a full position (12.5% of the account), the
  rest is the last add (+20c over the buy on a new high, as a regular buy's);
  after it the floor rises to the average (V36_FLOOR_AVG, as for any add).
  v37: V37_ACCEL_SIZE (0.15, 0.08), (0.20, 0.08), (0.30, 0.325) - under
  furious speed a regular 20% start; furious half of its 65% (the owner's
  10-07 "60-70%"), the rest on its add (still furious, a new high 2% over).
- v37's spike test now sells at 30% back of a $1+ gain (BIG_GAIN, r34.36),
  a little before the spike rule's third.

### DECISION (the owner, ~10:25pm): the 10c leash on furious buys - v36b and v37
- v36b: "that's it, perfect" - 3% on regular buys (cuts the losers that go
  nowhere), v36's 10c leash on furious buys. v37: "the exact same thing - 3%,
  and 10c for the furious one; when the stock starts moving it doesn't stop
  with 3%". Built: FURIOUS_TEN_CENTS (furious first stop = 10c under the
  fill, not the tighter of 10c and 3%); V37_STOP_MAX 0.08 -> 0.03 (v37's
  regular stop 3%). The whole / half dollar line under the buy still counts.
- v37's 5c cut stays on its furious buys - it sells before any 10c stop.
  Replayed, v37's 12 furious buys with data: 5c cut -$751 (3% or 10c the
  same); 10c leash + 30c/30% exit without the cut -$1,758. Told the owner;
  "that's great, let's do it that way" (~10:30pm).
- The owner: "implement all of this and make the strategies ready to deploy
  tomorrow at 4am" - r34.36 to main tonight (flat, after 8pm).

### DECISIONS (the owner, ~10:15pm): +$1 then 30% back; v37 two green candles; v36b as is
- "For the one dollar ... we'll go with that ... gain more than a dollar, we
  revert to thirty percent": BIG_GAIN_AT 1.00 / BIG_GAIN_BACK 0.30 - once the
  best price since the buy is $1+ a share over what we paid (the average),
  out on 30% of that gain back, the bid agreeing. All three; it bites on
  v36 / v36b's regular buys (the ABR trail); furious 30% and v37's 5c sell
  sooner anyway.
- v37: no three candles - it jumps in as the move comes; "only buy after two
  green candles, unless it's a furious move ... just what I described":
  V37_TWO_GREEN - the regular buy needs the last two closed 1-minute candles
  green, unless furious (the fast buy needed two green already). Measured
  (clean/two_green.py, candles from SEC_DUMP seconds): 73 of 134 buys had two
  green (-$860 live, -$11.8 a trade); it drops 57 regular buys (-$263, -$4.6
  a trade) - fewer trades and a smaller total loss, not better trades.
- v36: entry kept as is. v36b: "a little more flexibility, five cents, after
  that 10 - let's compare": its stop stays (3% under $3.33, 10c from there),
  now buying at the ask. Tomorrow: v36 (pays up, 10c) vs v36b (at the ask, 3%).

### The owner: from +$1 a share captured, give back a third, not half (~10pm)
- "Not the stock up 100% - us capturing a hundred cents: the stock up a whole
  dollar from our buy - then the trailing stop from a half to a third, to
  protect the gains." Words sent back to confirm (which bots it touches):
  v36/v36b furious already give back 30% from +30c, v37 5c from its best;
  only v36/v36b's regular buys (the 2-ABR trail from +10%) can give back more.
  In 3 days one trade got past +$1 a share (v36 DKI 6:54, +$1.34 kept).

### DECISION (the owner, ~9:50pm): buy at the ask - v37 and v36b
- "Buy at the ask is in ... that's a given." Built in r34.36 (BUY_AT_ASK =
  ("v36b", "v37")): every buy of theirs is a limit at the ask of that moment -
  fast buys no cents over (were +20c / +30c from $10), v37's other buys no
  10c over (V37_ASK_PLUS), v36b's other buys not 0.2% over. Retries, sizes,
  stops, exits unchanged. v36 pays up as before (the control).
- The owner on v36b: "v36 has an edge over v36b at the entry ... v36b is
  always shaken" - to discuss, simpler, before anything goes in.
- The owner on v37 (~9:55pm): the 5c leash instead of 1c (live since
  6:02pm), plus v36's features - start with the three-candle setup, after
  that only over the day's high + 5c - to discuss.

### The owner: what is clean for 10-09 - v37's buy, v36b's leash (~9:40pm)
- The owner: v37 loses "nonstop in that one cent" - change its entry now; v36
  beats v36b because of its leash up front - do something for v36b's entry.
- v37's 1c: already gone - "half the gain from 1c" (10-08: -$742, 0 of 19
  won) was replaced by the 5c cut (-$290 on the same trades), live since
  r34.35 6:02pm; 10-09 is its first day. Over 3 days the 5c cut won 10-08 only
  - no exit makes v37 profitable; its losses are at the buy.
- v37 buying AT THE ASK instead of ask + 20c (scratchpad clean/payup2.py,
  payup3.py; sizes counted, kind - first in line): 114 trades -$1,349 ->
  -$525..-$848, better on each day, 89-99% of shares bought. Words in
  memory/words_buy_at_ask.md (proposal; the owner reads first).
- v36b's 10c leash, replayed with v36's real exits (10c / line stop / 10s
  leash / 30c-30% / trail; clean/leash.py), 40 furious buys with data: v36b's
  22: 10c -$606 vs its 3% -$586; v36's 18: 10c -$1,605 vs 3% -$1,269. The
  wider stop gives back on the failures what it saves on the one that comes
  back (IPW 4:10 +$70 vs -$53; FLYE 7:22 is in the missing data). From
  $3.33 up both already use 10c (it is tighter there). Not clean - the
  owner's call. v36b's furious buys at the ask: -$586 -> -$371..-$424.

### The list: what we agree on, what is left (~9:35pm)
- The owner asked for everything from the afternoon sorted: decided, going
  out tonight, tested and dropped, candidates with an edge. Written in
  memory/now.md ("The list"). The owner on news: "just let them go into
  the log" - good-looking news often fizzles; information only.
- Times on tonight's entries corrected (they ran ~20-50 min ahead).

### The owner: trade premarket, stop at 9:30 (~9:20pm; when to switch: asked)
- On the session table: "very, very important ... if the system works, we
  can even start shutting it off at 9:30. Starts at 4am" - the guru never
  trades after 9:30: over 20 years he kept the hours that made money and
  dropped the ones that lost. Also wants news and short squeezes in
  ("short squeezes add fuel to the fire").
- Code: V35_ENTRY_END exists but V36 and V37 have their own maybe_enter, so
  it does not reach them; a cut-off for all three needs a small change in
  entries_allowed().

### The owner's factors at each buy, and the time of day (finding, ~9:15pm)
- Data: Webull 1-minute bars 4am-8pm for the 41 stock-days v36/v36b traded
  (replay/live/2026-10-08_secdump/bars/); replay/research/factors.py.
- By session, live, 3 days: v36 premarket 47 trades, 30% won, +$367 (+$7.8
  a trade; 10-07 -$280, 10-08 +$647); regular hours 36, 17%, -$1,653
  (-$46 a trade); after hours 11, 0 won, -$433. v36b: -$238 / -$549 / -$246
  (0 of 8 after hours). v37: -$1,367 premarket (99 trades on 10-06) / -$413 /
  -$11.
- The owner's factors (v36, 69 trades with 30+ minutes of bars): EMA9 over
  EMA20, MACD over zero, over VWAP - nearly every buy had them (the bots
  require them), so they cannot separate. EMA gap widening, MACD bars
  growing, small top wick: no difference here. Volume spike at the buy:
  worse (15% won). Price 20%+ over VWAP: 4% won (28 trades) vs 29% - mostly
  regular hours; in premarket not clean (DKI 6:54 +$631 was over). Green
  bodies shrinking: 14% won vs 22% (v36b 0% vs 18%).
- Thought (not decided): v36 premarket only - the 10-07 night proposal (a);
  the owner chose the full 4am-8pm schedule at 3:40am 10-08. To check on
  10-01..10-05 first.

### The three-candle setup as the bots trade it (finding, ~9:10pm)
- The owner: the three-candle setup (green, red, buy back over the red's
  open, stop under the red) works 80%+ for experienced traders, more with
  every filter that checks out; the first one especially.
- v36 on 10-08 took none (19 furious, 7 new-high to 9:47). On 10-06/07 it
  took 34 (31 matched to round trips: 5 won, -$409; starters ~$430).
- Second by second (R = buy - the red's low): +1R before the stop 15 of 34
  (44%), +2R 11 of 34 (32%) - about break-even before costs.
- Where it worked: LPCN 10-07 6:42-7:00, the #1 name, 4 of 4 to +2R;
  BIYA's first two (4:20, 4:23); DKI 11:28; MOBX. Every one failed on DLXY
  (3), SPAI (2), MTEN (3), MI (2), and BIYA's later ones. Next: the setup
  on the day's #1 name only, its first pullbacks, 3 days, after costs.

### How many trades for a 99.9% chance of a +2% day (the owner's question, ~8:50pm)
- Independent trades, fixed win and loss sizes, no costs (exact binomial).
  60% wins, wins = losses: 224 trades a day just to end above zero 99.9% of
  days; 244-300 for +2% (a loser 1%-0.25% of the account). 60% wins, wins =
  2x losses: 30 trades to end above zero; 37-49 for +2%.
- 55% wins: 930 / 970-1,086 (equal); 48 / 52-70 (2x). 65%: 96 / 108-144
  (equal); 21 / 25-37 (2x). The size of the wins matters more than a few
  points of win rate.
- v36's own payoff (wins 2.25x losses), 40 trades a day, a loser 0.5%: a
  +2% day 79% of days at 40% wins, 98% at 50%, 99.9% at ~58%. v36 now: 21%.
- Real trades are not independent (one stock, one market mood) and each pays
  ~0.6% in spread on these stocks: more trades than this, and a bigger edge.

### Trading like the owner: a few trades a day (finding, ~8:40pm)
- The owner: "1, 2 or 3 trades a day, sometimes none; under a dozen even
  scalping. A day with no trade beats a day worked and lost." The bots:
  v36 16/42/36 trades on 10-06/07/08, v36b 5/42/39, v37 110/11/20.
- Live P/L of only the trades kept, 3 days: v36 all -$1,718 | first trade a
  day +$268 | first 3 +$239 | stop after the 1st loss +$138 | after 2 losses
  +$144. v36b -$1,032 | +$111 | -$1 | +$97 | +$24. v37 -$1,790 | +$2 | -$76
  | -$3 | -$36. The first trades of the day (the 4am leaders) were the good
  ones; the rest lost.
- Costs: the spread plus paying over the ask seen were ~70-80% of v36/v36b's
  losses and more than v37's whole loss (3 days, approximate).
- Caveat: 3 days, 3-9 trades - AIXI 10-08 +$329 carries v36's numbers. A
  daily limit touches the owner's 10-08 decision (no limit on entries;
  LPCN 10-07). To test on earlier days' fills before any rule.

### Keeping the runners: the dip before the run (finding, ~8:30pm)
- The owner: the goal is keeping the runners. replay/research/runner_dips.py:
  most runners fell 20c+ under the buy before their top - v36 18 of 28,
  v36b 15 of 22, v37 48 of 56 - and ALL came back over the buy price later
  (median 1.5-3 minutes after the low). No acceptable stop holds them.
- Buying back once the price reclaims the buy + 2c and holds 3s (any number
  of times): it churns - v36 43 first buys -> 474 buys, 5c cut -$5,459 (vs
  -$567 one buy each, -$905 back in over the high + 5c); v36b 391 buys
  -$2,344; v37 434 buys -$4,499. Worse than no buy-back.
- Reading: for each runner there are many look-alikes that dip and do not
  come back. Keeping runners needs telling them apart - at the buy, or with a
  slower confirmation before getting back in (e.g. a minute closing over the
  old high). Not yet designed.

### v36's exit above +30c: 30% back vs the owner's ladder (finding, ~8:20pm)
- The owner: keep v36's exit, but from +30c give back half (30-50c), a
  third (50c-$1), a fifth (above $1) instead of 30% - did any trade get
  there? (replay/research/ladder30.py)
- 10-08, the three v36 trades past +30c, every print (v37 TICK_DUMP): DKI
  5:00 (best +35c) now +$277 / ladder +$203; DKI 6:54 (best +$1.87, data
  from 6:57:06) now +$612 / ladder +$711; FLYE 7:22 (best +44c) both +$733
  (it fell through both lines at once). Live: +$281, +$631, +$733.
- The rest of the three days: 10 more v36 trades past +30c, now -$3,635 vs
  ladder -$3,703 overall (v36b 7: -$1,540 vs -$1,571); differences $5-$40 a
  trade - half back loses on 30-50c moves (DKI 10-07 +$57 vs +$19).
- So about even overall. It helps only past +$1 (a fifth back instead of
  30%) - once in three days (DKI 6:54, +$99). An option: only that top
  step (30% back up to $1, a fifth back above) - one trade behind it.
- With re-entries (the owner, ~8:22pm; first buy of each stretch, then buy
  back over the day's high + 5c, same rule): v36 70 buys - now -$3,288,
  ladder -$3,365, top step only -$3,288; v36b 62: -$1,361 / -$1,396 /
  -$1,361; v37 62: -$1,483 / -$1,450 / -$1,483. One buy each instead: v36
  -$2,878. No edge from the ladder; re-entries add losses. The top step
  equals "now" here - its one case past +$1 (DKI 6:54) is in the missing
  data. Exits replayed without v36's 10-second leash: compare rules only.

### The runner table: 10c stop vs 3% (the owner: "remember", ~8:10pm)
- Runners = the stock 50c+ or 20%+ higher within 30 min of the buy;
  10-06/07/08, each with v36's furious exit (out on 30% back of a 30c+
  gain); 10-08 DKI, CRE and FLYE's start missing from the data.
- All trades (the replay takes the first buy only): v36 28 runners, 10c
  -$724 vs 3% -$835; v36b 22: -$172 vs -$149; v37 56: -$112 vs -$295.
- Trades with no adds: v36 14: -$566 vs -$565; v36b 16: -$235 vs -$219;
  v37 46: -$484 vs -$691. (My message first paired the all-trade dollars
  with the no-adds counts 14/16/46 - corrected here.)
- v37, 10c vs its own 3-8% stop (114 trades with no adds, 46 runners): with
  the 5c cut every stop gives -$1,329 (runners -$511) - the cut sells first;
  with the furious exit 10c -$3,318 (runners -$484), 3% -$2,778 (-$691), 5%
  -$3,994 (-$761), 8% -$5,482 (-$990).
- Proposal (the owner: "sensible", not yet decided): v36b keeps its 3% cap on
  normal buys; its furious buys get the owner's 10c, as v36's do.

### The tiered exit on v37's 19 trades of 10-08 (finding; the owner decides)
- The owner's design (~4:30pm): best gain 0-5c: out 5c under the best;
  5-20c: out at the buy price; 20-50c: keep half; 50c-$1: keep two thirds;
  $1+: give back a fifth (or a flat 20c). The line only rises; the stop
  stays under it. Re-entry unlimited, only over the day's high + 5c.
- Same entries, exit only (v37's own code, real prints, sold at the bid
  0.5s later; replay/research/tiers_1008.py): live -$742 (0 won); the 5c cut
  (r34.33) -$290 (3 won); tiers -$273 (1 won) - FLYE 7:23 +$383 vs +$256,
  SBFM 5:21 $0 vs +$89 (the break-even zone gave the gain back). Top tier
  flat 20c: same (nothing reached +$1). Edges x0.75 -$273, x1.5 -$223.
  A wider first leash loses more: 10c -$632, 15c -$598 - most of these
  entries go straight down.
- With re-entries over the day's high + 5c, filled at the ask 1s after the
  signal (live decision-to-fill is ~1.3s for v36/v36b), 6-8 minutes of data
  per stock: 5c cut -$885 on 37 entries, tiers -$1,077 on 36 - worse than
  live. The re-buys land at the top of one-second bursts (FLYE 7:25:54 went
  $2.40 -> $2.71 in 0.4s); DKI 4:13-4:21 ran $2.50 -> $3.70 and the rule
  bought 12 times and lost 11 (-$543). With no delay it looked good
  (-$378): the delay decides it.
- One day, 19 entries, v37 only. The real test is the three-day read.
- The full tiers were on in every run; today they hardly came into play:
  14 of the 19 buys never got more than 3c over the buy; SBFM +10c / +8c,
  MOBX +8c, DKI +6c reached tier 2 (the break-even zone gave SBFM's +$89
  and +$22 back to $0); FLYE 7:23 +35c reached tier 3 (sold by v37's
  furious exit, +$383). Nothing reached 50c. With "a buy at a line waits
  for the line + 5c" (ask 1s later; replay/research/tiers_lines_1008.py):
  within 3c of a line -$321, 5c -$320, 10c -$175 (FLYE 7:25 at $2.91 never
  crossed $3.05 in the data: -$233 skipped) vs tiers alone -$273.

### The owner's ladder ON TOP of the cents cut (the owner's correction, ~8pm)
- The owner: the tiers are an add-on to the 5c (or 4c) cut, not an
  alternative: the cut first ("5 introductory cents ... below 10c"), then
  never under the buy up to +20c, half the gain kept 20-50c, two thirds
  50c-$1, all but a fifth above $1. (My "tiers" row was already this with
  the cut until +5c; now also tested until +10c and with 4c:
  secsim.cut_then_tiers.)
- Trades with no adds, 3 days: v36 50: cut alone 5c -$692 / 4c -$581;
  ladder from +10c -$761 / -$750. v36b 59: -$391 / -$248 vs -$420 / -$311.
  v37 114: -$1,329 / -$1,063 vs -$1,368 / -$1,105. On the runners: the
  same within $15 for every bot.
- Why: the best gain each trade reached before it was sold (5c, ladder
  from +10c): 174 of 223 never got 5c above the buy; 12 reached 10-20c; 4
  reached 20-50c; none 50c+. The ladder's upper steps almost never come into
  play - the runners shake out in the first cents. (10-08's FLYE 7:22 and
  DKI 6:54, missing from the data, are two that did run.)

### The three-day test, second by second (findings, ~8pm 10-08; the owner decides)
- Data: SEC_DUMP read 6:03-7:29pm, 76 windows, none lost at the source.
  Fetched 72 (69 whole); missing: 10-08 DKI (3 windows), CRE, FLYE's first
  minutes (7:17-), part of VCIG 10-06 and CPHI 10-07 - the session's safety
  check blocked saving some log pages (base64 read as "credentials").
  Saved: replay/live/2026-10-08_secdump/ (windows/, roundtrips.json).
- Live, from the accounts' fills (corrected - a dedupe bug of mine dropped
  same-second fills): v36 94 trades -$1,718; v36b 86 -$1,032; v37 141
  -$1,790.
- Tool: replay/research/secsim.py (+ secsim_run.py, secsim_check.py);
  checked against the bot's own v37 code on 10-08: 5c -$260/-$297 vs -$290,
  10c -$637/-$661 vs -$632. Like for like = trades with no adds.
- Trades with no adds, 3 days (stop 10c under the buy):
  v36 (50): live -$1,550 | 4c cut -$581 | 5c -$692 | half from 2c -$767 |
    tiers -$1,097 | 10c cut -$1,724 | furious 30c/30% alone -$3,095.
  v36b (59): live -$964 | 4c -$248 | half any -$268 | 5c -$391 | tiers -$575.
  v37 (114): live -$995 | 4c -$1,063 | 3c -$1,108 | half any -$1,181 |
    5c -$1,329 | tiers -$1,595 | 10c -$2,327. By day v37 5c vs live: 10-06
    -$707 vs -$315 (92 trades; live then "half from any fraction"), 10-07
    -$504 vs -$368, 10-08 -$118 vs -$312.
- So: v36/v36b - a quick cut (4-6c, or half the gain) about halves their
  losses against their live exits on 10-07 and 10-08 alike. v37 - no exit
  beats what it did live over the three days; the 5c cut won 10-08 only.
  Tiers never beat the plain 5c cut (the 5-20c "back to the buy" zone
  gives the small gains back). 10c is worse than 5c for all three.
- v36's 10c stop vs v36b's 3%: with quick cuts no difference; with slow
  exits 3% did better on both bots' trades - but 10-08's FLYE and DKI (where
  10c won) are in the missing data. Not settled.
- Runners (the stock 50c+ or 20%+ higher within 30 min of the buy): every
  rule lost on them - v37 56 trades, the whole move worth $15,370: live
  -$759, 5c -$643, tiers -$687, v36's furious 30c/30% -$112, a 10c stop
  and nothing else -$1,157. They fall through any leash first, then run.
- Buying back over the day's high + 5c (ask 1s later), same stretches:
  v36 5c -$567 -> -$905 (43 -> 78 buys); v36b -$199 -> -$318; v37 -$756 ->
  -$899. The buy-backs lose too.
- Reading: the exits are not where the money is lost; the entries are -
  bought at the top of one-second bursts. Next: the entry (e.g. buy the
  hold after the burst, not the burst), on this data.

### r34.35 released 6:02pm 10-08 (the owner: "push")
- The owner (~6pm): stop all three for tonight ("flatten them; we'll start
  them later") and get the three-day data now. All three were flat (no
  positions since 4:53pm). main a8cc776 -> 6eec247: r34.33's 5c cut for
  v37, r34.34's read (SEC_DUMP), NO_BUYS_FROM 10-08 from 6pm. 644 tests.
- The first push was held by the session's safety check until the owner
  said "push" - a push to main is a production deploy; it needs the owner's
  word in the chat.
- Day's end (5:45pm): v36 +$191 (+1.16%), v36b -$356 (-5.58%), v37 -$744
  (-5.22%).
- v37 on 10-08's 19 trades, 10c cut vs 5c: -$632 (1 won) vs -$290 (3 won).
- The owner: v36b's re-buys did happen (FLYE 8 buys) - each one higher, at
  a burst's top, with the same ~6c stop: out again in 1-2s. Getting back on
  cannot make up for a stop narrower than the stock's normal swing.

### v36 vs v36b on 10-08 (finding, ~6pm; the owner decides)
- The day at 5:45pm: v36 +$191 (+1.16%, $16,681); v36b -$356 (-5.58%,
  $6,028); v37 -$744 (-5.22%). v36b = v36 + three settings: the first stop
  at most 3% under the trigger (MAX_STOP), no buy under a 60% top wick
  (WICK_VETO), stops on fresh prints only (FRESH_EXITS). Sizes are % of
  each account (25% for a furious buy), so compare in %.
- Paired trade by trade (replay/research/v36_vs_v36b_1008.py): the whole
  6.7-point gap is two stocks. FLYE 7:22-7:26 v36 +0.39%, v36b -4.33%; IPW
  4:10 v36 +0.66%, v36b -1.57%. On $1.77-$1.80, 3% under the trigger is
  ~6c - tighter than the owner's furious 10c - so v36b was stopped in 1-6
  seconds (FLYE 7:22:53 out at $1.70 in 0.7s; v36 held to $2.21, +$733,
  +4.45%), then bought again higher (FLYE 8 buys vs 7, IPW 3 vs 1). The
  same tight stop saved v36b on stocks that fell at once: BIAF 8:06-8:09
  +1.9 points, CHR +0.8.
- 10-07: v36b lost less (-8.62% vs -9.45%). One day each way; the v36b
  replay (09-28..10-06) was on 1-minute bars, blind to these seconds. To
  judge on the three-day read, per entry.

### The owner on rules working against each other (~5:50pm)
- "Some of the rules are working against each other, even though they are
  not completely contradictory ... as a human I would have said this takes
  priority and those other rules do not apply here. But the bot checks every
  single one of them." (WORX: after the furious stop it fell back to the
  slow route - the 2-minute wait, the high + 5c, a tenth of a position.)
- Confirmed live, nothing dropped: furious = speed 0.30 with the price up 3%
  in the minute (inside real_speed), $250k in the minute, last candle not
  red; at the buy, up over 5 seconds and the ask within 10c of the bid.
- Proposed: a map of situations, each with the rules that apply and the
  ones set aside (furious; back on after a furious stop; the leader's new
  high; the regular setups), written from the code for the owner to read;
  and from the three-day read, every rule's blocked buys and what the stock
  did next.

### DECISION (the owner, ~5:35pm): the scanner's 10% baseline stays as it is
- "The rules we are working under now, we'll keep those ... not moving the
  goalposts" - all that has been measured would stop counting. So: 4:00-9:30
  10% over yesterday's close; from 9:30 10% over today's open (unchanged).
  The 4am-baseline idea below is dropped.
- And (~5:40pm): the 2-minute crowd wait stays as it is - no look-back.
  Only a furious move throws it away, as the code already does (in_crowd:
  speeding at 0.30 on real money; also a top-2 gainer with $1M, an
  acceleration, a rip in the last 2 minutes - unchanged).

### The scanner's baseline and the 2-minute crowd wait (the owner, ~5:30pm; words sent, to confirm)
- The owner: "fix right away" - a stock goes on the list when it is up 10%
  FOR THE DAY, measured from 4:00am of the same day: not yesterday's close,
  not from 4pm. Today: 4:00-9:30 from yesterday's 4pm close; from 9:30 from
  today's 9:30 open (GAIN_FROM_OPEN, day_reference).
- WORX check: first trade 10-08 $5.90 at 4:05am; 9:30 open $5.49; prior
  close $5.75. List at 10%: 4am rule $6.49, today's rule $6.04 (it came in
  at $6.09, 4:50:13), from 4pm $4.62. The 4am rule would not have seen WORX
  sooner. Premarket changes most: a stock that gapped overnight starts at 0%
  at 4am. The "top gainer" rank (from yesterday's close) would contradict
  it unless it moves too.
- The owner: some rules get in the way of orders - the 2-minute crowd hold
  (V36_CROWD_HOLD_MIN) "could have looked back": the last two minutes were
  green. Proposed words: top 2 by money and the last two closed 1-minute
  candles green -> no wait. WORX: open at 4:51:00 instead of 4:53:01. (A rip
  in the last two minutes already skips it, but needs $250k a minute -
  WORX's 4:50 minute traded ~$232k: "not ripping".)

### WORX after hours, 4:48-4:53pm (v36/v36b; findings, the owner's chart)
- Times: the owner's Alpaca Activities page shows CENTRAL time (WORX buy
  "03:51:35 PM" = 4:51:35pm ET; BIAF "07:06" = 8:06am ET). The bot's log
  is UTC. Memory and replies use ET.
- WORX closed $4.20 (-27% on the day), then ran $4.79 (4:48) -> $7.20
  (4:53) after hours. The bots saw it only from 4:50:13 ($6.09): after
  9:30 the scanner measures the gain from TODAY'S OPEN (GAIN_FROM_OPEN
  10%), so a stock that fell all day is invisible until 10% over its open.
- 4:51:00 v36/v36b: NO CROWD (needs #1/#2 held 2 minutes; #2 for 0m).
  4:51:33 furious at $6.72: FAST BUY NO, the ask 19c over the bid (r34.29);
  4:51:34.8 OK (4c). v36 filled 613 @ $6.74 (print $6.69) 4:51:35.97,
  stop $6.64 (10c, furious). 0.9s later the market 6.58 x 6.68: its middle
  under the stop -> out; after hours a limit sale, 152 shares then the
  other 461 (cancel and resend) by 4:51:39, avg $6.65: -$53.55 (Alpaca:
  152 @ $6.60, 461 @ $6.67 - the bid back up 9c in 2s). v36b 184 @
  $6.73 -> $6.62, -$19.66. No print at the stop: a 10c-wide quote.
- 4:52 ran $6.57 -> $6.99 through the day's high ($6.77): no re-entry -
  "get back on it above the high of the day" (furious_new_high) also needs
  a new burst of speed; the regular route waited for the crowd's 2 minutes
  (4:53:01) and then the high + 5c ($7.05): starters (a tenth) @ $7.11 at
  4:53:43, the top was $7.20; out at $6.93 in 2s (-$10 / -$4).
- Proposals for the owner (words first, test on the three-day read): the
  after-hours gain from the 4pm close; the furious re-entry on the day's
  high without a new burst; the stop on a wide quote decided by a print.

### The runners of 10-08, and why v37 bought BIAF late (findings, ~5:30pm)
- v37 bought FLYE at $1.90 at 7:23:30, as its run to $3.17 (7:25:55)
  began; live sold it 7s later at $1.88 (-$36: half the gain armed at
  +1c). The 5c cut: +$256; the tiers: +$383 (out at $2.08 on a dip from
  $2.25 to $1.99). Live v37 won 0 of 19.
- The runners swing hard inside the run (replay/research/runners_1008.py):
  FLYE's deepest pullback on the way up 41c (17%, $2.44 -> $2.03); DKI
  4:13 ($2.50 -> $3.72) dipped 8c under the buy in seconds, then 34c (9%);
  BIAF fell 85c under v37's $7.99 buy before $8.33; AIXI 47c under. No
  cents leash tight enough for the dead entries holds through these: the
  first tier (5c under the best) took DKI out at $2.44 in 2 seconds.
  Holding a runner whole needs a leash as wide as its swings, or getting
  out and back in well (the owner's way) - the re-entry test bought the
  tops of bursts.
- BIAF: in the bots' list only from 8:05:39 ($6.79; before that 1-3k
  shares a minute). 8:06 burst 6.66 -> 7.65 -> 6.70: v36 bought the top
  ($7.49, 5s -0.7%, -$382; r34.29 now blocks that). v37 did not buy then:
  its crowd rule wants the #1/#2 name with $1M traded in 5 minutes
  (V37_CROWD_MIN_DOLLARS) - BIAF had ~$0.4M; by 8:09 $2.4M (crowd #2), and
  v37 bought at $7.99 on acceleration, near the leg's $8.19 high. v37 does
  not log why it skips - inferred from its rules and the volumes.
- r34.34's read now keeps one row a second from 5 minutes before each buy
  (SEC_DUMP_BEFORE 300; prints from 30s before) - how early each could have
  got in.

### Whole and half dollars (the owner, ~4:45pm; words to write, then the owner reads)
- The owner: incorporate the lines ($x.00, $x.50) as resistance and
  support. A buy waits for the line + 5c ($2.05, $1.55, $3.05) - "not
  always profitable, but most of the time; all traders watch them". In a
  position near a line with a good profit: be diligent, jump out if it
  comes back ("I leave a lot on the table, but at least I assured that").
  A strong / furious stock: the lines are not a limiting factor.
- Built already: v36/v36b no buy or add from 3c under a line to 5c over
  it until held 3s past (V36_LEVELS, not for furious); the stop under the
  line under the buy, rising to each line cleared (V36_LEVEL_STOP, all
  three). v37 has no line wait on buys. Earlier research: tops did not
  land near lines more often than elsewhere (leaders_retests.py).
- 10-08 (levels_near / levels_wait / levels_hesitate.py): 10 of 74 buys
  sat at a line, 1 won, -$742 (-$74 an entry; the other 64: +$121, +$2 an
  entry); 9 of the 10 were furious. Waiting for the line + 5c on the 9
  with ticks, same exit (5c cut): -$188 (held 3s: -$431) vs -$142 as
  bought - the cross often came at the top. A "hesitates at the line" exit
  on v37: -$367 (3c/2c) vs -$290; with strong stocks exempt -$289. Small
  sample; to test on the three-day read with the profit condition.

### The read for the three days, r34.34 (to release after 8pm with r34.33)
- SEC_DUMP: read-only, once at start-up: each account's fills on 10-06,
  10-07, 10-08 into the log; around every buy 30s before to 30 min after,
  every print and quote change for the first minute, one row a second for
  the rest (OHLC, volume, bid/ask). zlib + base64 SECDUMP lines,
  100 requests a minute; replay/research/secread.py reads them back. Next
  release: SEC_DUMP_DAYS = ().
- After it: the tiered exit, the 5c cut, re-entries and the line rules
  for v36, v36b and v37 on all three days, per entry. Then the owner's
  next question: why v36b is not better than v36.

### The green-tape idea, measured (finding)
- The owner: buy only when the time and sales is green (trades at the ask).
  10-08's tape, while rising, last 5s >=70% at the ask: the mid +0.41c 1s
  later, -0.24c at 5s, -1.32c at 30s; a red tape: +0.27 / +0.94 / +0.41c.
  No lasting edge (replay/research/green_test.py). On v37's 19 buys with the
  5c cut: green >=50% -$231, >=60% -$57, >=70% +$44 (4 kept) vs -$290 all -
  hangs on single trades (FLYE 7:23 +$256 and 7:25 -$233 both 63% green).
  Not built. v37's fast buy already needs a 60/40 tape (V37_ACCEL_TAPE).
- Next question if v37 still loses with the 5c cut: its buy - one-second
  bursts that snap back.

### The uptick idea, measured (finding); r34.33 waiting for 8pm
- The owner: buy only on an uptick (one, two or three in a row) - "an uptick
  is more likely followed by an uptick". Measured on 10-08's time and sales
  (the TICK_DUMP windows): after an uptick the next print is up 21.8%, the
  same 30.6%, down 47.7% (rising stocks: 21.2 / 32.1 / 46.6) - the bid-ask
  bounce; the middle of bid/ask a second later is only ~0.4c better after an
  uptick than after a downtick. On v37's 19 trades: uptick-only + 5c cut
  -$91 vs -$290, but the result flips with half a second of timing, and 2-3
  upticks in a row skip the winners. Not built (no-overfitting rule).
- The owner chose to try the 5c cut ("something we'd like to try"):
  r34.33 on the branch (c08b67b) - V37_TRAIL_CENTS 0.05, TICK_DUMP off, the
  furious comment lists the never-rules. To push after 8pm ET 10-08 (a
  reminder is set for 8:05pm), all three flat.
- Correction kept for the record: v37's trigger is NOT always an uptick - 7
  of 19 trigger prints on 10-08 came right after a higher print.

### v37 exit tested print by print on 10-08's own trades (findings; the owner decides)
- Data: TICK_DUMP's 353k trades / 47k quotes, saved in
  replay/live/2026-10-08_ticks/tickdump_v37.txt.gz; tool
  replay/research/tickreplay.py (v37's own exit code on the real prints,
  sold at the real bid 0.5s after the decision; adds off; each trade alone).
  Check: "half the gain from 1c" gives -$752, 0 won - live was -$742, 0 won.
- "Half the gain" armed from 1/2/3/4/5/10c: -$752 / -$756 / -$620 / -$738 /
  -$738 / -$617 - the arming is not the main problem; 8 of 19 trades lose the
  same at every setting (-$560), straight to the stop.
- The owner's idea - out once the price is X cents under its best since the
  buy, in place of half the gain: 2c -$664, 3c -$569, 4c -$532, **5c -$290**
  (3 won), 6c -$339, 8c -$471. Built as V37_TRAIL_CENTS, OFF; proposed at 5c
  for a live (paper) trial. Half the gain from 2/4/6c: -$756 / -$738 / -$738.
- r34.29's buy checks would have let every v37 buy through (rising, spreads
  1-8c). A buy cap was looked at and dropped - the owner: the buy stays as is
  (pays up on flying stocks, the ask otherwise).

### r34.32 live (pushed 3:25:13pm, flat): a one-off read of v37's trades, print by print
- The owner: the 1-minute replay "gives a sense of false hope" - it cannot
  judge rules that act in seconds (v37's exits; replay 69% won vs live 0/19).
  The 8-day v37 replay: re-buy 10c/20c and fix 3 made no difference; arming
  "half the gain" at 5/10/15c lowered the replay's P/L step by step - but the
  replay never shows the 1c flicker. Minute bars on today's 15 trades could
  not reproduce the live 1c result (-$993..+$457 vs -$249), so no verdict.
- Decision: v37 unchanged live (20c re-buy, half the gain from 1c); the
  10c-under-$2 re-buy built OFF on the branch; fix 3 built OFF.
- The owner asked for an exact test on today's data: TICK_DUMP (read-only, at
  start-up) read every trade and bid/ask change in 12 windows around v37's 19
  trades - 353k trades, 47k quotes, logged as TICKDUMP lines 3:26pm. A tick
  replay (scratchpad tick/tickreplay.py) runs them through V37's own exit
  code at 1-5c arming, selling at the real bid 0.5s after the decision.
- Ways to get second-by-second data from now on: the recorder (proposed), or
  a read-only data key in the environment (POLYGON_API_KEY or
  ALPACA_DATA_KEY_ID / ALPACA_DATA_SECRET) for past days.

### r34.31 live (pushed 2:17:50pm, all three flat); a standing rule
- The owner (decision): v37 buys back within 60s of a sale only once the
  price is 20c over it - not 30c, and no 10% ("just 20 cents higher").
  V37_REBUY_JUMP 0.20, V37_REBUY_JUMP_PCT 0 (not used). On a $1 stock that is
  now 20% (was 10c); on $2+ it is easier than before. A furious new high
  still buys back at once.
- Standing rule (CLAUDE.md): no overfitting - few rules, each with a market
  reason and results over many entries; every change checked against the
  rules already there, naming what it touches or overrides, conflicts
  resolved in words first.
- Check of today's three releases against the existing rules:
  - r34.29's fast-buy checks are new never-rules for furious buys; the
    V36_FURIOUS_ALL comment ("every entry check set aside") should list them
    - comment to fix with the next release.
  - r34.30 makes V36_LEADER_NO_CAP and the speed exception to the cap moot
    (no cap left). With no cap, the brakes on repeated full-size whipsaws on
    one stock are: one buy a minute (a furious new high exempt), r34.29's
    5-second and spread checks, re-entries over the day's high + 5c at speed
    0.10, and the day's -10% halt.
  - r34.31 is consistent with the furious new-high re-buy.

### r34.30 live (pushed 1:26:03pm, all three flat): no limit on buys of a stock a day
- The owner (decision, ~1:20pm): "they can go there as many times as
  possible... we cannot limit the number of entries for the day" - removed
  from all strategies, released at once. V36_MAX_ENTRIES 6 -> 0 (v36, v36b);
  v37's has been 0 since 10-06. The owner had believed it was gone: on 10-06
  only v37's limit was removed; 10-07 added only the leader exception.
- Why: FLYE 7:22-7:25 spent v36's six buys (four whipsaws), then "NO: 6 buys
  today" every minute 7:26-7:40 while the #1 name ran $2.23 -> $3.60; the
  leader exception needs a new high over the closed minutes' high ($3.09,
  the 7:25 spike), which FLYE did not clear until 7:40.
- The owner on the numbers: win rates and averages per ENTRY (32 / 35 / 19
  today), added up over days before judging a rule. v36 today: 37.5% won,
  average win $210 vs loss $112 - "starting to act like something good";
  its +$289 rests on FLYE +$733 and DKI +$631.
- v36's drawdown from +9.2% (8:00am) to +1.8%: CHR 8:02 -$348 (up 14c, not
  protected), BIAF 8:06 -$382 and KAPA 9:34 -$225 (both now blocked by
  r34.29), BIAF 8:09 -$134, KAPA 9:37 -$63, the rest -$70.

### r34.29 live (pushed 1:08:58pm, all three flat): two fast-buy checks
- The owner's decisions (~9:15am, released "at the next flat moment"):
  - no fast buy (v36/v36b furious, v37 accelerating) unless the price is
    higher than 5 seconds ago - "to buy in five seconds when the market went
    down, we need to make sure that does not happen" (FAST_BUY_5S_UP);
  - no fast buy when the ask is more than the 10c stop over the bid
    (FAST_BUY_MAX_SPREAD = 0.10). No quote: no fast buy.
- Each check logs `FAST BUY OK` / `FAST BUY NO` with the 5s move and the bid
  and ask - the market at every fast-buy decision is now on record.
- Tests: 622 pass; the new ones fail with the check removed.

### The day to 1pm, and what it taught (findings)
- 1:05pm, all flat: v36 +$288 (+1.7%, 32 trades), v36b -$326 (-5.1%, 35),
  v37 -$743 (-5.2%, 19, none up). Best DKI +$965 (all three); worst BIAF
  -$643, CHR -$570, FLYE -$510, KAPA -$479.
- Audit of the 74 trades to 9:47 (scratchpad audit1008, from the Render log):
  - F2: the bid already under the stop at the fill - 12 trades, -$1,519.
    Cause: a fast buy pays up to the ask + 20c, the stop is 10c under the
    fill. BIAF 8:06:44 paid $7.49 with the bid $6.82; sold 8 ms later.
  - F9: never a cent above the fill - 16 trades, -$1,925.
  - F8: up 10c+ and still closed at or under the buy - 10 trades, -$945.
    A furious buy's gain is protected only from +30c (V36_FURIOUS_EVEN_AT).
  - F7: v37 "half the gain" on a 1-2c gain - 14 trades, -$246; it fired
    1 ms after a buy (V37_GIVEBACK_ARM_CENTS = 0.01, gain read from prints).
  - F3: the stop set from the decision print, not the fill - 29 trades
    (v36b BIAF 8:06:45: 7.0191 = 1% under the fill, not $6.99).
  - F6: quick re-buys (within 10s of a stop) made +$313 net on 14 trades -
    the owner: "if it gets shook up, jump back in". Proposal 4 (a 2s wait)
    withdrawn.
  - F4: sales over 2s or 2+ orders: 46 trades (premarket limits cancelled
    and re-sent about every second).
- BIAF replay (the bot's code, 1-minute bars): the 8:08 rip-pullback the
  owner saw is rejected by the bot's own rules, not the crowd hold - the 8:06
  green's top wick 61% (> V36_WICK_MAX 50%) and the 8:07 red heavier than the
  green (V36_PULLBACK_VOL, the SPAI rule). Lifting the crowd hold changed
  nothing; lifting the re-entry speed added one loss at 8:14 (the top).
  At their stop prices BIAF would have cost v36 -$157, not -$516: the
  damage was the fills.
- Big runs held with tiny positions: BIAF to $9.38 at 10:07 (v36 37 shares,
  +$10); INHD to $6.30 at 10:31 (30 shares). The adds never came.
- The give-back tiers (built 10-08 4am on claude/laughing-gates-cor709,
  GIVEBACK_TIERS, off): the 7-day replay lost ~$1,050 each for v36/v36b
  ("half back under +50%" is looser than 30%). Kept off; not on main.

### The owner's direction (~9:15am)
- Every trade laid out action by action next to the market, to the
  millisecond, each action checked against the rules; then clean the rules
  up. "When the rules are solid and they act by them, losses are okay."
- Goals: stay with the big runs; don't get shaken out; if shaken out, jump
  back in; cut the small losses. Entries that build a cushion at once.
- Proposed (not built): a recorder in the bot - the last minute of every
  print and quote per watched name, written out around each trade with
  every bot action, to the millisecond - and a nightly audit from it.

## 2026-10-07

### Tonight's review (memory/review_1007.md) - findings, not decisions
- **The day was worse than I reported at 4:10pm.** "All flat" was true at
  4:06, but the session runs to 8pm. From 4:22 to 5:00pm, v36/v36b bought
  IRIX, AIXI, NCPL and ERNA as furious full positions. r34.28's block covered
  9:30-4 only. All 8 trades lost: v36 -$289, v36b -$204; v37 made +$2 on 2.
- **Final, from the 7pm summary:**
  - v36 -$1,722 (-9.45%), $99 above its daily halt;
  - v36b -$602 (-8.62%), $96 above its halt;
  - v37 -$293 (-2.01%).
- **Every losing trade, tagged** (premarket from the morning audit):
  - market -$360;
  - rule -$1,377;
  - code -$571;
  - release (the deploy overlap) -$508.

  87% of the money lost on losing trades came from things known or
  knowable. From 9:29 to 8pm, v36 and v36b: 40 trades, all losers but one
  break-even.
- **v37 SXTC 1:40, -$290:**
  - $62 was the plan (10c);
  - $100 was the stop decided on a print 16c through it (the stop is checked
    only on prints);
  - $128 was the slow sale (cancel and resend, fixed in r34.24).

  The buy was the top tick of a spike: 7.5% over the prior 3-minute high;
  SXTC then fell to $5.13 by 1:47 and was back over $7.75 only at 1:55. 13 of the 23 buys from 1:35pm on filled in the top 15%
  of their minute.
- **The 10c furious stop sits inside the noise.** SXTC's 1-minute ranges 1:30-2:00
  were 24c to $1.50, typically 74c (11%). The 1:55 buys were stopped in 2-5 seconds, then SXTC ran
  +$1.67.
- **A sale: 0.2-0.8s to send** (three broker calls, one of them an unused bid
  snapshot), then 0.9-3.9s to fill on paper.
- **The replay of 10-07 (r34.28) says v36 +$50,060 and v37 +$127,977** on
  $15k. Almost all of it is two premarket squeezes bought at full size:
  - BIYA 8:20, $2.54 to $28.54 in one minute on the bars;
  - SXTC 8:16.

  Live, the code running then did not hold either. Even the replay loses
  9:30-4 on 10-07 (v36 -$2,022 at 0.2% worse fills).
- **Proposals in the review (none chosen):**
  - v36/v36b premarket only, until a regular-hours design exists;
  - releases after 8pm only + D;
  - furious size from a dollar risk, with the stop sized to the stock's
    swing;
  - C;
  - the stop checked on quotes, and no unused bid read before a market
    sell;
  - cents to percent on cheap stocks;
  - the scorecard;
  - a halt rule.

### The owner near the close (~3:55pm): sizing by speed; the v37 bite; slow sales
- "If the stock is moving furiously fast it's okay to enter with a bigger
  position; if it is moving fast but moderately, always enter with a small
  position - ease in slowly." Decision (confirms the tiers: furious = big;
  fast-but-moderate = small starter and adds).
- v37's one SXTC trade (-$290, 35% of the account on the top tick, a 7.5s
  sale) "took the best out of it - that should not have been the case";
  "the selling is slow - how can we get it faster"; and check whether the
  buys come at the right time. For tonight, words first (memory/checklist.md).

### Words before code (the owner, ~3:40pm) - a standing rule
- "When you have it built, put it in words and we'll examine those words
  really closely ... every hole plugged and every contingency accounted for.
  Now everything we built is full of holes, and the strategies are losing
  money hand over fist." Decision: every new rule is first written in plain
  sentences and answered against memory/checklist.md (the price it decides
  on, the buy order, the position, the sell order, the account and process,
  the session and the stock); the owner reads it before any code. Added to
  CLAUDE.md's standing rules.
- The owner, right after: "losses due to the randomness of the market or
  unpredictable things - that's fine; things we already know well and can
  predict should be in the code." Every audited loss gets tagged market or
  code/process; each code/process loss gets a fix.
- Today's foreseeable holes, for the record: a buy-side cancel rule applied
  to market sells; a gain measured from a stale print; two processes trading
  during a release; a position sold by one process still held by the other;
  paper fills slower than the 0.5s order window; premarket rules applied to
  regular hours untested.

### The owner, ~2:50pm: "our strategy is no good if it loses that much a day"
- v36 -7.8%, v36b -5.7%, v37 -2.0%: "we have not succeeded yet in translating
  our ideas into code - pull away fast from the losers, capture the gainers,
  and even with small numbers we would have a positive day." Analyze why.
- Found: >80% of the day's loss was 9:30-4; v36's furious full-size buys
  after 1:35 -$932 in 6 trades; deploy overlaps ~-$508 (releases during
  market hours - my process failure). The replay's gains are premarket; its
  9:30-4 is near zero for v36 even with kind fills.
- The owner chose: stop v36/v36b buys 9:30-4 for the rest of today (r34.28,
  3:32pm). Not chosen yet: furious full size premarket only; releases after
  8pm only.

### CPHI 2:11pm: the deploy overlap, a stuck v36 - r34.27 (2:18pm)
- Flat when r34.26 was pushed (2:10:28), but the old process kept trading
  during the ~45s build/switch: it bought CPHI furiously for v36 and v36b and
  sold both (-$259, -$70). The new process adopted v36's CPHI 2s before the old
  one sold it, then looped selling 0 shares; v36's tick queue filled and
  dropped ticks. r34.27 (the owner's "Push r34.27 now"): a sale that finds
  nothing held closes the position. Day at 2:17pm: v36 -7.3% ($489 above its
  halt), v36b -5.3%, v37 -2.0%.

### Furious churn on SXTC; r34.25 and r34.26 (2:00-2:15pm)
- The owner: 9:30-4 every sell at market, as fast as possible ("those round
  trips of 2-3 seconds, 13 seconds back and forth, no good"); "cancelling and
  re-sending a market order during business hours is a bug". Sells 9:30-4 were
  already market orders (r34.17); r34.24 stopped the cancel-and-resend; r34.25
  sends the first sell straight out and logs each sell's order type.
  Premarket: market orders are not accepted - limits (the owner agrees).
- SXTC 1:40-1:59pm: 8 furious full-size trades, all losers, -$959 - buys
  filled above the print (v36's 6-second loop: $8.90 on an $8.75 print), a 10c
  stop inside 20-50c swings, buy-backs seconds apart; the 1:56 pair traded by
  the OLD instance during the deploy overlap.
- Offered A-D; the owner chose A only: v36/v36b furious buys use v37's fast
  buy (r34.26, live ~2:12pm). B (stop = larger of 10c and 2%), C (buy-back
  waits) and D (no buys 60s after a deploy) not chosen.

### SXTC 1:40pm: the exit too slow - r34.24 (live ~1:56pm)
- The owner sent the chart: v37 respected the high of the day and tried to
  get out at once, "but the exit did not work fast enough". The log: bought
  625 @ $7.75 at 1:40:07.7 (35% of the account) - the top tick of a candle
  $7.15 -> $7.74 -> $7.17; stop $7.65 (the new 10c); price ~$7.74 at
  1:40:10.5; stop decided at 1:40:14.0 on a $7.49 print; the sale 1:40:14 ->
  1:40:21.6, three market orders, the first two cancelled after partial
  fills (our follow() rule meant for buys), out at $7.29: -$290. v36 bought
  547 @ $7.73, out $7.32 (-$228); v36b filled $7.35 on a stale $7.72 print
  and sold on a 37c "gain" it never had (-$6).
- Built and released at the owner's OK ("Push r34.24 when flat"): market
  sells left to fill; the stop also on the live market (mid of bid and ask -
  the middle, because a premarket spread can be wider than a 10c stop); a
  furious gain counted from the fill. The owner is checking for a resistance
  level near $7.74 (open: should furious buys respect resistance?).

### The owner's furious exit, r34.23 (~1pm, live 1:35pm)
- The owner: "not the 8% - too big; these furious ones can crash faster than
  you would ever imagine. If the stock drops 10 cents from the entry, close
  it, and get back on it as soon as it moves above the high of the day
  again." Keep the 10-second leash. "Up 30 cents over the buy and back to
  it - cut it off there instead of a loss; above 30 cents, close it on
  giving back 30% of the gain." And on the levels (12:50pm): "bought at
  6.15... the stop should end at 5.98 or 5.99, not 5.80"; "at 1.65 coming
  back to 1.50 - if it breaches 1.49, 1.48, sell; a little more churning,
  but that's the best strategy overall". Decisions.
- The owner asked to see the table before releasing it. 7 days replayed, $15k,
  fills 0.2% / 1% worse, r34.22 -> r34.23: v36 +$8,583 -> +$12,487 /
  +$5,410 -> +$9,016; v36b +$10,466 -> +$13,377 / +$7,244 -> +$9,826; v37
  +$31,263 -> +$34,693 / +$19,122 -> +$20,019; worst days better for all
  three. The 1-minute replay cannot show the seconds inside a furious
  minute: live, the 10c stop will be hit more often. The owner: "Push r34.23
  when flat" - live 1:35pm.

### The owner's stop and furious rules, r34.22 (12:20pm, live 12:36pm)
- On DKI 11:37 (v36's first stop at the last minute's low, 16.6% under the
  buy, -$71 on a $406 starter) the owner chose "B": keep the chart stop,
  size the starter so a stop costs at most ~3% of a normal starter.
- And, the owner's words: "when it retraces to a .00 or .50 and breaches it -
  it goes under three - you sell immediately; you don't wait for 2.87; give it
  a little, five cents" (sometimes the owner sells at 2.99-2.98). Built as
  the stop 5c under the whole / half dollar under the buy, rising to each one
  the price clears and holds.
- Buys stay over the whole / half dollars (built 10-07 morning, V36_LEVELS)
  and every entry rule holds - except on a furious move: "throw everything
  through the window, get in really quick", and "the size should be
  increased - I enter with a full position on the very first hit; if I
  miss, I try again". v37 already sizes its fast buys by speed (35% of the
  account at 0.30).
- On exits: "when I see it has made enough, I get out... before I know it
  the gains have evaporated - here we control that, we should do better".
  Built for v36's furious buys: v37's give back a third once up 30%, the
  10-second leash, deep premarket exits.
- The owner: push as soon as all three are flat; then replay the seven days
  with the new entries, one table for the three strategies; and save the
  scanner's list through the day (ROSTER lines in the log, from r34.22). The
  recorded days hold the traded names plus the day's premarket and regular
  gainers, not the live scanner's list.

### r34.21 live: keep trying on furious movers only (12:05pm)
- The owner (~12pm): a fast buy must not stop at 20% over the breakout or
  after 6 seconds - "the market can stay irrational" - keep trying; then:
  remove the cap "only for furious movers... the rest maybe we should keep
  it because it's a nice safety net". Decision.
- Built (66bcb73), released as r34.21 (the owner's "Push r34.21 when flat",
  pushed 12:04:59, engine up 12:05:45): when the owner's speed says furious,
  each try is one limit at the ask + 20c (30c from $10), no price cap, no
  time limit, the next furious print over the old high tries again, paced
  0.5s a symbol and 35 orders a minute an account. Every other fast buy keeps
  the 20% net and the 6s/12-try loop.
- The 7-day replay is the same with or without it (v37 +$28,133 at fills
  0.2% worse, +$16,539 at 1% worse): 1-minute bars cannot show a 5-second
  chase. Almost all of the big-move gain is one replay trade (MI 10-05,
  +$10,048), and the replay's fills are kinder than live. Live results
  will tell.

### Furious moves: one order to the ceiling (~12:00pm)
- The owner: in a move like BIYA 8:20 the bot should act within a second
  and re-price every ~50 ms. Told: Alpaca takes about 200 requests a minute,
  so a send/cancel/check loop that fast would be refused within seconds;
  built instead (branch fa28edb, V37_SWEEP): a fast buy is ONE limit at the
  ceiling (the breakout level + 20%), filling at the best ask at once; the
  stop is set from the real fill. The owner agreed.
- The owner on latency: Alpaca paper (simulated) orders take about 200 ms;
  real money about 14 ms (the owner used 50 ms to be safe).
- Also built for the big moves (not yet released, replay running): trend
  checks with the live price; the fast-buy ceiling from the old high; speed
  counts as the crowd and lifts the 6-buy cap; at furious speed v36 sets
  trend, tape and room aside; the halt crowd rule 9:30-4 only (the owner: no
  halts premarket); a 5-second move measure logged; and the r34.18 bug fixed
  - the v37 high margin measured from the closed-candle high (a climb a cent
  at a time never cleared it; 10-05 replayed: 12 v37 trades became 1).

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
