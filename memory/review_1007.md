# Review of 10-07, written the night of 10-07 (words before code)

The owner asked for: the v37 SXTC loss and the buy timing; where the seconds
go in a sale; the live rules written out against `memory/checklist.md`, with
every hole, contradiction and stack marked; each loss tagged as the market's
or ours; and the scorecard idea. Nothing here is code, and nothing here is
live. Every change below is a PROPOSAL until the owner says yes.

## 1. The short version

The day, from the bots' 7pm summary (the broker's equity):
- v36 (T6HH): -$1,722 (-9.45%), ending $99 above its 10% daily halt;
- v36b (AUES): -$602 (-8.62%), ending $96 above its halt;
- v37 (P28T): -$293 (-2.01%).

Every trade is accounted for: the trades add up to the three accounts' change
to the cent.

**A correction.** At 4:10 I reported the day as v36 -7.9%, v36b -5.7%,
v37 -2.0%, and "all flat". That was wrong: the session runs to 8pm, and I
stopped watching at 4:06.
- r34.28 stopped v36/v36b buys from 9:30 to 4 only.
- From 4:22 to 5:00pm they bought four after-hours stocks (IRIX, AIXI, NCPL,
  ERNA), every one a furious full position. They lost all eight trades:
  -$289 for v36 and -$204 for v36b.
- v37 broke even on two.

From 9:29 to 8pm, v36 and v36b made 40 trades, all losers but one break-even.

Every losing trade is sorted into one of four causes:
- **market** - the rule did what it should and the stock went the other way;
- **rule** - the code did what the rule says, but the rule has a hole we knew
  of or could have known of;
- **code** - the code did not do what the rule says (a bug);
- **release** - two copies of the bot trading at once during a deploy.

| | market | rule | code | release | wins | day |
|---|---|---|---|---|---|---|
| v36 | -$274 | -$774 | -$391 | -$377 | +$95 | -$1,722 |
| v36b | -$78 | -$357 | -$53 | -$130 | +$15 | -$602 |
| v37 | -$8 | -$247 | -$128 | - | +$90 | -$293 |
| **all** | **-$360** | **-$1,377** | **-$571** | **-$508** | **+$200** | **-$2,617** |

**Of $2,817 lost on losing trades, $360 (13%) was the market. The other
$2,456 (87%) came from things we knew or could have known:** the rules, the
code and the releases. Section 7 has the list, trade by trade.

Three lessons carry most of the money:

1. **A full position with a 10-cent stop does not fit the stocks that are
   furious.** Those are the stocks with the widest swings. From 1:30 to 2:00,
   SXTC's 1-minute candles spanned 24c to $1.50, typically 74c (11% of the
   price). A 10c stop is 1.3% of a $7.75 stock, inside ten seconds of normal
   swing.
   - At 1:55, v36 and v36b bought SXTC at $7.91-7.92. Both were stopped out
     within 2 to 5 seconds.
   - In the next five minutes SXTC went $1.67 higher.
   - Full size times a stop inside the noise means full-size stop-outs, one
     after another: 8 SXTC trades, -$959.
2. **The bots bought the top of spikes.**
   - Of the 23 regular-hours buys after 1:35, 13 filled in the top 15% of
     their minute's range. Eight filled at the very top.
   - v37's SXTC buy at $7.75 was the top tick of the minute. It was 7.5%
     above the high of the 3 minutes before. Within 7 minutes SXTC fell to
     $5.13 (-34%). It got back over $7.75 only at 1:55, on the next run (to
     $9.59 at 2:00).
   - On a furious mover, nothing limits how far over the breakout a buy may
     pay. That limit was removed on purpose on 10-07.
3. **Releasing during market hours cost $508.**
   - The old copy of the bot keeps trading for 20-45 seconds after the new
     copy starts.
   - It traded at 1:56, 2:11 and 2:18. One position was sold by the old copy
     while the new copy still managed it.
   - This one is my process failure, not the market's and not the rules'.

**One thing to decide before 4am.** r34.28's "no v36/v36b buys 9:30-4" is
written for 10-07 only, and it never covered 4-8pm. Tomorrow from 9:30, v36
and v36b will buy furious movers at full size again, with the 10c stop. See
section 10.

## 2. v37's SXTC trade at 1:40pm: -$290, piece by piece

What happened (times ET):
- **Before the buy.**
  - SXTC was halted around 1:26-1:29 (the bars show no trades) and reopened
    at $5.53.
  - It pushed to $6.74 at 1:31, then $7.13 at 1:36, then fell back to $5.98.
  - 1:39: a green minute from $6.36 to $7.16, high $7.21, 895,000 shares.
- **1:40:06.2.** The first fast-buy try missed: one order at the ask + 20c.
- **1:40:07.7.** The second try filled: 625 shares at $7.75, worth $4,844,
  33% of the account.
  - The print it decided on was $7.73.
  - The size was the speed table's top tier: speed 0.46, so 35% of the
    account.
  - The stop was $7.65, 10c under the fill. Its score was 13.
- **The rest of the minute.** The candle opened at $7.15 and touched $7.74
  within its first 7 seconds. It closed at $7.17.
- **1:40:14.0.** The stop was decided on a $7.49 print, already 16c under the
  stop.
- **1:40:14.0 to 1:40:21.6.** The sale: three market orders. Each of the
  first two was cancelled after a partial fill and sent again; that was the
  bug fixed in r34.24. The average fill was $7.29.

Where the $290 went:

| piece | per share | dollars | cause |
|---|---|---|---|
| the planned risk: $7.75 down to the $7.65 stop | 10c | $62 | the rule |
| the stop to the first print acted on ($7.65 to $7.49) | 16c | $100 | the rule: the stop is checked only when a print arrives |
| that print to the average fill ($7.49 to $7.29), 7.5s | 20c | $128 | code: the market sell was cancelled and re-sent (fixed in r34.24) |

**Was the buy at the right time? No.**
- It bought the first seconds of a spike: about 8% in 7 seconds. This was
  the third push after a halt, at 1:40 in the afternoon.
- It paid 54c (7.5%) over the previous minute's high of $7.21.
- After it, SXTC fell to $5.13 by 1:47 (-34%). No stop width would have
  saved this trade; only not buying it, or a smaller size, would have. Getting
  out fast was right, and the sale was too slow.
- Our checks could not see the danger:
  - The wick checks look at closed candles. The 1:39 candle closed near its
    high, so it had no wick. The wick on the 1:40 candle formed after the
    buy.
  - The score was 13 of 15.
  - The speed was 0.46, the top tier, so the size was the top tier too.
- Three things would have shown the danger, and nothing in the rules looks at
  any of them:
  - how far over the breakout level the price already was;
  - how much of the minute's move came in its last few seconds;
  - this being a third push after a halt.
- The playbook says: "a green candle with a high wick: do not enter" and
  "approaching a resistance level and the stock hesitates: jump out." The
  owner reads that on the chart in real time. The bot reads it only on closed
  1-minute candles.

## 3. Where the seconds go in a sale

The regular-hours sales after r34.25 (2:07pm), measured from the log:

| time | bot | stock | decision to order sent | order sent to booked | decision print | fill | slippage |
|---|---|---|---|---|---|---|---|
| 2:18:40 | v36b | CPHI | 0.83s | 0.92s | $1.115 | $1.110 | -0.5c |
| 2:21:42 | v36b | CPHI | 0.73s | 1.61s | $1.150 | $1.170 | +2c |
| 2:22:50 | v36 | CPHI | 0.21s | 3.22s | $1.195 | $1.150 | -4.5c (3.8%) |
| 2:28:50 | v36 | NCPL | 0.44s | 2.35s | $1.630 | $1.636 | +0.6c |
| 2:28:50 | v36b | NCPL | 0.45s | 2.71s | $1.630 | $1.640 | +1c |
| 2:30:20 | v36 | MOBX | 0.23s | 3.90s | $1.330 | $1.320 | -1c |
| 2:30:20 | v36b | MOBX | 0.40s | 2.70s | $1.330 | $1.320 | -1c |
| 2:55:12 | v36b | PFAI | 0.24s | 2.25s | $4.680 | $4.640 | -4c |
| 2:55:30 | v36 | PFAI | 0.22s | 3.31s | stop $4.49, market $4.47 x $4.48 | $4.392 | -8c under the bid (1.8%) |

Before r34.24 and r34.25 (from 1:56pm), the SXTC sales at 1:36-1:40pm took
3.8-8.0s from decision to out, and v37's 1:40 sale took 7.5s.

A sale has four steps.

1. **Before the decision: 0 to several seconds.**
   - The stop is checked only when a print arrives. The middle of the bid and
     ask is also checked, but again only when a print arrives.
   - Quotes move first and much more often than prints. When the price falls
     fast or the prints thin out, the first print the bot acts on can already
     be well through the stop. At 1:40, v37's was 16c through: $100.
2. **Decision to order sent: 0.2-0.8s.**
   - Three trips to Alpaca before the order goes: list our open orders, read
     the position, and read a snapshot for the bid.
   - The bid is not used at all for a market order. It only sets a limit
     price that a market order ignores.
3. **Order sent to fill: 0.9-3.9s on paper.**
   - Alpaca's paper market orders fill in pieces over 1-6 seconds. This is
     where the slippage comes from: CPHI -4.5c, PFAI -8c under the bid.
   - Real money should be faster, but we cannot measure that on paper. The
     log does not yet record Alpaca's own fill time, so we cannot separate
     the broker's delay from ours.
4. **Fill to booked: 0.3-0.5s.**
   - Two more broker reads before the EXIT line is written: the position,
     then the equity. This costs nothing, because the shares are already
     sold.

What can be cut (PROPOSALS, words only):
- **S1.** Check the stop on every quote, not only on prints: when the middle
  of the bid and ask reaches the stop, sell. This targets step 1, where most
  of the 1:40 money went.
- **S2.** Before a market sell, do not read the snapshot for the bid. It is
  unused and costs one round trip. This is safe: nothing reads it.
- **S3.** Send the first market sell before reading the position, using the
  share count the bot already holds. Read the position after.
  - This saves one more round trip.
  - Risk: if the bot's count is wrong (sold elsewhere, a partial fill it
    missed), the sale could ask for more shares than are held. Alpaca may
    refuse that, or on a margin account open a short.
  - So S3 needs the checklist first; S1 and S2 do not.
- **S4.** Log Alpaca's own submitted and filled times on every order, so the
  paper-fill delay is measured, not guessed.
- **S5.** A market sell that is not filled in 6 seconds is cancelled and sent
  again, up to 8 times. In a LULD halt this repeats for about 50 seconds,
  then logs "STILL HOLDING". There is no halt plan yet; see hole H16.

## 4. The live rules (r34.28) in plain sentences

### All three bots
- **Hours.**
  - They trade 4:00am to 8:00pm ET.
  - No new buys from 9:29 to 9:31 (the opening auction) or after 7:00pm.
  - From 7:00pm they sell everything.
- **One stock's data** comes from one Alpaca data connection, shared by the
  three. Each strategy decides on each print, one print at a time, in order.
- **A print outside the live bid and ask** by more than 2c (or 0.5% of the
  price, whichever is larger) decides nothing. This works only while there
  is a quote under 2 seconds old. With no such quote, the print decides.
- **The daily halt.** An account down 10% on the day stops buying. After
  losing days in a row the threshold steps down to 5%, then 2.5%.
- **Exposure.** Never more than 95% of the account in stocks.
- **Selling.**
  - 9:30-4: market orders. Each is left up to 6 seconds to fill; what is
    left is cancelled and sent again, up to 8 times.
  - Premarket and after hours: limit orders 0.5% under the bid. For a fast
    or furious buy the limit is 10% under the bid. Each limit works 2
    seconds, then it is re-priced from the new bid, up to 8 tries.
  - A sale first cancels any order of ours working on the stock.
- **Dead stock.** No print for 10 minutes: sell.
- **A restart.**
  - Positions held at the broker are adopted with a stop 8% under the price,
    without their original rules (no furious exit, no level stop).
  - The day's high is read back from the day's bars, and so are buys per
    stock.
  - Candles, averages, the crowd's timing and the tape start empty.

### v36 (T6HH) and v36b (AUES): the same rules, three settings apart

**Which stocks.**
- On the scanner's list: $1-$20, up 10%+ on the day. Float 20M shares or
  less; a stock with an unknown float passes.
- "In the crowd" means any one of these:
  - one of the day's top 2 gainers with $1M traded in 5 minutes;
  - accelerating: 2 green minutes, each closing higher on more volume, at
    3x the normal minute, speed 0.15+, $250k+;
  - furious (below);
  - top 2 by money in the last 5 minutes, held there 2 minutes;
  - ripping in the last 2 closed minutes.
- At most 2 positions.
- At most 6 buys of a stock a day. That cap is lifted for the #1/#2 name at
  a new high, and for a furious stock.
- One buy a minute per stock, lifted for a furious new high of the day.
- Today only: no buys 9:30-4.

**The normal buy (not furious).**
- **The pattern.** Either:
  - a rip (2 green minutes adding 5%, or 1 adding 5%, each on 3x the volume
    of the 5 minutes before and $250k+), then a pullback, bought 1c over the
    last red candle's open; or
  - the high of the day breaking, on a candle with 2x volume.
- **After the first buy of a stock,** only the high of the day + 5c.
- **What blocks a buy:**
  - more than 5% over the trigger;
  - within 3c under to 5c over a whole or half dollar, until the price has
    held 5c past it for 3 seconds;
  - a re-entry under speed 0.1;
  - (v36b only) a last closed candle with a top wick over 60% of its range;
  - a failed trend: the price over VWAP, the 9 average over the 20 and MACD
    over zero are all required;
  - the tape: under 60% of the last 30 seconds' shares at the ask, or over
    40% at the bid;
  - room: the prior day's high within 2x the risk.
- **Size.**
  - A starter is a tenth of a full position (full = 25% of the account), so
    2.5% of the account.
  - It is cut so its first stop risks at most 3% of the starter's dollars
    (B).
- **Stop.**
  - The pattern's low, never closer than 1%.
  - v36b: never further than 3% under the price.
  - Never under the whole or half dollar under the buy minus 1c.
  - The highest of these wins.
- **Adds.**
  - +15c over the starter's price, on a new high that holds 2 seconds: to
    half a position.
  - +20c: to the full position.
  - Each add needs the 60/40 tape and must not be at a level.
  - After an add, the stop rises to the new average (the owner's decision).
- **Exits.**
  - The stop.
  - The line: when the price holds 5c past the next half dollar for 3
    seconds, the stop moves to 1c under it.
  - After an add: the 10-second leash, a red 10-second candle closing under
    the lows of the two before it (from 10 seconds after the add).
  - Up 10%: the trail, 2 average bars under the high, kept between 2% and
    25%.
  - v36b only: stops act only on prints under 2 seconds old. v36 acts on
    prints of any age.

**The furious buy.**
- **What "furious" means.** "Speeding" is all three of:
  - the owner's speed of 0.30+: the price's rise over the last minute times
    the volume ratio, with the price itself up 3%+;
  - $250k traded in the last 60 seconds;
  - the last closed candle not red.
- **What it does.** It counts as the crowd. It lifts the 6-buy cap and the
  one-a-minute rule.
- **What it sets aside:** the pattern (any print over the last minute's high
  and the day's high will do), the 5% limit, the levels, the re-entry speed,
  the wick veto, the trend, the tape and the room.
- **Size.** The full position at once: 25% of the account.
- **The buy.**
  - One order at the ask + 20c (30c from $10), working 0.5 seconds, never
    under the trigger - 1c.
  - Missed, it tries again on the next furious print, 0.5 seconds later.
  - There is no limit on how far over the breakout it pays.
- **The stop.**
  - 10c under the fill, or 1c under the half dollar under it, whichever is
    higher.
  - Never further than 8% under the price.
- **The exits.**
  - The stop.
  - The middle of the bid and ask at the stop.
  - The line climbing.
  - Once up 30c: out at the buy price, or on giving back 30% of the gain.
  - The 10-second leash from the first second.
  - The trail at +10%.
- **Back in at once** on a new high of the day while still furious: no wait,
  no limit.

### v37 (P28T)

**Every buy:**
- the scanner's list;
- above the real high of the day, clearing the closed-minute high by 2c or
  0.5%;
- on a print under 2 seconds old;
- not within 60 seconds of a sale unless 30c (or 10%) higher. A furious new
  high lifts this wait.
- A re-buy needs green 1-minute closes over the old high first (0, 0, 1, 2 by
  the buy's number that day) or extraordinary volume.

**Route A, fast.**
- Either the candles are accelerating at speed 0.15+, or the stock is
  furious (as above).
- The speed must be real (0.15+ by the price too) and the tape must be
  60/40.
- The price must be over the last minute's high.
- Size by speed:
  - 0.15: 4% of the account;
  - 0.20: 10%;
  - 0.30: 35%.
- Furious: one order at the ask + 20c/30c, no price cap, tried again on each
  print 0.5 seconds apart, never at or under the old high.
- Not furious: tries for 6 seconds or 12 orders, never 20% over the breakout
  level.

**Route B, the crowd.**
- #1/#2 by money in 5 minutes with $1M+ (or a top-2 gainer with $1M+).
- Up 3% in 60 seconds on $250k.
- Volume 2x normal and 70% of the busiest of the last 5 minutes.
- A score of 12 of 15. Ripping at speed 0.3+ skips the score, but never over
  a red candle or a 60% wick.
- The ask above the high.
- A tenth of a full position: full is 40% of the account alone, so 4%.
- Adds: +10c to half, +20c to full; a third step when beside another
  position.

**Stops.**
- A third of the last minute's move, 3-8% under the buy.
- A furious buy: never more than 10c under the fill.
- Never under the half dollar - 1c, but not closer than 1%.

**Exits.**
- The stop.
- The middle of the bid and ask at the stop.
- Half the gain given back, from the first cent, with the bid agreeing.
- A fast buy up 30%: a third of the gain given back.
- A furious buy up 30c: never back under the buy, out at 30% given back.
- A furious buy still furious on a new high 2%+ up: an add to 65% of the
  account.

## 5. The checklist, answered for the live rules

Each item is **covered**, **partly**, or a **hole**, with today's example.
"Hn" numbers are holes to close.

**The price it decides on**
- **H1. An old print.**
  - v37: only prints under 2 seconds old buy, add or sell (covered).
  - v36 and v36b buy on prints of any age.
  - v36b sells only on fresh prints.
  - v36 (T6HH) sells on prints of any age. Today it decided an APUS sale on
    a print 5.8 seconds old, and an SXTC 1:40 sale on one 13 seconds old.
  - **Partly.**
- **H2. A print outside the bid and ask.** Covered since r34.15, while a live
  quote exists. **Partly.**
- **H3. No quote, or a quote over 2 seconds old.** The print decides alone,
  and the mid-quote stop cannot fire. The buy reads the ask from a separate
  snapshot call: at 9:29 the two sources disagreed (SXTC). **Hole.**
- **H4. A gap past the stop, trigger or level in one print.**
  - Stop: the sale goes out at once (covered, but see H17).
  - Trigger: a normal buy stops 5% over. A furious buy has no limit (SXTC
    $7.75, 7.5% over the prior high).
  - **Hole for furious.**
- **H5. The decision print far from the fill.**
  - A buy never fills at or under the old high (covered).
  - Nothing checks the fill after it comes back. v36's 1:59:20 buy paid 15c
    over the print, and the market was already under the stop. That was the
    old 6-second loop, since replaced by one order.
  - v36b's 3% stop cap is measured from the decision price, not the fill.
  - **Partly.**

**The buy order**
- **H6. Fills above the print: how far.**
  - Furious: the ask + 20c on any stock under $10. That is 2.5% on an $8
    stock and 18% on a $1.10 stock (CPHI).
  - **Hole: cents, not percent.**
- **H7. Fills below the print** (the market already left).
  - The old-high floor protects v37 and furious buys.
  - "Sell at once if filled under the old high" is not built. A stop already
    above the fill is not checked: APUS 9:58, v36b bought and was stopped in
    the same millisecond.
  - **Hole.**
- **H8. Partial fills, no fill, refused, filled after the cancel.** Fills are
  counted from the broker; a cancelled order is read until it is closed.
  **Covered.**
- **H9. Paper fills slower than real money.** A furious buy works 0.5
  seconds, and paper often takes longer (FFR 12:25 missed). The 1-second
  proposal was not chosen. **Hole on paper.**
- **H10. The same stock bought again seconds after a stop.**
  - Normal path: one a minute, 6 a day, HOD + 5c, speed 0.1 (covered).
  - Furious: back in at once, no wait, full size. SXTC 1:59:20 and 1:59:29:
    two full positions in 10 seconds, -$258.
  - **Hole.**
- **H11. More than one process buying at once.** During a deploy the old copy
  keeps trading 20-45 seconds: -$508 today. **Hole.**

**The position**
- **H12. The stop: from the fill, how far, never above the fill.**
  - v37 and furious buys measure from the fill (covered).
  - A v36 normal stop has no distance cap; B shrinks the size instead. Today:
    DKI 16.6%. Earlier, SXTC 8:17 v36b had a stop 44% away, before r34.15.
  - "Never above the fill" is not checked (APUS 9:58).
  - **Partly.**
- **H13. The gain counted from the fill.** v37 yes; furious v36 since r34.24.
  **Covered.**
- **H14. Adds, and the floor after an add.**
  - The new high must hold 2 seconds (covered).
  - The floor jumps to the new average (the owner's decision). It cost APUS
    and DKI about $170 today.
  - **Covered as decided; the cost is known.**
- **H15. Sold elsewhere.** r34.27 closes a position when a sale finds
  nothing held. A position adopted at a restart gets an 8% stop and loses
  its furious and level exits. **Partly.**
- **H16. A halt (LULD).**
  - No plan. With no prints, nothing is decided until the reopen; the first
    print after it decides.
  - A sell sent during a halt is cancelled after 6 seconds and re-sent for
    about 50 seconds, then logs "STILL HOLDING".
  - DKI 11:31-11:35: held through it, which worked that time.
  - **Hole: the owner's rule is needed.**

**The sell order**
- **H17. 9:30-4: market, left to fill.**
  - Since r34.24, yes, for up to 6 seconds; then cancel and resend.
  - Three broker round trips before it goes, one of them unused (S2/S3).
  - The stop is checked on prints only (S1).
  - **Partly.**
- **H18. Premarket and after hours: limits.** 0.5% under the bid (10% for
  fast buys), 2 seconds each, re-priced, 8 tries. **Covered.**
- **H19. Partly filled, slow, refused, halted mid-sale.**
  - Partial and slow: covered.
  - Refused: falls back to a limit (covered).
  - Halted: H16.
  - **Partly.**
- **H20. Our own working order in the way.** Cancelled and confirmed first.
  **Covered.**

**The account and the process**
- **H21. A restart or release mid-day.** It wipes candles, averages and the
  crowd's timing; the old copy trades on. 14 releases went out during market
  hours on 10-07. **Hole: a process rule plus option D.**
- **H22. Loss limits.**
  - The account halt at 10% is covered.
  - There is no limit per stock (SXTC cost the three accounts $959 in 20
    minutes) and none per rule (furious lost 6 in a row and kept going).
  - **Hole.**
- **H23. Alpaca's ~200 requests a minute.** Buys are capped at 35 orders a
  minute an account. The CPHI zero-share loop is fixed. A starter that B cuts
  under $100 is worked out again on every print (CPHI 2:21: 272 times in 12
  seconds). The account read is cached, so that is log noise, not broker
  calls. **Covered.**
- **H24. The tick queue backing up.**
  - A sale runs inside that strategy's print handler, so no other stock is
    read while it sells.
  - 9:30 SXTC: the queue reached 20,000 and 30,278 prints were dropped.
  - A 7-second sale is 7 seconds blind on every other stock.
  - **Hole.**
- **H25. Many signals at once.** 2 positions, 95% exposure. Two furious
  stocks take 25% each; first come, first served, with no ranking. **Partly.**

**The session and the stock**
- **H26. Premarket vs 9:30-4.**
  - One rule set for all sessions.
  - The replay's edge is premarket (section 8). Over 8 days, v36 from 9:30
    to 4 makes -$954 at 0.2% worse fills and -$3,970 at 1% worse.
  - Today from 9:30 to 4: 34 trades, no wins. After hours (4-8pm): 10
    trades, one $2 winner.
  - The standing rule calls for a separate regular-hours design. None exists,
    and nobody has designed or decided anything for after hours.
  - **Hole.**
- **H27. $1 stocks vs $10-20 stocks.** Every cents rule changes meaning with
  the price:

  | rule | at $1.10 | at $7.75 | at $20 |
  |---|---|---|---|
  | the 10c furious stop | 9% | 1.3% | 0.5% |
  | the 30c furious arm | 27% | 3.9% | 1.5% |
  | the buy at ask + 20c | 18% | 2.6% | 1.5% (30c) |
  | v36 adds at +15c / +20c | 14% / 18% | 2% / 2.6% | 0.75% / 1% |

  CPHI, NCPL and MOBX could never reach the 30c arm; only the leash sold
  them. **Hole.**
- **H28. Wide spreads.**
  - The mid-quote stop helps.
  - A 10c furious stop can sit inside a 10c+ premarket spread and fire at
    once.
  - A furious buy has no spread check.
  - **Hole.**
- **H29. What the replay cannot see.** Every execution hole today was
  invisible to it: the cancel-and-resend, the 6-second loop, the phantom
  gain, the deploy overlap, slow paper fills. Recording prints and quotes
  live would let it replay seconds. **Hole.**

## 6. Contradictions and stacks

- **C1. Furious full size vs the 10c stop (H27).**
  - The faster a stock moves, the wider its normal swing, so the tighter
    stop is hit by noise.
  - The rule pairs the biggest size with the tightest stop exactly on the
    stocks that swing most.
  - SXTC 1:55: stopped in 2-5 seconds, then +$1.67 a share in five minutes.
- **C2. "Back in at once on a new high" + full size + 10c stop = churn.** Each
  loop costs a full-size stop plus slippage. SXTC 1:59: two full positions in
  10 seconds.
- **C3. One yes/no opens everything.** "Speeding" is one number over a
  60-second window, which a 7-second spike can dominate. That one number:
  - lets a stock in that is not the #1/#2 leader (it counts as the crowd);
  - lifts the 6-buy cap, the one-a-minute rule and v37's 60-second wait;
  - sets aside about 12 entry checks;
  - sets the size from a tenth to the full position;
  - for v37, removes the 20% safety net.

  No second opinion confirms it: v36's furious path drops the tape and the
  trend too. "The day's #1 and #2 first" and "speeding counts as the crowd"
  pull in different directions.
- **C4. B vs furious full: one yes/no multiplies the risk 4 to 27 times.**
  - A B-sized starter risks at most 0.075% of the account (about $14 on
    $18k).
  - A furious full position risks the 10c stop times 25% of the account:
    - about 0.3% on a $7.75 stock (4x);
    - about 2% on a $1 stock (27x; CPHI: $355).
  - Slippage comes on top. v36's SXTC at 1:40 planned $55 and lost $228.
  - CPHI at 2:21 shows both sides within seconds.
    - From 2:21:22 to 2:21:34, B cut v36's starter to $100 of stock with a
      12.6% stop, $13 at risk. That was under the $100 minimum, so on every
      print, 272 times, it bought nothing.
    - At 2:21:46 the speed read 0.31: a full position, 3,406 shares, with a
      7.2% stop, $286 at risk.
  - The owner's sizing words (10-07, near the close): "furiously fast:
    bigger position OK; fast but moderate: always a small starter, ease in".
    Bigger is the owner's call. How much bigger, and with what stop, is
    open.
- **C5. The same family, different eyes.** v36 decides on prints of any age;
  v36b and v37 only on fresh ones. The same print sells one and not the
  other.
- **C6. The exit stack on a furious v36 buy.**
  - Seven exits run at once: the stop (the highest of 4 rules), the mid
    quote, the climbing line, the 30c/30% giveback, the 10-second leash, the
    trail at +10%, the halt.
  - In practice the one that acts is "10c under the fill, or 1c under the
    half dollar" within seconds; the rest rarely get a turn.
  - This is not wrong, but the owner should know that the 30c and 30% rules
    did nothing today.
- **C7. The stop is checked on prints, while the market moves on quotes
  (S1).**
- **C8. The same size table at 4am and 1:40pm.** v37's 35%-at-speed-0.30
  tier was set from premarket runs. It was used at 1:40pm on a stock that
  had halted and was on its third push.

## 7. Today's losses, tagged

From 9:29 to 8pm (the "after the fixes" audit page has each trade's right /
wrong / fix, through 2:55pm):

| time | bot | stock | P/L | cause | why |
|---|---|---|---|---|---|
| 9:29 | v36 | SXTC | -$58 | code | wrong high of the day after the restart; stuck exit |
| 9:52 | v37 | WETO | -$68 | rule | a 1c touch counted as a new high; reloaded under it |
| 9:58 | v36 | APUS | -$43 | rule | 4c under $9 (level band too narrow); 9.2% stop |
| 9:58 | v36b | APUS | -$2 | rule | stale print; bought and stopped at once |
| 10:18 | v36b | APUS | -$10 | market | |
| 10:21 | v36b | APUS | -$3 | market | |
| 10:18 | v36 | APUS | -$7 | rule | the add bought the top; the floor jumped (owner's decision) |
| 11:28 | v36 | DKI | -$44 | code | the add after the top (r34.19 bug) |
| 11:28 | v36b | DKI | -$46 | code | the same |
| 11:37 | v36 | DKI | -$71 | rule | 16.6% stop |
| 11:37 | v36b | DKI | -$7 | market | |
| 1:36 | v36 | SXTC | -$14 | market | |
| 1:36 | v36b | SXTC | -$3 | market | |
| 1:40 | v37 | SXTC | -$290 | rule $162 + code $128 | the top tick, 35%, 10c stop, stop checked on prints / the cancel-resend |
| 1:40 | v36 | SXTC | -$228 | code | the 6-second loop filled at the top; stop on a 13s-old print |
| 1:40 | v36b | SXTC | -$6 | code | a phantom gain from a stale print |
| 1:55 | v36b | SXTC | -$9 | rule | 10c stop in the noise (then +$1.67) |
| 1:55 | v36 | SXTC | -$9 | rule | the same |
| 1:56 | v36b | SXTC | -$47 | release | the old copy |
| 1:56 | v36 | SXTC | -$119 | release | the old copy |
| 1:59:20 | v36 | SXTC | -$121 | code $61 + rule $61 | paid 15c over (old loop); 10c stop |
| 1:59:21 | v36b | SXTC | -$11 | rule | 10c stop |
| 1:59:29 | v36 | SXTC | -$137 | rule | back in after 9 seconds, full size, 10c stop |
| 2:11 | v36b | CPHI | -$70 | release | the old copy |
| 2:11 | v36 | CPHI | -$259 | release | the old copy; sold elsewhere |
| 2:18 | v36b | CPHI | -$13 | release | the old copy |
| 2:21 | v36b | CPHI | -$2 | market | |
| 2:21 | v36 | CPHI | -$68 | market | 3,406 shares; the sale slipped 4.5c |
| 2:26 | v36 / v36b | NCPL | -$4 / $0 | market | |
| 2:27 | v36 / v36b | MOBX | -$12 / -$12 | market | |
| 2:54 | v36 / v36b | PFAI | -$16 / -$1 | market | B shrank v36's buy to 37 shares |
| 4:22pm | v36 / v36b / v37 | IRIX | -$77 / -$10 / $0 | rule | furious full position after hours (24% of v36), out by the leash |
| 4:30pm | v36b / v36 | AIXI | -$54 / -$35 | rule | furious full after hours; v36b's stop sold 1c through it |
| 4:32pm | v36b / v36 / v37 | NCPL | -$80 / -$139 / +$2 | rule | furious on $20k in 5 seconds; full positions in a thin after-hours stock |
| 4:59pm | v36 / v36b | ERNA | -$38 / -$59 | rule | furious full; the limit sale filled 8c under a $3.14 print |

The after-hours trades are tagged "rule". Each stop or leash worked as
written, but the size came from the furious rule: 16-25% of the account in
thin after-hours stocks. A starter's size would have lost about a tenth as
much.

Premarket (4:00-9:29), from the morning audit:

| | won | market (plain stops) | rule: re-bought within 10 min of a loss | rule: decided on a print that was not the market | rule: stop over 10% away |
|---|---|---|---|---|---|
| v36 (22 trades) | 5, +$95 | 10, -$159 | 4, -$72 | 3, -$85 | |
| v36b (22) | 1, +$15 | 8, -$40 | 8, -$37 | 4, -$20 | 1, -$74 (SXTC 8:17, a 44% stop) |
| v37 (7) | 3, +$88 | 2, -$8 | | 2, -$16 | |

Most of the code and rule causes before 1:36 were fixed during the day,
r34.15 to r34.20. The rule causes after 1:36 are all one family: furious,
full size, a 10c stop, back in at once (C1 to C4). None of those is fixed;
only the 9:30-4 stop for 10-07 holds them off.

## 8. What the replay says about 10-07, and why its big number is wrong

The live code (r34.28, with the 10-07 block taken out), replayed on all 8
recorded days at $15,000 a strategy, fills 0.2% / 1% worse than the bars, by
session:

| | premarket | 9:30-4 | after hours (4-8pm) |
|---|---|---|---|
| v36 | 88 trades, +$64,052 / +$50,684 | 71 trades, 23% won, -$954 / -$3,970 | 16 trades, -$546 / -$1,492 |
| v36b | 86 trades, +$64,702 / +$51,265 | 73 trades, 23% won, +$690 / -$2,660 | 17 trades, -$1,438 / -$2,286 |
| v37 | 47 trades, +$157,770 / +$141,564 | 43 trades, 74% won, +$3,784 / -$1,759 | 8 trades, +$1,117 / +$69 |

- **The premarket totals are mostly two trades on 10-07.** The replay bought
  both at full size and sold near the top of a 1-minute bar:

  | trade | the bars | v36 | v37 |
  |---|---|---|---|
  | BIYA 8:20 | $2.54 to $28.54 in one minute | +$47,544 | +$116,752 |
  | SXTC 8:16 | $2.44 to $7.12 | +$5,655 | +$13,010 |

  Live, the code running at that hour (r34.14) had no furious full size. It
  did not buy BIYA, and v37 held a tenth of SXTC for one second (+$75).
- **Without those two trades, the 8 days' premarket:**
  - v36: +$10,853 at 0.2% worse fills, -$1,319 at 1%;
  - v36b: +$11,266 / -$1,973;
  - v37: +$28,007 / +$17,924.

  This is approximate, because those trades grew the account the rest of
  the day traded with.
- **Even the replay, with its kind fills, loses 9:30-4 on 10-07:**
  - v36: -$2,022 / -$3,304;
  - v36b: -$928 / -$2,335;
  - v37: -$1,883 / -$3,491.

  Live it was worse: the fills were not kind, and the releases overlapped.
- **The market reason the two sessions differ.**
  - From 9:30 to 4, a stock that moves too far too fast is paused for 5
    minutes (LULD: about 10% in 5 minutes, 20% under $3), then reopens
    either way. SXTC paused at 1:26.
  - Premarket has no such pause, so BIYA could go ten times in one minute.
  - The squeezes the furious rule is built for happen premarket. From 9:30,
    the same rule buys spikes that the pause and the crowd turn around.

**The what-ifs for decision 0, the same 8 days.**

$15,000 each, fills 0.2% / 1% worse:

| | v36, 7 days before 10-07 | v36, 10-07 | v36b, 7 days | v36b, 10-07 |
|---|---|---|---|---|
| as live (r34.28, every session) | +$12,492 / -$1,550 | +$50,060 / +$46,771 | +$13,366 / -$979 | +$50,588 / +$47,299 |
| (a) premarket only | +$11,181 / -$740 | +$52,870 / +$51,425 | +$11,540 / -$441 | +$53,162 / +$51,706 |
| furious at a starter's size, every session | +$7,074 / +$3,483 | +$30,347 / +$28,552 | +$7,048 / +$3,412 | +$30,038 / +$28,490 |

- **(a) gives up v36's 9:30-8pm trading.** Over the 8 days that made -$1,500
  at 0.2% worse fills and -$5,464 at 1%. On 10-07 alone it was -$2,811 /
  -$4,654. v36b looks the same.
- **Full size or a starter, when furious.**
  - On the 7 ordinary days, full size makes more only with kind fills (0.2%).
  - At 1% worse fills, the starter does better: +$3,483 vs -$1,550.
  - Full size pays on squeeze days: MI 10-05, BIYA and SXTC 10-07.
  - Live fills on today's furious buys were worse than 1%. At 1:40 v36 paid
    $7.73 for SXTC with the market at $7.33 x $7.44, about 4% over.
  - So full size is a bet on the rare squeeze, paid for in fills on the other
    days. Your call; the replay cannot settle it.
- **(b) a starter outside premarket.**
  - Furious at a starter's size, 9:30-4 only: +$862 / +$166 over 7 days and
    +$388 / -$269 on 10-07.
  - The same at full size: +$1,067 / -$667 and -$2,022 / -$3,304.

## 9. Does the bot learn? The scorecard (PROPOSAL)

Today it does not. Every number is fixed in the code. Results change nothing
unless we change the code, and we do that by hand, by eye, often mid-day.

Proposal, three parts. None of it changes a rule by itself.

1. **Every trade records why it happened.**
   - The route: furious, accelerating, crowd, or pattern.
   - The size tier, which stop rule set the stop, which exit sold it, the
     session.
   - The times: decision to order, order to fill, fill to out.
   - The slippage at the buy and at the sale.
2. **A nightly scorecard per rule and per session.**
   - Trades, % won, dollars, average slippage, live next to the replay.
   - A rule losing over its last N live trades is flagged for the owner (N is
     the owner's number, e.g. 10).
3. **Brakes inside the day, within limits the owner sets.** They only ever
   make the bot smaller or slower, never bigger. For example:
   - a route that loses 3 in a row goes back to starters for the rest of the
     day;
   - a stock that stops us out twice in 10 minutes gets no full-size buy for
     15 minutes;
   - a stock that has lost 1% of the account today is done for the day.

   Any permanent change stays the owner's decision. "Learning" here means
   measured and owner-approved, not the bot rewriting itself.

## 10. What I need from the owner

0. **Before 4am.** From 9:30 tomorrow, v36/v36b furious full-size buys come
   back. r34.28 covered 9:30-4 on 10-07 only; after hours was never covered.
   Choose one:
   - **(a)** v36/v36b buy only in premarket (4:00-9:29), every day, until a
     regular-hours design (and an after-hours one, if wanted) is written,
     checked and tested (my recommendation);
   - **(b)** a furious buy outside premarket goes back to a starter + adds;
   - **(c)** leave it as it is.

   Any of these needs a release, so it goes out tonight after 8pm while all
   three accounts are flat. v37 is untouched by all three choices.

   **(a) in words, with its checklist:**
   - **The rule.** v36 and v36b open positions only from 4:00 to 9:29am ET.
     From 9:29am to 8:00pm they buy nothing: no new position and no add. A
     position bought before 9:29 keeps every exit it has, and from 9:30 it
     sells at market as now. v37 is unchanged.
   - **The price it decides on, the buy order:** premarket unchanged. After
     9:29 there are no buys, so H4, H6, H7 and H10 cannot happen then.
   - **The position.** A starter bought at 9:25 would today still add after
     9:30, because adds do not go through the buy gate. Under (a) it does
     not: a buy is a buy.
     - The cost: a premarket starter that runs after the open stays small.
     - Your call: allow adds after 9:30 to a position opened premarket?
   - **The sell order:** unchanged.
   - **The account and the process.** A restart after 9:29 still adopts
     positions with an 8% stop (H15). That is unchanged and stays open.
   - **The session and the stock.** This closes H26 for v36/v36b by not
     trading where nothing has been designed or tested.
     - What it gives up: any 9:30-4 or after-hours winner.
     - The replay over 8 days (section 8): v36's 9:30-8pm made -$1,500 at
       0.2% worse fills and -$5,464 at 1%.
     - Live 10-07: 40 trades, no winner.
   - **What it does not fix:** the premarket rules themselves, including C1
     (full size with the 10c stop) and H27 (cents on cheap stocks).
1. **Releases only after 8pm or before 4am, all three flat.** Plus option D:
   no buys for 60 seconds after a start. That removes the $508 cause.
2. **Furious sizing (C1, C4).** "Bigger" when furious, but how big, against
   what stop? A proposal to write up in full, for the owner to read:
   - the stop sized to the stock's own last-10-seconds range;
   - the size from a fixed dollar risk, e.g. 0.5% of the account, so bigger
     than a starter and never a full 25% at a 10c stop;
   - no buy more than a set % over the last closed minute's high.

   At SXTC's $7.75 with a 40c stop and $90 at risk (0.5% of an $18,000
   account), that is 225 shares, not 625.
3. **Back in after a furious stop (C2).** Option C again: wait for the new
   high to hold 2 seconds, at most 2 a stock in 10 minutes.
4. **Selling faster.**
   - S1 (the stop on quotes) and S2 (drop the unused bid read) are low-risk.
   - S3 needs its checklist first.
   - S4 (log Alpaca's fill time) is measurement only.
5. **Cents into percent for cheap stocks (H27).** For example, the 30c arm
   becomes the larger of 30c and 10%.
6. **The scorecard (section 9):** yes, no, or change.
7. **Halts (H16):** during a LULD halt, hold, or sell at the reopen?

Each yes goes through `memory/checklist.md` in words, item by item, before
any code.
