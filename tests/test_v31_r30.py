"""
r30 - three ideas built as switches and left OFF, because the five-day replay
said no: a time-based speed for entries, buying a spiked runner's break of
the day high, and jumping off near the day high. These tests keep each one
working for when it is tried live.
"""

import time
from datetime import timedelta

import pytest

import bot
from helpers import breakout, feed_bars, hold, raw_bar, run

TRIGGER = 10.01


def tick(strat, s, price):
    s.last_price = price
    strat.note_trade(s, price, 100)
    run(strat.evaluate(s, price))


def entered(strat, s):
    return s.in_position and len(strat.broker.buys(s.symbol)) > 0


def bar_ago(strat, clock, minutes, close, volume=40_000, symbol="ABCD", high=None):
    now = clock.now.astimezone(bot.timezone.utc)
    strat.offer_bar(raw_bar(symbol, now - timedelta(minutes=minutes),
                            close, high or close, close, close, volume))


def test_all_three_ship_off():
    assert bot.V31_SPEED_BY_TIME is False
    assert bot.V31_SPIKE_HOD_OK is False
    assert bot.V31_RES_EXIT is False


# ---- speed by time ----------------------------------------------------------------

@pytest.fixture
def speed_by_time(monkeypatch):
    monkeypatch.setattr(bot, "V31_SPEED_BY_TIME", True)


@pytest.mark.usefixtures("speed_by_time")
@pytest.mark.parametrize("close_6_min_ago,allowed", [(10.20, False), (9.90, True)])
def test_entry_needs_the_price_above_5_minutes_ago(v31, clock, close_6_min_ago, allowed):
    bar_ago(v31, clock, 6, close_6_min_ago)          # closed 5 minutes ago
    s = breakout(v31, clock)
    tick(v31, s, TRIGGER)
    assert entered(v31, s) is allowed


@pytest.mark.usefixtures("speed_by_time")
def test_a_minimum_move_can_be_asked(v31, clock, monkeypatch):
    monkeypatch.setattr(bot, "V31_SPEED_MIN_MOVE", 0.02)
    bar_ago(v31, clock, 6, 9.90)                     # +1.1%: not enough
    s = breakout(v31, clock)
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)


@pytest.mark.usefixtures("speed_by_time")
def test_unknown_5_minute_price_falls_back_to_the_print_speed(v31, clock):
    s = breakout(v31, clock)                         # bars only 3 minutes back
    tick(v31, s, TRIGGER)
    assert entered(v31, s)


# ---- a spiked runner's break of the day high ---------------------------------------

def spiked_runner(strat, clock):
    """Spiked 8.00 -> 9.40 at 5am, never traded, last bar green (no setup),
    highest closed bar 10.50."""
    bar_ago(strat, clock, 300, 8.00)
    bar_ago(strat, clock, 285, 9.40)
    s = breakout(strat, clock)
    now = clock.now.astimezone(bot.timezone.utc)
    strat.offer_bar(raw_bar("ABCD", now, 10.00, 10.50, 9.95, 10.35, 40_000))
    s.hod_closed = 10.50
    return s


def test_a_spiked_untraded_name_stays_off_limits_by_default(v31, clock):
    s = spiked_runner(v31, clock)
    tick(v31, s, 10.56)
    assert not entered(v31, s)


def test_with_the_switch_its_day_high_break_is_bought(v31, clock, monkeypatch):
    monkeypatch.setattr(bot, "V31_SPIKE_HOD_OK", True)
    s = spiked_runner(v31, clock)
    tick(v31, s, 10.56)
    assert entered(v31, s) and s.entry_kind == "hod"


def test_with_the_switch_a_pullback_setup_is_still_refused(v31, clock, monkeypatch):
    monkeypatch.setattr(bot, "V31_SPIKE_HOD_OK", True)
    bar_ago(v31, clock, 300, 8.00)
    bar_ago(v31, clock, 285, 9.40)
    s = breakout(v31, clock)
    s.hod_closed = 12.00                             # far above: no break
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)


def test_the_day_high_from_before_subscribing_counts(v31, clock, data):
    now = clock.now.astimezone(bot.timezone.utc)
    data.history["ABCD"] = [(now - timedelta(minutes=50), 10.00, 50_000, 11.80)]
    s = breakout(v31, clock)
    run(v31.recent_bars(s))
    assert s.hod_closed == 11.80


# ---- jump off near the day high ---------------------------------------------------

@pytest.fixture
def res_on(monkeypatch):
    monkeypatch.setattr(bot, "V31_RES_EXIT", True)
    monkeypatch.setattr(bot, "V31_TRIM_FRACTION", 0.0)     # this rule alone


def near_resistance(strat, clock):
    """Entered at 10.00 under a day high of 11.00; typical range 0.10."""
    now = clock.now.astimezone(bot.timezone.utc)
    feed_bars(strat, "ABCD", now, [(10.0, 10.05, 9.95, 10.0, 40_000)] * 10)
    s = hold(strat, "ABCD", 1000, 10.0, stop=5.0)
    s.entry_at = time.time() - 120
    s.res_level = 11.00
    return s


@pytest.mark.usefixtures("res_on")
def test_turning_down_just_under_the_high_sells(v31, clock, broker):
    s = near_resistance(v31, clock)
    for p in (10.50, 10.92, 10.85):                  # within 1% of 11.00, then -0.07
        tick(v31, s, p)
    assert broker.held["ABCD"] == 1000
    tick(v31, s, 10.81)                              # past 10.92 - 1 ABR (0.10)
    assert broker.held["ABCD"] == 0


@pytest.mark.usefixtures("res_on")
def test_turning_down_far_below_the_high_is_left_to_the_other_rules(v31, clock, broker):
    s = near_resistance(v31, clock)
    for p in (10.50, 10.38):
        tick(v31, s, p)
    assert broker.held["ABCD"] == 1000


@pytest.mark.usefixtures("res_on")
def test_once_the_high_is_cleared_the_rule_stands_down(v31, clock, broker):
    s = near_resistance(v31, clock)
    for p in (10.60, 10.92, 11.12, 11.00):           # cleared by 1%, back to 11.00
        tick(v31, s, p)
    assert s.res_done and broker.held["ABCD"] == 1000


@pytest.mark.usefixtures("res_on")
def test_it_can_sell_half_instead(v31, clock, broker, monkeypatch):
    monkeypatch.setattr(bot, "V31_RES_FRACTION", 0.5)
    s = near_resistance(v31, clock)
    for p in (10.50, 10.92, 10.81):
        tick(v31, s, p)
    assert broker.held["ABCD"] == 500


def test_a_buy_under_the_day_high_remembers_it(v31, clock):
    s = breakout(v31, clock)
    s.hod_closed = 11.00
    tick(v31, s, TRIGGER)
    assert entered(v31, s) and s.res_level == 11.00
