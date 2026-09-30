"""
v32 - "keep only what holds".

  * Buy EVERY stock our scanner surfaces, on the first tick after it qualifies.
  * Stop = entry minus one cent (or 0.1% of price, whichever is larger).
  * Once stopped, it can only return on a NEW HIGH OF THE DAY plus the margin.
  * Close everything at the end of the day.

What survives to the close is the set of stocks that never came back to where
we bought them.

Environment:
  ALPACA_API_KEY, ALPACA_SECRET_KEY
  ALPACA_PAPER   true/1 for paper (default), false/0 for live
  ALPACA_FEED    "sip" (recommended) or "iex"
"""

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockSnapshotRequest
from alpaca.data.enums import DataFeed
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest, LimitOrderRequest
from alpaca.trading.enums import AssetStatus, OrderSide, TimeInForce

ET = ZoneInfo("America/New_York")

START_CAPITAL = 30_000.0
MAX_NAMES = 50
SLOT_DOLLARS = START_CAPITAL / MAX_NAMES

PRICE_MIN = 1.00
PRICE_MAX = 20.00
GAIN_FROM_OPEN = 0.10

STOP_CENTS = 0.01
STOP_PCT = 0.001

HALT_LADDER = [0.10, 0.05, 0.025]
FLATTEN_AT = (15, 58)

BUY_CHASE_CAP = 0.02
CHASE_ATTEMPTS = 8
CHASE_PAUSE = 0.35
SCAN_SECONDS = 8

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("v32")


class DecisionLog:
    """Buffered, flushed off the critical path. Never blocks a decision."""

    def __init__(self, path="/tmp/v32_decisions.log", maxlen=20000):
        self.buf = deque(maxlen=maxlen)
        self.path = path

    def record(self, **f):
        try:
            f["t"] = datetime.now(ET).isoformat()
            self.buf.append(f)
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
                with open(self.path, "a") as fh:
                    fh.write("\n".join(lines) + "\n")
            except Exception:
                pass


DLOG = DecisionLog()


@dataclass
class SymState:
    symbol: str
    last_price: float = 0.0
    day_high: float = 0.0
    shares: float = 0.0
    entry: float = 0.0
    stop: float = 0.0
    traded_today: bool = False

    @property
    def in_position(self) -> bool:
        return self.shares > 0


def margin_for(price: float) -> float:
    """1% of price, floor 5 cents, capped at 40 cents."""
    if price <= 5:
        return 0.05
    if price <= 20:
        return 0.01 * price
    if price <= 50:
        return 0.20 + (price - 20) * (0.10 / 30)
    if price <= 100:
        return 0.30 + (price - 50) * (0.10 / 50)
    return 0.40


def stop_for(entry: float) -> float:
    return entry - max(STOP_CENTS, STOP_PCT * entry)


class V32:

    def __init__(self):
        key = os.environ["ALPACA_API_KEY"]
        secret = os.environ["ALPACA_SECRET_KEY"]
        paper_raw = os.environ.get("ALPACA_PAPER", "1").strip().lower()
        self.paper = paper_raw in ("1", "true", "t", "yes", "y", "on")
        feed_name = os.environ.get("ALPACA_FEED", "sip").strip().lower()
        feed = DataFeed.SIP if feed_name == "sip" else DataFeed.IEX

        self.trading = TradingClient(key, secret, paper=self.paper)
        self.data = StockHistoricalDataClient(key, secret)
        self.stream = StockDataStream(key, secret, feed=feed)

        self.state: dict[str, SymState] = {}
        self.subscribed: set[str] = set()
        self.qualified: set[str] = set()

        self.day = None
        self.day_start_equity = 0.0
        self.halt_streak = 0
        self.halted_today = False
        self.stopped = False
        self.last_auth_warn = 0.0

    def st(self, symbol: str) -> SymState:
        if symbol not in self.state:
            self.state[symbol] = SymState(symbol=symbol)
        return self.state[symbol]

    def equity(self) -> float:
        try:
            return float(self.trading.get_account().equity)
        except Exception:
            return self.day_start_equity

    def halt_threshold(self) -> float:
        return HALT_LADDER[min(self.halt_streak, len(HALT_LADDER) - 1)]

    def open_positions(self):
        return [s for s in self.state.values() if s.in_position]

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
        self.qualified.clear()
        log.info("New day %s, baseline equity %.2f, halt at -%.1f%%",
                 today, self.day_start_equity, 100 * self.halt_threshold())

    def scan(self) -> list:
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
                    log.critical("KEYS AND ENDPOINT DO NOT MATCH. Using the %s "
                                 "endpoint. Paper keys need ALPACA_PAPER=true; "
                                 "live keys need ALPACA_PAPER=false.",
                                 "PAPER" if self.paper else "LIVE")
            return []

        picks = []
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
                    if bar.open <= 0 or last < bar.open * (1 + GAIN_FROM_OPEN):
                        continue
                    picks.append(sym)
                    s = self.st(sym)
                    s.day_high = max(s.day_high, float(bar.high or 0.0))
                except Exception:
                    continue
        return picks

    async def on_trade(self, trade):
        s = self.st(trade.symbol)
        s.last_price = trade.price
        s.day_high = max(s.day_high, trade.price)
        await self.evaluate(s)

    async def subscribe(self, symbols):
        new = [x for x in symbols if x not in self.subscribed]
        if not new:
            return
        for sym in new:
            self.stream.subscribe_trades(self.on_trade, sym)
            self.subscribed.add(sym)
        log.info("watching %d names (+%d)", len(self.subscribed), len(new))

    async def evaluate(self, s: SymState):
        if self.stopped or self.halted_today:
            return
        price = s.last_price
        if price <= 0:
            return

        eq = self.equity()
        if self.day_start_equity and eq <= self.day_start_equity * (1 - self.halt_threshold()):
            await self.flatten_all("daily-halt")
            self.halted_today = True
            return

        if s.in_position:
            if price <= s.stop:
                await self.exit(s, "stop")
            return

        if s.symbol not in self.qualified:
            return
        if len(self.open_positions()) >= MAX_NAMES:
            return

        if s.traded_today and price < s.day_high + margin_for(price):
            return

        shares = int(SLOT_DOLLARS / price)
        if shares <= 0:
            return
        filled = await self.buy(s.symbol, shares, price)
        if filled:
            s.shares = filled
            s.entry = price
            s.stop = stop_for(price)
            s.traded_today = True
            DLOG.record(ev="ENTER", sym=s.symbol, px=price, sh=filled, stop=s.stop)

    async def exit(self, s: SymState, why: str):
        if s.shares <= 0:
            return
        sold = await self.sell(s.symbol, int(s.shares), s.last_price)
        DLOG.record(ev="EXIT", sym=s.symbol, why=why, px=s.last_price,
                    sh=sold, entry=s.entry, stop=s.stop)
        s.shares = max(0.0, s.shares - sold)
        if s.shares <= 0:
            s.entry = 0.0
            s.stop = 0.0

    async def flatten_all(self, why: str):
        for s in self.open_positions():
            await self.exit(s, why)

    async def buy(self, symbol: str, shares: int, ref: float) -> int:
        remaining = shares
        for _ in range(CHASE_ATTEMPTS):
            if remaining <= 0:
                break
            ask = self.quote(symbol, "ask") or ref
            limit = round(min(ask * 1.002, ref * (1 + BUY_CHASE_CAP)), 2)
            got = await self.send(symbol, remaining, OrderSide.BUY, limit)
            remaining -= got
            if got == 0:
                await asyncio.sleep(CHASE_PAUSE)
        return shares - remaining

    async def sell(self, symbol: str, shares: int, ref: float) -> int:
        remaining = shares
        for _ in range(CHASE_ATTEMPTS):
            if remaining <= 0:
                break
            bid = self.quote(symbol, "bid") or ref
            limit = round(max(bid * 0.995, 0.01), 2)
            got = await self.send(symbol, remaining, OrderSide.SELL, limit)
            remaining -= got
            if got == 0:
                await asyncio.sleep(CHASE_PAUSE)
        return shares - remaining

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

    async def scanner_loop(self):
        while True:
            try:
                self.roll_day()
                if not self.stopped and not self.halted_today:
                    picks = self.scan()
                    self.qualified.update(picks)
                    await self.subscribe(picks[:200])
            except Exception as e:
                log.error("scanner: %s", e)
            await asyncio.sleep(SCAN_SECONDS)

    async def close_loop(self):
        while True:
            await asyncio.sleep(20)
            now = datetime.now(ET)
            if (now.hour, now.minute) >= FLATTEN_AT and self.open_positions():
                log.info("End of day - flattening everything.")
                await self.flatten_all("end-of-day")

    async def stream_forever(self):
        while True:
            try:
                if hasattr(self.stream, "_run_forever"):
                    await self.stream._run_forever()
                else:
                    await asyncio.to_thread(self.stream.run)
            except Exception as e:
                log.error("stream dropped (%s) - reconnecting in 5s", e)
                await asyncio.sleep(5)

    def check_account(self):
        try:
            acct = self.trading.get_account()
            log.info("Connected to Alpaca %s account %s - equity %.2f",
                     "PAPER" if self.paper else "LIVE",
                     acct.account_number, float(acct.equity))
            return True
        except Exception as e:
            log.critical("CANNOT REACH THE ACCOUNT: %s", e)
            log.critical("Using the %s endpoint. Paper keys need "
                         "ALPACA_PAPER=true; live keys need ALPACA_PAPER=false.",
                         "PAPER" if self.paper else "LIVE")
            return False

    async def run(self):
        self.check_account()
        self.roll_day()
        log.info("v32 starting - %d slots of $%.0f each", MAX_NAMES, SLOT_DOLLARS)
        await asyncio.gather(
            self.scanner_loop(),
            self.close_loop(),
            DLOG.flusher(),
            self.stream_forever(),
        )


if __name__ == "__main__":
    asyncio.run(V32().run())
