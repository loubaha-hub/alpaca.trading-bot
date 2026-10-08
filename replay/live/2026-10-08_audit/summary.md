# Trade audit - 2026-10-08 (r34.py v31-r34.28)

Built 2026-10-08 13:51 UTC by parse.py from 10 raw/<SYM>.jsonl files (Render log lines that name the symbol, 90 s before each decision to 30 s after each exit). Times are ET (UTC-4) to the millisecond, from the bot's own log stamps. 74 trades, first fill 04:01:54.774 ET, last exit 09:38:00.565 ET.

## Per strategy

| strategy (account) | trades | up / down | P/L (sum of EXIT lines) |
|---|---:|---:|---:|
| v36 (T6HH) | 26 | 9 / 17 | +$359.07 |
| v36b (AUES) | 30 | 6 / 24 | -$239.91 |
| v37 (P28T) | 18 | 0 / 18 | -$739.95 |

## BOOK cross-check

| BOOK line (ET) | strategy | BOOK trades | BOOK realised | trades here (exits up to then) | sum here | difference |
|---|---|---:|---:|---:|---:|---:|
| 09:27:18 | v36 | 24 | +$647.51 | 24 | +$647.51 | match |
| 09:27:18 | v37 | 18 | -$739.95 | 18 | -$739.95 | match |
| 09:27:18 | v36b | 28 | -$49.76 | 28 | -$49.76 | match |
| 09:47:22 | v36 | 26 | +$359.07 | 26 | +$359.07 | match |
| 09:47:22 | v37 | 18 | -$739.95 | 18 | -$739.95 | match |
| 09:47:22 | v36b | 30 | -$239.91 | 30 | -$239.91 | match |

## Flags (count / summed P/L of the flagged trades)

| flag | v36 | v36b | v37 | all |
|---|---:|---:|---:|---:|
| F1 furious_or_fast_buy_with_5s_down | 2 / -$607.37 | 2 / -$144.81 | 0 / +$0.00 | 4 / -$752.18 |
| F2 bid_gap_over_stop | 4 / -$804.03 | 6 / -$377.48 | 2 / -$337.84 | 12 / -$1,519.35 |
| F3 stop_not_from_fill | 4 / +$263.19 | 18 / -$459.08 | 7 / -$176.64 | 29 / -$372.53 |
| F4 slow_sale | 19 / -$416.92 | 15 / -$308.28 | 12 / -$540.81 | 46 / -$1,266.01 |
| F5 stop_fill_slippage | 4 / +$45.15 | 8 / -$204.44 | 2 / -$278.07 | 14 / -$437.36 |
| F6 quick_rebuy | 5 / +$349.82 | 5 / +$6.83 | 4 / -$43.82 | 14 / +$312.83 |
| F7 v37_tiny_giveback | 0 / +$0.00 | 0 / +$0.00 | 14 / -$246.30 | 14 / -$246.30 |
| F8 gain_given_back | 6 / -$778.96 | 4 / -$166.46 | 0 / +$0.00 | 10 / -$945.42 |
| F9 never_above_fill | 5 / -$982.26 | 7 / -$449.56 | 4 / -$493.65 | 16 / -$1,925.47 |
| any flag | 24 / +$68.34 | 24 / -$313.72 | 18 / -$739.95 | 66 / -$985.33 |

F1 is judged only on the trade's own FURIOUS line: v37 logs no 5-second move (see data gaps). A trade can carry several flags, so rows overlap.

## The 10 worst trades

| # | trade | route | decision -> fill | fill | stop | exit | P/L | flags |
|---:|---|---|---:|---:|---:|---|---:|---|
| 1 | v36 BIAF 08:06:44.547 | furious (FULL POSITION at once) | 903 ms | 7.4900 | 7.3900 | stop 6.8307 @ 08:06:50.684 | -$382.37 | F1, F2, F4, F5, F9 |
| 2 | v36 CHR 08:02:10.133 | furious (FULL POSITION at once) | 1343 ms | 1.9200 | 1.8200 | stop 1.7700 @ 08:02:34.134 | -$347.85 | F8 |
| 3 | v37 FLYE 07:25:56.835 | accel (ACCELERATING 0.40, furious speed), re-entry (buy 2 today) | n/a | 2.9100 | 2.8100 | stop 2.5065 @ 07:26:01.310 | -$261.07 | F2, F4, F5, F9 |
| 4 | v36 KAPA 09:34:49.212 | furious (FULL POSITION at once) | 1181 ms | 1.1600 | 1.0600 | 10s 1.1000 @ 09:36:17.443 | -$225.00 | F1, F4 |
| 5 | v36 FLYE 07:24:13.656 | furious (FULL POSITION at once), re-entry (buy 5 today) | 1319 ms | 2.3300 | 2.2300 | stop 2.2157 @ 07:24:16.210 | -$218.62 | F2, F4, F9 |
| 6 | v36 FLYE 07:22:08.726 | furious (FULL POSITION at once) | 1804 ms | 1.6399 | 1.5399 | stop 1.5333 @ 07:22:26.824 | -$197.07 | F4, F8 |
| 7 | v36 FLYE 07:22:36.740 | furious (FULL POSITION at once), re-entry (buy 2 today) | 1745 ms | 1.7800 | 1.6800 | stop 1.6732 @ 07:22:50.119 | -$178.23 | F4, F6, F9 |
| 8 | v37 CHR 08:02:18.670 | accel (ACCELERATING 0.54, furious speed) | n/a | 2.0600 | 1.9900 | stop 1.9900 @ 08:02:22.070 | -$138.81 | F9 |
| 9 | v36 AIXI 04:02:40.813 | furious (FULL POSITION at once), re-entry (buy 2 today) | 1089 ms | 2.4300 | 2.3300 | 10s 2.3527 @ 04:03:35.698 | -$130.54 | F4, F6, F8 |
| 10 | v36 BIAF 08:09:51.335 | furious (FULL POSITION at once), re-entry (buy 3 today) | 1368 ms | 8.1800 | 8.0800 | stop 7.9500 @ 08:09:53.541 | -$107.64 | F2, F4, F5, F6, F9 |

- **v36-BIAF-080644**: F1 decision 08:06:43.644 at 7.4580: 5s -0.7% (speed 2.47); F2 fill 7.4900, stop 7.3900, bid 6.8200 295 ms after the fill (SELL line (bid)); the stop triggered 8 ms after the fill; F4 trigger -> EXIT 6129 ms, 3 sell orders, 2 cancels; F5 stop 7.3900, filled 6.8307 (55.9c under); F9 peak 7.4900 == fill 7.4900
- **v36-CHR-080210**: F8 fill 1.9200, peak 2.0600 (+14.0c), exit 1.7700
- **v37-FLYE-072556**: F2 fill 2.9100, stop 2.8100, bid 2.6400 0 ms after the fill (the market ... is at the stop); the stop triggered 7 ms after the fill; F4 trigger -> EXIT 4468 ms, 2 sell orders, 2 cancels; F5 stop 2.8100, filled 2.5065 (30.4c under); F9 peak 2.9100 == fill 2.9100
- **v36-KAPA-093449**: F1 decision 09:34:48.031 at 1.1200: 5s +0.0% (speed 0.48); F4 trigger -> EXIT 2795 ms, 1 sell orders, 0 cancels
- **v36-FLYE-072413**: F2 fill 2.3300, stop 2.2300, bid 2.2200 5 ms after the fill (the market ... is at the stop); the stop triggered 8 ms after the fill; F4 trigger -> EXIT 2546 ms, 2 sell orders, 0 cancels; F9 peak 2.3300 == fill 2.3300
- **v36-FLYE-072208**: F4 trigger -> EXIT 8861 ms, 5 sell orders, 4 cancels; F8 fill 1.6399, peak 1.7502 (+11.0c), exit 1.5333
- **v36-FLYE-072236**: F4 trigger -> EXIT 3247 ms, 2 sell orders, 0 cancels; F6 decision 8.171 s (fill 9.916 s) after the previous EXIT; F9 peak 1.7800 == fill 1.7800
- **v37-CHR-080218**: F9 peak 2.0600 == fill 2.0600
- **v36-AIXI-040240**: F4 trigger -> EXIT 5301 ms, 4 sell orders, 1 cancels; F6 decision 0.969 s (fill 2.058 s) after the previous EXIT; F8 fill 2.4300, peak 2.5400 (+11.0c), exit 2.3527
- **v36-BIAF-080951**: F2 fill 8.1800, stop 8.0800, bid 8.0500 79 ms after the fill (the market ... is at the stop); the stop triggered 3 ms after the fill; F4 trigger -> EXIT 2203 ms, 1 sell orders, 0 cancels; F5 stop 8.0800, filled 7.9500 (13.0c under); F6 decision 0.539 s (fill 1.907 s) after the previous EXIT; F9 peak 8.1800 == fill 8.1800

## Flag evidence

### F1 furious_or_fast_buy_with_5s_down - 4 trade(s), -$752.18

- v36-BIAF-080644 (-$382.37): decision 08:06:43.644 at 7.4580: 5s -0.7% (speed 2.47)
- v36b-BIAF-080645 (-$61.65): decision 08:06:43.645 at 7.4580: 5s -0.7% (speed 2.47)
- v36-KAPA-093449 (-$225.00): decision 09:34:48.031 at 1.1200: 5s +0.0% (speed 0.48)
- v36b-KAPA-093451 (-$83.16): decision 09:34:48.044 at 1.1200: 5s +0.0% (speed 0.48)

### F2 bid_gap_over_stop - 12 trade(s), -$1,519.35

- v37-DKI-041338 (-$76.77): fill 2.5000, stop 2.4750, bid 2.4600 219 ms after the fill (SELL line (bid)); the stop triggered 0 ms after the fill
- v36b-FLYE-072253 (-$89.42): fill 1.8000, stop 1.7363, bid 1.7200 701 ms after the fill (the market ... is at the stop); the stop triggered 702 ms after the fill
- v36b-FLYE-072316 (-$65.84): fill 1.8300, stop 1.7654, bid 1.7600 1196 ms after the fill (the market ... is at the stop); the stop triggered 1198 ms after the fill
- v36b-FLYE-072413 (-$48.10): fill 2.3300, stop 2.2300, bid 2.2200 10 ms after the fill (the market ... is at the stop); the stop triggered 108 ms after the fill
- v36-FLYE-072413 (-$218.62): fill 2.3300, stop 2.2300, bid 2.2200 5 ms after the fill (the market ... is at the stop); the stop triggered 8 ms after the fill
- v36b-FLYE-072556 (-$101.46): fill 2.7300, stop 2.7027, bid 2.6700 24 ms after the fill (the market ... is at the stop); the stop triggered 30 ms after the fill
- v37-FLYE-072556 (-$261.07): fill 2.9100, stop 2.8100, bid 2.6400 0 ms after the fill (the market ... is at the stop); the stop triggered 7 ms after the fill
- v36-FLYE-072557 (-$95.40): fill 2.7500, stop 2.6680, bid 2.5700 97 ms after the fill (the market ... is at the stop); the stop triggered 103 ms after the fill
- v36-BIAF-080644 (-$382.37): fill 7.4900, stop 7.3900, bid 6.8200 295 ms after the fill (SELL line (bid)); the stop triggered 8 ms after the fill
- v36b-BIAF-080645 (-$61.65): fill 7.0900, stop 7.0191, bid 6.8200 4 ms after the fill (the market ... is at the stop); the stop triggered 4 ms after the fill
- v36-BIAF-080951 (-$107.64): fill 8.1800, stop 8.0800, bid 8.0500 79 ms after the fill (the market ... is at the stop); the stop triggered 3 ms after the fill
- v36b-BIAF-080951 (-$11.01): fill 8.1900, stop 8.0900, bid 8.0500 2 ms after the fill (the market ... is at the stop); the stop triggered 3 ms after the fill

### F3 stop_not_from_fill - 29 trade(s), -$372.53

- v36b-AIXI-040155 (+$132.96): stop 2.1627 vs fill - 0.10 = 2.1400 (3.45% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 2.1700, print 2.2296) = 2.1627, under the 1% floor 2.2176 so min() kept it, and above fill - 0.10 = 2.1400 so max() kept it.
- v36b-AIXI-040235 (-$13.63): stop 2.3668 vs fill - 0.10 = 2.3300 (2.60% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 2.3400, print 2.4400) = 2.3668, under the 1% floor 2.4057 so min() kept it, and above fill - 0.10 = 2.3300 so max() kept it.
- v36b-AIXI-040302 (-$55.09): stop 2.4760 vs fill - 0.10 = 2.4010 (1.00% under the fill); matches: 1% under the fill (MIN_STOP_PCT floor: min(stop_ref, fill x 0.99)) - v36b: the stop was set from the decision print, not the fill: stop_ref = max(bar low, 3% under 2.5000 = 2.4250, 8% under 2.5000 = 2.3000, line 2.49) sat above the fill-based floor, so min(stop_ref, fill x 0.99) took 2.4760 (1% under the fill 2.5010); fill - 0.10 = 2.4010 is lower, so max() kept 2.4760.
- v36b-IPW-041018 (-$52.56): stop 1.7072 vs fill - 0.10 = 1.6700 (3.55% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.7500, print 1.7600) = 1.7072, under the 1% floor 1.7523 so min() kept it, and above fill - 0.10 = 1.6700 so max() kept it.
- v37-IPW-041018 (-$41.10): stop 1.7044 vs fill - 0.10 = 1.6800 (4.25% under the fill); matches: v37 speed stop: fill x (1 - 4.25%) (V37_STOP_SHARE of the last minute's move, 3-8%) - v37 stop_for(): max(fill x (1 - stop_pct), fill - 0.10) = max(1.7044, 1.6800): the speed-based stop is the tighter one, so it was kept; the whole/half-dollar line (1.50 - 0.01) is lower still.
- v36b-IPW-041049 (-$42.18): stop 1.7654 vs fill - 0.10 = 1.7100 (2.46% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.8000, print 1.8200) = 1.7654, under the 1% floor 1.7919 so min() kept it, and above fill - 0.10 = 1.7100 so max() kept it.
- v37-IPW-041050 (-$44.58): stop 1.7743 vs fill - 0.10 = 1.7500 (4.09% under the fill); matches: v37 speed stop: fill x (1 - 4.09%) (V37_STOP_SHARE of the last minute's move, 3-8%) - v37 stop_for(): max(fill x (1 - stop_pct), fill - 0.10) = max(1.7743, 1.7500): the speed-based stop is the tighter one, so it was kept; the whole/half-dollar line (1.50 - 0.01) is lower still.
- v36b-DKI-041337 (-$6.51): stop 2.3959 vs fill - 0.10 = 2.3900 (3.78% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 2.1500, print 2.4700) = 2.3959, under the 1% floor 2.4651 so min() kept it, and above fill - 0.10 = 2.3900 so max() kept it.
- v37-DKI-041338 (-$76.77): stop 2.4750 vs fill - 0.10 = 2.4000 (1.00% under the fill); matches: 1% under the fill (MIN_STOP_PCT floor: min(stop_ref, fill x 0.99)) - v37: the line stop min(line - 0.01 = 2.4900, fill x 0.99 = 2.4750) raised the stop to the 1% floor 2.4750, above fill - 0.10 = 2.4000.
- v36-SBFM-052114 (+$207.36): stop 1.1040 vs fill - 0.10 = 1.1000 (8.00% under the fill); matches: 8% under the decision print (V36_FURIOUS_STOP_MAX) - V36_FURIOUS_STOP_MAX: 8% under the print 1.2000 = 1.1040, above fill - 0.10 = 1.1000.
- v36b-SBFM-052114 (+$78.36): stop 1.1640 vs fill - 0.10 = 1.1000 (3.00% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.1900, print 1.2000) = 1.1640, under the 1% floor 1.1880 so min() kept it, and above fill - 0.10 = 1.1000 so max() kept it.
- v37-SBFM-052117 (+$0.00): stop 1.1625 vs fill - 0.10 = 1.1200 (4.71% under the fill); matches: v37 speed stop: fill x (1 - 4.71%) (V37_STOP_SHARE of the last minute's move, 3-8%) - v37 stop_for(): max(fill x (1 - stop_pct), fill - 0.10) = max(1.1625, 1.1200): the speed-based stop is the tighter one, so it was kept; the whole/half-dollar line (1.00 - 0.01) is lower still.
- v37-SBFM-052126 (+$0.00): stop 1.1780 vs fill - 0.10 = 1.1400 (5.00% under the fill); matches: v37 speed stop: fill x (1 - 5.00%) (V37_STOP_SHARE of the last minute's move, 3-8%) - v37 stop_for(): max(fill x (1 - stop_pct), fill - 0.10) = max(1.1780, 1.1400): the speed-based stop is the tighter one, so it was kept; the whole/half-dollar line (1.00 - 0.01) is lower still.
- v37-SBFM-052136 (-$14.19): stop 1.2319 vs fill - 0.10 = 1.1900 (4.50% under the fill); matches: v37 speed stop: fill x (1 - 4.50%) (V37_STOP_SHARE of the last minute's move, 3-8%) - v37 stop_for(): max(fill x (1 - stop_pct), fill - 0.10) = max(1.2319, 1.1900): the speed-based stop is the tighter one, so it was kept; the whole/half-dollar line (1.00 - 0.01) is lower still.
- v36-MOBX-070133 (+$118.46): stop 1.3400 vs fill - 0.10 = 1.3300 (6.29% under the fill); matches: the ENTER-line stop (sizing stop_ref, unchanged) - v36: stop 1.3400 = the sizing stop_ref from the ENTER line (the last 1-minute bar's low for a furious 'hod' entry - the bar itself is not logged), above fill - 0.10 = 1.3300, so max() kept it; 8% under the print = 1.3156 and the line 0.99 are lower.
- v36b-MOBX-070134 (+$60.06): stop 1.3871 vs fill - 0.10 = 1.3300 (3.00% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.3600, print 1.4300) = 1.3871, under the 1% floor 1.4157 so min() kept it, and above fill - 0.10 = 1.3300 so max() kept it.
- v37-MOBX-070149 (+$0.00): stop 1.4162 vs fill - 0.10 = 1.3600 (3.00% under the fill); matches: v37 speed stop: fill x (1 - 3.00%) (V37_STOP_SHARE of the last minute's move, 3-8%) - v37 stop_for(): max(fill x (1 - stop_pct), fill - 0.10) = max(1.4162, 1.3600): the speed-based stop is the tighter one, so it was kept; the whole/half-dollar line (1.00 - 0.01) is lower still.
- v36b-FLYE-072207 (-$71.54): stop 1.6005 vs fill - 0.10 = 1.5400 (2.41% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.5800, print 1.6500) = 1.6005, under the 1% floor 1.6236 so min() kept it, and above fill - 0.10 = 1.5400 so max() kept it.
- v36b-FLYE-072236 (-$72.81): stop 1.7072 vs fill - 0.10 = 1.6800 (4.09% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.6300, print 1.7600) = 1.7072, under the 1% floor 1.7622 so min() kept it, and above fill - 0.10 = 1.6800 so max() kept it.
- v36b-FLYE-072253 (-$89.42): stop 1.7363 vs fill - 0.10 = 1.7000 (3.54% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.6300, print 1.7900) = 1.7363, under the 1% floor 1.7820 so min() kept it, and above fill - 0.10 = 1.7000 so max() kept it.
- v36b-FLYE-072316 (-$65.84): stop 1.7654 vs fill - 0.10 = 1.7300 (3.53% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.8100, print 1.8200) = 1.7654, under the 1% floor 1.8117 so min() kept it, and above fill - 0.10 = 1.7300 so max() kept it.
- v36b-FLYE-072323 (+$175.98): stop 1.7848 vs fill - 0.10 = 1.7700 (4.56% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.8100, print 1.8400) = 1.7848, under the 1% floor 1.8513 so min() kept it, and above fill - 0.10 = 1.7700 so max() kept it.
- v36-FLYE-072342 (+$32.77): stop 1.9899 vs fill - 0.10 = 1.9100 (1.00% under the fill); matches: 1% under the fill (MIN_STOP_PCT floor: min(stop_ref, fill x 0.99)) - v36: the stop was set from the decision print, not the fill: stop_ref = max(bar low, 8% under 2.0200 = 1.8584, line 1.99) sat above the fill-based floor, so min(stop_ref, fill x 0.99) took 1.9899 (1% under the fill 2.0100); fill - 0.10 = 1.9100 is lower, so max() kept 1.9899.
- v36b-FLYE-072556 (-$101.46): stop 2.7027 vs fill - 0.10 = 2.6300 (1.00% under the fill); matches: 1% under the fill (MIN_STOP_PCT floor: min(stop_ref, fill x 0.99)) - v36b: the stop was set from the decision print, not the fill: stop_ref = max(bar low, 3% under 2.9000 = 2.8130, 8% under 2.9000 = 2.6680, line 2.49) sat above the fill-based floor, so min(stop_ref, fill x 0.99) took 2.7027 (1% under the fill 2.7300); fill - 0.10 = 2.6300 is lower, so max() kept 2.7027.
- v36-FLYE-072557 (-$95.40): stop 2.6680 vs fill - 0.10 = 2.6500 (2.98% under the fill); matches: 8% under the decision print (V36_FURIOUS_STOP_MAX) - V36_FURIOUS_STOP_MAX: 8% under the print 2.9000 = 2.6680, above fill - 0.10 = 2.6500.
- v36b-CHR-080209 (-$83.60): stop 1.8430 vs fill - 0.10 = 1.7900 (2.49% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.8700, print 1.9000) = 1.8430, under the 1% floor 1.8711 so min() kept it, and above fill - 0.10 = 1.7900 so max() kept it.
- v36b-BIAF-080645 (-$61.65): stop 7.0191 vs fill - 0.10 = 6.9900 (1.00% under the fill); matches: 1% under the fill (MIN_STOP_PCT floor: min(stop_ref, fill x 0.99)) - v36b: the stop was set from the decision print, not the fill: stop_ref = max(bar low, 3% under 7.4580 = 7.2343, 8% under 7.4580 = 6.8614, line 6.99) sat above the fill-based floor, so min(stop_ref, fill x 0.99) took 7.0191 (1% under the fill 7.0900); fill - 0.10 = 6.9900 is lower, so max() kept 7.0191.
- v36b-KAPA-093451 (-$83.16): stop 1.0864 vs fill - 0.10 = 1.0600 (6.34% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.1000, print 1.1200) = 1.0864, under the 1% floor 1.1484 so min() kept it, and above fill - 0.10 = 1.0600 so max() kept it.
- v36b-KAPA-093737 (-$106.99): stop 1.1640 vs fill - 0.10 = 1.1400 (6.13% under the fill); matches: 3% under max(trigger, decision print) (v36b MAX_STOP) - v36b MAX_STOP: stop_ref = 3% under max(trigger 1.1800, print 1.2000) = 1.1640, under the 1% floor 1.2276 so min() kept it, and above fill - 0.10 = 1.1400 so max() kept it.

### F4 slow_sale - 46 trade(s), -$1,266.01

- v36-AIXI-040154 (+$328.75): trigger -> EXIT 8908 ms, 8 sell orders, 2 cancels
- v36b-AIXI-040155 (+$132.96): trigger -> EXIT 4557 ms, 3 sell orders, 2 cancels
- v37-AIXI-040231 (-$3.02): trigger -> EXIT 2930 ms, 2 sell orders, 1 cancels
- v36b-AIXI-040235 (-$13.63): trigger -> EXIT 6101 ms, 4 sell orders, 2 cancels
- v36-AIXI-040240 (-$130.54): trigger -> EXIT 5301 ms, 4 sell orders, 1 cancels
- v36b-AIXI-040302 (-$55.09): trigger -> EXIT 5303 ms, 4 sell orders, 1 cancels
- v36-IPW-041018 (+$108.88): trigger -> EXIT 2784 ms, 2 sell orders, 1 cancels
- v37-IPW-041050 (-$44.58): trigger -> EXIT 4719 ms, 3 sell orders, 2 cancels
- v36b-DKI-041337 (-$6.51): trigger -> EXIT 2085 ms, 2 sell orders, 0 cancels
- v36-DKI-041337 (-$65.34): trigger -> EXIT 9455 ms, 7 sell orders, 2 cancels
- v37-DKI-041338 (-$76.77): trigger -> EXIT 2731 ms, 3 sell orders, 0 cancels
- v37-DKI-041345 (-$12.63): trigger -> EXIT 7156 ms, 6 sell orders, 1 cancels
- v37-DKI-041626 (-$0.22): trigger -> EXIT 3374 ms, 1 sell orders, 0 cancels
- v36b-DKI-041803 (-$4.81): trigger -> EXIT 5040 ms, 3 sell orders, 2 cancels
- v37-DKI-050047 (-$13.11): trigger -> EXIT 4049 ms, 4 sell orders, 0 cancels
- v36b-DKI-050459 (-$6.08): trigger -> EXIT 2524 ms, 2 sell orders, 1 cancels
- v36-DKI-050503 (-$14.90): trigger -> EXIT 2072 ms, 1 sell orders, 0 cancels
- v36-DKI-062022 (-$13.25): trigger -> EXIT 4204 ms, 3 sell orders, 2 cancels
- v36-DKI-063953 (-$12.40): trigger -> EXIT 4334 ms, 3 sell orders, 1 cancels
- v36-DKI-064651 (-$1.69): trigger -> EXIT 2428 ms, 2 sell orders, 1 cancels
- v36-DKI-065438 (+$630.56): trigger -> EXIT 4499 ms, 3 sell orders, 1 cancels
- v36b-DKI-065441 (+$218.21): trigger -> EXIT 7303 ms, 4 sell orders, 1 cancels
- v37-DKI-065736 (-$29.88): trigger -> EXIT 12147 ms, 5 sell orders, 3 cancels
- v36-MOBX-070133 (+$118.46): trigger -> EXIT 5432 ms, 5 sell orders, 1 cancels
- v37-MOBX-070149 (+$0.00): trigger -> EXIT 2181 ms, 2 sell orders, 0 cancels
- v36b-FLYE-072207 (-$71.54): trigger -> EXIT 4672 ms, 3 sell orders, 2 cancels
- v36-FLYE-072208 (-$197.07): trigger -> EXIT 8861 ms, 5 sell orders, 4 cancels
- v36-FLYE-072236 (-$178.23): trigger -> EXIT 3247 ms, 2 sell orders, 0 cancels
- v36b-FLYE-072253 (-$89.42): trigger -> EXIT 5033 ms, 4 sell orders, 1 cancels
- v37-FLYE-072330 (-$35.86): trigger -> EXIT 6476 ms, 6 sell orders, 0 cancels
- v36-FLYE-072342 (+$32.77): trigger -> EXIT 4282 ms, 2 sell orders, 1 cancels
- v36b-FLYE-072413 (-$48.10): trigger -> EXIT 8305 ms, 6 sell orders, 3 cancels
- v36-FLYE-072413 (-$218.62): trigger -> EXIT 2546 ms, 2 sell orders, 0 cancels
- v36b-FLYE-072556 (-$101.46): trigger -> EXIT 5683 ms, 4 sell orders, 0 cancels
- v37-FLYE-072556 (-$261.07): trigger -> EXIT 4468 ms, 2 sell orders, 2 cancels
- v36-BIAF-080644 (-$382.37): trigger -> EXIT 6129 ms, 3 sell orders, 2 cancels
- v36b-BIAF-080645 (-$61.65): trigger -> EXIT 3212 ms, 3 sell orders, 0 cancels
- v36-BIAF-080940 (-$25.85): trigger -> EXIT 2395 ms, 2 sell orders, 0 cancels
- v37-BIAF-080941 (-$46.67): trigger -> EXIT 6882 ms, 5 sell orders, 2 cancels
- v37-BIAF-080951 (-$17.00): trigger -> EXIT 2937 ms, 2 sell orders, 1 cancels
- v36-BIAF-080951 (-$107.64): trigger -> EXIT 2203 ms, 1 sell orders, 0 cancels
- v36b-BIAF-080951 (-$11.01): trigger -> EXIT 13128 ms, 7 sell orders, 5 cancels
- v36-KAPA-093449 (-$225.00): trigger -> EXIT 2795 ms, 1 sell orders, 0 cancels
- v36b-KAPA-093451 (-$83.16): trigger -> EXIT 10092 ms, 1 sell orders, 0 cancels
- v36-KAPA-093736 (-$63.44): trigger -> EXIT 3800 ms, 1 sell orders, 0 cancels
- v36b-KAPA-093737 (-$106.99): trigger -> EXIT 3015 ms, 1 sell orders, 0 cancels

### F5 stop_fill_slippage - 14 trade(s), -$437.36

- v36b-AIXI-040302 (-$55.09): stop 2.4760, filled 2.4111 (6.5c under)
- v36-DKI-065438 (+$630.56): stop 6.9900, filled 6.9092 (8.1c under)
- v36b-DKI-065441 (+$218.21): stop 6.9900, filled 6.8350 (15.5c under)
- v36b-FLYE-072556 (-$101.46): stop 2.7027, filled 2.5425 (16.0c under)
- v37-FLYE-072556 (-$261.07): stop 2.8100, filled 2.5065 (30.4c under)
- v36-FLYE-072557 (-$95.40): stop 2.6680, filled 2.5700 (9.8c under)
- v36b-CHR-080209 (-$83.60): stop 1.8430, filled 1.7900 (5.3c under)
- v36-BIAF-080644 (-$382.37): stop 7.3900, filled 6.8307 (55.9c under)
- v36b-BIAF-080645 (-$61.65): stop 7.0191, filled 6.7964 (22.3c under)
- v36b-BIAF-080940 (-$2.85): stop 7.8700, filled 7.7800 (9.0c under)
- v37-BIAF-080951 (-$17.00): stop 7.9900, filled 7.9113 (7.9c under)
- v36-BIAF-080951 (-$107.64): stop 8.0800, filled 7.9500 (13.0c under)
- v36b-BIAF-080951 (-$11.01): stop 8.0900, filled 7.8459 (24.4c under)
- v36b-KAPA-093737 (-$106.99): stop 1.1640, filled 1.1100 (5.4c under)

### F6 quick_rebuy - 14 trade(s), +$312.83

- v36b-AIXI-040235 (-$13.63): decision 0.005 s (fill 0.988 s) after the previous EXIT
- v36-AIXI-040240 (-$130.54): decision 0.969 s (fill 2.058 s) after the previous EXIT
- v36b-AIXI-040302 (-$55.09): decision 3.723 s (fill 5.032 s) after the previous EXIT
- v37-DKI-041345 (-$12.63): decision 4.150 s (fill 4.150 s) after the previous EXIT
- v37-SBFM-052126 (+$0.00): decision 3.479 s (fill 3.479 s) after the previous EXIT
- v37-SBFM-052136 (-$14.19): decision 0.928 s (fill 0.928 s) after the previous EXIT
- v36-FLYE-072236 (-$178.23): decision 8.171 s (fill 9.916 s) after the previous EXIT
- v36-FLYE-072253 (+$733.46): decision 1.830 s (fill 2.997 s) after the previous EXIT
- v36b-FLYE-072253 (-$89.42): decision 7.881 s (fill 9.150 s) after the previous EXIT
- v36b-FLYE-072323 (+$175.98): decision 3.956 s (fill 4.813 s) after the previous EXIT
- v36-FLYE-072342 (+$32.77): decision 0.008 s (fill 1.255 s) after the previous EXIT
- v37-BIAF-080951 (-$17.00): decision 2.766 s (fill 2.766 s) after the previous EXIT
- v36-BIAF-080951 (-$107.64): decision 0.539 s (fill 1.907 s) after the previous EXIT
- v36b-BIAF-080951 (-$11.01): decision 2.501 s (fill 3.937 s) after the previous EXIT

### F7 v37_tiny_giveback - 14 trade(s), -$246.30

- v37-AIXI-040231 (-$3.02): peak 2.4497 - entry 2.4320 = 1.8c
- v37-IPW-041018 (-$41.10): peak 1.7900 - entry 1.7800 = 1.0c
- v37-IPW-041050 (-$44.58): peak 1.8600 - entry 1.8500 = 1.0c
- v37-DKI-041345 (-$12.63): peak 2.6100 - entry 2.6000 = 1.0c
- v37-DKI-041626 (-$0.22): peak 2.9900 - entry 2.9800 = 1.0c
- v37-DKI-050047 (-$13.11): peak 3.9112 - entry 3.9000 = 1.1c
- v37-SBFM-052117 (+$0.00): peak 1.2300 - entry 1.2200 = 1.0c
- v37-SBFM-052126 (+$0.00): peak 1.2500 - entry 1.2400 = 1.0c
- v37-SBFM-052136 (-$14.19): peak 1.3000 - entry 1.2900 = 1.0c
- v37-MEDS-054351 (-$5.04): peak 4.1400 - entry 4.1300 = 1.0c
- v37-DKI-065736 (-$29.88): peak 7.3900 - entry 7.3800 = 1.0c
- v37-MOBX-070149 (+$0.00): peak 1.4700 - entry 1.4600 = 1.0c
- v37-FLYE-072330 (-$35.86): peak 1.9200 - entry 1.9000 = 2.0c
- v37-BIAF-080941 (-$46.67): peak 8.0000 - entry 7.9900 = 1.0c

### F8 gain_given_back - 10 trade(s), -$945.42

- v36-AIXI-040240 (-$130.54): fill 2.4300, peak 2.5400 (+11.0c), exit 2.3527
- v36b-DKI-041337 (-$6.51): fill 2.4900, peak 2.6900 (+20.0c), exit 2.4777
- v36-DKI-041337 (-$65.34): fill 2.5000, peak 2.6900 (+19.0c), exit 2.4607
- v36b-DKI-041803 (-$4.81): fill 3.1728, peak 3.3400 (+16.7c), exit 3.0704
- v36b-FLYE-072207 (-$71.54): fill 1.6400, peak 1.7502 (+11.0c), exit 1.5674
- v36-FLYE-072208 (-$197.07): fill 1.6399, peak 1.7502 (+11.0c), exit 1.5333
- v36-FLYE-074043 (-$12.31): fill 3.3619, peak 3.6000 (+23.8c), exit 3.0200
- v36b-CHR-080209 (-$83.60): fill 1.8900, peak 2.0600 (+17.0c), exit 1.7900
- v36-CHR-080210 (-$347.85): fill 1.9200, peak 2.0600 (+14.0c), exit 1.7700
- v36-BIAF-080940 (-$25.85): fill 7.9000, peak 8.0500 (+15.0c), exit 7.8500

### F9 never_above_fill - 16 trade(s), -$1,925.47

- v37-DKI-041338 (-$76.77): peak 2.5000 == fill 2.5000
- v36-FLYE-072236 (-$178.23): peak 1.7800 == fill 1.7800
- v36b-FLYE-072236 (-$72.81): peak 1.7800 == fill 1.7800
- v36b-FLYE-072316 (-$65.84): peak 1.8300 == fill 1.8300
- v36b-FLYE-072413 (-$48.10): peak 2.3300 == fill 2.3300
- v36-FLYE-072413 (-$218.62): peak 2.3300 == fill 2.3300
- v37-FLYE-072556 (-$261.07): peak 2.9100 == fill 2.9100
- v36-FLYE-072557 (-$95.40): peak 2.7500 == fill 2.7500
- v37-CHR-080218 (-$138.81): peak 2.0600 == fill 2.0600
- v36-BIAF-080644 (-$382.37): peak 7.4900 == fill 7.4900
- v36b-BIAF-080645 (-$61.65): peak 7.0900 == fill 7.0900
- v37-BIAF-080951 (-$17.00): peak 8.1900 == fill 8.1900
- v36-BIAF-080951 (-$107.64): peak 8.1800 == fill 8.1800
- v36b-BIAF-080951 (-$11.01): peak 8.1900 == fill 8.1900
- v36b-KAPA-093451 (-$83.16): peak 1.1600 == fill 1.1600
- v36b-KAPA-093737 (-$106.99): peak 1.2400 == fill 1.2400

## Other things the log shows (not one of F1-F9)

- v36-AIXI-040154 (+$328.75): 1 buy attempt(s) got nothing before the one that filled; the first FURIOUS attempt (04:01:43.161, 5s +0.0%) missed; the buy that filled was decided at 5s +2.8% (F1 judged on the filling decision)
- v36b-AIXI-040155 (+$132.96): 1 buy attempt(s) got nothing before the one that filled; the first FURIOUS attempt (04:01:43.163, 5s +0.0%) missed; the buy that filled was decided at 5s +1.4% (F1 judged on the filling decision)
- v37-IPW-041050 (-$44.58): 1 buy attempt(s) got nothing before the one that filled
- v36-DKI-041803 (+$9.41): ADD at 04:19:28.726 set the stop to the new average 3.3743; the stop sold 5 ms later (stop)
- v36-DKI-050043 (+$281.32): 1 buy attempt(s) got nothing before the one that filled
- v37-DKI-050047 (-$13.11): 1 buy attempt(s) got nothing before the one that filled
- v37-DKI-065736 (-$29.88): 2 buy attempt(s) got nothing before the one that filled

## Every trade

| trade | route | 5s at decision | decision -> fill ms | fill | bid after fill | stop | fill -> trigger ms | trigger -> EXIT ms | sells | exit | peak | P/L | flags |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| v36-AIXI-040154 | furious (FULL POSITION at once) | +2.8% | 1012 | 2.2400 | 2.3400 (+7517 ms) | 2.1400 | 35073 | 8908 | 8 | trail 2.4214 | 2.4900 | +$328.75 | F4 |
| v36b-AIXI-040155 | furious (FULL POSITION at once) | +1.4% | 1238 | 2.2400 | 2.3400 (+6930 ms) | 2.1627 | 34488 | 4557 | 3 | trail 2.4297 | 2.4900 | +$132.96 | F3, F4 |
| v37-AIXI-040231 | normal starter (a tenth of a position) | - | - | 2.4320 | 2.4000 (+522 ms) | 2.2374 | 8608 | 2930 | 2 | giveback 2.4176 | 2.4497 | -$3.02 | F4, F7 |
| v36b-AIXI-040235 | furious (FULL POSITION at once), re-entry (buy 2 today) | +23.2% | 983 | 2.4300 | 2.3900 (+3 ms) | 2.3668 | 15853 | 6101 | 4 | stop 2.3730 | 2.4497 | -$13.63 | F3, F4, F6 |
| v36-AIXI-040240 | furious (FULL POSITION at once), re-entry (buy 2 today) | +20.2% | 1089 | 2.4300 | 2.4100 (+901 ms) | 2.3300 | 49584 | 5301 | 4 | 10s 2.3527 | 2.5400 | -$130.54 | F4, F6, F8 |
| v36b-AIXI-040302 | furious (FULL POSITION at once), re-entry (buy 3 today) | +3.3% | 1309 | 2.5010 | 2.4500 (+2474 ms) | 2.4760 | 2476 | 5303 | 4 | stop 2.4111 | 2.5400 | -$55.09 | F3, F4, F5, F6 |
| v36b-IPW-041018 | furious (FULL POSITION at once) | +2.3% | 1231 | 1.7700 | 1.7900 (+2 ms) | 1.7072 | 5281 | 1140 | 1 | stop 1.7100 | 1.8100 | -$52.56 | F3 |
| v37-IPW-041018 | accel (ACCELERATING 0.46, furious speed) | - | - | 1.7800 | 1.7600 (+4 ms) | 1.7044 | 6 | 956 | 1 | giveback 1.7500 | 1.7900 | -$41.10 | F3, F7 |
| v36-IPW-041018 | furious (FULL POSITION at once) | +2.3% | 1341 | 1.7800 | 1.7700 (+36 ms) | 1.6800 | 103844 | 2784 | 2 | trail 1.8599 | 2.0000 | +$108.88 | F4 |
| v36b-IPW-041049 | furious (FULL POSITION at once), re-entry (buy 2 today) | +4.6% | 1790 | 1.8100 | 1.8400 (+75 ms) | 1.7654 | 14572 | 1003 | 1 | stop 1.7500 | 1.8600 | -$42.18 | F3 |
| v37-IPW-041050 | accel (ACCELERATING 0.36, furious speed), re-entry (buy 2 today) | - | - | 1.8500 | 1.8400 (+2358 ms) | 1.7743 | 2124 | 4719 | 3 | giveback 1.8300 | 1.8600 | -$44.58 | F3, F4, F7 |
| v36b-IPW-041148 | normal starter (a tenth of a full position), re-entry (buy 3 today) | - | - | 1.9200 | 1.9200 (+4004 ms) | 1.8624 | 12321 | 1156 | 1 | stop 1.8500 | 2.0000 | -$5.53 | - |
| v36b-DKI-041337 | furious (FULL POSITION at once) | +3.4% | 1331 | 2.4900 | 2.4600 (+1364 ms) | 2.3959 | 82761 | 2085 | 2 | stop 2.4777 | 2.6900 | -$6.51 | F3, F4, F8 |
| v36-DKI-041337 | furious (FULL POSITION at once) | +3.4% | 1447 | 2.5000 | 2.4600 (+1250 ms) | 2.4000 | 82645 | 9455 | 7 | stop 2.4607 | 2.6900 | -$65.34 | F4, F8 |
| v37-DKI-041338 | accel (ACCELERATING 3.97, furious speed) | - | - | 2.5000 | 2.4600 (+219 ms) | 2.4750 | 0 | 2731 | 3 | stop 2.4307 | 2.5000 | -$76.77 | F2, F3, F4, F9 |
| v37-DKI-041345 | accel (ACCELERATING 7.03, furious speed), re-entry (buy 2 today) | - | - | 2.6000 | 2.5700 (+250 ms) | 2.5000 | 1 | 7156 | 6 | giveback 2.5362 | 2.6100 | -$12.63 | F4, F6, F7 |
| v37-DKI-041626 | normal starter (a tenth of a position), re-entry (buy 3 today) | - | - | 2.9800 | 2.9700 (+3093 ms) | 2.8266 | 2876 | 3374 | 1 | giveback 2.9600 | 2.9900 | -$0.22 | F4, F7 |
| v36b-DKI-041803 | normal starter (a tenth of a full position), re-entry (buy 2 today) | - | - | 3.1728 | 3.1600 (+25117 ms) | 3.0943 | 41985 | 5040 | 3 | stop 3.0704 | 3.3400 | -$4.81 | F4, F8 |
| v36-DKI-041803 | normal starter (a tenth of a full position), re-entry (buy 2 today), + 1 add(s) | - | 4492 | 3.1739 | 3.1600 (+24651 ms) | 2.9900 | 85087 | 866 | 1 | stop 3.3900 | 3.4300 | +$9.41 | - |
| v36b-DKI-050041 | furious (FULL POSITION at once), re-entry (buy 3 today) | +2.8% | 1320 | 3.7467 | 3.8800 (+7183 ms) | 3.6467 | 51978 | 852 | 1 | giveback 4.0200 | 4.1000 | +$96.48 | - |
| v36-DKI-050043 | furious (FULL POSITION at once), re-entry (buy 3 today) | +3.0% | 888 | 3.7500 | 3.8800 (+5554 ms) | 3.6500 | 50347 | 929 | 1 | giveback 4.0100 | 4.1000 | +$281.32 | - |
| v37-DKI-050047 | accel (ACCELERATING 0.52, furious speed), re-entry (buy 4 today) | - | - | 3.9000 | 3.8800 (+1212 ms) | 3.8000 | 996 | 4049 | 4 | giveback 3.8843 | 3.9112 | -$13.11 | F4, F7 |
| v36b-DKI-050459 | normal starter (a tenth of a full position), re-entry (buy 4 today) | - | - | 4.1638 | 4.0200 (+41849 ms) | 4.0255 | 41853 | 2524 | 2 | stop 3.9995 | 4.2400 | -$6.08 | F4 |
| v36-DKI-050503 | normal starter (a tenth of a full position), re-entry (buy 4 today) | - | 6246 | 4.1686 | 4.0200 (+38134 ms) | 3.9900 | 39182 | 2072 | 1 | stop 3.9800 | 4.2400 | -$14.90 | F4 |
| v36-SBFM-052114 | furious (FULL POSITION at once) | +3.3% | 1367 | 1.2000 | 1.2200 (+8495 ms) | 1.1040 | 38695 | 939 | 1 | trail 1.2600 | 1.3200 | +$207.36 | F3 |
| v36b-SBFM-052114 | furious (FULL POSITION at once) | +3.3% | 1533 | 1.2000 | 1.2200 (+8410 ms) | 1.1640 | 38612 | 1869 | 1 | trail 1.2600 | 1.3200 | +$78.36 | F3 |
| v37-SBFM-052117 | accel (ACCELERATING 0.78, furious speed) | - | - | 1.2200 | 1.2200 (+5019 ms) | 1.1625 | 4805 | 919 | 1 | giveback 1.2200 | 1.2300 | +$0.00 | F3, F7 |
| v37-SBFM-052126 | accel (ACCELERATING 0.97, furious speed), re-entry (buy 2 today) | - | - | 1.2400 | 1.2400 (+7900 ms) | 1.1780 | 7684 | 1136 | 1 | giveback 1.2400 | 1.2500 | +$0.00 | F3, F6, F7 |
| v37-SBFM-052136 | accel (ACCELERATING 0.59, furious speed), re-entry (buy 3 today) | - | - | 1.2900 | 1.2800 (+1574 ms) | 1.2319 | 1351 | 919 | 1 | giveback 1.2800 | 1.3000 | -$14.19 | F3, F6, F7 |
| v37-MEDS-054351 | normal starter (a tenth of a position) | - | - | 4.1300 | 4.0700 (+222 ms) | 3.9900 | 2 | 1853 | 1 | giveback 4.0700 | 4.1400 | -$5.04 | F7 |
| v36-DKI-062022 | normal starter (a tenth of a full position), re-entry (buy 5 today) | - | 1679 | 4.6872 | 4.6500 (+8306 ms) | 4.4900 | 32120 | 4204 | 3 | stop 4.4700 | 4.7000 | -$13.25 | F4 |
| v36b-DKI-062023 | normal starter (a tenth of a full position), re-entry (buy 5 today) | - | - | 4.6909 | 4.6500 (+7921 ms) | 4.5590 | 30793 | 1121 | 1 | stop 4.5300 | 4.7000 | -$5.31 | - |
| v36b-DKI-063952 | normal starter (a tenth of a full position), re-entry (buy 6 today) | - | - | 4.8178 | 4.8500 (+33030 ms) | 4.6657 | 225576 | 1802 | 1 | stop 4.6400 | 4.8800 | -$5.69 | - |
| v36-DKI-063953 | normal starter (a tenth of a full position), re-entry (buy 6 today) | - | 3563 | 4.8148 | 4.8500 (+32374 ms) | 4.5300 | 242968 | 4334 | 3 | stop 4.5452 | 4.8800 | -$12.40 | F4 |
| v36b-DKI-064647 | normal starter (a tenth of a full position), re-entry (buy 7 today), + 1 add(s) | - | - | 5.1047 | 5.2200 (+31448 ms) | 4.9900 | 200174 | 993 | 1 | stop 5.2700 | 5.3700 | -$2.06 | - |
| v36-DKI-064651 | normal starter (a tenth of a full position), re-entry (buy 7 today), + 1 add(s) | - | - | 5.0965 | 5.2200 (+27197 ms) | 4.9900 | 195926 | 2428 | 2 | stop 5.2737 | 5.3700 | -$1.69 | F4 |
| v36-DKI-065438 | normal starter (a tenth of a full position), re-entry (buy 8 today), + 2 add(s) | - | - | 5.5700 | 5.5600 (+3416 ms) | 5.4900 | 184661 | 4499 | 3 | stop 6.9092 | 7.4400 | +$630.56 | F4, F5 |
| v36b-DKI-065441 | normal starter (a tenth of a full position), re-entry (buy 8 today), + 2 add(s) | - | - | 5.5732 | 5.5600 (+5 ms) | 5.4900 | 181254 | 7303 | 4 | stop 6.8350 | 7.4400 | +$218.21 | F4, F5 |
| v37-DKI-065736 | normal starter (a tenth of a position), re-entry (buy 5 today) | - | - | 7.3800 | 7.3400 (+220 ms) | 6.9900 | 4 | 12147 | 5 | giveback 6.9470 | 7.3900 | -$29.88 | F4, F7 |
| v36-MOBX-070133 | furious (FULL POSITION at once) | +2.1% | 1160 | 1.4300 | 1.4600 (+17428 ms) | 1.3400 | 96542 | 5432 | 5 | 10s 1.4688 | 1.5400 | +$118.46 | F3, F4 |
| v36b-MOBX-070134 | furious (FULL POSITION at once) | +2.1% | 1319 | 1.4300 | 1.4600 (+17268 ms) | 1.3871 | 96383 | 1179 | 1 | 10s 1.5000 | 1.5400 | +$60.06 | F3 |
| v37-MOBX-070149 | accel (ACCELERATING 1.77, furious speed) | - | - | 1.4600 | 1.4600 (+2028 ms) | 1.4162 | 1814 | 2181 | 2 | giveback 1.4600 | 1.4700 | +$0.00 | F3, F4, F7 |
| v36b-FLYE-072207 | furious (FULL POSITION at once) | +7.1% | 1001 | 1.6400 | 1.6600 (+900 ms) | 1.6005 | 6179 | 4672 | 3 | stop 1.5674 | 1.7502 | -$71.54 | F3, F4, F8 |
| v36-FLYE-072208 | furious (FULL POSITION at once) | +7.1% | 1804 | 1.6399 | 1.6600 (+99 ms) | 1.5399 | 9237 | 8861 | 5 | stop 1.5333 | 1.7502 | -$197.07 | F4, F8 |
| v36-FLYE-072236 | furious (FULL POSITION at once), re-entry (buy 2 today) | +6.7% | 1745 | 1.7800 | 1.6900 (+5636 ms) | 1.6800 | 10132 | 3247 | 2 | stop 1.6732 | 1.7800 | -$178.23 | F4, F6, F9 |
| v36b-FLYE-072236 | furious (FULL POSITION at once), re-entry (buy 2 today) | +6.7% | 1807 | 1.7800 | 1.6900 (+5570 ms) | 1.7072 | 5354 | 1918 | 1 | stop 1.6900 | 1.7800 | -$72.81 | F3, F9 |
| v36-FLYE-072253 | furious (FULL POSITION at once), re-entry (buy 3 today) | +6.5% | 1167 | 1.7700 | 1.7200 (+813 ms) | 1.6700 | 46301 | 1877 | 1 | giveback 2.0800 | 2.2100 | +$733.46 | F6 |
| v36b-FLYE-072253 | furious (FULL POSITION at once), re-entry (buy 3 today) | +6.5% | 1269 | 1.8000 | 1.7200 (+701 ms) | 1.7363 | 702 | 5033 | 4 | stop 1.6999 | 1.8100 | -$89.42 | F2, F3, F4, F6 |
| v36b-FLYE-072316 | furious (FULL POSITION at once), re-entry (buy 4 today) | +1.1% | 1302 | 1.8300 | 1.7600 (+1196 ms) | 1.7654 | 1198 | 861 | 1 | stop 1.7500 | 1.8300 | -$65.84 | F2, F3, F9 |
| v36b-FLYE-072323 | furious (FULL POSITION at once), re-entry (buy 5 today) | +2.8% | 857 | 1.8700 | 1.8800 (+3 ms) | 1.7848 | 15675 | 1853 | 1 | giveback 2.0800 | 2.2100 | +$175.98 | F3, F6 |
| v37-FLYE-072330 | accel (ACCELERATING 0.45, furious speed) | - | - | 1.9000 | 1.8800 (+370 ms) | 1.8000 | 79 | 6476 | 6 | giveback 1.8832 | 1.9200 | -$35.86 | F4, F7 |
| v36-FLYE-072342 | furious (FULL POSITION at once), re-entry (buy 4 today) | +2.8% | 1247 | 2.0100 | 2.0800 (+13069 ms) | 1.9899 | 13734 | 4282 | 2 | stop 2.0251 | 2.1000 | +$32.77 | F3, F4, F6 |
| v36b-FLYE-072413 | furious (FULL POSITION at once), re-entry (buy 6 today) | +13.4% | 1232 | 2.3300 | 2.2200 (+10 ms) | 2.2300 | 108 | 8305 | 6 | stop 2.2199 | 2.3300 | -$48.10 | F2, F4, F9 |
| v36-FLYE-072413 | furious (FULL POSITION at once), re-entry (buy 5 today) | +13.4% | 1319 | 2.3300 | 2.2200 (+5 ms) | 2.2300 | 8 | 2546 | 2 | stop 2.2157 | 2.3300 | -$218.62 | F2, F4, F9 |
| v36b-FLYE-072556 | furious (FULL POSITION at once), re-entry (buy 7 today) | +20.8% | 1399 | 2.7300 | 2.6700 (+24 ms) | 2.7027 | 30 | 5683 | 4 | stop 2.5425 | 2.7500 | -$101.46 | F2, F3, F4, F5 |
| v37-FLYE-072556 | accel (ACCELERATING 0.40, furious speed), re-entry (buy 2 today) | - | - | 2.9100 | 2.6400 (+0 ms) | 2.8100 | 7 | 4468 | 2 | stop 2.5065 | 2.9100 | -$261.07 | F2, F4, F5, F9 |
| v36-FLYE-072557 | furious (FULL POSITION at once), re-entry (buy 6 today) | +20.8% | 2056 | 2.7500 | 2.5700 (+97 ms) | 2.6680 | 103 | 1921 | 1 | stop 2.5700 | 2.7500 | -$95.40 | F2, F3, F5, F9 |
| v36-FLYE-074043 | normal starter (a tenth of a full position), re-entry (buy 7 today) | - | 4124 | 3.3619 | 3.3600 (+6789 ms) | 2.9900 | 35954 | 1676 | 1 | stop 3.0200 | 3.6000 | -$12.31 | F8 |
| v36b-FLYE-074045 | normal starter (a tenth of a full position), re-entry (buy 8 today) | - | - | 3.3887 | 3.3600 (+4579 ms) | 3.2592 | 6223 | 1143 | 1 | stop 3.3000 | 3.4700 | -$4.08 | - |
| v36b-CHR-080209 | furious (FULL POSITION at once) | +7.9% | 1173 | 1.8900 | 1.9000 (+175 ms) | 1.8430 | 22872 | 1141 | 1 | stop 1.7900 | 2.0600 | -$83.60 | F3, F5, F8 |
| v36-CHR-080210 | furious (FULL POSITION at once) | +7.9% | 1343 | 1.9200 | 1.9000 (+9 ms) | 1.8200 | 22871 | 1130 | 1 | stop 1.7700 | 2.0600 | -$347.85 | F8 |
| v37-CHR-080218 | accel (ACCELERATING 0.54, furious speed) | - | - | 2.0600 | 2.0400 (+0 ms) | 1.9900 | 2265 | 1135 | 1 | stop 1.9900 | 2.0600 | -$138.81 | F9 |
| v36-BIAF-080644 | furious (FULL POSITION at once) | -0.7% | 903 | 7.4900 | 6.8200 (+295 ms) | 7.3900 | 8 | 6129 | 3 | stop 6.8307 | 7.4900 | -$382.37 | F1, F2, F4, F5, F9 |
| v36b-BIAF-080645 | furious (FULL POSITION at once) | -0.7% | 1421 | 7.0900 | 6.8200 (+4 ms) | 7.0191 | 4 | 3212 | 3 | stop 6.7964 | 7.0900 | -$61.65 | F1, F2, F3, F4, F5, F9 |
| v36-BIAF-080940 | furious (FULL POSITION at once), re-entry (buy 2 today) | +4.9% | 1558 | 7.9000 | 7.8700 (+13 ms) | 7.8000 | 6771 | 2395 | 2 | stop 7.8500 | 8.0500 | -$25.85 | F4, F8 |
| v36b-BIAF-080940 | furious (FULL POSITION at once), re-entry (buy 2 today) | +4.9% | 1695 | 7.9700 | 7.9200 (+3 ms) | 7.8700 | 6202 | 871 | 1 | stop 7.7800 | 8.0500 | -$2.85 | F5 |
| v37-BIAF-080941 | accel (ACCELERATING 0.34, furious speed) | - | - | 7.9900 | 7.9100 (+219 ms) | 7.8900 | 1 | 6882 | 5 | giveback 7.9075 | 8.0000 | -$46.67 | F4, F7 |
| v37-BIAF-080951 | normal starter (a tenth of a position), re-entry (buy 2 today) | - | - | 8.1900 | 8.0500 (+155 ms) | 7.9900 | 438 | 2937 | 2 | stop 7.9113 | 8.1900 | -$17.00 | F4, F5, F6, F9 |
| v36-BIAF-080951 | furious (FULL POSITION at once), re-entry (buy 3 today) | +1.9% | 1368 | 8.1800 | 8.0500 (+79 ms) | 8.0800 | 3 | 2203 | 1 | stop 7.9500 | 8.1800 | -$107.64 | F2, F4, F5, F6, F9 |
| v36b-BIAF-080951 | furious (FULL POSITION at once), re-entry (buy 3 today) | +1.9% | 1436 | 8.1900 | 8.0500 (+2 ms) | 8.0900 | 3 | 13128 | 7 | stop 7.8459 | 8.1900 | -$11.01 | F2, F4, F5, F6, F9 |
| v36-KAPA-093449 | furious (FULL POSITION at once) | +0.0% | 1181 | 1.1600 | 1.1400 (+2839 ms) | 1.0600 | 85436 | 2795 | 1 | 10s 1.1000 | 1.1800 | -$225.00 | F1, F4 |
| v36b-KAPA-093451 | furious (FULL POSITION at once) | +0.0% | 3496 | 1.1600 | 1.1400 (+511 ms) | 1.0864 | 84716 | 10092 | 1 | 10s 1.1000 | 1.1600 | -$83.16 | F1, F3, F4, F9 |
| v36-KAPA-093736 | furious (FULL POSITION at once), re-entry (buy 2 today) | +1.7% | 1724 | 1.2400 | 1.2300 (+2 ms) | 1.1400 | 20317 | 3800 | 1 | stop 1.1100 | 1.2500 | -$63.44 | F4 |
| v36b-KAPA-093737 | furious (FULL POSITION at once), re-entry (buy 2 today) | +1.7% | 2817 | 1.2400 | 1.2200 (+99 ms) | 1.1640 | 19230 | 3015 | 1 | stop 1.1100 | 1.2400 | -$106.99 | F3, F4, F5, F9 |

## Data gaps - what the logs do not show

- **The quote at the decision moment.** No line logs the bid x ask when a buy is decided. Quotes exist only where a line happens to print them: IGNORED prints (at most one per strategy per symbol per 30 s), "the market B x A is at the stop", SELL limit lines (bid only, premarket), TRIGGER NOT CONFIRMED and BUY SHORT reasons (ask only). 32 of 74 trades have no logged bid within 2000 ms after the fill.
- **Every print.** The log has no tape: only the prints a decision or an IGNORED line names (FURIOUS, ENTER print, EXIT trigger print, WHY-NOT px, SKIP, IGNORED). The peak in the EXIT line is the bot's own s.peak, not a print list; for v36/v36b starters it starts at max(decision print, fill), so a peak equal to the decision print may never have traded after the fill.
- **v37's decision time, speed-at-decision and 5-second move.** v37 logs no line before it buys (no FURIOUS), so its decision -> fill latency is unknown and F1 cannot be judged for it (18 v37 trades; 0 had a v36/v36b FURIOUS line with a 5s move <= 0 within 2 s before the v37 fill - context only, recorded as five_sec_move_proxy_from_sibling).
- **Decision time for v36/v36b normal starters** is logged only when the "STARTER sized for its stop" line fires; 28 of 74 trades have no decision timestamp at all.
- **Buy orders.** Order sends, order ids, each order's limit and partial fills are not logged. A limit appears only in a BUY SHORT line (the last order's "filled at up to X (the ask + 0.20)"); a buy that filled in full prints no BUY SHORT, so its limit is null and only the rule from the code is recorded. The fill time is the ENTER line's time (after the broker confirmed the average price), not the exchange fill time.
- **Sell orders.** Each SELL line is one order sent; its fill size and price are not logged - only the next SELL's smaller quantity and the EXIT's average price. Cancels say only "cancelled 1 working order(s)". 4 trade(s) sold at MARKET (9:30-4:00): those lines carry no bid.
- **Stops in between.** Stop moves are logged only by "held past $X" and ADD lines; the trail stop, the 10-second leash and v37's giveback line are not logged until they fire (the EXIT line's stop field is s.stop, not the trail).
- **Exit trigger print time.** The EXIT line gives the trigger print's age at the sale's start; its time is approximated as (selling line - age).
- **Only the trade windows were fetched.** raw/<SYM>.jsonl holds the lines from 90-100 s before each trade's first logged decision (or its fill when no decision is logged) to 30 s after its EXIT, merged per symbol; lines between windows are not in the files. Render returns each log line with its own ingestion time; parse.py uses the bot's asctime (ms) instead.
- **BOOK row ownership.** BOOK table rows carry no strategy tag (the header line does, but it does not name the symbol); rows are attached to a trade only when shares and entry match.

## Parsing problems

- none: every strategy line matched a known r34.py format, every trade has ENTER and EXIT, and every EXIT's P/L equals (price - entry) x shares to the cent.
