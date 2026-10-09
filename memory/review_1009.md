# 10-09 blow by blow - VEEA, MI (from the bot's own log and the owner's charts)

The owner, 10-09 ~8am: "why did we miss it? ... it may have acted as designed ...
get the exact entry by seconds for every one ... what the bot did and what it
should have done instead."

Source: Render log lines (WHY-NOT, FURIOUS, FAST BUY, BUY SHORT, ENTER, SELL,
EXIT, SKIP). Prices between decisions are the bot's once-a-minute WHY-NOT
snapshots, NOT the full tape. The exact second-by-second tape comes from the
read-only read (r34.39, SEC_DUMP_DAYS = 10-09) after 8pm; the "what if" lines
below are to be redone on it.

## The run-up (v36 / v36b - same lines for both)
| ET | VEEA | crowd (money, 5 min) | gainer | why no buy |
|---|---|---|---|---|
| 6:40-6:46 | $5.07-5.17 | #3, $150-350k | #2 | no crowd: not top 2 for 2 min |
| 6:47:43 | $5.20 | #2, $353k, held 0.7m | #2 | no crowd yet (2-min hold) |
| 6:49:46 | $5.22 | #2, $611k, held 2.8m | #2 | crowd OK; no pattern (no rip) |
| 6:50-6:55 | $5.16-5.29 | #1-#2, $400-640k | #2 | no pattern; red candles, volume 0.4-1.9x |
| 6:56:56 | $5.35 | #1, $763k | #2 | no pattern (GG, 3.3x - not over the day's high) |
| 6:59:56 | $5.44 | #1, $1.55M | #2 | no pattern (last candle red) |

## The buy and the stop
| ET | what |
|---|---|
| 7:00:12.596 | FURIOUS at $5.5326 (speed 0.35; the last 5s +0.6% on $134k); bid $5.51 ask $5.55; both v36 and v36b |
| 7:00:13.836 | v36b: 238 of 270 wanted @ $5.55 (at the ask) - 22% of the account |
| 7:00:14.601 | v36: 629 of 740 wanted @ $5.5473 avg (limit ask + 20c = $5.75) - 21% |
| | stop for both $5.49 = the $5.50 line - 1c (tighter than the 10c leash, $5.45); add planned at ~$5.75 on a new high |
| 7:00:14-24 | best fresh print $5.56 |
| 7:00:24.669 | the bid at $5.49 = the stop: sell (premarket: limit 10% under the bid) |
| 7:00:26.601 | v36b out 238 @ $5.49: -$14.28, held 13s |
| 7:00:24-34 | v36 out in 8 pieces as the bid fell $5.49 -> $5.45: 628 @ $5.4847 avg, -$39.33 |
| 7:00:34 | market $5.41 x $5.42 (the dip's low, ~15c under the buys) |
| 7:00:35 | v36's last share @ $5.40 (-$0.15; the "STILL HOLDING 1 share" CRITICAL) |

v37: no line at 7:00:12. Its quiet checks before a buy are: a fresh print over
the day's high by 2c or 0.5% (~2.8c here), confirmation, and for the furious
route the last 1-minute candle not red (the 6:58 candle was red). Which one
stopped it - from the tape tonight.

## After the stop - every chance to get back in
| ET | VEEA | v36 / v36b | v37 | what came next (minute snapshots) |
|---|---|---|---|---|
| 7:04:33-54 | $5.65-5.66 (day high + 5c) | NO SPEED for a re-entry: 0.04-0.06 under 0.10 | - | $5.57 at 7:08:54, $5.79 at 7:10 |
| 7:10:36-56 | $5.79-5.88 | NO SPEED: 0.00-0.06 | SKIP: score 9/15 (speed 0, lows 0) | $5.77 7:11, $5.69 7:13, $5.59 7:15 |
| 7:24:08 | $5.95 | NO SPEED: 0.00 | SKIP: last two candles not both green | $5.82 at 7:25 |
| 7:26:49-59 | $6.03-6.04 | at the $6.00 line - wait till it holds 5c past | - | high ~$6.11 7:27, ~$6.13 ~7:31; $5.98 7:30, $5.86 7:36 |
| 7:48 | $5.63 | | | crowd #2, faded |

## Reading it (to confirm on the tape)
- Each bot did what its rules say. Nothing ran against the code.
- Each later point to get back in ($5.65, $5.79, $5.95, $6.03) was followed by a
  pullback of 10c or more within minutes. On these snapshots a 10c stop would
  have caught 3 of the 4 (5.79, 5.95, 6.03) and $5.65 is unclear (the 7:05-7:09
  low is not in the log). The speed rule and the $6 line wait most likely saved
  losses - the owner's read.
- The money in VEEA was in the FIRST buy, held through a 15c dip: from $5.55
  to ~$6.13 (+58c). Only a stop 15c+ under the buy (about 3%, v36b's regular
  stop, $5.38) held; the 10c leash ($5.45) and the line stop ($5.49) did not.
- A question for the owner (rules meeting, not a change): the buy was 5c over
  the $5.50 line, so the line stop ($5.49) was tighter than the furious 10c
  leash - 6c of room. Which should win right after a furious buy just over a
  line? On 10-08's 40 furious buys the 3% stop was as good or better than 10c
  (v36 -$1,269 vs -$1,605; v36b -$586 vs -$606) - one more case for that table.
- v36 (pays up) vs v36b (at the ask): the same price here ($5.5473 vs $5.55);
  both filled 85-88% of the shares wanted.

## The owner's chart (Webull 1-minute, 6:55-8:09 ET; read by eye, +-2c)
- 7:00 candle: green ~$5.29 -> ~$5.46, top wick to ~$5.53-5.56 - our buys at
  $5.55 were at the top of that wick. 7:01: red to ~$5.37 (the stop-out).
- 7:02-7:06: five greens, ~$5.40 -> ~$5.63, over EMA9.
- 7:07-7:08: two reds, pullback to ~$5.55-5.58, over EMA20. 7:09-7:11:
  green again, ~$5.84-5.88 at 7:11.
- 7:13-7:17: pullback to ~$5.58-5.60 (EMA20). 7:18-7:29: climb to the $6.13
  high (~7:29). Then $5.70 by 7:41, $5.84 at 7:53, ~$5.52 at 8:04, $5.67 at 8:09.
- Two of the playbook's green-red-green pullbacks on the #1 leader: buy back
  over the red's open ~$5.67 at ~7:09-7:10 (stop under the red ~$5.55) and
  ~$5.77 at ~7:19-7:20 (stop ~$5.58). Both ran to $5.88 / $6.13.
- Why no bot took them: the furious buy at 7:00:12 was VEEA's first buy, and
  V36_SETUP_BUYS = 1 (the owner, 10-07, SPAI / LPCN: "a re-entry has to go
  past the high of the day") - after one buy, no candle setups; only the
  day's high + 5c, at speed 0.10 (V36_REENTRY_SPEED). The code's own comment
  quotes the owner (10-06): the setups are "for the first and second buys".
- Question for the owner (words, not code): should a furious buy stopped out
  within seconds use up the leader's setup buy? Touches V36_SETUP_BUYS and the
  10-07 SPAI decision (SPAI's 2nd buy was under the high, on a red candle, no
  speed). Ties to candidate 7 in now.md (the #1 leader's first pullbacks,
  LPCN 10-07 4 of 4 to +2R). Needs the tape and more days before any change.

# MI 10-09, blow by blow (log + the owner's Webull charts, 1m / 10m / 10s)
The chart: yesterday $0.80 low; today ~$1.00 at 4:30, a burst to the $1.75
high, then $1.40-1.65 chop to ~5:30 and a fade to $1.28 by 8:15.

| ET | MI | what the bots did, and why |
|---|---|---|
| 4:30:35 | $1.00 | back on the scanner's list (up 10%+) |
| 4:32:00 | $1.05 | v36/v36b: no crowd (#5, $98k) |
| 4:32:38.3 | $1.34 | FURIOUS (speed 1.22, +3.9% in 5s): $1.05 -> $1.34 in 38s |
| 4:32:39.4 | | v36: 2,383 of 3,050 @ $1.38 (limit ask + 20c, $1.59); v36b: 925 of 1,102 @ $1.38 at the ask. Stop $1.28 (10c) |
| 4:32:40.5 | $1.42 | v37 fast buy: 0 at the $1.44 ask; 4:32:42.1 again at $1.48 (ask $1.49) |
| 4:32:43.7 | | v37: 2,019 @ $1.45 avg - as the bid fell to $1.40 |
| 4:32:43.8-46.2 | $1.40 | v37's 5c cut (5c under its best, the fill) - out @ $1.40, -$101, held 2s |
| 4:32:55.5 | best $1.54 | v36/v36b out on the +10% trail (armed at +10%; 2% under the high = ~3c on $1.54); print $1.5032, filled $1.47 / $1.45 -> +$190 / +$73 |
| 4:33:00 | $1.395 | crowd #1 $758k, gainer #1; waiting for the high + 5c ($1.60) |
| 4:33:43.8 | $1.59 | FURIOUS again (a new high, speed 0.31): v36 paid up (limit $1.83), 872 of 2,600 @ $1.68 avg; v36b at the $1.63 ask: 0 |
| 4:33:45.7 | $1.54 x $1.55 | under v36's $1.58 stop: out $1.50-1.53, -$156, held 3s |
| 4:36:28-33 | $1.73-1.75 (the high) | v36/v36b: NO SPEED for a re-entry (0.07-0.08 under 0.10); v37: SKIP at $1.70, last two candles not both green |
| 4:37:33 | $1.50 | then $1.53-1.65 to 4:44, crowd #1 $2-3M |

## Reading it
- The rules worked as written. Blocks that saved money: the speed rule and
  v37's two-green rule at $1.70-1.75 (the high, then $1.50 a minute later);
  v36b's at-the-ask order on the 4:33:43 spike (v36 paid up and lost $156).
- Pay up vs at the ask, case 1: MI 4:33:43 (-$156 vs $0). VEEA 7:00: no
  difference (v36 $5.5473, v36b $5.55).
- Rules meeting (a question, no change): a furious buy is ALSO under the
  regular +10% trail. On a $1.38 stock +10% is 14c, so the trail (2% under
  the high, ~3c) armed long before the owner's furious exit (from +30c, out
  on 30% back). Furious rule alone here: the $1.68 spike reaches +30c, line
  $1.59, the crash to $1.54 -> out ~$1.55: about +17c vs +8c (v36 ~+$215,
  v36b ~+$83 more) - IF the fill came. Against it: the 10-08 three-day table,
  v36 trades with no adds (50): live -$1,550 vs "furious 30c/30% alone"
  -$3,095. One case against 50 - keep, count.
- v37 bought the top of a 1-second burst ($1.48 print, bid $1.40 a second
  later); the 5c cut sold it in 2s. v37 did not buy the 4:33:43 burst - no
  line in the log (a quiet check; the tape will tell).

## MI: why v37 did not buy right over the day's high (the owner's question, ~8:40am)
- The owner: v36/v36b not in the first minute is fine (the wick would have
  shaken them; after it, too volatile - "I won't trust that pattern");
  the one thing to examine: v37 did not buy right after the high of the day.
- MI's high before the burst: $1.13 (v36's furious "new-high trigger
  1.1300"). 4:32:00: $1.05, $98k traded in 5 min (#5 by money, #2 gainer).
  4:32:00-4:32:38: ~215,000 shares, $1.05 -> $1.34 (the tape at 4:32:39:
  215,463 shares in the last 60s).
- v37 has two doors, and both need $250,000 traded in the last 60 seconds:
  - the regular buy: the #1/#2 by money with $1M+ in 5 min, or the top
    gainer - MI was #5 and #2 - then "flying": up 3% in 60s on $250k
    (V37_FAST_DOLLARS);
  - the fast / furious buy: the owner's speed 0.30+ on $250k in the last
    minute (ACCEL_DOLLARS), the last candle not red.
  The speed was there early (1.22 at 4:32:38, far over 0.30); the money was
  not. It reached $250k at about 4:32:38 with MI at $1.34 - 21c (19%) over
  the $1.13 high. v36/v36b's furious door opened that same moment (4:32:38.3).
- v37 went 2.1s later (4:32:40.5, $1.42) - most likely its extra tape check
  (60% of shares at the ask; the tape read 61/39 at 4:32:39.5, right at the
  edge) - to confirm on the tape. Its first order at the $1.44 ask got 0;
  the second (ask $1.49) filled 2,019 @ $1.45 at 4:32:43.7 - the top of the
  burst; the bid $1.40; the 5c cut out in 2s.
- To test on the tape tonight (all days, not MI alone): when MI crossed
  $1.13 and its money crossed $100k / $150k / $250k in a minute; where v37
  would have bought with a lower money bar, and whether the wick shook it out
  (the owner expects so); the same for every furious buy of 10-06..10-09.

# NTCL 10-09 (the owner's chart, ~8:50am) - no bot traded it
Chart: prev close $1.795; ~$1.83 at 8:29, a jump to ~$2.17 in the 8:30
minute, a burst to the $2.65 high ~8:32:50, then $2.10-2.45 chop.

| ET | NTCL | the log |
|---|---|---|
| 8:30:23 | $2.17 | first on the scanner's list (10% over the close = $1.975), already 19% over its $1.829 high; watched from the next batch (~30s) |
| 8:32:00 | $2.08 | v36/v36b: no crowd (#3, $701k in 5 min; gainer #5) |
| ~8:32:50 | $2.65 high | no FURIOUS line from any bot at any time |
| 8:33:00 | $2.44 | "rip 08:32 alive", last candles red-green - waiting for the pullback pattern |
| 8:33:44 | | the news (benzinga, 8:33): AI pet launch through a 40% joint venture - after the move started |
| 8:34-8:36 | $2.25-2.31 | crowd #1 ($3-6M) from 8:34, held 2 min at 8:36; no pattern (green-red, the buy over the red's open never came) |
| 8:37-8:48 | $2.12-2.30 | no pattern; the rip "dead" 8:45, "alive" again 8:48 |

- The first leg ($1.83 -> $2.17) was over before NTCL reached the list: the
  scanner's 10% bar.
- The burst ($2.08 -> $2.65, 8:32) passed with no furious line. The furious
  door needs speed 0.30+, $250k in the last minute and the last 1-minute
  candle NOT red; the 8:31 candle was most likely red ($2.16 at 8:30:47 ->
  $2.08 at 8:32:00) - the likely blocker; the tape confirms.
- After it: not a crowd name for 2 minutes until 8:36, by then falling.
- "Missed the start" count (the owner: lower the money bar only if we keep
  missing the early start): MI 4:32 (money bar), NTCL 8:30-8:32 (the list's
  10%, then most likely the red-candle check).
- The owner (~8:55am): NTCL had the conditions for v37 and the three-candle
  pattern - why missed? Maybe v37's two green candles? From the log and code:
  - Not the two-green rule: it writes a SKIP line; v37 wrote none for NTCL.
  - During the burst (8:32, new highs $2.08 -> $2.65): v37's regular door
    needs #1/#2 by money or the top gainer - NTCL was #3 ($701k) and gainer
    #5. Every bot's furious door needs the last 1-minute candle not red - the
    8:31 candle WAS red (v36's line at 8:33:00: "last candles RG" = 8:31 red,
    8:32 green). Both doors shut, no line written.
  - After 8:33: v37 buys only over the day's high; NTCL never got back over
    $2.65 (high $2.45 by 8:48).
  - v36/v36b's three-candle pattern: crowd #1 from 8:34, held 2 min at 8:36.
    The green-red pairs were there (8:32/8:33, 8:34/8:35, 8:36/8:37...), but
    the pattern refuses a pullback whose red trades as much as the green
    before it (V36_PULLBACK_VOL, 10-07, "selling, not a light pullback") or
    dips under the rip candle's open (V36_FAILED_RIP) - most likely the
    volume check on the 8:33 crash; the 8:34 green never got back over the
    8:33 red's open (~$2.44). The log says only "NO PATTERN" - it does not
    name which check (a gap; information only).
- r34.39 now also reads NTCL 8:20-9:20 (SEC_DUMP_MISSED) to settle it.
- The owner (~9am): NTCL was not a clean entry anyway - the top wick, then
  the red's long lower wick: the risk from the buy (over the red's open) to
  the bottom of that wick needs twice that much room up to the green's top
  wick (the day's high), and that may not be there. "I want to know the
  reasons why the bots did not enter" - the two blocks above.
- The bots never reached their room check on NTCL. And that check
  (V35_ROOM_RR 2.0) measures room only to YESTERDAY's high (prev_high), not
  to today's high - so on a pullback under today's high it does not do the
  owner's 2:1. NTCL by eye: buy ~$2.45, stop ~$2.17-2.20 (~25-28c risk), $2.65
  high 20c away - under 1:1.
