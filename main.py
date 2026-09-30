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
  Three strategies share one event loop. A blocking call inside one would freeze
  the other two's tick handling. So:
    * every broker/data call runs off the loop via asyncio.to_thread
    * every stream subscribe call does too - see flush_subscriptions
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

A strategy with no keys logs a warning and does not run. Nothing else changes.
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
from alpaca.trading.requests import GetAssetsRequest, LimitOrderRequest
from alpaca.trading.enums import AssetStatus, OrderSide, TimeInForce
from alpaca.data.enums import DataFeed

# ----------------------------------------------------------------------------
# SHARED CONFIGURATION
# ----------------------------------------------------------------------------

ET = ZoneInfo("America/New_York")           # the ONE clock. Never local time.

SESSION = ((4, 0), (20, 0))                 # the session WE trade, ET
FLATTEN_AT = (15, 58)                       # flatten everything at 15:58 ET

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

# --- reconciliation (shared) -------------------------------------------------
ORPHAN_MODE = os.environ.get("ORPHAN_MODE", "adopt").strip().lower()
ORPHAN_FLATTEN_WINDOW = ((4, 0), (4, 10))
RECONCILE_SECONDS = 60
EQUITY_TTL = 5

# --- tick fan-out ------------------------------------------------------------
QUEUE_MAX = 20000                           # per strategy; drops oldest if full

# --- subscription batching ---------------------------------------------------
# New names are collected and sent in ONE batch, at most this often, rather than
# one call per symbol. A position we hold jumps the queue.
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
            msg = str(e).lower()
            log.error("[%s] order failed %s %s: %s", self.label, side, symbol, e)
            if "not allowed to short" in msg or "40310000" in msg:
                return -1                      # we do not own it - stop trying
            return 0


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
        """One connection for the whole process. Never opened twice.

        The SDK does its own reconnecting for connection errors and data
        staleness - on thin premarket names a quiet stretch can trip that, and
        the retry briefly collides with its own not-yet-released socket. That is
        self-healing and expected. This wrapper only catches the case where the
        SDK gives up entirely.
        """
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
        start = awaitself.broker.qty(symbol)
