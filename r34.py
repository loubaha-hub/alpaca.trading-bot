"""
Trading engine - three strategies, one process, one market-data connection.

WHY ONE PROCESS
  Alpaca limits websocket connections per USER (login), not per paper account.
  The observed limit on this account is 1. Three separate services therefore
  cannot run at once - two of them sit in `connection limit exceeded` forever.
  One process opens the single connection, subscribes to the union of every
  strategy's symbols, and hands each tick to three independent strategy engines.

WHAT IS SHARED AND WHAT IS NOT
  Shared : the websocket, the market scan, the snapshot client.
  NOT shared: accounts, keys, positions, cash, P&L, rules, decisions.
  Each strategy holds its own TradingClient pointed at its own paper account, so
  orders never contend - execution goes over REST, not the socket.

THE ONE REAL RISK, AND HOW IT IS HANDLED
  Three strategies share one event loop. A blocking HTTP call inside one would
  freeze the other two's tick handling. So:
    * every broker/data call runs off the loop via asyncio.to_thread
    * each strategy drains its OWN tick queue in its OWN task
  One strategy stuck in an order chase falls behind by itself. The others do not
  notice.

ENVIRONMENT VARIABLES
  ALPACA_API_KEY / ALPACA_SECRET_KEY   v31's account (required)
  V32_API_KEY    / V32_SECRET_KEY      v32's account (optional - omit to skip)
  V33_API_KEY    / V33_SECRET_KEY      v34's account (v34 took over v33's)
  V35_API_KEY    / V35_SECRET_KEY      v35's account (optional - omit to skip)
  ALPACA_PAPER   "1"/"true" for paper (default), "0"/"false" for live
  ALPACA_FEED    "sip" (default) or "iex"
  ORPHAN_MODE    "adopt" (default) or "flatten" - leave unset
  FLOAT_FILE     v31's float list (default floats.csv next to this file)
  TAPE_QUOTES    "positions" (default), "all" or "off" - quotes for v31's
                 tape log (see TAPE_QUOTES below)
"""

import asyncio
import csv
import logging
import os
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (GetAssetsRequest, GetOrdersRequest,
                                     LimitOrderRequest)
from alpaca.trading.enums import (AssetStatus, OrderSide, QueryOrderStatus,
                                  TimeInForce)
from alpaca.data.enums import DataFeed

# ----------------------------------------------------------------------------
# SHARED CONFIGURATION
# ----------------------------------------------------------------------------

ET = ZoneInfo("America/New_York")           # the ONE clock. Never local time.

SESSION = ((4, 0), (20, 0))                 # the session WE trade, ET
FLATTEN_AT = (19, 0)                        # start closing at 7:00pm ET - a full
                                            # hour to work out of thin after-hours
                                            # books, flat well before 8:00pm

# --- scanner (shared by all three) -------------------------------------------
PRICE_MIN = 1.00
PRICE_MAX = 20.00
GAIN_FROM_OPEN = 0.10                       # up 10% from the day's reference
MAX_BAR_AGE_DAYS = 5                        # ignore names that have not traded
SCAN_SECONDS = 8
MAX_WATCH = 200                             # symbols on the stream

# --- execution (shared) ------------------------------------------------------
BUY_CHASE_CAP = 0.02                        # buys capped 2% above the ask
CHASE_ATTEMPTS = 8
CHASE_PAUSE = 0.35
# BUYING A RUNNER - RELOAD THE LIMIT FAST (the owner, 2026-10-05: "put a new
# order and a new order until it gets, especially when the stock is flying").
# The old chase left each limit working about 2 seconds before re-pricing it;
# on a stock moving 5% a minute the ask is gone by then, and a person on hot
# keys reloads faster than that. With FAST_BUY each limit works FAST_BUY_WAIT
# seconds, is cancelled - the cancel CONFIRMED before the next one goes out,
# so two orders are never live at once - and is re-priced off the new ask,
# for up to FAST_BUY_MAX_SEC or FAST_BUY_TRIES orders. Never over the cap
# above the trigger. About 4 broker requests an order; Alpaca allows about
# 200 a minute per account.
FAST_BUY = True
FAST_BUY_WAIT = 0.4
FAST_BUY_MAX_SEC = 6.0
FAST_BUY_TRIES = 12
FAST_BUY_OVER_ASK = 0.002                   # the limit: this far over the ask, as before
# PAYING UP ON A REAL RUNNER: "sometimes I'm almost half a point above what I
# bought" on a $5-10 stock that is flying. With FAST_BUY_SPEED_CAP set, the
# ceiling over the trigger is this many of the stock's typical one-minute
# ranges (ABR), kept between BUY_CHASE_CAP and FAST_BUY_CAP_MAX. 0 = off:
# paying up is safe only on a stock with real volume behind it, and that guard
# belongs to the playbook strategy still to be built (memory/playbook.md).
FAST_BUY_SPEED_CAP = 0.0
FAST_BUY_CAP_MAX = 0.10
# THE QUOTE CHECK'S TOLERANCE. CONFIRM_ENTRY_WITH_QUOTE refuses a buy when the
# ask is under the trigger - on 2026-10-05 by half a cent: RETO at 4:06am
# (ask 1.99, trigger 1.9993; 9 refusals in 4 seconds, a top-2 runner a minute
# later), BBD (4.30 vs 4.305), NVAX (11.79 vs 11.795). The ask may sit this
# many dollars under the trigger. 0 = off, as before.
CONFIRM_TOLERANCE = 0.0
MIN_TRADE_DOLLARS = 100

# --- risk (shared) -----------------------------------------------------------
HALT_LADDER = [0.10, 0.05, 0.025]           # then a full stop
RISK_CHECK_SECONDS = 5                      # the halt runs on a CLOCK, not ticks

# --- position size limits ----------------------------------------------------
# "Risk 1% of equity" is only 1% if the stop holds to the cent. On 2026-09-30 a
# 4-cent stop on a $5.65 stock produced 7,688 shares - $43,437 on a $28,996
# account, 1.5x leverage. The stock then moved 23 cents instead of 4 and the
# account lost 15% in one trade, jumping clean over its own -10% halt before the
# halt could be checked. These two numbers make that arithmetically impossible.
# The file name and this string are changed together, every single time. The
# log then answers "which code is actually running?" without anyone guessing
# from line numbers or from behaviour that only shows up once a trade is on.
VERSION = "v31-r34.3"

# WHERE THE DAY'S HALT BASELINE COMES FROM.
#   "last_equity" - equity at the PREVIOUS session's close, read from the broker.
#                   Restart-proof: the halt measures the whole day no matter how
#                   many times the process restarts. This is the correct setting.
#   "boot"        - equity at the moment the process started (the old behaviour).
#                   On 2026-09-30 a midday restart re-anchored the baseline from
#                   28,995 to 23,954, so an account already 17.4% down for the
#                   day read as 0% down and the halt sat 10% below that.
# Set DAY_BASELINE=boot in the environment only to deliberately give the bot a
# fresh 10% of room after a bad morning. Remove it again the same day.
#
# BEFORE 4:00AM ET (AND ALL WEEKEND) "last_equity" IS NOT USED.
# The day rolls at midnight ET, and at midnight Alpaca's last_equity is still
# the close of the day BEFORE yesterday - it moves some hours later. On
# 2026-10-01 v31 rolled against Tuesday's 28,772 with 22,670 in the account,
# read -21%, and halted at 12:00am; on 10-02 it rolled against Wednesday's
# 22,649 with 20,264, read -10.5%, and halted again. Both mornings v31 never
# traded from 4am - only a restart after 7am un-stuck it - and each false halt
# also tightened the next day's ladder. Nothing trades between midnight and
# 4am, so the account's equity at that moment IS the day's starting value.
# CONFIRM A BREAKOUT AGAINST THE QUOTE BEFORE BUYING.
# On 2026-09-30 IBRX triggered an entry whose level was 9.8850 while the candle
# that closed at 12:51 never traded above 9.8700 - and the fill came back at
# 9.8600, BELOW the level that was supposed to be required. A fill below the
# trigger is the signature of firing on a print that is not the real market:
# an odd lot, a derivatively-priced trade, a prior-reference-price print. Those
# never touch a chart's high but they do arrive on the trade websocket.
# With this on, the level must also be backed by the ASK before any order goes
# out. It costs one snapshot call on the entry path and nothing otherwise.
# WHICH PRINTS ARE ALLOWED TO MOVE THE BOT.
# CONFIRMED on 2026-09-30 at 2:29pm ET. MNKD logged:
#     triggering print 4.0200 x 12  cond ['@', 'I']
# 'I' is ODD LOT. A TWELVE-SHARE odd lot at 4.0200 fired the entry, the real
# market was lower, and the position was stopped out one second later for
# -$78.97. Odd lots do not update the consolidated last/high/low - which is
# exactly why the chart never showed the price the bot reacted to, and why
# IBRX earlier filled BELOW its own trigger.
# A print carrying any of these conditions is not the market: it does not set
# the price, does not raise the day high, does not feed the speed baseline and
# cannot trigger anything. 'T' and 'U' (extended hours) are deliberately NOT
# here - this bot trades 4am-8pm and those are its normal prints.
NON_QUALIFYING_CONDS = frozenset((
    "I",    # odd lot
    "W",    # average price
    "B",    # average price
    "4",    # derivatively priced
    "7",    # qualified contingent
    "9",    # corrected consolidated close
    "C",    # cash
    "G",    # bunched sold
    "H",    # price variation
    "M",    # market centre official close
    "N",    # next day
    "P",    # prior reference price
    "Q",    # market centre official open
    "R",    # seller
    "V",    # contingent
    "Z",    # sold out of sequence
))


def qualifies(conds) -> bool:
    """True when this print is a real market trade we may act on."""
    if not conds:
        return True
    return not any(c in NON_QUALIFYING_CONDS for c in conds)


CONFIRM_ENTRY_WITH_QUOTE = os.getenv(
    "CONFIRM_ENTRY_WITH_QUOTE", "1").strip().lower() not in ("0", "false", "no")

DAY_BASELINE = os.getenv("DAY_BASELINE", "last_equity").strip().lower()

MAX_POSITION_PCT = 0.25                     # a starter is never >25% of equity
MIN_STOP_PCT = 0.01                         # a stop nearer than 1% counts as 1%
                                            # FOR SIZING *AND* FOR THE STOP ITSELF.
                                            # On 2026-09-30 IBRX entered at 9.86 with
                                            # the red bar's low at 9.85 - a 1-CENT stop.
                                            # It was bought and stopped out one second
                                            # later for -$6.06. Sizing used the 1% floor;
                                            # the stop price did not, so the two
                                            # disagreed and every tight bar became an
                                            # instant round trip.
MAX_EXPOSURE_PCT = 0.95                     # NEVER borrow. Total stock held can
                                            # never exceed the account's own
                                            # equity - on 2026-09-30 the adds
                                            # built $27,281 of SDEV on a $24,126
                                            # account, 113%, on margin.

# --- dead-tape exit ----------------------------------------------------------
# Every trading rule in this engine fires inside evaluate(), and evaluate() only
# runs when a trade prints. A stock that stops trading altogether therefore gets
# HELD - the stall rule cannot see it, because the stall counter is driven by
# bars and a silent stock sends no bars. This is the one exit that runs on the
# clock instead of on ticks, so silence itself becomes a reason to get out.
DEAD_MINUTES = 10                           # no print for this long -> close it
DEAD_CHECK_SECONDS = 30

# --- reconciliation (shared) -------------------------------------------------
# A strategy's daily halt can be turned off entirely with 0. v32 and v33 run
# with no halt on purpose: the question being tested is whether the design
# depletes an account or grows it, and a halt would end the experiment early
# and hide the answer.
HALT_PCT_OVERRIDE = {
    "v32": float(os.getenv("V32_HALT_PCT", "0") or 0) / 100.0,
    "v33": float(os.getenv("V33_HALT_PCT", "0") or 0) / 100.0,
    "v34": float(os.getenv("V34_HALT_PCT", "0") or 0) / 100.0,
}

ORPHAN_MODE = os.environ.get("ORPHAN_MODE", "adopt").strip().lower()
ORPHAN_FLATTEN_WINDOW = ((4, 0), (4, 10))
RECONCILE_SECONDS = 60
EQUITY_TTL = 5

# --- tick fan-out ------------------------------------------------------------
QUEUE_MAX = 20000                           # per strategy; drops oldest if full

# --- subscription batching ---------------------------------------------------
# Every subscribe call makes the SDK restart the socket and re-send the whole
# list. With the scanner finding a new name every 8 seconds that means a
# reconnect every 8 seconds, a gap in ticks each time, and a real chance of
# colliding with our own not-yet-released connection. So new names are collected
# and sent in ONE batch, at most this often. A position we hold jumps the queue.
SUBSCRIBE_INTERVAL = 30

# --- v31 ---------------------------------------------------------------------
V31_MAX_POSITIONS = 3
V31_LEADER_CAP = 0.25
V31_RISK_PER_TRADE = 0.01
V31_ENTRY_TICK = 0.01
V31_TRADE_WINDOW = 50
V31_SPEED_ADD_MULT = 2.0
# ADDS ARE OFF. An add tops the position up to the 25% cap but leaves the
# stop where the starter's 1% risk put it, so every add raised the risk past
# 1%. Replayed over 2026-09-30..10-02 (59 trades), adds made every version
# worse: r25 -$1,729 with them, -$862 without; the biggest losers (CHGA,
# AHG, PMAX) were all added to on the way down to their stops.
V31_ADDS = False
# RE-ENTER A RUNNER AT EVERY NEW HIGH OF THE DAY. Once a name has been traded
# today, a print V31_HOD_BREAK_CENTS above the day's high buys it again - no
# fresh green/red setup needed. The old high is then support underneath the
# position instead of resistance overhead. The 2026-09-28..10-02 replays made
# +$4,880 on 50%+ runners and lost on everything else, yet entered each runner
# once: AMOD (+308%) was stopped out at 7:05am and never re-entered.
# The entry stop sits V31_HOD_STOP_ABR typical one-minute ranges (ABR) under
# the old high, never nearer than MIN_STOP_PCT.
#
# OFF BY DEFAULT - the replay says it loses. Over 2026-09-28..10-02 it added
# 75-81 re-entries that won 37% of the time but lost net: r26 -$439, with
# re-entry -$1,868 (3 ABR stop, no limit) to -$3,574; no stop width or cap
# tried came out ahead. It does find runners (AMOD +$1,111 held 8:54-9:31),
# but six other AMOD re-entries were shaken out within minutes. The replay
# draws each minute bar as open-low-high-close, so a buy at a new high always
# meets that bar's drop to its close at once - likely unfair to exactly this
# entry. Settle it with tick data before switching it on.
#
# ON IN r29. Behind the no-chase rule and the rising-volume rule (which apply
# to re-entries too) it made 7 re-entries over the same five days, 4 up, and
# +$196 net (+$2,971 vs +$2,775 without). Stricter volume for re-entries
# (2x, 3x, 5x) did worse (+$2,441 to +$2,676), and letting re-entries past
# the rest-of-day cool-off did worse too (+$2,359, 17 re-entries). Seven
# trades is thin evidence - watch it live.
V31_HOD_REENTRY = True
V31_HOD_BREAK_CENTS = 0.05
V31_HOD_STOP_ABR = 1.0          # entry stop this many ABRs under the broken high
V31_HOD_MAX_REENTRIES = 0       # new-high re-entries per name per day; 0 = no limit
# A LONGER LEASH FOR RE-ENTRIES. A runner's normal pullbacks shook re-entries
# out within minutes. These apply only to positions opened by a new-high
# re-entry; 1.0 / the base risk mean "same as any other position".
V31_RUNNER_CRASH_MULT = 1.0     # crash line x this
V31_RUNNER_TRAIL_MULT = 1.0     # trail distance x this
V31_RUNNER_RISK = V31_RISK_PER_TRADE   # risk budget per re-entry
V31_RUNNER_FADE = True          # False: the fade exit does not apply
# DON'T CHASE. No entry when the price is already up V31_CHASE_MAX_PCT or more
# on its price V31_CHASE_MINUTES ago (the close of the last one-minute bar that
# had closed by then). Research over 2026-09-28..10-02 (replay/research/):
# the r26 replay's entries made after a 15%+ run in the previous 15 minutes
# lost -$2,415 over 28 trades (25% won); those after a 5-15% run made +$1,792.
# Across every name the bot could have bought, a 15%+ run in 15 minutes was
# followed by a 7.5% drop before a 15% rise 73% of the time. The move is
# usually over by the time it is that obvious.
#
# AND DON'T BUY THE FADE AFTER IT. With the check alone, every one of the 24
# trades that took the skipped trades' place was the SAME name bought minutes
# later on the pullback (BKYI refused at 3.10, bought at 2.88) - and they lost
# $2,248, as much as the skipped chases had. A name that rose 15% within any
# 15 minutes of the last V31_CHASE_COOLOFF_MIN minutes is left alone.
#
# Replayed over 2026-09-28..10-02 (r27: -$439, 102 trades):
#   cool-off  0 min  +$521     60 min  -$2,583    120 min  +$416
#   cool-off  4 h    +$1,714   8 h     +$1,782    rest of day  +$1,825 (47 trades)
# Short cool-offs swing with which trade happens to take the free slot; from
# 4 hours up it is steady, and the rest of the day stayed ahead with a 10- or
# 30-minute window (+$1,910 / +$2,906) and a 20% or 25% limit (+$1,154 /
# +$1,141). Only a 10% limit lost (-$368, 27 trades). The 50%+ runners kept
# most of their gain (+$2,753 vs r27's +$3,698); everything else lost $928
# instead of $4,138. Most of the gain is Tuesday 09-29, where it took the same
# 13 winning trades as r27 and skipped 12 losers.
V31_NO_CHASE = True
V31_CHASE_MINUTES = 15
V31_CHASE_MAX_PCT = 0.15
V31_CHASE_COOLOFF_MIN = 1440    # how long a spike keeps a name off-limits;
                                # 1440 = the rest of the day (never looks back
                                # before today's 4:00am), 0 = the current print only
# SIZE BY FLOAT. A name with fewer than V31_FLOAT_SMALL shares free to trade
# buys V31_FLOAT_SMALL_MULT of the normal size - the risk budget AND the 25%
# cap, so a capped starter shrinks too. The tiny floats run hardest and fall
# hardest. Research over 2026-09-28..10-02 (replay/research/): r26's trades in
# floats under 5M lost -$1,556 over 46 trades (28% won), 5M-30M made +$1,324
# over 16 (44% won); across every name the bot could have bought, under 5M
# fell 7.5% before rising 15% in 51-58% of cases, 5M-30M in 35-37%.
# Alpaca has no float data: floats come from FLOAT_FILE (CSV with columns
# symbol,float_shares; a path relative to this file), read at startup. A name
# not in it gets V31_FLOAT_UNKNOWN_MULT - full size unless that is changed.
#
# Replayed over 2026-09-28..10-02 on top of the no-chase rule it protects
# rather than earns: +$1,671 vs +$1,825 without it, the same 47 trades, but
# losses of $2,976 instead of $3,730, worst trade -$232 instead of -$296,
# worst day -$400 instead of -$450. The two rules overlap - the spikes the
# no-chase rule skips are mostly tiny floats; on r27's entries alone float
# sizing turned -$439 into +$349. Halving under 2M instead: +$1,922; under
# 10M: +$496; skipping small floats outright: +$1,515.
V31_FLOAT_SIZING = True
V31_FLOAT_SMALL = 5_000_000
V31_FLOAT_SMALL_MULT = 0.5
V31_FLOAT_UNKNOWN_MULT = 1.0
FLOAT_FILE = os.environ.get("FLOAT_FILE", "floats.csv")
# VOLUME MUST BE RISING. No entry unless the last V31_VOL_RECENT_MIN closed
# minutes traded at least V31_VOL_RISING_MIN times the per-minute pace of the
# V31_VOL_BEFORE_MIN minutes before them (minutes without a bar count as no
# volume). Research over 2026-09-28..10-02 (replay/research/), every name the
# bot could have bought, edge per trade by that ratio: under 0.5x (drying up)
# -0.12R, 0.5-2x -0.07R, 2-4x 0.00R, 4x+ +0.02R. Unknown (under 10 minutes of
# session to compare with, or no volume figures) does not block.
#
# Replayed over 2026-09-28..10-02 on top of r28 (+$1,937, 47 trades):
#   needs x1.0  +$2,038   x1.25 +$2,392   x1.5 +$2,775 (39 trades, 38% won)
#   needs x1.75 +$2,364   x2.0  +$2,110   x0.5 +$1,861 (only drying up blocked)
# x1.5 was ahead of r28 on four of the five days; with a 10-minute recent
# window +$2,119, with 60 minutes before +$2,257.
V31_VOL_RISING_MIN = 1.5        # 0 = off
# New-high re-entries (V31_HOD_REENTRY) can be held to a stricter volume
# pickup, and can be let past the no-chase cool-off - a runner that spiked
# earlier is exactly what they are for. The current print's 15%-in-15-minutes
# check still applies to them. Neutral by default.
V31_HOD_VOL_MIN = 0.0           # 0 = the same as V31_VOL_RISING_MIN
V31_HOD_SKIP_COOLOFF = False
# RUNNERS AFTER A SPIKE. The rest-of-day ban kept v31 out of most of the
# week's big runners: KNRX banned 10:18, peaked +426% at 14:01; AMOD banned
# 7:06, peaked +308% at 9:47. What lost after a spike was buying the PULLBACK
# (BKYI refused at 3.10, bought at 2.88). With this on, a spiked name stays
# closed to pullback setups for the day but may be bought on a break of its
# day high by V31_HOD_BREAK_CENTS - traded today or not - when every other
# rule passes (not up 15% in the last 15 minutes, volume rising, speed).
# Replayed over 2026-09-28..10-02: +$2,213 vs r29's +$2,971 (61 trades vs 46).
# The replay draws each bar open-low-high-close, which meets a breakout buy
# with the bar's drop at once - likely unfair to this entry. Try it live.
V31_SPIKE_HOD_OK = False
# THE DAY'S LEADERS. The top V31_LEADER_TOP names by dollar volume traded
# today (of those on the scanner's list, from the bars this strategy holds)
# may be bought on a break of the day high - traded today or not, spiked
# earlier or not - when every other rule passes. Traders crowd one to three
# names a day; this aims the breakout entry at those only. 0 = off.
# Replayed over 2026-09-28..10-02 (r29: +$2,971): top 1 +$2,784, top 2
# +$2,453, top 3 +$2,385, top 5 +$2,233; top 2 with the 5-minute speed
# +$2,412. Same caveat as V31_SPIKE_HOD_OK - try it live.
V31_LEADER_TOP = 0
# EARN YOUR WAY BACK IN (2026-10-05). The no-chase rule shut SAIQ out for the
# day at 4:18am - it then ran from ~7 to 18.37 - and each breakout it made on
# the way was itself "up 15% in 15 minutes right now". For that one minute a
# fade and a run look alike; what tells them apart is the high: a run keeps
# making new ones, on volume, and a fade does not. So a name the rule shut out
# may be bought again - by v31, v34 and v35 alike - only by proving it: one of
# the day's top V31_EARN_LEADERS names by dollar volume, breaking its highest
# closed candle by V31_HOD_BREAK_CENTS, the last closed minute's volume at
# least V31_EARN_VOL_MULT times the average of the V31_EARN_PAUSE_BARS minutes
# before it, and the ask within V31_EARN_MAX_SPREAD of the bid (SAIQ's book
# after its top: 10.80 / 11.60 - a 7% loss the moment it fills). Every other
# entry rule still applies. 0 = off.
V31_EARN_LEADERS = 1           # ON 2026-10-05 (r34.2): the day's top leader.
# Replayed 09-28..10-02 + 10-05 premarket: v31 +$462, v34 +$311 over the six
# days, gaining on both samples at x1.5 and x2 volume (x3 hardly fires).
# v35's loser re-entry through it (V35_REENTRY_EARN) only broke even: +$10.
V31_EARN_VOL_MULT = 2.0
V31_EARN_PAUSE_BARS = 5
V31_EARN_MAX_SPREAD = 0.01
# THE VOLUME SURGE, MEASURED HOW (2026-10-05, from the user's charts): a runner
# keeps trading heavily while it pulls back, so "2x the 5 minutes before"
# asks for a surge on top of a surge - SAIQ's 4:21-4:25 breakouts never got
# it. 0 = the last closed minute vs the V31_EARN_PAUSE_BARS before it (r34.2);
# 1 = the last closed minute vs the day's average minute; 2 = the minute in
# progress, scaled to a full minute, vs the day's average minute - the surge
# comes IN the breakout minute, not the one before it.
V31_EARN_VOL_MODE = 0
# THE SPREAD, AS A SHARE OF HOW FAST THE STOCK MOVES. Paying 3% to get into a
# name whose typical minute is 15% is cheap; on a 2% name it is the whole
# trade. With this set, the spread may be up to this fraction of the stock's
# typical one-minute range (its ABR) - never under V31_EARN_MAX_SPREAD, never
# over V31_EARN_SPREAD_CAP, so an empty book never qualifies. 0 = the flat 1%.
V31_EARN_SPREAD_ABR = 0.0
V31_EARN_SPREAD_CAP = 0.05
# FOLLOW A NAME PAST $20 (the user, 2026-10-05). The $1-$20 band is checked at
# every BUY, so a name found at $15 that runs to $43 could never be bought
# back - though everything held keeps its stops and exits at any price. With
# this on, a name already on the day's list stays buyable above PRICE_MAX
# under the same rules; the scanner still adds new names only at $1-$20.
V31_FOLLOW_ABOVE_MAX = False
# AN EARNED BUY HAS PROVED ITS VOLUME. v31's general rising-volume rule (the
# last 5 minutes at V31_VOL_RISING_MIN x the pace of the 30 before) refused
# SAIQ's earned breakouts at 4:22, 4:23 and 4:25 on the 2026-10-05 replay
# (x1.10, x1.38, x1.46): a name that has traded heavily for half an hour can
# never look like a surge against its own last half hour. With this on, an
# earned buy is held to the earn rule's own volume test only.
V31_EARN_SKIP_VOL_RISING = False
# LEADERS BY WHAT IS MOVING NOW. leader_rank() sums the whole day's dollar
# volume, so SAIQ's 4am volume kept it #1 for hours after it stopped moving -
# and v35 trades only the top 2. With this set, only the last N minutes count.
# 0 = the whole day.
V31_LEADER_WINDOW_MIN = 0
# EARNED BUYS IN THE PREMARKET ONLY (2026-10-05, six-day replay). Before
# 9:30 a top leader through its high has no halts ahead of it and a thin
# crowd behind it; after 9:30 the open's flood of volume makes every name
# look "earned" and most of those breakouts fail - on 09-28..10-05 every
# variant's earned buys made money before 9:30 (v31 live rule +$782 on 2,
# top-2/day-average +$1,080 on 15) and lost after it (-$212 on 4, -$946 on
# 20, mostly entry-stops at the open and in the afternoon). Minutes after
# midnight ET at which earned buys stop - 570 = 9:30. 0 = all session.
V31_EARN_UNTIL_MIN = 0
# THE SPEED AN ENTRY NEEDS. v31 used to ask only that its 100-print speed be
# above zero. Checked against the 1-minute charts (replay/research/
# speed_check.py), the bot's speed lit up on minutes that were really ripping
# 13% of the time and missed two thirds of the rips; a plain 5-minute price
# change was right 34% of the time and caught 71%. With V31_SPEED_BY_TIME the
# entry needs the price up at least V31_SPEED_MIN_MOVE on the close of the
# last bar closed V31_SPEED_MINUTES ago (falling back to the print speed when
# that price is unknown).
# Replayed over 2026-09-28..10-02 it did worse the more it asked: any rise
# +$2,857, 1% +$2,706, 2% +$2,405, 3% +$1,393, 5% +$346 (r29: +$2,971). v31
# buys the break of a RED bar's open - a pullback - which a "must be rising
# over 5 minutes" test refuses; rising volume (V31_VOL_RISING_MIN) is the
# better gate for this entry.
V31_SPEED_BY_TIME = False
V31_SPEED_MINUTES = 5
V31_SPEED_MIN_MOVE = 0.0
# JUMP OFF AT RESISTANCE. The day's high is real resistance: retested after a
# 5% pullback it failed to break by 3% within 15 minutes 59% of the time
# (replay/research/leaders_retests.py). Half and whole dollars were not
# (tops landed near them no more often than anywhere else). A position bought
# below the day's high remembers that high; once its best price has come
# within V31_RES_NEAR of it, a drop of V31_RES_GIVE_ABR typical one-minute
# ranges from that best price sells V31_RES_FRACTION of it - once. Clearing
# the high by V31_RES_NEAR turns it into support and the rule stands down.
# Nothing is ever bought back on the break: adds churned and lost before.
#
# Replayed over 2026-09-28..10-02 (r29: +$2,971) it lost every way: sell all
# within 1% of the high on a 1-ABR drop +$2,239, within 2% +$2,822, on a 2-ABR
# drop +$2,238 / +$2,893, half instead +$2,613 to +$2,746. It cut Friday's
# winners just before they broke through; the trail does this job better.
V31_RES_EXIT = False
V31_RES_NEAR = 0.01
V31_RES_GIVE_ABR = 1.0
V31_RES_FRACTION = 1.0          # 1.0 = all of it, 0.5 = half
V31_VOL_RECENT_MIN = 5
V31_VOL_BEFORE_MIN = 30
# THE TAPE - LOG ONLY, nothing trades on it yet. Every print is marked the
# moment it arrives: a BUY (green) at or above the ask, a SELL (red) at or
# below the bid, BETWEEN (white) inside the spread - against the latest quote
# when it is at most TAPE_QUOTE_MAX_AGE seconds old. Without a fresh quote the
# tick rule stands in: above the previous print a buy, below it a sell, at the
# same price whatever the last price change was. The split over the last
# minute and five minutes is logged at every v31 entry, trim and exit, and
# once a minute for each open position, so the logs can show whether it
# predicts anything before any rule uses it.
# TAPE_QUOTES (environment): "positions" (default) streams quotes for the
# names v31 holds; "all" for every watched name - far more messages; "off"
# for none, the tick rule only.
TAPE_QUOTES = os.environ.get("TAPE_QUOTES", "positions").strip().lower()
TAPE_QUOTE_MAX_AGE = 2.0
TAPE_WINDOWS = (60, 300)
# PROTECTING A GAIN - two ways, built side by side.
#  SELL HALF AT +20% (ON): the first time the price is V31_TRIM_AT above the
#    entry, sell V31_TRIM_FRACTION of the shares; the rest runs on the normal
#    exits, and with V31_TRIM_STOP_TO_ENTRY its stop moves up to the entry, so
#    the rest of a trade that reached +20% can no longer lose.
#  KEEP HALF THE GAIN (off): once a position has been up V31_KEEP_GAIN_ARM
#    from its entry, close ALL of it if the price falls back to entry +
#    V31_KEEP_GAIN x the best gain so far (0.5 = keep half of it).
# Replayed over 2026-09-28..10-02 with the no-chase rule and float sizing
# (+$1,671 with neither): sell half at +20% +$1,937; at +30% +$1,855; at +15%
# +$1,519; at +10% +$1,055 - too early cuts the winners. Keep half the gain
# +$1,718 (armed at +10% or +20%), +$1,676 armed at +30% - the trail and the
# flush almost always close a position before half its gain is gone. Both
# together +$1,961. Moving the rest's stop to the entry changed nothing here
# (the flush, at most 12% under the high, always fires above it); it is kept
# for a print that gaps through everything.
V31_KEEP_GAIN = 0.0             # 0 = off
V31_KEEP_GAIN_ARM = 0.20
V31_TRIM_FRACTION = 0.5         # 0 = off
V31_TRIM_AT = 0.20
V31_TRIM_STOP_TO_ENTRY = True
V31_SPEED_FADE_MULT = 0.25
V31_SPEED_FLUSH_MULT = 5.0
# THE FLUSH: out when the price gives back this much from its high since
# entry. A fixed 3% was ordinary noise for the $1-$5 names this scans - on
# the 2026-10-02 replay it closed winners within seconds. It now scales with
# the stock's own volatility: V31_FLUSH_ABR_MULT typical one-minute ranges
# (the ABR the trail already uses), never tighter than MIN, never wider than
# MAX. Friday's names had a typical one-minute range of 0.3%-2.4% of price,
# so this is 4% on a calm name, ~5-6% on a typical one, 12% on a wild one.
V31_FLUSH_ABR_MULT = 5.0
V31_FLUSH_MIN_PCT = 0.04
V31_FLUSH_MAX_PCT = 0.12
V31_FLUSH_DROP_PCT = 0.06                   # only until the name has an ABR
V31_FLUSH_SPEED_ABS = -1.0                  # the old speed flush, out of reach
                                            # (was -0.03); the crash guard
                                            # below does its job properly.

# THE CRASH GUARD: these names flush DOWN violently. A fall of
# V31_CRASH_ABR_MULT typical one-minute ranges from the highest print of the
# last V31_CRASH_WINDOW_SEC seconds (since entry) is not noise - out at once,
# before the slower giveback flush is reached. 3% floor, 10% ceiling.
V31_CRASH_WINDOW_SEC = 30
V31_CRASH_ABR_MULT = 3.0
V31_CRASH_MIN_PCT = 0.03
V31_CRASH_MAX_PCT = 0.10
V31_CRASH_DROP_PCT = 0.05                   # only until the name has an ABR
V31_BASELINE_MIN_SAMPLES = 1
V31_ABR_BARS = 10
V31_ABR_MIN_BARS = 3
V31_ABR_GROWTH_CAP = 1.5
V31_TRAIL_MULT = 3.0
V31_TRAIL_ARM_MULT = 1.5
V31_TRAIL_MIN_PCT = 0.02
V31_TRAIL_MAX_PCT = 0.25
V31_STALL_BARS = 6
V31_BAR_SHARES_MIN = 30_000
V31_THREE_BAR_SHARES_MIN = 100_000
V31_REBALANCE_SECONDS = 300
# THE REBALANCE IS OFF. It shares capital out by trade-speed every 5 minutes
# and on speed swings - and a name whose 100-print speed dips to zero gets a
# target of $0, so the rebalance SELLS ALL OF IT. On the 2026-10-02 replay it
# closed 5 of 12 trades, CYPH while +3.8% and SDEV before a further +12%.
# Every real exit rule (stop, flush, trail, stall, fade) still runs.
V31_REBALANCE = False
V31_SPEED_EVENT_MULT = 2.0
V31_ORPHAN_STOP_PCT = 0.08

# --- v32 and v33 -------------------------------------------------------------
# --- the simple strategies (v32, v33) ---------------------------------------
# Where the initial cut is measured FROM. A buy fills at the ASK; the tape then
# prints at the BID. On a 1-cent spread "fill minus a penny" IS the bid, so an
# unchanged market stops the position out on its next print. Measuring from the
# bid means the stock has to trade BELOW the price we could have sold at - a
# real failure to hold, which is the rule. On a winner it changes nothing: this
# stop never moves.
SIMPLE_STOP_REF = os.getenv("SIMPLE_STOP_REF", "bid").strip().lower()

# HOW FAR ABOVE THE FAILURE POINT A RE-ENTRY HAS TO REACH. Deliberately small -
# the whole purpose of re-entering where the stock threw us out, rather than at
# a new day high, is to catch the rest of an upward run instead of sitting out
# the recovery. Two cents is enough that a single tick cannot knock the position
# in and out, and close enough that almost none of the move is given away.
SIMPLE_REENTRY_TICK = float(os.getenv("SIMPLE_REENTRY_TICK", "0.02"))

# The book table and the end-of-day summary. The Render log is the only place
# the user sees any of this, so it has to be readable there.
BOOK_SECONDS = int(os.getenv("BOOK_SECONDS", "120"))
PROBE_LOG = os.getenv("PROBE_LOG", "0").strip().lower() not in ("0", "false", "no")

SIMPLE_MAX_NAMES = 50
SIMPLE_START_CAPITAL = 30_000.0
SIMPLE_SLOT = SIMPLE_START_CAPITAL / SIMPLE_MAX_NAMES     # $600 per name
SIMPLE_STOP_CENTS = 0.01
SIMPLE_STOP_PCT = 0.001

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("engine")


class _Named(logging.LoggerAdapter):
    """v31's log lines say "[v31]". v34 runs v31's code too; this makes the
    same lines say "[v34]" when v34 is the one running it."""

    def process(self, msg, kwargs):
        if isinstance(msg, str) and msg.startswith("[v31]"):
            msg = "[%s]" % self.extra["name"] + msg[5:]
        return msg, kwargs


def load_floats(path) -> dict:
    """{symbol: float shares} from a CSV with symbol and float_shares columns.
    Rows without a usable number are skipped; a missing file is an empty map."""
    path = Path(path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    floats = {}
    try:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                try:
                    n = float(row.get("float_shares") or 0)
                except ValueError:
                    continue
                if n > 0 and row.get("symbol"):
                    floats[row["symbol"].strip().upper()] = n
    except FileNotFoundError:
        pass
    return floats


FLOATS = load_floats(FLOAT_FILE)

# THE LOG IS THE ONLY WINDOW ONTO THIS BOT, so it has to be readable. alpaca-py
# dumps the ENTIRE symbol list on every subscribe - four times, one line per
# channel - which buries every line that matters. Errors still come through.
for _noisy in ("alpaca", "alpaca.data", "alpaca.data.live",
               "alpaca.data.live.websocket", "websockets", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def margin_for(price: float) -> float:
    """How far above a level counts as a genuine break of it."""
    if price <= 5:
        return 0.05
    if price <= 20:
        return 0.01 * price
    if price <= 50:
        return 0.20 + (price - 20) * (0.10 / 30)
    if price <= 100:
        return 0.30 + (price - 50) * (0.10 / 50)
    return 0.40


def simple_stop(entry: float) -> float:
    return entry - max(SIMPLE_STOP_CENTS, SIMPLE_STOP_PCT * entry)


def sane_stop(stop: float, price: float) -> float:
    """A stop must be a real price below the fill. Never zero, never negative,
    never above the entry. If the arithmetic produced nonsense, fall back to
    the ordinary cut under the fill - an unprotected position is the one
    outcome that is never acceptable."""
    if stop is None or stop <= 0 or stop >= price:
        return simple_stop(price)
    return stop


def entries_allowed() -> bool:
    """NO NEW POSITIONS ONCE THE DAY IS CLOSING.

    close_loop starts flattening at FLATTEN_AT, but nothing stopped the entry
    rules from buying at the same time. On 2026-09-30 at 7:15pm v32 logged
    "end of day - flattening" and then opened XRPN nine seconds later, so the
    bot was buying and liquidating at once and could not get flat.
    """
    now = datetime.now(ET)
    hm = (now.hour, now.minute)
    if hm >= FLATTEN_AT:
        return False
    return SESSION[0] <= hm < SESSION[1]


def in_window(window) -> bool:
    now = datetime.now(ET)
    start, end = window
    return start <= (now.hour, now.minute) < end


def market_is_open() -> bool:
    """The session WE trade: 4:00am-8:00pm ET, weekdays. Not 9:30-16:00."""
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    return in_window(SESSION)


def nothing_traded_today() -> bool:
    """Midnight to 4:00am ET, or a weekend: no session has run yet today, so
    the account's equity right now is the day's starting value."""
    now = datetime.now(ET)
    return now.weekday() >= 5 or (now.hour, now.minute) < SESSION[0]


# ----------------------------------------------------------------------------
# DECISION LOG - one file per strategy, flushed off the critical path
# ----------------------------------------------------------------------------

class DecisionLog:
    def __init__(self, name):
        self.buf = deque(maxlen=20000)
        self.path = "/tmp/%s_decisions.log" % name

    def record(self, **fields):
        try:
            fields["t"] = datetime.now(ET).isoformat()
            self.buf.append(fields)
        except Exception:
            pass

    async def flusher(self):
        while True:
            await asyncio.sleep(2.0)
            try:
                if not self.buf:
                    continue
                lines = []
                while self.buf:
                    lines.append(repr(self.buf.popleft()))
                await asyncio.to_thread(self._write, lines)
            except Exception:
                pass

    def _write(self, lines):
        with open(self.path, "a") as fh:
            fh.write("\n".join(lines) + "\n")


# ----------------------------------------------------------------------------
# BROKER - every call runs OFF the event loop
# ----------------------------------------------------------------------------

ORDER_CLOSED = {"filled", "canceled", "cancelled", "expired", "rejected",
                "replaced", "done_for_day"}


def order_done(o) -> bool:
    """The order is closed - nothing more can fill on it."""
    if o is None:
        return False
    status = getattr(o, "status", "")
    name = getattr(status, "value", None) or str(status).rsplit(".", 1)[-1]
    return str(name).lower() in ORDER_CLOSED


class Broker:
    """One account. Every method awaits a thread so the loop never blocks.

    This is the whole reason three strategies can share a process safely. A
    synchronous submit_order() on the event loop would freeze the other two
    strategies' tick handling for the length of the round trip.
    """

    def __init__(self, key: str, secret: str, paper: bool, label: str):
        self.client = TradingClient(key, secret, paper=paper)
        self.paper = paper
        self.label = label
        self._eq = 0.0
        self._eq_at = 0.0
        self.baseline_source = DAY_BASELINE
        self._fill_log: dict[str, list] = {}   # symbol -> [(shares, avg price)]

    def take_fill_price(self, symbol: str) -> float:
        """The average price of everything that filled on this symbol since
        the last call - what a sale REALLY got, not the print that triggered
        it. 0.0 when nothing filled or the broker did not say."""
        rows = self._fill_log.pop(symbol, [])
        shares = sum(q for q, _ in rows)
        return sum(q * p for q, p in rows) / shares if shares else 0.0

    async def account(self):
        return await asyncio.to_thread(self.client.get_account)

    async def day_baseline(self, fallback: float = 0.0) -> float:
        """The equity the day's -10% halt is measured against.

        account.last_equity is the account's equity at the previous session's
        close, so it does not move when this process restarts. Reading the day
        baseline from it is the whole fix: a restart at noon can no longer tell
        the bot that a 17% loss never happened.

        Except before 4:00am and on weekends, when last_equity is still a day
        behind (see DAY_BASELINE above) and the live equity is the right value.
        """
        self.baseline_source = DAY_BASELINE
        if DAY_BASELINE == "boot":
            return await self.equity(fallback)
        try:
            acct = await self.account()
            if nothing_traded_today():
                now_eq = float(getattr(acct, "equity", 0) or 0)
                if now_eq > 0:
                    self.baseline_source = "equity before 4am"
                    return now_eq
            prev = float(getattr(acct, "last_equity", 0) or 0)
            if prev > 0:
                return prev
            log.warning("[%s] broker reported no last_equity - "
                        "falling back to current equity for the day baseline",
                        self.label)
        except Exception as e:
            log.error("[%s] cannot read last_equity (%s) - "
                      "falling back to current equity", self.label, e)
        return await self.equity(fallback)

    async def equity(self, fallback: float = 0.0) -> float:
        """Cached - this is consulted on every tick."""
        now = time.time()
        if now - self._eq_at < EQUITY_TTL and self._eq > 0:
            return self._eq
        try:
            acct = await self.account()
            self._eq = float(acct.equity)
            self._eq_at = now
            return self._eq
        except Exception:
            return self._eq or fallback

    async def positions(self):
        """All holdings. None means UNREACHABLE - never confuse that with flat."""
        try:
            raw = await asyncio.to_thread(self.client.get_all_positions)
        except Exception as e:
            log.error("[%s] cannot read positions: %s", self.label, e)
            return None
        out = {}
        for p in raw:
            try:
                qty = float(p.qty)
            except Exception:
                continue
            if qty <= 0:                       # long only; ignore any short
                continue
            out[p.symbol] = {"qty": qty,
                             "entry": float(p.avg_entry_price or 0.0),
                             "price": float(p.current_price or 0.0)}
        return out

    async def qty(self, symbol: str):
        """One symbol's real share count. 0.0 when flat, None when unreachable."""
        try:
            pos = await asyncio.to_thread(self.client.get_open_position, symbol)
            return float(pos.qty)
        except Exception as e:
            t = str(e).lower()
            if "position does not exist" in t or "404" in t:
                return 0.0
            return None

    async def avg_entry(self, symbol: str):
        """What the position really cost per share. None when unreachable."""
        try:
            pos = await asyncio.to_thread(self.client.get_open_position, symbol)
            return float(pos.avg_entry_price)
        except Exception:
            return None

    async def send(self, symbol: str, qty: int, side, limit: float,
                   wait: float = 2.0) -> int:
        """Returns filled shares, 0 on no fill, -1/-2 when the broker refuses.

        NOTHING IS LEFT WORKING WHEN THIS RETURNS. The old version returned on
        the first partial fill and left the rest of the order live. The chase
        then sent a second order for the remainder, both kept filling, and a
        1,000-share buy could end near 1,900 - the likeliest way a 25% starter
        became 35% on QTEX on 2026-10-02. Whatever has not filled is cancelled
        here, every time, before the caller decides what to do next.
        """
        try:
            order = await asyncio.to_thread(
                self.client.submit_order,
                LimitOrderRequest(symbol=symbol, qty=qty, side=side,
                                  time_in_force=TimeInForce.DAY,
                                  limit_price=limit, extended_hours=True))
        except Exception as e:
            return self.classify(e, side, symbol)
        filled = 0
        o = None
        self.settled = True
        polls = max(1, int(round(wait / 0.2)))
        try:
            for _ in range(polls):
                await asyncio.sleep(wait / polls)
                o = await asyncio.to_thread(self.client.get_order_by_id, order.id)
                filled = int(float(o.filled_qty or 0))
                if filled >= qty or order_done(o):
                    break
                if filled > 0:
                    break                      # partial: cancel the rest below
        except Exception as e:
            log.error("[%s] cannot poll order on %s: %s", self.label, symbol, e)
        if filled < qty:
            try:
                await asyncio.to_thread(self.client.cancel_order_by_id, order.id)
            except Exception:
                pass
            if not order_done(o):
                # WHAT FILLED IS KNOWN ONLY ONCE THE CANCEL IS DONE. Shares can
                # fill between the last poll and the cancel; counted from the
                # last poll, the chase sent them again - NU, 2026-10-05: sized
                # at 300 shares, 394 held. Read the order until it is closed.
                o = await self.settle(symbol, order.id, o)
                if o is not None:
                    filled = int(float(o.filled_qty or 0))
        avg = float(getattr(o, "filled_avg_price", 0) or 0) if filled > 0 else 0.0
        if avg > 0:
            self._fill_log.setdefault(symbol, []).append((filled, avg))
        return filled

    async def settle(self, symbol, oid, last):
        """Read a cancelled order until the broker says it is closed. Sets
        self.settled False when it never does - its final fill is unknown, and
        the caller must not send another order on top of it."""
        for _ in range(10):
            try:
                o = await asyncio.to_thread(self.client.get_order_by_id, oid)
                last = o
                if order_done(o):
                    return o
            except Exception:
                pass
            await asyncio.sleep(0.1)
        self.settled = False
        log.warning("[%s] %s: an order was not confirmed closed after its "
                    "cancel - no further order on top of it", self.label, symbol)
        return last

    def classify(self, e, side, symbol) -> int:
        """Turn a rejection into an instruction. NEVER match on the code.

        Alpaca returns 40310000 for at least four unrelated things - shorting,
        buying power, wash trades and quantity. On 2026-09-30 this code treated
        every one of them as "the position is gone", so a wash-trade rejection
        made the stop abandon 7,688 shares it was still holding. Match the
        message, not the number.

          -2  our own open order is in the way -> cancel it and retry
          -1  fatal for this chase -> stop
           0  ordinary failure -> retry
        """
        msg = str(e).lower()
        log.error("[%s] order failed %s %s: %s", self.label, side, symbol, e)
        if "wash trade" in msg or "sell limit price should be greater" in msg:
            return -2
        if "not allowed to short" in msg:
            return -1                          # long-only account, we are flat
        if "insufficient qty available" in msg:
            # NOT an empty account. Alpaca sends this when the shares exist but
            # are reserved by working orders - read held_for_orders in the same
            # payload. On 2026-09-30 AHG reported existing_qty 1040 with
            # held_for_orders 1040 and available 0, and the old -1 made the
            # chase give up and ghost-clear a position that was really there.
            # -2 means "our own order is in the way": cancel it and try again.
            return -2                          # we hold less than we asked
        if "insufficient buying power" in msg:
            return -1 if side == OrderSide.BUY else 0
        return 0

    async def cancel_open(self, symbol: str) -> int:
        """Cancel our own working orders on one symbol.

        A resting BUY makes Alpaca reject the SELL that is trying to stop the
        same position out - it reads as a wash trade. The exit has to clear its
        own path first.
        """
        try:
            orders = await asyncio.to_thread(
                self.client.get_orders,
                GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol]))
        except Exception as e:
            log.error("[%s] cannot list open orders for %s: %s",
                      self.label, symbol, e)
            return 0
        n = 0
        for o in orders or []:
            try:
                await asyncio.to_thread(self.client.cancel_order_by_id, o.id)
                n += 1
            except Exception:
                pass
        if n:
            log.warning("[%s] cancelled %d working order(s) on %s",
                        self.label, n, symbol)
            await asyncio.sleep(0.4)           # let the broker release them
        return n


# ----------------------------------------------------------------------------
# MARKET DATA - ONE connection, shared by every strategy
# ----------------------------------------------------------------------------

class MarketData:

    def __init__(self, key: str, secret: str, feed: DataFeed):
        self.hist = StockHistoricalDataClient(key, secret)
        self.stream = StockDataStream(key, secret, feed=feed)
        self.feed = feed
        self.subscribed: set[str] = set()
        self.pending: set[str] = set()
        self.last_sub_at = 0.0
        self.trade_sinks = []                  # callables(symbol, price, size)
        self.bar_sinks = []                    # callables(bar)
        self.quote_sinks = []                  # callables(symbol, bid, ask) - the tape
        self.quoted: set[str] = set()

    async def subscribe(self, symbols, force: bool = False):
        """Queue names for the next batch. force=True sends them right now."""
        new = [s for s in symbols if s not in self.subscribed]
        if not new:
            return
        self.pending.update(new)
        if force:
            await self.flush_subscriptions()

    async def flush_subscriptions(self):
        """ONE call for the whole batch, and it MUST go through a thread.

        alpaca-py's subscribe_bars/subscribe_trades do:
            asyncio.run_coroutine_threadsafe(self._send_subscribe_msg(),
                                             self._loop).result()
        self._loop is OUR loop, because we drive the stream inside it. Calling
        that from inside the loop means the loop blocks on .result() waiting for
        a coroutine only the loop itself can run - a hard, permanent freeze of
        every strategy at once. Handing it to a worker thread lets .result()
        block there while our loop stays free to do the sending.
        """
        if not self.pending:
            return
        batch = sorted(self.pending)
        try:
            await asyncio.to_thread(self.stream.subscribe_bars,
                                    self._on_bar, *batch)
            await asyncio.to_thread(self.stream.subscribe_trades,
                                    self._on_trade, *batch)
        except Exception as e:
            log.error("subscribe failed (%d names): %s", len(batch), e)
            return
        # NOT .clear(). The two awaits above take real time, and the scanner
        # can queue a fresh symbol while they run. Clearing would throw that
        # symbol away unsubscribed - it would never be watched and no log line
        # would say so. Remove exactly what was sent, nothing else.
        self.pending.difference_update(batch)
        self.subscribed.update(batch)
        self.last_sub_at = time.time()
        log.info("watching %d names (+%d batched) on the shared connection",
                 len(self.subscribed), len(batch))
        if TAPE_QUOTES == "all":
            await self.watch_quotes(batch)

    async def watch_quotes(self, symbols):
        """Stream quotes for these names as well, for the tape. Same
        connection; on a running stream the SDK sends one subscribe message
        (no reconnect). Through a thread, for the reason given above."""
        new = [s for s in symbols if s not in self.quoted]
        if not new:
            return
        try:
            await asyncio.to_thread(self.stream.subscribe_quotes,
                                    self._on_quote, *new)
        except Exception as e:
            log.error("quote subscribe failed (%d names): %s", len(new), e)
            return
        self.quoted.update(new)
        log.info("quotes for the tape: %d names (+%d)", len(self.quoted), len(new))

    async def _on_quote(self, quote):
        try:
            bid = float(quote.bid_price or 0)
            ask = float(quote.ask_price or 0)
        except Exception:
            return
        for sink in self.quote_sinks:
            try:
                sink(quote.symbol, bid, ask)
            except Exception as e:          # one strategy's error is its own
                log.error("quote %s: %s", quote.symbol, e)

    async def subscribe_loop(self):
        """First batch goes immediately; after that, at most every 30 seconds."""
        while True:
            await asyncio.sleep(2)
            if not self.pending:
                continue
            first = not self.subscribed
            if first or time.time() - self.last_sub_at >= SUBSCRIBE_INTERVAL:
                await self.flush_subscriptions()

    async def _on_trade(self, trade):
        # The condition codes ride along. They are the only way to tell a real
        # print from an odd lot or a derivatively-priced one, and a bot that
        # cannot tell them apart will trigger on prices the market never had.
        conds = tuple(getattr(trade, "conditions", None) or ())
        # The print's own time, so an exit can say how old the print that
        # triggered it was. On 2026-10-05 at 4:06am a QTEX print at 1.27 threw
        # v31 and v34 out of a position while QTEX traded 1.40-1.52 - its last
        # 1.27 had been four minutes earlier.
        ts = getattr(trade, "timestamp", None)
        ts = ts.timestamp() if hasattr(ts, "timestamp") else 0.0
        for sink in self.trade_sinks:
            try:
                sink(trade.symbol, float(trade.price), float(trade.size), conds, ts)
            except Exception as e:          # one strategy's error is its own
                log.error("trade %s: %s", trade.symbol, e)

    async def _on_bar(self, bar):
        for sink in self.bar_sinks:
            try:
                sink(bar)
            except Exception as e:          # one strategy's error is its own
                log.error("bar %s: %s", getattr(bar, "symbol", "?"), e)

    async def snapshots(self, symbols):
        return await asyncio.to_thread(
            self.hist.get_stock_snapshot,
            StockSnapshotRequest(symbol_or_symbols=symbols))

    async def bars_between(self, symbol: str, start, end):
        """[(bar start, close, volume, high)] of the one-minute bars that
        opened between start and end, oldest first. SIP bars from the last 15 minutes need a
        paid data plan; the caller retries without them if this is refused."""
        res = await asyncio.to_thread(
            self.hist.get_stock_bars,
            StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Minute,
                             start=start, end=end, feed=self.feed))
        rows = (getattr(res, "data", None) or {}).get(symbol, [])
        return [(b.timestamp, float(b.close), float(b.volume), float(b.high))
                for b in rows]

    async def quote(self, symbol: str, side: str):
        try:
            snap = await self.snapshots(symbol)
            q = snap[symbol].latest_quote
            return q.ask_price if side == "ask" else q.bid_price
        except Exception:
            return None

    async def run_forever(self):
        """One connection for the whole process. Never opened twice."""
        while True:
            try:
                if hasattr(self.stream, "_run_forever"):
                    await self.stream._run_forever()
                else:
                    await asyncio.to_thread(self.stream.run)
            except Exception as e:
                msg = str(e).lower()
                if "connection limit" in msg:
                    try:
                        await self.stream.close()
                    except Exception:
                        pass
                    log.error("stream refused (connection limit) - waiting 30s. "
                              "Another process is holding this account's ONE "
                              "data connection; suspend it.")
                    await asyncio.sleep(30)
                else:
                    log.error("stream dropped (%s) - reconnecting in 5s", e)
                    await asyncio.sleep(5)


# ----------------------------------------------------------------------------
# PER-SYMBOL STATE
# ----------------------------------------------------------------------------

@dataclass
class Bar:
    ts: datetime
    o: float
    h: float
    l: float
    c: float
    v: float

    @property
    def green(self) -> bool:
        return self.c > self.o

    @property
    def red(self) -> bool:
        return self.c < self.o


@dataclass
class SymState:
    symbol: str
    last_price: float = 0.0
    day_high: float = 0.0

    shares: float = 0.0
    entry: float = 0.0
    stop: float = 0.0                       # the live stop, whatever sets it
    peak: float = 0.0
    trail_stop: float = 0.0
    armed: bool = False
    entry_at: float = 0.0            # time.time() of the fill, for hold-time
    last_conds: tuple = ()           # condition codes of the last print
    last_size: float = 0.0           # size of the last print
    last_print_ts: float = 0.0       # when the last print traded (epoch s, 0 = unknown)
    earn_logged_at: float = 0.0      # V31_EARN_LEADERS: the last "earned" log line
    min_index: int = 0               # the minute the running volume below belongs to
    min_vol: float = 0.0             # shares traded so far in that minute (V31_EARN_VOL_MODE 2)
    earn_high: float = 0.0           # the day high an earned buy last broke - the next
                                     # one needs a higher closed high (no re-buy churn)
    spread_logged_at: float = 0.0    # the last "spread kept it out" log line
    first_entry: float = 0.0         # v32: today's original entry, fixed
    first_stop: float = 0.0          # v32: today's original stop, fixed
    v32_trips: int = 0               # v32: entries taken in this name today
    prev_high: float = 0.0           # v35: the prior session's high
    ema9: float = 0.0                # v35: 1-min EMAs and VWAP, today's bars
    ema20: float = 0.0
    ema12: float = 0.0
    ema26: float = 0.0
    vwap_pv: float = 0.0
    vwap_v: float = 0.0
    ema_break: bool = False          # v35: a candle closed under EMA9 since the buy
    v35_added: bool = False
    v35_starter: float = 0.0
    v35_peak: float = 0.0            # v35: the highest price seen while holding, today
    last_exit: float = 0.0           # v33: the level that threw us out
    skipped_prints: int = 0          # odd lots etc. we refused to act on
    adopted: bool = False
    traded_today: bool = False
    last_tick_at: float = 0.0               # when this name last printed a trade
    recent: deque = field(default_factory=deque)   # v31: (time, price) prints
    hod_reentries: int = 0           # v31: new-high re-entries taken today
    entry_kind: str = ""             # v31: "setup" or "hod" for the open position
    chase_bars: tuple = ()           # v31: (fetched at, [(bar start, close)]) from
                                     # the data API, for the no-chase check
    chase_logged_at: float = 0.0     # v31: last "not chasing" log line
    vol_logged_at: float = 0.0       # v31: last "volume not rising" log line
    quote: tuple = ()                # v31 tape: (bid, ask, time) of the latest quote
    tape: deque = field(default_factory=lambda: deque(maxlen=20000))
                                     # v31 tape: (time, size, side, by quote);
                                     # side 1 buy, -1 sell, 0 between
    tape_last_px: float = 0.0
    tape_tick_dir: int = 0           # last price change: 1 up, -1 down
    tape_logged_at: float = 0.0
    trimmed: bool = False            # v31: this position has sold its part at V31_TRIM_AT
    res_level: float = 0.0           # v31: the day's high above the entry - resistance
    res_done: bool = False           # v31: the resistance rule has fired or stood down
    hod_closed: float = 0.0          # v31: highest CLOSED one-minute bar today -
                                     # the resistance a new-high re-entry breaks
                                                   # inside the crash window

    # v31 only
    bars: list = field(default_factory=list)
    trades: deque = field(default_factory=lambda: deque(maxlen=V31_TRADE_WINDOW * 2 + 5))
    abr_history: deque = field(default_factory=lambda: deque(maxlen=600))
    speed_samples: list = field(default_factory=list)
    quiet_bars: int = 0
    setup_level: float = 0.0
    setup_low: float = 0.0
    setup_ready: bool = False

    @property
    def in_position(self) -> bool:
        return self.shares > 0


# ----------------------------------------------------------------------------
# STRATEGY BASE - accounts, reconciliation, execution. No trading rules here.
# ----------------------------------------------------------------------------

class Strategy:

    name = "base"

    def __init__(self, broker: Broker, data: MarketData):
        self.broker = broker
        self.data = data
        self.log = _Named(log, {"name": self.name})
        self.state: dict[str, SymState] = {}
        self.qualified: set[str] = set()
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
        self.dlog = DecisionLog(self.name)
        self.day = None
        self.day_start_equity = 0.0
        self.halt_streak = 0
        self.halted_today = False
        self.slot = SIMPLE_SLOT
        self.closed_today = []           # (sym, entry, exit, shares, pl, why)
        self.stopped = False
        self.needs_reconcile = True
        self.dropped_ticks = 0
        self.locks: dict[str, asyncio.Lock] = {}

    # ---- plumbing -----------------------------------------------------------

    def lock(self, symbol: str) -> asyncio.Lock:
        """ONE ORDER ACTIVITY PER SYMBOL AT A TIME, across every task.

        Ticks run in one task, the rebalance in another, the halt, dead-tape and
        end-of-day exits in others. They used to act on the same position at
        once: two adds sized from the same share count and both bought, or an
        exit and an add each counted the other's fills as their own and churned
        4,000 shares in and 5,000 out to close a 1,000-share position. Every
        entry, add, trim and exit now holds this lock from its decision to its
        bookkeeping, and re-checks the position once it has it.
        """
        if symbol not in self.locks:
            self.locks[symbol] = asyncio.Lock()
        return self.locks[symbol]

    def st(self, symbol: str) -> SymState:
        if symbol not in self.state:
            self.state[symbol] = SymState(symbol=symbol)
        return self.state[symbol]

    def open_positions(self):
        return [s for s in self.state.values() if s.in_position]

    async def stop_reference(self, symbol: str, price: float) -> float:
        """The price the initial cut is measured from.

        "fill" reproduces the original design exactly. "bid" (the default) uses
        the bid at entry, so the spread alone cannot stop the position out.
        """
        if SIMPLE_STOP_REF != "bid":
            return price
        bid = await self.data.quote(symbol, "bid")
        if bid and 0 < bid <= price:
            return bid
        return price

    def halt_threshold(self) -> float:
        if self.name in HALT_PCT_OVERRIDE:
            return HALT_PCT_OVERRIDE[self.name]
        return HALT_LADDER[min(self.halt_streak, len(HALT_LADDER) - 1)]

    async def self_check(self):
        """Verify our OWN state against our OWN hard rules. A violation here
        means the sizing or stop logic is wrong somewhere, not a market
        event - it must never be silent. Added 2026-10-02 after a v31
        starter entry landed at 35% of equity against a 25% cap, discovered
        only by reading a fill by hand."""
        eq = await self.broker.equity(self.day_start_equity)
        if eq <= 0:
            return
        # Each strategy against ITS OWN cap. v35 was missing here and was held
        # to 25% while its add is designed to reach 40% - every winner with an
        # add would log a false CRITICAL every 5 seconds, burying a real one.
        cap = {"v31": V31_LEADER_CAP, "v34": V34_MAX_POSITION_PCT,
               "v35": V35_MAX_POSITION_PCT}.get(self.name, MAX_POSITION_PCT)
        total_value = 0.0
        for s in self.open_positions():
            price = s.last_price or s.entry
            value = s.shares * price
            total_value += value
            pct = value / eq
            if pct > cap + 0.03:
                log.critical(
                    "[%s] SELF-CHECK VIOLATION: %s is %.1f%% of equity "
                    "(cap %.0f%%) - %d shares @ %.4f = $%.0f",
                    self.name, s.symbol, 100 * pct, 100 * cap,
                    s.shares, price, value)
            if not s.stop or s.stop <= 0:
                log.critical(
                    "[%s] SELF-CHECK VIOLATION: %s has no real stop "
                    "(stop=%s) while holding %d shares",
                    self.name, s.symbol, s.stop, s.shares)
        exposure_pct = total_value / eq
        if exposure_pct > MAX_EXPOSURE_PCT + 0.03:
            log.critical(
                "[%s] SELF-CHECK VIOLATION: total exposure %.1f%% of "
                "equity (cap %.0f%%), $%.0f held",
                self.name, 100 * exposure_pct, 100 * MAX_EXPOSURE_PCT,
                total_value)

    def offer_tick(self, symbol, price, size, conds=(), ts=0.0):
        """Called from the shared stream. NEVER blocks - just queues."""
        try:
            self.queue.put_nowait((symbol, price, size, conds, ts))
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()        # drop the oldest, keep the newest
                self.queue.put_nowait((symbol, price, size, conds, ts))
            except Exception:
                pass
            self.dropped_ticks += 1

    def offer_bar(self, bar):
        """Bars are cheap and rare - handled inline."""
        pass

    def offer_quote(self, symbol, bid, ask):
        """Quotes, for the strategies that keep a tape (v31). Never blocks."""
        pass

    async def tick_worker(self):
        """Each strategy drains its OWN queue in its OWN task.

        This is what keeps them independent: if this strategy is sitting in an
        order chase, its queue backs up and nobody else's does.
        """
        while True:
            symbol, price, size, conds, ts = await self.queue.get()
            try:
                s = self.st(symbol)
                if not qualifies(conds):
                    # The tape is alive - so the dead-tape clock is refreshed -
                    # but this print sets no price and triggers no rule.
                    s.last_tick_at = time.time()
                    s.skipped_prints += 1
                    continue
                s.last_price = price
                s.last_conds = conds
                s.last_size = size
                s.last_print_ts = ts
                s.last_tick_at = time.time()
                self.note_trade(s, price, size)
                # Evaluate FIRST, then raise the day high. "A new high plus the
                # margin" has to mean the high as it stood BEFORE this trade -
                # if the high is raised first, price is never above it and the
                # gate can never open. That bug made v33 unable to take a single
                # entry, and blocked every re-entry in v31 and v32.
                await self.evaluate(s, price)
                s.day_high = max(s.day_high, price)
            except Exception as e:
                log.error("[%s] tick %s: %s", self.name, symbol, e)

    def note_trade(self, s: SymState, price, size):
        pass

    # ---- day roll -----------------------------------------------------------

    async def roll_day(self):
        today = datetime.now(ET).date()
        if self.day == today:
            return
        if self.day is not None:
            self.halt_streak = self.halt_streak + 1 if self.halted_today else 0
            if self.halt_streak >= 3:
                self.stopped = True
                log.critical("[%s] three halted days - stopped until restarted.",
                             self.name)
        self.day = today
        self.halted_today = False
        self.closed_today = []
        self.day_start_equity = await self.broker.day_baseline(
            self.day_start_equity)
        # The $600 slot assumed a $30,000 account. Size it from what the
        # account is really worth so fifty names can never put it on margin,
        # and never let it grow beyond the designed slot.
        live_eq = await self.broker.equity(self.day_start_equity)
        self.slot = min(SIMPLE_START_CAPITAL, live_eq or SIMPLE_START_CAPITAL)
        self.slot = max(0.0, self.slot) / SIMPLE_MAX_NAMES
        self.state.clear()
        self.qualified.clear()
        self.needs_reconcile = True
        now_eq = await self.broker.equity(self.day_start_equity)
        gap = ((now_eq / self.day_start_equity - 1) * 100
               if self.day_start_equity else 0.0)
        source = getattr(self.broker, "baseline_source", DAY_BASELINE)
        if self.halt_threshold() <= 0:
            log.info("[%s] new day %s, baseline equity %.2f (source %s), "
                     "now %.2f (%+.1f%% on the day), DAILY HALT OFF",
                     self.name, today, self.day_start_equity, source,
                     now_eq, gap)
        else:
            log.info("[%s] new day %s, baseline equity %.2f (source %s), "
                     "now %.2f (%+.1f%% on the day), halt at -%.1f%% = %.2f",
                     self.name, today, self.day_start_equity, source,
                     now_eq, gap, 100 * self.halt_threshold(),
                     self.day_start_equity * (1 - self.halt_threshold()))

    # ---- reconciliation -----------------------------------------------------

    async def reconcile(self, why: str = "startup"):
        """The broker is the truth. Memory is a cache every restart wipes."""
        held = await self.broker.positions()
        if held is None:
            return                              # unreachable - change nothing

        adopted, dropped, corrected, flattened = [], [], [], []

        for sym, info in held.items():
            if self.lock(sym).locked():
                # An order is in flight on this name. Its owner books the
                # result; correcting the count underneath it double-counts.
                continue
            s = self.st(sym)
            price = info["price"] or info["entry"] or s.last_price
            if not s.in_position:
                if (ORPHAN_MODE == "flatten" and market_is_open()
                        and in_window(ORPHAN_FLATTEN_WINDOW)):
                    sold = await self.sell(sym, int(info["qty"]), price)
                    flattened.append((sym, sold))
                    self.dlog.record(ev="ORPHAN-FLATTEN", sym=sym, sh=sold)
                    continue
                self.adopt(s, info, price)
                adopted.append((sym, info["qty"], s.stop))
                self.dlog.record(ev="ADOPT", sym=sym, sh=info["qty"],
                                 entry=s.entry, px=price, stop=s.stop, why=why)
            elif abs(s.shares - info["qty"]) >= 1:
                corrected.append((sym, s.shares, info["qty"]))
                self.dlog.record(ev="QTY-FIX", sym=sym, ours=s.shares,
                                 broker=info["qty"], why=why)
                s.shares = info["qty"]

        for s in list(self.state.values()):
            if self.lock(s.symbol).locked():
                continue
            if s.in_position and s.symbol not in held:
                dropped.append((s.symbol, s.shares))
                self.dlog.record(ev="GHOST-CLEAR", sym=s.symbol, sh=s.shares)
                self.clear(s)

        if adopted:
            await self.data.subscribe([sym for sym, _, _ in adopted], force=True)
            for sym, qty, stop in adopted:
                log.warning("[%s] ADOPTED %s: %.0f shares held, stop %.4f",
                            self.name, sym, qty, stop)
        for sym, sold in flattened:
            log.warning("[%s] FLATTENED orphan %s: sold %d", self.name, sym, sold)
        for sym, ours, real in corrected:
            log.warning("[%s] QTY CORRECTED %s: we said %.0f, broker %.0f",
                        self.name, sym, ours, real)
        for sym, qty in dropped:
            log.warning("[%s] GHOST CLEARED %s: we thought %.0f, broker none",
                        self.name, sym, qty)
        if not (adopted or flattened or corrected or dropped):
            log.info("[%s] reconcile (%s): agrees with broker, %d position(s)",
                     self.name, why, len(held))

    def adopt(self, s: SymState, info, price):
        """Take over a position we have no memory of opening."""
        s.shares = info["qty"]
        s.entry = info["entry"] or price
        s.adopted = True
        s.traded_today = True
        s.peak = price or s.entry
        s.day_high = max(s.day_high, price)
        s.last_price = s.last_price or price
        s.last_tick_at = time.time()        # do not kill it for silence we
                                            # were not here to hear
        s.stop = max(s.stop, simple_stop(s.entry))

    def clear(self, s: SymState):
        s.shares = 0.0
        s.entry = s.stop = s.trail_stop = s.peak = 0.0
        s.armed = False
        s.adopted = False
        s.quiet_bars = 0
        s.trimmed = False
        s.res_level = 0.0
        s.res_done = False

    # ---- execution ----------------------------------------------------------

    async def buy(self, symbol: str, shares: int, ref: float,
                  cap: float = None) -> int:
        """Fills counted from the BROKER, never from the order reply.

        A cancel racing a fill used to report "got nothing" and the next attempt
        bought the whole clip again - a $600 slot became $3,050 that way.

        cap: how far over ref the buy may pay (BUY_CHASE_CAP when not given).
        """
        cap = BUY_CHASE_CAP if cap is None else cap
        start = await self.broker.qty(symbol)
        if start is None:
            # Without a starting count no fill can be measured, and guessing 0
            # double-counts anything already held. Do not buy blind.
            log.error("[%s] cannot read %s position - not buying", self.name,
                      symbol)
            return 0
        if FAST_BUY:
            got, why = await self.buy_fast(symbol, shares, ref, cap)
            last = start + got
        else:
            last = await self.buy_chase(symbol, shares, ref, cap, start)
            why = "the chase ended"
        await self.broker.cancel_open(symbol)     # nothing of ours left working
        end = await self.broker.qty(symbol)
        if end is None:
            end = last
        filled = max(0, int(end - start))
        if filled < shares:
            # EVERY MISS IS LOGGED. A buy that came back empty used to leave no
            # line at all, so how often the bot missed a runner was unknowable.
            log.info("[%s] %s BUY SHORT - wanted %d, got %d at a limit up to "
                     "%.4f: %s", self.name, symbol, shares, filled,
                     ref * (1 + cap), why)
        return filled

    async def buy_fast(self, symbol, shares, ref, cap):
        """FAST_BUY: a limit off the ask, re-priced every FAST_BUY_WAIT seconds
        until filled, out of time or tries, or the ask is past the ceiling.
        Counts what the broker CONFIRMED filled on each closed order. Returns
        (shares filled, why it stopped)."""
        ceiling = ref * (1 + cap)
        got = 0
        ask = ref
        deadline = time.monotonic() + FAST_BUY_MAX_SEC
        past = lambda: (" - the ask %.4f is past the ceiling" % ask
                        if ask > ceiling else "")
        for _ in range(FAST_BUY_TRIES):
            if got >= shares:
                return got, "filled"
            if time.monotonic() > deadline:
                return got, "out of time (%.0fs)%s" % (FAST_BUY_MAX_SEC, past())
            # Past the ceiling, the bid still sits AT the ceiling: a runner
            # that dips for a moment fills it.
            ask = await self.data.quote(symbol, "ask") or ref
            limit = round(min(ask * (1 + FAST_BUY_OVER_ASK), ceiling), 2)
            n = await self.broker.send(symbol, shares - got, OrderSide.BUY, limit,
                                       FAST_BUY_WAIT)
            if n == -2:
                await self.broker.cancel_open(symbol)
                continue                       # our own order was in the way
            if n < 0:
                return got, "the broker refused the order"
            got += n
            if not getattr(self.broker, "settled", True):
                return got, "an order was not confirmed closed"
        return got, ("filled" if got >= shares else
                     "out of tries (%d)%s" % (FAST_BUY_TRIES, past()))

    async def buy_chase(self, symbol, shares, ref, cap, start):
        """The chase before FAST_BUY: up to CHASE_ATTEMPTS limits at the ask
        + 0.2%, each working about 2 seconds. Returns the last share count."""
        last = start
        confirmed = 0                  # filled on closed orders, per the broker
        for _ in range(CHASE_ATTEMPTS):
            now = await self.broker.qty(symbol)
            if now is None:
                # UNKNOWN IS NOT ZERO. Reading a failed count as "nothing
                # filled" re-sent the whole order on top of a partial fill.
                await asyncio.sleep(CHASE_PAUSE)
                continue
            last = now
            # The position can lag the order: what the closed orders say
            # filled counts too, whichever is more.
            remaining = int(shares - max(now - start, confirmed))
            if remaining <= 0:
                break
            ask = await self.data.quote(symbol, "ask") or ref
            limit = round(min(ask * 1.002, ref * (1 + cap)), 2)
            got = await self.broker.send(symbol, remaining, OrderSide.BUY, limit)
            if got == -2:
                await self.broker.cancel_open(symbol)
                continue
            if got < 0:
                break
            confirmed += got
            if not getattr(self.broker, "settled", True):
                break                          # its final fill is unknown
            if got == 0:
                await asyncio.sleep(CHASE_PAUSE)
        return max(last, start + confirmed)

    async def sell(self, symbol: str, shares: int, ref: float) -> int:
        """Uncapped chase down - a stop must always get out. Clamped to what
        we really own, so it can never be rejected for shorting."""
        # Clear our own working orders before trying to get out. A resting buy
        # order on this symbol will have the sell rejected as a wash trade.
        await self.broker.cancel_open(symbol)
        start = await self.broker.qty(symbol)
        if start is None:
            start = float(shares)
        want = min(int(shares), int(start))
        if want <= 0:
            return 0
        for _ in range(CHASE_ATTEMPTS):
            # EVERY pass, not just the first. The old code cancelled once above
            # and then submitted a fresh limit sell on each pass without
            # clearing the previous unfilled one. Two or three passes and two or
            # three resting sells each reserved shares, held_for_orders climbed
            # to the whole position, available fell to 0, and the bot strangled
            # its own exit with its own orders.
            await self.broker.cancel_open(symbol)
            now = await self.broker.qty(symbol)
            if now is None:
                await asyncio.sleep(CHASE_PAUSE)  # unknown is not "none sold"
                continue
            sold = start - now
            remaining = int(want - sold)
            if remaining <= 0:
                break
            bid = await self.data.quote(symbol, "bid") or ref
            limit = round(max(bid * 0.995, 0.01), 2)
            got = await self.broker.send(symbol, remaining, OrderSide.SELL, limit)
            if got == -2:
                await self.broker.cancel_open(symbol)
                continue                       # our own order was in the way
            if got < 0:
                log.warning("[%s] %s: broker holds none - stopping the chase",
                            self.name, symbol)
                break
            if got == 0:
                await asyncio.sleep(CHASE_PAUSE)
        end = await self.broker.qty(symbol)
        if end is None:
            return want
        if end > 0:
            log.critical("[%s] %s STILL HOLDING %.0f share(s) after %d chase "
                         "attempts - the exit did not complete. This position "
                         "is unprotected until the next pass.",
                         self.name, symbol, end, CHASE_ATTEMPTS)
        return max(0, int(start - end))

    async def exit(self, s: SymState, why: str):
        async with self.lock(s.symbol):
            # Re-check inside the lock: whatever held it before us may already
            # have closed this position.
            if s.shares <= 0:
                return
            await self.reduce(s, int(s.shares), why)

    async def reduce(self, s: SymState, shares: int, why: str):
        """Sell part or all of a position and BOOK it - the EXIT/TRIM line,
        the decision log and closed_today. Every sale goes through here; the
        rebalance used to sell around it, so a position it closed left no
        record and kept its old entry and stop. Caller holds the lock."""
        # What the decision was made on, taken before the sale: the chase
        # awaits, and the price moves on under it.
        trigger = self.print_text(s)
        self.broker.take_fill_price(s.symbol)    # drop fills from before this sale
        sold = await self.sell(s.symbol, shares, s.last_price)
        # Booked at what the sale REALLY got. The print that triggered it can
        # be far from the market: QTEX, 2026-10-05 4:06am, was logged at 1.27
        # and -$311 while the shares sold near 1.44 and the account barely
        # moved. v35's re-entry-after-a-winner reads this P/L.
        px = (self.broker.take_fill_price(s.symbol) if sold else 0.0) or s.last_price
        self.dlog.record(ev="EXIT", sym=s.symbol, why=why, px=px, trigger=trigger,
                         sh=sold, entry=s.entry, peak=s.peak, stop=s.stop)
        pl = (px - s.entry) * sold if s.entry else 0.0
        self.closed_today.append((s.symbol, s.entry, px, sold, pl, why))
        # The level that threw us out. v33 re-enters just above it, so the
        # ladder climbs with the stock instead of waiting for a new day high.
        s.last_exit = s.last_price
        held = (time.time() - s.entry_at) if s.entry_at else 0.0
        eq = await self.broker.equity(self.day_start_equity)
        log.info("[%s] %s %s %s %d @ %.4f | trigger %s | entry %.4f peak %.4f "
                 "stop %.4f | held %.0fs | P/L %+.2f (%+.2f%% of the trade, "
                 "%+.2f%% of the account)",
                 self.name, "EXIT" if s.shares - sold <= 0 else "TRIM", why,
                 s.symbol, sold, px, trigger, s.entry, s.peak,
                 s.stop, held, pl,
                 100 * (px - s.entry) / s.entry if s.entry else 0.0,
                 100 * pl / eq if eq else 0.0)
        s.shares = max(0.0, s.shares - sold)
        if s.shares <= 0:
            self.clear(s)

    @staticmethod
    def print_text(s: SymState) -> str:
        """The print a decision was made on: price x size, condition codes,
        and how long before now it traded. A late-reported print - one that
        arrives minutes after it happened - shows here as its age."""
        age = ("%.1fs old" % (time.time() - s.last_print_ts)
               if s.last_print_ts else "age unknown")
        return "print %.4f x %d cond %s, %s" % (
            s.last_price, s.last_size, list(s.last_conds) or "-", age)

    async def flatten_all(self, why: str):
        for s in self.open_positions():
            await self.exit(s, why)

    # ---- the account-level halt, checked before any rule ---------------------

    async def halted(self) -> bool:
        if self.stopped or self.halted_today:
            return True
        if self.halt_threshold() <= 0:
            return False                      # halt deliberately disabled
        eq = await self.broker.equity(self.day_start_equity)
        if self.day_start_equity and eq <= self.day_start_equity * (
                1 - self.halt_threshold()):
            log.critical("[%s] DAILY HALT at equity %.2f", self.name, eq)
            await self.flatten_all("daily-halt")
            self.halted_today = True
            return True
        return False

    # ---- to be provided by each strategy ------------------------------------

    async def evaluate(self, s: SymState, price: float):
        raise NotImplementedError

    async def periodic(self):
        """Optional per-strategy background work."""
        return


# ----------------------------------------------------------------------------
# v31 - the runner strategy
# ----------------------------------------------------------------------------

class V31(Strategy):
    """Closed bars set the levels. Ticks fire the actions.

    An in-progress bar is NEVER treated as closed - that bug made an older build
    enter one bar early, inside the red candle.
    """

    name = "v31"

    def __init__(self, broker, data):
        super().__init__(broker, data)
        self.last_rebalance = 0.0
        self.last_speeds: dict[str, float] = {}
        self.leader_cache = (None, {})
        if V31_FLOAT_SIZING:
            if FLOATS:
                self.log.info("[v31] float sizing: %d names from %s; under %.0fM "
                         "shares buy %.0f%% size, names not listed %.0f%%",
                         len(FLOATS), FLOAT_FILE, V31_FLOAT_SMALL / 1e6,
                         100 * V31_FLOAT_SMALL_MULT, 100 * V31_FLOAT_UNKNOWN_MULT)
            else:
                self.log.warning("[v31] float sizing is on but %s has no floats - "
                            "every name is sized as unknown (%.0f%%)",
                            FLOAT_FILE, 100 * V31_FLOAT_UNKNOWN_MULT)

    # ---- bars ---------------------------------------------------------------

    def offer_bar(self, raw):
        s = self.st(raw.symbol)
        bar = Bar(ts=raw.timestamp, o=raw.open, h=raw.high,
                  l=raw.low, c=raw.close, v=raw.volume)
        s.bars.append(bar)
        if len(s.bars) > 400:
            s.bars = s.bars[-400:]
        s.day_high = max(s.day_high, bar.h)
        s.hod_closed = max(s.hod_closed, bar.h)
        s.abr_history.append((bar.ts, self.abr_raw(s)))
        sp = self.bar_speed(s)
        if sp is not None and sp > 0:
            s.speed_samples.append(sp)
        self.refresh_setup(s)
        self.track_stall(s)

    def note_trade(self, s, price, size):
        s.trades.append((price, size))
        now = time.time()
        s.recent.append((now, price))
        minute = int(now // 60)
        if s.min_index != minute:
            s.min_index, s.min_vol = minute, 0.0
        s.min_vol += size
        while s.recent and now - s.recent[0][0] > V31_CRASH_WINDOW_SEC:
            s.recent.popleft()

    # ---- ABR ----------------------------------------------------------------

    def abr_raw(self, s) -> float:
        """Median TRUE RANGE of the last V31_ABR_BARS closed bars."""
        if len(s.bars) < V31_ABR_MIN_BARS:
            return 0.0
        window = s.bars[-V31_ABR_BARS:]
        trs = []
        for i, b in enumerate(window):
            prev_close = window[i - 1].c if i > 0 else b.o
            trs.append(max(b.h, prev_close) - min(b.l, prev_close))
        return statistics.median(trs) if trs else 0.0

    def abr(self, s) -> float:
        """Capped, so one violent stretch cannot blow the leash wide open."""
        raw = self.abr_raw(s)
        if raw <= 0:
            return 0.0
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        older = [v for ts, v in s.abr_history if ts <= cutoff and v > 0]
        if older:
            return min(raw, V31_ABR_GROWTH_CAP * older[-1])
        return raw

    # ---- speed --------------------------------------------------------------

    def bar_speed(self, s):
        """Minute clock - used for ranking and for the stall count."""
        if len(s.bars) < 2:
            return None
        a, b = s.bars[-2], s.bars[-1]
        if a.c <= 0 or a.v <= 0:
            return None
        return ((b.c - a.c) / a.c) * (b.v / a.v)

    def fast_speed(self, s):
        """Trade clock - used for every action.

        Trade-count windows, not time windows: on a furious stock N trades span
        a second, on a quiet one much longer. Self-adjusting, and the volume
        term is a RATIO so it can never divide by zero or flip sign.
        """
        n = V31_TRADE_WINDOW
        if len(s.trades) < 2 * n:
            return None
        recent = list(s.trades)[-n:]
        prior = list(s.trades)[-2 * n:-n]
        p0, p1 = prior[0][0], recent[-1][0]
        v_recent = sum(t[1] for t in recent)
        v_prior = sum(t[1] for t in prior)
        if p0 <= 0 or v_prior <= 0:
            return None
        return ((p1 - p0) / p0) * (v_recent / v_prior)

    # ---- exits scaled to the stock's own volatility ------------------------

    def vol_pct(self, s, price) -> float:
        """The stock's typical one-minute range as a fraction of `price` - the
        high a drop is measured from. 0.0 until it has V31_ABR_MIN_BARS bars."""
        abr = self.abr(s)
        return abr / price if abr > 0 and price > 0 else 0.0

    def flush_pct(self, s, price) -> float:
        v = self.vol_pct(s, price)
        if v <= 0:
            return V31_FLUSH_DROP_PCT
        return min(V31_FLUSH_MAX_PCT, max(V31_FLUSH_MIN_PCT, V31_FLUSH_ABR_MULT * v))

    def crash_pct(self, s, price) -> float:
        v = self.vol_pct(s, price)
        if v <= 0:
            return V31_CRASH_DROP_PCT
        return min(V31_CRASH_MAX_PCT, max(V31_CRASH_MIN_PCT, V31_CRASH_ABR_MULT * v))

    def crashed(self, s, price) -> bool:
        """Has the price fallen crash_pct from the highest print of the last
        V31_CRASH_WINDOW_SEC seconds? Only prints since entry count - a dip
        the position was not there for is not its crash."""
        since = [p for t, p in s.recent if t >= s.entry_at] if s.entry_at else \
            [p for _, p in s.recent]
        if not since:
            return False
        high = max(since)
        pct = self.crash_pct(s, high)
        if s.entry_kind == "hod":
            pct = min(0.95, pct * V31_RUNNER_CRASH_MULT)
        return price <= high * (1 - pct)

    def baseline(self, s) -> float:
        if len(s.speed_samples) < V31_BASELINE_MIN_SAMPLES:
            return 0.0
        return statistics.median(s.speed_samples)

    # ---- setup and filters --------------------------------------------------

    def refresh_setup(self, s):
        """Read from CLOSED bars only: a green closes, then a red closes."""
        s.setup_ready = False
        if len(s.bars) < 2:
            return
        green, red = s.bars[-2], s.bars[-1]
        if green.green and red.red:
            s.setup_level = red.o + V31_ENTRY_TICK
            s.setup_low = red.l
            s.setup_ready = True

    def thin_ok(self, s) -> bool:
        if len(s.bars) < 3:
            return False
        last3 = s.bars[-3:]
        if any(b.v < V31_BAR_SHARES_MIN for b in last3):
            return False
        return sum(b.v for b in last3) >= V31_THREE_BAR_SHARES_MIN

    def track_stall(self, s):
        base = self.baseline(s)
        sp = self.bar_speed(s)
        if base <= 0 or sp is None:
            return
        if abs(sp) < V31_SPEED_FADE_MULT * base:
            s.quiet_bars += 1
        else:
            s.quiet_bars = 0

    # ---- protecting a gain -----------------------------------------------------

    async def trim(self, s):
        """Sell V31_TRIM_FRACTION once, at the first print V31_TRIM_AT above
        the entry; then, with V31_TRIM_STOP_TO_ENTRY, the rest cannot close
        below the entry - the entry stop while unarmed, the trail once armed."""
        async with self.lock(s.symbol):
            if s.shares <= 0 or s.trimmed:
                return
            s.trimmed = True
            n = int(s.shares * V31_TRIM_FRACTION)
            if n <= 0:
                return
            await self.reduce(s, n, "trim +%.0f%%" % (100 * V31_TRIM_AT))
            if s.shares > 0 and V31_TRIM_STOP_TO_ENTRY:
                s.stop = max(s.stop, s.entry)
                s.trail_stop = max(s.trail_stop, s.entry)

    # ---- the tape (log only) ---------------------------------------------------

    def offer_tick(self, symbol, price, size, conds=(), ts=0.0):
        # Marked on arrival, against the quote as it stood when the print came
        # in - not when the queue gets to it.
        if qualifies(conds):
            try:
                self.tape_add(self.st(symbol), price, size)
            except Exception as e:
                self.log.error("[v31] tape %s: %s", symbol, e)
        super().offer_tick(symbol, price, size, conds, ts)

    def offer_quote(self, symbol, bid, ask):
        if bid > 0 and ask >= bid:
            self.st(symbol).quote = (bid, ask, time.time())

    def tape_add(self, s, price, size, now=None):
        now = time.time() if now is None else now
        if s.tape_last_px:
            if price > s.tape_last_px:
                s.tape_tick_dir = 1
            elif price < s.tape_last_px:
                s.tape_tick_dir = -1
        s.tape_last_px = price
        q = s.quote
        by_quote = bool(q) and now - q[2] <= TAPE_QUOTE_MAX_AGE
        if by_quote:
            bid, ask = q[0], q[1]
            side = 1 if price >= ask else -1 if price <= bid else 0
        else:
            side = s.tape_tick_dir
        s.tape.append((now, size, side, by_quote))
        horizon = now - max(TAPE_WINDOWS)
        while s.tape and s.tape[0][0] < horizon:
            s.tape.popleft()

    def tape_split(self, s, seconds, now=None):
        """(buy, sell, between, total shares, share marked by quote) over the
        last `seconds`."""
        now = time.time() if now is None else now
        cut = now - seconds
        buy = sell = mid = quoted = 0.0
        for t, size, side, by_quote in reversed(s.tape):
            if t < cut:
                break
            if side > 0:
                buy += size
            elif side < 0:
                sell += size
            else:
                mid += size
            if by_quote:
                quoted += size
        total = buy + sell + mid
        return buy, sell, mid, total, (quoted / total if total else 0.0)

    def tape_text(self, s, now=None) -> str:
        parts = []
        for seconds in TAPE_WINDOWS:
            buy, sell, mid, total, quoted = self.tape_split(s, seconds, now)
            label = "%ds" % seconds if seconds < 120 else "%dm" % (seconds // 60)
            if not total:
                parts.append("%s: no prints" % label)
                continue
            parts.append("%s: buy %.0f%% sell %.0f%% between %.0f%% of %s sh "
                         "(%.0f%% by quote)" % (
                             label, 100 * buy / total, 100 * sell / total,
                             100 * mid / total, format(int(total), ","),
                             100 * quoted))
        return "tape " + " | ".join(parts)

    async def watch_quotes(self, symbol):
        if TAPE_QUOTES != "positions":
            return
        watch = getattr(self.data, "watch_quotes", None)
        if watch is None:
            return
        try:
            await watch([symbol])
        except Exception as e:
            self.log.warning("[v31] %s quotes for the tape: %s", symbol, e)

    async def reduce(self, s, shares, why):
        self.log.info("[v31]   %s %s (selling: %s)", s.symbol, self.tape_text(s), why)
        await super().reduce(s, shares, why)

    # ---- the day's leaders ------------------------------------------------------

    def leader_rank(self, symbol) -> int:
        """1 for the scanner-list name with the most dollar volume today (from
        the bars held here), 2 for the next... Recounted once a minute."""
        minute = int(time.time() // 60)
        if self.leader_cache[0] != minute:
            since = (datetime.now(timezone.utc)
                     - timedelta(minutes=V31_LEADER_WINDOW_MIN)
                     if V31_LEADER_WINDOW_MIN else None)
            dv = {}
            for sym in self.qualified:
                st = self.state.get(sym)
                if st and st.bars:
                    dv[sym] = sum(b.c * b.v for b in st.bars
                                  if since is None or b.ts >= since)
            order = sorted(dv, key=dv.get, reverse=True)
            self.leader_cache = (minute, {sym: i + 1 for i, sym in enumerate(order)})
        return self.leader_cache[1].get(symbol, 10**6)

    # ---- the speed an entry needs ---------------------------------------------

    def price_ago(self, bars, now, minutes):
        """Close of the last bar that had closed `minutes` minutes ago."""
        cutoff = now - timedelta(minutes=minutes)
        minute = timedelta(minutes=1)
        before = [row[1] for row in bars if row[0] + minute <= cutoff]
        return before[-1] if before else None

    async def moving_up(self, s, price, fast) -> bool:
        if V31_SPEED_BY_TIME:
            ref = self.price_ago(await self.recent_bars(s),
                                 datetime.now(timezone.utc), V31_SPEED_MINUTES)
            if ref:
                return price > ref and price >= ref * (1 + V31_SPEED_MIN_MOVE)
        return fast is not None and fast > 0

    # ---- volume must be rising -------------------------------------------------

    def volume_ratio(self, bars, now):
        """Per-minute volume of the last V31_VOL_RECENT_MIN closed minutes over
        that of the V31_VOL_BEFORE_MIN before them (never before today's
        4:00am). None when it cannot be judged."""
        minute = timedelta(minutes=1)
        t0 = now.replace(second=0, microsecond=0)
        recent_start = t0 - V31_VOL_RECENT_MIN * minute
        session = now.astimezone(ET).replace(hour=4, minute=0, second=0,
                                             microsecond=0).astimezone(timezone.utc)
        before_start = max(session, recent_start - V31_VOL_BEFORE_MIN * minute)
        before_minutes = (recent_start - before_start) / minute
        if before_minutes < 10:
            return None
        recent = before = 0.0
        for ts, _c, v in bars:
            if not (before_start <= ts < t0):
                continue
            if v is None:
                return None
            if ts >= recent_start:
                recent += v
            else:
                before += v
        if before <= 0:
            return float("inf") if recent > 0 else None
        return (recent / V31_VOL_RECENT_MIN) / (before / before_minutes)

    async def volume_rising(self, s, needed=None) -> bool:
        needed = V31_VOL_RISING_MIN if needed is None else needed
        if not needed:
            return True
        ratio = self.volume_ratio(await self.recent_bars(s),
                                  datetime.now(timezone.utc))
        if ratio is None or ratio >= needed:
            return True
        if time.time() - s.vol_logged_at >= 60:
            s.vol_logged_at = time.time()
            self.log.info("[v31] %s VOLUME NOT RISING - the last %d minutes traded "
                     "x%.2f the pace of the %d before (needs x%.2f)", s.symbol,
                     V31_VOL_RECENT_MIN, ratio, V31_VOL_BEFORE_MIN, needed)
        return False

    async def at_resistance(self, s):
        async with self.lock(s.symbol):
            if s.shares <= 0:
                return
            n = s.shares if V31_RES_FRACTION >= 1 else int(s.shares * V31_RES_FRACTION)
            if n > 0:
                await self.reduce(s, int(n), "resistance %.4f" % s.res_level)

    # ---- float sizing ---------------------------------------------------------

    def float_mult(self, symbol) -> float:
        if not V31_FLOAT_SIZING:
            return 1.0
        shares = FLOATS.get(symbol)
        if not shares:
            return V31_FLOAT_UNKNOWN_MULT
        return V31_FLOAT_SMALL_MULT if shares < V31_FLOAT_SMALL else 1.0

    # ---- don't chase ---------------------------------------------------------

    async def recent_bars(self, s):
        """[(bar start, close, volume)] of closed one-minute bars, oldest
        first, back far enough for the no-chase and rising-volume checks.
        Volume is None where the source gave none.

        This strategy's own bars when they reach back that far. A name the
        scanner found a few minutes ago has no bars that old here - bars only
        arrive after subscribing - and that is exactly when a chase happens, so
        the stretch before the first bar of our own comes from the data API.
        That stretch is in the past, so one answer that reaches our first bar
        is kept for the day; otherwise it is asked again once a minute at most.
        Never further back than today's 4:00am session start."""
        now = datetime.now(timezone.utc)
        minute = timedelta(minutes=1)
        session = datetime.now(ET).replace(hour=4, minute=0, second=0,
                                           microsecond=0).astimezone(timezone.utc)
        need = max(session, now - timedelta(minutes=1 + max(
            V31_CHASE_MINUTES + V31_CHASE_COOLOFF_MIN,
            V31_VOL_RECENT_MIN + V31_VOL_BEFORE_MIN)))
        own = [(b.ts, b.c, b.v) for b in s.bars if b.ts + minute <= now]
        if own and own[0][0] <= need:
            return own
        covered = (s.chase_bars and own
                   and s.chase_bars[0] >= own[0][0].timestamp())
        if not covered and (not s.chase_bars
                            or time.time() - s.chase_bars[0] > 60):
            got = None
            # The free data plan refuses SIP bars from the last 15 minutes;
            # then the older part is still worth having.
            for end in (now, now - timedelta(minutes=16)):
                try:
                    got = await self.data.bars_between(s.symbol, need - minute, end)
                    break
                except Exception as e:
                    self.log.warning("[v31] %s bars to %s for the entry checks "
                                "failed: %s", s.symbol,
                                end.astimezone(ET).strftime("%H:%M"), e)
            s.chase_bars = (time.time(), list(got or []))
            # The day's high from before we subscribed is resistance too: a
            # break of the day high must clear it, not just our own bars'.
            highs = [row[3] for row in s.chase_bars[1]
                     if len(row) > 3 and row[0] + minute <= now and row[0] >= need - minute]
            if highs:
                s.hod_closed = max(s.hod_closed, max(highs))
        first_own = own[0][0] if own else now
        older = [(row[0], row[1], row[2] if len(row) > 2 else None)
                 for row in s.chase_bars[1]
                 if need - minute <= row[0] < first_own and row[0] + minute <= now]
        return older + own

    def spike(self, closes, now, price, cooloff=None):
        """The first rise of V31_CHASE_MAX_PCT or more within
        V31_CHASE_MINUTES that ended in the last V31_CHASE_COOLOFF_MIN minutes
        or ends now at `price`, as (rise, from price, when it ended); None if
        there is none. A rise is measured to each bar's close (and to `price`)
        from the close of the last bar that had closed V31_CHASE_MINUTES
        before."""
        minute = timedelta(minutes=1)
        span = timedelta(minutes=V31_CHASE_MINUTES)
        start = now - timedelta(minutes=V31_CHASE_COOLOFF_MIN
                                if cooloff is None else cooloff)
        points = [(row[0] + minute, row[1]) for row in closes] + [(now, price)]
        j = -1
        for i, (t, c) in enumerate(points):
            while j + 1 < i and points[j + 1][0] <= t - span:
                j += 1
            if t < start or j < 0:
                continue
            ref = points[j][1]
            if ref > 0 and c >= ref * (1 + V31_CHASE_MAX_PCT):
                return c / ref - 1, ref, t
        return None

    async def spike_hit(self, s, price, cooloff=None):
        if not V31_NO_CHASE:
            return None
        return self.spike(await self.recent_bars(s), datetime.now(timezone.utc),
                          price, cooloff)

    async def chasing(self, s, price, cooloff=None) -> bool:
        hit = await self.spike_hit(s, price, cooloff)
        if not hit:
            return False
        self.log_chase(s, price, hit)
        return True

    def minute_volume(self, s) -> float:
        """Shares traded in the minute in progress, scaled to a full minute
        (never from under 15 seconds of it - a few prints are not a pace)."""
        now = time.time()
        if s.min_index != int(now // 60):
            return 0.0
        return s.min_vol * 60.0 / max(15.0, now - s.min_index * 60)

    def price_ok(self, s, price, lo=None, hi=None) -> bool:
        """The price band at a buy - with V31_FOLLOW_ABOVE_MAX, a name already
        on the day's list has no ceiling."""
        lo = PRICE_MIN if lo is None else lo
        hi = PRICE_MAX if hi is None else hi
        if price < lo:
            return False
        return price <= hi or (V31_FOLLOW_ABOVE_MAX and s.symbol in self.qualified)

    def earn_candidate(self, s, price) -> bool:
        """The cheap half of earned(): a top leader through its day high -
        a HIGHER one than the last earned buy broke. On the 2026-10-05 replay
        MI was bought back three times in 17 seconds on the same 3.99 high
        (+$130, -$37, -$60): after each exit the next print over it qualified
        again. One earned buy per new closed-candle high."""
        # 1e-9: 10.45 + 0.05 is 10.500000000000002 in floating point, and a
        # print at exactly 10.50 is the 5c break.
        if V31_EARN_UNTIL_MIN:
            now = datetime.now(ET)
            if now.hour * 60 + now.minute >= V31_EARN_UNTIL_MIN:
                return False
        return bool(V31_EARN_LEADERS and s.hod_closed > 0
                    and s.hod_closed > s.earn_high
                    and price >= s.hod_closed + V31_HOD_BREAK_CENTS - 1e-9
                    and self.leader_rank(s.symbol) <= V31_EARN_LEADERS)

    async def earned(self, s, price) -> bool:
        """V31_EARN_LEADERS: a name the chase rule shut out proves it is
        running, not fading - a top leader breaking its day high on volume
        well above the pause before it, with a tight spread."""
        if not self.earn_candidate(s, price):
            return False
        bars = list(s.bars)
        if V31_EARN_VOL_MODE == 0:
            if len(bars) < V31_EARN_PAUSE_BARS + 1:
                return False
            pause = bars[-1 - V31_EARN_PAUSE_BARS:-1]
            avg = sum(b.v for b in pause) / len(pause)
            vol = bars[-1].v
        else:
            if len(bars) < V31_EARN_PAUSE_BARS:
                return False                    # too little of a day to average
            avg = sum(b.v for b in bars) / len(bars)
            vol = bars[-1].v if V31_EARN_VOL_MODE == 1 else self.minute_volume(s)
        if avg <= 0 or vol < V31_EARN_VOL_MULT * avg:
            return False
        bid = ask = 0.0
        spread_ok = V31_EARN_MAX_SPREAD
        if V31_EARN_SPREAD_ABR and price > 0:
            spread_ok = max(spread_ok, min(V31_EARN_SPREAD_CAP,
                                           V31_EARN_SPREAD_ABR * self.abr(s) / price))
        if spread_ok:
            bid = await self.data.quote(s.symbol, "bid")
            ask = await self.data.quote(s.symbol, "ask")
            if not bid or not ask or ask > bid * (1 + spread_ok):
                # Logged so the limit can be set from what runners' books
                # really look like - a furious run widens the spread.
                if bid and ask and time.time() - s.spread_logged_at >= 60:
                    s.spread_logged_at = time.time()
                    self.log.info("[%s] %s would earn its way back in at %.4f "
                                  "but the spread is %.1f%% (%.4f / %.4f), over "
                                  "the %.1f%% limit", self.name, s.symbol, price,
                                  100 * (ask / bid - 1), bid, ask,
                                  100 * spread_ok)
                return False
        if time.time() - s.earn_logged_at >= 60:
            s.earn_logged_at = time.time()
            self.log.info("[%s] %s EARNED ITS WAY BACK IN - %.4f over the day "
                          "high %.4f, volume %.1fx its baseline, spread "
                          "%.4f/%.4f", self.name, s.symbol, price,
                          s.hod_closed, vol / avg, bid or 0, ask or 0)
        return True

    def log_chase(self, s, price, hit):
        now = datetime.now(timezone.utc)
        if time.time() - s.chase_logged_at >= 60:
            s.chase_logged_at = time.time()
            rise, ref, at = hit
            if at >= now:
                self.log.info("[v31] %s NOT CHASING - %.4f is %+.0f%% on %.4f %d "
                         "minutes ago (limit %+.0f%%)", s.symbol, price,
                         100 * rise, ref, V31_CHASE_MINUTES,
                         100 * V31_CHASE_MAX_PCT)
            else:
                until = ("for the rest of the day" if V31_CHASE_COOLOFF_MIN >= 1440
                         else "until " + (at + timedelta(minutes=V31_CHASE_COOLOFF_MIN))
                         .astimezone(ET).strftime("%H:%M"))
                self.log.info("[v31] %s NOT BUYING THE FADE - it rose %+.0f%% from "
                         "%.4f in %d minutes up to %s; left alone %s",
                         s.symbol, 100 * rise, ref, V31_CHASE_MINUTES,
                         at.astimezone(ET).strftime("%H:%M"), until)

    # ---- the trail ----------------------------------------------------------

    def update_trail(self, s, price):
        """Arm on progress, not on time. Then ratchet up, never down."""
        s.peak = max(s.peak, price)
        if s.adopted and not s.armed:
            # No red-bar low exists - we were not there when it was opened.
            s.stop = max(s.stop, s.peak * (1 - V31_ORPHAN_STOP_PCT))
        abr = self.abr(s)
        if abr <= 0:
            return
        if not s.armed and s.peak >= s.entry + V31_TRAIL_ARM_MULT * abr:
            s.armed = True
        if not s.armed:
            return
        distance = V31_TRAIL_MULT * abr
        if s.entry_kind == "hod":
            distance *= V31_RUNNER_TRAIL_MULT
        distance = max(distance, V31_TRAIL_MIN_PCT * s.peak)     # never tighter
        distance = min(distance, V31_TRAIL_MAX_PCT * s.peak)     # never wider
        entry_risk = s.entry - s.stop
        if entry_risk > 0:
            distance = max(distance, entry_risk)
        s.trail_stop = max(s.trail_stop, s.peak - distance)

    def adopt(self, s, info, price):
        super().adopt(s, info, price)
        s.armed = False
        s.trail_stop = 0.0
        s.stop = max(s.stop, (price or s.entry) * (1 - V31_ORPHAN_STOP_PCT))

    # ---- the precedence ladder ---------------------------------------------

    async def evaluate(self, s, price):
        if await self.halted():
            # Halted means stop OPENING, never stop CLOSING. Leaving a position
            # stranded because the account tripped its own limit is the worst
            # possible reading of a risk rule.
            if s.in_position:
                await self.exit(s, "halted")
            return
        fast = self.fast_speed(s)
        base = self.baseline(s)

        if s.in_position:
            self.update_trail(s, price)

            # 0. protecting a gain - sell half at +20% (see V31_TRIM_FRACTION)
            if (V31_TRIM_FRACTION and not s.trimmed and s.entry
                    and price >= s.entry * (1 + V31_TRIM_AT)):
                await self.trim(s)
                return
            if (V31_KEEP_GAIN and s.entry
                    and s.peak >= s.entry * (1 + V31_KEEP_GAIN_ARM)
                    and price <= s.entry + V31_KEEP_GAIN * (s.peak - s.entry)):
                await self.exit(s, "keep-gain")
                return
            if V31_RES_EXIT and s.res_level and not s.res_done:
                if s.peak >= s.res_level * (1 + V31_RES_NEAR):
                    s.res_done = True                    # broken: now support
                elif (s.peak >= s.res_level * (1 - V31_RES_NEAR)
                      and price <= s.peak - V31_RES_GIVE_ABR * max(self.abr(s), 0.01)):
                    s.res_done = True
                    await self.at_resistance(s)
                    return
            if self.crashed(s, price):
                await self.exit(s, "crash")
                return
            if s.peak > 0 and price <= s.peak * (1 - self.flush_pct(s, s.peak)):
                await self.exit(s, "flush")
                return
            if fast is not None and fast <= V31_FLUSH_SPEED_ABS:
                await self.exit(s, "flush")
                return
            # 3. entry stop, while unproven
            if not s.armed and s.stop and price <= s.stop:
                await self.exit(s, "entry-stop")
                return
            # 4. the trail
            if s.armed and s.trail_stop and price <= s.trail_stop:
                await self.exit(s, "trail")
                return
            # 5. stall
            if s.quiet_bars >= V31_STALL_BARS:
                await self.exit(s, "stall")
                return
            if (fast is not None and base > 0 and len(s.bars) >= 5 and fast < 0
                    and s.quiet_bars >= 2 and (V31_RUNNER_FADE or s.entry_kind != "hod")):
                await self.exit(s, "fade")
                return
            # 7. add on strong speed - off while V31_ADDS is False
            if (V31_ADDS and fast is not None and base > 0 and
                    fast >= V31_SPEED_ADD_MULT * base and
                    (not s.entry_at or time.time() - s.entry_at >= 60)):
                await self.add(s, price)
            return

        await self.maybe_enter(s, price, fast, base)

    async def maybe_enter(self, s, price, fast, base):
        if not entries_allowed():
            return
        if s.symbol not in self.qualified:
            return
        # THE PRICE RANGE AT THE MOMENT OF BUYING. The scanner checks $1-$20
        # when it adds a name, and a name stays qualified all day - so a stock
        # that fell under $1 after qualifying could still be bought (PMAX at
        # $0.905 on the 2026-10-01 replay).
        if not self.price_ok(s, price):
            return
        if len(self.open_positions()) >= V31_MAX_POSITIONS:
            return
        # TWO WAYS IN.
        #   setup - a green bar then a red bar closed; buy 1c over the red
        #           open. A name already traded today must also clear the
        #           day's high plus margin_for().
        #   hod   - a name already traded today prints V31_HOD_BREAK_CENTS
        #           over the day's high (see V31_HOD_REENTRY).
        # The level is the highest CLOSED bar, not s.day_high: s.day_high rises
        # with every print (tick_worker) and every scan, so a print can never
        # stand 5 cents above it - a re-entry measured against it never fired.
        # A closed bar's high is real resistance; breaking it by 5c is the
        # breakout.
        setup_ok = s.setup_ready and price >= s.setup_level and (
            not s.traded_today or price >= s.day_high + margin_for(price))
        hod_level = s.hod_closed + V31_HOD_BREAK_CENTS
        hod_break = (V31_HOD_REENTRY and s.hod_closed > 0 and price >= hod_level
                     and (not V31_HOD_MAX_REENTRIES
                          or s.hod_reentries < V31_HOD_MAX_REENTRIES))
        hod_ok = hod_break and s.traded_today
        leader = bool(V31_LEADER_TOP and hod_break
                      and self.leader_rank(s.symbol) <= V31_LEADER_TOP)
        runner = (V31_SPIKE_HOD_OK and hod_break) or leader
        earn_try = self.earn_candidate(s, price)
        if not (setup_ok or hod_ok or runner or earn_try):
            return
        if not self.thin_ok(s):
            return
        if not await self.moving_up(s, price, fast):
            return
        # THE NO-CHASE RULE. Up 15% in the last 15 minutes right now: never.
        # A spike earlier today: no pullback buys; with V31_SPIKE_HOD_OK a
        # break of the day high still may (and with V31_HOD_SKIP_COOLOFF a
        # traded name's new-high re-entry). A leader that EARNS its way back
        # (V31_EARN_LEADERS) passes both.
        earn = earn_try and await self.earned(s, price)
        if not earn and await self.chasing(s, price, 0):
            return
        earlier = await self.spike_hit(s, price)
        if earlier:
            if runner or earn or (hod_ok and V31_HOD_SKIP_COOLOFF):
                kind = "hod"
            else:
                self.log_chase(s, price, earlier)
                return
        elif setup_ok:
            kind = "setup"
        elif hod_ok or leader:
            kind = "hod"
        else:
            return          # an untraded name's new high with no spike: the setup rules apply
        if kind == "setup":
            trigger, stop_ref = s.setup_level, s.setup_low
        else:
            trigger = hod_level
            stop_ref = s.hod_closed - V31_HOD_STOP_ABR * max(self.abr(s), 0.01)
        hod = kind == "hod"
        if not (earn and V31_EARN_SKIP_VOL_RISING) and not await self.volume_rising(
                s, V31_HOD_VOL_MIN if hod and V31_HOD_VOL_MIN else None):
            return

        # The symbol's lock, not a flag. The r23 `entering` flag guarded
        # against two ticks overlapping, which cannot happen - one task
        # handles every tick, one at a time. What CAN overlap is this entry
        # and an order from another task (an exit, the rebalance) on the same
        # name. If one is in flight, skip this tick; the next one re-decides.
        lock = self.lock(s.symbol)
        if lock.locked():
            return
        async with lock:
            if s.in_position:
                return
            await self._maybe_enter_inner(s, price, fast, base,
                                          kind, trigger, stop_ref)
            if earn and s.in_position:
                s.earn_high = s.hod_closed

    def buy_cap(self, s, price) -> float:
        """How far over the trigger a buy may pay: BUY_CHASE_CAP, or with
        FAST_BUY_SPEED_CAP set, more on a fast stock - its typical one-minute
        range times FAST_BUY_SPEED_CAP, never over FAST_BUY_CAP_MAX. Sizing
        uses the same number, so the position cap holds at the worst fill."""
        if not FAST_BUY_SPEED_CAP or price <= 0:
            return BUY_CHASE_CAP
        return min(FAST_BUY_CAP_MAX,
                   max(BUY_CHASE_CAP, FAST_BUY_SPEED_CAP * self.abr(s) / price))

    def entry_shares(self, s, price, worst, stop_ref, eq, kind) -> int:
        """1% of equity at risk to the stop, capped at 25% of equity and at
        the room left under MAX_EXPOSURE_PCT - all at the worst fill."""
        risk_per_share = max(worst - stop_ref, MIN_STOP_PCT * worst, 0.01)
        risk = V31_RUNNER_RISK if kind == "hod" else V31_RISK_PER_TRADE
        shares = int((eq * risk) / risk_per_share)
        # Hard ceiling on the starter, whatever the risk maths says. Speed
        # weights may grow a winner beyond this later; a fresh entry never
        # starts there.
        held_all = sum(x.shares * (x.last_price or price)
                       for x in self.open_positions())
        room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
        cap = int(min(eq * MAX_POSITION_PCT, room) / worst)
        if shares > cap:
            self.log.info("[v31] %s sized down %d -> %d shares (25%% cap)",
                          s.symbol, shares, cap)
            shares = cap
        return shares

    async def _maybe_enter_inner(self, s, price, fast, base,
                                 kind="setup", trigger=None, stop_ref=None):
        """Size, confirm and buy. `trigger` is the level the print had to reach
        and the ask must back; `stop_ref` is where the entry stop goes (the red
        bar's low for a setup, under the old day high for a HOD re-entry)."""
        if trigger is None:
            trigger = s.setup_level
        if stop_ref is None:
            stop_ref = s.setup_low
        # A stop nearer than MIN_STOP_PCT is treated as MIN_STOP_PCT. Without
        # that floor a 4-cent stop divides into the risk budget and asks for
        # thousands of shares - which is exactly how a $29k account ended up
        # holding $43k of one stock.
        #
        # SIZED FOR THE WORST PRICE buy() IS ALLOWED TO PAY, not for the print.
        # buy() chases up to BUY_CHASE_CAP above the trigger. Sized from the
        # print, a fill 1.7% higher turned a 1% risk into 1.33% and a 25%
        # starter into 25.5%. Sized from the cap, neither can be exceeded
        # whatever the fill.
        cap = self.buy_cap(s, price)
        worst = price * (1 + cap)
        eq = await self.broker.equity(self.day_start_equity)
        shares = self.entry_shares(s, price, worst, stop_ref, eq, kind)
        mult = self.float_mult(s.symbol)
        if mult != 1.0:
            flt = FLOATS.get(s.symbol)
            self.log.info("[v31] %s float %s -> %d shares x %.2f = %d",
                     s.symbol, "%.1fM" % (flt / 1e6) if flt else "unknown",
                     shares, mult, int(shares * mult))
            shares = int(shares * mult)
        if shares * price < MIN_TRADE_DOLLARS:
            return

        # THE BREAKOUT HAS TO BE BACKED BY THE MARKET, NOT BY ONE PRINT.
        if CONFIRM_ENTRY_WITH_QUOTE:
            ask = await self.data.quote(s.symbol, "ask")
            if ask is not None and ask < trigger - CONFIRM_TOLERANCE:
                self.log.info("[v31] %s TRIGGER NOT CONFIRMED - print %.4f%s reached "
                         "%.4f but the ask is %.4f, below the trigger. "
                         "No order sent.",
                         s.symbol, price,
                         (" cond %s" % (list(s.last_conds),)) if s.last_conds
                         else "",
                         trigger, ask)
                return
            if ask is None:
                self.log.warning("[v31] %s no quote available - entering on the "
                            "print alone", s.symbol)

        filled = await self.buy(s.symbol, shares, price, cap)
        if filled and kind == "hod":
            s.hod_reentries += 1
        if filled:
            s.shares = filled
            s.entry_kind = kind
            # THE ENTRY IS WHAT THE ACCOUNT PAID, not the print that triggered
            # it. P/L, the stop floor and the trail all measure from here.
            s.entry = await self.broker.avg_entry(s.symbol) or price
            # THE STOP OBEYS THE SAME FLOOR THE SIZING USES. The red bar's low
            # can sit a single cent under the trigger, and a one-cent stop is
            # not a stop - it is a coin toss paid for with the spread. Size and
            # stop must be computed from the SAME risk-per-share or the trade
            # is sized for a 1% loss and exited on a 0.1% wiggle.
            floor_stop = s.entry * (1 - MIN_STOP_PCT)
            s.stop = min(stop_ref, floor_stop)
            s.peak = max(price, s.entry)
            s.trail_stop = 0.0
            s.armed = False
            s.adopted = False
            s.traded_today = True
            high = max(s.hod_closed, s.day_high)
            s.res_level = high if high > s.entry * (1 + V31_RES_NEAR) else 0.0
            s.res_done = False
            self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                             kind=kind, level=trigger, stop=s.stop,
                             stop_ref=stop_ref, speed=fast, baseline=base)
            s.entry_at = time.time()
            self.log.info("[v31] ENTER %s %d @ %.4f (print %.4f) = $%.0f (%.0f%% of "
                     "equity) | stop %.4f (%.2f%% away) | %s trigger %.4f",
                     s.symbol, filled, s.entry, price, filled * s.entry,
                     100 * filled * s.entry / eq if eq else 0.0,
                     s.stop, 100 * (s.entry - s.stop) / s.entry if s.entry else 0.0,
                     "new-high" if kind == "hod" else "setup", trigger)
            self.log.info("[v31]   %s %s (buying)", s.symbol, self.tape_text(s))
            await self.watch_quotes(s.symbol)
            if kind == "hod":
                return                           # no green/red bars to show
            # THE TWO BARS THE SETUP WAS BUILT FROM, printed in full. Without
            # these the question "did it enter on the red candle?" can only be
            # argued from a chart, and it has been argued all day. bars[-1] is
            # the last CLOSED bar (the red one), bars[-2] the one before it.
            # The bar we are buying inside has not closed and has no colour yet.
            try:
                g, r = s.bars[-2], s.bars[-1]
                self.log.info("[v31]   setup %s  green? %-5s  %s  O %.4f H %.4f "
                         "L %.4f C %.4f  V %.0f",
                         s.symbol, g.green, g.ts.astimezone(ET).strftime("%H:%M:%S"),
                         g.o, g.h, g.l, g.c, g.v)
                self.log.info("[v31]   setup %s  red?   %-5s  %s  O %.4f H %.4f "
                         "L %.4f C %.4f  V %.0f  -> trigger %.4f = O + %.2f",
                         s.symbol, r.red, r.ts.astimezone(ET).strftime("%H:%M:%S"),
                         r.o, r.h, r.l, r.c, r.v, s.setup_level, V31_ENTRY_TICK)
                self.log.info("[v31]   buying inside the bar that opened after %s "
                         "- its colour is not knowable yet",
                         r.ts.astimezone(ET).strftime("%H:%M:%S"))
                self.log.info("[v31]   triggering print %.4f x %.0f  cond %s",
                         price, s.last_size, list(s.last_conds) or "-")
            except Exception as e:
                self.log.error("[v31]   could not print setup bars for %s: %s",
                          s.symbol, e)

    async def add(self, s, price):
        """Adding is bounded by the same walls as entering.

        Two ceilings, both learned the hard way on 2026-09-30:
          * no single name above LEADER_CAP of equity
          * the whole book never above MAX_EXPOSURE_PCT of equity - i.e. never
            on borrowed money, whatever buying power the broker offers
        """
        async with self.lock(s.symbol):
            if not s.in_position:
                return                         # closed while we waited
            eq = await self.broker.equity(self.day_start_equity)
            target = min(await self.target_dollars(s.symbol),
                         eq * V31_LEADER_CAP)

            held_all = sum(x.shares * (x.last_price or price)
                           for x in self.open_positions())
            room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)

            gap = min(target - s.shares * price, room)
            if gap < MIN_TRADE_DOLLARS:
                return
            shares = int(gap / (price * (1 + BUY_CHASE_CAP)))   # worst fill
            if shares <= 0:
                return
            old_shares, old_entry = s.shares, s.entry
            filled = await self.buy(s.symbol, shares, price)
            if filled:
                s.shares += filled
                # The entry becomes the AVERAGE cost, or every P/L after an
                # add is measured from the first fill only.
                s.entry = (await self.broker.avg_entry(s.symbol)
                           or (old_entry * old_shares + price * filled)
                           / (old_shares + filled))
                self.dlog.record(ev="ADD", sym=s.symbol, px=price, sh=filled)

    async def target_dollars(self, symbol) -> float:
        """Capital in proportion to speed, leader capped at 80%."""
        speeds = {}
        for s in self.open_positions():
            f = self.fast_speed(s)
            speeds[s.symbol] = max(f, 0.0) if f is not None else 0.0
        total = sum(speeds.values())
        if total <= 0:
            return 0.0
        w = {k: v / total for k, v in speeds.items()}
        top = max(w, key=w.get)
        if w[top] > V31_LEADER_CAP:
            rest = 1 - V31_LEADER_CAP
            other = sum(v for k, v in w.items() if k != top)
            if other > 0:
                w = {k: (V31_LEADER_CAP if k == top else (v / other) * rest)
                     for k, v in w.items()}
            else:
                # Only one position. There is nobody to hand the excess to, and
                # the old code therefore left the weight at 1.00 - the leader
                # "capped at 80%" quietly became the leader taking everything,
                # which is how one name reached 113% of the account.
                w = {k: min(v, V31_LEADER_CAP) for k, v in w.items()}
        eq = await self.broker.equity(self.day_start_equity)
        return eq * w.get(symbol, 0.0)

    async def periodic(self):
        """The 5-minute rebalance clock, plus off-clock speed events.
        Does nothing while V31_REBALANCE is False - except log the tape of
        each open position once a minute."""
        now = time.time()
        for s in self.open_positions():
            if now - s.tape_logged_at >= 60:
                s.tape_logged_at = now
                pct = 100 * (s.last_price / s.entry - 1) if s.entry and s.last_price else 0.0
                self.log.info("[v31] TAPE %s held %+.1f%% | %s", s.symbol, pct,
                         self.tape_text(s))
                await self.watch_quotes(s.symbol)    # adopted positions too
        if not V31_REBALANCE:
            return
        now = time.time()
        due = now - self.last_rebalance >= V31_REBALANCE_SECONDS
        event = False
        for s in self.open_positions():
            f = self.fast_speed(s)
            if f is None:
                continue
            was = self.last_speeds.get(s.symbol)
            if was and was > 0 and (f >= V31_SPEED_EVENT_MULT * was
                                    or f <= was / V31_SPEED_EVENT_MULT):
                event = True
            self.last_speeds[s.symbol] = max(f, 0.0)
        if not (due or event) or not self.open_positions():
            return
        for s in self.open_positions():
            price = s.last_price
            if price <= 0:
                continue
            if s.entry_at and time.time() - s.entry_at < 60:
                continue
            if self.fast_speed(s) is None:
                # NO DATA IS NOT ZERO SPEED. A position adopted after a restart
                # has no prints in memory yet; scored as zero, its target was $0
                # and the first rebalance - due the moment the process starts -
                # sold it outright. Leave it until there is a speed to weigh.
                continue
            target = await self.target_dollars(s.symbol)
            diff = target - s.shares * price
            if abs(diff) < MIN_TRADE_DOLLARS:
                continue
            if diff > 0:
                await self.add(s, price)
            else:
                async with self.lock(s.symbol):
                    if not s.in_position:
                        continue
                    shares = min(int(s.shares), int(abs(diff) / price))
                    if shares > 0:
                        await self.reduce(s, shares, "rebalance")
        self.last_rebalance = now
        self.dlog.record(ev="rebalance", why="clock" if due else "speed-event")


# ----------------------------------------------------------------------------
# v32 - keep only what holds
# ----------------------------------------------------------------------------

# v32 keeps its own idea - buy EVERY scanner name, the same small slot each
# (1/50th of the account), cut what does not hold, keep what does - and since
# r33 runs on v31's machinery (bars, liquidity floor, no-chase, volume, exits)
# for the rest. Each switch below is one replayed step; all of them off is
# r32's v32 exactly (replayed: -$22,014, to the dollar on every day).
# What r32 and before got wrong:
#   * re-entered 2c over the FIRST entry, all day, however often that level
#     had failed: 2,215 of 2,825 trades were re-entries (-$17,268), up to 23
#     round trips in one name in a day
#   * a stop a penny under the bid. Thin $1-$20 names gap through it, so the
#     typical stop-out lost 1.3-1.6%, not a penny - 1,764 stops, -$28,446
#   * bought every name however thin, however far it had just run
#   * no daily halt (it lost 35% of its account on 2026-10-02), no $1-$20
#     check at the buy, entry = the print, no lock, no ask check on a
#     re-entry, and 50 slots of 1/50th could pass the 95% exposure cap
# What r32 got right: the names that held all day made +$6,073 at the close.
#
# Replayed over 2026-09-28..10-02, $30,000 a day, each step on top of the last:
#   r32 as it was                          -$22,014  2,825 trades
#   1 the bugs above + a halt at -10%      -$14,681  1,687
#   2 a traded name needs a new day high   -$10,860    873
#   3 v31's liquidity floor                 -$3,807    253
#   4 v31's no-chase rule                       -$6    119
#   5 rising volume                           +$100    114
#   6 float sizing                            +$307    114
#   7 the stop 1% under the entry             +$495    113
# Tried on top of 7 and left off: v31's whole exit ladder (-$104 from step
# 5 - it sells the all-day holders), half at +20% (+$293), a 1.5% or 2% stop
# (+$358 / +$265), an ABR-wide stop (+$119), at most 2 entries a name (no
# change). 10 all-day holders make +$1,204 and 100 stops cost -$727; the two
# SDEV holds are +$712 of the +$495, so this is thin evidence.
V32_DAILY_HALT = 0.10           # down 10% on the day: stop opening (r32: none)
                                # - V32_HALT_PCT in the environment overrides
V32_FIXES = True                # $1-$20 at the buy, entry = what was paid, the
                                # entry under the symbol's lock, the ask must
                                # back a re-entry, never past MAX_EXPOSURE_PCT
V32_REENTRY_HIGH = True         # a name traded today needs the highest closed
                                # bar + margin_for() (r32: 2c over the FIRST
                                # entry, all day, however often it failed)
V32_MAX_TRIPS = 0               # entries per name per day; 0 = no limit
V32_THIN_OK = True              # v31's liquidity floor before any entry
V32_NO_CHASE = True             # v31's no-chase rule before any entry
V32_VOL_RISING = True           # v31's rising-volume rule before any entry
V32_STOP_PCT = 0.01             # 0: the old cut, 1c / 0.1% under the bid;
                                # else this far under the entry
V32_STOP_ABR = 0.0              # also at least this many ABRs under the entry
V32_V31_EXITS = False           # v31's exit ladder instead of the one stop
V32_TRIM = False                # sell half at +20%, the rest's stop to the
                                # entry (v31's trim, V31_TRIM_AT)
V32_FLOAT_SIZING = True         # v31's float sizing on the slot


class V32(V31):
    """Buy every scanner name on its first qualifying tick, one equal slot
    each. Cut it when it fails. Re-enter only on strength."""

    name = "v32"

    def halt_threshold(self) -> float:
        env = os.getenv("V32_HALT_PCT")
        if env not in (None, ""):
            return float(env) / 100.0
        return V32_DAILY_HALT

    async def evaluate(self, s, price):
        if V32_V31_EXITS:
            return await super().evaluate(s, price)   # entries via maybe_enter
        if await self.halted():
            # Halted means stop OPENING, never stop CLOSING.
            if s.in_position:
                await self.exit(s, "halted")
            return
        if s.in_position:
            if price <= s.stop:
                await self.exit(s, "stop")
                return
            if (V32_TRIM and not s.trimmed and s.entry
                    and price >= s.entry * (1 + V31_TRIM_AT)):
                await self.trim(s)
            return
        await self.maybe_enter(s, price)

    async def maybe_enter(self, s, price, fast=None, base=None):
        if not entries_allowed():
            return
        if s.symbol not in self.qualified:
            return
        if V32_FIXES and not (PRICE_MIN <= price <= PRICE_MAX):
            return
        if len(self.open_positions()) >= SIMPLE_MAX_NAMES:
            return
        # s.first_entry is 0 when this process never opened the position -
        # after a restart, or when reconciliation adopted it. That is a FIRST
        # entry, not a re-entry: "price < 0 + 2c" always passes and the fill
        # then takes first_stop = 0.0, a position with no stop (TNON and LPA,
        # live 2026-09-30 6:43pm ET).
        first = (not s.traded_today) or not s.first_entry or not s.first_stop
        level = 0.0
        if not first:
            if V32_MAX_TRIPS and s.v32_trips >= V32_MAX_TRIPS:
                return
            if V32_REENTRY_HIGH:
                high = s.hod_closed or s.day_high
                level = high + margin_for(price)
            else:
                level = s.first_entry + SIMPLE_REENTRY_TICK
            if price < level:
                return
        if V32_THIN_OK and not self.thin_ok(s):
            return
        if V32_NO_CHASE and await self.chasing(s, price):
            return
        if V32_VOL_RISING and not await self.volume_rising(s):
            return
        if not V32_FIXES:
            await self.v32_enter(s, price, first, level)
            return
        lock = self.lock(s.symbol)
        if lock.locked():
            return
        async with lock:
            if s.in_position:
                return
            await self.v32_enter(s, price, first, level)

    def v32_stop(self, s, entry) -> float:
        if not (V32_STOP_PCT or V32_STOP_ABR):
            return sane_stop(s.first_stop, entry)
        stop = entry * (1 - V32_STOP_PCT)
        abr = self.abr(s)
        if V32_STOP_ABR and abr > 0:
            stop = min(stop, entry - V32_STOP_ABR * abr)
        return sane_stop(stop, entry)

    async def v32_enter(self, s, price, first, level):
        shares = int(self.slot / price)
        if V32_FLOAT_SIZING:
            shares = int(shares * self.float_mult(s.symbol))
        if V32_FIXES:
            # The slot assumes no more than 50 names at once, and 50 slots
            # are the whole account - never past MAX_EXPOSURE_PCT.
            eq = await self.broker.equity(self.day_start_equity)
            held_all = sum(x.shares * (x.last_price or price)
                           for x in self.open_positions())
            room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
            shares = min(shares, int(room / (price * (1 + BUY_CHASE_CAP))))
            if shares * price < MIN_TRADE_DOLLARS:
                return
            # A re-entry needs the market at its level, not one stray print.
            if not first and CONFIRM_ENTRY_WITH_QUOTE:
                ask = await self.data.quote(s.symbol, "ask")
                if ask is not None and ask < level - CONFIRM_TOLERANCE:
                    return
        if shares <= 0:
            return
        ref = await self.stop_reference(s.symbol, price) if first else s.first_entry
        filled = await self.buy(s.symbol, shares, price)
        if not filled:
            return
        s.shares = filled
        s.entry = ((await self.broker.avg_entry(s.symbol) or price)
                   if V32_FIXES else price)
        s.peak = max(price, s.entry)
        if first:
            s.first_entry = price
            s.first_stop = simple_stop(ref)
        s.stop = self.v32_stop(s, s.entry)
        s.trail_stop = 0.0
        s.armed = False
        s.entry_kind = "setup"
        s.entry_at = time.time()
        s.traded_today = True
        s.adopted = False
        s.v32_trips += 1
        self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                         stop=s.stop, first=first)
        self.log.info("[v32] %s %s %d @ %.4f = $%.0f | stop %.4f (%.2f%% away) "
                      "| %s",
                      "ENTER" if first else "RE-ENTER",
                      s.symbol, filled, s.entry, filled * s.entry, s.stop,
                      100 * (s.entry - s.stop) / s.entry if s.entry else 0.0,
                      "first entry today" if first else
                      "back above %.4f, entry %d today" % (level, s.v32_trips))


# ----------------------------------------------------------------------------
# v33 - give back half
# ----------------------------------------------------------------------------

class V33(Strategy):
    """Enter on a NEW day high plus the margin. The stop is the midpoint between
    entry and peak - give back half the gain and we are out. Ratchets up only.

    Self-widening by construction: 11% below the peak on a small move, 40% below
    it on a five-bagger."""

    name = "v33"

    def adopt(self, s, info, price):
        super().adopt(s, info, price)
        s.peak = max(s.entry, price)
        if s.peak > s.entry:
            s.stop = max(s.stop, (s.entry + s.peak) / 2.0)

    async def evaluate(self, s, price):
        if await self.halted():
            # Halted means stop OPENING, never stop CLOSING. Leaving a position
            # stranded because the account tripped its own limit is the worst
            # possible reading of a risk rule.
            if s.in_position:
                await self.exit(s, "halted")
            return
        if s.in_position:
            if price > s.peak:
                s.peak = price
                if s.peak > s.entry:
                    s.stop = max(s.stop, (s.entry + s.peak) / 2.0)
            if price <= s.stop:
                await self.exit(s, "half-back")
            return
        if not entries_allowed():
            return
        if s.symbol not in self.qualified:
            return
        if len(self.open_positions()) >= SIMPLE_MAX_NAMES:
            return
        # THE LADDER CLIMBS WITH THE RUN. First entry is unconditional, exactly
        # like v32. After a give-back exit, buy it back 2c above the level that
        # threw us out - NOT at a new day high, which would mean sitting out the
        # whole recovery. 4 -> 8 -> shaken out at 6 -> back in at 6.02, and the
        # next cushion is halved from there.
        # Same reasoning as v32: s.last_exit is 0 after a restart or an
        # adoption, and "price < 0.02" would let anything through with a stop
        # built from zero.
        if s.traded_today and s.last_exit and \
                price < s.last_exit + SIMPLE_REENTRY_TICK:
            return
        shares = int(self.slot / price)
        if shares <= 0:
            return
        first = (not s.traded_today) or not s.last_exit
        # On a re-entry the stop is the failure point minus a penny, not the bid
        # minus a penny. Otherwise the stop sits 1c under the fill and the next
        # downtick throws us straight back out, over and over at the same price.
        ref = await self.stop_reference(s.symbol, price) if first else s.last_exit
        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares = filled
            s.entry = price
            s.peak = price
            s.stop = sane_stop(simple_stop(ref), price)
            s.entry_at = time.time()
            s.traded_today = True
            s.adopted = False
            self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                             stop=s.stop, first=first)
            log.info("[v33] %s %s %d @ %.4f = $%.0f | stop %.4f (%.2f%% away) "
                     "| %s",
                     "ENTER" if first else "RE-ENTER",
                     s.symbol, filled, price, filled * price, s.stop,
                     100 * (price - s.stop) / price if price else 0.0,
                     ("first entry, stop from the bid"
                      if first else
                      "back above the %.4f that threw us out" % s.last_exit))


# ----------------------------------------------------------------------------
# THE ENGINE - one scan, one connection, three strategies
# ----------------------------------------------------------------------------

# --- v34 ---------------------------------------------------------------------
# v34 keeps its own idea - ONE position at a time, in the best-RANKED name
# with a green-then-red setup (dollar volume of the last 50 prints x the
# 100-print speed), starting at 10% of the account - and since r31 runs on
# v31's machinery for everything else. What r30 and before got wrong:
#   * its 4% flush fired before its 8% trail could, so the trail never ran,
#     and 4% from the high is ordinary noise for a $1-$5 name
#   * an add was confirmed against the latest red bar's open, which moves
#     with every bar, and never updated the entry it measured P/L from
#   * it bought until 8:00pm though the engine flattens from 7:00pm
#   * no $1-$20 check at the buy, no ask confirmation, entry = the print
#     rather than what was paid, no lock against an exit in flight, a stop
#     that could sit a cent under the entry, and no daily halt at all
#
# Replayed over 2026-09-28..10-02, $30,000 a day, each step on top of the last:
#   r30 as it was                          -$19,645  458 trades
#   1 the bugs above fixed                 -$12,379  292
#     + a daily halt at -10%               -$12,419  278
#   2 adds off                              -$8,124  292
#   3 v31's exits                           -$8,649  414
#   4 a traded name needs a new day high    -$4,801  200
#   5 v31's no-chase rule                   -$2,508  130
#   6 float sizing                          -$2,099  130
#   7 sell half at +20%                     -$1,949  130
#   8 rising volume                           -$952  100
#   9 v31's liquidity floor                   +$418   23
# With 3 positions instead of 1 (still ranked) +$1,053; unranked as well
# +$1,404 - which is v31 at a smaller size. v34 keeps its one ranked position.
V34_MAX_POSITIONS = 1
V34_STARTER_PCT = 0.10
V34_DAILY_HALT = 0.10           # down 10% on the day: stop opening (r30: none)
                                # - V34_HALT_PCT in the environment overrides
V34_V31_EXITS = True            # True: v31's exits (volatility flush, crash
                                # guard, ABR trail, stall/fade, half at +20%)
                                # False: v34's own staged ladder below
V34_FLUSH_DROP_PCT = 0.04       # own ladder: out 4% under the high...
V34_ARM_GAIN = 0.25             # ...until up 25%, then the trail:
V34_TRAIL_MED_PCT = 0.08        #    8% under the high
V34_TRAIL_TIGHT_PCT = 0.03      #    3% once up 100%
V34_ADDS = False                # own ladder: double up, 10% -> 20% -> 40%
V34_ADD_MIN_AGE_SEC = 90
V34_ADD_CONFIRM_MARGIN = 0.02   # an add needs the price this far above the ENTRY
V34_ADD_MULT = 2.0
V34_MAX_POSITION_PCT = 0.40
V34_REENTRY_HIGH = True         # a name traded today needs a new day high
                                # plus margin_for() to be bought again
V34_RANKED = True               # only the best-ranked setup may be bought
V34_THIN_OK = True              # v31's liquidity floor (30k shares a bar,
                                # 100k over the last three)


class V34(V31):
    """One position at a time, picked by rank, sized in stages."""

    name = "v34"

    def halt_threshold(self) -> float:
        env = os.getenv("V34_HALT_PCT")
        if env not in (None, ""):
            return float(env) / 100.0
        return V34_DAILY_HALT

    # ---- picking the one name ---------------------------------------------------

    def dollar_volume_recent(self, s, n=50):
        return sum(p * sz for p, sz in list(s.trades)[-n:])

    def rank_score(self, s) -> float:
        sp = self.fast_speed(s)
        if sp is None or sp <= 0:
            return 0.0
        return self.dollar_volume_recent(s) * sp

    def best_candidate(self):
        best_sym, best_score = None, 0.0
        for sym in self.qualified:
            st = self.state.get(sym)
            if st is None or st.in_position or not st.setup_ready:
                continue
            score = self.rank_score(st)
            if score > best_score:
                best_sym, best_score = sym, score
        return best_sym

    # ---- the precedence ladder ----------------------------------------------------

    async def evaluate(self, s, price):
        if V34_V31_EXITS:
            return await super().evaluate(s, price)
        if await self.halted():
            if s.in_position:
                await self.exit(s, "halted")
            return
        if not s.in_position:
            await self.maybe_enter(s, price, self.fast_speed(s), self.baseline(s))
            return
        s.peak = max(s.peak, price)
        gain = (s.peak / s.entry - 1) if s.entry else 0.0
        if gain >= V34_ARM_GAIN:
            s.armed = True
        if not s.armed:
            # Before the trail takes over: the flush and the entry stop. (r30
            # kept the flush on after arming too, so it always beat the trail.)
            if s.peak > 0 and price <= s.peak * (1 - V34_FLUSH_DROP_PCT):
                await self.exit(s, "flush")
                return
            if s.stop and price <= s.stop:
                await self.exit(s, "entry-stop")
                return
        else:
            pct = V34_TRAIL_TIGHT_PCT if gain >= 1.0 else V34_TRAIL_MED_PCT
            s.trail_stop = max(s.trail_stop, s.peak * (1 - pct))
            if price <= s.trail_stop:
                await self.exit(s, "trail")
                return
        if (V34_ADDS and s.entry and s.entry_at
                and time.time() - s.entry_at >= V34_ADD_MIN_AGE_SEC
                and price >= s.entry * (1 + V34_ADD_CONFIRM_MARGIN)):
            await self.v34_add(s, price)

    async def maybe_enter(self, s, price, fast, base):
        if not entries_allowed():               # r30 bought until 8pm; flat from 7pm
            return
        if s.symbol not in self.qualified:
            return
        if not self.price_ok(s, price):
            return
        if len(self.open_positions()) >= V34_MAX_POSITIONS:
            return
        setup = s.setup_ready and price >= s.setup_level
        earn_try = self.earn_candidate(s, price)        # V31_EARN_LEADERS
        if not (setup or earn_try):
            return
        if (setup and V34_REENTRY_HIGH and s.traded_today
                and price < s.day_high + margin_for(price)):
            setup = False
            if not earn_try:
                return
        if V34_THIN_OK and not self.thin_ok(s):
            return
        # The ranking picks among names with a setup; an earned breakout has
        # none - being a top leader (V31_EARN_LEADERS) is its ranking.
        if setup and V34_RANKED and self.best_candidate() != s.symbol:
            setup = False
            if not earn_try:
                return
        if not V34_RANKED and (fast is None or fast <= 0):
            return
        # The no-chase rule (V31_NO_CHASE) - unless the name earns its way
        # back in on a new high. Only that breakout may then be bought.
        earn = False
        if await self.spike_hit(s, price):
            earn = earn_try and await self.earned(s, price)
            if not earn:
                await self.chasing(s, price)    # says why, once a minute
                return
        elif not setup:
            return                              # no spike: the setup rules apply
        if not (earn and V31_EARN_SKIP_VOL_RISING) and \
                not await self.volume_rising(s):    # V31_VOL_RISING_MIN
            return
        if earn:
            kind, trigger = "hod", s.hod_closed + V31_HOD_BREAK_CENTS
            stop_ref = s.hod_closed - V31_HOD_STOP_ABR * max(self.abr(s), 0.01)
        else:
            kind, trigger, stop_ref = "setup", s.setup_level, s.setup_low
        lock = self.lock(s.symbol)
        if lock.locked():
            return
        async with lock:
            if s.in_position:
                return
            await self._maybe_enter_inner(s, price, fast, base, kind,
                                          trigger, stop_ref)
            if earn and s.in_position:
                s.earn_high = s.hod_closed

    def entry_shares(self, s, price, worst, stop_ref, eq, kind) -> int:
        """V34_STARTER_PCT of the account at the worst fill, inside the room
        left under MAX_EXPOSURE_PCT."""
        held_all = sum(x.shares * (x.last_price or price)
                       for x in self.open_positions())
        room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
        return int(min(eq * V34_STARTER_PCT, room) / worst)

    async def v34_add(self, s, price):
        async with self.lock(s.symbol):
            if not s.in_position:
                return
            eq = await self.broker.equity(self.day_start_equity)
            now_pct = (s.shares * price) / eq if eq else 0.0
            if now_pct >= V34_MAX_POSITION_PCT:
                return
            target = min(now_pct * V34_ADD_MULT, V34_MAX_POSITION_PCT)
            worst = price * (1 + BUY_CHASE_CAP)
            held_all = sum(x.shares * (x.last_price or price)
                           for x in self.open_positions())
            room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
            gap = min(target * eq - s.shares * price, room)
            if gap < MIN_TRADE_DOLLARS:
                return
            shares = int(gap / worst)
            if shares <= 0:
                return
            filled = await self.buy(s.symbol, shares, price)
            if filled:
                s.shares += filled
                s.entry = await self.broker.avg_entry(s.symbol) or s.entry
                s.entry_at = time.time()
                self.dlog.record(ev="ADD", sym=s.symbol, px=price, sh=filled)
                self.log.info("[v34] ADD %s %d @ %.4f -> now %.0f%% of equity, "
                              "entry %.4f", s.symbol, filled, price,
                              100 * s.shares * price / eq if eq else 0.0, s.entry)


# ----------------------------------------------------------------------------
# v35 - the leaders' pullback
# ----------------------------------------------------------------------------
# One idea, as few rules as it takes. Trade only the day's leaders - the names
# with the most dollar volume, where the traders are. Buy the first push out of
# a pullback: a green candle, one or more reds, then 1c over the last red's
# open. Out at once if that push fails back under the reds' low. Out on a
# candle that closes under the 9 EMA while the trade is young; once it is up
# V35_LEASH_AT, a long leash instead, so a runner can run. v31's machinery
# underneath: bars, ABR, liquidity floor, no-chase, rising volume, sizing (1%
# of the account at risk, never over 25%), float sizing, the crash guard.
#
# Replayed over 2026-09-28..10-02, $30,000 a day, each step on top of the last:
#   the core rules, any scanner name       -$13,923  264 trades
#   1 only the day's top 2 leaders              +$33   33
#   2 v31's liquidity floor                    +$293   27
#   3 above VWAP, EMA9 over EMA20              +$233   20
#   4 rising volume                            +$820   19
#   5 2:1 room to the prior day's high,
#     spread under 1%                          +$913   18
#   6 above EMA9, MACD over zero               +$859   18
#   7 float 20M shares or less               +$1,134   16
#   8 long leash 2 ABRs (was 3)              +$1,488   16
#   9 one add at +5%, stop to the average    +$2,016   16
# Tried and left off: v31's no-chase rule (+$503, 5 trades - it shuts out the
# leaders, which are the names that just spiked); the trigger over the red's
# HIGH (+$317 vs +$820); top 1 or top 3 leaders (+$734 / +$575); $4-$12 only
# (+$253); float 10M or less (+$411); no EMA9 exit (+$766); the long leash
# from +20% (+$1,357); a 3 or 5 ABR leash; half at +20% (no change); volume
# drying up on the pullback (+$440); buying only until 9:30 or 11:00 (+$92 /
# +$309); the ignition candle (never fired at 15-20%; at 10% +$719).
# RE-ENTRY (on top of step 9): back in when a name that made money breaks the
# day's highest closed candle by 5c - no margin when it crosses at 3x its
# usual speed - with the stop AT the broken high, out if it slips back under.
# +$1,896, 18 trades. Re-entering every traded name instead: +$1,154 (AMOD,
# a loser, was bought back three times on 10-02); a stop 1-3 ABRs under the
# high: +$491..+$1,845. No re-entry at all: +$2,016 - kept anyway, on the
# runners it is the only way back in, and 5 days cannot tell $120 apart.
# 4 winners average +$752, 12 losers -$83 - small, fast losses and a few big
# winners. Without the 2 best trades it is -$41: 16 trades is thin evidence.
V35_LEADERS = 2                 # only today's top N names by dollar volume (0 = any)
V35_PRICE_MIN = 1.00            # the price band v35 buys in (the scanner's is $1-$20)
V35_PRICE_MAX = 20.00
V35_MAX_FLOAT = 20_000_000      # only floats up to this many shares (0 = any;
                                # a name not in the float list is allowed)
V35_MAX_SPREAD = 0.01           # no buy when the ask is more than this over the bid
V35_MAX_POSITIONS = 2
V35_DAILY_HALT = 0.10           # down 10% on the day: stop opening
                                # - V35_HALT_PCT in the environment overrides
V35_TRIGGER_HIGH = False        # False: 1c over the last red candle's OPEN;
                                # True: 1c over its HIGH
V35_TREND = True                # at the buy: price above VWAP and above EMA9,
                                # EMA9 above EMA20
V35_MACD = True                 # at the buy: MACD (EMA12 - EMA26) above zero
V35_DRY_PULLBACK = False        # the red candles traded fewer shares, on average,
                                # than the green one before them
V35_ENTRY_END = 0               # no new buys from this time, as HHMM (930 = 9:30am;
                                # 0 = until the engine's FLATTEN_AT)
V35_ROOM_RR = 2.0               # the prior day's high above the trigger has to be
                                # at least this many times the risk (trigger - stop)
                                # away, or no buy (0 = off)
V35_NO_CHASE = False            # v31's no-chase rule on pullback entries - off:
                                # the leaders are the names that just spiked
V35_IGNITION_PCT = 0.0          # a 1-min candle up this much on V31_BAR_SHARES_MIN
                                # x 3 shares: buy its high at once, out at its
                                # midpoint - no pullback, no chase rule (0 = off)
V35_IGNITION_FIRST_BARS = 0     # ignition only within a name's first N candles
                                # held - its first minutes on the scanner, where a
                                # runner like SAIQ (4:00, +42%) shows (0 = any time)
V35_IGNITION_LEADERS = 0        # ignition only for the top N leaders by dollar
                                # volume (0 = V35_LEADERS, like every v35 entry)
V35_REENTRY_HOD = True          # a name traded today: back in when the price breaks
                                # the day's highest CLOSED candle + margin_for(),
                                # stop V31_HOD_STOP_ABR under it (False: only a
                                # new pullback that is also a new day high)
V35_MAX_REENTRIES = 0           # new-high re-entries per name per day (0 = no limit)
V35_REENTRY_STOP_ABR = 0.0      # a re-entry's stop: this many ABRs under the broken
                                # high; 0 = AT the broken high - a short leash, out
                                # if it slips back under (never nearer than 1%)
V35_REENTRY_CENTS = 0.05        # the break needed over the high: these cents
                                # (0 = margin_for(), 5c to $5 then 1%)
V35_REENTRY_FAST_MULT = 3.0     # crossing at this many times the name's usual
                                # speed: no margin at all (0 = off)
V35_REENTRY_AFTER_WIN = True    # re-enter only a name whose last trade made money
V35_REENTRY_EARN = False        # ...and a name whose last trade LOST may come back
                                # only by earning it (V31_EARN_LEADERS: new day
                                # high, volume over the pause, tight spread)
V35_EMA_EXIT = True             # young trade: out when a candle closes under EMA9
V35_LEASH_AT = 0.10             # once up this much from the entry: the long leash
V35_LEASH_ABR = 2.0             # long leash: this many ABRs under the high, kept
                                # between V31_TRAIL_MIN_PCT and V31_TRAIL_MAX_PCT
V35_TRIM = False                # sell half at V31_TRIM_AT, the rest's stop to entry
V35_ADD_AT = 0.05               # once up this much, on a new high: one add the size
                                # of the starter, stop to the new average (0 = off)
V35_MAX_POSITION_PCT = 0.40     # a position with its add never passes this


def _ema(prev: float, x: float, n: int) -> float:
    return x if not prev else prev + (2.0 / (n + 1)) * (x - prev)


class V35(V31):
    """The day's leaders only. Buy the push out of a pullback; cut it fast if
    it fails; give it a long leash once it works."""

    name = "v35"

    def halt_threshold(self) -> float:
        env = os.getenv("V35_HALT_PCT")
        if env not in (None, ""):
            return float(env) / 100.0
        return V35_DAILY_HALT

    # ---- the candles and the averages ----------------------------------------

    def offer_bar(self, raw):
        super().offer_bar(raw)
        s = self.st(raw.symbol)
        b = s.bars[-1]
        s.ema9 = _ema(s.ema9, b.c, 9)
        s.ema20 = _ema(s.ema20, b.c, 20)
        s.ema12 = _ema(s.ema12, b.c, 12)
        s.ema26 = _ema(s.ema26, b.c, 26)
        s.vwap_pv += (b.h + b.l + b.c) / 3 * b.v
        s.vwap_v += b.v
        # A candle that CLOSED under the 9 EMA after we bought ends a young
        # trade; the next print acts on it.
        if (s.in_position and not s.armed and s.entry_at
                and b.ts.timestamp() + 60 > s.entry_at and b.c < s.ema9):
            s.ema_break = True

    def vwap(self, s) -> float:
        return s.vwap_pv / s.vwap_v if s.vwap_v else 0.0

    def trend_ok(self, s, price) -> bool:
        vwap = self.vwap(s)
        return vwap > 0 and price > vwap and price > s.ema9 > s.ema20

    def pullback(self, s):
        """The last closed candles: a green one, then one or more reds.
        Returns (trigger, stop under the reds' low) or None."""
        bars = s.bars
        if len(bars) < 2 or not bars[-1].red:
            return None
        i = len(bars) - 1
        while i >= 0 and bars[i].red:
            i -= 1
        if i < 0 or not bars[i].green:
            return None
        reds = bars[i + 1:]
        if V35_DRY_PULLBACK and sum(b.v for b in reds) / len(reds) >= bars[i].v:
            return None
        last = reds[-1]
        trigger = (last.h if V35_TRIGGER_HIGH else last.o) + V31_ENTRY_TICK
        return trigger, min(b.l for b in reds)

    def ignition(self, s):
        """The last closed candle up V35_IGNITION_PCT or more, on heavy volume.
        Returns (trigger at its high, stop at its midpoint) or None."""
        if not V35_IGNITION_PCT or not s.bars:
            return None
        if V35_IGNITION_FIRST_BARS and len(s.bars) > V35_IGNITION_FIRST_BARS:
            return None
        if V35_IGNITION_LEADERS and self.leader_rank(s.symbol) > V35_IGNITION_LEADERS:
            return None
        b = s.bars[-1]
        if b.o <= 0 or b.c < b.o * (1 + V35_IGNITION_PCT):
            return None
        if b.v < 3 * V31_BAR_SHARES_MIN:
            return None
        return b.h + V31_ENTRY_TICK, (b.h + b.l) / 2

    # ---- entries -----------------------------------------------------------

    async def maybe_enter(self, s, price, fast, base):
        if not entries_allowed():
            return
        if V35_ENTRY_END:
            now = datetime.now(ET)
            if now.hour * 100 + now.minute >= V35_ENTRY_END:
                return
        if s.symbol not in self.qualified:
            return
        if not self.price_ok(s, price, max(PRICE_MIN, V35_PRICE_MIN),
                             min(PRICE_MAX, V35_PRICE_MAX)):
            return
        if len(self.open_positions()) >= V35_MAX_POSITIONS:
            return
        if V35_MAX_FLOAT and FLOATS.get(s.symbol, 0) > V35_MAX_FLOAT:
            return
        if V35_LEADERS and self.leader_rank(s.symbol) > V35_LEADERS:
            return
        kind, found = "setup", None
        earned_back = False
        ignition = self.ignition(s)
        if ignition and price >= ignition[0]:
            kind, found = "ignition", ignition
        elif s.traded_today and V35_REENTRY_HOD and s.hod_closed:
            # RE-ENTRY ON A NEW HIGH. Measured against the highest CLOSED
            # candle: s.day_high moves with every print, so nothing can ever
            # stand above it.
            if V35_MAX_REENTRIES and s.hod_reentries >= V35_MAX_REENTRIES:
                return
            if V35_REENTRY_AFTER_WIN:
                last = [c for c in self.closed_today if c[0] == s.symbol]
                if not last or last[-1][4] <= 0:
                    # A loser comes back only by earning it.
                    if not (V35_REENTRY_EARN and await self.earned(s, price)):
                        return
                    earned_back = True
            margin = V35_REENTRY_CENTS or margin_for(price)
            if (V35_REENTRY_FAST_MULT and fast is not None and base > 0
                    and fast >= V35_REENTRY_FAST_MULT * base):
                margin = 0.0                    # flying through it: no waiting
            # The high to break: the highest closed candle, or the highest
            # price seen while holding if that is higher - a peak printed
            # inside the current minute is not in a closed candle yet, and
            # without it a trail exit could buy straight back in under its
            # own high. (s.peak is cleared when a position closes.)
            high = max(s.hod_closed, s.v35_peak)
            level = high + margin
            kind = "hod"
            found = (level, high - V35_REENTRY_STOP_ABR * max(self.abr(s), 0.01))
        else:
            # A name already traded today has to make a new day high to be
            # bought again - no buying back the same failed level.
            if s.traded_today and price < s.day_high + margin_for(price):
                return
            found = self.pullback(s)
        if not found or price < found[0]:
            return
        trigger, stop_ref = found
        if kind != "ignition":
            if not self.thin_ok(s):
                return
            if V35_TREND and not self.trend_ok(s, price):
                return
            if V35_MACD and not s.ema12 > s.ema26:
                return
            if V35_NO_CHASE and await self.chasing(s, price):
                return
            if not await self.volume_rising(s):
                return
        # ROOM TO RUN: the prior day's high is the wall overhead. The gain to
        # it has to be at least V35_ROOM_RR times what the stop risks.
        risk = trigger - min(stop_ref, trigger * (1 - MIN_STOP_PCT))
        if (V35_ROOM_RR and s.prev_high > trigger
                and s.prev_high - trigger < V35_ROOM_RR * risk):
            return
        if V35_MAX_SPREAD:
            bid = await self.data.quote(s.symbol, "bid")
            ask = await self.data.quote(s.symbol, "ask")
            if bid and ask and ask > bid * (1 + V35_MAX_SPREAD):
                return
        lock = self.lock(s.symbol)
        if lock.locked():
            return
        async with lock:
            if s.in_position:
                return
            s.ema_break = False
            s.v35_added = False
            s.setup_level = trigger             # what the entry log prints
            await self._maybe_enter_inner(s, price, fast, base,
                                          "hod" if kind == "hod" else "setup",
                                          trigger, stop_ref)
            if s.in_position:
                s.v35_starter = s.shares
                if earned_back:
                    s.earn_high = s.hod_closed
                if kind == "ignition":
                    self.log.info("[v35] %s IGNITION entry - candle %+.0f%%",
                                  s.symbol, 100 * (s.bars[-1].c / s.bars[-1].o - 1))

    # ---- exits ---------------------------------------------------------------

    async def evaluate(self, s, price):
        if await self.halted():
            if s.in_position:
                await self.exit(s, "halted")
            return
        if not s.in_position:
            await self.maybe_enter(s, price, self.fast_speed(s), self.baseline(s))
            return
        s.peak = max(s.peak, price)
        s.v35_peak = max(s.v35_peak, price)
        if s.entry and s.peak >= s.entry * (1 + V35_LEASH_AT):
            s.armed = True
        if self.crashed(s, price):
            await self.exit(s, "crash")
            return
        if s.stop and price <= s.stop:
            await self.exit(s, "stop")
            return
        if s.armed:
            dist = V35_LEASH_ABR * self.abr(s)
            dist = min(max(dist, V31_TRAIL_MIN_PCT * s.peak),
                       V31_TRAIL_MAX_PCT * s.peak)
            s.trail_stop = max(s.trail_stop, s.peak - dist)
            if price <= s.trail_stop:
                await self.exit(s, "trail")
                return
        elif V35_EMA_EXIT and s.ema_break:
            await self.exit(s, "under-ema9")
            return
        if (V35_TRIM and not s.trimmed and s.entry
                and price >= s.entry * (1 + V31_TRIM_AT)):
            await self.trim(s)
            return
        if (V35_ADD_AT and not s.v35_added and s.entry
                and price >= s.entry * (1 + V35_ADD_AT) and price > s.day_high):
            await self.v35_add(s, price)

    async def v35_add(self, s, price):
        async with self.lock(s.symbol):
            if not s.in_position or s.v35_added:
                return
            s.v35_added = True
            eq = await self.broker.equity(self.day_start_equity)
            worst = price * (1 + BUY_CHASE_CAP)
            held_all = sum(x.shares * (x.last_price or price)
                           for x in self.open_positions())
            room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
            cap = max(0.0, eq * V35_MAX_POSITION_PCT - s.shares * price)
            shares = int(min(s.v35_starter * price, room, cap) / worst)
            if shares * price < MIN_TRADE_DOLLARS:
                return
            filled = await self.buy(s.symbol, shares, price)
            if filled:
                s.shares += filled
                s.entry = await self.broker.avg_entry(s.symbol) or s.entry
                s.stop = max(s.stop, s.entry)
                self.log.info("[v35] ADD %s %d @ %.4f -> %d shares, entry %.4f, "
                              "stop to the entry", s.symbol, filled, price,
                              s.shares, s.entry)


class Engine:

    def __init__(self):
        paper_raw = os.environ.get("ALPACA_PAPER", "1").strip().lower()
        self.paper = paper_raw in ("1", "true", "t", "yes", "y", "on")
        feed_name = os.environ.get("ALPACA_FEED", "sip").strip().lower()
        feed = DataFeed.SIP if feed_name == "sip" else DataFeed.IEX

        key = os.environ["ALPACA_API_KEY"]
        secret = os.environ["ALPACA_SECRET_KEY"]

        # ONE data connection for the whole process, on v31's keys.
        self.data = MarketData(key, secret, feed)
        self.assets_client = TradingClient(key, secret, paper=self.paper)

        self.strategies = []
        self.add_strategy(V31, key, secret)
        self.add_strategy(V32, os.environ.get("V32_API_KEY"),
                          os.environ.get("V32_SECRET_KEY"))
        self.add_strategy(V34, os.environ.get("V33_API_KEY"),
                          os.environ.get("V33_SECRET_KEY"))
        self.add_strategy(V35, os.environ.get("V35_API_KEY"),
                          os.environ.get("V35_SECRET_KEY"))

        for strat in self.strategies:
            self.data.trade_sinks.append(strat.offer_tick)
            self.data.bar_sinks.append(strat.offer_bar)
            self.data.quote_sinks.append(strat.offer_quote)

        self.last_auth_warn = 0.0
        self.last_probe = 0.0
        self.prev_highs: dict[str, float] = {}

    def add_strategy(self, cls, key, secret):
        if not key or not secret:
            log.warning("%s has no keys - NOT running. Set %s_API_KEY and "
                        "%s_SECRET_KEY to turn it on.",
                        cls.name, cls.name.upper(), cls.name.upper())
            return
        broker = Broker(key, secret, self.paper, cls.name)
        self.strategies.append(cls(broker, self.data))

    # ---- the shared scanner -------------------------------------------------

    def day_reference(self, bar, today):
        """The price the day's gain is measured FROM, and how stale the bar is.

        daily_bar is the last session that actually TRADED. Premarket that is
        yesterday, and on a thin name it can be two weeks old. Measuring a
        premarket price against yesterday's OPEN is meaningless - BRLS read
        +10.7% that way while it was down 3% on the session.
          bar dated today  -> its OPEN   (the session has started)
          bar dated before -> its CLOSE  (a true overnight gap)
        """
        ts = getattr(bar, "timestamp", None)
        try:
            bar_day = ts.astimezone(ET).date()
        except Exception:
            return 0.0, "none", 999
        age = (today - bar_day).days
        if age <= 0:
            return float(getattr(bar, "open", 0) or 0), "open", 0
        return float(getattr(bar, "close", 0) or 0), "prev-close", age

    async def scan(self):
        try:
            assets = await asyncio.to_thread(
                self.assets_client.get_all_assets,
                GetAssetsRequest(status=AssetStatus.ACTIVE))
            symbols = [a.symbol for a in assets
                       if a.tradable and a.symbol.isalpha() and len(a.symbol) <= 4]
        except Exception as e:
            now = time.time()
            if now - self.last_auth_warn > 60:
                self.last_auth_warn = now
                log.error("asset list failed: %s", e)
                if "not authorized" in str(e):
                    log.critical("KEYS AND ENDPOINT DO NOT MATCH. Using the %s "
                                 "endpoint. Paper keys need ALPACA_PAPER=true.",
                                 "PAPER" if self.paper else "LIVE")
            return {}

        picks, probe = {}, []
        today = datetime.now(ET).date()
        for chunk in [symbols[i:i + 500] for i in range(0, len(symbols), 500)]:
            try:
                snaps = await self.data.snapshots(chunk)
            except Exception:
                continue
            for sym, snap in (snaps or {}).items():
                try:
                    bar = snap.daily_bar
                    last = snap.latest_trade.price if snap.latest_trade else None
                    if not bar or not last:
                        continue
                    if not (PRICE_MIN <= last <= PRICE_MAX):
                        continue
                    ref, kind, age = self.day_reference(bar, today)
                    if ref <= 0 or age > MAX_BAR_AGE_DAYS:
                        continue
                    if len(probe) < 5:
                        probe.append((sym, float(last), float(ref), kind, age))
                    if last < ref * (1 + GAIN_FROM_OPEN):
                        continue
                    # Seed the day high so a "new high" means something the
                    # moment we start watching. Today's bar carries a real
                    # session high; premarket the best we have is the last
                    # print, which is exactly "the high as of right now".
                    seed = float(getattr(bar, "high", 0) or 0) if age == 0 else 0.0
                    picks[sym] = max(seed, float(last))
                    # The prior session's high, for v35's room check: before
                    # today trades, daily_bar IS the prior session.
                    prev = snap.previous_daily_bar if age == 0 else bar
                    self.prev_highs[sym] = float(getattr(prev, "high", 0) or 0)
                except Exception:
                    continue
        self.log_probe(probe)
        return picks

    def log_probe(self, probe):
        now = time.time()
        if not probe or now - self.last_probe < 60:
            return
        self.last_probe = now
        if not PROBE_LOG:
            return
        for sym, last, ref, kind, age in probe:
            gain = (last / ref - 1) * 100 if ref else 0.0
            log.info("PROBE %-5s last=%.4f vs %s %.4f (bar %dd old) -> %+.1f%%",
                     sym, last, kind, ref, age, gain)

    # ---- loops --------------------------------------------------------------

    async def scanner_loop(self):
        """ONE scan for all three. Previously this ran three times over."""
        while True:
            try:
                for strat in self.strategies:
                    await strat.roll_day()
                    if strat.needs_reconcile:
                        strat.needs_reconcile = False
                        await strat.reconcile("day-roll")
                if any(not s.stopped and not s.halted_today
                       for s in self.strategies):
                    picks = await self.scan()
                    if picks:
                        symbols = list(picks)[:MAX_WATCH]
                        for strat in self.strategies:
                            strat.qualified.update(symbols)
                            for sym in symbols:
                                st = strat.st(sym)
                                st.day_high = max(st.day_high, picks[sym])
                                st.prev_high = self.prev_highs.get(sym, st.prev_high)
                        await self.data.subscribe(symbols)
            except Exception as e:
                log.error("scanner: %s", e)
            await asyncio.sleep(SCAN_SECONDS)

    async def reconcile_loop(self):
        while True:
            await asyncio.sleep(RECONCILE_SECONDS)
            for strat in self.strategies:
                try:
                    await strat.reconcile("periodic")
                except Exception as e:
                    log.error("[%s] reconcile: %s", strat.name, e)

    async def periodic_loop(self):
        while True:
            await asyncio.sleep(5)
            for strat in self.strategies:
                try:
                    if not strat.stopped and not strat.halted_today:
                        await strat.periodic()
                except Exception as e:
                    log.error("[%s] periodic: %s", strat.name, e)

    async def risk_loop(self):
        """The account halt, on a timer.

        It used to be checked only inside evaluate(), which needs a trade to
        print. On 2026-09-30 the account fell from -9% to -18% between two
        ticks and the halt was not consulted until the damage was done. It also
        re-flattens every pass, so anything reconciliation adopts after a halt
        gets closed instead of sitting there for the rest of the day.
        """
        while True:
            await asyncio.sleep(RISK_CHECK_SECONDS)
            for strat in self.strategies:
                try:
                    if strat.stopped or not strat.day_start_equity:
                        continue
                    await strat.self_check()
                    # A threshold of 0 means the halt is DELIBERATELY OFF.
                    # Without this line the limit equals the baseline and the
                    # first cent of loss halts the strategy - which is exactly
                    # what happened to v32 and v33 the moment they were switched
                    # on, 2026-09-30 5:42pm ET. halted() had this guard;
                    # risk_loop kept its own copy of the test and did not.
                    if strat.halt_threshold() <= 0:
                        continue
                    eq = await strat.broker.equity(strat.day_start_equity)
                    limit = strat.day_start_equity * (1 - strat.halt_threshold())
                    if eq <= limit and not strat.halted_today:
                        log.critical("[%s] DAILY HALT at equity %.2f "
                                     "(baseline %.2f, limit %.2f)",
                                     strat.name, eq, strat.day_start_equity, limit)
                        strat.halted_today = True
                    if strat.halted_today and strat.open_positions():
                        log.warning("[%s] halted - flattening %d position(s)",
                                    strat.name, len(strat.open_positions()))
                        await strat.flatten_all("halted")
                except Exception as e:
                    log.error("[%s] risk loop: %s", strat.name, e)

    async def dead_loop(self):
        """Close positions whose stock has gone silent.

        Runs on a timer, NOT on ticks - that is the whole point. A held name
        that has not printed a trade in DEAD_MINUTES is not resting, it is
        untradeable, and every tick-driven rule we have is blind to it.
        """
        while True:
            await asyncio.sleep(DEAD_CHECK_SECONDS)
            if not market_is_open():
                continue
            now = time.time()
            for strat in self.strategies:
                if strat.stopped or strat.halted_today:
                    continue
                for s in list(strat.open_positions()):
                    if not s.last_tick_at:
                        s.last_tick_at = now
                        continue
                    quiet = now - s.last_tick_at
                    if quiet < DEAD_MINUTES * 60:
                        continue
                    try:
                        log.warning("[%s] %s silent for %.1f min - closing",
                                    strat.name, s.symbol, quiet / 60.0)
                        await strat.exit(s, "dead-tape")
                    except Exception as e:
                        log.error("[%s] dead-tape %s: %s",
                                  strat.name, s.symbol, e)

    async def close_loop(self):
        while True:
            await asyncio.sleep(20)
            now = datetime.now(ET)
            if (now.hour, now.minute) >= FLATTEN_AT:
                for strat in self.strategies:
                    if strat.open_positions():
                        log.info("[%s] end of day - flattening.", strat.name)
                        await strat.flatten_all("end-of-day")

    async def health_loop(self):
        """One line a minute: are the queues draining, is anything stuck?"""
        while True:
            await asyncio.sleep(60)
            parts = []
            for s in self.strategies:
                parts.append("%s q=%d pos=%d drop=%d skipped=%d"
                             % (s.name, s.queue.qsize(),
                                len(s.open_positions()), s.dropped_ticks,
                                sum(x.skipped_prints for x in s.state.values())))
            # The equity on this line, once a minute, IS the account curve -
            # and unlike /tmp/<name>_decisions.log it survives a restart,
            # because Render keeps the log stream.
            money = []
            for s_ in self.strategies:
                try:
                    eq = await s_.broker.equity(s_.day_start_equity)
                    base = s_.day_start_equity or 0.0
                    halt_txt = ("halt OFF" if s_.halt_threshold() <= 0
                                else "halt %.2f"
                                % (base * (1 - s_.halt_threshold())))
                    money.append("%s eq %.2f (%+.1f%% day, %s)"
                                 % (s_.name, eq,
                                    100 * (eq / base - 1) if base else 0.0,
                                    halt_txt))
                except Exception:
                    pass
            log.info("health %s | %s | watching %d (+%d queued) | %s",
                     VERSION, " | ".join(money) or "equity n/a",
                     len(self.data.subscribed), len(self.data.pending),
                     " | ".join(parts))

    # ---- the book: the only view the user actually reads --------------------

    async def book_loop(self):
        """One readable table per strategy, on a clock.

        Everything here is already in the log somewhere. The point is that it is
        in ONE place, in order, with the totals worked out - so a glance answers
        "where do I stand" without arithmetic or a second website.
        """
        while True:
            await asyncio.sleep(BOOK_SECONDS)
            for strat in self.strategies:
                try:
                    await self.print_book(strat)
                except Exception as e:
                    log.error("book %s: %s", strat.name, e)

    async def print_book(self, strat, title="BOOK"):
        held = strat.open_positions()
        closed = strat.closed_today
        if not held and not closed:
            return
        eq = await strat.broker.equity(strat.day_start_equity)
        base = strat.day_start_equity or 0.0
        day_d = eq - base
        day_p = (100 * day_d / base) if base else 0.0
        deployed = sum(x.shares * (x.last_price or x.entry) for x in held)
        now = datetime.now(ET).strftime("%-I:%M %p")

        lines = ["", "===== %s %s  %s ET | %d open, $%s deployed ====="
                 % (strat.name, title, now, len(held), f"{deployed:,.0f}")]
        lines.append("  %-6s %8s %9s %9s %9s %10s %8s %6s"
                     % ("SYM", "shares", "entry", "last", "stop",
                        "P/L $", "P/L %", "held"))
        open_pl = 0.0
        for x in sorted(held, key=lambda y: -((y.last_price or y.entry) /
                                              y.entry - 1 if y.entry else 0)):
            last = x.last_price or x.entry
            pl = (last - x.entry) * x.shares
            open_pl += pl
            pct = 100 * (last / x.entry - 1) if x.entry else 0.0
            mins = int((time.time() - x.entry_at) / 60) if x.entry_at else 0
            lines.append("  %-6s %8.0f %9.4f %9.4f %9.4f %+10.2f %+7.1f%% %5dm"
                         % (x.symbol, x.shares, x.entry, last, x.stop,
                            pl, pct, mins))
        realised = sum(c[4] for c in closed)
        wins = sum(1 for c in closed if c[4] > 0)
        lines.append("  " + "-" * 70)
        lines.append("  %-6s %8s %9s %9s %9s %+10.2f"
                     % ("OPEN", "", "", "", "", open_pl))
        lines.append("  %-6s %-38s %+10.2f"
                     % ("CLOSED", "%d trades, %d up / %d down"
                        % (len(closed), wins, len(closed) - wins), realised))
        lines.append("  " + "-" * 70)
        lines.append("  %-6s %11s %-26s %+10.2f  %+7.2f%%"
                     % ("ACCOUNT", f"{eq:,.2f}", "TODAY", day_d, day_p))
        lines.append("")
        log.info("\n".join(lines))

    async def summary_loop(self):
        """The day's full record, once at the flatten time and once at close."""
        done = set()
        while True:
            await asyncio.sleep(30)
            now = datetime.now(ET)
            for label, when in (("FLATTEN", FLATTEN_AT), ("CLOSE", SESSION[1])):
                key = (now.date(), label)
                if key in done:
                    continue
                if (now.hour, now.minute) >= when and \
                        (now.hour, now.minute) < (when[0], when[1] + 5):
                    done.add(key)
                    for strat in self.strategies:
                        try:
                            await self.print_day(strat, label)
                        except Exception as e:
                            log.error("summary %s: %s", strat.name, e)

    async def print_day(self, strat, label):
        closed = strat.closed_today
        eq = await strat.broker.equity(strat.day_start_equity)
        base = strat.day_start_equity or 0.0
        lines = ["", "===== %s DAY SUMMARY (%s) %s ====="
                 % (strat.name, label, datetime.now(ET).strftime("%Y-%m-%d"))]
        if not closed:
            lines.append("  no closed trades today")
        else:
            lines.append("  %-6s %8s %9s %9s %10s %8s  %s"
                         % ("SYM", "shares", "entry", "exit", "P/L $",
                            "P/L %", "why"))
            for sym, entry, exit_, sh, pl, why in closed:
                pct = 100 * (exit_ / entry - 1) if entry else 0.0
                lines.append("  %-6s %8.0f %9.4f %9.4f %+10.2f %+7.1f%%  %s"
                             % (sym, sh, entry, exit_, pl, pct, why))
            wins = sum(1 for c in closed if c[4] > 0)
            best = max(closed, key=lambda c: c[4])
            worst = min(closed, key=lambda c: c[4])
            lines.append("  " + "-" * 70)
            lines.append("  %d trades | %d up / %d down (%.0f%% hit rate)"
                         % (len(closed), wins, len(closed) - wins,
                            100 * wins / len(closed)))
            lines.append("  best  %-6s %+10.2f     worst %-6s %+10.2f"
                         % (best[0], best[4], worst[0], worst[4]))
            lines.append("  realised %+.2f" % sum(c[4] for c in closed))
        lines.append("  " + "-" * 70)
        lines.append("  started %s   now %s   day %+.2f (%+.2f%%)"
                     % (f"{base:,.2f}", f"{eq:,.2f}", eq - base,
                        (100 * (eq - base) / base) if base else 0.0))
        lines.append("")
        log.info("\n".join(lines))

    # ---- boot ---------------------------------------------------------------

    async def check_accounts(self) -> bool:
        ok = True
        for strat in self.strategies:
            try:
                acct = await strat.broker.account()
                log.info("[%s] connected to Alpaca %s account %s - equity %.2f",
                         strat.name, "PAPER" if self.paper else "LIVE",
                         acct.account_number, float(acct.equity))
            except Exception as e:
                ok = False
                log.critical("[%s] CANNOT REACH THE ACCOUNT: %s", strat.name, e)
                log.critical("[%s] paper keys need ALPACA_PAPER=true; live keys "
                             "need ALPACA_PAPER=false. It will not trade.",
                             strat.name)
        return ok

    async def run(self):
        if not self.strategies:
            log.critical("No strategies have keys. Nothing to do.")
            return
        await self.check_accounts()
        for strat in self.strategies:
            await strat.roll_day()
            strat.needs_reconcile = False
            await strat.reconcile("startup")

        log.info("engine up: VERSION %s | %s | one data connection | "
                 "orphan mode %s | baseline " + DAY_BASELINE + " | "
                 "quote-confirm " + ("on" if CONFIRM_ENTRY_WITH_QUOTE else "OFF") + " | "
                 "odd-lot filter on | stop-ref " + SIMPLE_STOP_REF + " | "
                 "book every %ds | no entries after %02d:%02d | " % (BOOK_SECONDS, FLATTEN_AT[0], FLATTEN_AT[1]) + 
                 "exposure cap %.0f%% | position cap %.0f%% | "
                 "min stop %.0f%% | session %02d:%02d-%02d:%02d ET | "
                 "flatten %02d:%02d ET | dead exit %d min",
                 VERSION, ", ".join(s.name for s in self.strategies),
                 ORPHAN_MODE, MAX_EXPOSURE_PCT * 100, MAX_POSITION_PCT * 100,
                 MIN_STOP_PCT * 100, SESSION[0][0], SESSION[0][1],
                 SESSION[1][0], SESSION[1][1], FLATTEN_AT[0], FLATTEN_AT[1],
                 DEAD_MINUTES)

        tasks = [self.scanner_loop(), self.reconcile_loop(), self.periodic_loop(),
                 self.close_loop(), self.dead_loop(), self.risk_loop(),
                 self.health_loop(), self.book_loop(), self.summary_loop(),
                 self.data.subscribe_loop(), self.data.run_forever()]
        for strat in self.strategies:
            tasks.append(strat.tick_worker())
            tasks.append(strat.dlog.flusher())
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(Engine().run())
