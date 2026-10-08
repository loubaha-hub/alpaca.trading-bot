# The playbook as numbers - the rule sheet for the new strategy

Draft 1, 2026-10-06. Built from `memory/playbook.md` (the owner's words).
Numbers marked **(?)** are starting guesses for the owner to correct. Status:
**built** (in r34.py), **partly**, **tested** (replay/research), **to build**.

## 1. Where to look - the screen, every few seconds, the whole market
| Rule | Number | Status |
|---|---|---|
| Price | $1-$20 | built |
| Float | 20M shares or less | partly (v35 only); floats.csv |
| Relative volume | 3x the stock's normal for the time of day or more (?), and rising | to build (v31 has "rising" only) |
| Liquidity | at least $250k traded a minute (?) - "stay away from thin, period" | tested: the biggest single gain in rip_test |
| Float rotation | shares traded today / float - ranks the list, "where everybody is" | tested: picks the runners, not a trigger |
| Reverse split | **the owner, 10-06: the day the split takes effect** (one or two days at most) - it runs like crazy that day, then fizzles; older splits count for nothing. Today: top of the list; yesterday: a smaller lift | to build (a list of splits taking effect today, each morning) |
| News today | **the owner, 10-06: very important but NOT required** - 10-20% of runners have none ("somebody knows something"). A boost on the list | to build (Webull filings; a news feed) |
| Up on the day | at least 10% | built (the scanner's GAIN_FROM_OPEN) |
| Hard to borrow, no shelf | rank the list higher, not required (?) | to build (Alpaca borrow flag; filings) |
| Chinese stocks | allowed; their own exit (section 6) | to build (company country) |

## 2. Which stock - the one ripping NOW, where the crowd is
- The owner, 10-06: "the key element is where the crowd is" - people buying
  and selling. Usually the leader of the day, not always: the crowd migrates
  to a new stock, "and that's where we need to be".
- The crowd, measured: each stock's share of all the dollars traded on the
  list in the last 5 minutes (?). A new stock whose share jumps while the old
  leader's falls = the crowd moving. Proposed: watch the top 2; a stock must
  hold the top spot 2 minutes (?) to count as the new leader (on 10-05 the top
  spot flipped back and forth when two stocks shared the crowd).
- 10-05 premarket, by that measure: SAIQ/SDEV 4:05-6:45, VEEA 5:06 and
  6:52-7:31, ALEC 7:26-7:51 (at $2.52; it reached $3.20 by 7:51 - the bot
  bought it at 2.51 at 7:24 and was out in 14 seconds), APUS 8:02, MI 8:15 at
  $3.40 (the old rule had banned it at 8:09; high later $10.42), AMOD 9:01.
- Rank by the last 5 minutes (?): price move and volume against the stock's
  normal. Not the day's top gainer - a slowed leader loses to a new runner.
- Status: tested roughly - MI showed at 8:12am on 10-05, 3 minutes after the
  old rule banned it.

## 3. The rip - ready to buy
| Rule | Number | Status |
|---|---|---|
| Two green 1-minute candles | together +5% or more (owner: 5-10%); or one minute +2-5% | tested |
| Volume | each candle 3x the 5 minutes before or more; rising bar to bar | tested |
| Tape (time and sales against the bid/ask - no Level 2 needed) | **the owner, 10-06: at least 60% green (at the ask), no more than 40% red (at the bid)** - "good enough" as a number; real life is less consistent. Never buy into mostly selling (on 10-05 all 7 such buys lost) | to build: quotes must stream for the leaders BEFORE the buy (today only for names held) |
| No high wick | upper wick no more than half the candle (?) | to build |

## 4. The entry
- The pattern: after the rip, the first red; buy 1c over the red's open as
  the next candle goes green; stop at the red's low. **Built** (v31, v35).
- Or through the high of the day / a half-dollar level, green candles stacking
  on rising volume. **Partly** (v31's new-high entry).
- Room: the next resistance (half-dollar level, the day's earlier highs)
  at least 2x the risk away. **Partly** (v35 checks yesterday's high only).
- Level 2: no big ask in the way; a big ask being eaten fast = go; spoofed
  asks vanish. **Later** - not in the owner's data now; Webull's API has it
  (10 levels pulled for MI). Until then: time and sales plus the bid/ask.
- Fast reload: re-price every 0.4s. **Built, on.** On a real runner pay up to
  5-10% over the trigger. **Built, off** (FAST_BUY_SPEED_CAP).
- Front entries: the first and second entries of each run.

## 5. Size
- About $5,000 a trade (?), at most 2 at once (?). Later: add as it runs.

## 6. The exit
| Rule | Number | Status |
|---|---|---|
| A short burst of red prints while the stock stays strong | hold through it - the price dips a tiny bit and picks up again; not an exit by itself | to build |
| Short leash at first | out on a red 10-second candle closing under the one before (?) or a bar flickering green/red | to build (needs 10-second candles from the prints) |
| Longer leash once it has run | from +10% (?): trail 2 typical one-minute ranges (?) | partly (v35's long leash) |
| At a resistance / half-dollar level | hesitates there: out; bolts through: stay | to build |
| Chinese stocks | sell into strength: out on the first 10-second candle that fails to make a new high (?) | to build |
| Hard floor | the red's low | built |

## 7. Coming back in
- The same stock can run two or three times a day. Back in when the price is
  at the high of the day with green bars lining up on rising volume - a
  trigger, never a timer. On skittish volume, wait for a confirmation (above
  a resistance, or the top of the hour / the open). No ban for running.
  **Partly** (v31/v35 new-high re-entries; the no-chase ban still in v31).

## 8. Execution (from the live logs)
- Fast reload with confirmed cancels (no overfill). **Built.**
- Every missed buy logged. **Built.**
- Quote check's half cent (RETO, BBD, NVAX). **Built, off** (CONFIRM_TOLERANCE).
- No restarts during trading; two copies never trading at once. **To build.**

## 9. How it is judged
- Win rate against the owner's 60-65%; average win at least ~2x the average
  loss; every day, never one stock; live paper results outrank replays.
