# v38 - the speed strategy, in words for the owner to read

Draft 1, written 10-09 night / 10-10, before any code (the owner's "words
before code"). Status: NOT BUILT. Each part is marked **DECIDED** (the owner
said so, with the time) or **PROPOSED** (mine, for the owner to say yes, change
or no). The questions for the owner are collected at the end.

## Why
- On the full second-by-second read (10-06..10-09, 99 windows: the bots' buys
  and each day's top runners), v38 with the owner's trailing thirds made
  +$8,930 ($7,500 full position, $15,000 account): premarket +$10,240,
  regular hours -$274, after hours -$1,036. The three bots on the same days:
  v36 -$2,733, v36b -$1,362, v37 -$2,165.
- What kind of strategy it is: 188 trades, 8 won. Average win +$2,135,
  average loss -$45 (median -$29); 71% of the losers are out within 5
  seconds. Three stocks made it all: BIYA 10-07 +$11,331, FRGT 10-06 +$2,874,
  SBFM 10-07 +$2,504. Without them: -$7,778. Longest run of losers: 65 trades.
  Many tiny losses and a rare monster. It pays only if it is in the monster.
- The replay's fills are invented and kinder than the live market, and these
  four days were used to design v38. There are no unseen days yet (see the
  questions).

## The rule in plain sentences

**Which stocks, when**
- The bot's own watch list (the scanner's names), priced **$0.50-$20**
  (**DECIDED**, the owner 10-10: "take the bar down to 50 cents and we should
  not go below that" - a 50c stock going to $2 is 4x; they trade in big lots
  with spreads under a penny). The scanner's list is $1-$20 today: it must
  add $0.50-$1 names for v38 only (v36 / v36b / v37 keep $1). FRGT and SBFM
  were bought under $1: inside $1-$20 v38 made +$4,377 of its +$9,254; the 8
  trades under $1 made +$4,877.
- The cents rules do not fit them (the owner): +10c / +20c is +20% / +40% on
  a 50c stock, the 3c floor 6%. In percent the spreads are alike at every
  price (the read's median: 0.59% under $1 - 0.45c -, 0.68% at $1-$3, 0.59%
  at $3-$10, 0.67% over $10), so steps and a floor in percent would fit all
  of them. **OPEN**: a percent version, to test before the build.
- Paper: 4:00am-8:00pm; no new buy from 7:00pm, everything sold from 7:00pm
  (the bot's FLATTEN_AT / close_loop). **DECIDED** (the owner, 10-09 ~7:50pm).
- Real money: premarket only (4:00-9:30). **DECIDED** (~9pm). Open: what a
  position held at 9:30 does (see the questions).

**The buy - the speed test** (**DECIDED** 10-09 ~2:15pm; the numbers, as I
read the owner on 10-09 night, stay: 3%, 0.30, 30). All four at once, on
prints that qualify (the bot's qualifies()):
- the price now at least 3% over the price 60 seconds ago;
- the volume ratio (shares in the last 60s / the 60s before, capped at 30)
  times that move at least 0.30;
- at least $250,000 traded in the last 60 seconds;
- the last closed 1-minute candle not red.
- Plus the checks the bot's furious buy already has, which v38 inherits:
  no buy over a 10c spread, none unless the price is up over the last 5
  seconds, none on a print off the bid/ask (2c or 0.5%), a quote needed.
  Tested: +$9,254 with them vs +$8,930 without - neutral; they stay.
- Tonight's tests of the owner's points on the speed test (v38_gaps.txt):
  - The red candle stays (**PROPOSED**). Off: +$346 overall, all from one
    earlier SBFM entry in regular hours. In premarket the check is worth
    +$737. The owner's "bad omen" holds there.
  - A stock waking up from no volume stays as it is: no shares the minute
    before means no signal (**PROPOSED**). Counting it as the full ratio
    added 20 trades, 0 won, -$2,093, all in regular hours. That is most
    likely the reopen after a LULD halt (no trades during a halt), the
    moment WFF 10-09 lost on.
  - The chug (a slow stair-step climb). The owner, 10-10: 5 minutes is too
    short - "if it goes up 10% in the first twenty minutes, then we can get
    into that". Tested (v38_chug.txt): over the last 20 closed minutes up
    10%+, $250k a minute on average, the last candle not red, the price over
    all their highs. With the 3c floor it never works (0-1 won in every
    setting). With the floor at the last candle's low (at most 10%) it
    caught WFF 10-09 ($1.75 -> $14.40) in every setting - +$14,479 with the
    last-sale re-entry level - and its other buys lost: 20 min / 10% the
    chug buys +$4,634 (32 buys, 3 won), without WFF -$9,533; 15 / 30 min and
    15% the same picture (+$4,558..+$9,392; without WFF -$4,775..-$9,609).
    By session (20 / 10%): premarket -$982, regular hours +$8,141 (WFF),
    after hours -$2,524. A chug needs a leash a minute wide, not 3c.
  - The owner, 10-10: the chug for REGULAR HOURS only (9:30-4:00) - not
    premarket ("the time is short, the spreads wider, the trading
    thinner"); in regular hours there are six and a half hours, lower
    spreads, slower runs - "one or two a day, maybe none ... they make a
    little bit of money, that's good". Tested (v38_chug_rth.txt; no re-entry
    level, a limit at the ask + 2%): 20 min / +10% 12 chug buys, 2 won,
    +$15,027 (WFF +$14,479, SXTC 10-07 12:53 +$4,596), without WFF +$860;
    15 min / 10% +$13,526 (-$641); 30 min / 10% +$14,345 (-$134); 20 min /
    15% +$16,427 (+$2,260); 60 min / 30% 3 buys +$9,445 (+$3,284). About 2-4
    a day; about even without WFF. With the last sale's price as the level,
    worse (without WFF -$3,539..-$6,706). **PROPOSED**: the chug 9:30-4:00,
    20 min / +10%, the floor at the last candle's low (at most 10%).
  - The owner's breather (a run, a pause, buy as it goes again - the
    playbook's first red then green; v38_breath.txt): premarket negative in
    every setting (-$910..-$3,040); the plus came from WFF only and was not
    stable (10 min / 20%+ +$14,466; 30%+ -$5,679). **PROPOSED: not now.**
  - The owner's scouts (1-2% in the top runners before the speed, the
    first rung of the ease-in; v38_scout.txt): they cost -$4,718..-$22,210
    over the four days at every setting (2%: 342 scouts, 4 won, -$17,792;
    258 reached the first add, 3 of the 84 that got full won). A stock up
    20% near its high wiggles 10c all the time - the adds bought the
    wiggles. **PROPOSED: no scouts.** The owner's later versions -
    adds only as the speed picks up, step by step (v38_scout2.txt): about
    even (-$163..+$779); the floating 1% scout with a speed path and a chug
    path (v38_scout3.txt): -$660..-$2,117 against speed only, the chug lots
    0 of 54 won. A floating 1% scout could be a paper-account experiment.
  - Fire earlier? (the owner: "early on the volume is not there yet"). The
    speed 0.30 -> 0.25 / 0.20 / 0.15, the move 2%, $150k (v38_thresholds*):
    the first signal in the first quarter of a 40%+ run: 11 of 39 now, 12
    at 0.15. Lower numbers do not fire earlier - before the explosion the
    price is not moving. With no re-entry level BIYA is kept at every
    setting (+$34,895..+$41,665; totals +$39,156..+$58,280). **PROPOSED: the
    numbers stay** (3%, 0.30, $250k).
    IPDN 10-06 ($3.10 -> $6.99) was not missed by the speed test: it fired
    seven times on the climb; the 3c floor threw each buy out in 1-3 seconds
    (7:26:52: bought $3.65, sold a second later 36c lower).

**How much** (**DECIDED** 10-09 ~12:30pm / ~7:20pm)
- The first buy: 10% of the account. **HOW IT FILLS decides the big runners**
  (the owner, 10-10: "if we exclude the two or three big runners, the
  strategy is dead in the water"; "willing to go ten, twenty cents above the
  ask not to lose the big runners" - but in a thin premarket the many quick
  losers pay it too). The replay had filled every first buy at the ask one
  second after the signal - a limit with no ceiling that never misses.
  Tested (v38_fills.txt, v38_limits.txt):
  - One second late is enough to lose BIYA if the re-entry level is the
    day's high: BIYA +$11,403 -> +$195 at 2 seconds. The breakout of the
    day's high came in the vertical part (dollars a second): under the
    day's high no limit caught it, not even the ask + 20c (+$72). Over the
    last sale's price v38 is in at the wake-up ($2.65-$2.82), before the
    vertical part: BIYA +$10,227..+$40,675 with fills 1-5 seconds late.
  - A real limit, the re-entry over the last sale's price: at the ask -$151
    (BIYA missed, 275 misses); the ask + 2c +$31,500 (BIYA +$34,989); + 5c
    +$31,315; + 10c +$33,017; + 20c +$33,159; + 1% +$30,934; + 2% +$32,521
    (no ceiling +$33,046) - filled at the ask when filled (kind).
  - What paying over costs when every fill pays it all (the unkind end):
    1c +$29,480, 2c +$27,082, 5c +$15,749, 1% +$25,614. The losers are most
    of the trades - the owner's worry, in numbers: about $1,800-$3,600 a
    cent over four days. Live, v37's ask + 20c limits paid 0.8% over the
    ask on average (10-06..08).
  - Paying over is safe only if the floor is measured from the market: 2c
    over with the floor under our fill -$2,642 (day's high level, BIYA
    lost); under the ask we bought into +$5,651 (BIYA kept).
  - Live 10-09 (buy_short_1009.txt): even v36's ask + 20c got nothing at
    times (AIXI 1:04pm three tries, FLYE 3:05pm, ZYBT 3:06pm, AAOX 9:31am):
    each try works 0.5s and is cancelled; paper fills can take longer. The
    next try waits for the next furious print, 0.5s+ later - not the fast
    loop of 0.2s the owner had in mind (the adds do re-price every 0.4s).
  - **PROPOSED**: a limit at the ask + 2% (1c on a 50c stock, 6c at $3, 10c
    at $5, 20c at $10 - the owner's 10-20c on the bigger stocks); while it
    has not filled, it stays working and is moved up to the new ask + 2%
    (one replace, never two orders live), for as long as the speed holds;
    the floor 3c under the lower of our fill and the ask we bought into;
    no re-entry level (below). To verify when building:
    Alpaca's replace-order call (one request, not cancel + new); the ~200
    requests a minute per account.
- Sales filled 1-2c under the bid: +$7,280 / +$5,630 (BIYA kept).
- At +10c over the first fill: up to 25% of the account; at +20c: up to 50%
  (the full position). Each add at the ask, at any price; the shares already
  held count (a partly filled first buy gets a bigger add).
- Two stocks at once, each up to 50% of the account (**DECIDED** ~9:10pm). A
  third signal while both are held: no buy, logged. Tested: 2 of 188 trades
  blocked (-$41). The read holds only 99 windows - live sees more stocks.

**The floor and the sales** (**DECIDED**: the trailing thirds, the owner's,
10-09 ~7:45pm)
- The floor: 3c under the first fill; after each add, 3c under the new
  average. It sells everything when a print or the bid-ask midpoint is at
  or under it (the bot's own stop works this way). Tested: a floor on prints
  only +$9,627, on the bid +$7,791, 3% under +$6,601, 5% under +$2,607 - the
  tight floor stays.
- Nothing is sold on the way up. Once the position is full (50%): a third
  sold when the price is 20% off its peak since the last add, another third
  at 40% off, the rest at 50% off - or everything at the floor, whichever
  comes first. The peak comes from prints that pass the off-quote check (a
  stray print sets no peak).
- Before it is full, only the floor sells.

**After the day is down $500** (**DECIDED** in parts, 10-09 ~8:50pm-9:30pm)
- Smaller: 5% of the account, 10% at +10c, 25% at +20c.
- The top-up: a stock up 30% over its average once full (**PROPOSED** +30%;
  the owner said "when it is really running"; +30% tested best of 30/50/100%)
  is taken to 50% of the account at the ask. The top-up is a SEPARATE LOT
  (**DECIDED** ~9:30pm): its own floor 10% under its fill, its own trailing
  thirds. The starter keeps its floor (its average less 3c) and its thirds.
  A lot at its floor is sold alone. No limit on how many a day.
- "The day is down $500" - **PROPOSED**: the account's equity now against its
  equity at the day's start (closed trades and open positions, winners and
  losers) - one number, the same base as the -10% shut-off. (The test counted
  closed trades plus running winners.)
- Tested on the real days: +$10,212 all day (worst day -$1,327); premarket
  only +$10,648 (worst -$940).

**The catastrophic shut-off** (**DECIDED** ~8:55pm): always on - at -10% of
the day's starting equity everything is sold and v38 stops for the day (the
bot's halted() / flatten_all, checked every 5 seconds). Under the bot's
ladder the days after a halt day stop sooner (5%, then 2.5%, then a full
stop) - **PROPOSED** to keep the ladder for v38.

**Coming back in** (**DECIDED**: re-entries are a must, 10-09 ~2:30pm; the
level is open - the owner, 10-09 night: "we don't have to wait for the high
of the day ... you have to have a level before it", not a clock)
- The first speed signal of the day in a stock needs no level.
- Every later buy in it needs the speed test AND a price over a level.
  Tested with the bot's buy checks (v38_levels.txt):

  | the level | trades | won | total | PRE | RTH | AFTER | without BIYA 10-07 |
  |---|---|---|---|---|---|---|---|
  | the day's high (as decided) | 173 | 7 | +$9,254 | +$10,033 | +$249 | -$1,028 | -$2,148 |
  | the price of v38's last sale of it | 333 | 13 | +$33,046 | +$34,811 | -$397 | -$1,368 | -$1,998 |
  | no level (the speed test alone) | 424 | 16 | +$44,209 | +$45,501 | +$245 | -$1,536 | +$2,773 |

  With the sales 1c / 2c under the bid: the day's high +$7,565 / +$5,877;
  the last sale's price +$30,043 / +$27,021; no level +$40,820 / +$37,431.
  The order holds. "The highest price since the last sale" was worse than
  all three (+$3,776; too much churn under it).
- What the table says: the day's high blocks the wake-up. BIYA woke at
  8:20:38 at $2.65, under its $3.10 high from 4am, and ran to $33.96 within
  a minute. Over the last sale's price let it in at $2.82 four seconds later
  (+$34,972); with no level at $2.65 (+$41,519). Over the last sale's price
  keeps the other days about where they are today. No level at all did as well or better, but with 2.5 times the trades.
  All of it rests on one stock on one day.
- The last sale's price can block the monster too: at speed 0.20 a 4:55am
  trade sold BIYA at $2.93, three hours before - and the 8:20 wake-up asks
  were $2.65-$2.86, under it (v38_thresholds.txt: BIYA -$44). Any price
  level can sit near an old high and block the explosion.
- With the real limit (the ask + 2%), at nine speed settings: no level kept
  BIYA every time; the last sale's price lost it at two. Totals: no level
  +$39,156..+$58,280 (without BIYA +$392..+$16,615); the last sale's price
  -$3,757..+$36,278.
- **PROPOSED (changed 10-10): no re-entry level** - every speed signal may buy,
  as long as v38 does not hold the stock. The speed test is the filter
  (3%+ in a minute on rising volume and $250k); a level adds nothing but a
  way to block the wake-up. It goes against the owner's "you have to have
  a level before it" - the owner's call. v38 logs every re-entry, and live
  results decide.

## The checklist, answered

**The price it decides on**
- Old print: the speed test uses each print's trade time; v38 uses the bot's
  fresh-print check (2 seconds, as v36b's exits) for its sales. **PROPOSED**:
  for its buys too - v36's entries have no print-age check today.
- A print off the bid/ask: decides nothing (2c or 0.5%) - as the replay.
- No quote / an old quote: no buy without a quote (the fast-buy check). A
  quote streams for crowd names and held names; otherwise the buy reads a
  snapshot. Covered.
- A gap past the floor or a third: the sale is at the bid of that moment,
  wherever it is - the replay prices it so.
- The decision print far from the fill: the limit IS the ask read just
  before sending; it fills at the ask or under, or not at all.

**The buy order**
- Fills above the print: never over the ask (a limit at the ask).
- Fills below the print: the floor is measured from the fill, so it is
  always under the fill.
- Partly: the shares filled are the position; the adds top it up to 25% /
  50%. Not filled: no position; the next signal tries again (0.5s apart).
  A fill after the cancel: the bot's 60-second check with the broker
  corrects the count (QTY-FIX). Covered.
- Paper fills kinder than real money: yes - why the paper account runs next
  to the real one.
- The same stock again seconds after a sale: allowed, only at speed over the
  level. At no level it would be every 2 seconds in a spike (BIYA 8:20).
- Another strategy in the same stock: each strategy has its own account; one
  position per stock within v38.

**The position**
- The floor from the fill, 3c (and after each add from the average); never
  over the fill.
- The gain counted from the fill and the prints after it.
- Adds at +10c / +20c over the first fill; a new high of the day is not
  needed (the price is already over the fill); the floor rises to the
  average less 3c.
- Sold elsewhere: the bot's 60-second check clears a position the broker no
  longer has (GHOST-CLEAR), and fixes the count. **PROPOSED**: with two lots,
  shares that are missing come off the top-up lot first.
- A halt (9:30-4 LULD): **NOT COVERED** - nothing sells during a halt; at the
  reopen the floor and the thirds read the first prints and sell (a market
  order in regular hours). WFF 10-09, 8 halts: -$824. Paper only in regular
  hours; real money premarket has no LULD bands (a news halt still can
  happen - covered the same way).

**The sell order**
- 9:30-4: a market order, left to fill (the bot's). Premarket / after hours:
  a limit 10% under the bid for a speed position (the bot's furious
  "deep" sale), re-priced each pass, 8 passes. Covered as the bot does it.
- A third of the position is a smaller order than a whole sale - fewer shares
  into the bids.
- Partly / slow / refused: the next pass tries again; shares left log
  "STILL HOLDING". A halt mid-sale: **NOT COVERED** (as today).
- Our own buy in the way: the sale cancels it first. Covered.

**The account and the process**
- A restart mid-position: **A HOLE**. The bot adopts the shares without
  v38's state: no lots, no peak, no thirds, a generic stop. **PROPOSED**:
  (1) never release with v38 holding (the standing rule: flat or after 8pm);
  (2) if it happens anyway, v38 rebuilds its state from the day's fills -
  the starter's average, the top-up's fill, the thirds already sold - with
  the peak from the price at the restart (the adoption logged).
- The caps: the bot's per-position cap is 25% and its exposure cap 95%. v38
  needs 50% a stock and 100% in all. **PROPOSED**: 50% / 100% for v38 only,
  with its self-check cap at 60% (otherwise it logs false CRITICALs).
- Buying power for real money: two positions of 50% is the whole account.
  **A HOLE, for the real account**: check the account type's day-trade
  rules for its size (pattern day trader, or a cash account's settled funds)
  before it opens - v38 trades many times a day.
- Orders a minute: few per trade (a buy, two adds, a top-up, three thirds);
  the bot's 35-a-minute buy budget caps re-entries.
- Many signals at once: two positions at most; first come, first served.
  The standing rule says the day's #1 and #2 leaders come first. **NOT
  COVERED**: a weak stock can take the room a leader needs. 2 of 188 in the
  read; the log will count it live.

**The session and the stock**
- Premarket vs regular vs after hours: every table is split. v38 earns its
  money premarket. Regular hours is -$274 (with halts); after hours -$1,036.
- $1 vs $20 stocks: **A HOLE**. The floor (3c) and the steps (+10c / +20c) are
  cents. On a $15 stock 3c is 0.2% - noise. The read is mostly $1-$8 (3
  trades over $10, -$385). **PROPOSED**: build as tested, watch $10+ live, and
  turn them into percents only on evidence.
- Wide spreads: no buy over 10c. The 3c floor still sits inside a 6c+ spread
  (IPDN). That is a known cost: the losers are the spread.
- What only live trading shows: fills, partial fills, slow paper fills. The
  paper account is the check.

## Rules it touches
- v36, v36b and v37 are untouched; v38 runs on its own account.
- The playbook's rule sheet (memory/rules.md):
  - The rip and the entry pattern (two green candles, the tape, the first
    red) are not v38's. The speed test is its one entry.
  - Size "about $5,000, at most 2 at once": v38 is 50% of the account, 2 at
    once.
  - The exits: a short leash first (the 3c floor), a longer one once it has
    run (the thirds) - the same idea.
  - Coming back in "at the high of the day, a trigger, never a timer": the
    owner's new "a level before it" changes the level, keeps the trigger.
  - "Judged by a win rate against 60-65%": v38's is 4%, with its average win
    47 times its average loss. A different kind of strategy - **the owner's
    call** how to judge it.
- Replaced on 10-09: the half-back line and the quarter scale-out (by the
  thirds); "A then B" (made moot by the thirds); one floor (by the separate
  lots).
- The standing rule "the #1 and #2 leaders first, never banned for ripping":
  v38 never bans a runner; it does not rank leaders (above).

## Questions for the owner
1. ANSWERED 10-10: $0.50-$20. Open: the steps and the floor in percent for
   them (to test).
2. The re-entry level: no level (proposed 10-10), the last sale's price, or
   the day's high?
3. Which account runs v38 - one of the three (replacing v36, v37 or v36b),
   or a fourth?
4. "Down $500": the account's equity against the day's start (proposed)? A
   fixed $500, or a percent of the account (3.3% of $15,000)?
5. The top-up at +30% (tested best)?
6. Real money: a position still held at 9:30 - kept on its floor and thirds
   until it exits, with no new buys (proposed), or sold at 9:30?
7. Unseen days: a one-time read of earlier days' top runners (e.g. 9-29..
   10-03), second by second, after 8pm, read-only - needs a release with the
   owner's OK. Or the paper run itself as the first unseen days.
8. The first buy: a limit at the ask + 2%, kept working and moved up while
   unfilled (proposed) - or a cents ceiling (2c / 5c / 10c / 20c)?
9. ANSWERED 10-10 (the owner): the chug in regular hours only. Proposed
   numbers: 20 min / +10%, the floor at the last candle's low.
