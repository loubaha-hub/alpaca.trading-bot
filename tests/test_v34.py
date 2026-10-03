"""
v34 (r31) - ONE position at a time, in the best-ranked name with a green-then-
red setup, starting at 10% of the account, on v31's machinery for the rest.

Tests marked "r30:" name what the old v34 did instead - run them against
r30.py (BOT_FILE=r30.py) to see each one fail.
"""

import time

import pytest

import bot
from helpers import breakout, feed_bars, feed_trades, hold, run

TRIGGER = 10.01
WORST = TRIGGER * 1.02
STARTER = int(10_000 / WORST)          # 10% of $100,000 at the worst fill: 979


@pytest.fixture
def v34(broker, data, clock):
    strat = bot.V34(broker, data)
    strat.day_start_equity = broker.eq
    return strat


def tick(strat, s, price):
    s.last_price = price
    strat.note_trade(s, price, 100)
    run(strat.evaluate(s, price))


def entered(strat, s):
    return s.in_position and len(strat.broker.buys(s.symbol)) > 0


# ---- picking the one name -----------------------------------------------------------

def test_a_ranked_setup_enters(v34, clock):
    s = breakout(v34, clock)
    tick(v34, s, TRIGGER)
    assert entered(v34, s)


def test_only_the_best_ranked_setup_is_bought(v34, clock):
    big = breakout(v34, clock, "BIG")
    feed_trades(v34, "BIG", 9.0, 10.0, size=5_000)        # far more dollars, faster
    small = breakout(v34, clock, "SMALL")
    tick(v34, small, TRIGGER)
    assert not entered(v34, small)
    tick(v34, big, TRIGGER)
    assert entered(v34, big)


def test_one_position_at_a_time(v34, clock):
    hold(v34, "AAA", 100, 5.0)
    s = breakout(v34, clock)
    tick(v34, s, TRIGGER)
    assert not entered(v34, s)


def test_no_setup_no_entry(v34, clock):
    s = breakout(v34, clock)
    tick(v34, s, TRIGGER - 0.001)
    assert not entered(v34, s)


def test_no_buying_once_the_day_is_closing(v34, clock):
    """r30: v34 bought until 8:00pm while the engine flattened from 7:00pm."""
    s = breakout(v34, clock)
    clock.set(19, 30)
    tick(v34, s, TRIGGER)
    assert not entered(v34, s)


def test_the_price_range_is_checked_at_the_buy(v34, clock):
    """r30: no $1-$20 check when buying."""
    s = breakout(v34, clock, red_open=20.20, red_low=19.90)
    tick(v34, s, 20.21)
    assert not entered(v34, s)


def test_a_thin_name_is_not_bought(v34, clock):
    s = breakout(v34, clock, bar_volume=20_000)
    tick(v34, s, TRIGGER)
    assert not entered(v34, s)


def test_a_name_traded_today_needs_a_new_day_high(v34, clock):
    """r30: a name could be bought again on every new setup - up to 18 round
    trips in one name in a day."""
    s = breakout(v34, clock)
    s.traded_today, s.day_high = True, 10.50
    tick(v34, s, TRIGGER)
    assert not entered(v34, s)
    tick(v34, s, 10.65)                                  # 10.50 + 1% margin
    assert entered(v34, s)


# ---- the size and the stop ---------------------------------------------------------

def test_the_starter_is_10_percent_at_the_worst_fill(v34, clock, broker):
    s = breakout(v34, clock)
    tick(v34, s, TRIGGER)
    assert [o[1] for o in broker.buys(s.symbol)] == [STARTER]


def test_a_small_float_buys_half(v34, clock, broker, monkeypatch):
    monkeypatch.setattr(bot, "FLOATS", {"ABCD": 2_000_000})
    s = breakout(v34, clock)
    tick(v34, s, TRIGGER)
    assert [o[1] for o in broker.buys(s.symbol)] == [STARTER // 2]


def test_the_entry_is_what_was_paid(v34, clock, broker, data):
    """r30: the triggering print was the entry."""
    s = breakout(v34, clock)
    data.quotes[(s.symbol, "ask")] = 10.16
    tick(v34, s, TRIGGER)
    assert s.entry == pytest.approx(broker.avg_cost(s.symbol))


def test_the_stop_is_never_closer_than_1_percent(v34, clock):
    """r30: the red bar's low, even a cent under the entry."""
    s = breakout(v34, clock, red_low=9.99)
    tick(v34, s, TRIGGER)
    assert s.stop <= s.entry * 0.99 + 1e-9


def test_the_ask_has_to_back_the_trigger(v34, clock, broker, data):
    """r30: no quote check at all."""
    s = breakout(v34, clock)
    data.quotes[(s.symbol, "ask")] = TRIGGER - 0.02
    tick(v34, s, TRIGGER)
    assert broker.orders == []


# ---- the daily halt -------------------------------------------------------------------

def test_v34_halts_at_10_percent_down(v34):
    """r30: no halt unless V34_HALT_PCT was set - it lost 35% on 2026-10-02."""
    assert v34.halt_threshold() == pytest.approx(0.10)


def test_the_environment_can_set_the_halt(v34, monkeypatch):
    monkeypatch.setenv("V34_HALT_PCT", "5")
    assert v34.halt_threshold() == pytest.approx(0.05)


# ---- exits: v31's by default ------------------------------------------------------------

def position(strat, clock, rng=0.10):
    now = clock.now.astimezone(bot.timezone.utc)
    half = rng / 2
    feed_bars(strat, "ABCD", now, [(10.0, 10.0 + half, 10.0 - half, 10.0, 40_000)] * 10)
    s = hold(strat, "ABCD", 1000, 10.0, stop=5.0)
    s.entry_at = time.time() - 120
    return s


def test_v31s_crash_guard_runs_for_v34(v34, clock, broker):
    s = position(v34, clock)                             # crash line 3% in 30s
    tick(v34, s, 10.0)
    tick(v34, s, 9.65)
    assert broker.held["ABCD"] == 0


def test_a_3_percent_dip_on_a_wild_name_is_held(v34, clock, broker):
    """r30's fixed 4% flush is gone: on a name with a 5% typical range the
    flush sits 12% under the high."""
    s = position(v34, clock, rng=0.50)
    for p in (10.4, 10.1):
        tick(v34, s, p)
    assert broker.held["ABCD"] == 1000


# ---- v34's own ladder (V34_V31_EXITS = False) -------------------------------------------

@pytest.fixture
def own_ladder(monkeypatch):
    monkeypatch.setattr(bot, "V34_V31_EXITS", False)


@pytest.mark.usefixtures("own_ladder")
def test_own_ladder_flushes_4_percent_under_the_high_before_arming(v34, clock, broker):
    s = position(v34, clock)
    tick(v34, s, 10.4)
    tick(v34, s, 9.98)                                   # 4.0% under 10.40
    assert broker.held["ABCD"] == 0


@pytest.mark.usefixtures("own_ladder")
def test_own_ladder_trail_runs_once_armed(v34, clock, broker):
    """r30: the 4% flush stayed on after arming and always fired before the
    8% trail - the trail never ran."""
    s = position(v34, clock)
    tick(v34, s, 12.6)                                   # +26%: armed, trail 11.59
    tick(v34, s, 12.0)                                   # 4.8% under the high
    assert broker.held["ABCD"] == 1000
    tick(v34, s, 11.5)
    assert broker.held["ABCD"] == 0


@pytest.mark.usefixtures("own_ladder")
def test_own_ladder_add_is_confirmed_against_the_entry(v34, clock, broker, monkeypatch):
    """r30: confirmed against the newest red bar's open, and the entry was
    never moved to the average cost."""
    monkeypatch.setattr(bot, "V34_ADDS", True)
    s = position(v34, clock)
    tick(v34, s, 10.25)                                  # +2.5% on the entry
    assert broker.held["ABCD"] > 1000
    assert s.entry == pytest.approx(broker.avg_cost("ABCD"))
    assert broker.held["ABCD"] * 10.25 <= 2 * 1000 * 10.25 + 1   # doubled, no more


@pytest.mark.usefixtures("own_ladder")
def test_own_ladder_adds_are_off_by_default(v34, clock, broker):
    s = position(v34, clock)
    tick(v34, s, 10.25)
    assert broker.held["ABCD"] == 1000
