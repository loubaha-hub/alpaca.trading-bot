"""
Fakes and builders shared by the tests.

FakeBroker and FakeData have the same async methods the strategies call on the
real Broker and MarketData. Every broker call yields to the event loop once,
like the real ones do (they run in a thread), so concurrency bugs show up here
the way they would live.
"""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import bot


class FakeBroker:
    """One paper account. Orders fill at their limit price.

    fills : fraction of each order that fills, consumed one per send(); when
            empty, orders fill in full.
    qty_fails_on : 1-based numbers of qty() calls that fail (return None, as
            the real Broker.qty does when the broker is unreachable).
    """

    def __init__(self, equity=100_000.0):
        self.eq = equity
        self.held = {}                 # symbol -> shares
        self.cost = {}                 # symbol -> total dollars paid
        self.orders = []               # (symbol, qty, side, limit, filled)
        self.fills = []
        self.fill_log = {}             # symbol -> [(shares, price)], as Broker
        self.qty_fails_on = set()
        self.qty_calls = 0
        self.settled = True            # as Broker.send: the last order closed
        self.market_refused = False    # as Broker.send_market
        self.market_orders = []        # (symbol, qty, side) sent at market
        self.working = 0               # wait_clear() says "still working" this many times
        self.clear_checks = 0
        self.day_fills = []            # as Broker.fills_today: (t, sym, side, qty, px)

    # -- what the strategy calls ------------------------------------------------

    async def equity(self, fallback=0.0):
        await asyncio.sleep(0)
        return self.eq

    async def fills_today(self):
        await asyncio.sleep(0)
        return sorted(self.day_fills)

    async def fills_between(self, start, end=None, pages=20):
        await asyncio.sleep(0)
        hi = end.timestamp() if end else float("inf")
        return sorted(f for f in self.day_fills if start.timestamp() <= f[0] < hi)

    async def qty(self, symbol):
        await asyncio.sleep(0)
        self.qty_calls += 1
        if self.qty_calls in self.qty_fails_on:
            return None
        return self.held.get(symbol, 0.0)

    async def send(self, symbol, qty, side, limit, wait=None):
        await asyncio.sleep(0)
        frac = self.fills.pop(0) if self.fills else 1.0
        if side == bot.OrderSide.BUY:
            got = int(qty * frac)
            self.held[symbol] = self.held.get(symbol, 0.0) + got
            self.cost[symbol] = self.cost.get(symbol, 0.0) + got * limit
        else:
            got = min(int(qty * frac), int(self.held.get(symbol, 0.0)))
            if self.held.get(symbol):
                avg = self.cost[symbol] / self.held[symbol]
                self.held[symbol] -= got
                self.cost[symbol] = avg * self.held[symbol]
        self.orders.append((symbol, qty, side, limit, got))
        if got > 0:                    # as Broker.send: what filled, at what price
            self.fill_log.setdefault(symbol, []).append((got, limit))
        return got

    async def send_market(self, symbol, qty, side, ref=0.0, wait=None):
        """As Broker.send_market; fills at ref (what the limit would have been)."""
        self.market_orders.append((symbol, qty, side))
        return await self.send(symbol, qty, side, ref, wait)

    async def wait_clear(self, symbol, timeout=None):
        await asyncio.sleep(0)
        self.clear_checks += 1
        if self.working > 0:
            self.working -= 1
            return False
        return True

    def take_fill_price(self, symbol):
        rows = self.fill_log.pop(symbol, [])
        shares = sum(q for q, _ in rows)
        return sum(q * p for q, p in rows) / shares if shares else 0.0

    async def cancel_open(self, symbol):
        await asyncio.sleep(0)
        return 0

    async def avg_entry(self, symbol):
        await asyncio.sleep(0)
        return self.avg_cost(symbol) or None

    async def positions(self):
        await asyncio.sleep(0)
        return {sym: {"qty": q, "entry": self.avg_cost(sym), "price": self.avg_cost(sym)}
                for sym, q in self.held.items() if q > 0}

    # -- for assertions ---------------------------------------------------------

    def avg_cost(self, symbol):
        q = self.held.get(symbol, 0.0)
        return self.cost[symbol] / q if q else 0.0

    def buys(self, symbol=None):
        return [o for o in self.orders
                if o[2] == bot.OrderSide.BUY and (symbol is None or o[0] == symbol)]


class FakeData:
    """Quotes are whatever the test sets; unset means "no quote available"."""

    def __init__(self):
        self.quotes = {}               # (symbol, "ask"|"bid") -> price
        self.history = {}              # symbol -> [(bar start, close[, volume])] the data API has
        self.bar_requests = 0

    async def quote(self, symbol, side):
        return self.quotes.get((symbol, side))

    async def bars_between(self, symbol, start, end):
        self.bar_requests += 1
        return [row for row in self.history.get(symbol, []) if start <= row[0] <= end]

    async def subscribe(self, symbols, force=False):
        return None


# ---- building a v31 setup ---------------------------------------------------

def raw_bar(symbol, ts, o, h, l, c, v):
    """The shape of an alpaca bar, as offer_bar receives it."""
    return SimpleNamespace(symbol=symbol, timestamp=ts, open=o, high=h,
                           low=l, close=c, volume=v)


def feed_bars(strat, symbol, now, bars):
    """bars: list of (o, h, l, c, v), oldest first, one minute apart, the last
    one closing at `now`."""
    for i, (o, h, l, c, v) in enumerate(bars):
        ts = now - timedelta(minutes=len(bars) - i)
        strat.offer_bar(raw_bar(symbol, ts, o, h, l, c, v))


def feed_trades(strat, symbol, start, end, count=2 * bot.V31_TRADE_WINDOW,
                size=100):
    """`count` prints stepping evenly from `start` to `end`. Enough of them
    (100) makes fast_speed() a number; its sign follows end - start."""
    s = strat.st(symbol)
    for i in range(count):
        price = start + (end - start) * i / max(1, count - 1)
        strat.note_trade(s, round(price, 4), size)


def breakout(strat, clock, symbol="ABCD", *, red_open=10.00, red_low=9.75,
             bar_volume=40_000, speed="up", qualified=True):
    """Everything the v31 entry gate asks for, in one call:

      * three closed bars, the last two green then red, each `bar_volume`
        shares (40k each clears both thin_ok floors)
      * 100 recent prints moving `speed` ("up", "down" or None for too few)
      * the symbol on the scanner's list

    The trigger is then red_open + 0.01 and the red bar's low is red_low.
    Returns the symbol's state.
    """
    now = clock.now.astimezone(bot.timezone.utc)
    feed_bars(strat, symbol, now, [
        (red_open - 0.60, red_open - 0.30, red_open - 0.65, red_open - 0.40, bar_volume),
        (red_open - 0.40, red_open + 0.05, red_open - 0.45, red_open, bar_volume),   # green
        (red_open, red_open + 0.02, red_low, max(red_low, red_open - 0.20), bar_volume),  # red
    ])
    if speed == "up":
        feed_trades(strat, symbol, red_open - 0.10, red_open)
    elif speed == "down":
        feed_trades(strat, symbol, red_open, red_open - 0.10)
    elif speed is None:
        feed_trades(strat, symbol, red_open, red_open, count=10)
    if qualified:
        strat.qualified.add(symbol)
    s = strat.st(symbol)
    assert s.setup_ready, "breakout() failed to build a green-then-red setup"
    return s


def hold(strat, symbol, shares, price, entry=None, stop=None):
    """Put an open position straight into the strategy's memory and the fake
    broker, as if it had been entered earlier."""
    s = strat.st(symbol)
    s.shares = float(shares)
    s.entry = entry if entry is not None else price
    s.last_price = price
    s.peak = price
    s.stop = stop if stop is not None else price * 0.95
    s.traded_today = True
    strat.broker.held[symbol] = float(shares)
    strat.broker.cost[symbol] = shares * s.entry
    return s


def run(coro):
    return asyncio.run(coro)
