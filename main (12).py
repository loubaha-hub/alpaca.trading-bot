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
MAX_POSITION_PCT = 0.25                     # a starter is never >25% of equity
MIN_STOP_PCT = 0.01                         # a stop nearer than 1% counts as 1%
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
V31_LEADER_CAP = 0.80
V31_RISK_PER_TRADE = 0.01
V31_ENTRY_TICK = 0.01
V31_TRADE_WINDOW = 50
V31_SPEED_ADD_MULT = 5.0
V31_SPEED_FADE_MULT = 0.25
V31_SPEED_FLUSH_MULT = 5.0
V31_BASELINE_MIN_SAMPLES = 10
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
V31_SPEED_EVENT_MULT = 2.0
V31_ORPHAN_STOP_PCT = 0.08

# --- v32 and v33 -------------------------------------------------------------
SIMPLE_MAX_NAMES = 50
SIMPLE_START_CAPITAL = 30_000.0
SIMPLE_SLOT = SIMPLE_START_CAPITAL / SIMPLE_MAX_NAMES     # $600 per name
SIMPLE_STOP_CENTS = 0.01
SIMPLE_STOP_PCT = 0.001

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("engine")


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

    async def send(self, symbol: str, qty: int, side, limit: float) -> int:
        """Returns filled shares, 0 on no fill, -1 when the broker refuses."""
        try:
            order = await asyncio.to_thread(
                self.client.submit_order,
                LimitOrderRequest(symbol=symbol, qty=qty, side=side,
                                  time_in_force=TimeInForce.DAY,
                                  limit_price=limit, extended_hours=True))
            for _ in range(10):
                await asyncio.sleep(0.2)
                o = await asyncio.to_thread(self.client.get_order_by_id, order.id)
                if o.filled_qty and float(o.filled_qty) > 0:
                    return int(float(o.filled_qty))
                if str(o.status) in ("OrderStatus.FILLED", "OrderStatus.CANCELED"):
                    break
            try:
                await asyncio.to_thread(self.client.cancel_order_by_id, order.id)
            except Exception:
                pass
            return 0
        except Exception as e:
            return self.classify(e, side, symbol)

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
            return -1                          # we hold less than we asked
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
        self.pending.clear()
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
        for sink in self.trade_sinks:
            sink(trade.symbol, float(trade.price), float(trade.size))

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
    adopted: bool = False
    traded_today: bool = False
    last_tick_at: float = 0.0               # when this name last printed a trade

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
        self.stopped = False
        self.needs_reconcile = True
        self.dropped_ticks = 0

    # ---- plumbing -----------------------------------------------------------

    def st(self, symbol: str) -> SymState:
        if symbol not in self.state:
            self.state[symbol] = SymState(symbol=symbol)
        return self.state[symbol]

    def open_positions(self):
        return [s for s in self.state.values() if s.in_position]

    def halt_threshold(self) -> float:
        return HALT_LADDER[min(self.halt_streak, len(HALT_LADDER) - 1)]

    def offer_tick(self, symbol, price, size):
        """Called from the shared stream. NEVER blocks - just queues."""
        try:
            self.queue.put_nowait((symbol, price, size))
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()        # drop the oldest, keep the newest
                self.queue.put_nowait((symbol, price, size))
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
            symbol, price, size = await self.queue.get()
            try:
                s = self.st(symbol)
                s.last_price = price
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
        self.day_start_equity = await self.broker.equity(self.day_start_equity)
        self.state.clear()
        self.qualified.clear()
        self.needs_reconcile = True
        log.info("[%s] new day %s, baseline equity %.2f, halt at -%.1f%%",
                 self.name, today, self.day_start_equity,
                 100 * self.halt_threshold())

    # ---- reconciliation -----------------------------------------------------

    async def reconcile(self, why: str = "startup"):
        """The broker is the truth. Memory is a cache every restart wipes."""
        held = await self.broker.positions()
        if held is None:
            return                              # unreachable - change nothing

        adopted, dropped, corrected, flattened = [], [], [], []

        for sym, info in held.items():
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
            start = 0.0
        for _ in range(CHASE_ATTEMPTS):
            now = await self.broker.qty(symbol)
            filled = (now - start) if now is not None else 0.0
            remaining = int(shares - filled)
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
        end = await self.broker.qty(symbol)
        if end is None:
            return 0
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
            now = await self.broker.qty(symbol)
            sold = (start - now) if now is not None else 0.0
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
        return max(0, int(start - end))

    async def exit(self, s: SymState, why: str):
        if s.shares <= 0:
            return
        sold = await self.sell(s.symbol, int(s.shares), s.last_price)
        self.dlog.record(ev="EXIT", sym=s.symbol, why=why, px=s.last_price,
                         sh=sold, entry=s.entry, peak=s.peak, stop=s.stop)
        log.info("[%s] EXIT %s %s %d @ %.4f (entry %.4f peak %.4f)",
                 self.name, why, s.symbol, sold, s.last_price, s.entry, s.peak)
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

            # 2. flush - large NEGATIVE speed. Never consults the trail.
            if fast is not None and base > 0 and fast <= -V31_SPEED_FLUSH_MULT * base:
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
            if fast is not None and base > 0 and fast < 0 and s.quiet_bars >= 2:
                await self.exit(s, "fade")
                return
            # 7. add on strong speed
            if fast is not None and base > 0 and fast >= V31_SPEED_ADD_MULT * base:
                await self.add(s, price)
            return

        await self.maybe_enter(s, price, fast, base)

    async def maybe_enter(self, s, price, fast, base):
        if s.symbol not in self.qualified:
            return
        if len(self.open_positions()) >= V31_MAX_POSITIONS:
            return
        if not s.setup_ready or price < s.setup_level:
            return
        if not self.thin_ok(s):
            return
        if fast is None or fast <= 0:
            return
        if base > 0 and fast < V31_SPEED_ADD_MULT * base:
            return
        if s.traded_today and price < s.day_high + margin_for(price):
            return

        # A stop nearer than MIN_STOP_PCT is treated as MIN_STOP_PCT. Without
        # that floor a 4-cent stop divides into the risk budget and asks for
        # thousands of shares - which is exactly how a $29k account ended up
        # holding $43k of one stock.
        risk_per_share = max(price - s.setup_low, MIN_STOP_PCT * price, 0.01)
        eq = await self.broker.equity(self.day_start_equity)
        shares = int((eq * V31_RISK_PER_TRADE) / risk_per_share)

        # Hard ceiling on the starter, whatever the risk maths says. Speed
        # weights may grow a winner beyond this later; a fresh entry never
        # starts there.
        held_all = sum(x.shares * (x.last_price or price)
                       for x in self.open_positions())
        room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)
        cap = int(min(eq * MAX_POSITION_PCT, room) / price)
        if shares > cap:
            log.info("[v31] %s sized down %d -> %d shares (25%% cap)",
                     s.symbol, shares, cap)
            shares = cap
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
            self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                             level=s.setup_level, stop=s.setup_low,
                             speed=fast, baseline=base)
            log.info("[v31] ENTER %s %d @ %.4f stop %.4f",
                     s.symbol, filled, price, s.setup_low)

    async def add(self, s, price):
        """Adding is bounded by the same walls as entering.

        Two ceilings, both learned the hard way on 2026-09-30:
          * no single name above LEADER_CAP of equity
          * the whole book never above MAX_EXPOSURE_PCT of equity - i.e. never
            on borrowed money, whatever buying power the broker offers
        """
        eq = await self.broker.equity(self.day_start_equity)
        target = min(await self.target_dollars(s.symbol), eq * V31_LEADER_CAP)

        held_all = sum(x.shares * (x.last_price or price)
                       for x in self.open_positions())
        room = max(0.0, eq * MAX_EXPOSURE_PCT - held_all)

        gap = min(target - s.shares * price, room)
        if gap < MIN_TRADE_DOLLARS:
            return
        shares = int(gap / price)
        if shares <= 0:
            return
        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares += filled
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
        """The 5-minute rebalance clock, plus off-clock speed events."""
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
            target = await self.target_dollars(s.symbol)
            diff = target - s.shares * price
            if abs(diff) < MIN_TRADE_DOLLARS:
                continue
            if diff > 0:
                await self.add(s, price)
            else:
                shares = min(int(s.shares), int(abs(diff) / price))
                if shares > 0:
                    sold = await self.sell(s.symbol, shares, price)
                    s.shares = max(0.0, s.shares - sold)
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
        if s.symbol not in self.qualified:
            return
        if len(self.open_positions()) >= SIMPLE_MAX_NAMES:
            return
        if s.traded_today and price < s.day_high + margin_for(price):
            return
        shares = int(SIMPLE_SLOT / price)
        if shares <= 0:
            return
        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares = filled
            s.entry = price
            s.peak = price
            s.stop = simple_stop(price)
            s.traded_today = True
            s.adopted = False
            self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                             stop=s.stop)
            log.info("[v32] ENTER %s %d @ %.4f stop %.4f",
                     s.symbol, filled, price, s.stop)


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
        if s.symbol not in self.qualified:
            return
        if len(self.open_positions()) >= SIMPLE_MAX_NAMES:
            return
        if price < s.day_high + margin_for(price):
            return
        shares = int(SIMPLE_SLOT / price)
        if shares <= 0:
            return
        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares = filled
            s.entry = price
            s.peak = price
            s.stop = simple_stop(price)
            s.traded_today = True
            s.adopted = False
            self.dlog.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                             stop=s.stop)
            log.info("[v33] ENTER %s %d @ %.4f stop %.4f",
                     s.symbol, filled, price, s.stop)


# ----------------------------------------------------------------------------
# THE ENGINE - one scan, one connection, three strategies
# ----------------------------------------------------------------------------

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
        self.add_strategy(V33, os.environ.get("V33_API_KEY"),
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
                parts.append("%s q=%d pos=%d drop=%d"
                             % (s.name, s.queue.qsize(),
                                len(s.open_positions()), s.dropped_ticks))
            log.info("health | watching %d (+%d queued) | %s",
                     len(self.data.subscribed), len(self.data.pending),
                     " | ".join(parts))

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

        log.info("engine up: %s | one data connection | orphan mode %s",
                 ", ".join(s.name for s in self.strategies), ORPHAN_MODE)

        tasks = [self.scanner_loop(), self.reconcile_loop(), self.periodic_loop(),
                 self.close_loop(), self.dead_loop(), self.risk_loop(),
                 self.health_loop(),
                 self.data.subscribe_loop(), self.data.run_forever()]
        for strat in self.strategies:
            tasks.append(strat.tick_worker())
            tasks.append(strat.dlog.flusher())
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(Engine().run())
