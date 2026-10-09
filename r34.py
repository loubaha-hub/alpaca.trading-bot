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
import base64
import csv
import logging
import json
import os
import re
import statistics
import time
import zlib
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import (StockBarsRequest, StockSnapshotRequest,
                                   StockTradesRequest, StockQuotesRequest,
                                   NewsRequest)
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (GetAssetsRequest, GetOrdersRequest,
                                     LimitOrderRequest, MarketOrderRequest)
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
NO_BUYS_FROM = ()                           # (ET date, (hour, minute)): no new buys
                                            # by any strategy from then to the day's end -
                                            # the owner, 10-08 6pm: "flatten them; we'll
                                            # start them later" (the next day trades as usual)

# --- scanner (shared by all three) -------------------------------------------
PRICE_MIN = 1.00
PRICE_MAX = 20.00
GAIN_FROM_OPEN = 0.10                       # up 10% from the day's reference
MAX_BAR_AGE_DAYS = 5                        # ignore names that have not traded
SCAN_SECONDS = 8
MAX_WATCH = 200                             # symbols on the stream
ROSTER_LOG_MIN = 15                         # the scanner's list in the log: what came
                                            # and went at each scan, and all of it this
                                            # often (minutes) - the replay's stock list
                                            # for the day (the owner, 10-07). 0 = off

# --- execution (shared) ------------------------------------------------------
BUY_CHASE_CAP = 0.02                        # buys capped 2% above the ask
CHASE_ATTEMPTS = 8
CHASE_PAUSE = 0.35
# THE EXIT (the owner, 10-07: "the exit is the key - get out very quick, at any
# price"). SXTC 9:30:16 that day: the stop's limit sell did not fill in the
# opening seconds, its cancel was not confirmed, and the chase sent 8 more
# sells in about 4 seconds - all refused, the shares held by the first - then
# did it again, "unprotected", for 5.7 minutes while SXTC fell $3.03 -> $2.85.
SELL_MARKET_RTH = True          # 9:30-4:00 a sell goes out at market: out at any
                                # price. Premarket and after hours take limits only.
CANCEL_WAIT = 10.0              # a sell waits this long for its own cancelled order
                                # to close - never another order on top of it
OPEN_PAUSE = ((9, 29), (9, 31)) # no new buys around the opening auction (SXTC
                                # 9:29:39: bought 21 seconds before the open)
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
VERSION = "v31-r34.36"

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
        if isinstance(msg, str):
            for tag in ("[v31]", self.extra.get("as")):
                if tag and msg.startswith(tag):
                    msg = "[%s]" % self.extra["name"] + msg[len(tag):]
                    break
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
    stop = dict(NO_BUYS_FROM).get(now.date().isoformat())
    if stop and hm >= stop:
        return False                    # the owner stopped the buying for the day
    if OPEN_PAUSE and OPEN_PAUSE[0] <= hm < OPEN_PAUSE[1]:
        return False                    # the opening auction: gaps, slow cancels
    return SESSION[0] <= hm < SESSION[1]


def regular_hours() -> bool:
    """9:30-4:00 ET on a weekday: when a market order is allowed."""
    now = datetime.now(ET)
    return now.weekday() < 5 and (9, 30) <= (now.hour, now.minute) < (16, 0)


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
        self._sent = deque()                   # when each order went out (ORDER_BUDGET)
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
        self.note_sent()
        try:
            order = await asyncio.to_thread(
                self.client.submit_order,
                LimitOrderRequest(symbol=symbol, qty=qty, side=side,
                                  time_in_force=TimeInForce.DAY,
                                  limit_price=limit, extended_hours=True))
        except Exception as e:
            return self.classify(e, side, symbol)
        return await self.follow(symbol, order, qty, wait)

    def note_sent(self):
        now = time.time()
        sent = getattr(self, "_sent", None)
        if sent is None:
            sent = self._sent = deque()
        sent.append(now)
        while sent and sent[0] < now - 60:
            sent.popleft()

    def orders_in_last_minute(self) -> int:
        sent = getattr(self, "_sent", None) or ()
        now = time.time()
        return sum(1 for x in sent if x >= now - 60)

    async def send_market(self, symbol: str, qty: int, side, ref: float = 0.0,
                          wait: float = 6.0) -> int:
        """A market order - regular hours only: out at any price. As send():
        what filled, nothing left working. self.market_refused is set when the
        broker would not take it, so the caller can fall back to a limit.
        `ref` is not used by the broker (the fake fills at it)."""
        self.market_refused = False
        self.note_sent()
        try:
            order = await asyncio.to_thread(
                self.client.submit_order,
                MarketOrderRequest(symbol=symbol, qty=qty, side=side,
                                   time_in_force=TimeInForce.DAY))
        except Exception as e:
            self.market_refused = True
            return self.classify(e, side, symbol)
        return await self.follow(symbol, order, qty, wait, market=True)

    async def follow(self, symbol, order, qty, wait, market=False) -> int:
        """Poll a submitted order; cancel and settle what has not filled. A
        market order is left to fill: SXTC 10-07 1:40pm, each market sell was
        cancelled after its first partial fill and sent again - 7.5 seconds
        and three orders to get out of a crashing stock (-$290)."""
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
                if filled > 0 and not market:
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
        for _ in range(max(1, int(CANCEL_WAIT / 0.2))):
            try:
                o = await asyncio.to_thread(self.client.get_order_by_id, oid)
                last = o
                if order_done(o):
                    return o
            except Exception:
                pass
            await asyncio.sleep(0.2)
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

    async def fills_today(self) -> list:
        """Every fill on this account since 4am ET, oldest first, as
        (epoch seconds, symbol, "buy" or "sell", shares, average price) -
        what a restart reads back. [] when the broker cannot say."""
        start = datetime.now(ET).replace(hour=4, minute=0, second=0, microsecond=0)
        return await self.fills_between(start)

    async def fills_between(self, start, end=None, pages=20) -> list:
        """As fills_today, for orders submitted from `start` to `end` (None =
        now)."""
        orders, until = [], end
        for _ in range(pages):                  # 500 a page, newest first
            try:
                page = await asyncio.to_thread(
                    self.client.get_orders,
                    GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=start,
                                     until=until, limit=500))
            except Exception as e:
                log.error("[%s] cannot list orders since %s: %s", self.label, start, e)
                return []
            orders += page or []
            if not page or len(page) < 500:
                break
            until = min(o.submitted_at for o in page)
        out = []
        for o in orders:
            q = float(o.filled_qty or 0)
            if q <= 0 or not o.filled_at:
                continue
            side = getattr(o.side, "value", o.side)
            out.append((o.filled_at.timestamp(), o.symbol, str(side).lower(), q,
                        float(o.filled_avg_price or 0)))
        return sorted(set(out))

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

    async def wait_clear(self, symbol: str, timeout: float = None) -> bool:
        """True once no order of ours is working on the symbol. A sell sent on
        top of one is refused - the shares are held for it (SXTC 10-07 9:30).
        A failed read counts as clear: a refused order costs nothing, a
        blocked exit does."""
        timeout = CANCEL_WAIT if timeout is None else timeout
        for _ in range(max(1, int(timeout / 0.25))):
            try:
                orders = await asyncio.to_thread(
                    self.client.get_orders,
                    GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol]))
            except Exception as e:
                log.error("[%s] cannot list open orders for %s: %s",
                          self.label, symbol, e)
                return True
            if not orders:
                return True
            await asyncio.sleep(0.25)
        log.warning("[%s] %s: our cancelled order is still working after %.0fs "
                    "- no sell on top of it", self.label, symbol, timeout)
        return False


# ----------------------------------------------------------------------------
# MARKET DATA - ONE connection, shared by every strategy
# ----------------------------------------------------------------------------

def _pack_ticks(tr, qr, sym, t0):
    """TICK_DUMP's rows as JSON text lines of about TICK_DUMP_CHARS each:
    (trade lines, quote lines, trade count, quote count)."""
    ms = lambda ts: int(round((ts.timestamp() - t0) * 1000))
    trades = [[ms(x.timestamp), float(x.price), float(x.size), "".join(x.conditions or [])]
              for x in (getattr(tr, "data", None) or {}).get(sym, [])]
    quotes, last = [], None
    for x in (getattr(qr, "data", None) or {}).get(sym, []):
        key = (float(x.bid_price), float(x.ask_price))
        if key != last:
            last = key
            quotes.append([ms(x.timestamp), key[0], key[1], float(x.bid_size),
                           float(x.ask_size)])

    def lines(rows):
        out, cur, size = [], [], 0
        for r in rows:
            s = json.dumps(r, separators=(",", ":"))
            if cur and size + len(s) + 1 > TICK_DUMP_CHARS:
                out.append("[" + ",".join(cur) + "]")
                cur, size = [], 0
            cur.append(s)
            size += len(s) + 1
        if cur:
            out.append("[" + ",".join(cur) + "]")
        return out
    return lines(trades), lines(quotes), len(trades), len(quotes)


_EPOCH_CACHE = {}


def _epoch(t) -> float:
    """A raw data-service time ("2026-10-08T08:01:53.762123456Z") or a datetime,
    as seconds since the epoch."""
    if not isinstance(t, str):
        return t.timestamp()
    head, _, frac = t.rstrip("Z").partition(".")
    base = _EPOCH_CACHE.get(head)
    if base is None:
        if len(_EPOCH_CACHE) > 5000:
            _EPOCH_CACHE.clear()
        base = _EPOCH_CACHE[head] = datetime.fromisoformat(head).replace(
            tzinfo=timezone.utc).timestamp()
    return base + (float("0." + frac) if frac else 0.0)


def _pack_seconds(tr, qr, sym, a, m, spans):
    """SEC_DUMP's rows for one minute of one window that starts at `a` (epoch
    seconds), as zlib + base64 text in TICK_DUMP_CHARS pieces: (pieces, trades,
    quotes, seconds). In `spans` [(from, to)]: T [ms after a, price, size,
    conditions] for every trade and Q [ms, bid, ask, bid size, ask size] for each
    change of the bid / ask. Everywhere: S [second after a, open, high, low,
    close, volume, prints, bid, ask, lowest bid] - the prices from the prints
    that count (qualifies), the bid / ask as the second ended."""
    inside = lambda x: any(p <= x < q for p, q in spans)
    T, Q, S = [], [], {}
    for x in (tr or {}).get(sym, []):
        ts, p, sz, conds = _epoch(x["t"]), x["p"], x["s"], x.get("c") or []
        if inside(ts):
            T.append([int(round((ts - a) * 1000)), p, sz, "".join(conds)])
        if not qualifies(conds):
            continue
        k = int(ts - a)
        r = S.get(k)
        if r is None:
            S[k] = [k, p, p, p, p, sz, 1, 0, 0, 0]
        else:
            r[2], r[3], r[4] = max(r[2], p), min(r[3], p), p
            r[5] += sz
            r[6] += 1
    last = None
    for x in (qr or {}).get(sym, []):
        bid, ask = x["bp"], x["ap"]
        if (bid, ask) == last:
            continue
        last = (bid, ask)
        ts = _epoch(x["t"])
        if inside(ts):
            Q.append([int(round((ts - a) * 1000)), bid, ask, x.get("bs", 0), x.get("as", 0)])
        k = int(ts - a)
        r = S.get(k)
        if r is None:
            r = S[k] = [k, 0, 0, 0, 0, 0, 0, 0, 0, bid]
        r[7], r[8] = bid, ask
        r[9] = min(r[9], bid) if r[9] else bid
    rows = [S[k] for k in sorted(S)]
    blob = json.dumps({"m": int(m - a), "T": T, "Q": Q, "S": rows}, separators=(",", ":"))
    text = base64.b64encode(zlib.compress(blob.encode(), 9)).decode()
    pieces = [text[i:i + TICK_DUMP_CHARS] for i in range(0, len(text), TICK_DUMP_CHARS)]
    return pieces, len(T), len(Q), len(rows)


class MarketData:

    def __init__(self, key: str, secret: str, feed: DataFeed):
        self.hist = StockHistoricalDataClient(key, secret)
        self.hist_raw = StockHistoricalDataClient(key, secret, raw_data=True)  # SEC_DUMP
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

    async def dump_ticks(self, day, windows):
        """TICK_DUMP: read-only. Each window's trades [ms after the window's
        start, price, size, conditions] and its quotes [ms, bid, ask, bid size,
        ask size] - a quote only when the bid or ask changed - into the log,
        TICK_DUMP_CHARS of rows to a TICKDUMP line."""
        for sym, a, b in windows:
            start = datetime.fromisoformat("%sT%s" % (day, a)).replace(tzinfo=ET)
            end = datetime.fromisoformat("%sT%s" % (day, b)).replace(tzinfo=ET)
            try:
                tr = await asyncio.to_thread(self.hist.get_stock_trades, StockTradesRequest(
                    symbol_or_symbols=sym, start=start, end=end, feed=self.feed))
                qr = await asyncio.to_thread(self.hist.get_stock_quotes, StockQuotesRequest(
                    symbol_or_symbols=sym, start=start, end=end, feed=self.feed))
            except Exception as e:
                log.error("TICKDUMP %s %s-%s: %s", sym, a, b, e)
                continue
            packed = await asyncio.to_thread(_pack_ticks, tr, qr, sym,
                                             start.timestamp())  # off the event loop
            for kind, lines in (("T", packed[0]), ("Q", packed[1])):
                for i, part in enumerate(lines):
                    log.info("TICKDUMP %s %s %s %s %d/%d %s", day, sym, a, kind, i + 1,
                             len(lines), part)
                    if i % 20 == 19:
                        await asyncio.sleep(0)  # never hold up the trading
            log.info("TICKDUMP %s %s %s-%s: %d trades, %d quotes", day, sym, a, b,
                     packed[2], packed[3])
        log.info("TICKDUMP done: %d windows", len(windows))

    async def dump_seconds(self, buys):
        """SEC_DUMP: read-only. `buys` [(epoch seconds, symbol)]. Per day and
        symbol, the buys' windows (SEC_DUMP_BEFORE before to SEC_DUMP_AFTER after)
        joined where they overlap; each read a minute at a time - every trade and
        quote change near a buy, one row a second throughout (_pack_seconds) - and
        written to SECDUMP lines."""
        by = {}
        for t, sym in sorted(set(buys)):
            by.setdefault((datetime.fromtimestamp(t, ET).date().isoformat(), sym), []).append(t)
        windows = []
        for (day, sym), times in sorted(by.items()):
            for t in times:
                a, b = int(t - SEC_DUMP_BEFORE), t + SEC_DUMP_AFTER
                if windows and windows[-1][1] == sym and a <= windows[-1][3]:
                    windows[-1][3] = max(windows[-1][3], b)
                    windows[-1][4].append(t)
                else:
                    windows.append([day, sym, a, b, [t]])
        hms = lambda x: datetime.fromtimestamp(x, ET).strftime("%H:%M:%S")
        log.info("SECDUMP plan: %d buys, %d windows, %d minutes to read", len(buys),
                 len(windows), sum(int((b - a + 59) // 60) for _, _, a, b, _ in windows))
        gap = 60.0 / SEC_DUMP_RPM if SEC_DUMP_RPM else 0.0
        for day, sym, a, b, times in windows:
            spans = [(t - SEC_DUMP_TICKS_BEFORE, t + SEC_DUMP_TICKS) for t in times]
            nt = nq = ns = lost = 0
            m = a
            while m < b:
                e = min(m + 60, b)
                req = dict(symbol_or_symbols=sym, feed=self.feed,
                           start=datetime.fromtimestamp(m, timezone.utc),
                           end=datetime.fromtimestamp(e, timezone.utc))
                try:
                    tr = await asyncio.to_thread(self.hist_raw.get_stock_trades,
                                                 StockTradesRequest(**req))
                    await asyncio.sleep(gap)
                    qr = await asyncio.to_thread(self.hist_raw.get_stock_quotes,
                                                 StockQuotesRequest(**req))
                    await asyncio.sleep(gap)
                    packed = await asyncio.to_thread(_pack_seconds, tr, qr, sym, a, m, spans)
                except Exception as ex:
                    log.error("SECDUMP %s %s %s minute %d: %s", day, sym, hms(a), (m - a) // 60, ex)
                    lost += 1
                    m = e
                    await asyncio.sleep(max(gap, 1.0))
                    continue
                tr = qr = None
                pieces = packed[0]
                for i, part in enumerate(pieces):
                    log.info("SECDUMP %s %s %s %d %d/%d %s", day, sym, hms(a), int(m - a),
                             i + 1, len(pieces), part)
                nt, nq, ns = nt + packed[1], nq + packed[2], ns + packed[3]
                m = e
            log.info("SECDUMP %s %s %s-%s: %d buys (%s), %d trades, %d quotes, %d seconds, "
                     "%d minutes lost", day, sym, hms(a), hms(b), len(times),
                     " ".join(datetime.fromtimestamp(t, ET).strftime("%H:%M:%S.%f")[:12]
                              for t in times), nt, nq, ns, lost)
        log.info("SECDUMP done: %d windows", len(windows))

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
    v36_entries: int = 0             # v36: buys of this name today
    v36_entry_bar_ts: object = None  # v36: the last closed candle at the last buy -
                                     # one buy a minute (by time: bars are capped at 400)
    v36_rip_ts: object = None        # v36: the latest rip's last candle (its start time)
    v36_rip_base: float = 0.0        # v36: the average minute's volume before that rip
    v36_first: float = 0.0           # v36: what the starter paid
    v36_why_at: float = 0.0          # v36: when its last "why not" line was logged
    v36_adds: int = 0                # v36: adds made to this position (V36_ADD1_*, V36_ADD2_*)
    v36_leash_from: float = 0.0      # v36: the short leash watches candles from here
    ten: tuple = ()                  # v36: the 10-second candle in progress
                                     # (bucket, open, high, low, close)
    tens: deque = field(default_factory=lambda: deque(maxlen=6))
                                     # v36: the last closed 10-second candles
    ten_break: bool = False          # v36: the short leash has fired since the buy
    ref_price: float = 0.0           # the previous session's close (the scanner) -
                                     # the day's gain is measured from it
    v37_prints: deque = field(default_factory=deque)
    v37_speed_prints: deque = field(default_factory=deque)   # v37: two windows of prints
    v37_stop_pct: float = 0.0        # v37: the stop's distance under the average
    v37_pace_at_buy: float = 0.0     # v37: shares in the 60 seconds before the buy
    v37_old_high: float = 0.0        # v37: a high a break must be confirmed over
    v37_high_ts: float = 0.0         # v37: when the last new high of the day traded
    v37_sold_px: float = 0.0         # v37: what the last sale of this stock got
    v37_sold_ts: float = 0.0         # v37: when it was
    v37_peak_after: float = 0.0      # v37: the best price since the grace ended
    v37_skip_logged: float = 0.0     # v37: when a "not running" skip was last logged
    v36_add_try_ts: float = 0.0      # v36: when an add was last tried
    v36_line: float = 0.0            # v36/v37: the whole / half dollar the stop sits
                                     # under (V36_LEVEL_STOP); 0 = none
    v36_line_since: float = 0.0      # ...since when the price has held past the next one
    v36_furious: bool = False        # v36: this position was bought furious
    mom_high_ts: float = 0.0         # v36/v37: when the last new high of the day printed
                                     # v37: (time, price, size) over V37_FAST_SECONDS
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

    async def dump_history(self, first, last):
        """Write this account's fills from `first` up to `last` (ET dates,
        `last` not included) into the log, HISTORY_PER_LINE to a line, with a
        total per day. Read-only."""
        start = datetime.fromisoformat(first).replace(tzinfo=ET)
        end = datetime.fromisoformat(last).replace(tzinfo=ET)
        fills = await self.broker.fills_between(start, end, pages=HISTORY_PAGES)
        days = {}
        for t, sym, side, q, px in fills:
            days.setdefault(datetime.fromtimestamp(t, ET).date().isoformat(), []).append(
                (t, sym, side, q, px))
        log.info("[%s] history %s..%s: %d fills on %d days", self.name, first, last,
                 len(fills), len(days))
        for day, rows in sorted(days.items()):
            bought = sum(q * px for _, _, side, q, px in rows if side == "buy")
            sold = sum(q * px for _, _, side, q, px in rows if side == "sell")
            log.info("[%s] history %s: %d fills, %d stocks, bought $%.2f, sold $%.2f",
                     self.name, day, len(rows), len({r[1] for r in rows}), bought, sold)
            for k in range(0, len(rows), HISTORY_PER_LINE):
                log.info("[%s] history %s #%d: %s", self.name, day, k // HISTORY_PER_LINE + 1,
                         "; ".join("%s %s %s %g@%.4f" % (
                             datetime.fromtimestamp(t, ET).strftime("%H:%M:%S"),
                             side[0].upper(), sym, q, px)
                             for t, sym, side, q, px in rows[k:k + HISTORY_PER_LINE]))
        return fills
    log_as = None           # a copy of another strategy: its "[vNN]" lines say our name

    def __init__(self, broker: Broker, data: MarketData):
        self.broker = broker
        self.data = data
        self.log = _Named(log, {"name": self.name, "as": self.log_as})
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

    def seed_high(self, s: SymState, high: float):
        """The real high of the day, read from today's bars - a restart must
        not forget the morning. v37 reads day_high, v36 hod_closed. SXTC
        2026-10-07 9:29:39: after the 9:20 restart v36 knew only the candles
        since then and bought $3.23 as a "new high" on a day already up to
        $7.12."""
        if high and high > 0:
            s.day_high = max(s.day_high, high)
            s.hod_closed = max(s.hod_closed, high)

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
               "v35": V35_MAX_POSITION_PCT,
               # v36 buys to 25% of equity on the way up; a runner it holds
               # keeps growing past that, as v35's does.
               "v36": V35_MAX_POSITION_PCT,
               "v36b": V35_MAX_POSITION_PCT,
               "v37": max(0.60, V37_ACCEL_MAX_PCT + 0.10)}.get(
                   self.name, MAX_POSITION_PCT)   # 40% (65% furious), grown by a run
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
                    self.note_skipped(s, price, conds)
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

    def note_skipped(self, s: SymState, price, conds):
        """A print that may not set the price or trigger anything."""
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
                  cap: float = None, floor: float = None, sweep: float = None,
                  keep: bool = False) -> int:
        """Fills counted from the BROKER, never from the order reply.

        A cancel racing a fill used to report "got nothing" and the next attempt
        bought the whole clip again - a $600 slot became $3,050 that way.

        cap: how far over ref the buy may pay (BUY_CHASE_CAP when not given).
        sweep: None, or the cents over the ask of buy_sweep's orders (0.0 = at
        the ask, BUY_AT_ASK).
        """
        cap = BUY_CHASE_CAP if cap is None else cap
        start = await self.broker.qty(symbol)
        if start is None:
            # Without a starting count no fill can be measured, and guessing 0
            # double-counts anything already held. Do not buy blind.
            log.error("[%s] cannot read %s position - not buying", self.name,
                      symbol)
            return 0
        if sweep is not None:
            got, why = await self.buy_sweep(symbol, shares, ref, cap, floor, sweep, keep)
            last = start + got
        elif FAST_BUY:
            got, why = await self.buy_fast(symbol, shares, ref, cap, floor)
            last = start + got
        else:
            last = await self.buy_chase(symbol, shares, ref, cap, start)
            why = "the chase ended"
        await self.broker.cancel_open(symbol)     # nothing of ours left working
        end = await self.broker.qty(symbol)
        if end is None:
            end = last
        filled = max(0, int(end - start))
        if filled and not start and NEWS_LOG:  # information only (r34.36)
            try:
                log.info("[%s] CONTEXT %s: %s", self.name, symbol, context_line(symbol))
            except Exception:
                pass
        if filled < shares:
            # EVERY MISS IS LOGGED. A buy that came back empty used to leave no
            # line at all, so how often the bot missed a runner was unknowable.
            log.info("[%s] %s BUY SHORT - wanted %d, got %d at a limit up to "
                     "%.4f: %s", self.name, symbol, shares, filled,
                     ref * (1 + cap), why)
        return filled

    def buy_limit(self, ask, ceiling) -> float:
        """The limit for one try of the fast buy: a little over the ask - AT the
        ask for BUY_AT_ASK."""
        if self.name in BUY_AT_ASK:
            return min(ask, ceiling)
        return min(ask * (1 + FAST_BUY_OVER_ASK), ceiling)

    async def buy_sweep(self, symbol, shares, ref, cap, floor=None, cents=0.20,
                        keep=False):
        """V37_SWEEP: a limit at the ask plus `cents`, filling at once; what is
        left unfilled is tried again at the new ask - for V37_SWEEP_SECONDS or
        V37_SWEEP_TRIES orders, never over the safety net (ref x (1 + cap))
        and never at or under the old high (`floor`). Returns (shares, why)."""
        top = round(ref * (1 + cap), 2) if cap != float("inf") else float("inf")
        got, why = 0, "no order sent"
        deadline = time.monotonic() + V37_SWEEP_SECONDS
        budget = getattr(self.broker, "orders_in_last_minute", None)
        for _ in range(1 if keep else V37_SWEEP_TRIES):   # keep: the next print retries
            if budget and budget() >= ORDER_BUDGET:
                return got, "the order budget: %d orders in the last minute" % budget()
            if got >= shares:
                break
            if time.monotonic() > deadline:
                return got, "out of time (%.0fs) - the move left us behind" % (
                    V37_SWEEP_SECONDS)
            ask = await self.data.quote(symbol, "ask") or ref
            if floor and ask <= floor:
                return got, "the ask %.4f is back at the high %.4f - no buy under it" % (
                    ask, floor)
            if ask > top:
                return got, "the ask %.4f is past the safety net %.4f" % (ask, top)
            limit = round(min(ask + cents, top), 2)
            n = await self.broker.send(symbol, shares - got, OrderSide.BUY, limit,
                                       V37_SWEEP_WAIT)
            if n < 0:
                return got, "the broker refused the order"
            got += n
            why = "filled at up to %.4f (the ask + %.2f)" % (limit, cents)
        return got, why

    async def buy_fast(self, symbol, shares, ref, cap, floor=None):
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
            if floor and ask <= floor:
                # WETO 2026-10-07 9:52: one print a cent over the $1.32 high,
                # then the reloads followed the ask down and filled at $1.26 -
                # under the high it was buying the break of.
                return got, ("the ask %.4f fell back to the high %.4f - no buy "
                             "under it" % (ask, floor))
            limit = round(self.buy_limit(ask, ceiling), 2)
            if floor:
                limit = min(limit, ceiling)
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

    async def sell(self, symbol: str, shares: int, ref: float, deep: bool = False) -> int:
        """Uncapped chase down - a stop must always get out. Clamped to what
        we really own, so it can never be rejected for shorting."""
        # Clear our own working orders before trying to get out. A resting buy
        # order on this symbol will have the sell rejected as a wash trade.
        cleared = await self.broker.cancel_open(symbol)
        start = await self.broker.qty(symbol)
        if start is None:
            start = float(shares)
        want = min(int(shares), int(start))
        if want <= 0:
            return 0
        market = SELL_MARKET_RTH and regular_hours()
        first = True
        for _ in range(CHASE_ATTEMPTS):
            # EVERY pass, not just the first. The old code cancelled once above
            # and then submitted a fresh limit sell on each pass without
            # clearing the previous unfilled one. Two or three passes and two or
            # three resting sells each reserved shares, held_for_orders climbed
            # to the whole position, available fell to 0, and the bot strangled
            # its own exit with its own orders.
            # The first pass, with nothing of ours working a moment ago, goes
            # straight out: three broker round trips fewer (the owner, 10-07:
            # "as fast as possible").
            if first and not cleared and start is not None:
                first = False
                now = start
            else:
                first = False
                await self.broker.cancel_open(symbol)
                if not await self.broker.wait_clear(symbol):
                    continue                   # never a sell on top of our own order
                now = await self.broker.qty(symbol)
            if now is None:
                await asyncio.sleep(CHASE_PAUSE)  # unknown is not "none sold"
                continue
            sold = start - now
            remaining = int(want - sold)
            if remaining <= 0:
                break
            bid = await self.data.quote(symbol, "bid") or ref
            limit = round(max(bid * (1 - (SELL_DEEP if deep else 0.005)), 0.01), 2)
            if market:                         # 9:30-4: at market, always
                log.info("[%s] %s SELL %d at MARKET", self.name, symbol, remaining)
                got = await self.broker.send_market(symbol, remaining,
                                                    OrderSide.SELL, limit)
                if getattr(self.broker, "market_refused", False):
                    market = False             # e.g. a half day: limits from here
            else:                              # premarket / after hours: limits only
                log.info("[%s] %s SELL %d at a limit %.2f (bid %.4f)", self.name, symbol,
                         remaining, limit, bid)
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
        sold = await self.sell(s.symbol, shares, s.last_price,
                               deep=(getattr(s, "entry_kind", "") == "accel"
                                     or getattr(s, "v36_furious", False)))
        if not sold and await self.broker.qty(s.symbol) == 0:
            # NOTHING LEFT TO SELL: sold elsewhere. CPHI 10-07 2:12pm - during a
            # deploy the old process sold the position the new one had just
            # adopted, and the new one tried to sell 0 shares every print.
            log.warning("[%s] %s: the broker holds none - already sold elsewhere; "
                        "closed here, nothing booked", self.name, s.symbol)
            self.clear(s)
            return
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
        # v36 does not cut size on small floats (it wants them): no line.
        if V31_FLOAT_SIZING and type(self).float_mult is V31.float_mult:
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

    def confirm_tolerance(self) -> float:
        """How far under the trigger the ask may sit and still back a buy."""
        return CONFIRM_TOLERANCE

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

    async def entry_buy(self, s, shares, price, cap) -> int:
        """The order behind an entry - V36 sends a furious one as one fast order."""
        return await self.buy(s.symbol, shares, price, cap)

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
            if ask is not None and ask < trigger - self.confirm_tolerance():
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

        filled = await self.entry_buy(s, shares, price, cap)
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

    def live_emas(self, s, price):
        """(EMA9, EMA20, EMA12, EMA26) as the owner's chart draws them: with the
        forming candle at `price` (V36_TREND_LIVE), not only the closed ones.
        BIYA 2026-10-07 4:13:44-4:14:00: "NO TREND" every 5 seconds on the 4:12
        candle's MACD of -0.0002 while the price went $2.25 -> $2.76."""
        if not V36_TREND_LIVE or not price:
            return s.ema9, s.ema20, s.ema12, s.ema26
        return tuple(e + 2.0 / (n + 1) * (price - e) if e else e
                     for e, n in ((s.ema9, 9), (s.ema20, 20), (s.ema12, 12), (s.ema26, 26)))

    def trend_ok(self, s, price) -> bool:
        vwap = self.vwap(s)
        e9, e20, _, _ = self.live_emas(s, price)
        return vwap > 0 and price > vwap and price > e9 > e20

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


# ----------------------------------------------------------------------------
# V36 - THE OWNER'S PLAYBOOK
# ----------------------------------------------------------------------------
# Written 2026-10-05/06 from how the owner traded by hand, February to June
# 2026, for $5-10k a month with 60-65% of trades winning (memory/playbook.md;
# the numbers, and which are still guesses: memory/rules.md). Built on v35 -
# the leaders' pullback, with the owner's four filters - with the owner's own
# choice of stock, entry, size and exit in place of v35's:
#   WHICH STOCK  where the crowd is NOW: the biggest share of the dollars
#                traded on the scanner's list in the last few minutes, held a
#                couple of minutes. Not the day's top gainer - "a stock up 120%
#                that slowed loses to one up 30% that is ripping".
#   READY        a rip: two green minutes adding 5% or more (or one minute of
#                5%), each on 3x the volume of the minutes before, on real
#                money - a thin stock is left alone however fast it runs - and
#                no long upper wick. The run stays alive as long as its volume
#                does - no clock.
#   THE BUY      after the rip, the green-red pattern (1c over the red's open,
#                stop at the red's low), or the high of the day breaking with
#                green candles stacking on rising volume. Above VWAP and the 9
#                EMA, the 9 over the 20, MACD over zero. The tape at least 60%
#                at the ask and no more than 40% at the bid. Never banned for
#                running: "that's where the money is made".
#   SIZE         ease in: a tenth of a full position, so a shakeout costs
#                little - and the starter gets room: only the red's low takes it
#                out. Then keep adding as the stock proves it is moving: to half
#                at +15 cents, to a full position at +20 cents.
#   THE EXIT     once added to, a short leash - out when a 10-second candle
#                closes red under the lows of the two before it; a long leash
#                once up 10%; after each add the floor rises to breakeven.
#   AGAIN        back in on a new rip or a new high of the day, as long as the
#                stock keeps running, each time small.
V36_MAX_FLOAT = 20_000_000      # float this many shares or less (a name not in
                                # the float list is allowed)
V36_MIN_DOLLARS = 250_000       # each rip minute traded at least this many dollars
V36_CROWD_MINUTES = 5           # the crowd: share of the list's dollars traded in
                                # the last N minutes
V36_CROWD_TOP = 2               # trade only the top N
V36_CROWD_HOLD_MIN = 2          # ...after it has held a top spot N minutes
V36_GAINER_TOP = 2              # OR one of the day's top N gainers (from the
V36_GAINER_MIN_DOLLARS = 1_000_000  # previous close) with at least this many dollars
                                # traded in the crowd window. The owner, 10-06:
                                # 60-70% of the stocks they pick are the day's top
                                # gainer with news; sometimes the crowd moves to a
                                # lower one picking up speed. Either will do.
V36_RIP_PCT = 0.05              # two green minutes adding this much
V36_RIP_ONE_PCT = 0.05          # or one green minute adding this much
V36_RIP_VOL_MULT = 3.0          # each rip minute on this many times the average
V36_RIP_BEFORE = 5              # ...of this many minutes before it
V36_ALIVE_BARS = 3              # THE RUN IS ALIVE WHILE THE VOLUME IS: the last N
V36_ALIVE_MULT = 2.0            # minutes trade at this many times the volume before
                                # the rip. A run lasts 2 minutes or 40 - "what
                                # dictates that is the volume" (the owner, 10-06).
V36_PICKUP_MULT = 2.0           # the high of the day breaking: its candle on this
                                # many times the volume of the 5 minutes before
V36_WICK_MAX = 0.5              # the rip's last candle: upper wick at most this
                                # share of its range ("a high retreat")
V36_TAPE_SECONDS = 30           # the tape window at the buy
V36_TAPE_GREEN = 0.60           # at least this share of shares at the ask
V36_TAPE_RED = 0.40             # no more than this share at the bid
V36_TAPE_MID_ASIDE = True       # ...of the shares at the ask OR the bid: prints
                                # between them set aside. The playbook: "green
                                # outweighing red is what matters". 2026-10-06: at
                                # the day's buys 26-54% of all shares were at the
                                # ask and 27-42% between - 60% of ALL never came.
V36_RIP_SKIPS_HOLD = True       # a stock that ripped in its last 2 closed minutes
                                # is the crowd at once, without the hold - the hold
                                # cost AIXI at 4:17 (2.85, ran to 4.47) and IPDN
                                # at 7:29 on 2026-10-06
V36_WHY_NOT = True              # a "why not" line, a minute apart, for the top 3
                                # crowd names and the top gainers; 5s apart once the
                                # price is at a trigger and a check says no
V36_POSITION_PCT = 0.25         # a full position: this share of equity
V36_STARTER = 0.10              # the first buy: this fraction of a full position
# KEEP ADDING AS IT MOVES: once up ADD1_AT from the starter, on a new high with
# the tape still green, to ADD1_TO of a full position; at ADD2_AT, to ADD2_TO.
# V36_ADD_CENTS: the AT numbers are dollars (0.15 = 15 cents) instead of a
# share of the price - the owner, 10-06: "3% on a $10 stock is 30 cents
# before you start adding; by then the run has probably fizzled out".
# Replayed 09-28..10-05 (fills 0.5% worse; total / the five days without SAIQ):
#   +3% to half, +6% to full          +$1,717 / -$1,185
#   +15c to 25%, +20c to 75%          +$1,844 /   +$129
#   +15c to half, +20c to full        +$2,949 /   +$538   <- the owner's, kept
#   +1.5% to half, +2% to full          +$787 / -$1,561
V36_ADD_CENTS = True
V36_ADD1_AT = 0.15
V36_ADD1_TO = 0.50
V36_ADD2_AT = 0.20
V36_ADD2_TO = 1.00
# 2026-10-06 (the owner): APUS 1:49pm ripped 7.36 -> 8.12 in a minute on 608k
# shares with v36 holding a 56-share starter. Add 1 asked up to 7.62 with the
# ask at 8.01, add 2 up to 7.68 with the ask at 7.97: nothing filled, and both
# misses used up the add steps, so it never tried again - +$41 instead of
# roughly +$200 on a full position. "If we did not catch it, go right after it."
V36_ADD_RETRY = True            # a miss does not use up the add: try again on the
V36_ADD_RETRY_SEC = 2.0         # next new high, this long after the miss
V36_ADD_HOLD_GIVE = 0.01        # ...a print this far under the new high resets it
V36_ADD_HOLD_SEC = 2.0          # an add waits for the price to hold at or over its
                                # level this long, no print under it (the owner,
                                # 10-07: "add after the new high holds, about two
                                # seconds" - APUS 10:25:08 added at $9.56, the floor
                                # moved to the average, sold 5 seconds later). 0 = off
V36_ADD_FROM_ASK = True         # an add's limit counts from the current ask when it
                                # is above the print (prints can lag in a rush)
V36_ADD_RIP_PAY = 0.10          # ripping (busiest minute of its day): an add may pay
                                # up to half of the last minute's move, at most this
                                # (as v37's entries); 0 = off
# 2026-10-06 (the owner): the same score as v37 at v36's entries - its pullback
# rule bought APUS 11:35 after a 64% top wick and a big red candle (-$38), and
# 1:51 after a 69% top wick at the top of the blow-off (-$16).
V36_SCORE_MIN = 0               # 0 = off; else the points needed (of 15)
# 2026-10-06 (the owner): the candles - green, then red, buy back over the red's
# open - are the introduction, for the first and second buys of a stock (or
# after it has slept for hours). After that: only the high of the day plus 5
# cents, jump right at it - if the moment scores (V36_SCORE_MIN). "I don't
# want it to run into a ceiling that is just the high of the day."
# 10-07 (the owner, SPAI 8:13 re-entry @ $4.99 under the $5.10 high, LPCN 7:18
# @ $3.42 under $3.50): "a re-entry has to go past the high of the day".
V36_SETUP_BUYS = 1              # >0: candle setups only for this many buys of a
                                # stock a day; after that the high of the day only
V36_HOD_PLUS = 0.05             # ...plus this over the highest closed minute
V36_SLEEP_MIN = 120             # a stock with no new high this long: setups again
# 2026-10-06, to test (the owner: "only what benefits v36"). In the replay, 84
# of 153 v36 trades never reached the first add and lost $1,718 (stopped at a
# median -4.6%); the 69 that added made +$3,635. Fewer bad starters, smaller
# losses on the ones that fail - and decide exits on fresh prices (today's
# v36 stops acted on prints 2.5-7s old: APUS 11:32, AVBP 12:19, DLXY 10:46).
V36_WICK_VETO = 0.0             # >0: no buy when the last closed candle's top wick
                                # is more than this share of it (APUS 11:35, 1:51)
V36_MAX_STOP = 0.0              # >0: the first stop no further than this under
                                # the trigger (the pullback's low was up to 9% away)
V36_FRESH_EXITS = False         # stops and the trail decide only on prints under
                                # V37_FRESH_SECONDS old (as v37 since r34.8)
# 10-07 live, the owner reading the charts:
# - LPCN 7:21-7:35: through $3.50 to $3.99 as the #1 name ($8-16M per 5 min),
#   both v36s logged "NO: 6 buys today" every minute - the six spent on whipsaws.
# - SPAI 8:09: "rip then red pullback" bought - but the red fell $4.92 -> $4.41,
#   under the green's open $4.58: the rip erased, not a pullback.
# - BIYA 4:20 (add @ $2.51), LPCN 7:18 ($3.42), SPAI 8:12 (add @ $5.08): buys at
#   a whole / half dollar - "natural resistance; wait for it to cross, about 5
#   cents, and hold a moment".
V36_LEADER_NO_CAP = True        # the #1/#2 name making a new high of the day is not
                                # held to V36_MAX_ENTRIES
V36_FAILED_RIP = True           # a red "pullback" under the rip candle's open is a
                                # failed rip: no buy on it
V36_PULLBACK_VOL = 1.0          # >0: a red of the pullback trading this share of the
                                # green's volume or more is no light pullback (0 = off)
V36_LEVELS = True               # no buy or add from V36_LEVEL_BELOW under a $x.00 or
V36_LEVEL_BELOW = 0.03          # $x.50 level to V36_LEVEL_PAST over it - and past it,
V36_LEVEL_PAST = 0.05           # only once the price has stayed past that long
V36_LEVEL_HOLD_SEC = 3.0
# 10-07 ~12:20 (the owner, on DKI 11:37: v36's first stop sat at the last
# minute's low, 16.6% under the buy, and one $406 starter lost $71):
V36_STARTER_RISK = 0.03         # "B": a starter is sized so its first stop costs at
                                # most this share of a normal starter - 3% of $406 is
                                # $12; a far stop buys fewer shares. 0 = off
V36_LEVEL_STOP = True           # the stop sits under the whole / half dollar under the
V36_LEVEL_GIVE = 0.01           # buy, this far under it - "it goes under three, you sell
                                # immediately; you don't wait for 2.87" - and moves up to
                                # each level the price then clears by V36_LEVEL_PAST and
                                # holds V36_LEVEL_HOLD_SEC: a support. 10-07 ~12:50 (the
                                # owner): "bought at 6.15, it went to 6.30 and is coming
                                # back - the stop should end at 5.98 or 5.99, not 5.80";
                                # "at 1.65 retracing to 1.50 - if it breaches 1.49, 1.48,
                                # it should sell". The stop only ever tightens. 7 days
                                # replayed, 1c beat 2c and 5c for all three (r34.22: 5c)
V36_FURIOUS_FULL = True         # furious (speeding): the FULL position in the first buy -
                                # "I enter with a full position on the very first hit; if
                                # I miss, I try again"...
V36_FURIOUS_STOP_MAX = 0.08     # ...its stop no further than this under the buy (v37's
                                # most), and the 10-second leash on it at once...
V36_FURIOUS_STOP_CENTS = 0.10   # ...and no further than this (dollars) under what it
                                # paid - "not the 8%, too big; if the stock drops 10
                                # cents from the entry, close it, and get back on it as
                                # soon as it moves above the high of the day again" (the
                                # owner, 10-07 ~1pm). v36, v36b and v37's furious buys
V36_FURIOUS_EVEN_AT = 0.30      # ...once up this much (dollars) over the buy, never
                                # back under the buy - "up thirty cents and back to it,
                                # cut it off there instead of a loss" (the owner, 10-07
                                # ~1pm)...
V36_FURIOUS_GIVEBACK = 0.30     # ...and from there out on giving back this share of the
                                # gain from its high ("thirty percent of the gain").
                                # 0 = off. Replaces r34.22's "up 30%, a third back".
V37_FURIOUS_EXIT = True         # v37's furious buys (speed >= V37_FURIOUS_SPEED): the same
BID_STOP = True                 # a position's stop also fires when the live market -
                                # the middle of the bid and ask - is at or under it, not
                                # only on a print the bot accepts (SXTC 10-07 1:40pm:
                                # stop $7.65, first counted print $7.49). The middle, not
                                # the bid: a premarket spread can be wider than a 10c stop
V36_FURIOUS_SWEEP = True        # furious: the buy is v37's fast buy - one order at the
                                # ask + 20c (30c from $10), filled or dropped within
                                # V37_SWEEP_WAIT; the next furious print tries again,
                                # V37_RETRY_GAP apart - not the 6-second loop that paid
                                # $8.90 on an $8.75 print with the market already back
                                # under the stop (SXTC 10-07 1:59pm; the owner's "A")
V36_NO_RTH_BUYS_ON = ("2026-10-07",)   # these days (ET): no new v36/v36b buys 9:30-4
                                # (the owner, 10-07 2:50pm, after -7.8% / -5.7%: "stop
                                # v36/v36b buys until 4pm"); premarket and after hours,
                                # and v37, unchanged
V36_FURIOUS_ALL = True          # furious: EVERY entry check set aside - the levels, the
                                # wick, the re-entry speed, the score, the 5% over the
                                # trigger, and no candle pattern needed (a new high over
                                # the last minute is the trigger). The never-rules stay:
                                # hours, 9:29-9:31, the scanner's list and price band, the
                                # float, the quote backing the trigger (and no buy once the
                                # ask is back at the old high), the last candle not red,
                                # FAST_BUY_5S_UP and FAST_BUY_MAX_SPREAD (r34.29), the
                                # account and position caps, the day's loss halt
FAST_BUY_5S_UP = True           # a fast buy - v36/v36b furious, v37 accelerating - goes
                                # out only while the price is higher than 5 seconds ago
                                # (the owner, 10-08: "to buy in five seconds when the
                                # market went down - make sure that does not happen").
                                # BIAF 8:06:43 went furious at 5s -0.7% and bought the
                                # top, -$382; KAPA 9:34:48 at 5s +0.0%, -$225. Flat or
                                # down, or no print 5 seconds back: no buy - the next
                                # print tries again
FAST_BUY_MAX_SPREAD = 0.10      # ...and only while the ask is no more than this over the
                                # bid - the furious stop's 10 cents. Wider, and what we
                                # pay is past the stop the moment we own it: BIAF 8:06:44
                                # paid $7.49 with the bid $6.82 and was sold 8 ms later;
                                # 12 trades like it on 10-08, -$1,519. No quote: no buy.
                                # 0 = off
# To judge in the replay (the owner: "once it runs, don't cut it until it has
# given back half of its gain"; "the speed was not respected"):
# SXTC 8:17: both v36s bought @ $4.83 / $4.78 on a new-high trigger of $2.77 -
# 74% over it, after the spike - v36's stop $2.21 (54% away), v36b's 3% cap,
# taken from the trigger, $2.69 (44% away).
V36_CHASE_MAX = 0.05            # no buy more than this over the trigger: the move
                                # already happened (0 = off, as before)
V36_RUNNER_HALF = False         # after an add: out on giving back half the gain since
                                # the starter, in place of the floor at the average
                                # and the 10-second leash
V36_REENTRY_SPEED = 0.1         # >0: a re-entry needs the owner's speed this high
                                # (replayed on v36b: +$1,779 / +$519 vs +$1,037 / -$692)
V36_FLOOR_AVG = True            # after an add, the floor rises to: True = the
                                # position's average (breakeven), False = what the
                                # starter paid. Replayed 09-28..10-05: average
                                # +$3,270, starter -$204 - a full position that
                                # falls back to the starter's price loses ~4.5%.
V36_MAX_POSITIONS = 2
V36_TEN_SEC = 10                # the short leash's candles, in seconds
V36_TEN_GRACE = 10              # seconds after an add before the short leash acts
V36_LEASH_AT = 0.10             # up this much: the long leash instead
V36_LEASH_ABR = 2.0             # long leash: this many ABRs under the high
V36_MAX_ENTRIES = 0             # buys per name per day; 0 = no limit (the owner, 10-08:
                                # "they can go there as many times as possible" - FLYE
                                # 7:22-7:25 spent the six on whipsaws, then 7:26-7:40
                                # "NO: 6 buys today" as the #1 name ran $2.23 -> $3.60;
                                # as V37_MAX_ENTRIES since 10-06)
# THE BIG MOVES (the owner, 10-07: "the other fixes are small potatoes - if we
# miss these moves the program will not advance"):
V36_TREND_LIVE = True           # trend checks with the forming candle at the live
                                # price, as the chart draws them (BIYA 4:13)
V36_CROWD_TRADING = True        # 9:30-4:00 the crowd counts the last V36_CROWD_MINUTES
V36_CROWD_SPAN_MIN = 30         # minutes the stock TRADED, within this span - after
                                # a halt it is not "$0k" (DKI 10:36 and 10:50).
                                # Premarket has no halts (the owner): the clock window
V36_FURIOUS = True              # the owner's speed at V37_FURIOUS_SPEED on real money
                                # counts as the crowd and lifts the buy cap (BIYA 8:20)
V36_FURIOUS_SKIPS = True        # ...and sets the trend (VWAP, EMA, MACD), tape and room
                                # checks aside: "all the filters tossed aside in a
                                # movement like this" (the owner, 10-07)
V36_PAY_UP_ABR = 1.0            # a buy may pay this many ABRs over the trigger...
V36_PAY_UP_MAX = 0.05           # ...never more than this (BUY_CHASE_CAP at least)
V36_CONFIRM_TOLERANCE = 0.01    # the ask may sit this far under the trigger
# READ-ONLY, ONE-OFF (the owner, 10-06 night: find the first strategies'
# trades). Alpaca's website lists only the last 30 pages of an account's
# orders (back to 10-02). At start-up each account writes its fills from the
# first date up to the second (ET, the second not included) into the log, in
# the background - v27 (T6HH) from 09-24, v24 (AUES) and v30 (P28T) from
# 09-25. () = off.
HISTORY_DUMP = ()               # read 10-07 (r34.14); off
# READ-ONLY, ONE-OFF (the owner, 10-08: "have the bot generate that for us for
# v37 today"): at start-up, every trade and every change of the bid / ask in
# these windows (ET, on TICK_DUMP_DAY) is read from the data service and written
# to the log in packed TICKDUMP lines - v37's 19 trades of 10-08, 30 seconds
# before each buy to minutes after, so its exit can be replayed print by print.
# No orders, no trading state touched. () = off.
TICK_DUMP_DAY = "2026-10-08"
TICK_DUMP = ()                  # read once by r34.32 (10-08 3:26pm); saved in
                                # replay/live/2026-10-08_ticks/tickdump_v37.txt.gz
TICK_DUMP_CHARS = 3500          # characters of rows in one log line
# READ-ONLY, ONE-OFF (the owner, 10-08: run the exit table "on today and the
# last two days" for v36, v36b and v37 - second by second, not minute bars): at
# start-up each account writes its fills on SEC_DUMP_DAYS into the log (as
# HISTORY_DUMP); then, around every buy of the three, SEC_DUMP_BEFORE seconds
# before to SEC_DUMP_AFTER after, the market is read from the data service a
# minute at a time (SEC_DUMP_RPM requests a minute at most) and written to the
# log: every trade and every change of the bid / ask from SEC_DUMP_TICKS_BEFORE
# before each buy to SEC_DUMP_TICKS after it, and for the whole window one row a second
# (open, high, low, close, volume and count of the prints that count, the bid
# and ask at the second's end, the second's lowest bid). zlib + base64, one
# SECDUMP line per TICK_DUMP_CHARS (replay/research/secread.py reads them back).
# No orders, no trading state touched. () = off.
SEC_DUMP_DAYS = ()              # read once by r34.35 (10-08 6:03-7:29pm, 76 windows,
                                # none lost); saved in replay/live/2026-10-08_secdump
SEC_DUMP_BEFORE = 300           # one row a second from 5 minutes before a buy (how
                                # early it could have got in: BIAF 10-08 ran 8:05-8:14,
                                # v37 bought 8:09:41) ...
SEC_DUMP_AFTER = 1800           # ...to 30 minutes after it
SEC_DUMP_TICKS_BEFORE = 30      # every print and quote from this long before a buy...
SEC_DUMP_TICKS = 60             # ...to this long after it
SEC_DUMP_RPM = 100
HISTORY_PAGES = 40              # 500 orders a page
HISTORY_PER_LINE = 25           # fills per log line

# THE NEWS AND BORROW LOG (r34.36; the owner, 10-08: Alpaca publishes hard to
# borrow and the news - "just let them go into the log"). INFORMATION ONLY: no
# rule reads any of it, nothing trades differently. News that looks good often
# fizzles once the market has read it through; the log lets it be judged later.
#   BORROW   - the list's names as they come in: hard to borrow (Alpaca's
#              easy_to_borrow is false) or not shortable; any change in the day.
#   NEWS     - the list's names checked every NEWS_SECONDS; a name's first
#              check of the day reaches back to the last session's 4pm close.
#              Each headline once, with its age and its NEWS_FLAGS words.
#   CONTEXT  - at each opening buy: the borrow status and the day's headlines.
#   NEWSDUMP - once, at a start-up on a NEWS_DUMP_ON date: each account's fills
#              from the first to the last of NEWS_DUMP_DAYS (as HISTORY_DUMP)
#              and the headlines of every stock bought each day, from the 4pm
#              close before to 8pm. () = off.
NEWS_LOG = True
NEWS_SECONDS = 60               # how often the list's names are checked
NEWS_BATCH = 40                 # names a request
NEWS_RPM = 60                   # requests a minute at most, the dump included
NEWS_OVERLAP = 900              # each check reaches 15 minutes back (late stories)
NEWS_KEEP = 3                   # headlines quoted in a CONTEXT line
NEWS_FLAGS = (                  # a word's start must match (\b), any case
    ("offering", ("offering", "registered direct", "private placement",
                  "at-the-market", "at the market", "warrant", "shelf", "priced",
                  "pricing", "dilut", "securities purchase agreement")),
    ("reverse split", ("reverse split", "reverse stock split", "share consolidation")),
    ("listing", ("delist", "nasdaq notice", "minimum bid", "deficiency", "compliance")),
    ("fda / trial", ("fda", "phase 1", "phase 2", "phase 3", "clinical", "trial")),
    ("deal", ("merger", "acquisition", "acquire", "partnership", "contract",
              "collaboration", "license", "purchase order", "agreement")),
    ("earnings", ("earnings", "quarter", "results", "revenue", "guidance")),
    ("squeeze", ("squeeze", "short interest")),
    ("halt", ("halt",)),
)
NEWS_DUMP_DAYS = ("2026-10-01", "2026-10-08")   # first and last ET date, both read
NEWS_DUMP_ON = ("2026-10-08", "2026-10-09")     # start-ups on these ET dates only

BORROW: dict = {}               # sym -> (easy to borrow, shortable), the scanner's asset list
NEWS: dict = {}                 # sym -> [(epoch, source, headline, flags)] today, oldest first
NEWS_FROM: dict = {}            # sym -> epoch its headlines are read from today

_NEWS_RX = [(name, re.compile("|".join(r"\b" + re.escape(w) for w in words), re.I))
            for name, words in NEWS_FLAGS]


def news_flags(text) -> list:
    """The NEWS_FLAGS a headline (and its summary) carries."""
    return [name for name, rx in _NEWS_RX if rx.search(text or "")]


def news_since(day):
    """The 4pm close of the last weekday before ET date `day`."""
    d = day - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return datetime(d.year, d.month, d.day, 16, 0, tzinfo=ET)


def borrow_text(sym) -> str:
    etb, short = BORROW.get(sym, (None, None))
    if short is False:
        return "not shortable"
    if etb is False:
        return "hard to borrow"
    if etb:
        return "easy to borrow"
    return "borrow unknown"


def _ago(seconds) -> str:
    m = max(0, int(seconds // 60))
    return "%dm" % m if m < 120 else "%dh" % (m // 60)


def context_line(sym, now=None) -> str:
    """What is known about `sym` besides its price: borrow and today's news."""
    now = time.time() if now is None else now
    parts = [borrow_text(sym)]
    if sym not in NEWS_FROM:
        parts.append("news not read yet")
        return " | ".join(parts)
    items = NEWS.get(sym, [])
    since = datetime.fromtimestamp(NEWS_FROM[sym], ET).strftime("%m-%d %H:%M")
    if not items:
        parts.append("no news since %s" % since)
        return " | ".join(parts)
    flags = sorted({f for it in items for f in it[3]})
    parts.append("%d headline%s since %s%s" % (
        len(items), "" if len(items) == 1 else "s", since,
        " (%s)" % ", ".join(flags) if flags else ""))
    for t, src, head, fl in items[::-1][:NEWS_KEEP]:
        parts.append("%s %s ago: %s" % (datetime.fromtimestamp(t, ET).strftime("%H:%M"),
                                        _ago(now - t), head[:140]))
    return " | ".join(parts)

# WHICH STRATEGY TRADES EACH ACCOUNT (the owner, 2026-10-06): v31's keys
# (T6HH, "v27-30k") run v36; v34's keys (V33_*, P28T, "V30-100k") run v37;
# v35's keys (AUES) run v36b (v36 with r34.13's changes; v35 until 10-06).
# Each can be changed in the environment with no code change: SLOT_V31 /
# SLOT_V34 / SLOT_V35 = v31, v34, v35, v36, v36b, v37 or off.
SLOT_DEFAULTS = {"v31": "v36", "v34": "v37", "v35": "v36b"}


def account_classes(env=None):
    """The strategy class for each account slot (None = off), by the slot's
    old name."""
    env = os.environ if env is None else env
    names = {"v31": V31, "v34": V34, "v35": V35, "v36": V36, "v36b": V36B,
             "v37": V37}
    out = {"v32": V32}
    for slot, default in SLOT_DEFAULTS.items():
        chosen = (env.get("SLOT_" + slot.upper()) or default).strip().lower()
        out[slot] = names.get(chosen)
    return out


class _Restore:
    """After a restart (a release restarts the bot): what each stock did
    today, read back from the account's filled orders - its buys of the day
    (the 0/0/1/2 confirmation and the v36 limit count them) and its last
    sale. APUS 10-06: bought at 9:51 and 10:22; the 10:21 release forgot
    both, so the 3rd and 4th buys (11:33, 11:36) waited for no candles."""

    async def restore_today(self):
        fills = await self.broker.fills_today()
        held, seen = {}, {}
        for t, sym, side, q, px in fills:
            d = seen.setdefault(sym, {"buys": 0, "sold": None})
            if side == "buy":
                if held.get(sym, 0.0) <= 0:
                    d["buys"] += 1              # bought while flat: a buy of the day
                held[sym] = held.get(sym, 0.0) + q
            else:
                held[sym] = held.get(sym, 0.0) - q
                if held[sym] <= 1e-6:
                    held[sym] = 0.0
                    d["sold"] = (t, px)
        for sym, d in seen.items():
            s = self.st(sym)
            s.v36_entries = max(s.v36_entries, d["buys"])
            if d["buys"]:
                s.traded_today = True
            if d["sold"] and not s.in_position:
                await self.restore_sale(s, *d["sold"])
        if seen:
            self.log.info("[%s] restored from today's orders: %s", self.name, ", ".join(
                "%s %d buy(s)%s" % (sym, d["buys"], " last sold %s at %.4f" % (
                    datetime.fromtimestamp(d["sold"][0], ET).strftime("%H:%M:%S"),
                    d["sold"][1]) if d["sold"] else "")
                for sym, d in sorted(seen.items())))

    async def restore_sale(self, s, t, px):
        pass


class _Momentum:
    """What v36 and v37 both read off the tape: the last two minutes of
    prints, the owner's speed, how far it moved, and the score of the moment
    (2026-10-06)."""

    def note_trade(self, s, price, size):
        super().note_trade(s, price, size)
        # Timed by when the print TRADED, not when it was read: a queue of
        # prints drained in a burst must not look like a stock moving fast.
        now = time.time()
        t = s.last_print_ts or now
        if price > s.day_high:
            s.mom_high_ts = t                   # a new high of the day
        cut = now - V37_FAST_SECONDS
        if t >= cut:                            # a print reported late stays out
            s.v37_prints.append((t, price, size))
        while s.v37_prints and s.v37_prints[0][0] < cut:
            s.v37_prints.popleft()
        if t >= now - 2 * V37_FAST_SECONDS:
            s.v37_speed_prints.append((t, price, size))
        while s.v37_speed_prints and s.v37_speed_prints[0][0] < now - 2 * V37_FAST_SECONDS:
            s.v37_speed_prints.popleft()

    def fresh(self, s) -> bool:
        """The print being decided on traded within V37_FRESH_SECONDS (a
        print with no trade time counts as fresh - the replay has none)."""
        return (not s.last_print_ts
                or time.time() - s.last_print_ts <= V37_FRESH_SECONDS)

    def pace(self, s) -> float:
        """Shares traded in the last V37_FAST_SECONDS (by when they traded)."""
        return sum(x[2] for x in s.v37_prints)

    def move(self, s, price) -> float:
        """How far the price is above the low of the last V37_FAST_SECONDS."""
        low = min((x[1] for x in s.v37_prints), default=0.0)
        return price / low - 1 if low > 0 else 0.0

    def speed(self, s, price) -> float:
        """The owner's speed: (P2 - P1) / P1 x (V2 / V1) over rolling
        V37_FAST_SECONDS windows. 0.0 until both windows have prints."""
        move, ratio = self.speed_parts(s, price)
        return move * min(ratio, V37_SPEED_VOL_CAP)

    def speed_parts(self, s, price):
        """(P2 - P1) / P1 and V2 / V1 - the price part and the volume part
        of the speed. (0, 0) until both windows have prints."""
        now = time.time()
        w = V37_FAST_SECONDS
        recent = [x for x in s.v37_speed_prints if x[0] >= now - w]
        before = [x for x in s.v37_speed_prints if now - 2 * w <= x[0] < now - w]
        if not recent or not before:
            return 0.0, 0.0
        p1 = before[-1][1]                      # the price a window ago
        v1 = sum(x[2] for x in before)
        v2 = sum(x[2] for x in recent)
        if p1 <= 0 or v1 <= 0:
            return 0.0, 0.0
        return (price - p1) / p1, v2 / v1

    def real_speed(self, s, price) -> float:
        """The owner's speed, but 0 unless the price part of it - up from a
        minute ago - is at least V37_SPEED_MOVE_MIN."""
        move, ratio = self.speed_parts(s, price)
        if move < V37_SPEED_MOVE_MIN:
            return 0.0
        return move * min(ratio, V37_SPEED_VOL_CAP)

    def ripping(self, s) -> bool:
        """The last 60 seconds traded more than any closed minute of the day
        so far - a true rip (XHG 9:39am 10-06: 2.4M shares after 1.9M)."""
        vols = [b.v for b in s.bars]
        return bool(vols) and self.pace(s) > max(vols)

    def five_sec(self, s, price):
        """The last 5 seconds of prints: (how far the price moved, dollars
        traded). The owner, 10-07: "how much the stock appreciated every five
        seconds" - logged with each furious decision, to set a number on it."""
        now = s.last_print_ts or time.time()
        old, dollars = None, 0.0
        for t, px, sz in reversed(s.v37_prints):
            if t < now - 5:
                old = px
                break
            dollars += px * sz
        return ((price / old - 1) if old else 0.0), dollars

    def speeding(self, s, price) -> bool:
        """The owner's speed at V37_FURIOUS_SPEED on ACCEL_DOLLARS in the last
        minute, the last candle not red - the moves that pay for the months."""
        if self.real_speed(s, price) < V37_FURIOUS_SPEED:
            return False
        if sum(x[1] * x[2] for x in s.v37_prints) < ACCEL_DOLLARS:
            return False
        return bool(s.bars) and not s.bars[-1].red

    def accelerating(self, s) -> float:
        """The owner's speed of the last closed minute when the minutes before
        a run are accelerating (ACCEL_*), else 0.0."""
        bars = s.bars
        n = ACCEL_BARS
        if len(bars) < n + 10:
            return 0.0
        for k in range(len(bars) - n, len(bars)):
            b, prev = bars[k], bars[k - 1]
            rng = b.h - b.l
            if (not b.green or rng <= 0 or b.h - b.c > ACCEL_TOP * rng
                    or b.c <= prev.c or b.v <= prev.v):
                return 0.0
        a, b = bars[-2], bars[-1]
        if b.v < ACCEL_VOL_STEP * a.v or b.c * b.v < ACCEL_DOLLARS:
            return 0.0
        normal = statistics.median(x.v for x in bars[-30:-n])
        if normal <= 0 or b.v < ACCEL_VOL_NORMAL * normal:
            return 0.0
        speed = (b.c / a.c - 1) * (b.v / a.v)
        return speed if speed >= ACCEL_SPEED else 0.0

    def rip_exception(self, s, price) -> bool:
        """Ripping, and fast enough to skip the score: the owner's speed at
        V37_RIP_SPEED or more (LPCN 6:33am 10-07 "ripped" at speed 0.07)."""
        if not self.ripping(s):
            return False
        return not V37_RIP_SPEED or self.real_speed(s, price) >= V37_RIP_SPEED

    def live_quote(self, s):
        """(bid, ask) of the streamed quote while under V37_QUOTE_AGE old."""
        q = s.quote
        if not q or len(q) < 3 or time.time() - q[2] > V37_QUOTE_AGE:
            return None
        return q[0], q[1]

    def off_quote(self, s, price) -> bool:
        """V37_PRINT_CHECK: the print is not the market - outside the live
        bid-ask by more than the tolerance. No live quote: it cannot say."""
        if not V37_PRINT_CHECK:
            return False
        q = self.live_quote(s)
        if not q:
            return False
        bid, ask = q
        tol = max(V37_PRINT_TOL_CENTS, V37_PRINT_TOL_PCT * price)
        return price > ask + tol or price < bid - tol

    def note_off_quote(self, s, price):
        last = getattr(self, "_off_quote_logged", None)
        if last is None:
            last = self._off_quote_logged = {}
        if time.time() - last.get(s.symbol, 0.0) >= 30:
            last[s.symbol] = time.time()
            bid, ask = self.live_quote(s) or (0.0, 0.0)
            self.log.info("[%s] IGNORED %s print %.4f - the market is %.4f x %.4f "
                          "(decides nothing)", self.name, s.symbol, price, bid, ask)

    def score(self, s, price, pullback=False):
        """V37_SCORE_MIN: how favourable the moment is, out of 15 points, and
        the parts - or (None, why) when it is no buy at all: a red last candle
        (the owner: "zero - we are not going to enter there", until the bots
        learn bounces off solid support) or a huge top wick on it.
          speed        4  the owner's speed - price change x volume change over
                          the last minute: 1 at 0.1, 2 at 0.2, 4 at 0.3
          last candle  2  green, closed in its top third (1: green, a bigger
                          wick - "two thirds up can still be favourable")
          wicks        1  top wicks not growing 3 candles in a row ("sellers
                          pushing it back"; one odd one is forgiven)
          bodies       1  green bodies not shrinking noticeably 3 in a row
                          (each under 3/4 of the one before; irregular is fine)
          lows         1  at least 2 of the last 3 lows stepping up
          volume       2  2x normal in at least 2 of the last 3 minutes - high
                          and staying high, one dip forgiven (1: in one)
          trend        2  over VWAP (1), over the 9 EMA over the 20 (1)
          MACD         1  the 12 EMA over the 26
          room         1  no prior-day high within V37_SCORE_ROOM above
        pullback=True (v36 buying back over a red candle's open): the red last
        candle is the pattern, not a no-buy. It scores 2 as a LIGHT pullback -
        a smaller body and less volume than the green before it - 1 with one
        of the two, 0 with neither (heavy selling); a huge top wick on it is
        still no buy (a rejection, APUS 1:51pm 10-06)."""
        bars = s.bars
        if len(bars) < 4:
            return 15, "too few candles to judge"
        last = bars[-1]
        light_pullback = pullback and not last.green
        if not last.green and not light_pullback:
            return None, "the last candle closed red"
        rng = last.h - last.l
        wick = (last.h - max(last.o, last.c)) / rng if rng > 0 else 0.0
        if wick > V37_SCORE_HUGE_WICK:
            return None, "a huge top wick on the last candle (%.0f%% of it)" % (100 * wick)
        parts = {}
        spd = self.real_speed(s, price)         # 0 if the price did not really move
        parts["speed"] = max((p for t, p in V37_SCORE_SPEED if spd >= t), default=0)
        if light_pullback:
            green = next((b for b in reversed(bars[:-1]) if b.green), None)
            small = bool(green) and (last.o - last.c) < 0.5 * (green.c - green.o)
            quiet = bool(green) and last.v < green.v
            parts["candle"] = int(small) + int(quiet)
        else:
            parts["candle"] = 2 if wick <= 1 / 3 else 1
        def top_wick(b):
            r = b.h - b.l
            return (b.h - max(b.o, b.c)) / r if r > 0 else 0.0
        w = [top_wick(b) for b in bars[-3:]]
        parts["wicks"] = 0 if (w[0] < w[1] < w[2] and w[2] > 1 / 3) else 1
        bodies = [b.c - b.o for b in bars[-3:]]
        fading = (all(x > 0 for x in bodies)
                  and bodies[1] < 0.75 * bodies[0] and bodies[2] < 0.75 * bodies[1])
        parts["bodies"] = 0 if fading else 1
        steps = sum(1 for k in (1, 2, 3) if bars[-k].l >= bars[-k - 1].l)
        parts["lows"] = 1 if steps >= 2 else 0
        normal = statistics.median(b.v for b in bars[-30:])
        busy = sum(1 for b in bars[-3:] if normal and b.v >= 2 * normal)
        parts["volume"] = min(2, busy)
        vwap = self.vwap(s)
        e9, e20, e12, e26 = self.live_emas(s, price)
        parts["trend"] = (1 if vwap and price > vwap else 0) + (
            1 if e9 and price > e9 > e20 else 0)
        parts["macd"] = 1 if e12 > e26 else 0
        parts["room"] = 0 if (s.prev_high > price
                              and s.prev_high < price * (1 + V37_SCORE_ROOM)) else 1
        return sum(parts.values()), " ".join("%s %d" % kv for kv in parts.items())


class V36(_Restore, _Momentum, V35):
    """The owner's playbook - see the V36 settings above."""

    name = "v36"
    # This strategy's own value of a V36_ setting, where it has one (v36b);
    # None = the module setting, shared by every copy of v36.
    WICK_VETO = None
    MAX_STOP = None
    FRESH_EXITS = None
    LEVEL_STOP = None

    def own(self, setting):
        mine = getattr(self, setting)
        return globals()["V36_" + setting] if mine is None else mine

    def __init__(self, broker, data):
        super().__init__(broker, data)
        self.crowd = (-1, {})                  # (minute, {symbol: rank})
        self.crowd_dv = {}                     # symbol -> dollars in the crowd window
        self.gainers = (-1, {})                # (minute, {symbol: rank by day gain})
        self.crowd_since = {}                  # symbol -> when it entered the top

    def halt_threshold(self) -> float:
        env = os.getenv("V36_HALT_PCT")
        if env not in (None, ""):
            return float(env) / 100.0
        return Strategy.halt_threshold(self)

    def confirm_tolerance(self) -> float:
        # RETO, BBD and NVAX were refused over half a cent on 2026-10-05.
        return max(CONFIRM_TOLERANCE, V36_CONFIRM_TOLERANCE)

    def buy_cap(self, s, price) -> float:
        """Paying up on a runner: "sometimes I'm almost half a point above
        what I bought". Safe here because every v36 buy has a rip on real
        money behind it (V36_MIN_DOLLARS)."""
        if price <= 0:
            return BUY_CHASE_CAP
        return min(V36_PAY_UP_MAX,
                   max(BUY_CHASE_CAP, V36_PAY_UP_ABR * self.abr(s) / price))

    def float_mult(self, symbol) -> float:
        return 1.0                             # small floats are what the owner wants

    def entry_shares(self, s, price, worst, stop_ref, eq, kind) -> int:
        """EASE IN: a tenth of a full position (V36_POSITION_PCT of equity) -
        a shakeout costs little, and the next buy is cheap too. add_step()
        takes it to the full position once the stock is moving."""
        held_all = sum(x.shares * (x.last_price or price)
                       for x in self.open_positions())
        room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
        if s.v36_furious and V36_FURIOUS_FULL:  # "a full position on the first hit"
            return int(min(eq * V36_POSITION_PCT, eq * MAX_POSITION_PCT, room) / worst)
        dollars = min(eq * V36_POSITION_PCT * V36_STARTER, room)
        shares = int(dollars / worst)
        if V36_STARTER_RISK and price > 0:      # "B": a far stop buys fewer shares
            risk = max(price - stop_ref, MIN_STOP_PCT * price, 0.01)
            budget = eq * V36_POSITION_PCT * V36_STARTER * V36_STARTER_RISK
            fit = int(budget / risk)
            if fit < shares:
                self.log.info("[v31] %s STARTER sized for its stop: %d -> %d shares "
                              "($%.0f) - the stop %.4f is %.1f%% under %.4f, $%.0f at "
                              "risk", s.symbol, shares, fit, fit * price, stop_ref,
                              100 * (price - stop_ref) / price, price, fit * risk)
                shares = fit
        return shares

    async def bid_stop(self, s) -> bool:
        """BID_STOP: the live market (the middle of the bid and ask) at or under
        the stop sells now - whatever the last print was, and however old."""
        if not (BID_STOP and s.in_position and s.stop):
            return False
        q = self.live_quote(s)
        if not q or not q[0] or not q[1]:
            return False
        mid = (q[0] + q[1]) / 2.0
        if mid > s.stop:
            return False
        self.log.info("[v31] %s the market %.4f x %.4f is at the stop %.4f - out",
                      s.symbol, q[0], q[1], s.stop)
        await self.exit(s, "stop")
        return True

    @staticmethod
    def paid_up_cents(price) -> float:
        """V37_SWEEP_CENTS: the cents over the ask a fast buy paid up to r34.35."""
        lo, hi = V37_SWEEP_CENTS
        return hi if price >= V37_SWEEP_BIG else lo

    def sweep_cents(self, price) -> float:
        """The cents a fast buy may pay over the ask: none for BUY_AT_ASK."""
        return 0.0 if self.name in BUY_AT_ASK else self.paid_up_cents(price)

    async def entry_buy(self, s, shares, price, cap) -> int:
        if s.v36_furious and V36_FURIOUS_SWEEP:
            floor = max(0.0, s.setup_level - self.confirm_tolerance())  # as the
            return await self.buy(s.symbol, shares, price, float("inf"),  # quote check
                                  floor=floor, sweep=self.sweep_cents(price),
                                  keep=True)
        return await super().entry_buy(s, shares, price, cap)

    async def fast_buy_no(self, s, price) -> str:
        """FAST_BUY_5S_UP / FAST_BUY_MAX_SPREAD: why a fast buy may not go out
        now - "" when it may. Each answer is logged with the 5-second move and
        the bid and ask at that moment, so every fast buy's market is on record
        (a refusal at most every 5 seconds a name). A refusal stands for
        V37_RETRY_GAP: the next print after that checks again."""
        now = time.time()
        if now - getattr(s, "fast_no_at", 0.0) < V37_RETRY_GAP:
            return getattr(s, "fast_no_why", "")
        move, _ = self.five_sec(s, price)
        q = self.live_quote(s)
        if q:
            bid, ask = q
        else:
            bid = await self.data.quote(s.symbol, "bid")
            ask = await self.data.quote(s.symbol, "ask")
        quoted = bool(bid and ask and bid > 0 and ask > 0)
        why = ""
        if FAST_BUY_5S_UP and move <= 0:
            why = "the last 5 seconds are not up"
        elif FAST_BUY_MAX_SPREAD and not quoted:
            why = "no bid and ask to check"
        elif FAST_BUY_MAX_SPREAD and ask - bid > FAST_BUY_MAX_SPREAD + 1e-9:
            why = "the ask is %.0fc over the bid, more than the %.0fc stop" % (
                100 * (ask - bid), 100 * FAST_BUY_MAX_SPREAD)
        market = ("bid %.4f ask %.4f (%.0fc)" % (bid, ask, 100 * (ask - bid))
                  if quoted else "no quote")
        if why:
            s.fast_no_at, s.fast_no_why = now, why
            if now - getattr(s, "fast_no_logged", 0.0) >= 5:
                s.fast_no_logged = now
                self.log.info("[%s] FAST BUY NO %s at %.4f | 5s %+.1f%% | %s | %s",
                              self.name, s.symbol, price, 100 * move, market, why)
        else:
            self.log.info("[%s] FAST BUY OK %s at %.4f | 5s %+.1f%% | %s",
                          self.name, s.symbol, price, 100 * move, market)
        return why

    def furious_new_high(self, s, price) -> bool:
        """Furious and over the high of the day as it stood before this print:
        back in at once after a stop - "get back on it as soon as it moves up
        above the high of the day" (the owner, 10-07)."""
        return bool(V36_FURIOUS_ALL and V36_FURIOUS and s.day_high
                    and price > s.day_high and self.speeding(s, price))

    def big_gain_line(self, s, price) -> float:
        """BIG_GAIN_AT: once the best price since this position's buy is that
        far over what we paid (the average), the price giving back
        BIG_GAIN_BACK of the best gain - 0.0 until then. The best is counted
        only from prices after the buy, never a high from before it."""
        if not BIG_GAIN_AT or not s.entry:
            return 0.0
        if getattr(s, "big_key", None) != s.v36_entries:   # a new position
            s.big_key, s.big_best = s.v36_entries, price
        s.big_best = max(s.big_best, price)
        gain = s.big_best - s.entry
        if gain < BIG_GAIN_AT - 1e-9:
            return 0.0
        return s.entry + (1 - BIG_GAIN_BACK) * gain

    async def big_gain_exit(self, s, price) -> bool:
        """Out on BIG_GAIN_BACK of a $1+ gain given back, the bid agreeing."""
        line = self.big_gain_line(s, price)
        if not line or price > line + 1e-9:
            return False
        q = self.live_quote(s)
        if q and q[0] > line + 1e-9:
            return False                        # a stray print: the bid is still over
        best = getattr(s, "big_best", price)
        self.log.info("[v31] %s gave back %.0f%% of a $%.2f gain (best %.4f, paid "
                      "%.4f): out", s.symbol, 100 * BIG_GAIN_BACK, best - s.entry,
                      best, s.entry)
        await self.exit(s, "giveback")
        return True

    def furious_line(self, s, top) -> float:
        """A furious buy, once its best price `top` is V36_FURIOUS_EVEN_AT over
        the buy: out at the buy price, or on giving back V36_FURIOUS_GIVEBACK of
        the gain, whichever is higher. 0.0 until then (the stop and the
        10-second leash only)."""
        if not V36_FURIOUS_EVEN_AT or not s.entry or top < s.entry + V36_FURIOUS_EVEN_AT - 1e-9:
            return 0.0
        if not V36_FURIOUS_GIVEBACK:
            return s.entry
        return max(s.entry, s.entry + (1 - V36_FURIOUS_GIVEBACK) * (top - s.entry))

    # ---- the whole / half dollar under the stop (V36_LEVEL_STOP) ---------------

    @staticmethod
    def half_under(price) -> float:
        """The whole or half dollar at or under the price."""
        return int(price * 2 + 1e-9) / 2.0 if price > 0 else 0.0

    def line_stop(self, price) -> float:
        """Where the stop goes for a buy at `price`: V36_LEVEL_GIVE under the
        whole or half dollar under it (0.0 with V36_LEVEL_STOP off)."""
        if not self.own("LEVEL_STOP"):
            return 0.0
        line = self.half_under(price)
        return line - V36_LEVEL_GIVE if line > 0 else 0.0

    def set_line(self, s, price):
        """At a buy: the line is the whole or half dollar under the price."""
        s.v36_line = self.half_under(price) if self.own("LEVEL_STOP") else 0.0
        s.v36_line_since = 0.0

    def raise_line(self, s, price):
        """The next whole or half dollar over the line, once the price has
        cleared it by V36_LEVEL_PAST and stayed past it V36_LEVEL_HOLD_SEC (no
        print under), becomes the line; the stop moves up to V36_LEVEL_GIVE
        under it - "it goes back under, you sell immediately" (the owner)."""
        if not (s.v36_line and self.own("LEVEL_STOP")):
            return
        nxt = s.v36_line + 0.5
        if price < nxt + V36_LEVEL_PAST - 1e-9:
            s.v36_line_since = 0.0
            return
        now = time.time()
        if not s.v36_line_since:
            s.v36_line_since = now
            return
        if now - s.v36_line_since < V36_LEVEL_HOLD_SEC:
            return
        s.v36_line = nxt
        s.v36_line_since = now                  # the next one's clock, if past it too
        if nxt - V36_LEVEL_GIVE > s.stop:
            s.stop = nxt - V36_LEVEL_GIVE
            self.log.info("[v31] %s held past $%.2f: the stop up to %.4f (entry %.4f)",
                          s.symbol, nxt, s.stop, s.entry)

    # ---- where the crowd is ---------------------------------------------------

    def crowd_rank(self, symbol) -> int:
        """1 for the scanner-list name with the biggest share of the dollars
        traded in the last V36_CROWD_MINUTES, 2 for the next... Recounted once
        a minute; a name entering the top V36_CROWD_TOP is stamped, so a name
        must HOLD there (in_crowd) - two names sharing the crowd swap the top
        spot minute to minute."""
        minute = int(time.time() // 60)
        if self.crowd[0] != minute:
            since = datetime.now(timezone.utc) - timedelta(minutes=V36_CROWD_MINUTES)
            span = datetime.now(timezone.utc) - timedelta(minutes=V36_CROWD_SPAN_MIN)
            dv = {}
            for sym in self.qualified:
                st = self.state.get(sym)
                if st and st.bars:
                    if V36_CROWD_TRADING and regular_hours():   # halts: 9:30-4
                        recent = [b for b in st.bars[-V36_CROWD_MINUTES:]   # only - a
                                  if b.ts >= span]      # halt is not $0
                    else:
                        recent = [b for b in st.bars if b.ts >= since]
                    d = sum(b.c * b.v for b in recent)
                    if d > 0:
                        dv[sym] = d
            order = sorted(dv, key=dv.get, reverse=True)
            ranks = {sym: i + 1 for i, sym in enumerate(order)}
            top = {sym for sym, r in ranks.items() if r <= V36_CROWD_TOP}
            now = time.time()
            for sym in list(self.crowd_since):
                if sym not in top:
                    del self.crowd_since[sym]
            for sym in top:
                self.crowd_since.setdefault(sym, now)
            self.crowd = (minute, ranks)
            self.crowd_dv = dv
        return self.crowd[1].get(symbol, 10**6)

    def crowd_dollars(self, symbol) -> float:
        """Dollars traded in the last V36_CROWD_MINUTES (as crowd_rank counted)."""
        self.crowd_rank(symbol)
        return self.crowd_dv.get(symbol, 0.0)

    def gainer_rank(self, symbol) -> int:
        """1 for the scanner-list name up the most on the day (from the
        previous close), 2 for the next... Recounted once a minute."""
        minute = int(time.time() // 60)
        if self.gainers[0] != minute:
            up = {}
            for sym in self.qualified:
                st = self.state.get(sym)
                if st and st.ref_price > 0 and st.last_price > 0:
                    up[sym] = st.last_price / st.ref_price - 1
            order = sorted(up, key=up.get, reverse=True)
            self.gainers = (minute, {sym: i + 1 for i, sym in enumerate(order)})
        return self.gainers[1].get(symbol, 10**6)

    def top_gainer(self, s) -> bool:
        return (V36_GAINER_TOP and self.gainer_rank(s.symbol) <= V36_GAINER_TOP
                and self.crowd_dollars(s.symbol) >= V36_GAINER_MIN_DOLLARS)

    def in_crowd(self, s) -> bool:
        """Where the crowd is (held V36_CROWD_HOLD_MIN), or the day's top
        gainer with real money trading - either will do."""
        if self.top_gainer(s):
            return True
        if V36_ACCEL and self.accelerating(s):
            return True                         # SXTC 8:16: no need to wait for the crowd
        if V36_FURIOUS and self.speeding(s, s.last_price):
            return True                         # BIYA 8:20: #4 by money, a minute late
        if self.crowd_rank(s.symbol) > V36_CROWD_TOP:
            return False
        if V36_RIP_SKIPS_HOLD and self.ripping_now(s):
            return True
        since = self.crowd_since.get(s.symbol)
        return since is not None and time.time() - since >= V36_CROWD_HOLD_MIN * 60

    def ripping_now(self, s) -> bool:
        """A rip among the last two closed minutes."""
        j = self.rip(s)
        return j is not None and j >= len(s.bars) - 2

    async def quote_the_crowd(self):
        """The tape needs the bid and ask BEFORE a buy, not after: until now
        quotes streamed only for names held, so a name about to be bought was
        marked by up/down ticks ("0% by quote" at almost every buy, 10-05)."""
        watch = getattr(self.data, "watch_quotes", None)
        if watch is None or not self.crowd_since:
            return
        try:
            await watch(list(self.crowd_since))
        except Exception as e:
            self.log.warning("[v36] quotes for the crowd: %s", e)

    # ---- the rip --------------------------------------------------------------

    @staticmethod
    def wick_ok(b) -> bool:
        rng = b.h - b.l
        return rng <= 0 or b.h - max(b.o, b.c) <= V36_WICK_MAX * rng

    @staticmethod
    def vol_base(bars, k) -> float:
        base = bars[max(0, k - V36_RIP_BEFORE):k]
        return sum(x.v for x in base) / len(base) if len(base) >= 2 else 0.0

    def rip_kind(self, bars, j) -> int:
        """bars[j] ends a rip: green, no long upper wick, on real money, and
        either the second of two greens adding V36_RIP_PCT on rising volume
        (2), or one green adding V36_RIP_ONE_PCT (1) - each on
        V36_RIP_VOL_MULT x the minutes before. 0: no rip."""
        b = bars[j]
        if not b.green or not self.wick_ok(b) or b.c * b.v < V36_MIN_DOLLARS:
            return 0
        a = bars[j - 1] if j >= 1 else None
        if (a is not None and a.green and b.v > a.v and a.c * a.v >= V36_MIN_DOLLARS
                and a.o > 0 and b.c >= a.o * (1 + V36_RIP_PCT)):
            avg = self.vol_base(bars, j - 1)
            if avg > 0 and min(a.v, b.v) >= V36_RIP_VOL_MULT * avg:
                return 2
        if V36_RIP_ONE_PCT and b.o > 0 and b.c >= b.o * (1 + V36_RIP_ONE_PCT):
            avg = self.vol_base(bars, j)
            if avg > 0 and b.v >= V36_RIP_VOL_MULT * avg:
                return 1
        return 0

    def offer_bar(self, raw):
        super().offer_bar(raw)
        s = self.st(raw.symbol)
        j = len(s.bars) - 1
        kind = self.rip_kind(s.bars, j)
        if kind:
            s.v36_rip_ts = s.bars[j].ts
            s.v36_rip_base = self.vol_base(s.bars, j - 1 if kind == 2 else j)

    def rip(self, s):
        """The index in s.bars of today's latest rip's last candle, or None."""
        if s.v36_rip_ts is None:
            return None
        for j in range(len(s.bars) - 1, -1, -1):
            if s.bars[j].ts == s.v36_rip_ts:
                return j
        return None

    def alive(self, s) -> bool:
        """The run is alive while the volume is: the last V36_ALIVE_BARS
        minutes at V36_ALIVE_MULT x the volume before the rip. No clock."""
        recent = s.bars[-V36_ALIVE_BARS:]
        if not recent or s.v36_rip_base <= 0:
            return False
        return sum(b.v for b in recent) / len(recent) >= V36_ALIVE_MULT * s.v36_rip_base

    def tape_ok(self, s) -> bool:
        """The owner: "at least sixty green, and no more than forty red".
        V36_TAPE_GREEN = 0 turns the check off - the replay has no real tape."""
        if not V36_TAPE_GREEN:
            return True
        buy, sell, _, total, _ = self.tape_split(s, V36_TAPE_SECONDS)
        if V36_TAPE_MID_ASIDE:
            total = buy + sell
        return total > 0 and buy >= V36_TAPE_GREEN * total \
            and sell <= V36_TAPE_RED * total

    # ---- the buy --------------------------------------------------------------

    def pullback_after(self, s, j):
        """The green-red pattern after the rip: the last closed candles red,
        the green before them at or after the rip's last candle. Returns
        (trigger 1c over the last red's open, stop at the reds' low, kind)."""
        bars = s.bars
        if not bars or not bars[-1].red:
            return None
        i = len(bars) - 1
        while i >= 0 and bars[i].red:
            i -= 1
        if i < j or not bars[i].green:
            return None
        reds = bars[i + 1:]
        if V36_FAILED_RIP and min(b.l for b in reds) < bars[j].o:
            return None                         # the rip erased: a failed rip
        if V36_PULLBACK_VOL and max(b.v for b in reds) >= V36_PULLBACK_VOL * bars[i].v:
            return None                         # selling, not a light pullback
        return reds[-1].o + V31_ENTRY_TICK, min(b.l for b in reds), "setup"

    def breaking_high(self, s, price):
        """The high of the day breaking with green candles stacking on rising
        volume: the last two closed candles green, the second on more volume
        and on V36_PICKUP_MULT x the minutes before, both on real money. Needs
        no earlier rip - the pick-up is its own. Stop at the last green's low."""
        bars = s.bars
        if len(bars) < 2 or not s.hod_closed:
            return None
        a, b = bars[-2], bars[-1]
        if not (a.green and b.green and b.v > a.v and self.wick_ok(b)):
            return None
        if min(a.c * a.v, b.c * b.v) < V36_MIN_DOLLARS:
            return None
        base = self.vol_base(bars, len(bars) - 1)
        if base <= 0 or b.v < V36_PICKUP_MULT * base:
            return None                         # the volume has to pick up
        level = max(s.hod_closed, s.v35_peak) + margin_for(price)
        return level, b.l, "hod"

    def leader_new_high(self, s, price) -> bool:
        """V36_LEADER_NO_CAP: the #1/#2 name making a new high of the day."""
        return (V36_LEADER_NO_CAP and self.crowd_rank(s.symbol) <= V36_CROWD_TOP
                and bool(s.hod_closed) and price > s.hod_closed)

    def at_level(self, s, price) -> bool:
        """V36_LEVELS: at a whole or half dollar - from V36_LEVEL_BELOW under it
        to V36_LEVEL_PAST over it - or past it for less than V36_LEVEL_HOLD_SEC."""
        if not V36_LEVELS:
            return False
        level = int((price + V36_LEVEL_BELOW) * 2 + 1e-9) / 2.0
        if level <= 0:
            return False
        if price < level + V36_LEVEL_PAST - 1e-9:
            s.v36_level_band = (level, time.time())     # at it: when, last
            return True
        band = getattr(s, "v36_level_band", None)       # just crossed: hold a moment
        return bool(band and band[0] == level
                    and time.time() - band[1] < V36_LEVEL_HOLD_SEC)

    def candles_allowed(self, s) -> bool:
        """V36_SETUP_BUYS: the candle setups for the first buys of a stock, or
        again after V36_SLEEP_MIN without a new high."""
        if not V36_SETUP_BUYS or s.v36_entries < V36_SETUP_BUYS:
            return True
        return bool(s.mom_high_ts) and time.time() - s.mom_high_ts >= V36_SLEEP_MIN * 60

    def hod_plus(self, s):
        """Past the first buys: the high of the day (its highest closed minute)
        plus V36_HOD_PLUS; the stop under the last closed candle."""
        if not s.hod_closed or not s.bars:
            return None
        return s.hod_closed + V36_HOD_PLUS, s.bars[-1].l, "hod"

    # ---- why not (V36_WHY_NOT) -------------------------------------------------

    def why_not(self, s, price, why, urgent=False):
        """One line: which check said no, with its numbers - a minute apart per
        name, 5 seconds apart once the price is at a trigger (urgent). Only for
        the top 3 crowd names and the top gainers."""
        if not V36_WHY_NOT:
            return
        rank, grank = self.crowd_rank(s.symbol), self.gainer_rank(s.symbol)
        if rank > 3 and grank > V36_GAINER_TOP:
            return
        now = time.time()
        if now - s.v36_why_at < (5 if urgent else 60):
            return
        s.v36_why_at = now
        since = self.crowd_since.get(s.symbol)
        held = " held %.1fm" % ((now - since) / 60) if since else ""
        self.log.info("[v36] WHY-NOT %s px %.4f | crowd #%s $%.0fk%s, gainer #%s | %s",
                      s.symbol, price, rank if rank < 10**6 else "-",
                      self.crowd_dollars(s.symbol) / 1000, held,
                      grank if grank < 10**6 else "-", why)

    def pattern_text(self, s) -> str:
        """Where the two entry patterns stand, for a "why not" line."""
        bars = s.bars
        j = self.rip(s)
        rip = ("rip %s %s" % (bars[j].ts.astimezone(ET).strftime("%H:%M"),
                              "alive" if self.alive(s) else "dead")
               if j is not None else "no rip")
        if len(bars) < 2:
            return rip + ", too few candles"
        a, b = bars[-2], bars[-1]
        base = self.vol_base(bars, len(bars) - 1)
        colour = lambda x: "G" if x.green else ("R" if x.red else "-")
        return "%s | last candles %s%s, vol %.1fx the 5 before (high break needs %.1fx)" % (
            rip, colour(a), colour(b), b.v / base if base else 0.0, V36_PICKUP_MULT)

    async def maybe_enter(self, s, price, fast, base):
        if not entries_allowed():
            return
        if (V36_NO_RTH_BUYS_ON and regular_hours()
                and datetime.now(ET).date().isoformat() in V36_NO_RTH_BUYS_ON):
            return                              # the owner: no v36/v36b buys 9:30-4 today
        if s.symbol not in self.qualified:      # the scanner: $1-$20, up 10%+
            return
        if not self.price_ok(s, price):
            return
        if len(self.open_positions()) >= V36_MAX_POSITIONS:
            self.why_not(s, price, "NO: %d positions open" % len(self.open_positions()))
            return
        if (V36_MAX_ENTRIES and s.v36_entries >= V36_MAX_ENTRIES
                and not self.leader_new_high(s, price)
                and not (V36_FURIOUS and self.speeding(s, price))):
            self.why_not(s, price, "NO: %d buys today" % s.v36_entries)
            return
        if (s.v36_entry_bar_ts is not None and s.bars
                and s.bars[-1].ts <= s.v36_entry_bar_ts
                and not self.furious_new_high(s, price)):
            return                              # one buy a minute: no churn
        if V36_MAX_FLOAT and FLOATS.get(s.symbol, 0) > V36_MAX_FLOAT:
            self.why_not(s, price, "NO FLOAT: %.1fM > %.0fM" % (
                FLOATS.get(s.symbol, 0) / 1e6, V36_MAX_FLOAT / 1e6))
            return
        if not self.in_crowd(s):
            self.why_not(s, price, "NO CROWD: not top %d held %dm, not ripping, not a "
                         "top gainer with $%.0fk" % (V36_CROWD_TOP, V36_CROWD_HOLD_MIN,
                                                    V36_GAINER_MIN_DOLLARS / 1000))
            return
        await self.quote_the_crowd()
        # V36_FURIOUS_ALL (the owner, 10-07): running furious, every entry check
        # below is set aside - "throw everything through the window, get in
        # really quick" - and the first buy is the full position.
        rush = V36_FURIOUS_ALL and V36_FURIOUS and self.speeding(s, price)
        found = None
        candles_ok = self.candles_allowed(s)
        j = self.rip(s)
        if candles_ok and j is not None and self.alive(s):
            found = self.pullback_after(s, j)
        if not found:
            found = self.breaking_high(s, price) if candles_ok else self.hod_plus(s)
        if rush and s.bars and (not found or price < found[0]):
            level = max(s.hod_closed, s.bars[-1].h)     # no pattern needed: over the
            if price > level:                           # last minute and the day's high
                found = (level, s.bars[-1].l, "hod")
        if not found:
            self.why_not(s, price, "NO PATTERN: " + self.pattern_text(s))
            return
        if price < found[0]:
            self.why_not(s, price, "WAIT: %s trigger %.4f" % (found[2], found[0]))
            return
        trigger, stop_ref, kind = found
        if not rush and V36_CHASE_MAX and price > trigger * (1 + V36_CHASE_MAX):
            self.why_not(s, price, "NO: %.4f is %.0f%% over the trigger %.4f - the move "
                         "already happened" % (price, 100 * (price / trigger - 1), trigger),
                         urgent=True)
            return
        if not rush and self.at_level(s, price):
            self.why_not(s, price, "NO: at the $%.2f level - wait till it holds %.0fc "
                         "past" % (int((price + V36_LEVEL_BELOW) * 2 + 1e-9) / 2.0,
                                   100 * V36_LEVEL_PAST), urgent=True)
            return
        if (not rush and V36_REENTRY_SPEED and s.v36_entries >= 1
                and self.real_speed(s, price) < V36_REENTRY_SPEED):
            self.why_not(s, price, "NO SPEED for a re-entry: %.2f under %.2f" % (
                self.real_speed(s, price), V36_REENTRY_SPEED), urgent=True)
            return
        veto = 0.0 if rush else self.own("WICK_VETO")
        if veto and s.bars:
            b = s.bars[-1]
            rng = b.h - b.l
            wick = (b.h - max(b.o, b.c)) / rng if rng > 0 else 0.0
            if wick > veto:
                self.why_not(s, price, "NO: a %.0f%% top wick on the last candle - sellers "
                             "rejected the high" % (100 * wick), urgent=True)
                return
        if self.own("MAX_STOP") and not (rush and FURIOUS_TEN_CENTS):
            # under what it pays, not an old trigger - a regular buy only: a
            # furious one has v36's 10c leash (FURIOUS_TEN_CENTS)
            stop_ref = max(stop_ref, max(trigger, price) * (1 - self.own("MAX_STOP")))
        if rush and V36_FURIOUS_STOP_MAX:       # a full position: never a far stop
            stop_ref = max(stop_ref, price * (1 - V36_FURIOUS_STOP_MAX))
        stop_ref = max(stop_ref, self.line_stop(price))   # under the whole / half dollar
        furious = V36_FURIOUS_SKIPS and self.speeding(s, price)
        if furious:                             # the owner, 10-07: running this fast,
            move, dollars = self.five_sec(s, price)   # every filter is set aside
            self.log.info("[v36] FURIOUS %s at %.4f: speed %.2f, 5s %+.1f%% on $%.0fk - "
                          "trend, tape and room set aside", s.symbol, price,
                          self.real_speed(s, price), 100 * move, dollars / 1000)
        e9, e20, e12, e26 = self.live_emas(s, price)
        if not furious and (not self.trend_ok(s, price) or not e12 > e26):
            self.why_not(s, price, "NO TREND at the trigger %.4f: vwap %.4f e9 %.4f e20 "
                         "%.4f macd %+.4f" % (trigger, self.vwap(s), e9, e20,
                                              e12 - e26), urgent=True)
            return
        if not furious and not self.tape_ok(s):
            b, r, m, tot, q = self.tape_split(s, V36_TAPE_SECONDS)
            self.why_not(s, price, "NO TAPE at the trigger %.4f: %ds ask %.0f%% bid %.0f%% "
                         "between %.0f%% of %.0f sh (%.0f%% by quote)" % (
                             trigger, V36_TAPE_SECONDS, 100 * b / tot if tot else 0,
                             100 * r / tot if tot else 0, 100 * m / tot if tot else 0,
                             tot, 100 * q), urgent=True)
            return
        # ROOM TO RUN: the next wall overhead - the prior day's high - at
        # least V35_ROOM_RR times what the stop risks.
        risk = trigger - min(stop_ref, trigger * (1 - MIN_STOP_PCT))
        if (not furious and V35_ROOM_RR and s.prev_high > trigger
                and s.prev_high - trigger < V35_ROOM_RR * risk):
            self.why_not(s, price, "NO ROOM at the trigger %.4f: prior high %.4f" % (
                trigger, s.prev_high), urgent=True)
            return
        if V36_SCORE_MIN and not rush and not self.ripping(s):
            points, parts = self.score(s, price, pullback=(kind != "hod"))
            if points is None or points < V36_SCORE_MIN:
                self.why_not(s, price, "NO SCORE at the trigger %.4f: %s" % (
                    trigger, parts if points is None else "%d/15 under %d: %s" % (
                        points, V36_SCORE_MIN, parts)), urgent=True)
                return
        lock = self.lock(s.symbol)
        if lock.locked():
            return
        async with lock:
            if s.in_position:
                return
            if (rush and V36_FURIOUS_SWEEP      # a missed fast buy: the next furious
                    and time.time() - getattr(s, "v36_try_at", 0.0) < V37_RETRY_GAP):
                return                          # print tries again, this far apart
            if rush and await self.fast_buy_no(s, price):
                return                          # falling, or the market not there
            s.v36_adds = 0
            s.ten_break = False
            s.setup_level = trigger
            s.v36_furious = rush                # entry_shares: the full position
            await self._maybe_enter_inner(s, price, fast, base, kind, trigger,
                                          stop_ref)
            if rush and not s.in_position:
                s.v36_try_at = time.time()      # missed: the pace for the next try
            if s.in_position:
                s.v36_entries += 1
                s.v36_entry_bar_ts = s.bars[-1].ts if s.bars else None
                s.v36_first = s.entry
                self.set_line(s, price)
                if rush and V36_FURIOUS_STOP_CENTS:      # 10 cents under what it paid
                    s.stop = max(s.stop, s.entry - V36_FURIOUS_STOP_CENTS)
                if rush:                        # its gain counts from the fill: SXTC
                    s.peak = s.entry            # 1:40pm v36b paid $7.35 on a $7.72
                                                # print and sold on a "gain" it never had
                if rush and V36_FURIOUS_FULL:
                    s.v36_adds = len(self.add_steps())   # full already: no adds, and
                    s.v36_leash_from = time.time()       # the 10-second leash on it
                    self.log.info("[v36] %s FULL POSITION %d shares at once (furious), "
                                  "buy %d today - stop %.4f, line $%.2f", s.symbol,
                                  s.shares, s.v36_entries, s.stop, s.v36_line)
                else:
                    self.log.info("[v36] %s STARTER %d shares (a tenth of a full "
                                  "position), buy %d today - adds at %.4f and %.4f "
                                  "on a new high", s.symbol, s.shares, s.v36_entries,
                                  self.add_level(s, 0), self.add_level(s, 1))

    @staticmethod
    def add_steps():
        return ((V36_ADD1_AT, V36_ADD1_TO), (V36_ADD2_AT, V36_ADD2_TO))

    def add_level(self, s, step) -> float:
        """The price at which add `step` (0 or 1) comes, from the starter's."""
        at = self.add_steps()[step][0]
        return s.v36_first + at if V36_ADD_CENTS else s.v36_first * (1 + at)

    async def add_step(self, s, price, to_fraction):
        """Keep adding as the stock moves: to `to_fraction` of a full position
        (V36_POSITION_PCT of equity). The floor rises to what the starter
        paid, and the short leash starts watching from here."""
        async with self.lock(s.symbol):
            if not s.in_position:
                return
            if not V36_ADD_RETRY:
                s.v36_adds += 1                 # the old way: a miss used it up
            ref = price
            if V36_ADD_FROM_ASK:
                ask = await self.data.quote(s.symbol, "ask")
                if ask and ask > ref:
                    ref = ask                   # the print lags: count from the ask
            cap = self.buy_cap(s, ref)
            if V36_ADD_RIP_PAY and self.ripping(s):
                cap = max(cap, min(V36_ADD_RIP_PAY, 0.5 * self.move(s, ref)))
            eq = await self.broker.equity(self.day_start_equity)
            worst = ref * (1 + cap)
            held_all = sum(x.shares * (x.last_price or ref)
                           for x in self.open_positions())
            room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
            want = max(0.0, eq * V36_POSITION_PCT * to_fraction - s.shares * ref)
            shares = int(min(want, room) / worst)
            if shares * ref < MIN_TRADE_DOLLARS:
                if V36_ADD_RETRY:
                    s.v36_adds += 1             # nothing to add: the step is done
                return
            filled = await self.buy(s.symbol, shares, ref, cap)
            if not filled:
                s.v36_add_try_ts = time.time()  # a miss: the next try waits a moment
            elif V36_ADD_RETRY:
                s.v36_adds += 1
            if filled:
                s.shares += filled
                s.entry = await self.broker.avg_entry(s.symbol) or s.entry
                if not V36_RUNNER_HALF:
                    s.stop = max(s.stop, s.entry if V36_FLOOR_AVG else s.v36_first)
                s.ten_break = False
                s.v36_leash_from = time.time()
                self.log.info("[v36] %s ADD to %.0f%% of a full position: +%d @ "
                              "%.4f -> %d shares, entry %.4f, floor %.4f (what the "
                              "starter paid)", s.symbol, 100 * to_fraction, filled,
                              price, s.shares, s.entry, s.stop)

    # ---- the exit -------------------------------------------------------------

    def offer_tick(self, symbol, price, size, conds=(), ts=0.0):
        if qualifies(conds):
            try:
                self.ten_add(self.st(symbol), price, ts or time.time())
            except Exception as e:
                self.log.error("[v36] 10s candle %s: %s", symbol, e)
        super().offer_tick(symbol, price, size, conds, ts)

    def ten_add(self, s, price, t):
        bucket = int(t // V36_TEN_SEC)
        if s.ten and s.ten[0] == bucket:
            _, o, h, l, _ = s.ten
            s.ten = (bucket, o, max(h, price), min(l, price), price)
            return
        if s.ten:
            s.tens.append(s.ten)
            self.ten_check(s)
        s.ten = (bucket, price, price, price, price)

    def ten_check(self, s):
        """THE SHORT LEASH, once the position has been added to: a 10-second
        candle that opened after the last add (and its grace) and closed red,
        under the lows of the two before it. A small red patch inside a strong
        run does not do it - "you hold up through that little bout". The
        starter alone has only the red's low under it."""
        if not (s.in_position and s.v36_adds and s.v36_leash_from) or len(s.tens) < 3:
            return
        bucket, o, _, _, c = s.tens[-1]
        if bucket * V36_TEN_SEC < s.v36_leash_from + V36_TEN_GRACE:
            return
        if c < o and c < min(s.tens[-2][3], s.tens[-3][3]):
            s.ten_break = True

    async def evaluate(self, s, price):
        if await self.halted():
            if s.in_position:
                await self.exit(s, "halted")
            return
        if await self.bid_stop(s):
            return
        if self.off_quote(s, price):
            self.note_off_quote(s, price)       # not the market: decides nothing
            return
        if not s.in_position:
            await self.maybe_enter(s, price, self.fast_speed(s), self.baseline(s))
            return
        if self.own("FRESH_EXITS") and not self.fresh(s):
            return                              # an old print: the next fresh one decides
        new_high = price >= s.peak
        s.peak = max(s.peak, price)
        s.v35_peak = max(s.v35_peak, price)
        self.raise_line(s, price)
        if s.entry and s.peak >= s.entry * (1 + V36_LEASH_AT):
            s.armed = True
        if s.stop and price <= s.stop:
            await self.exit(s, "stop")
            return
        if s.v36_furious:
            line = self.furious_line(s, s.peak)
            if line and price <= line:
                await self.exit(s, "giveback")  # up 30c, then 30% of the gain back
                return
        if await self.big_gain_exit(s, price):
            return                              # up $1+, then 30% of it back
        if s.armed:
            dist = V36_LEASH_ABR * self.abr(s)
            dist = min(max(dist, V31_TRAIL_MIN_PCT * s.peak),
                       V31_TRAIL_MAX_PCT * s.peak)
            s.trail_stop = max(s.trail_stop, s.peak - dist)
            if price <= s.trail_stop:
                await self.exit(s, "trail")
                return
        elif V36_RUNNER_HALF and s.v36_adds:
            if (s.peak > s.v36_first
                    and price <= s.v36_first + 0.5 * (s.peak - s.v36_first)):
                await self.exit(s, "half")      # half the run given back
                return
        elif s.ten_break and s.v36_adds:
            await self.exit(s, "10s")
            return
        steps = self.add_steps()
        if s.v36_adds < len(steps) and s.v36_first:
            level = self.add_level(s, s.v36_adds)
            ready = (self.add_held(s, price, level, new_high) if V36_ADD_HOLD_SEC
                     else new_high)
            if (ready and time.time() - s.v36_add_try_ts >= V36_ADD_RETRY_SEC
                    and price >= level and self.tape_ok(s)
                    and not self.at_level(s, price)):
                await self.add_step(s, price, steps[s.v36_adds][1])

    def add_held(self, s, price, level, new_high) -> bool:
        """V36_ADD_HOLD_SEC: a NEW HIGH over the add's level that then holds that
        long - no print more than V36_ADD_HOLD_GIVE under it. DKI 11:36:39: the
        hold alone (r34.19) added at $3.33 on the way down from $3.52, the floor
        moved to the average and the next dip sold it all."""
        now = time.time()
        key = (level, s.entry_at)
        hold = getattr(s, "v36_add_hold", None)
        if hold and hold[0] == key:
            if price < hold[2] - V36_ADD_HOLD_GIVE:
                s.v36_add_hold = None           # the new high did not hold
                return False
            return now - hold[1] >= V36_ADD_HOLD_SEC
        if new_high and price >= level:
            s.v36_add_hold = (key, now, price)  # the clock starts on the new high
        return False


# ----------------------------------------------------------------------------
# V37 - THE SIMPLEST: WHERE THE CROWD IS, WHEN IT RIPS
# ----------------------------------------------------------------------------
# The owner, 2026-10-06: "a strategy that is simplest of all". No candles, no
# indicators, no tape check:
#   WHICH STOCK  the #1 or #2 by activity right now (dollars traded in the
#                last few minutes), with a big crowd behind it - or the day's
#                top gainer with real money trading (V36_GAINER_*).
#   THE BUY      the moment it rips: up V37_FAST_PCT in the last V37_FAST_SECONDS
#                on real money. Like the owner's hot keys: each try at the ask
#                plus 10 cents, re-priced every 0.4s, under a ceiling that grows
#                with the speed (2% to 10% over the price seen); missed, it tries
#                again on the next print that still rips. After a sale, again only with the crowd still there,
#                at a new high of the day.
#   SIZE         a tenth of a position; half at +10 cents, full at +20 cents.
#                Full is 40% of the account alone; a second one gets what is
#                left under 50%, and if it keeps running the first is trimmed
#                so both hold 25%.
#   THE EXIT     "no tolerance for loss": V37_STOP_CENTS under the buy. "Half of
#                the profit gone, exit": half of the best gain given back.
# Numbers marked (?) are first guesses for the owner to correct.
V37_CROWD_TOP = 2               # the #1 or #2 by activity
V37_CROWD_MIN_DOLLARS = 1_000_000   # "a really huge crowd": dollars traded in the
                                # last V36_CROWD_MINUTES at least this (?)
V37_FAST_SECONDS = 60           # "fast" (?): up V37_FAST_PCT within this many
V37_FAST_PCT = 0.03             # seconds...
V37_FAST_DOLLARS = 250_000      # ...on at least this many dollars traded in them
# THE OWNER'S SPEED (2026-10-06): speed = (P2 - P1) / P1 x (V2 / V1) - the
# price move times the volume's change, over rolling V37_FAST_SECONDS windows:
# P2 now, P1 a window ago; V2 shares in the last window, V1 in the one before.
# +10% on equal volume = 0.10; +5% on double volume = 0.10. A falling price is
# negative: never a buy. When on, it replaces "up V37_FAST_PCT" as what
# "flying" means (the money traded still has to reach V37_FAST_DOLLARS); the
# owner: enter between 0.1 and 2 or more. V2/V1 capped at V37_SPEED_VOL_CAP.
V37_SPEED_MIN = 0.0             # 0 = off (the old fast rule); the owner, 10-06:
                                # hold off - judge "up 3%" on a big enough sample first
V37_SPEED_VOL_CAP = 30.0        # the owner: volume 20x with the price barely moving
                                # is "about to take off" - 1% x 20 = 0.20, a buy
V37_ASK_PLUS = 0.10             # each try's limit: the ask plus this many dollars -
                                # the owner's hot keys ("ask plus 10 cents"); it fills
                                # at the best offers up to there, usually at the ask
V37_ENTRY_MAX = 0.10            # the ceiling grows with the speed: half of the last
                                # minute's move, between V37_ENTRY_PCT and this
V37_ENTRY_PCT = 0.02            # a buy pays at least this share over the price seen;
                                # it re-prices every 0.4s up to there (FAST_BUY), and
                                # if the stock runs past it, the next print that still
                                # rips tries again from there - "so that way we are in"
V37_SOLO_PCT = 0.40             # a full position when it is the only one (the
                                # owner, 10-06: "one position can go all the way to
                                # 40"); the worst replayed trade lost 2.5% of it
V37_PAIR_PCT = 0.25             # each of two in the end...
V37_PAIR_TOTAL = 0.50           # ...and two together never over this. The owner,
                                # 10-06: beside a first one at 40%, a second one's
                                # full position is what is left (10%: 1%, 5%, 10%);
                                # if it keeps running (+V37_ADD3_CENTS on a new
                                # high), the first is trimmed to 25% and the second
                                # grows to 25%.
V37_ADD3_CENTS = 0.30           # "keeps running" for a second position (?)
V37_STARTER = 0.10              # the first buy: this fraction of a full position
V37_ADD1_CENTS = 0.10           # up this much from the first buy, on a new high:
V37_ADD1_TO = 0.50              # to this fraction of a full position
V37_ADD2_CENTS = 0.20
V37_ADD2_TO = 1.00
V37_STOP_CENTS = 0.02           # no tolerance for loss: this far under the buy, out
V37_GIVEBACK = 0.50             # this share of the best gain given back: out
# PROPOSED 2026-10-06, off until the owner decides. Live, 8:11-8:12am: IPDN
# bought 7 times at real new highs while it rose 10% in under 2 minutes, each
# shaken out by the 2c stop within 1-3 seconds (-$35) - on a $6 stock moving
# 10c a second, 2c is noise.
V37_STOP_SPEED = True           # the stop sized to the stock's speed instead:
V37_STOP_SHARE = 1 / 3          # this share of the last minute's move under the
V37_STOP_MIN = 0.03             # buy, never less than this...
V37_STOP_MAX = 0.03             # ...nor more than this; after an add, the same
                                # (the owner, 10-08 night: v37 "the exact same thing" as
                                # v36b - 3% on a regular buy, 10c on a furious one;
                                # was 8%)
                                # distance under the new average
V37_GIVEBACK_ARM = 0.0          # "half the gain" only once the best gain reached
                                # this (0 = from the first cent, as before)
# 10-07 (the owner: "from the first cent"). SPAI 8:10:00: bought @ $4.8053,
# best price $4.81 - half a cent - sold one second later by "half the gain"
# @ $4.69 while the stop ($4.59, under the red candle) was nowhere near; the
# next candle closed $4.93. Half a cent is not a gain.
V37_TRAIL_CENTS = 0.05          # in place of "half the gain", out once the price is this
                                # many dollars under its best since the buy - the price paid,
                                # if it never rose; the stop stays under it (the owner, 10-08,
                                # a trial on v37). 10-08's 19 v37 trades, print by print
                                # (replay/research/tickreplay.py): half the gain from 1c
                                # -$752 (live -$742); out 2c under the best -$664, 3c -$569,
                                # 4c -$532, 5c -$290, 6c -$339, 8c -$471. 0 = off
V37_TRAIL_KEEPS_HALF = False     # ...True: beside "half the gain", not in place of it
V37_GIVEBACK_FROM_BID = False   # PROPOSAL (10-08, fix 3, off until the owner decides):
                                # "half the gain" arms only once the live bid has been
                                # over what we paid - a gain we could sell at. 10-08: 15
                                # of v37's 19 sales were "half the gain" on 1-3c of prints
                                # (bought at the ask, sold at the bid), held 1-12s, -$249
V37_GIVEBACK_ARM_CENTS = 0.01   # "half the gain" only once the best gain is a
                                # full cent or more (0 = any fraction, as before)
# 10-07: the bots acted on single prints that were not the market. BIYA
# 4:13:55: sold by "half the gain" on a $2.64 print (1.1s old) while it traded
# $2.73. SPAI 8:09:58: bought "above the high" on a $5.05 print while the
# market was ~$4.78 (Webull's 8:09 high $5.02; it filled $4.81).
V37_PRINT_CHECK = True          # a print outside the live bid-ask by more than
V37_PRINT_TOL_CENTS = 0.02      # this, or this share of the price (whichever is
V37_PRINT_TOL_PCT = 0.005       # larger), decides nothing - buy, add or sell
V37_QUOTE_AGE = 2.0             # a streamed quote older than this is not "live"
V37_CONFIRM_ASK = True          # a buy needs the ask itself above the old high
V37_GIVEBACK_BID = True         # "half the gain" needs the bid under the line too
# PROPOSED 2026-10-06, off until the owner decides. All 6 v37 trades from
# 9:02 to 11:40am were sold by "half the gain" 4-13 seconds after the buy,
# on a gain of 1-8c - noise right after the buy. A grace: for this many
# seconds after a buy only the stop (3-8% under) sells; the owner: "that
# little noise up front can be cut off by your 3 and 8% below".
V37_GRACE_SECONDS = 0.0         # 0 = off
V37_GRACE_FORGET = False        # True: "half the gain" counts only the gain made
                                # after the grace, not a spike inside it
# PROPOSED 2026-10-06 (the owner), off until the owner decides: buy only while
# the stock is RUNNING. The 9 v37 buys from 9:02am to 2:25pm 10-06 all came at
# the top of a one-minute burst out of quiet (already up 7-28% in 2 minutes)
# and all lost. The owner: price up, volume up, and none of the bearish signs
# - a wick on the candle before ("the momentum is fizzling out"), green bodies
# getting smaller one after another. A stock truly ripping (the last 60s
# busier than any minute of its day so far) skips these checks.
V37_MOMENTUM = False            # the checks below; False = as before
V37_STAIR_MINUTES = 2           # the last N closed minutes each with a low at or
                                # above the one before (the price stepping up)
V37_CROWD_STAYS = 2             # ...each trading at least V37_CROWD_REL x the
V37_CROWD_REL = 2.0             # stock's normal minute - not one burst out of quiet
V37_LAST_GREEN = True           # the minute before the buy closed green
V37_WICK_MAX = 0.25             # the minute before the buy: green, its top wick at
                                # most this share of its range ("full all the way
                                # to the top, no wick or a very short wick")...
V37_BODY_FADE = 0.50            # ...and its body at least this share of the bigger
                                # of the two before it (bodies not shrinking)
# PROPOSED 2026-10-06 (the owner), off until the owner decides: the same signs
# WEIGHED instead of pass/fail - "the world is not black and white; trading
# is messy". Points for what favours a run, a buy at V37_SCORE_MIN or more.
# Only a huge top wick on the last candle stops a buy outright ("almost a
# stop"). A stock ripping skips the score.
V37_SCORE_MIN = 12              # 0 = off; else the points needed (of 15) - the
                                # owner, 10-06: 12 (replay: 75% won, the only
                                # version profitable at live-like fill costs)
V37_SCORE_HUGE_WICK = 0.60      # the last candle's top wick over this share of it:
                                # no buy
V37_SCORE_ROOM = 0.05           # resistance: the prior day's high this close above
V37_SCORE_SPEED = ((0.1, 1), (0.2, 2), (0.3, 4))   # the owner's speed: (at, points)
                                # - 0.3 is worth 4 ("the speed is very important")
V37_SPEED_MOVE_MIN = 0.03       # the speed counts (its points, the furious override,
                                # speed as the trigger) only when the PRICE itself is
                                # up this much in the last minute - the owner: huge
                                # volume on a flat price is selling met by buying,
                                # not a run ("I would wait for a confirmation")
# 10-07: "ripping" (the last 60s out-traded every minute so far) skipped the
# score - and the red-candle no-buy with it. LPCN 6:33am: score 9, speed 0.07,
# early-premarket minutes small; LPCN 7:00 and SPAI 8:09:58 bought with the
# last candle red ("score None"). The owner: the exception is for the furious.
V37_RIP_SPEED = 0.3             # ripping skips the score only at this speed or
                                # more (0 = any ripping, as before)
V37_RIP_NO_RED = True           # a red last candle or a huge wick is no buy, ripping
                                # or not (False = ripping skipped it, as before)
# PROPOSED 10-07, off until replayed - SXTC (the owner: "a move like that should
# not be missed; this is where the money is"): 8:13 +3% on 38k, 8:14 +6.6% on
# 114k (3x), 8:15 +8% on 261k (2.3x), each closing at its high, the #1 gainer -
# then 8:16 $2.44 -> $7.12. Every bot waited for the crowd rules ($1M, top 2).
# THE ACCELERATION: green minutes in a row, each closing higher in its top third
# on rising volume; the last on ACCEL_VOL_STEP x the one before and
# ACCEL_VOL_NORMAL x the stock's normal minute, the owner's speed over
# ACCEL_SPEED on ACCEL_DOLLARS - a candidate whatever the crowd says.
ACCEL_BARS = 2
ACCEL_TOP = 1 / 3
ACCEL_VOL_STEP = 2.0
ACCEL_VOL_NORMAL = 3.0
ACCEL_SPEED = 0.15
ACCEL_DOLLARS = 250_000
V36_ACCEL = True                # v36/v36b: an acceleration counts as the crowd
V37_ACCEL = True                # v37: buy it over the last minute's high...
# The owner, 10-07: "the position has to get bigger, faster - more than half of
# the account in the next few seconds, 60-70%; I would have used the whole
# account. You see this once a month or two; it pays for the months."
V37_ACCEL_SIZE = ((0.15, 0.04), (0.20, 0.10), (0.30, 0.35))   # ...the first buy, a
                                # share of the ACCOUNT by the speed...
V37_ACCEL_MAX_PCT = 0.65        # ...still furious on a new high 2% over the buy:
V37_ACCEL_ADD_AT = 0.02         # up to this share of the account in one add
V37_FURIOUS_SPEED = 0.30        # the owner's speed this high on ACCEL_DOLLARS in the
                                # last minute: a buy whatever the crowd, the money
                                # rules or the score ("the speed overrides
                                # everything") - not over a red candle, never on a
                                # print the quote does not back
V37_ACCEL_CHASE = 0.20          # no fast buy this far over the last closed minute's
                                # high: BIYA 10-07 8:20-8:21 went $2.54 -> $33.96 ->
                                # $8.20 in under a minute (SXTC 8:16:38 bought 13%
                                # over it). 0 = no limit
V37_HOD_CLEAR = (0.02, 0.005)   # a new high must clear the old one by this much -
                                # the larger of 2 cents and 0.5% (WETO 10-07 9:52: a
                                # print a cent over $1.32, then $1.26). () = off
V37_ACCEL_REAL = True           # a fast buy needs the owner's speed at ACCEL_SPEED
                                # too, not only the candles (WETO: candles 0.26,
                                # the owner's speed 0.06)...
V37_ACCEL_TAPE = True           # ...and the tape at 60/40 (WETO: 49/51)
V37_ACCEL_FROM_HIGH = True      # ...over the breakout level: the larger of the last
                                # minute's high and the old high of the day (BIYA
                                # 8:20: the last candle $2.54, the high $3.10 - from
                                # the candle alone no price passed both rules)
V37_SWEEP = True                # a fast buy is an order at the ask plus a few cents,
                                # filling at once; unfilled, it tries again at the new
                                # ask - "keep trying, the markets are irrational" (the
                                # owner, 10-07) - up to the safety net below
V37_SWEEP_CENTS = (0.20, 0.30)  # the cents over the ask: 20c under V37_SWEEP_BIG, 30c
V37_SWEEP_BIG = 10.0            # from it - "30 cents is $300 on a thousand shares; good
                                # enough" (20% was $2,000 on a $10 stock)
BUY_AT_ASK = ("v36b", "v37")    # the owner, 10-08 night ("buy at the ask is in"): every
                                # buy of theirs is a limit AT the ask - the fast buys
                                # (v37's, v36b's furious) no cents over, the others not
                                # FAST_BUY_OVER_ASK over; each try at the ask of that
                                # moment, everything else as before. v36 pays up (the
                                # control). Replayed second by second, 10-06/07/08: v37
                                # -$1,349 -> -$525..-$848 (better each day, 89-99% of the
                                # shares bought); v36b's furious -$586 -> -$371..-$424.
                                # memory/words_buy_at_ask.md. () = all pay up as before
BIG_GAIN_AT = 1.00              # the owner, 10-08 night: once the best price since the
BIG_GAIN_BACK = 0.30            # buy is $1.00 a share or more over what we paid (the
                                # average), out on giving back 30% of that best gain -
                                # "us capturing a hundred cents, not the stock up 100%".
                                # Beside the other rules (the first to sell wins): v36 /
                                # v36b furious already 30% from +30c, v37 5c from its
                                # best; it bites on v36 / v36b's regular buys (the ABR
                                # trail). All three, all sessions. 0 = off
FURIOUS_TEN_CENTS = True        # the owner, 10-08 night: a furious buy's first stop is
                                # v36's 10c leash - "when the stock starts moving, it
                                # doesn't stop with 3%" - for v36b (its 3% MAX_STOP on
                                # regular buys only) and v37 (10c, not the tighter of
                                # 10c and its 3%). The whole / half dollar line under
                                # the buy still counts, as for v36. v37's 5c cut still
                                # sells first (replayed: its 12 furious buys -$751 with
                                # it, -$1,758 with the 10c leash alone). False = before
V37_TWO_GREEN = True            # the owner, 10-08 night: v37 buys only after two green
                                # candles - the last two closed 1-minute candles each
                                # closed over its open - unless the move is furious
                                # (V37_FURIOUS_SPEED). The fast buy needed them already
                                # (ACCEL_BARS); now the regular buy too. 10-06/07/08: 73
                                # of v37's 134 buys had them (-$11.8 a trade live); the
                                # 57 regular ones without them lost -$263 (-$4.6 each)
V37_SWEEP_SECONDS = 6.0         # (V37_KEEP_TRYING off) it stops trying after this long,
                                # or once the ask is V37_ACCEL_CHASE over the breakout
V37_SWEEP_TRIES = 12            # ...or this many orders (Alpaca: ~200 requests a minute)
V37_KEEP_TRYING = True          # the owner, 10-07 noon: "keep trying - the market can
                                # stay irrational for a long time; stopping closes the
                                # door on a winner". One order per try at the ask + the
                                # cents, no price cap, no time limit: every print that
                                # is still furious and over the old high fires the next
                                # try, its rules checked again on fresh prices
V37_RETRY_GAP = 0.5             # ...at most one try a symbol this often
ORDER_BUDGET = 35               # orders an account may send in 60 seconds (each try is
                                # ~5 requests; Alpaca refuses past ~200 a minute)
V37_SWEEP_WAIT = 0.5            # seconds each order works (paper fills take ~200 ms)
SELL_DEEP = 0.10                # premarket (limit orders only) a fast buy's exit is a
                                # limit this far under the bid - it fills at the best
                                # bids there are, at once: "the exit as furious as can
                                # be, more than the entry - at any price" (the owner)
V37_SPIKE_AT = 0.30             # an acceleration buy up this much: out on giving
V37_SPIKE_GIVEBACK = 1 / 3      # back this share of the gain (spikes collapse fast)
V37_SCORE_FURIOUS = 0.0         # >0: a speed this high buys whatever the score (the
                                # owner: "the speed is everything" - never miss the
                                # furious ones); 0 = off
V37_STEADY_PAY = 0.0            # >0: a buy may pay at most this share over the price
                                # seen unless the stock is ripping (the owner: "you
                                # can do that only if the stock is ripping"); 0 = off
# PROPOSED 2026-10-06, off until the owner decides. IPDN: volume 497k, 446k,
# 242k at 8:11, 8:12, 8:13 - "the volume has come down three candles in a
# row" - and v37 bought at 8:14:29; it bought twice in 8:12 on falling
# volume. The owner: "buy when the stock is flying" - the playbook: "volume
# rising bar by bar, the bars 3-5x the size of the bars before them".
# The owner, a minute later: not "three candles coming down" - a runner on
# 10x, 8x, 7x its normal volume, green candles, price running, is a buy. The
# volume matters in context: high for THIS stock, and not fallen off a cliff.
V37_VOL_RULE = True             # the buy needs the volume, as below
V37_VOL_REL = 2.0               # high: the last 60 seconds' shares at least this
                                # x the stock's normal minute (the median of its
                                # last 30 closed minutes) - the playbook's 3-5x
V37_VOL_FADE = 0.70             # not fading: the last 60 seconds' shares at least
                                # this share of the busiest of its last 5 closed
                                # minutes. The owner, 2026-10-06: "70%, we should not
                                # go below that... after that the stock is getting
                                # ready to come down".
V37_VOL_PRICE = False           # (off - the owner's 70% is a floor) or less volume
                                # but the price moving FASTER: the
                                # last 60 seconds up at least as much as that busiest
                                # minute was. The owner: less volume and a faster
                                # price is the buyers winning the tug of war.
V37_VOL_EXIT = 0.0              # out once the last 60 seconds' shares fall under
                                # this share of what they were at the buy (0 = off)
V37_MAX_POSITIONS = 2
V37_MAX_ENTRIES = 0             # buys per name per day; 0 = no limit (the owner,
                                # 2026-10-06: the 10-buy limit locked v37 out of
                                # AIXI and SDEV before their second legs)
# CONFIRMATION (the owner, 2026-10-06, IPDN 8:35: through the 6.97 high on
# volume it had already traded at 8:14 and 8:20, after 15 minutes going
# sideways - "I would be on my toes, watching the second and third minutes
# before confirmation"). A break must be confirmed when it is a RE-BUY (the
# old high: the high of the day at the last sale) or comes after
# V37_SIDEWAYS_SECONDS without a new high (the old high: that ceiling):
# the last V37_CONFIRM_BARS closed 1-minute candles all closed GREEN above the
# old high ("the price still going up"), then a buy on a new high. The
# owner, a minute later: 15 minutes is too long - "after five minutes going
# sideways... I would have waited for one more candle and entered". A fresh run, or EXTRAORDINARY volume (the
# last 60 seconds more than any minute of the last 30), buys at once.
V37_CONFIRM_BY_BUY = (0, 0, 1, 2)   # candles to wait before the 1st, 2nd, 3rd,
                                # 4th (and every later) buy of a stock today. The
                                # owner, 2026-10-06: "the first one and the second
                                # one, no way - that's where the money is... the
                                # third can wait one minute"; after that, two.
V37_SIDEWAYS_SECONDS = 300
V37_EXTRAORDINARY = True
# A RE-BUY RIGHT AFTER A SALE (the owner, 2026-10-06: 65 of the day's trades
# were bought back within 15 seconds of selling): not within V37_REBUY_WAIT
# seconds of the sale unless the price is already V37_REBUY_JUMP above what
# the sale got - V37_REBUY_JUMP_CHEAP for a sale under V37_REBUY_CHEAP_UNDER
# (V37_REBUY_JUMP_PCT of the price instead, if smaller; 0 = not used). 0 =
# off. The owner, 10-08: 20 cents, not 30, and no 10% - then 10 cents under
# $2, 20 cents from $2 up.
V37_REBUY_WAIT = 60.0
V37_REBUY_JUMP = 0.20
V37_REBUY_JUMP_CHEAP = 0.0      # 10c under $2: built, OFF - the 1-minute replay showed
                                # no difference on 8 days and cannot judge a seconds rule;
                                # live stays at 20c (the owner, 10-08: judge on live data)
V37_REBUY_CHEAP_UNDER = 2.00
V37_REBUY_JUMP_PCT = 0.0
V37_FRESH_EXITS = True          # sells, stops and adds decide only on prints under
                                # V37_FRESH_SECONDS old. 2026-10-06: 76 sales were
                                # decided on older prices (up to 59s), 13 of them
                                # "stops" that sold ABOVE the buy; XHG 9:40 under
                                # r34.9 on a print 6.9s old.
V37_ODD_LOT_HIGH = True         # odd lots raise the high of the day (never trigger)
V37_FRESH_SECONDS = 2.0         # buy and add only on a print that traded this
                                # recently. AIXI, 4:17am 2026-10-06: while an order
                                # worked, prints queued; drained oldest first, each
                                # old print of the run-up looked like a new high
                                # and v37 bought 10 times in 100s on prices up to
                                # 58s old (one "new high" at 3.30 filled at 3.06)


class V36B(V36):
    """v36 with r34.13's three changes, on its own account (the owner,
    10-06: v36 on two accounts side by side - T6HH as it is, AUES with
    these). Replayed 09-28..10-06 on $15,000: +$2,272 / -$78 at fills 0.2% /
    1% worse, against v36's +$1,540 / -$985; worst trade -$39 against -$102."""

    name = "v36b"
    log_as = "[v36]"
    WICK_VETO = 0.60        # no buy under a candle that is 60%+ top wick
    MAX_STOP = 0.03         # the first stop no more than 3% under the trigger
    FRESH_EXITS = True      # stops and the trail act only on fresh prints


class V37(V36):
    """The simplest strategy - see the V37 settings above. Borrows v36's
    crowd count and v31's order machinery; nothing else."""

    name = "v37"

    def halt_threshold(self) -> float:
        env = os.getenv("V37_HALT_PCT")
        if env not in (None, ""):
            return float(env) / 100.0
        return Strategy.halt_threshold(self)

    def note_trade(self, s, price, size):
        super().note_trade(s, price, size)     # the last minutes' prints (_Momentum)
        t = s.last_print_ts or time.time()
        if not s.v37_high_ts:
            s.v37_high_ts = t                   # watching starts the clock
        if price > s.day_high:
            self.note_high(s, price, t)

    def note_skipped(self, s, price, conds):
        """An odd lot still raises the high of the day - the high the owner's
        chart shows - though it can never trigger a buy. IPDN 8:35am
        2026-10-06: the chart's highs were 6.97 and 7.10, set by odd lots
        (most IPDN prints were 1-70 shares); v37 never saw them and bought a
        round lot at 6.97 as "a new high" - out 6 seconds later, -$21."""
        if V37_ODD_LOT_HIGH and conds and set(conds) & NON_QUALIFYING_CONDS == {"I"}:
            if price > s.day_high:
                self.note_high(s, price, time.time())
            s.day_high = max(s.day_high, price)

    def clear(self, s):
        if s.shares <= 0 and s.entry:           # a v37 position just closed: a
            s.v37_old_high = s.day_high         # re-buy must confirm over this
            sold = [c for c in self.closed_today if c[0] == s.symbol]
            s.v37_sold_px = sold[-1][2] if sold else s.last_price
            s.v37_sold_ts = time.time()
        super().clear(s)

    async def restore_sale(self, s, t, px):
        """The last sale: the re-buy wait counts from it, and a re-buy must
        confirm over the day's high as it stood then."""
        s.v37_sold_px, s.v37_sold_ts = px, t
        try:
            high = await day_high_since_open(
                self.data, s.symbol, datetime.fromtimestamp(t, timezone.utc))
        except Exception:
            high = 0.0
        s.v37_old_high = max(s.v37_old_high, high, px)

    def in_grace(self, s) -> bool:
        """Within V37_GRACE_SECONDS of the buy (0 = no grace)."""
        return bool(V37_GRACE_SECONDS and s.entry_at
                    and time.time() - s.entry_at < V37_GRACE_SECONDS)

    def too_soon(self, s, price) -> bool:
        """Within V37_REBUY_WAIT of a sale and not yet the jump above it."""
        if not V37_REBUY_WAIT or not s.v37_sold_ts:
            return False
        if V37_FURIOUS_EXIT and self.furious_new_high(s, price):
            return False                        # furious, a new high: back on it
        if time.time() - s.v37_sold_ts >= V37_REBUY_WAIT:
            return False
        jump = (V37_REBUY_JUMP_CHEAP if V37_REBUY_JUMP_CHEAP
                and s.v37_sold_px < V37_REBUY_CHEAP_UNDER else V37_REBUY_JUMP)
        if V37_REBUY_JUMP_PCT:
            jump = min(jump, V37_REBUY_JUMP_PCT * s.v37_sold_px)
        return price < s.v37_sold_px + jump

    def note_high(self, s, price, t):
        """A print above the high of the day. After V37_SIDEWAYS_SECONDS
        without one, the old ceiling is a level to confirm over."""
        if (s.day_high > 0 and s.v37_high_ts and not s.in_position
                and t - s.v37_high_ts >= V37_SIDEWAYS_SECONDS):
            s.v37_old_high = s.day_high
        s.v37_high_ts = t

    def extraordinary(self, s) -> bool:
        """The last 60 seconds traded more than any closed minute of the last 30."""
        vols = [b.v for b in s.bars[-30:]]
        return bool(vols) and self.pace(s) > max(vols)

    def not_running(self, s) -> str:
        """V37_MOMENTUM: why the stock is NOT running right now - "" when it
        is, when it is ripping, or when there are too few closed minutes to
        judge. Checked on the minutes before the buy."""
        if not V37_MOMENTUM or self.ripping(s):
            return ""
        bars = s.bars
        need = max(V37_STAIR_MINUTES + 1, V37_CROWD_STAYS, 3)
        if len(bars) < need:
            return ""
        last = bars[-1]
        if V37_LAST_GREEN and not last.green:
            return "the last candle closed red"
        rng = last.h - last.l
        if rng > 0 and (last.h - last.c) / rng > V37_WICK_MAX:
            return "a top wick on the last candle (%.0f%% of it)" % (
                100 * (last.h - last.c) / rng)
        before = max(bars[-2].c - bars[-2].o, bars[-3].c - bars[-3].o)
        if before > 0 and last.c - last.o < V37_BODY_FADE * before:
            return "green bodies shrinking (%.4f after %.4f)" % (last.c - last.o, before)
        for k in range(1, V37_STAIR_MINUTES + 1):
            if bars[-k].l < bars[-k - 1].l:
                return "not stepping up (a lower low %d min ago)" % k
        normal = statistics.median(b.v for b in bars[-30:])
        for k in range(1, V37_CROWD_STAYS + 1):
            if bars[-k].v < V37_CROWD_REL * normal:
                return "volume not staying up (%.1fx normal %d min ago)" % (
                    bars[-k].v / normal if normal else 0.0, k)
        return ""

    def confirm_bars(self, s) -> int:
        """How many candles the next buy of this stock waits for."""
        if not V37_CONFIRM_BY_BUY:
            return 0
        return V37_CONFIRM_BY_BUY[min(s.v36_entries, len(V37_CONFIRM_BY_BUY) - 1)]

    def confirmed(self, s) -> bool:
        """confirm_bars() closed 1-minute candles closed green above the old
        high (a re-buy, or a break out of a sideways stretch) - or
        extraordinary volume. No old high, or no candles due: no wait."""
        need = self.confirm_bars(s)
        if not need or not s.v37_old_high:
            return True
        if V37_EXTRAORDINARY and self.extraordinary(s):
            return True
        recent = s.bars[-need:]
        return (len(recent) == need
                and all(b.green and b.c > s.v37_old_high for b in recent))

    def volume_ok(self, s) -> bool:
        """V37_VOL_RULE: the last 60 seconds' shares HIGH for this stock
        (V37_VOL_REL x the median of its last 30 closed minutes) and NOT
        FADING (V37_VOL_FADE x the busiest of its last 5). A name with no
        closed minutes yet has nothing to compare: it passes."""
        if not V37_VOL_RULE:
            return True
        vols = [b.v for b in s.bars[-30:]]
        if not vols:
            return True
        pace = self.pace(s)
        normal = statistics.median(vols)
        if pace < V37_VOL_REL * normal:
            return False
        if pace >= V37_VOL_FADE * max(vols[-5:]):
            return True
        if not V37_VOL_PRICE or not s.v37_prints:
            return False
        busiest = max(s.bars[-5:], key=lambda b: b.v)
        then = busiest.c / busiest.o - 1 if busiest.o > 0 else 0.0
        first = s.v37_prints[0][1]
        now = s.last_price / first - 1 if first > 0 else 0.0
        return now > 0 and now >= then

    def fast(self, s, price) -> bool:
        """Up V37_FAST_PCT within the last V37_FAST_SECONDS, on at least
        V37_FAST_DOLLARS traded in them."""
        p = s.v37_prints
        if len(p) < 2:
            return False
        low = min(x[1] for x in p)
        dollars = sum(x[1] * x[2] for x in p)
        return low > 0 and price >= low * (1 + V37_FAST_PCT) \
            and dollars >= V37_FAST_DOLLARS

    def flying(self, s, price) -> bool:
        """V37_SPEED_MIN on: the owner's speed at least that, on real money.
        Off: up V37_FAST_PCT in V37_FAST_SECONDS (fast())."""
        if not V37_SPEED_MIN:
            return self.fast(s, price)
        dollars = sum(x[1] * x[2] for x in s.v37_prints)
        return self.real_speed(s, price) >= V37_SPEED_MIN and dollars >= V37_FAST_DOLLARS

    def buy_limit(self, ask, ceiling) -> float:
        return min(ask + (0.0 if self.name in BUY_AT_ASK else V37_ASK_PLUS), ceiling)

    def stop_pct(self, s, price) -> float:
        """V37_STOP_SPEED: the stop's distance under the buy - a share of the
        last minute's move, within V37_STOP_MIN..V37_STOP_MAX. 0 = the old
        V37_STOP_CENTS."""
        if not V37_STOP_SPEED:
            return 0.0
        return min(V37_STOP_MAX, max(V37_STOP_MIN, V37_STOP_SHARE * self.move(s, price)))

    def stop_for(self, s) -> float:
        """The stop under the average now held - for a furious buy never more
        than V36_FURIOUS_STOP_CENTS under it."""
        if s.v37_stop_pct:
            stop = s.entry * (1 - s.v37_stop_pct)
        else:
            stop = s.entry - V37_STOP_CENTS
        if (V37_FURIOUS_EXIT and V36_FURIOUS_STOP_CENTS
                and getattr(s, "v37_accel", 0.0) >= V37_FURIOUS_SPEED):
            if FURIOUS_TEN_CENTS:               # the leash: 10c, not the tighter of two
                return s.entry - V36_FURIOUS_STOP_CENTS
            stop = max(stop, s.entry - V36_FURIOUS_STOP_CENTS)
        return stop

    def entry_cap(self, s, price) -> float:
        """How far over the price seen the first buy may pay: half of the last
        minute's move, between V37_ENTRY_PCT and V37_ENTRY_MAX. A stock up 20%
        in a minute may cost 10% more to get into - "sometimes I get in more
        like 10% more, but the stock took me to a higher level"."""
        if V37_STEADY_PAY and not self.ripping(s):
            return V37_STEADY_PAY               # steady, not ripping: no chasing
        return min(V37_ENTRY_MAX, max(V37_ENTRY_PCT, 0.5 * self.move(s, price)))

    def in_the_crowd(self, s) -> bool:
        """The #1 or #2 by activity with a big crowd - or the day's top gainer
        with real money trading."""
        if self.top_gainer(s):
            return True
        return (self.crowd_rank(s.symbol) <= V37_CROWD_TOP
                and self.crowd_dollars(s.symbol) >= V37_CROWD_MIN_DOLLARS)

    async def maybe_enter(self, s, price, fast, base):
        if not entries_allowed():
            return
        if s.symbol not in self.qualified:      # the scanner: $1-$20, up 10%+
            return
        if not self.price_ok(s, price):
            return
        if len(self.open_positions()) >= V37_MAX_POSITIONS:
            return
        if V37_MAX_ENTRIES and s.v36_entries >= V37_MAX_ENTRIES:
            return
        if not self.fresh(s):
            return                              # an old print: the market has moved on
        if self.too_soon(s, price):
            return                              # just sold it: wait, or a real jump
        if price <= s.day_high:
            return                              # every buy ABOVE the high of the day
                                                # (the owner, 2026-10-06) - touching
                                                # it is not a new high
        if V37_HOD_CLEAR and s.day_high:
            # From the high of the closed minutes (and the morning's, seeded),
            # not the high this minute's prints keep raising: measured from
            # that one, a stock climbing a cent at a time never cleared it
            # (10-05 replayed: 12 trades became 1).
            ref = s.hod_closed or s.day_high
            if price < ref + max(V37_HOD_CLEAR[0], V37_HOD_CLEAR[1] * ref) - 1e-9:
                return                          # a cent over it is a touch too
        if not self.confirmed(s):
            return                              # a re-buy, or out of a sideways stretch:
                                                # not confirmed above the old high yet
        accel = self.accelerating(s) if V37_ACCEL else 0.0
        if V37_ACCEL and not accel and self.furious(s, price):
            accel = self.real_speed(s, price)   # the speed overrides the crowd rules
        if accel and V37_ACCEL_REAL and self.real_speed(s, price) < ACCEL_SPEED:
            accel = 0.0                         # the candles say fast, the price does not
        if accel and V37_ACCEL_TAPE and not self.tape_ok(s):
            accel = 0.0                         # nobody buying at the ask
        if accel and s.bars and price > s.bars[-1].h:
            base = (max(s.bars[-1].h, s.day_high) if V37_ACCEL_FROM_HIGH
                    else s.bars[-1].h)          # the breakout level: BIYA 8:20 broke
            if (V37_ACCEL_CHASE and not self.keeps_trying(s, price)
                    and price > self.fast_top(base)):                     # $3.10
                if time.time() - s.v37_skip_logged >= 30:   # the spike has run
                    s.v37_skip_logged = time.time()
                    self.log.info("[v37] SKIP %s at %.4f - %.0f%% over the breakout "
                                  "level %.4f: too late for a fast buy",
                                  s.symbol, price, 100 * (price / base - 1), base)
                return
            return await self.accel_buy(s, price, accel)
        if not self.in_the_crowd(s) or not self.flying(s, price):
            return
        if V37_TWO_GREEN and not self.two_green(s) and not self.furious(s, price):
            if time.time() - s.v37_skip_logged >= 30:
                s.v37_skip_logged = time.time()
                self.log.info("[v37] SKIP %s at %.4f - the last two candles are not "
                              "both green (not furious)", s.symbol, price)
            return
        if not self.volume_ok(s):
            return                              # flying means the volume is rising
        why = self.not_running(s)
        rip = self.rip_exception(s, price)
        if (not why and V37_SCORE_MIN
                and not (rip and not V37_RIP_NO_RED)
                and not (V37_SCORE_FURIOUS
                         and self.real_speed(s, price) >= V37_SCORE_FURIOUS)):
            points, parts = self.score(s, price)
            if points is None:
                why = parts                     # a red last candle or a huge wick:
                                                # no buy, ripping or not
            elif points < V37_SCORE_MIN and not rip:
                why = "score %s/15 under %d: %s" % (points, V37_SCORE_MIN, parts)
        if why:                                 # it spiked, it is not running
            if time.time() - s.v37_skip_logged >= 30:
                s.v37_skip_logged = time.time()
                self.log.info("[v37] SKIP %s at %.4f - not running: %s",
                              s.symbol, price, why)
            return
        if V37_CONFIRM_ASK:                     # the market, not one print
            q = self.live_quote(s)
            ask = q[1] if q else await self.data.quote(s.symbol, "ask")
            if ask is not None and ask <= s.day_high:
                if time.time() - s.v37_skip_logged >= 30:
                    s.v37_skip_logged = time.time()
                    self.log.info("[v37] SKIP %s at %.4f - the ask %.4f is not above "
                                  "the high %.4f: that print was not the market",
                                  s.symbol, price, ask, s.day_high)
                return
        lock = self.lock(s.symbol)
        if lock.locked():
            return
        async with lock:
            if s.in_position:
                return
            await self.v37_buy(s, price)

    def furious(self, s, price) -> bool:
        """V37_FURIOUS_SPEED on real money in the last minute, the last candle
        not red."""
        return self.speeding(s, price)

    @staticmethod
    def two_green(s) -> bool:
        """V37_TWO_GREEN: the last two closed 1-minute candles closed green."""
        return len(s.bars) >= 2 and s.bars[-1].green and s.bars[-2].green

    def keeps_trying(self, s, price) -> bool:
        """V37_KEEP_TRYING - for the furious movers only (the owner, 10-07: "the
        rest - keep the cap, it's a nice safety net")."""
        return V37_KEEP_TRYING and self.speeding(s, price)

    def fast_top(self, base) -> float:
        """The safety net: a fast buy never pays V37_ACCEL_CHASE over the
        breakout level."""
        return base * (1 + V37_ACCEL_CHASE) if V37_ACCEL_CHASE else float("inf")

    async def accel_buy(self, s, price, accel):
        """V37_ACCEL: over the last minute's high, the ask agreeing; sized by
        the speed (V37_ACCEL_SIZE)."""
        if V37_CONFIRM_ASK:
            q = self.live_quote(s)
            ask = q[1] if q else await self.data.quote(s.symbol, "ask")
            if ask is not None and ask <= s.bars[-1].h:
                return
        if await self.fast_buy_no(s, price):
            return                              # falling, or the market not there
        speed = max(accel, self.real_speed(s, price))
        share = 0.0
        for at, frac in V37_ACCEL_SIZE:
            if speed >= at:
                share = frac
        if not share:
            return
        lock = self.lock(s.symbol)
        if lock.locked():
            return
        async with lock:
            if s.in_position:
                return
            base = (max(s.bars[-1].h, s.day_high) if V37_ACCEL_FROM_HIGH
                    else s.bars[-1].h)
            keep = self.keeps_trying(s, price)
            if keep:
                if time.time() - getattr(s, "v37_try_at", 0.0) < V37_RETRY_GAP:
                    return                      # the next print tries again
                s.v37_try_at = time.time()
                sweep_to = float("inf")         # no cap: the ask + the cents, each try
            else:
                sweep_to = self.fast_top(base) if V37_SWEEP else None
            await self.v37_buy(s, price, account_share=share, accel=speed,
                               sweep_to=sweep_to, keep=keep)

    async def v37_buy(self, s, price, account_share=None, accel=0.0, sweep_to=None,
                      keep=False):
        spd = self.speed(s, price)              # logged for every buy, rule on or off
        pts, parts = self.score(s, price)       # the same
        eq = await self.broker.equity(self.day_start_equity)
        if self.v37_full(s, eq) <= 0:
            return                              # no room beside the position held
                                                # (09-30 replayed: a division by zero)
        starter = (account_share / self.v37_full(s, eq) if account_share
                   else V37_STARTER)            # a share of a full position
        cap = self.entry_cap(s, price)
        worst = price * (1 + cap)
        if sweep_to and sweep_to > price:
            cap = (max(cap, sweep_to / price - 1) if sweep_to != float("inf")
                   else float("inf"))           # tries up to the safety net, or none...
            worst = price + 2 * self.paid_up_cents(price)  # ...sized on the likely fill
                                                           # (as before r34.36: the same sizes)
        held_all = sum(x.shares * (x.last_price or price)
                       for x in self.open_positions())
        room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
        shares = int(min(eq * self.v37_full(s, eq) * starter, room) / worst)
        if shares * price < MIN_TRADE_DOLLARS:
            return
        filled = await self.buy(s.symbol, shares, price, cap,
                                floor=s.day_high,   # never under the old high
                                sweep=(self.sweep_cents(price)
                                       if sweep_to and sweep_to > price else None),
                                keep=keep)
        if not filled:
            return
        s.shares = filled
        s.entry = await self.broker.avg_entry(s.symbol) or price
        s.v36_first = s.entry
        s.v36_adds = 0
        s.v37_stop_pct = self.stop_pct(s, price)
        s.v37_accel = accel                     # stop_for: a furious buy's 10 cents
        s.stop = self.stop_for(s)
        self.set_line(s, price)                 # and under the whole / half dollar
        if s.v36_line:
            s.stop = max(s.stop, min(self.line_stop(price),
                                     s.entry * (1 - MIN_STOP_PCT)))
        s.v37_pace_at_buy = self.pace(s)
        s.v37_peak_after = 0.0
        s.v37_bid_over = False
        s.v37_accel = accel
        s.v37_accel_added = False
        s.peak = s.entry
        s.trail_stop = 0.0
        s.armed = False
        s.adopted = False
        s.entry_kind = "accel" if accel else "rip"
        s.traded_today = True
        s.v36_entries += 1
        s.entry_at = time.time()
        self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                         kind="rip", stop=s.stop, speed=round(spd, 3),
                         score=pts, parts=parts)
        self.log.info("[v37] ENTER %s %d @ %.4f (print %.4f) = $%.0f (%.1f%% of "
                      "equity) - %s, buy %d today | crowd #%d, "
                      "$%.0fk in %d min | stop %.4f | adds at %.4f and %.4f | "
                      "speed %.2f | score %s (%s)",
                      s.symbol, filled, s.entry, price, filled * s.entry,
                      100 * filled * s.entry / eq if eq else 0.0,
                      "ACCELERATING %.2f, %.0f%% of the account" % (
                          accel, 100 * starter * self.v37_full(s, eq))
                      if accel else "a tenth of a position", s.v36_entries,
                      self.crowd_rank(s.symbol),
                      self.crowd_dollars(s.symbol) / 1000, V36_CROWD_MINUTES,
                      s.stop, s.v36_first + V37_ADD1_CENTS,
                      s.v36_first + V37_ADD2_CENTS, spd, pts, parts)
        await self.quote_the_crowd()

    def others_pct(self, s, eq) -> float:
        return sum(x.shares * (x.last_price or x.entry)
                   for x in self.open_positions() if x is not s) / eq if eq else 0.0

    def v37_full(self, s, eq=None) -> float:
        """A full position for `s`: V37_SOLO_PCT alone; beside another, what
        is left under V37_PAIR_TOTAL, never over V37_PAIR_PCT."""
        if not [x for x in self.open_positions() if x is not s]:
            return V37_SOLO_PCT
        eq = eq or self.day_start_equity
        return max(0.0, min(V37_PAIR_PCT, V37_PAIR_TOTAL - self.others_pct(s, eq)))

    async def make_room(self, s, eq):
        """A second stock keeps running (+V37_ADD3_CENTS): any other position
        over V37_PAIR_PCT of the account is trimmed down to it."""
        for x in self.open_positions():
            if x is s or not x.last_price:
                continue
            over = x.shares * x.last_price - eq * V37_PAIR_PCT
            n = int(over / x.last_price)
            if over > 0.02 * eq * V37_PAIR_PCT and n > 0:
                async with self.lock(x.symbol):
                    if x.in_position:
                        self.log.info("[v37] %s TRIM to %.0f%% of the account - "
                                      "room for %s", x.symbol, 100 * V37_PAIR_PCT,
                                      s.symbol)
                        await self.reduce(x, min(n, int(x.shares)), "make-room")

    async def v37_add(self, s, price, to_fraction):
        async with self.lock(s.symbol):
            if not s.in_position:
                return
            s.v36_adds += 1
            eq = await self.broker.equity(self.day_start_equity)
            if to_fraction is None:                 # the third step, beside another
                await self.make_room(s, eq)
                to_fraction = 1.0
            worst = price * (1 + BUY_CHASE_CAP)
            held_all = sum(x.shares * (x.last_price or price)
                           for x in self.open_positions())
            room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
            want = max(0.0, eq * self.v37_full(s, eq) * to_fraction - s.shares * price)
            shares = int(min(want, room) / worst)
            if shares * price < MIN_TRADE_DOLLARS:
                return
            filled = await self.buy(s.symbol, shares, price)
            if filled:
                s.shares += filled
                s.entry = await self.broker.avg_entry(s.symbol) or s.entry
                s.peak = max(s.peak, price)
                # No tolerance for loss on the whole position: an add filled
                # over the price (ask + 10c on a fast stock) lifts the average
                # above the high, and "half the gain" then never fires.
                s.stop = max(s.stop, self.stop_for(s))
                self.log.info("[v37] ADD %s to %.0f%% of a position: +%d @ %.4f -> "
                              "%d shares, average %.4f, stop %.4f", s.symbol,
                              100 * to_fraction, filled, price, s.shares, s.entry,
                              s.stop)

    async def evaluate(self, s, price):
        if await self.halted():
            if s.in_position:
                await self.exit(s, "halted")
            return
        if await self.bid_stop(s):
            return
        if self.off_quote(s, price):
            self.note_off_quote(s, price)       # not the market: decides nothing
            return
        if not s.in_position:
            await self.maybe_enter(s, price, None, None)
            return
        if V37_FRESH_EXITS and not self.fresh(s):
            return                              # an old print: the next fresh one decides
        new_high = price >= s.peak
        s.peak = max(s.peak, price)
        self.raise_line(s, price)
        if price <= s.stop:
            await self.exit(s, "stop")          # no tolerance for loss
            return
        if (V37_VOL_EXIT and s.v37_pace_at_buy
                and self.pace(s) < V37_VOL_EXIT * s.v37_pace_at_buy):
            await self.exit(s, "volume-gone")   # the crowd has left
            return
        if self.in_grace(s):
            top = 0.0                           # the first seconds: only the stop sells
        else:
            s.v37_peak_after = max(s.v37_peak_after or s.entry, price)
            top = s.v37_peak_after if V37_GRACE_FORGET else s.peak
        gain = top - s.entry
        armed = (top >= s.entry * (1 + V37_GIVEBACK_ARM)
                 and gain >= V37_GIVEBACK_ARM_CENTS - 1e-9)
        if V37_GIVEBACK_FROM_BID:               # a gain the bid can pay
            q = self.live_quote(s)
            if q and q[0] > s.entry + 1e-9:
                s.v37_bid_over = True
            armed = armed and getattr(s, "v37_bid_over", False)
        if V37_FURIOUS_EXIT and getattr(s, "v37_accel", 0.0) >= V37_FURIOUS_SPEED:
            fline = self.furious_line(s, top)   # up 30c: 30% of the gain back, out
            if fline and price <= fline:
                q = self.live_quote(s) if V37_GIVEBACK_BID else None
                if not (q and q[0] > fline):
                    await self.exit(s, "giveback")
                    return
        if V37_TRAIL_CENTS:                     # the owner's cents off the best
            best = max(top, s.entry)
            tline = best - V37_TRAIL_CENTS
            if price <= tline + 1e-9:
                q = self.live_quote(s) if V37_GIVEBACK_BID else None
                if not (q and q[0] > tline):    # the bid agrees
                    await self.exit(s, "trail")
                    return
            if not V37_TRAIL_KEEPS_HALF:
                armed = False                   # "half the gain" set aside
        if await self.big_gain_exit(s, price):
            return                              # up $1+, then 30% of it back
        back = V37_GIVEBACK
        if (getattr(s, "v37_accel", 0.0) and V37_SPIKE_AT
                and top >= s.entry * (1 + V37_SPIKE_AT)):
            back = V37_SPIKE_GIVEBACK           # a spike: keep two thirds of it
        line = s.entry + (1 - back) * gain
        if gain > 0 and armed and price <= line:
            q = self.live_quote(s) if V37_GIVEBACK_BID else None
            if not (q and q[0] > line):         # the bid agrees the gain is gone
                await self.exit(s, "giveback")  # half of the profit gone
                return
        if (V37_ACCEL and getattr(s, "v37_accel", 0.0) >= V37_FURIOUS_SPEED
                and not getattr(s, "v37_accel_added", True) and new_high
                and self.fresh(s) and price >= s.v36_first * (1 + V37_ACCEL_ADD_AT)
                and self.real_speed(s, price) >= V37_FURIOUS_SPEED):
            s.v37_accel_added = True            # bigger, faster: to V37_ACCEL_MAX_PCT
            eq = await self.broker.equity(self.day_start_equity)
            full = self.v37_full(s, eq)
            if full > 0:
                await self.v37_add(s, price, V37_ACCEL_MAX_PCT / full)
            return
        steps = ((V37_ADD1_CENTS, V37_ADD1_TO), (V37_ADD2_CENTS, V37_ADD2_TO))
        if len(self.open_positions()) > 1:
            steps += ((V37_ADD3_CENTS, None),)     # beside another: make room, grow
        if s.v36_adds < len(steps) and new_high and self.fresh(s):
            at, to_fraction = steps[s.v36_adds]
            if price >= s.v36_first + at:
                await self.v37_add(s, price, to_fraction)


async def day_high_since_open(data, symbol, now=None) -> float:
    """The highest one-minute bar since 4:00am ET today, premarket included -
    0.0 before 4am or if no bars come back. IPDN, 8:10am 2026-10-06: a
    restart left the bot knowing only the prints since the restart, so 5.64
    looked like a high on a day already up to 5.83, and v37 bought three
    times under it. If the newest bars are refused (SIP's last 15 minutes
    need a paid plan) it asks again without them."""
    now = now or datetime.now(timezone.utc)
    start = now.astimezone(ET).replace(hour=4, minute=0, second=0, microsecond=0)
    if now <= start:
        return 0.0
    for end in (now, now - timedelta(minutes=16)):
        if end <= start:
            break
        try:
            rows = await data.bars_between(symbol, start, end)
        except Exception:
            continue
        return max((r[3] for r in rows), default=0.0)
    return 0.0


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
        self.news_client = NewsClient(key, secret, raw_data=True)   # NEWS, read-only

        self.strategies = []
        self.history_tasks = []
        # Which strategy each account runs: SLOT_DEFAULTS, or SLOT_V31 /
        # SLOT_V34 / SLOT_V35 in the environment.
        slots = account_classes()
        for slot, k, s_ in (("v31", key, secret),
                            ("v32", os.environ.get("V32_API_KEY"),
                             os.environ.get("V32_SECRET_KEY")),
                            ("v34", os.environ.get("V33_API_KEY"),
                             os.environ.get("V33_SECRET_KEY")),
                            ("v35", os.environ.get("V35_API_KEY"),
                             os.environ.get("V35_SECRET_KEY"))):
            if slots[slot] is None:
                log.warning("account slot %s is OFF (SLOT_%s=off)", slot, slot.upper())
                continue
            self.add_strategy(slots[slot], k, s_)

        for strat in self.strategies:
            self.data.trade_sinks.append(strat.offer_tick)
            self.data.bar_sinks.append(strat.offer_bar)
            self.data.quote_sinks.append(strat.offer_quote)

        self.last_auth_warn = 0.0
        self.last_probe = 0.0
        self.roster: set = set()                # the scanner's list at the last scan
        self.roster_all_at = 0.0
        self.prev_highs: dict[str, float] = {}
        self.prev_closes: dict[str, float] = {}
        self.day_highs: dict[str, float] = {}   # from today's bars, once a day
        self.day_highs_date = None
        self.news_day = None                    # NEWS: today's checks
        self.news_ids: set = set()              # (story id, sym) already logged
        self.news_last = 0.0
        self.news_next_at = 0.0
        self.borrow_seen: dict[str, str] = {}   # BORROW: what each name showed
        self.borrow_day = None

    async def history(self, strat, first, last):
        try:
            await strat.dump_history(first, last)
        except Exception as e:
            log.error("[%s] history %s..%s: %s", strat.name, first, last, e)

    async def sec_dump(self):
        """SEC_DUMP_DAYS: read-only. Each account's fills on those days into the
        log, then the market around every buy of the three (MarketData.dump_seconds)."""
        first = SEC_DUMP_DAYS[0]
        last = (datetime.fromisoformat(SEC_DUMP_DAYS[-1]) + timedelta(days=1)).date().isoformat()
        buys = []
        for strat in self.strategies:
            try:
                fills = await strat.dump_history(first, last) or []
            except Exception as e:
                log.error("[%s] SECDUMP fills %s..%s: %s", strat.name, first, last, e)
                continue
            buys += [(t, sym) for t, sym, side, q, px in fills if side == "buy"
                     and datetime.fromtimestamp(t, ET).date().isoformat() in SEC_DUMP_DAYS]
        try:
            await self.data.dump_seconds(buys)
        except Exception as e:
            log.error("SECDUMP: %s", e)

    # ---- the news and borrow log (information only) -------------------------

    async def read_news(self, symbols, start, end=None, limit=50):
        """The data service's stories on `symbols` from `start` (epoch) to `end`,
        newest first, at most `limit` (50 a request); NEWS_RPM paced."""
        if NEWS_RPM:
            wait = self.news_next_at - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self.news_next_at = max(time.monotonic(), self.news_next_at) + \
                60.0 / NEWS_RPM * max(1, -(-limit // 50))
        req = NewsRequest(symbols=",".join(symbols), limit=limit, sort="desc",
                          start=datetime.fromtimestamp(start, timezone.utc),
                          end=datetime.fromtimestamp(end, timezone.utc) if end else None)
        raw = await asyncio.to_thread(self.news_client.get_news, req)
        return list((raw or {}).get("news") or [])

    async def news_check(self):
        """NEWS: the list's names. A name's first check of the day reaches back
        to the last session's 4pm close; later ones NEWS_OVERLAP before the
        last check. Each story is logged once per name."""
        now = datetime.now(ET)
        today = now.date()
        if self.news_day != today:
            self.news_day = today
            NEWS.clear()
            NEWS_FROM.clear()
            self.news_ids = set()
            self.news_last = 0.0
        syms = sorted(self.roster)
        since = news_since(today).timestamp()
        new = [s for s in syms if s not in NEWS_FROM]
        old = [s for s in syms if s in NEWS_FROM]
        checked = now.timestamp()
        for group, start, limit, first in (
                (new, since, 200, True),
                (old, max(since, self.news_last - NEWS_OVERLAP), 50, False)):
            for i in range(0, len(group), NEWS_BATCH):
                batch = group[i:i + NEWS_BATCH]
                items = await self.read_news(batch, start, None, limit)
                self.take_news(items, set(batch), checked)
                if first:
                    none = [s for s in batch if not NEWS.get(s)]
                    for s in batch:
                        NEWS_FROM[s] = since
                    if none:
                        log.info("NEWS none since %s: %s", datetime.fromtimestamp(
                            since, ET).strftime("%m-%d %H:%M"), " ".join(none))
        self.news_last = checked

    def take_news(self, items, wanted, now):
        """Each new story on a wanted name into NEWS and the log, oldest first."""
        for it in sorted(items, key=lambda x: x.get("created_at") or ""):
            sid = it.get("id")
            syms = sorted(s for s in (it.get("symbols") or [])
                          if s in wanted and (sid, s) not in self.news_ids)
            if not syms:
                continue
            t = _epoch(it["created_at"]) if it.get("created_at") else now
            head = " ".join((it.get("headline") or "").split())
            flags = news_flags(head + " " + (it.get("summary") or ""))
            src = it.get("source") or "?"
            for s in syms:
                self.news_ids.add((sid, s))
                NEWS.setdefault(s, []).append((t, src, head, flags))
                NEWS[s].sort()
            log.info("NEWS %s %s (%s ago) [%s] %s%s", " ".join(syms),
                     datetime.fromtimestamp(t, ET).strftime("%m-%d %H:%M"), _ago(now - t),
                     src, head[:200], " | " + ", ".join(flags) if flags else "")

    async def news_loop(self):
        if not NEWS_LOG:
            return
        while True:
            await asyncio.sleep(NEWS_SECONDS)
            try:
                if self.roster:
                    await self.news_check()
            except Exception as e:
                log.error("NEWS: %s", e)

    def note_borrow(self, assets):
        """BORROW from the scanner's asset list (no extra request)."""
        try:
            fresh = {a.symbol: (getattr(a, "easy_to_borrow", None),
                                getattr(a, "shortable", None)) for a in assets}
        except Exception as e:
            log.error("BORROW: %s", e)
            return
        BORROW.clear()
        BORROW.update(fresh)

    def log_borrow(self, symbols):
        """BORROW: the list's names as they come in (once a day), and any change."""
        if not NEWS_LOG:
            return
        today = datetime.now(ET).date()
        if self.borrow_day != today:
            self.borrow_day = today
            self.borrow_seen = {}
        new, changed = {}, []
        for s in sorted(symbols):
            b = borrow_text(s)
            old = self.borrow_seen.get(s)
            if old is None:
                new.setdefault(b, []).append(s)
            elif old != b:
                changed.append("%s %s -> %s" % (s, old, b))
            self.borrow_seen[s] = b
        if new:
            log.info("BORROW in: %s", " | ".join(
                "%s: %s" % (b, " ".join(new[b])) for b in
                ("hard to borrow", "not shortable", "easy to borrow", "borrow unknown")
                if b in new))
        for c in changed:
            log.info("BORROW change: %s", c)

    async def news_dump(self):
        """NEWS_DUMP_DAYS, once: each account's fills over the days into the log
        (as HISTORY_DUMP), then the headlines of every stock bought each day,
        from the 4pm close before to 8pm. Read-only."""
        await asyncio.sleep(30)                 # the first scan fills BORROW
        first, last = NEWS_DUMP_DAYS
        end = (datetime.fromisoformat(last) + timedelta(days=1)).date().isoformat()
        firsts = {}                             # (ET date, sym) -> first buy
        for strat in self.strategies:
            try:
                fills = await strat.dump_history(first, end) or []
            except Exception as e:
                log.error("[%s] NEWSDUMP fills %s..%s: %s", strat.name, first, last, e)
                continue
            for t, sym, side, q, px in fills:
                if side == "buy":
                    k = (datetime.fromtimestamp(t, ET).date(), sym)
                    firsts[k] = min(firsts.get(k, t), t)
        log.info("NEWSDUMP plan: %d stock-days bought, %s..%s", len(firsts), first, last)
        done = 0
        for (day, sym), t0 in sorted(firsts.items()):
            since = news_since(day)
            until = datetime(day.year, day.month, day.day, 20, 0, tzinfo=ET)
            try:
                items = await self.read_news([sym], since.timestamp(), until.timestamp(), 50)
            except Exception as e:
                log.error("NEWSDUMP %s %s: %s", day, sym, e)
                continue
            done += 1
            log.info("NEWSDUMP %s %s: %d headlines from %s, first buy %s, %s (now)",
                     day, sym, len(items), since.strftime("%m-%d %H:%M"),
                     datetime.fromtimestamp(t0, ET).strftime("%H:%M:%S"), borrow_text(sym))
            for it in sorted(items, key=lambda x: x.get("created_at") or ""):
                head = " ".join((it.get("headline") or "").split())
                flags = news_flags(head + " " + (it.get("summary") or ""))
                log.info("NEWSDUMP %s %s %s [%s] %s%s", day, sym,
                         datetime.fromtimestamp(_epoch(it["created_at"]) if it.get(
                             "created_at") else t0, ET).strftime(
                             "%m-%d %H:%M"), it.get("source") or "?", head[:200],
                         " | " + ", ".join(flags) if flags else "")
        log.info("NEWSDUMP done: %d of %d stock-days", done, len(firsts))

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
            self.note_borrow(assets)
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
                    self.prev_closes[sym] = float(getattr(prev, "close", 0) or 0)
                except Exception:
                    continue
        self.log_probe(probe)
        return picks

    def log_roster(self, picks, symbols):
        """ROSTER_LOG_MIN: the names the scanner passed, as they come and go,
        and the whole list every ROSTER_LOG_MIN minutes - with each name's
        high so far."""
        if not ROSTER_LOG_MIN:
            return
        now = time.time()
        cur = set(symbols)
        new, gone = sorted(cur - self.roster), sorted(self.roster - cur)
        if new or gone:
            log.info("ROSTER %d names | in: %s | out: %s", len(cur),
                     " ".join("%s %.2f" % (s, picks[s]) for s in new) or "-",
                     " ".join(gone) or "-")
        if now - self.roster_all_at >= ROSTER_LOG_MIN * 60:
            self.roster_all_at = now
            log.info("ROSTER ALL %d%s: %s", len(cur),
                     " (of %d)" % len(picks) if len(picks) > len(cur) else "",
                     " ".join("%s %.2f" % (s, picks[s]) for s in sorted(cur)))
        self.roster = cur

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
                        self.log_roster(picks, symbols)
                        self.log_borrow(symbols)
                        # The real high of the day BEFORE a name can be
                        # traded - a restart must not forget the morning.
                        await self.seed_day_highs(symbols)
                        for strat in self.strategies:
                            strat.qualified.update(symbols)
                            for sym in symbols:
                                st = strat.st(sym)
                                st.day_high = max(st.day_high, picks[sym])
                                strat.seed_high(st, self.day_highs.get(sym, 0.0))
                                st.prev_high = self.prev_highs.get(sym, st.prev_high)
                                st.ref_price = self.prev_closes.get(sym, st.ref_price)
                        await self.data.subscribe(symbols)
            except Exception as e:
                log.error("scanner: %s", e)
            await asyncio.sleep(SCAN_SECONDS)

    async def seed_day_highs(self, symbols):
        """Each name's high since 4am, read from today's bars the first time
        it is seen today (eight at a time)."""
        today = datetime.now(ET).date()
        if self.day_highs_date != today:
            self.day_highs, self.day_highs_date = {}, today
        new = [s for s in symbols if s not in self.day_highs]
        for i in range(0, len(new), 8):
            batch = new[i:i + 8]
            highs = await asyncio.gather(
                *(day_high_since_open(self.data, s) for s in batch),
                return_exceptions=True)
            for sym, h in zip(batch, highs):
                self.day_highs[sym] = h if isinstance(h, float) else 0.0
        if new:
            log.info("day highs from today's bars: %d name(s) seeded, e.g. %s",
                     len(new), ", ".join("%s %.4f" % (s, self.day_highs[s])
                                         for s in new[:5]))

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
            if hasattr(strat, "restore_today"):
                try:
                    await strat.restore_today()
                except Exception as e:
                    log.error("[%s] restore from today's orders: %s", strat.name, e)
            if HISTORY_DUMP:
                self.history_tasks.append(asyncio.create_task(
                    self.history(strat, *HISTORY_DUMP)))
        if TICK_DUMP:                           # read-only, once, in the background
            self.history_tasks.append(asyncio.create_task(
                self.data.dump_ticks(TICK_DUMP_DAY, TICK_DUMP)))
        if SEC_DUMP_DAYS:                       # read-only, once, in the background
            self.history_tasks.append(asyncio.create_task(self.sec_dump()))
        if NEWS_DUMP_DAYS and datetime.now(ET).date().isoformat() in NEWS_DUMP_ON:
            self.history_tasks.append(asyncio.create_task(self.news_dump()))

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
                 self.news_loop(),
                 self.data.subscribe_loop(), self.data.run_forever()]
        for strat in self.strategies:
            tasks.append(strat.tick_worker())
            tasks.append(strat.dlog.flusher())
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(Engine().run())
