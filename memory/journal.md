# Journal

Decisions, instructions and results worth keeping. Newest first. Dates are ET.
Each entry: what was decided or found, the numbers, why, and where it lives.

## 2026-10-05

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
