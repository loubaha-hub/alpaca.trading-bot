"""
v31 - Runner strategy for Alpaca.

Design rules (see the v31 Rulebook):
  * Closed bars set the levels. Ticks fire the actions. An in-progress bar is
    NEVER treated as closed - that bug made the old build enter one bar early,
    inside the red candle.
  * Speed = (dP/P) x volume multiplier. Sign = direction, magnitude = urgency.
  * Trail = 3 x ABR (median true range of the last 10 closed bars), armed only
    after the trade is up 1.5 x ABR%. Until then the red bar's low is the stop.
  * Capital is split in proportion to speed, leader capped at 80%.
  * Exits run on a strict precedence ladder - one exit path per position.
  * The BROKER is the only truth about what we hold. Memory is a cache.

Environment variables required:
  ALPACA_API_KEY, ALPACA_SECRET_KEY
  ALPACA_PAPER   "1" for paper (default), "0" for live
  ALPACA_FEED    "sip" (recommended) or "iex"
  ORPHAN_MODE    "adopt" (default) or "flatten" - leave it unset
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
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest, LimitOrderRequest
from alpaca.trading.enums import AssetStatus, OrderSide, TimeInForce
from alpaca.data.enums import DataFeed

# ----------------------------------------------------------------------------
# CONFIGURATION - every tunable lives here
# ----------------------------------------------------------------------------

ET = ZoneInfo("America/New_York")          # the ONE clock. Never use local time.

# --- scanner -----------------------------------------------------------------
PRICE_MIN = 1.00
PRICE_MAX = 20.00
FLOAT_MIN = 1_000_000                       # only applied when float is known
FLOAT_MAX = 20_000_000
GAIN_FROM_OPEN = 0.10                       # up 10% from today's first trade
REQUIRE_VOLUME_GE_RDV = True                # volume >= one normal day's volume
HTB_BOOST = 1.25                            # hard-to-borrow ranking multiplier

# --- thin-stock filter (three closed bars) -----------------------------------
BAR_SHARES_MIN = 30_000                     # each of the last three bars
THREE_BAR_SHARES_MIN = 100_000              # the three together

# --- entry -------------------------------------------------------------------
ENTRY_TICK = 0.01                           # cross above red bar's OPEN + 1 cent

# --- speed -------------------------------------------------------------------
TRADE_WINDOW = 50                           # trades per window on the fast clock
SPEED_ADD_MULT = 5.0                        # add when speed >= 5x baseline
SPEED_FADE_MULT = 0.25                      # fading when speed < 0.25x baseline
SPEED_FLUSH_MULT = 5.0                      # flush when speed <= -5x baseline
BASELINE_MIN_SAMPLES = 10

# --- ABR and the trail -------------------------------------------------------
ABR_BARS = 10
ABR_MIN_BARS = 3                            # no trail until we have 3 bars
ABR_GROWTH_CAP = 1.5                        # vs its own value 10 minutes ago
TRAIL_MULT = 3.0                            # trail = 3 x ABR
TRAIL_ARM_MULT = 1.5                        # arm when gain >= 1.5 x ABR
TRAIL_MIN_PCT = 0.02                        # never tighter than 2%
TRAIL_MAX_PCT = 0.25                        # never wider than 25%

# --- stall -------------------------------------------------------------------
STALL_BARS = 6                              # 6 quiet candles -> close it

# --- position management -----------------------------------------------------
MAX_POSITIONS = 3
LEADER_CAP = 0.80                           # top name never above 80%
RISK_PER_TRADE = 0.01                       # starter sized off the entry stop
REBALANCE_SECONDS = 300                     # 5-minute clock
SPEED_EVENT_MULT = 2.0                      # doubles/halves -> off-clock rebalance
DISPLACE_MULT = 2.0                         # newcomer needs 2x the weakest
MIN_TRADE_DOLLARS = 100                     # don't bother with crumbs

# --- risk --------------------------------------------------------------------
HALT_LADDER = [0.10, 0.05, 0.025]           # then a full stop
FLATTEN_AT = (15, 58)                       # flatten everything at 15:58 ET

# --- execution ---------------------------------------------------------------
BUY_CHASE_CAP = 0.02                        # buys capped 2% above the ask
CHASE_ATTEMPTS = 8
CHASE_PAUSE = 0.35

# --- reconciliation ----------------------------------------------------------
# The broker is the ONLY truth about what we hold. Memory is a cache that a
# restart wipes. Everything below exists so a restart, a crash, a redeploy or a
# leftover position from an older strategy can never make the bot trade blind.
ORPHAN_MODE = os.environ.get("ORPHAN_MODE", "adopt").strip().lower()
ORPHAN_FLATTEN_WINDOW = ((4, 0), (4, 10))    # flatten mode only bites here
SESSION = ((4, 0), (20, 0))                  # the session WE trade, ET
ORPHAN_STOP_PCT = 0.08          # adopted position: leash 8% under its own peak
RECONCILE_SECONDS = 60          # re-check the broker every minute
EQUITY_TTL = 5                  # seconds to cache the account equity

# --- loop --------------------------------------------------------------------
SCAN_SECONDS = 8

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("v31")


# ----------------------------------------------------------------------------
# DECISION LOG - written AFTER the order is away, never on the critical path
# ----------------------------------------------------------------------------

class DecisionLog:
    """In-memory buffer, flushed by a background task. Never blocks a decision."""

    def __init__(self, path="/tmp/v31_decisions.log", maxlen=20000):
        self.buf = deque(maxlen=maxlen)
        self.path = path

    def record(self, **fields):
        try:
            fields["t"] = datetime.now(ET).isoformat()
            self.buf.append(fields)
        except Exception:
            pass                                    # a lost log line is acceptable

    async def flusher(self):
        while True:
            await asyncio.sleep(2.0)
            try:
                if not self.buf:
                    continue
                lines = []
                while self.buf:
                    lines.append(repr(self.buf.popleft()))
                with open(self.path, "a") as fh:
                    fh.write("\n".join(lines) + "\n")
            except Exception:
                pass


DLOG = DecisionLog()


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
    bars: list = field(default_factory=list)            # CLOSED bars only
    trades: deque = field(default_factory=lambda: deque(maxlen=TRADE_WINDOW * 2 + 5))
    last_price: float = 0.0
    day_open: float = 0.0
    day_high: float = 0.0
    abr_history: deque = field(default_factory=lambda: deque(maxlen=600))
    speed_samples: list = field(default_factory=list)
    easy_to_borrow: bool = True
    quiet_bars: int = 0

    # position
    shares: float = 0.0
    entry: float = 0.0
    entry_stop: float = 0.0                              # the red bar's low
    peak: float = 0.0
    trail_stop: float = 0.0
    armed: bool = False
    adopted: bool = False        # taken over from the broker, not opened by us

    # pending setup
    setup_level: float = 0.0                             # red open + 1 cent
    setup_low: float = 0.0                               # red low
    setup_ready: bool = False

    @property
    def in_position(self) -> bool:
        return self.shares > 0

    # ---- bar maths ----------------------------------------------------------

    def add_bar(self, bar: Bar):
        self.bars.append(bar)
        if len(self.bars) > 400:
            self.bars = self.bars[-400:]
        if not self.day_open:
            self.day_open = bar.o
        self.day_high = max(self.day_high, bar.h)
        self.abr_history.append((bar.ts, self.abr_raw()))
        s = self.bar_speed()
        if s is not None and s > 0:
            self.speed_samples.append(s)
        self.refresh_setup()
        self.track_stall()

    def abr_raw(self) -> float:
        """Median TRUE RANGE of the last ABR_BARS closed bars."""
        if len(self.bars) < ABR_MIN_BARS:
            return 0.0
        window = self.bars[-ABR_BARS:]
        trs = []
        for i, b in enumerate(window):
            prev_close = window[i - 1].c if i > 0 else b.o
            tr = max(b.h, prev_close) - min(b.l, prev_close)
            trs.append(tr)
        return statistics.median(trs) if trs else 0.0

    def abr(self) -> float:
        """ABR, capped so one violent stretch cannot blow the leash open."""
        raw = self.abr_raw()
        if raw <= 0:
            return 0.0
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        older = [v for ts, v in self.abr_history if ts <= cutoff and v > 0]
        if older:
            return min(raw, ABR_GROWTH_CAP * older[-1])
        return raw

    def bar_speed(self):
        """Speed on the minute clock - used for ranking."""
        if len(self.bars) < 2:
            return None
        a, b = self.bars[-2], self.bars[-1]
        if a.c <= 0 or a.v <= 0:
            return None
        return ((b.c - a.c) / a.c) * (b.v / a.v)

    def fast_speed(self):
        """Speed on the trade clock - used for every action.

        Trade-count windows, not time windows: on a furious stock N trades span
        about a second, on a quiet one much longer. Self-adjusting, and the
        volume term can never divide by zero.
        """
        n = TRADE_WINDOW
        if len(self.trades) < 2 * n:
            return None
        recent = list(self.trades)[-n:]
        prior = list(self.trades)[-2 * n:-n]
        p0 = prior[0][0]
        p1 = recent[-1][0]
        v_recent = sum(t[1] for t in recent)
        v_prior = sum(t[1] for t in prior)
        if p0 <= 0 or v_prior <= 0:
            return None
        return ((p1 - p0) / p0) * (v_recent / v_prior)

    def baseline_speed(self) -> float:
        """The stock's own stationary speed - thresholds are multiples of this."""
        if len(self.speed_samples) < BASELINE_MIN_SAMPLES:
            return 0.0
        return statistics.median(self.speed_samples)

    # ---- the three-candle setup --------------------------------------------

    def refresh_setup(self):
        """Pattern is read from CLOSED bars only: green closes, then red closes."""
        self.setup_ready = False
        if len(self.bars) < 2:
            return
        green, red = self.bars[-2], self.bars[-1]
        if green.green and red.red:
            self.setup_level = red.o + ENTRY_TICK
            self.setup_low = red.l
            self.setup_ready = True

    def thin_ok(self) -> bool:
        if len(self.bars) < 3:
            return False
        last3 = self.bars[-3:]
        if any(b.v < BAR_SHARES_MIN for b in last3):
            return False
        return sum(b.v for b in last3) >= THREE_BAR_SHARES_MIN

    def track_stall(self):
        base = self.baseline_speed()
        s = self.bar_speed()
        if base <= 0 or s is None:
            return
        if abs(s) < SPEED_FADE_MULT * base:
            self.quiet_bars += 1
        else:
            self.quiet_bars = 0

    # ---- the trail ----------------------------------------------------------

    def update_trail(self, price: float):
        """Arm on progress, not on time. Then ratchet up, never down."""
        if not self.in_position:
            return
        self.peak = max(self.peak, price)

        # An adopted position has no red-bar low - we were not there when it was
        # opened. Give it a self-widening leash under its own peak until the real
        # ABR trail arms, so it is never left completely unprotected.
        if self.adopted and not self.armed:
            self.entry_stop = max(self.entry_stop,
                                  self.peak * (1 - ORPHAN_STOP_PCT))

        abr = self.abr()
        if abr <= 0:
            return
        if not self.armed and self.peak >= self.entry + TRAIL_ARM_MULT * abr:
            self.armed = True
        if not self.armed:
            return

        distance = TRAIL_MULT * abr
        distance = max(distance, TRAIL_MIN_PCT * self.peak)          # never tighter
        distance = min(distance, TRAIL_MAX_PCT * self.peak)          # never wider
        entry_risk = self.entry - self.entry_stop
        if entry_risk > 0:
            distance = max(distance, entry_risk)                     # never tighter
                                                                     # than entry risk
        self.trail_stop = max(self.trail_stop, self.peak - distance)


# ----------------------------------------------------------------------------
# THE BOT
# ----------------------------------------------------------------------------

class V31:

    def __init__(self):
        key = os.environ["ALPACA_API_KEY"]
        secret = os.environ["ALPACA_SECRET_KEY"]
        paper_raw = os.environ.get("ALPACA_PAPER", "1").strip().lower()
        paper = paper_raw in ("1", "true", "t", "yes", "y", "on")
        self.paper = paper
        feed_name = os.environ.get("ALPACA_FEED", "sip").strip().lower()
        feed = DataFeed.SIP if feed_name == "sip" else DataFeed.IEX

        self.trading = TradingClient(key, secret, paper=paper)
        self.data = StockHistoricalDataClient(key, secret)
        self.stream = StockDataStream(key, secret, feed=feed)

        self.state: dict[str, SymState] = {}
        self.subscribed: set[str] = set()
        self.borrow: dict[str, bool] = {}

        self.day = None
        self.day_start_equity = 0.0
        self.halt_streak = 0
        self.halted_today = False
        self.stopped = False
        self.last_rebalance = 0.0
        self.last_speeds: dict[str, float] = {}
        self.last_auth_warn = 0.0
        self.needs_reconcile = True
        self._eq = 0.0
        self._eq_at = 0.0
        self.last_probe = 0.0

    # ---- helpers ------------------------------------------------------------

    def st(self, symbol: str) -> SymState:
        if symbol not in self.state:
            self.state[symbol] = SymState(symbol=symbol)
        return self.state[symbol]

    def equity(self) -> float:
        """Cached for EQUITY_TTL seconds.

        This is called from evaluate(), which runs on EVERY trade tick of every
        watched name. Uncached it was a blocking HTTP round-trip per tick -
        hundreds per second across the watchlist, enough to rate-limit the
        account and stall the very stops it was being called to check.
        """
        now = time.time()
        if now - self._eq_at < EQUITY_TTL and self._eq > 0:
            return self._eq
        try:
            self._eq = float(self.trading.get_account().equity)
            self._eq_at = now
            return self._eq
        except Exception:
            return self._eq or self.day_start_equity

    def halt_threshold(self) -> float:
        i = min(self.halt_streak, len(HALT_LADDER) - 1)
        return HALT_LADDER[i]

    # ---- day roll -----------------------------------------------------------

    def roll_day(self):
        today = datetime.now(ET).date()
        if self.day == today:
            return
        if self.day is not None:
            self.halt_streak = self.halt_streak + 1 if self.halted_today else 0
            if self.halt_streak >= 3:
                self.stopped = True
                log.critical("Three halted days in a row - stopped until restarted.")
        self.day = today
        self.halted_today = False
        self.day_start_equity = self.equity()
        self.state.clear()
        self.last_speeds.clear()
        self.needs_reconcile = True        # state was just wiped - re-read broker
        log.info("New day %s, baseline equity %.2f, halt at -%.1f%%",
                 today, self.day_start_equity, 100 * self.halt_threshold())

    # ---- reconciliation -----------------------------------------------------
    # The broker is the truth. Memory is a cache. On every restart, redeploy,
    # crash or day roll the cache is empty while the account may still be holding
    # stock - from this strategy, or from whatever ran here before. Without this
    # the bot would size new trades as if it held nothing, ignore the stops on
    # what it already owns, and leave old positions to rot untouched all day.

    def broker_positions(self) -> dict:
        """What the account ACTUALLY holds, keyed by symbol. {} if unreachable."""
        try:
            out = {}
            for p in self.trading.get_all_positions():
                try:
                    qty = float(p.qty)
                except Exception:
                    continue
                if qty <= 0:                       # long-only; ignore any short
                    continue
                out[p.symbol] = {
                    "qty": qty,
                    "entry": float(p.avg_entry_price or 0.0),
                    "price": float(p.current_price or 0.0),
                }
            return out
        except Exception as e:
            log.error("cannot read positions from the broker: %s", e)
            return None                            # None = unknown, NOT empty

    def broker_qty(self, symbol: str) -> float:
        """One symbol's real share count. 0.0 when flat, None when unreachable."""
        try:
            pos = self.trading.get_open_position(symbol)
            return float(pos.qty)
        except Exception as e:
            if "position does not exist" in str(e).lower() or "404" in str(e):
                return 0.0
            return None

    async def reconcile(self, why: str = "startup"):
        """Make memory agree with the broker. Runs at boot and every minute."""
        held = self.broker_positions()
        if held is None:
            return                                 # unreachable - change nothing

        market_open = self.market_is_open()
        adopted, dropped, corrected, flattened = [], [], [], []

        # --- positions the broker has ---------------------------------------
        for sym, info in held.items():
            s = self.st(sym)
            price = info["price"] or info["entry"] or s.last_price

            if not s.in_position:
                # We hold stock we have no memory of opening.
                if (ORPHAN_MODE == "flatten" and market_open
                        and self.in_flatten_window()):
                    sold = await self.sell(sym, int(info["qty"]), price)
                    flattened.append((sym, sold))
                    DLOG.record(ev="ORPHAN-FLATTEN", sym=sym, sh=sold, px=price)
                    continue
                s.shares = info["qty"]
                s.entry = info["entry"] or price
                s.adopted = True
                s.armed = False
                # Seed the peak from where the stock is NOW, not from its old
                # entry. We do not know the real high-water mark - seeding from
                # entry would put the leash above the price on anything that has
                # pulled back, and dump a healthy position the moment we restart.
                # Clearing out genuine junk is what ORPHAN_MODE=flatten is for.
                s.peak = price or s.entry
                s.last_price = s.last_price or price
                s.entry_stop = max(s.entry_stop,
                                   s.peak * (1 - ORPHAN_STOP_PCT))
                s.trail_stop = 0.0
                adopted.append((sym, info["qty"], s.entry_stop))
                DLOG.record(ev="ADOPT", sym=sym, sh=info["qty"],
                            entry=s.entry, px=price, stop=s.entry_stop, why=why)
            elif abs(s.shares - info["qty"]) >= 1:
                # Our count drifted from the broker's - the broker wins.
                corrected.append((sym, s.shares, info["qty"]))
                DLOG.record(ev="QTY-FIX", sym=sym, ours=s.shares,
                            broker=info["qty"], why=why)
                s.shares = info["qty"]

        # --- positions WE think we have but the broker does not -------------
        for s in list(self.state.values()):
            if s.in_position and s.symbol not in held:
                dropped.append((s.symbol, s.shares))
                DLOG.record(ev="GHOST-CLEAR", sym=s.symbol, sh=s.shares, why=why)
                s.shares = 0.0
                s.entry = s.entry_stop = s.trail_stop = 0.0
                s.armed = False
                s.adopted = False
                s.quiet_bars = 0

        if adopted:
            await self.subscribe([sym for sym, _, _ in adopted])
            for sym, qty, stop in adopted:
                log.warning("ADOPTED %s: %.0f shares already held, stop set %.4f",
                            sym, qty, stop)
        for sym, sold in flattened:
            log.warning("FLATTENED orphan %s: sold %d", sym, sold)
        for sym, ours, real in corrected:
            log.warning("QTY CORRECTED %s: we said %.0f, broker says %.0f",
                        sym, ours, real)
        for sym, qty in dropped:
            log.warning("GHOST CLEARED %s: we thought %.0f, broker holds none",
                        sym, qty)
        if not (adopted or flattened or corrected or dropped):
            log.info("reconcile (%s): broker and memory agree, %d position(s)",
                     why, len(held))

    def market_is_open(self) -> bool:
        """Tradeable session, NOT the 9:30-16:00 regular one.

        Extended hours open at 4:00am ET and the best moves of the day happen
        before 9:30. Every order this bot sends carries extended_hours=True, so
        4:00-20:00 is the real window. Anything that treats 9:30 as the start
        is wrong for this strategy.
        """
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        start, end = SESSION
        return start <= (now.hour, now.minute) < end

    def in_flatten_window(self) -> bool:
        """ORPHAN_MODE=flatten may only act in the first minutes of the session.

        Without this, leaving the variable set would be a loaded gun: a restart
        at 2pm finds an empty memory, calls its own healthy positions orphans,
        and sells the lot. Time-boxing it to the first ten minutes after the
        4:00am open means the switch clears what was left overnight and nothing
        else. It is still a blunt instrument - closing a leftover by hand in the
        Alpaca web interface is safer and always preferred.
        """
        now = datetime.now(ET)
        start, end = ORPHAN_FLATTEN_WINDOW
        return start <= (now.hour, now.minute) < end

    # ---- scanner ------------------------------------------------------------

    def load_borrow_flags(self, symbols):
        """easy_to_borrow comes free from the assets endpoint. Cache daily."""
        missing = [s for s in symbols if s not in self.borrow]
        if not missing:
            return
        try:
            assets = self.trading.get_all_assets(
                GetAssetsRequest(status=AssetStatus.ACTIVE))
            for a in assets:
                if a.symbol in missing:
                    self.borrow[a.symbol] = bool(getattr(a, "easy_to_borrow", True))
        except Exception as e:
            log.warning("borrow flags unavailable: %s", e)

    def scan(self) -> list[str]:
        """Universe: $1-20, up 10% from today's first trade, volume >= RDV.

        NOTE: float is NOT available from Alpaca. If a float source is wired in,
        apply FLOAT_MIN/FLOAT_MAX here. Until then the filter is skipped and the
        skip is logged, so it is never silently believed to be running.
        """
        try:
            assets = self.trading.get_all_assets(
                GetAssetsRequest(status=AssetStatus.ACTIVE))
            symbols = [a.symbol for a in assets
                       if a.tradable and a.symbol.isalpha() and len(a.symbol) <= 4]
        except Exception as e:
            now = time.time()
            if now - self.last_auth_warn > 60:
                self.last_auth_warn = now
                log.error("asset list failed: %s", e)
                if "not authorized" in str(e):
                    log.critical(
                        "KEYS AND ENDPOINT DO NOT MATCH. Currently using the %s "
                        "endpoint. Paper keys need ALPACA_PAPER=true (or 1); "
                        "live keys need ALPACA_PAPER=false (or 0).",
                        "PAPER" if self.paper else "LIVE")
            return []

        picks = []
        probe = []                    # premarket diagnostic - see log_probe()
        for chunk in [symbols[i:i + 500] for i in range(0, len(symbols), 500)]:
            try:
                snaps = self.data.get_stock_snapshot(
                    StockSnapshotRequest(symbol_or_symbols=chunk))
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
                    if len(probe) < 5:
                        pb = getattr(snap, "previous_daily_bar", None)
                        probe.append((
                            sym, float(last),
                            float(getattr(bar, "open", 0) or 0),
                            str(getattr(bar, "timestamp", ""))[:10],
                            float(getattr(pb, "close", 0) or 0)))
                    if bar.open <= 0 or last < bar.open * (1 + GAIN_FROM_OPEN):
                        continue
                    picks.append(sym)
                except Exception:
                    continue

        self.log_probe(probe)
        DLOG.record(ev="scan", n=len(picks), float_filter="SKIPPED-no-source")
        return picks

    def log_probe(self, probe):
        """Print what the qualifying test is ACTUALLY comparing against.

        Premarket there is no "today's open" yet. If daily_bar is still carrying
        yesterday's session, the 10% test is measuring this morning's price
        against yesterday's 9:30 open - which is not the rule we wrote. The bar's
        own date in this line settles it either way.
        """
        now = time.time()
        if not probe or now - self.last_probe < 60:
            return
        self.last_probe = now
        for sym, last, dopen, dts, pclose in probe:
            g_open = (last / dopen - 1) * 100 if dopen else 0.0
            g_prev = (last / pclose - 1) * 100 if pclose else 0.0
            log.info("PROBE %-5s last=%.4f | daily_bar.open=%.4f dated %s "
                     "-> %+.1f%% | prev_close=%.4f -> %+.1f%%",
                     sym, last, dopen, dts, g_open, pclose, g_prev)

    # ---- streaming ----------------------------------------------------------

    async def on_bar(self, bar):
        """Alpaca delivers a bar only once the minute has CLOSED."""
        s = self.st(bar.symbol)
        s.add_bar(Bar(ts=bar.timestamp, o=bar.open, h=bar.high,
                      l=bar.low, c=bar.close, v=bar.volume))

    async def on_trade(self, trade):
        s = self.st(trade.symbol)
        s.trades.append((trade.price, trade.size))
        s.last_price = trade.price
        s.day_high = max(s.day_high, trade.price)
        await self.evaluate(s)

    async def subscribe(self, symbols):
        new = [x for x in symbols if x not in self.subscribed]
        if not new:
            return
        for sym in new:
            self.stream.subscribe_bars(self.on_bar, sym)
            self.stream.subscribe_trades(self.on_trade, sym)
            self.subscribed.add(sym)
        log.info("watching %d names (+%d)", len(self.subscribed), len(new))

    # ---- the precedence ladder ---------------------------------------------

    async def evaluate(self, s: SymState):
        """One rule acts at a time. Highest match wins, the rest are skipped."""
        if self.stopped or self.halted_today:
            return
        price = s.last_price
        if price <= 0:
            return

        # 1. account halt
        eq = self.equity()
        if self.day_start_equity and eq <= self.day_start_equity * (1 - self.halt_threshold()):
            await self.flatten_all("daily-halt")
            self.halted_today = True
            return

        fast = s.fast_speed()
        base = s.baseline_speed()

        if s.in_position:
            s.update_trail(price)

            # 2. flush - large NEGATIVE speed. Never consult the trail.
            if fast is not None and base > 0 and fast <= -SPEED_FLUSH_MULT * base:
                await self.exit(s, "flush", urgency=abs(fast))
                return

            # 3. entry stop, while unproven
            if not s.armed and price <= s.entry_stop:
                await self.exit(s, "entry-stop")
                return

            # 4. the trail
            if s.armed and s.trail_stop and price <= s.trail_stop:
                await self.exit(s, "trail")
                return

            # 5. stall - sideways with volume gone
            if s.quiet_bars >= STALL_BARS:
                await self.exit(s, "stall")
                return
            if fast is not None and base > 0 and fast < 0 and s.quiet_bars >= 2:
                await self.exit(s, "fade")
                return

            # 7. add on strong speed
            if fast is not None and base > 0 and fast >= SPEED_ADD_MULT * base:
                await self.maybe_add(s, price)
            return

        # not holding - look for an entry
        await self.maybe_enter(s, price, fast, base)

    # ---- entry --------------------------------------------------------------

    def margin_for(self, price: float) -> float:
        if price <= 5:
            return 0.05
        if price <= 20:
            return 0.01 * price
        if price <= 50:
            return 0.20 + (price - 20) * (0.10 / 30)
        if price <= 100:
            return 0.30 + (price - 50) * (0.10 / 50)
        return 0.40

    async def maybe_enter(self, s: SymState, price: float, fast, base):
        if len(self.open_positions()) >= MAX_POSITIONS:
            return
        if not s.setup_ready:
            DLOG.record(ev="reject", sym=s.symbol, why="no-setup")
            return
        if price < s.setup_level:
            return                                   # trigger not hit yet
        if not s.thin_ok():
            DLOG.record(ev="reject", sym=s.symbol, why="thin")
            return
        if fast is None or fast <= 0:
            DLOG.record(ev="reject", sym=s.symbol, why="speed-not-positive")
            return
        if base > 0 and fast < SPEED_ADD_MULT * base:
            DLOG.record(ev="reject", sym=s.symbol, why="speed-below-5x")
            return

        # a name we already traded today must make a NEW high + margin
        if s.peak > 0 and price < s.day_high + self.margin_for(price):
            DLOG.record(ev="reject", sym=s.symbol, why="below-day-high+margin")
            return

        risk_per_share = max(price - s.setup_low, 0.01)
        risk_dollars = self.equity() * RISK_PER_TRADE
        shares = int(risk_dollars / risk_per_share)
        if shares * price < MIN_TRADE_DOLLARS:
            return

        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares = filled
            s.entry = price
            s.entry_stop = s.setup_low
            s.peak = price
            s.trail_stop = 0.0
            s.armed = False
            DLOG.record(ev="ENTER", sym=s.symbol, px=price, sh=filled,
                        level=s.setup_level, stop=s.setup_low,
                        speed=fast, baseline=base, abr=s.abr())

    async def maybe_add(self, s: SymState, price: float):
        target = self.target_dollars(s.symbol)
        held = s.shares * price
        gap = target - held
        if gap < MIN_TRADE_DOLLARS:
            return
        shares = int(gap / price)
        if shares <= 0:
            return
        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares += filled
            DLOG.record(ev="ADD", sym=s.symbol, px=price, sh=filled, target=target)

    # ---- sizing -------------------------------------------------------------

    def open_positions(self) -> list[SymState]:
        return [s for s in self.state.values() if s.in_position]

    def target_dollars(self, symbol: str) -> float:
        """Capital in proportion to speed, leader capped at 80%."""
        held = self.open_positions()
        speeds = {}
        for s in held:
            f = s.fast_speed()
            speeds[s.symbol] = max(f, 0.0) if f is not None else 0.0
        total = sum(speeds.values())
        if total <= 0:
            return 0.0
        weights = {k: v / total for k, v in speeds.items()}
        top = max(weights, key=weights.get)
        if weights[top] > LEADER_CAP:
            rest = 1 - LEADER_CAP
            other = sum(v for k, v in weights.items() if k != top)
            weights = {k: (LEADER_CAP if k == top else (v / other) * rest)
                       for k, v in weights.items()}
        return self.equity() * weights.get(symbol, 0.0)

    async def rebalance(self, reason: str):
        for s in self.open_positions():
            price = s.last_price
            if price <= 0:
                continue
            target = self.target_dollars(s.symbol)
            held = s.shares * price
            diff = target - held
            if abs(diff) < MIN_TRADE_DOLLARS:
                continue
            if diff > 0:
                await self.maybe_add(s, price)
            else:
                shares = min(s.shares, int(abs(diff) / price))
                if shares > 0:
                    sold = await self.sell(s.symbol, shares, price)
                    s.shares = max(0.0, s.shares - sold)
        DLOG.record(ev="rebalance", why=reason)

    # ---- exits --------------------------------------------------------------

    async def exit(self, s: SymState, why: str, urgency: float = 0.0):
        shares = s.shares
        if shares <= 0:
            return
        sold = await self.sell(s.symbol, int(shares), s.last_price)
        DLOG.record(ev="EXIT", sym=s.symbol, why=why, px=s.last_price,
                    sh=sold, entry=s.entry, peak=s.peak,
                    trail=s.trail_stop, urgency=urgency)
        s.shares = max(0.0, s.shares - sold)
        if s.shares <= 0:
            s.entry = s.entry_stop = s.trail_stop = 0.0
            s.armed = False
            s.quiet_bars = 0

    async def flatten_all(self, why: str):
        for s in self.open_positions():
            await self.exit(s, why)

    # ---- order chase --------------------------------------------------------

    async def buy(self, symbol: str, shares: int, ref_price: float) -> int:
        """Chase upward, capped 2% above the ask. Never let a runner escape.

        Fills are counted from the BROKER's position, not from what the order
        reply told us. A cancel that races a fill used to report "got nothing"
        and the next attempt bought the whole clip again - that is how a $600
        slot became $3,050. Asking the broker what we own makes that impossible.
        """
        start = self.broker_qty(symbol)
        if start is None:
            start = 0.0                            # unreachable: fall back
        for _ in range(CHASE_ATTEMPTS):
            now = self.broker_qty(symbol)
            filled = (now - start) if now is not None else 0.0
            remaining = int(shares - filled)
            if remaining <= 0:
                break
            ask = self.quote(symbol, "ask") or ref_price
            limit = round(min(ask * 1.002, ref_price * (1 + BUY_CHASE_CAP)), 2)
            got = await self.send(symbol, remaining, OrderSide.BUY, limit)
            if got == 0:
                await asyncio.sleep(CHASE_PAUSE)
        end = self.broker_qty(symbol)
        if end is None:
            return 0
        return max(0, int(end - start))

    async def sell(self, symbol: str, shares: int, ref_price: float) -> int:
        """Chase downward, UNCAPPED. A stop must always get out.

        Counted from the broker in the same way, and clamped to what we really
        own - so a stop can never try to sell more than the account holds and
        get the whole order rejected with shorting switched off.
        """
        start = self.broker_qty(symbol)
        if start is None:
            start = float(shares)
        want = min(int(shares), int(start))
        if want <= 0:
            return 0
        for _ in range(CHASE_ATTEMPTS):
            now = self.broker_qty(symbol)
            sold = (start - now) if now is not None else 0.0
            remaining = int(want - sold)
            if remaining <= 0:
                break
            bid = self.quote(symbol, "bid") or ref_price
            limit = round(max(bid * 0.995, 0.01), 2)
            got = await self.send(symbol, remaining, OrderSide.SELL, limit)
            if got == 0:
                await asyncio.sleep(CHASE_PAUSE)
        end = self.broker_qty(symbol)
        if end is None:
            return want
        return max(0, int(start - end))

    def quote(self, symbol: str, side: str):
        try:
            snap = self.data.get_stock_snapshot(
                StockSnapshotRequest(symbol_or_symbols=symbol))
            q = snap[symbol].latest_quote
            return q.ask_price if side == "ask" else q.bid_price
        except Exception:
            return None

    async def send(self, symbol: str, qty: int, side: OrderSide, limit: float) -> int:
        try:
            order = self.trading.submit_order(LimitOrderRequest(
                symbol=symbol, qty=qty, side=side,
                time_in_force=TimeInForce.DAY, limit_price=limit,
                extended_hours=True))
            for _ in range(10):
                await asyncio.sleep(0.2)
                o = self.trading.get_order_by_id(order.id)
                if o.filled_qty and float(o.filled_qty) > 0:
                    return int(float(o.filled_qty))
                if str(o.status) in ("OrderStatus.FILLED", "OrderStatus.CANCELED"):
                    break
            try:
                self.trading.cancel_order_by_id(order.id)
            except Exception:
                pass
            return 0
        except Exception as e:
            log.error("order failed %s %s: %s", side, symbol, e)
            return 0

    # ---- main loops ---------------------------------------------------------

    async def scanner_loop(self):
        while True:
            try:
                self.roll_day()
                if self.needs_reconcile:
                    self.needs_reconcile = False
                    await self.reconcile("day-roll")
                if not self.stopped and not self.halted_today:
                    picks = self.scan()
                    self.load_borrow_flags(picks)
                    for sym in picks:
                        self.st(sym).easy_to_borrow = self.borrow.get(sym, True)
                    await self.subscribe(picks[:200])
            except Exception as e:
                log.error("scanner: %s", e)
            await asyncio.sleep(SCAN_SECONDS)

    async def rebalance_loop(self):
        while True:
            await asyncio.sleep(5)
            try:
                now = time.time()
                due = now - self.last_rebalance >= REBALANCE_SECONDS
                event = False
                for s in self.open_positions():
                    f = s.fast_speed()
                    if f is None:
                        continue
                    was = self.last_speeds.get(s.symbol)
                    if was and was > 0 and (f >= SPEED_EVENT_MULT * was
                                            or f <= was / SPEED_EVENT_MULT):
                        event = True
                    self.last_speeds[s.symbol] = max(f, 0.0)
                if (due or event) and self.open_positions():
                    await self.rebalance("clock" if due else "speed-event")
                    self.last_rebalance = now
            except Exception as e:
                log.error("rebalance: %s", e)

    async def reconcile_loop(self):
        """A minute is fast enough to catch drift, slow enough to cost nothing."""
        while True:
            await asyncio.sleep(RECONCILE_SECONDS)
            try:
                await self.reconcile("periodic")
            except Exception as e:
                log.error("reconcile: %s", e)

    async def close_loop(self):
        while True:
            await asyncio.sleep(20)
            now = datetime.now(ET)
            if (now.hour, now.minute) >= FLATTEN_AT and self.open_positions():
                log.info("End of day - flattening everything.")
                await self.flatten_all("end-of-day")

    async def stream_forever(self):
        """Keep the websocket alive inside our own event loop.

        alpaca-py's public .run() creates its own loop, so inside a running
        loop we use the internal coroutine; if that name ever changes, fall
        back to running .run() on a worker thread.
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
                    # The old socket has not been released yet. Coming straight
                    # back only competes with ourselves - close and wait it out.
                    try:
                        await self.stream.close()
                    except Exception:
                        pass
                    log.error("stream refused (connection limit) - waiting 30s")
                    await asyncio.sleep(30)
                else:
                    log.error("stream dropped (%s) - reconnecting in 5s", e)
                    await asyncio.sleep(5)

    def check_account(self):
        """Fail loudly at boot instead of running with equity 0.00."""
        try:
            acct = self.trading.get_account()
            log.info("Connected to Alpaca %s account %s - equity %.2f",
                     "PAPER" if self.paper else "LIVE",
                     acct.account_number, float(acct.equity))
            return True
        except Exception as e:
            log.critical("CANNOT REACH THE ACCOUNT: %s", e)
            log.critical("Using the %s endpoint. Paper keys need ALPACA_PAPER=true "
                         "(or 1); live keys need ALPACA_PAPER=false (or 0). "
                         "Nothing will trade until this matches.",
                         "PAPER" if self.paper else "LIVE")
            return False

    async def run(self):
        self.check_account()
        self.roll_day()
        # Before a single decision is made, find out what we already own.
        self.needs_reconcile = False
        await self.reconcile("startup")
        log.info("v31 starting. equity %.2f, orphan mode %s",
                 self.day_start_equity, ORPHAN_MODE)
        await asyncio.gather(
            self.scanner_loop(),
            self.rebalance_loop(),
            self.reconcile_loop(),
            self.close_loop(),
            DLOG.flusher(),
            self.stream_forever(),
        )


if __name__ == "__main__":
    asyncio.run(V31().run())
