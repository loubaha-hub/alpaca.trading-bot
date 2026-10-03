"""
v31 EXITS ADDED IN r25 - the rebalance off, the flush scaled to the stock's
volatility, and the crash guard.

ABR (the stock's typical one-minute range) is set by feeding ten closed bars
of a known range, so 0.10 on a $10 stock is 1%: flush 5 x 1% = 5%, crash
3 x 1% = 3% within 30 seconds.
"""

import time

import pytest

import bot
from helpers import feed_bars, feed_trades, hold, run

PRICE = 10.0


def position(strat, clock, sym="ABCD", rng=0.10):
    """An open position whose ABR is `rng`, entered a while ago, with the
    entry stop far away so only the rule under test can fire."""
    now = clock.now.astimezone(bot.timezone.utc)
    half = rng / 2
    feed_bars(strat, sym, now, [(PRICE, PRICE + half, PRICE - half, PRICE, 40_000)] * 10)
    s = hold(strat, sym, 1000, PRICE, stop=PRICE * 0.5)
    s.entry_at = time.time() - 120
    return s


def tick(strat, s, price):
    s.last_price = price
    strat.note_trade(s, price, 100)
    run(strat.evaluate(s, price))


# ---- the rebalance is off ----------------------------------------------------

def test_rebalance_does_not_sell_a_position_whose_speed_dipped(v31, broker):
    s = hold(v31, "AAA", 1000, 10.0)
    s.entry_at = time.time() - 600
    feed_trades(v31, "AAA", 10.0, 9.8)               # speed negative
    run(v31.periodic())
    assert broker.held["AAA"] == 1000 and broker.orders == []


def test_rebalance_does_not_add_either(v31, broker):
    s = hold(v31, "AAA", 1000, 10.0)                 # 10%, under the 25% target
    s.entry_at = time.time() - 600
    feed_trades(v31, "AAA", 9.0, 10.0)
    run(v31.periodic())
    assert broker.orders == []


# ---- the flush scales with volatility ----------------------------------------

@pytest.mark.parametrize("rng,pct", [
    (0.10, 0.05),        # 1% ABR   -> 5 x 1%
    (0.03, 0.04),        # 0.3% ABR -> 1.5%, floored at 4%
    (0.30, 0.12),        # 3% ABR   -> 15%, capped at 12%
])
def test_flush_pct_follows_the_stocks_range(v31, clock, rng, pct):
    s = position(v31, clock, rng=rng)
    assert v31.flush_pct(s, PRICE) == pytest.approx(pct)


def test_flush_falls_back_to_6_percent_without_bars(v31):
    s = hold(v31, "AAA", 1000, PRICE)
    assert v31.flush_pct(s, PRICE) == 0.06
    assert v31.crash_pct(s, PRICE) == 0.05


def test_giveback_inside_the_flush_holds(v31, clock):
    s = position(v31, clock)                         # flush at 5%
    s.recent.clear()                                 # no crash window in play
    s.peak = PRICE
    run(v31.evaluate(s, 9.51))
    assert s.in_position


def test_giveback_past_the_flush_exits(v31, clock):
    s = position(v31, clock)
    s.recent.clear()
    s.peak = PRICE
    s.last_price = 9.49
    run(v31.evaluate(s, 9.49))
    assert not s.in_position
    assert v31.closed_today[-1][5] == "flush"


def test_old_3_percent_flush_no_longer_fires(v31, clock):
    s = position(v31, clock)
    s.recent.clear()
    s.peak = PRICE
    run(v31.evaluate(s, 9.65))                       # -3.5%: r24 sold here
    assert s.in_position


# ---- the crash guard ---------------------------------------------------------

def test_fast_drop_past_the_crash_line_exits(v31, clock):
    s = position(v31, clock)                         # crash at 3% in 30s
    tick(v31, s, PRICE)
    tick(v31, s, 9.69)                               # -3.1% seconds later
    assert not s.in_position
    assert v31.closed_today[-1][5] == "crash"


def test_fast_drop_short_of_the_crash_line_holds(v31, clock):
    s = position(v31, clock)
    tick(v31, s, PRICE)
    tick(v31, s, 9.71)                               # -2.9%
    assert s.in_position


def test_the_same_drop_spread_over_more_than_30_seconds_is_not_a_crash(v31, clock, monkeypatch):
    s = position(v31, clock)
    t0 = time.time()
    monkeypatch.setattr(bot.time, "time", lambda: t0)
    tick(v31, s, PRICE)
    monkeypatch.setattr(bot.time, "time", lambda: t0 + bot.V31_CRASH_WINDOW_SEC + 1)
    tick(v31, s, 9.69)
    assert s.in_position                             # the flush (5%) decides


def test_a_drop_from_before_the_entry_is_not_this_positions_crash(v31, clock):
    s = position(v31, clock)
    tick(v31, s, PRICE)                              # the high, pre-entry
    s.entry_at = time.time() + 0.001
    time.sleep(0.002)
    tick(v31, s, 9.69)
    assert s.in_position


def test_crash_line_is_floored_and_capped(v31, clock):
    calm = position(v31, clock, sym="CALM", rng=0.03)     # 0.3% -> 0.9% -> 3%
    wild = position(v31, clock, sym="WILD", rng=0.50)     # 5% -> 15% -> 10%
    assert v31.crash_pct(calm, PRICE) == pytest.approx(0.03)
    assert v31.crash_pct(wild, PRICE) == pytest.approx(0.10)


# ---- r26: adds off, price range checked at entry ------------------------------

def test_strong_speed_no_longer_adds(v31, clock, broker):
    s = position(v31, clock)
    s.entry_at = time.time() - 600
    feed_trades(v31, s.symbol, 9.0, 10.0)            # far above any baseline
    v31.st(s.symbol).speed_samples[:] = [0.0001]     # tiny baseline: add would fire
    run(v31.evaluate(s, PRICE))
    assert broker.buys(s.symbol) == []
