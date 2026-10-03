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
  V33_API_KEY    / V33_SECRET_KEY      v33's account (optional - omit to skip)
  ALPACA_PAPER   "1"/"true" for paper (default), "0"/"false" for live
  ALPACA_FEED    "sip" (default) or "iex"
  ORPHAN_MODE    "adopt" (default) or "flatten" - leave unset
"""

import asyncio
import logging
import os
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockSnapshotRequest
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
VERSION = "v31-r26"

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

    async def account(self):
        return await asyncio.to_thread(self.client.get_account)

    async def day_baseline(self, fallback: float = 0.0) -> float:
        """The equity the day's -10% halt is measured against.

        account.last_equity is the account's equity at the previous session's
        close, so it does not move when this process restarts. Reading the day
        baseline from it is the whole fix: a restart at noon can no longer tell
        the bot that a 17% loss never happened.
        """
        if DAY_BASELINE == "boot":
            return await self.equity(fallback)
        try:
            acct = await self.account()
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

    async def send(self, symbol: str, qty: int, side, limit: float) -> int:
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
        try:
            for _ in range(10):
                await asyncio.sleep(0.2)
                o = await asyncio.to_thread(self.client.get_order_by_id, order.id)
                filled = int(float(o.filled_qty or 0))
                if filled >= qty or str(o.status) in ("OrderStatus.FILLED",
                                                      "OrderStatus.CANCELED"):
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
        return filled

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
        self.subscribed: set[str] = set()
        self.pending: set[str] = set()
        self.last_sub_at = 0.0
        self.trade_sinks = []                  # callables(symbol, price, size)
        self.bar_sinks = []                    # callables(bar)

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
        for sink in self.trade_sinks:
            sink(trade.symbol, float(trade.price), float(trade.size), conds)

    async def _on_bar(self, bar):
        for sink in self.bar_sinks:
            sink(bar)

    async def snapshots(self, symbols):
        return await asyncio.to_thread(
            self.hist.get_stock_snapshot,
            StockSnapshotRequest(symbol_or_symbols=symbols))

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
    first_entry: float = 0.0         # v32: today's original entry, fixed
    first_stop: float = 0.0          # v32: today's original stop, fixed
    last_exit: float = 0.0           # v33: the level that threw us out
    skipped_prints: int = 0          # odd lots etc. we refused to act on
    adopted: bool = False
    traded_today: bool = False
    last_tick_at: float = 0.0               # when this name last printed a trade
    recent: deque = field(default_factory=deque)   # v31: (time, price) prints
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
        cap = {"v31": V31_LEADER_CAP, "v34": V34_MAX_POSITION_PCT}.get(
            self.name, MAX_POSITION_PCT)
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

    def offer_tick(self, symbol, price, size, conds=()):
        """Called from the shared stream. NEVER blocks - just queues."""
        try:
            self.queue.put_nowait((symbol, price, size, conds))
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()        # drop the oldest, keep the newest
                self.queue.put_nowait((symbol, price, size, conds))
            except Exception:
                pass
            self.dropped_ticks += 1

    def offer_bar(self, bar):
        """Bars are cheap and rare - handled inline."""
        pass

    async def tick_worker(self):
        """Each strategy drains its OWN queue in its OWN task.

        This is what keeps them independent: if this strategy is sitting in an
        order chase, its queue backs up and nobody else's does.
        """
        while True:
            symbol, price, size, conds = await self.queue.get()
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
        if self.halt_threshold() <= 0:
            log.info("[%s] new day %s, baseline equity %.2f (source %s), "
                     "now %.2f (%+.1f%% on the day), DAILY HALT OFF",
                     self.name, today, self.day_start_equity, DAY_BASELINE,
                     now_eq, gap)
        else:
            log.info("[%s] new day %s, baseline equity %.2f (source %s), "
                     "now %.2f (%+.1f%% on the day), halt at -%.1f%% = %.2f",
                     self.name, today, self.day_start_equity, DAY_BASELINE,
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

    # ---- execution ----------------------------------------------------------

    async def buy(self, symbol: str, shares: int, ref: float) -> int:
        """Fills counted from the BROKER, never from the order reply.

        A cancel racing a fill used to report "got nothing" and the next attempt
        bought the whole clip again - a $600 slot became $3,050 that way.
        """
        start = await self.broker.qty(symbol)
        if start is None:
            # Without a starting count no fill can be measured, and guessing 0
            # double-counts anything already held. Do not buy blind.
            log.error("[%s] cannot read %s position - not buying", self.name,
                      symbol)
            return 0
        last = start
        for _ in range(CHASE_ATTEMPTS):
            now = await self.broker.qty(symbol)
            if now is None:
                # UNKNOWN IS NOT ZERO. Reading a failed count as "nothing
                # filled" re-sent the whole order on top of a partial fill.
                await asyncio.sleep(CHASE_PAUSE)
                continue
            last = now
            remaining = int(shares - (now - start))
            if remaining <= 0:
                break
            ask = await self.data.quote(symbol, "ask") or ref
            limit = round(min(ask * 1.002, ref * (1 + BUY_CHASE_CAP)), 2)
            got = await self.broker.send(symbol, remaining, OrderSide.BUY, limit)
            if got == -2:
                await self.broker.cancel_open(symbol)
                continue
            if got < 0:
                break
            if got == 0:
                await asyncio.sleep(CHASE_PAUSE)
        await self.broker.cancel_open(symbol)     # nothing of ours left working
        end = await self.broker.qty(symbol)
        if end is None:
            end = last
        return max(0, int(end - start))

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
        sold = await self.sell(s.symbol, shares, s.last_price)
        self.dlog.record(ev="EXIT", sym=s.symbol, why=why, px=s.last_price,
                         sh=sold, entry=s.entry, peak=s.peak, stop=s.stop)
        pl = (s.last_price - s.entry) * sold if s.entry else 0.0
        self.closed_today.append((s.symbol, s.entry, s.last_price, sold, pl, why))
        # The level that threw us out. v33 re-enters just above it, so the
        # ladder climbs with the stock instead of waiting for a new day high.
        s.last_exit = s.last_price
        held = (time.time() - s.entry_at) if s.entry_at else 0.0
        eq = await self.broker.equity(self.day_start_equity)
        log.info("[%s] %s %s %s %d @ %.4f | entry %.4f peak %.4f stop %.4f | "
                 "held %.0fs | P/L %+.2f (%+.2f%% of the trade, %+.2f%% of the "
                 "account)",
                 self.name, "EXIT" if s.shares - sold <= 0 else "TRIM", why,
                 s.symbol, sold, s.last_price, s.entry, s.peak,
                 s.stop, held, pl,
                 100 * (s.last_price - s.entry) / s.entry if s.entry else 0.0,
                 100 * pl / eq if eq else 0.0)
        s.shares = max(0.0, s.shares - sold)
        if s.shares <= 0:
            self.clear(s)

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

    # ---- bars ---------------------------------------------------------------

    def offer_bar(self, raw):
        s = self.st(raw.symbol)
        bar = Bar(ts=raw.timestamp, o=raw.open, h=raw.high,
                  l=raw.low, c=raw.close, v=raw.volume)
        s.bars.append(bar)
        if len(s.bars) > 400:
            s.bars = s.bars[-400:]
        s.day_high = max(s.day_high, bar.h)
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
        return price <= high * (1 - self.crash_pct(s, high))

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
            if fast is not None and base > 0 and len(s.bars) >= 5 and fast < 0 and s.quiet_bars >= 2:
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
        if not (PRICE_MIN <= price <= PRICE_MAX):
            return
        if len(self.open_positions()) >= V31_MAX_POSITIONS:
            return
        if not s.setup_ready or price < s.setup_level:
            return
        if not self.thin_ok(s):
            return
        if fast is None or fast <= 0:
            return
        if s.traded_today and price < s.day_high + margin_for(price):
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
            await self._maybe_enter_inner(s, price, fast, base)

    async def _maybe_enter_inner(self, s, price, fast, base):
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
        worst = price * (1 + BUY_CHASE_CAP)
        risk_per_share = max(worst - s.setup_low, MIN_STOP_PCT * worst, 0.01)
        eq = await self.broker.equity(self.day_start_equity)
        shares = int((eq * V31_RISK_PER_TRADE) / risk_per_share)

        # Hard ceiling on the starter, whatever the risk maths says. Speed
        # weights may grow a winner beyond this later; a fresh entry never
        # starts there.
        held_all = sum(x.shares * (x.last_price or price)
                       for x in self.open_positions())
        room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
        cap = int(min(eq * MAX_POSITION_PCT, room) / worst)
        if shares > cap:
            log.info("[v31] %s sized down %d -> %d shares (25%% cap)",
                     s.symbol, shares, cap)
            shares = cap
        if shares * price < MIN_TRADE_DOLLARS:
            return

        # THE BREAKOUT HAS TO BE BACKED BY THE MARKET, NOT BY ONE PRINT.
        if CONFIRM_ENTRY_WITH_QUOTE:
            ask = await self.data.quote(s.symbol, "ask")
            if ask is not None and ask < s.setup_level:
                log.info("[v31] %s TRIGGER NOT CONFIRMED - print %.4f%s reached "
                         "%.4f but the ask is %.4f, below the trigger. "
                         "No order sent.",
                         s.symbol, price,
                         (" cond %s" % (list(s.last_conds),)) if s.last_conds
                         else "",
                         s.setup_level, ask)
                return
            if ask is None:
                log.warning("[v31] %s no quote available - entering on the "
                            "print alone", s.symbol)

        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares = filled
            # THE ENTRY IS WHAT THE ACCOUNT PAID, not the print that triggered
            # it. P/L, the stop floor and the trail all measure from here.
            s.entry = await self.broker.avg_entry(s.symbol) or price
            # THE STOP OBEYS THE SAME FLOOR THE SIZING USES. The red bar's low
            # can sit a single cent under the trigger, and a one-cent stop is
            # not a stop - it is a coin toss paid for with the spread. Size and
            # stop must be computed from the SAME risk-per-share or the trade
            # is sized for a 1% loss and exited on a 0.1% wiggle.
            floor_stop = s.entry * (1 - MIN_STOP_PCT)
            s.stop = min(s.setup_low, floor_stop)
            s.peak = max(price, s.entry)
            s.trail_stop = 0.0
            s.armed = False
            s.adopted = False
            s.traded_today = True
            self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                             level=s.setup_level, stop=s.stop,
                             setup_low=s.setup_low, speed=fast, baseline=base)
            s.entry_at = time.time()
            log.info("[v31] ENTER %s %d @ %.4f (print %.4f) = $%.0f (%.0f%% of "
                     "equity) | stop %.4f (%.2f%% away) | trigger %.4f",
                     s.symbol, filled, s.entry, price, filled * s.entry,
                     100 * filled * s.entry / eq if eq else 0.0,
                     s.stop, 100 * (s.entry - s.stop) / s.entry if s.entry else 0.0,
                     s.setup_level)
            # THE TWO BARS THE SETUP WAS BUILT FROM, printed in full. Without
            # these the question "did it enter on the red candle?" can only be
            # argued from a chart, and it has been argued all day. bars[-1] is
            # the last CLOSED bar (the red one), bars[-2] the one before it.
            # The bar we are buying inside has not closed and has no colour yet.
            try:
                g, r = s.bars[-2], s.bars[-1]
                log.info("[v31]   setup %s  green? %-5s  %s  O %.4f H %.4f "
                         "L %.4f C %.4f  V %.0f",
                         s.symbol, g.green, g.ts.astimezone(ET).strftime("%H:%M:%S"),
                         g.o, g.h, g.l, g.c, g.v)
                log.info("[v31]   setup %s  red?   %-5s  %s  O %.4f H %.4f "
                         "L %.4f C %.4f  V %.0f  -> trigger %.4f = O + %.2f",
                         s.symbol, r.red, r.ts.astimezone(ET).strftime("%H:%M:%S"),
                         r.o, r.h, r.l, r.c, r.v, s.setup_level, V31_ENTRY_TICK)
                log.info("[v31]   buying inside the bar that opened after %s "
                         "- its colour is not knowable yet",
                         r.ts.astimezone(ET).strftime("%H:%M:%S"))
                log.info("[v31]   triggering print %.4f x %.0f  cond %s",
                         price, s.last_size, list(s.last_conds) or "-")
            except Exception as e:
                log.error("[v31]   could not print setup bars for %s: %s",
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
        Does nothing while V31_REBALANCE is False."""
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

class V32(Strategy):
    """Buy every scanner name on its first tick. Cut it at the entry, plus a
    penny. Re-enter only on a NEW day high plus the margin."""

    name = "v32"

    async def evaluate(self, s, price):
        if await self.halted():
            # Halted means stop OPENING, never stop CLOSING. Leaving a position
            # stranded because the account tripped its own limit is the worst
            # possible reading of a risk rule.
            if s.in_position:
                await self.exit(s, "halted")
            return
        if s.in_position:
            if price <= s.stop:
                await self.exit(s, "stop")
            return
        if not entries_allowed():
            return
        if s.symbol not in self.qualified:
            return
        if len(self.open_positions()) >= SIMPLE_MAX_NAMES:
            return
        # ONE LEVEL, ALL DAY. The first entry is unconditional - the scanner
        # said the name qualifies, so buy it. After that the level never moves:
        # thrown out at the entry, bought back when it climbs 2c above the SAME
        # original entry, however high the stock went in between.
        # s.first_entry is 0 when this process never opened the position - after
        # a restart, or when reconciliation adopted it. Without the `and
        # s.first_entry` the test becomes "price < 0.02", which always passes,
        # and the fill below then takes s.first_stop = 0.0: a position with NO
        # STOP AT ALL. Seen live 2026-09-30 6:43pm ET on TNON and LPA.
        if s.traded_today and s.first_entry and \
                price < s.first_entry + SIMPLE_REENTRY_TICK:
            return
        shares = int(self.slot / price)
        if shares <= 0:
            return
        # No remembered level means this is a FIRST entry however the state got
        # here, so the stop comes from the bid and the day's level is set now.
        first = (not s.traded_today) or not s.first_entry or not s.first_stop
        ref = await self.stop_reference(s.symbol, price) if first else s.first_entry
        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares = filled
            s.entry = price
            s.peak = price
            if first:
                s.first_entry = price
                s.first_stop = simple_stop(ref)
            s.stop = sane_stop(s.first_stop, price)
            s.entry_at = time.time()
            s.traded_today = True
            s.adopted = False
            self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                             stop=s.stop, first=first)
            log.info("[v32] %s %s %d @ %.4f = $%.0f | stop %.4f (%.2f%% away) "
                     "| day level %.4f, re-entry at %.4f",
                     "ENTER" if first else "RE-ENTER",
                     s.symbol, filled, price, filled * price, s.stop,
                     100 * (price - s.stop) / price if price else 0.0,
                     s.first_entry, s.first_entry + SIMPLE_REENTRY_TICK)


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

V34_MAX_POSITIONS = 1
V34_STARTER_PCT = 0.10
V34_ADD_MIN_AGE_SEC = 90
V34_ADD_CONFIRM_MARGIN = 0.02
V34_ADD_MULT = 2.0
V34_MAX_POSITION_PCT = 0.40
V34_TRAIL_LOOSE_PCT = 0.15
V34_TRAIL_MED_PCT = 0.08
V34_TRAIL_TIGHT_PCT = 0.03
V34_FLUSH_DROP_PCT = 0.04
V34_ENTRY_WINDOW = ((4, 0), (20, 0))


class V34(Strategy):
    """One position at a time, picked by rank, sized in stages, protected in
    stages. Built 2026-10-02 from everything learned the two days before it:
    unselective entry loses, one big jump in size is dangerous, one stop width
    is wrong for every stage of a move, and a fresh position needs an instant,
    history-free floor under it from its very first tick.
    """

    name = "v34"

    def offer_bar(self, raw):
        s = self.st(raw.symbol)
        bar = Bar(ts=raw.timestamp, o=raw.open, h=raw.high,
                  l=raw.low, c=raw.close, v=raw.volume)
        s.bars.append(bar)
        if len(s.bars) > 400:
            s.bars = s.bars[-400:]
        s.day_high = max(s.day_high, bar.h)
        self._refresh_setup(s)

    def note_trade(self, s, price, size):
        s.trades.append((price, size))

    def _refresh_setup(self, s):
        s.setup_ready = False
        if len(s.bars) < 2:
            return
        green, red = s.bars[-2], s.bars[-1]
        if green.green and red.red:
            s.setup_level = red.o + V31_ENTRY_TICK
            s.setup_low = red.l
            s.setup_ready = True

    def _speed(self, s):
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

    def _dollar_volume_recent(self, s, n=50):
        if len(s.trades) < 1:
            return 0.0
        recent = list(s.trades)[-n:]
        return sum(p * sz for p, sz in recent)

    def _rank(self, sym):
        s = self.st(sym)
        sp = self._speed(s)
        if sp is None or sp <= 0:
            return 0.0
        return self._dollar_volume_recent(s) * sp

    def _best_candidate(self):
        best_sym, best_score = None, 0.0
        for sym in self.qualified:
            s = self.st(sym)
            if s.in_position or not s.setup_ready:
                continue
            score = self._rank(sym)
            if score > best_score:
                best_sym, best_score = sym, score
        return best_sym

    def _entries_allowed(self):
        now = datetime.now(ET)
        start, end = V34_ENTRY_WINDOW
        return start <= (now.hour, now.minute) < end

    async def evaluate(self, s, price):
        if await self.halted():
            if s.in_position:
                await self.exit(s, "halted")
            return

        if s.in_position:
            s.peak = max(s.peak, price)
            if s.peak > 0 and price <= s.peak * (1 - V34_FLUSH_DROP_PCT):
                await self.exit(s, "flush")
                return
            if not s.armed and s.stop and price <= s.stop:
                await self.exit(s, "entry-stop")
                return
            gain = (s.peak / s.entry - 1) if s.entry else 0.0
            if gain >= 1.0:
                trail_pct = V34_TRAIL_TIGHT_PCT
            elif gain >= 0.25:
                trail_pct = V34_TRAIL_MED_PCT
            else:
                trail_pct = V34_TRAIL_LOOSE_PCT
            if gain >= 0.25:
                s.armed = True
                s.trail_stop = max(s.trail_stop, s.peak * (1 - trail_pct))
                if price <= s.trail_stop:
                    await self.exit(s, "trail")
                    return
            if (s.entry_at and time.time() - s.entry_at >= V34_ADD_MIN_AGE_SEC
                    and price >= s.setup_level * (1 + V34_ADD_CONFIRM_MARGIN)):
                await self._add(s, price)
            return

        if not self._entries_allowed():
            return
        if s.symbol not in self.qualified:
            return
        if len(self.open_positions()) >= V34_MAX_POSITIONS:
            return
        if not s.setup_ready or price < s.setup_level:
            return
        if self._best_candidate() != s.symbol:
            return

        eq = await self.broker.equity(self.day_start_equity)
        shares = int((eq * V34_STARTER_PCT) / price)
        if shares * price < MIN_TRADE_DOLLARS:
            return
        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares = filled
            s.entry = price
            s.stop = s.setup_low
            s.peak = price
            s.trail_stop = 0.0
            s.armed = False
            s.adopted = False
            s.traded_today = True
            s.entry_at = time.time()
            self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                             level=s.setup_level, stop=s.setup_low)
            log.info("[v34] ENTER %s %d @ %.4f = $%.0f (%.0f%% of equity) | "
                     "stop %.4f | rank earned it",
                     s.symbol, filled, price, filled * price,
                     100 * filled * price / eq if eq else 0.0, s.stop)

    async def _add(self, s, price):
        async with self.lock(s.symbol):
            if s.in_position:
                await self._add_locked(s, price)

    async def _add_locked(self, s, price):
        eq = await self.broker.equity(self.day_start_equity)
        current_pct = (s.shares * price) / eq if eq else 0.0
        if current_pct >= V34_MAX_POSITION_PCT:
            return
        target_pct = min(current_pct * V34_ADD_MULT, V34_MAX_POSITION_PCT)
        gap = target_pct * eq - s.shares * price
        if gap < MIN_TRADE_DOLLARS:
            return
        shares = int(gap / price)
        if shares <= 0:
            return
        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares += filled
            s.entry_at = time.time()
            self.dlog.record(ev="ADD", sym=s.symbol, px=price, sh=filled)
            log.info("[v34] ADD %s %d @ %.4f -> now %.0f%% of equity",
                     s.symbol, filled, price,
                     100 * s.shares * price / eq if eq else 0.0)

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

        for strat in self.strategies:
            self.data.trade_sinks.append(strat.offer_tick)
            self.data.bar_sinks.append(strat.offer_bar)

        self.last_auth_warn = 0.0
        self.last_probe = 0.0

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
