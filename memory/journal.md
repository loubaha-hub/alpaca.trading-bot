# Journal

Decisions, instructions and results worth keeping. Newest first. Dates are ET.
Each entry: what was decided or found, the numbers, why, and where it lives.

## 2026-10-05

### Day review (8:15pm): the bot's own problems, not the market's
- Real results from the bot's equity lines (start v31 $19,124 / v34 $15,533 /
  v35 $7,158): v31 -$721 (-3.8%), v34 -$235 (-1.5%), v35 -$97 (-1.4%).
  Premarket v31 -$294, v34 -$123, v35 -$50; regular hours v31 -$383, v34 -$99,
  v35 -$47; after 4pm v31 -$44, v34 -$13. All flat by 8:17pm.
- 43 trades, 3 winners (v31 STNE +$122, SPCH +$50; v34 NVAX +$2). No earned
  buys and no spread refusals all day - no data yet for a spread allowance.
- OVERBUYING (fixed on the branch, commit 3400466, not live): NU was sized at
  300 shares (25% cap) and ended at 434 (35%). A cancelled order kept filling
  and the bot sent the size again. Same shape as AMOD 49% / QTEX 35% on 10-02.
  The self-check saw it (CRITICAL every 5s) but does nothing about it.
- FALLING BEHIND AT THE OPEN (not fixed): 9:33-9:35am the tick queue hit its
  20,000 limit and threw away 41,007 prints (v31) / 43,583 (v34). v31's
  9:35-9:48 buys (NU, WDCX, PAGS, ONDG, ITUB) came out of that backlog - all
  lost. Suspected cause: per-name data-API fetches in the chase/volume checks
  stalling the tick worker. Not yet measured.
- Restarts during trading hours: 46 bot starts on 09-30, 5 between 7:13 and
  8:00am on 10-02, 3 today. Each wipes the day's memory; old and new copies
  run side by side for about a minute.
- Old logs: v33 on 10-01 made 2,575 sales, median hold 12 seconds.
- Not done from the 8:15pm routine: the premarket rule study on the 1-minute
  replay - superseded by the afternoon's conclusion (stop patching; the
  replay is too kind). Waiting on the owner's walkthrough of how they trade.

### The owner trades this by hand at $5-10k a month
- With 1-3 red days a month. The bots, with "the same variables", have not
  had a green day. The owner will walk through how they trade, variable by
  variable, with real trades. Proposed: stop patching; compare the owner's
  real trades (Webull order history, read-only) with the bot's; rebuild
  simple from the owner's process.

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
