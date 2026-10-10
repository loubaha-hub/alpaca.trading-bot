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
- The bot's own watch list (the scanner's names), the bot's price band $1-$20
  (PRICE_MIN / PRICE_MAX). **PROPOSED**, and a question: FRGT and SBFM were
  bought under $1. Inside $1-$20 v38 makes +$4,377, not +$9,254 (with the
  bot's buy checks); the 8 trades under $1 made +$4,877.
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
  - The chug (a slow stair-step climb): no formula found that pays
    (**PROPOSED: no chug signal for now**). Every version lost: 5 minutes
    +10% with the 3c floor 62 buys, 0 won, -$2,247; with the candle's low
    as the floor -$8,918; 3 min / 6%, 5 min / 15%, 10 min / 20% all lost.
    IPDN 10-06 ($3.10 -> $6.99) was not missed by the speed test: it fired
    seven times on the climb. Its buys were thrown out within 1-3 seconds by
    the 3c floor in a fast, wide market (7:26:52: bought $3.65, sold a
    second later 36c lower), and the climb's later bursts were under the
    day's high (the re-entry rule). A chug is a pullback stock - the
    playbook's buy-the-red-then-green - a separate study, not this one.

**How much** (**DECIDED** 10-09 ~12:30pm / ~7:20pm)
- The first buy: 10% of the account, a limit AT THE ASK (as v36b and v37:
  BUY_AT_ASK, never paying over). Tested: a buy filled 2c over the ask pulls
  the 3c floor inside the spread, the midpoint sells it at once, and v38
  falls from +$8,930 to -$7,841 (BIYA lost). Sales filled 1-2c under the
  bid: +$7,280 / +$5,630 (BIYA kept).
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
- **PROPOSED**: the last sale's price - back above where v38 was shaken out
  means the drop is repaired. It is a level before the high, with a market
  reason, and it is the owner's "a level before it". v38 logs each signal
  that this level blocked, and what the price did in the next 15 minutes
  (both sides). Decide again on unseen days.

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
1. The price band: $1-$20 as the playbook, or under $1 too? Two of the three
   monsters were under $1; inside $1-$20 v38 made +$4,377 of the +$9,254.
2. The re-entry level: the last sale's price (proposed), no level, or the
   day's high?
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
