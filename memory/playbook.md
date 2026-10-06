# The owner's manual playbook

How the owner traded by hand, February to about June 2026, for $5,000-10,000 a
month with 1-3 losing days a month. Told on 2026-10-05, in their words as far
as possible. This is the method the bot is meant to follow; anything not here
is not part of it.

## What to trade
- Stocks popping on news: the day's top gainers, where the traders are.
- Above all, the leader of the day or the second leader.
- The leader is the stock ripping NOW, not the day's top gainer: a stock up
  120% that has slowed loses to one up 30% that is ripping. "Speed and volume
  is everything" - go where everybody is.

## The screen (what makes a stock a candidate)
- Price $1-$20.
- Float under about 20 million shares - big floats are stodgy and do not rip.
- Relative volume at least 2-3x normal (often 5x or more), and rising.
- News - very important; very few trades without it.
- Chinese companies are fine - the owner made MORE money on them than on US
  ones - but they retrace fast: be on your toes and get out early, even while
  it is still going up. Give up a little of the top; never ride the collapse. Typical: an unprofitable pharma
  or biotech that raised money, did a reverse split, then has news.
- A reverse split (a 1-for-10 turns 50M shares into 5M; a depressed stock
  near $1 can go to $10) - on the DAY it takes effect, one or two days at
  most. It runs like crazy that day, then fizzles back to earth; it very
  rarely keeps the price. Catch that run; what comes after does not matter.
- Short interest / hard to borrow - some shorting helps: the short squeeze.
- No shelf: the company is not selling shares.
- Float rotation (the guru's tell): the shares traded churn through the float
  many times - a 5M float trading 20-40M shares within an hour. Supply small,
  demand huge.
- Then the key: wait for the stock to start running.

## Filters
- MACD positive.
- Price above VWAP and above EMA9; EMA9 above EMA20.

## Entry
- Wait for the stock to rip. Enter while it is running, quickly, in one hit.
  Sometimes waits for three candles; usually not.
- The first and second entries ("front entries") are the ones that make money.
- After a retracement well below the high of the day, wait for it to come back
  to the high of the day.
- Re-enter while the stock keeps really moving.
- The pattern most traders use: a green candle, then a red one; when the
  next candle turns green and the price goes over the red's open, buy. Stop
  at the bottom of the red. If that green turns red before it closes, out with
  a small loss. When the stock is ripping it goes up "almost 90%" of the time.
- Room: the next resistance must be at least double the risk away (usually
  much more). If it is close, no entry.

## Ripping, in numbers (the owner, 10-05)
- Two green 1-minute candles that add about 5-10% or more before the first
  red; a single minute often +2-5%, sometimes more.
- Volume rising bar by bar, the bars 3-5x the size of the bars before them.
- The tape and the order book moving fast.
- The entry the owner trusts most: a real, bigger ask on the book being eaten
  up fast by buys - enter as it goes; the stock jumps.
- Spoofed sell orders appear to scare buyers off, then vanish.
- Speed first: the new runner, not the leader that has slowed.

## Do not enter
- A stock flying on skinny volume with a wide spread: "stay away, period".
  The spread eats the gain and an order of a few thousand shares moves it.
- But when a stock with real volume is going to the roof, the spread does not
  matter: buy at once, even half a point over. 500 shares that then run $2 is
  $1,000 in two or three minutes. The guard is volume, not the spread.
  (The bot caps a buy at 2% over the ask - BUY_CHASE_CAP - which would miss
  these fills.)
- A green candle with a high wick (it retreated from its high).
- A wide spread, or a thinly traded stock - go to liquid stocks.
- Sell orders in the way on Level 2. Level 2 is "a must".

## Confirm with the tape
- Time and sales: most prints green (at the ask). Red = at the bid, white = in
  between.

## Coming back in (the same stock is hot two or three times a day)
- Ride it, or jump out, wait for it to come back and jump in again. It can
  cool off for minutes or hours - sometimes until the market opens - then come
  back roaring. Not a timer: a trigger.
- The trigger: price back at the high of the day, the bars growing, green bars
  lining up one after another on increasing volume - get ready to jump in.
- Coming back to the high slowly on small, skittish volume: be careful. Wait
  for a confirmation - above a resistance line, or a time of day when stocks
  start running (around the top of the hour, the open).
- Banning a stock for running (the no-chase rule) was "a huge, huge mistake.
  That's where the money is made."

## Levels
- Resistance levels, and the natural half-dollar levels (1, 1.50, 2, 2.50 ...).
- Approaching one: get ready to get out. If it bolts straight through, stay.
- Usually waits for it to go past the level before entering.
- Trading clusters around the half-dollar levels; the stock runs in the span
  between them and slows as it nears one. Inside a span, if Level 2 shows no
  sell orders in the way (say $2.22 to $2.39), one or two orders can take it
  from $2.20 to $2.40 to $2.50, through every line.
- Approaching a resistance level and the stock hesitates: jump out. Sometimes
  it bolts through anyway and the run is missed - then get back in. When
  demand is strong it goes through the levels one by one, nonstop: that is
  where most of the money is made.

## Size
- About 1,000 shares on $5-10 stocks; roughly $4,000-7,000 a position, one to
  three positions.

## Exit
- Out very quickly when it starts coming down. The 10-second chart is what
  says "out". Many trades are scalps.
- A short leash to start; as the stock builds gains, a longer one, so a
  runner can be ridden.
- Any red bar, or a bar flickering between green and red: prepare to jump
  out.
- When it starts to retrace, out completely - or reduce the position if the
  stock is not wild and is drifting down.
- Hot keys: one key in, one key out.

## The trader the owner learns from
- Grows $2,000 to $100,000 in 40-56 trading days, again and again, for
  charity; over $1.5M in half a year on a large account. Very selective.
- Trades only the leader, and only once it rips fast; knows which names
  repeat and which retrace. Enters, then keeps adding as it runs, with heavy
  leverage (8-9x; the owner's broker allows 4x). Watches Level 2 closely.

## Results
- Aim: 5-10% a day, not 100%.
- Over three to four months: 60-65% of trades won (some stretches 80%); the
  average win was bigger than the average loss, up to about double. Rare
  large losses; the rule is to jump out quickly.
- Most days about $350-550 (range about $150-1,000; "if I made six or seven
  hundred I'm happy"); some days over $1,000, a few over $2,000.
- The first bot built from this, before the added rules, ran about -1% to +1%
  a day.

## Numbers still to get from the owner
- "Ripping" in numbers: how far, in how long.
- How long a wick is too long; how wide a spread is too wide; how much volume
  is liquid enough.
- What on the 10-second chart means "out" (one red candle, a lower low, ...).
- Account size at the time; most positions held at once.
