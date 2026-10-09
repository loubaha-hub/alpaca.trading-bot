# Where things stand

Updated 2026-10-09, ~12pm ET.

## 10-09 morning
- Working branch: `claude/three-strategies-x69ppg` (from
  `claude/happy-ride-o56nlz`, same history). Nothing goes to `main`
  without the owner's OK; a push to `main` restarts the bot.
- The owner, ~4:30am: "all three strategies up and running". Checked in
  Render's log: r34.38 (main d439a58) unchanged since 10:41pm, no restart;
  v36 / v37 / v36b all agree with the broker, 0 positions; no warning or
  error since 4am; 63 names watched by 4:30. Start equity: v36 $16,679
  (halt $15,013), v37 $13,503 (halt $12,154), v36b $6,027 (halt $5,425).
- First signal: SDEV 4:02:31 FURIOUS for v36 / v36b (speed 0.42, +6% in
  5s) - no order: the $2.29 print (Form T) stood 12c over the $2.17 ask,
  "TRIGGER NOT CONFIRMED". The price check worked as meant. No fills to
  4:30am.
- To 7:40am (premarket, 6 trades, all furious): v36 -$6 (3 trades, 1 won),
  v37 -$101 (1, 0 won), v36b +$59 (2, 1 won); all -$48. Equity 7:38am:
  v36 $16,673 (-0.1%), v37 $13,402 (-0.8%), v36b $6,086 (+1.0%).
  - MI 4:32:38 (furious, speed 1.22): v36 2,383 @ $1.38 -> $1.4596 trail,
    +$190, 19s; v36b 925 @ $1.38 -> $1.4594, +$73, 18s; v37 2,019 @ $1.45
    (its first try at the $1.44 ask got 0) -> out 2s later at $1.40 on its
    5c cut, -$101 - MI reached $1.54 about 10s later.
  - MI 4:33:43 (furious again at $1.59): v36 paid up (limit ask + 20c =
    $1.83), got 872 of 2,600 @ $1.68 avg with the market already $1.54 x
    $1.55 - out at $1.5006 in 3s, -$156. v36b's order at the ask ($1.63)
    got nothing - no loss. Pay-up vs at-the-ask, case 1.
  - VEEA 7:00:12 (furious at $5.53, stop the $5.50 line - 1c): v36 629 @
    $5.5473 -> $5.4847, -$39; v36b 238 @ $5.55 -> $5.49, -$14; 13-20s.
  - Furious first buys filled 78-85% of the shares wanted (20-22% of the
    account, not 25%); no add reached. A 1-share VEEA remnant logged
    CRITICAL "STILL HOLDING", sold a second later at $5.40 (-$0.15).
  - The owner (~7:50am): the bots took the two stocks that really moved.
    Checked: both were the #1 name by money when bought - MI crowd #1
    $758k / gainer #1 (4:33), VEEA crowd #1 $1.55M / gainer #2 (6:59).
  - VEEA ran after our stop: out at $5.49 (7:00:26; it dipped to $5.40 x
    $5.42 at 7:00:34), then $5.65 7:04, $5.88 7:10, $6.04 7:26, high about
    $6.13 ~7:31, $5.63 at 7:48. Nobody got back in: v36/v36b "NO SPEED for
    a re-entry" (0.00-0.06 under 0.10) at $5.65-$5.95, then "at the $6.00
    level - wait till it holds 5c past"; v37 SKIP score 9/15 at $5.79, "not
    two green" at $5.95. A 10c stop would also have gone ($5.45); only ~3%
    (v36b's regular stop, $5.38) held the 15c dip. Same pattern as 10-08:
    runners dip 15-20c+ first. One case - for the scorecard, not a change.
  - XRTX 7:47:10 (furious, speed 0.34; crowd #3 $975k, gainer #4 - not a
    top-2 name, furious sets the crowd aside): v36 1,250 @ $2.13 -> $2.1066
    on the 10s leash, -$29, 63s; v36b 119 of 699 wanted @ $2.13 -> $2.1076,
    -$3. Peak $2.20.
  - SAIQ 7:46:10 (a regular buy, "setup trigger 6.75", 5% of the account;
    SAIQ crowd #1 $4.4M): v36 121 @ $6.76 -> $6.66 stop, -$12.10, 45s; v36b
    44 @ $6.76 -> $6.6584, -$4.47. Afterwards "NO SPEED for a re-entry".
  - To 8:15am: v36 -$47.64 (5 trades, 1 won), v37 -$100.95 (1, 0),
    v36b +$52.01 (4, 1); all -$96.58. The owner pasted Alpaca's Activities
    for T6HH and AUES (Central time): every fill matches the bot's EXIT /
    TRIM lines to the cent (v36's VEEA: 459 @ $5.55 + 170 @ $5.54, sold in 9
    pieces $5.49 -> $5.40).
- VEEA blow by blow from the log: memory/review_1009.md. The owner
  (~8am): "it may have acted as designed" - the log agrees; each later point
  to get back in was followed by a 10c+ pullback; the money was in holding
  the first buy through a 15c dip. Open question for the owner: the $5.50
  line stop (6c) was tighter than the furious 10c leash.
- The owner (~8:50am): the line stop and v37's $250k money bar stay (journal).
  Distilled proposals to discuss: memory/proposals_1009.md.
- The owner (~9:25am): the bots respect the rules set for them; not perfect -
  a person overrules his own rules in some situations, the bot cannot; there
  are moves he would have taken that the stacked rules refuse.
- VIVK 9:07-9:14 ($4.46 -> ~$6.74 on deal news): v36 -$169.58 (5 trades),
  v36b -$74.98 (3), v37 +$11.91 (3); blow by blow in memory/review_1009.md.
  Day at 9:16: v36 -1.3%, v37 -0.7%, v36b -0.4%.
- Regular hours to 11:55am (8 trades): VEEA 10:17 (v36 starter + 2 adds ->
  608 @ $6.58 avg, out at the floor, +$1.60; v36b -$9.80; v37 -$9.73);
  PCSA 10:26 (v36 -$60.42, v36b -$15.96, the 10s leash); VEEA 11:40 (v36
  -$26.03, v36b -$4.56). VIVK 9:28-9:29: v36 -$23.20, v36b -$1.68.
  Equity 11:54: v36 $16,353.54 (-2.0%), v37 $13,404.59 (-0.7%), v36b
  $5,972.14 (-0.9%).
- By session, 4 days (10-06..10-09): v36 premarket about +$127 (~59
  trades, ~+$2 a trade), regular hours about -$1,738 (~39, ~-$45 a trade),
  after hours -$433 (11, 0 won); v36b premarket about -$263, regular about
  -$579, after hours -$246 (8, 0 won); v37 premarket about -$1,456 (10-06's
  99 trades before the fixes), regular about -$423, after hours -$11.
- The owner (~11:50am): premarket is more profitable for this niche - the
  news and the runners come there; the challenge is the volatility: tight
  entries and stops throw us out before the run; a human changes the plan
  after the entry by reading other factors, the bot cannot. Asked for my
  ideas along those lines, some maybe for today. Friday; one positive day
  on one strategy this week - "dismal ... however, it's a progress".
- The owner (~9:30am): after a month, no profit - do public, recognized
  strategies do better? Researched (4 parts, notes in research_notes/Small cap
  momentum strategy evidence/). Answer: no proven, cost-surviving strategy on
  our kind of stock; one candidate to test (opening range breakout on stocks
  in play, after 9:30, $5+, top relative volume); the research confirms our
  three leaks (burst-top buys, paying over the ask, the 1-minute replay).
  The map, research vs our live numbers: https://claude.ai/artifact/PT9fPxUXei5HVJsBRoKGDG
  The full report: reports/Small cap momentum strategy evidence.md.
- Tonight, agreed: the count of which check said no on the #1/#2 leaders
  today, and what each stock did in the next 15 minutes (from the log). Plus,
  from now on, every move the owner says he would have taken (his charts) is
  kept in memory/would_take.md with the check that blocked it - after 1-2
  weeks, the rule that blocks the most good moves is the one to look at.
- r34.40 on the branch (678 tests pass; r34.39 + the top runners): the
  read-only second-by-second read of every 10-09 buy of the three (10 min
  before to 50 after), the named moments (NTCL 10-09 8:30, BIYA 10-07 8:20,
  DKI 10-08 6:54, FLYE 10-08 7:17), and NEW: each day's top runners 10-06..
  10-09, found by the bot itself from hourly then 1-minute bars (x1.8+ within
  150 min, $5M+, $1-$20; six a day, 10 min before the low to 30 after the
  high; SECDUMP RUNNER lines list every runner found). About 2 hours of
  reading. WAITING ON THE OWNER'S OK to push to main after 8pm with all three
  flat; the next release turns SEC_DUMP off.
- After the read: save the SECDUMP lines (replay/live/2026-10-09_secdump),
  secread.py, then speedsim_study.py / speedsim_stops.py on all windows -
  every table split PRE / RTH / AFTER (the owner's standing rule, 10-09).
- Found so far (journal 10-09): on the slices of big runs already read, the
  speed strategy keeps only SXTC; 74% of its trades are out within 5s.

## 10-08 night
- Live: **r34.38** (main d439a58, up 10:41:40pm 10-08, all three 0 positions): r34.37 with the owner's corrected
  sizes - v36/v36b furious 25% of the account first, to 50% on the add (+20c,
  a new high); v37 fast under furious speed 20% of the account, to 40% at +20c;
  v37 furious 32.5% then 65%; regular buys 20% of a full position (v36/v36b
  5% of the account, v37 8%).
- r34.37 (main 1caa5a5, up 10:24:46pm 10-08, all three 0 positions;
  the owner: "tested ... then deploy") = r34.36 + the sizes: a
  regular first buy 20% of a full position (was 10%), then 50%, then all;
  a furious buy 50% first (v36/v36b 12.5% of the account, the rest at +20c on
  a new high; v37 32.5%, the rest to 65% on its furious add); v37's fast buys
  under furious speed 8% (20% of its full 40%). NEWS_DUMP_DAYS = () (read once
  by r34.36, 10:16-10:23pm: 425 of 425 stock-days, and the accounts' fills
  10-01..10-08 - v36 989, v37 14,153, v36b 5,767 - in Render's log).
- r34.36 (main 6219582, pushed ~10:15pm 10-08, all three flat; the
  owner: "implement all of this and make the strategies ready to deploy
  tomorrow at 4am"). Trades from 4am 10-09:
  - v37 and v36b buy AT THE ASK (BUY_AT_ASK); v36 pays up as before.
  - furious buys of v36b and v37: the 10c leash (FURIOUS_TEN_CENTS); v36b
    keeps 3% on regular buys; v37's regular stop 3% (V37_STOP_MAX); v37's 5c
    cut still sells first on all its buys.
  - v37's regular buys need two green candles unless furious (V37_TWO_GREEN).
  - from +$1 a share over the average, out on 30% back (BIG_GAIN_*), all three.
  - the news and borrow log (NEWS / BORROW / CONTEXT lines), information only;
    NEWSDUMP once tonight (fills 10-01..10-08 + headlines of every stock bought).
  - SEC_DUMP_DAYS = () and NO_BUYS_FROM = (): no read, no buy stop.
  Before it: r34.35 (6:02pm) v37's 5c cut; r34.29-31 the fast-buy checks, no
  per-stock buy limit, v37's 20c re-buy.
- Pre-flight for 10-09 (~10:50pm 10-08): r34.38 live, deploy "live", no errors
  since the restart, 0 positions on all three; buying 4:00-19:00 ET (paused
  9:29-9:31), no date blocks (NO_BUYS_FROM, SEC_DUMP_DAYS, NEWS_DUMP_DAYS all
  empty); the day rolls at midnight ET (10-08's roll logged "new day", halt at
  -10%); no order refused on 10-08. Two 10-08 "no real stop" CRITICALs (v36
  SAIQ 3:34pm, XRTX 4:08pm) were the self-check running 70 ms before the
  fill's stop was set - not a real gap. Sizes in dollars: v36 regular $834 ->
  $4,170, furious $4,170 -> $8,340; v36b $301 -> $1,507, furious $1,507 ->
  $3,014; v37 regular $1,080, fast $2,701 -> $5,402, furious $4,389 -> $8,778.
- To watch 10-09: v36 (pays up, 10c) vs v36b (at the ask, 3% / 10c furious);
  v37's trade count with two green candles; fills vs the ask; NEWS lines.
- Save the NEWSDUMP and the 10-01..10-05 history lines from Render (7-day
  retention) for the "first trades" and "premarket" checks.
- Judge rules per entry, added up over days (the owner, 10-08).

## Clean for 10-09 (the owner, ~9:35pm: "what are the clean ones?")
- v37's 1c exit: gone - the 5c cut is live since 6:02pm (r34.35).
- DECIDED and built (r34.36, BUY_AT_ASK): v37 and v36b buy AT THE ASK (no
  20c / 10c / 0.2% over); v36 unchanged (the control). Words:
  memory/words_buy_at_ask.md.
- DECIDED and built: furious buys of v36b and v37 get v36's 10c leash
  (FURIOUS_TEN_CENTS); v37's regular stop 3% (V37_STOP_MAX 0.03); v36b keeps
  3% on regular buys; v37 keeps its 5c cut on all buys. Also: from +$1 a share, out on 30% back (BIG_GAIN_AT / BIG_GAIN_BACK, all
  three); v37's regular buys need two green candles unless furious
  (V37_TWO_GREEN). 665 tests pass.

## The list (the owner, ~9:30pm 10-08: "what do we finally agree on?")
Everything from ~3:30pm to 9:30pm 10-08, sorted. Details in the journal.

Decided - stays as it is:
- the scanner's 10% (from yesterday's close before 9:30, today's open
  after); the 2-minute crowd wait (a furious move overrides it);
- v36's entry and exit: 10c stop, from +30c out on 30% back;
- no 9:30 cut-off on 10-09; no limit on buys of a stock a day (r34.30).

Going out tonight (r34.36, information only - nothing trades differently):
- hard-to-borrow / shortable for every name on the list, and at each buy;
- news headlines for the names on the list, logged as they come, with
  flags (offering, reverse split, ...), and at each buy; a one-time read of
  the headlines for the stocks traded 10-01..10-08. The owner: "just let
  them go into the log" - good-looking news often fizzles.

Tested on the three days and NOT adding an edge - not building:
- the owner's ladder on top of the 5c cut (5c, then the buy price to +20c,
  half 20-50c, a third 50c-$1, a fifth $1+) - 174 of 223 trades never got
  5c over the buy; it never beat the plain cut;
- v36's half / third / fifth above +30c instead of 30% back - about even;
- buying back over the day's high + 5c, or on reclaiming the buy price -
  both add losses (the re-buys land on the tops of one-second bursts);
- a wider first leash (10c, 15c) - worse than 5c for all three;
- buy only on an uptick; buy only on a green tape; wait for the whole /
  half dollar + 5c; out when it hesitates at a line - none held up;
- EMA 9 over 20, MACD over 0, over VWAP - nearly every buy had them, so
  they cannot pick the good ones; a volume spike at the buy was worse.

Showed an edge on the three days - candidates, each needs the owner's word
(and a check on more days; 3 days is a small sample):
1. Premarket (4:00-9:30): v36 +$367 there vs -$1,653 regular hours and
   -$433 after hours. The owner: not from 10-09; the guru stops at 9:30.
2. Few trades a day: v36's first trade of each day +$268 vs all -$1,718;
   stop after the first loss +$138. Touches nothing per stock (r34.30 is a
   per-stock limit); a per-day limit is new.
3. Stop paying up: the spread + paying over the ask seen = ~70-80% of
   v36/v36b's losses, more than v37's whole loss. Touches the owner's
   10-08 decision "the buy stays as is (pays up on flying stocks)".
4. No buy 20%+ over VWAP: 1 of 28 won vs 29% - mostly regular hours, so it
   overlaps with 1.
5. v36b (the loser): a quick 4c cut, trades with no adds -$964 -> -$248
   (59 trades). Holds no runners - but no rule held runners.
6. v36b's furious buys with the 10c stop instead of the 3% cap (the owner:
   "sensible"). The data: a wash on what we have; the 10-08 FLYE / DKI
   cases where 10c won are in the missing data.
7. The three-candle setup on the day's #1 leader, its first pullbacks
   (LPCN 10-07 4 of 4 to +2R) - not tested on its own yet.
8. Shrinking green bodies before the buy: 14% won vs 22% - weak.
1-4 point the same way: the morning's leaders, few trades, no chasing.

Untested proposals from WORX (after hours 4:51pm):
- a furious re-entry at the day's high without a new burst of speed;
- a stop on a wide quote decided by a real print, not the middle.

Housekeeping: v37 logs why it skips a buy (WHY-NOT); a map of which rules
apply in which situation (furious, back on after a stop, the leader's new
high, the regular setups); the 10-08 data that could not be saved (DKI x3,
CRE, FLYE's start). Older open items (10-08 morning): the stop from the
fill not the decision print; protect a furious gain before +30c; v37's
gain from the bid; premarket sells left working; the recorder; adds on big
runs.

## Earlier (10-07 night)


## Code
- Working branch: `claude/zealous-ramanujan-br3gay`. New work goes here;
  nothing goes to `main` without the owner's OK.
- **The day, final (7pm summary):**
  - v36 -$1,722 (-9.45%, $16,491), $99 above its halt;
  - v36b -$602 (-8.62%, $6,385), $96 above its halt;
  - v37 -$293 (-2.01%, $14,249).

  The 4:10pm figures were not final. After hours, 4:22-5:00pm, v36/v36b made
  8 furious full-size buys and lost them all (-$289 / -$204). r34.28's block
  is 9:30-4 only.
- **Tonight, done:**
  - the 10-07 bars (replay/data/2026-10-07, 132 names, aa15f03);
  - the logs (replay/live/2026-10-07_roster / _trades / _whynot, f8e23bf);
  - the review in words, memory/review_1007.md: the live rules, the
    checklist answered (H1-H29), contradictions (C1-C8), every loss tagged,
    the v37 SXTC bite, sale timing, the replay of 10-07, the scorecard
    proposal. The page: https://claude.ai/artifact/8YT1dAn77Nt346gUUUDgT7
- **WAITING ON THE OWNER BEFORE 4AM 10-08:** V36_NO_RTH_BUYS_ON covers 10-07
  only. From 9:30 on 10-08, v36/v36b furious full-size buys come back, and
  after hours was never blocked. Options in the review, section 10:
  - (a) v36/v36b premarket only, every day (recommended);
  - (b) a starter + adds outside premarket;
  - (c) as is.

  Any choice needs a release while flat after 8pm.
- **Other open decisions:**
  - releases after 8pm only, plus D (no buys 60s after a start);
  - furious size from a dollar risk, with the stop sized to the stock's
    swing;
  - C (buy-back waits);
  - S1-S4 (faster sales);
  - cents to percent on cheap stocks;
  - the scorecard;
  - a halt rule.
- Live on `main` (Render): VERSION v31-r34.28 (pushed 3:32:22pm ET 10-07 on
  the owner's "stop v36/v36b buys until 4pm"; flat since 2:55): no new
  v36/v36b buys 9:30-4 on 2026-10-07 only (V36_NO_RTH_BUYS_ON); v37,
  premarket and after hours unchanged. The day: v36 -7.9% ($16,780), v36b
  -5.7% ($6,588), v37 -2.0% ($14,247). By session: premarket v36 -$280,
  v36b -$156, v37 +$64; 9:30-4 v36 -$1,153, v36b -$243, v37 -$358. The
  furious full-size buys after 1:35 cost v36 -$932 in 6 trades; the deploy
  overlaps ~-$508. The 7-day replay's gains are premarket too (r34.23, fills
  0.2% / 1%: v36 premarket +$11,183 / +$9,190, 9:30-4 +$1,072 / -$121).
  Proposed to the owner (not chosen yet): furious full size premarket only,
  9:30-4 back to a starter + adds until a regular-hours design is built and
  tested; releases after 8pm only + 60s no-buy start. To analyze tonight.
- r34.27 (2:18pm) (pushed 2:17:50pm ET 10-07 on
  the owner's "Push r34.27 now"; all three flat at the broker): a sale that
  finds the broker holding none closes the position here, nothing booked.
  CPHI 2:11-2:17pm: during the r34.26 deploy the OLD process bought CPHI
  furiously (v36 3,552 @ $1.0654, v36b 1,487 @ $1.06; both sold, -$259 /
  -$70); the new process had adopted v36's CPHI 2s before the old one sold
  it, then tried to sell 0 shares on every print - v36's tick queue filled
  (19,999) and dropped ticks until r34.27. DEPLOY OVERLAP IS REAL: the old
  process keeps trading ~20-45s after the new one starts (1:56, 2:07, 2:11).
  Option D (no buys for 60s after a start) not chosen yet - raise again.
- r34.26 (2:12pm) (pushed 2:11:19pm ET 10-07 on
  the owner's choice "A"; flat at 2:10:28): v36/v36b furious buys use v37's
  fast buy (V36_FURIOUS_SWEEP, entry_buy) - one order at the ask + 20c (30c
  from $10), filled or dropped in 0.5s, the next furious print tries again
  0.5s after a miss. Worktree release22. The owner did NOT choose (open):
  B the furious stop as the larger of 10c and 2%; C a buy-back after a
  furious stop waits for the new high to hold 2s, at most 2 per stock per
  10 min; D no buys for 60s after a deploy (the old instance keeps trading
  ~20-40s after the new one starts - it did, 1:56pm).
- r34.25 (2:07pm, pushed 2:06:40 on the owner's "sell at market 9:30-4, as
  fast as possible"): the first sell goes straight out when nothing of ours
  was working; each sell logs "SELL n at MARKET" or "at a limit". Sells
  9:30-4 have been market orders since r34.17; premarket stays limits.
- SXTC 1:40-1:59pm, furious full positions: 8 trades, -$959 (v36 3 more after
  r34.24, -$377): fills above the print from v36's 6-second loop, the 10c stop
  inside SXTC's 20-50c swings, buy-backs 4s apart. Day at 2:10pm: v36 -5.9%
  ($747 above its halt), v37 -2.0%, v36b -4.3%.
- r34.24 (1:56pm) (pushed 1:55:20pm ET 10-07 on
  the owner's "Push r34.24 when flat"; flat at 1:54:45): exits, from SXTC
  1:40pm (v37 bought 625 @ $7.75, the top tick of a $7.15 -> $7.74 -> $7.17
  wick; stop $7.65 decided on a $7.49 print 6s later; the sale took 7.5s
  and three market orders, out at $7.29, -$290). A market sell is left to
  fill - Broker.follow(market=True) no longer cancels it after a partial
  fill and sends it again (send_market waits up to 6s); BID_STOP - the stop
  also fires when the middle of the live bid and ask is at or under it; a
  furious v36 buy's gain counts from the fill (v36b sold on a 37c "gain"
  measured from a stale $7.72 print). Worktree release20.
- r34.23 (1:36pm) (pushed 1:34:55pm ET 10-07 on
  the owner's "Push r34.23 when flat", after the owner saw the replay table;
  flat at 1:34:32): the owner's furious exit (~1pm, decisions) - a furious
  buy's stop 10c under what it paid, not 8% (V36_FURIOUS_STOP_CENTS; 8%
  stays the outer limit under $1.25); back in at once on a new high of the
  day while still furious (furious_new_high: one buy a minute and v37's
  60-second re-buy wait lifted for that); once up 30c, never back under the
  buy, and out on giving back 30% of the gain from the high
  (V36_FURIOUS_EVEN_AT, V36_FURIOUS_GIVEBACK; v36/v36b and v37's furious
  buys, V37_FURIOUS_EXIT); the 10-second leash kept. The whole / half dollar
  stop 1c under the level (V36_LEVEL_GIVE; the owner: "5.98 or 5.99"; 7 days
  replayed, 1c beat 2c and 5c for all three). Worktree release19.
  Replay, 7 days, $15k, fills 0.2% / 1% worse (r34.22 -> r34.23):
  v36 +$8,583 -> +$12,487 / +$5,410 -> +$9,016; v36b +$10,466 -> +$13,377 /
  +$7,244 -> +$9,826; v37 +$31,263 -> +$34,693 / +$19,122 -> +$20,019. MI
  10-05 is the biggest trade in every one. scratchpad sidebyside.py builds
  the table (names d0base_*, d1new_*, h1r23_*, c9split).
- To look at: v37's keep-trying buy at 12:25 (FFR) sent one order 20c over
  the $1.93 ask and nothing filled in its 0.5s (paper fills seem slower);
  proposed to the owner: 1 second a try on paper (V37_SWEEP_WAIT).
- r34.22 (12:36pm) (pushed 12:35:41pm ET 10-07 on
  the owner's "push them in right away, as soon as they are flat"; flat at
  12:34:45): the owner's stop and furious rules (12:20pm, decisions):
  "B" - a v36/v36b starter is sized so its first stop costs at most 3% of a
  normal starter (V36_STARTER_RISK; DKI 11:37's 16.6% stop lost $71); the
  stop sits 5c under the whole / half dollar under the buy and moves up to
  each level the price clears by 5c and holds 3s (V36_LEVEL_STOP,
  V36_LEVEL_GIVE; v36, v36b and v37); furious (speeding): the FULL position
  on the first hit (V36_FURIOUS_FULL), every entry check set aside -
  levels, wick, re-entry speed, score, 5% over the trigger, no candle
  pattern needed (V36_FURIOUS_ALL) - the stop within 8%
  (V36_FURIOUS_STOP_MAX), the 10-second leash at once, out on giving back a
  third once up 30% (V36_FURIOUS_SPIKE), deep premarket exits; the scanner's
  list in the log (ROSTER lines, all of it every 15 min) for the replay.
  Worktree release18. The 7-day replay of all three is running (fix1007
  jobs10.txt, names d0base_* / d1new_* / d2nolevel_v37).
- r34.21 (12:05pm) (pushed 12:04:59pm ET 10-07,
  the owner's "Push r34.21 when flat"; flat at 12:03:51; engine up 12:05:45):
  v37 keeps trying on FURIOUS movers only (keeps_trying = V37_KEEP_TRYING and
  speeding): one order a try at the ask + 20c (30c from $10), no price cap and
  no time limit, every print over the old high tries again, paced 0.5s a
  symbol (V37_RETRY_GAP) and 35 orders a minute an account (ORDER_BUDGET).
  Every other fast buy keeps the 20% safety net and the 6-second, 12-try loop
  (the owner: "only for furious movers... the rest keep it, a nice safety
  net"). The 7-day replay is unchanged by this (+$28,133 / +$16,539): 1-minute
  bars cannot show a 5-second chase - only live trading will. Worktree
  release17.
- r34.20 (11:58am) (pushed 11:57:59am ET 10-07, the owner's "Push r34.20 when flat"):
  the big moves - v37 fast buys from the
  breakout level (V37_ACCEL_FROM_HIGH) at the ask + 20c (30c from $10), retried
  for 6s within a 20% net (V37_SWEEP*), sized on the likely fill; a fast buy's
  premarket exit is a limit 10% under the bid (SELL_DEEP); trend checks with
  the live price (V36_TREND_LIVE); speed (V37_FURIOUS_SPEED on $250k) counts as
  the crowd, lifts the 6-buy cap and sets trend/tape/room aside for v36/v36b
  (V36_FURIOUS, V36_FURIOUS_SKIPS); the crowd counts trading minutes 9:30-4 only
  (V36_CROWD_TRADING; the owner: no halts premarket); a 5-second move logged;
  the r34.18 bug fixed (V37_HOD_CLEAR measured from the closed-candle high -
  v37 could not buy since 10:29); an add needs a NEW high that holds 2s (r34.19
  added on the way down, DKI 11:36); a sizing crash fixed. Worktree release16.
- r34.19 (10:56am): (pushed 10:55:42am ET 10-07 on
  the owner's standing instruction - agreed fixes go in at the next flat
  moment): an add waits for the price to hold at or over its level 2s
  (V36_ADD_HOLD_SEC); the floor still moves to the new average after an add
  and the sizes are unchanged (the owner's decisions). Worktree release14.
- r34.18 (10:29am): (pushed 10:28:34am ET 10-07,
  the owner's choice "Push r34.18 when flat", flat from 10:25:42): v37 needs
  the price over the old high by 2c or 0.5% (V37_HOD_CLEAR); a buy never
  reloads once the ask falls back to the old high (buy(floor=)); a fast buy
  needs the owner's speed >= ACCEL_SPEED and the 60/40 tape (WETO 9:52).
  Release worktree: scratchpad release13.
- Proposed to the owner (10:30, not decided): one gate of never-rules every
  buy passes whatever its route; a rule checklist logged with every buy
  and an automatic hourly/nightly audit; record prints and quotes so the
  replay sees seconds; fewer, slower releases; simplify to one entry
  pattern and one exit.
- r34.17 (10:16am): (pushed 10:15:54am ET 10-07
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
