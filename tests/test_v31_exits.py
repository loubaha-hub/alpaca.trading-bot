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


# ---- r27: a longer leash for new-high re-entries (neutral by default) ---------

def test_runner_crash_line_is_wider_for_a_reentry(v31, clock, monkeypatch):
    monkeypatch.setattr(bot, "V31_RUNNER_CRASH_MULT", 2.0, raising=False)
    s = position(v31, clock)                         # crash at 3% normally
    s.entry_kind = "hod"
    tick(v31, s, PRICE)
    tick(v31, s, 9.69)                               # -3.1%: inside the 6% line
    assert s.in_position
    s2 = position(v31, clock, sym="SETUP")
    s2.entry_kind = "setup"                          # same drop, ordinary leash
    tick(v31, s2, PRICE)
    tick(v31, s2, 9.69)
    assert not s2.in_position


def test_runner_leash_settings_are_neutral_by_default():
    assert bot.V31_RUNNER_CRASH_MULT == 1.0
    assert bot.V31_RUNNER_TRAIL_MULT == 1.0
    assert bot.V31_RUNNER_RISK == bot.V31_RISK_PER_TRADE
    assert bot.V31_RUNNER_FADE is True


# ---- r28: protecting a gain - sell half at +20% ---------------------------------

@pytest.fixture
def trim_on(monkeypatch):
    monkeypatch.setattr(bot, "V31_TRIM_FRACTION", 0.5)


@pytest.fixture
def keep_on(monkeypatch):
    monkeypatch.setattr(bot, "V31_KEEP_GAIN", 0.5)
    monkeypatch.setattr(bot, "V31_TRIM_FRACTION", 0.0)   # this rule alone


def test_shipped_settings_sell_half_at_20_percent_and_keep_no_gain_line(v31, clock, broker):
    assert bot.V31_TRIM_FRACTION == 0.5 and bot.V31_TRIM_AT == 0.20
    assert bot.V31_KEEP_GAIN == 0.0
    s = position(v31, clock, rng=0.50)
    for p in (12.0, 11.5, 11.0):                         # no keep-gain exit at 11.00
        tick(v31, s, p)
    assert broker.held["ABCD"] == 500


@pytest.mark.usefixtures("keep_on")
def test_keep_gain_alone(v31, clock, broker, monkeypatch):
    monkeypatch.setattr(bot, "V31_TRIM_FRACTION", 0.0)
    s = position(v31, clock, rng=0.50)
    for p in (12.0, 11.5, 11.0):
        tick(v31, s, p)
    assert broker.held["ABCD"] == 0


@pytest.mark.usefixtures("trim_on")
def test_first_print_20_percent_up_sells_half(v31, clock, broker):
    s = position(v31, clock)
    tick(v31, s, 12.0)
    assert broker.held["ABCD"] == 500 and s.shares == 500
    assert v31.closed_today[-1][3] == 500                # booked as a trim
    assert s.entry == PRICE                              # the rest keeps its entry


@pytest.mark.usefixtures("trim_on")
def test_nothing_is_sold_short_of_20_percent(v31, clock, broker):
    s = position(v31, clock)
    tick(v31, s, 11.99)
    assert broker.held["ABCD"] == 1000


@pytest.mark.usefixtures("trim_on")
def test_the_trim_happens_once(v31, clock, broker):
    s = position(v31, clock)
    for p in (12.0, 12.5, 13.0):
        tick(v31, s, p)
    assert broker.held["ABCD"] == 500


@pytest.mark.usefixtures("trim_on")
def test_after_the_trim_the_rest_cannot_close_below_the_entry(v31, clock):
    s = position(v31, clock)
    tick(v31, s, 12.0)
    assert s.stop >= PRICE and s.trail_stop >= PRICE


@pytest.mark.usefixtures("trim_on")
def test_stop_to_entry_can_be_switched_off(v31, clock, monkeypatch):
    monkeypatch.setattr(bot, "V31_TRIM_STOP_TO_ENTRY", False)
    s = position(v31, clock)
    tick(v31, s, 12.0)
    assert s.stop < PRICE


@pytest.mark.usefixtures("trim_on")
def test_a_new_position_can_trim_again(v31, clock, broker):
    s = position(v31, clock)
    tick(v31, s, 12.0)
    run(v31.exit(s, "test"))
    assert not s.trimmed                                 # cleared with the position


# ---- r28: protecting a gain - keep half of it ------------------------------------
# A wild name (5% typical range), so the trail and flush sit further away than
# half of a 20% gain and only this rule can fire.

@pytest.mark.usefixtures("keep_on")
def test_falling_back_to_half_the_best_gain_closes_it_all(v31, clock, broker):
    s = position(v31, clock, rng=0.50)
    for p in (12.0, 11.5, 11.01):
        tick(v31, s, p)
    assert broker.held["ABCD"] == 1000                   # still above 11.00
    tick(v31, s, 11.0)                                   # 10 + half of 2.00
    assert broker.held["ABCD"] == 0
    assert v31.closed_today[-1][5] == "keep-gain"


@pytest.mark.usefixtures("keep_on")
def test_keep_gain_arms_only_after_20_percent(v31, clock, broker):
    s = position(v31, clock, rng=0.50)
    for p in (11.9, 11.2, 10.95):                        # best gain 19%
        tick(v31, s, p)
    assert broker.held["ABCD"] == 1000

