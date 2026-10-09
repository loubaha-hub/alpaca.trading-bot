# Buy at the ask (v37, and v36b's furious buys) - words for the owner to read

Written 10-08 ~9:40pm, before any code (the owner's "words before code").
Status: PROPOSAL - waiting for the owner's yes / change / no.

## Why
The costs: v37 paid ~$740 over the ask it saw a second before its fills on its
114 trades with no adds (10-06/07/08) - 0.8% of what it bought; spread + paying
up was more than v37's whole loss. Its fast buy is a limit at the ask + 20c
(+30c from $10): on a thin stock it buys through the offers to the top of the
one-second burst. A limit at the ask buys only where sellers already are.

## The rule in plain sentences
- What changes: the PRICE of a fast buy only. v37's fast buy (acceleration,
  furious new high) and v36b's furious buy send one limit order AT THE ASK the
  bot reads just before sending - no cents over it (today: +20c, +30c from $10).
- Unchanged: when it buys (every signal and check), how much, the order working
  0.5s (V37_SWEEP_WAIT), the unfilled part cancelled (confirmed), the next
  furious print trying again (keep trying, V37_RETRY_GAP) - each try at the ask
  of that moment, never at or under the old high, never past the safety net;
  the stop (from the fill), the exits, the sessions.
- v36 keeps paying up as now: the control, as the owner decided ("keep v36").

## The checklist, answered
- Old print / off the bid-ask / no quote: unchanged (V37_PRINT_CHECK; r34.29:
  no fast buy unless up over 5 s and the ask within 10c of the bid; no quote,
  no fast buy).
- The decision print far from the fill: the limit IS the ask - the fill is at
  or under the ask read just before sending.
- Fills partly: the shares filled are the position (as now); the rest is tried
  on the next furious print at the new ask. Replay: 89-99% of the shares still
  bought.
- Does not fill: no position; the next furious print tries (as now). A runner
  can leave without us - the cost of not chasing.
- Paper vs real money: paper fills a limit at the ask easily (it fills against
  the quote); with real money only the shares offered at the ask fill at once.
  Paper will look kinder than real money.
- $1 vs $20 stock: no cents over at any price - the same everywhere.
- Wide spreads: unchanged (no fast buy over a 10c spread).
- Orders a minute: one order a try as now; misses mean more tries - the order
  budget (35 a minute) caps it.
- The replay cannot see seconds: tested second by second (SEC_DUMP, every
  print and quote), kind (first in line at the ask).

## Rules it touches
- The owner's 10-07 "keep trying" sweep at the ask + 20c (V37_SWEEP_CENTS):
  the sweep stays, the cents become 0 for v37 and v36b.
- The owner's 10-08 decision "the buy stays as is (pays up on flying
  stocks)": reversed for v37 and v36b only, by the owner's ask (10-08 ~9:35pm:
  "the entry for v37 ... I would have to change immediately").
- Nothing else: entries, sizes, stops and exits are untouched.

## The numbers (10-06/07/08, trades with no adds; the bot decided 0.3s / 0.6s / 1s before the live fill)
- v37 (114 trades, exit = the 5c cut, live since 6:02pm 10-08): as paid
  -$1,349; at the ask -$848 / -$737 / -$525 (1 s working). By day as paid
  -$674 / -$504 / -$170 -> at the ask 10-06 -$463..-$291, 10-07 -$403..-$431,
  10-08 +$18..+$197 (better every day).
- v36b (22 furious buys, v36's real exit): -$586 -> -$424 / -$420 / -$371.
- v36 (18 furious buys, not proposed): -$1,605 -> -$1,253 / -$1,537 / -$963.
- It lowers costs; it does not make the strategies profitable by itself.
