# Before any rule is coded: the words, then the holes

The owner, 2026-10-07 ~3:40pm: "When you have it built, you will put it in
words and we'll examine those words really closely ... every hole plugged and
every contingency accounted for." Every new rule or change goes through this
before any code is written:

1. **The rule in plain sentences** - what it does, step by step: when it may
   buy, how much, at what price, what the stop is, what moves the stop, when
   it sells, how it sells. Which session it is for: premarket (4:00-9:30),
   regular hours (9:30-4:00, LULD halts), after hours (4:00-8:00).
2. **This checklist, answered in words for that rule** - each item: what the
   rule does in that case. "Not covered" is an answer, and a hole to close.
3. **The owner reads both** and says yes, changes it, or no.
4. Then the code, a test for each item that applies, the replay, and the
   release after 8pm (or when flat and the owner says now).

## The checklist

**The price it decides on**
- A print that is old (seconds or minutes late).
- A print outside the bid and ask (a stray print, a stale quote).
- No quote at all, or a quote older than 2 seconds.
- A gap: the price jumps past the trigger, the stop, or a level in one print.
- The decision print is far from where the order will fill.

**The buy order**
- Fills above the print (how far is allowed - cents, percent, $1 vs $20 stock).
- Fills below the print (the market already left - is the trade still valid?
  Is the stop still under the fill?).
- Fills partly; does not fill; is refused; fills after it was cancelled.
- Paper fills take longer than real money (0.5s was often too short today).
- The same stock bought again seconds after a stop (how often, how big).
- More than one strategy or process buying the same stock at once.

**The position**
- The stop: measured from the fill, never from a stale print; how far at most
  (cents and percent, on a $1 stock and a $20 stock); never above the fill.
- The gain: counted from the fill and from prices after it, never from the
  print that triggered the buy.
- Adds: only on a new high that holds; what the floor does after an add.
- Sold elsewhere (another process, a manual sale, a broker action): the bot
  must see it and stop managing a position that is gone.
- A halt (9:30-4 LULD): nothing can be sold - what happens when it reopens.

**The sell order**
- 9:30-4: a market order, left to fill, never cancelled and resent.
- Premarket / after hours: limits only - how deep under the bid, re-priced
  when not filled.
- Partly filled; slow to fill; refused; the stock halts mid-sale.
- Our own working order in the way (a buy left working blocks a sell).

**The account and the process**
- A restart or release mid-position: the old process keeps trading 20-45s
  after the new one starts; positions adopted without their rules.
- The daily loss halt, the position and exposure caps.
- Alpaca's ~200 requests a minute per account; a loop that calls the broker
  on every print.
- The tick queue backing up (a slow handler on every print).
- Many signals at once (several stocks furious together).

**The session and the stock**
- Premarket vs regular hours vs after hours: different order types, spreads,
  halts, volume - a rule made from premarket runs is not tested for 9:30-4.
- $1 stocks vs $10-$20 stocks: cents rules (10c, 20c, 30c) mean 10% on one
  and 0.5% on the other.
- Wide spreads (premarket): a stop inside the spread.
- The replay cannot see seconds (1-minute bars, kind fills): what only live
  trading will show, and how to check it safely.
