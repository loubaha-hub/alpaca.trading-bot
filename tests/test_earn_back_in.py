"""
2026-10-05, SAIQ: the no-chase rule shut it out at 4:18am and it ran from ~7 to
18.37. These rules, all shipped OFF, let a shut-out name back in only by
proving it is running, not fading:

  * V31_EARN_LEADERS - a top leader by dollar volume breaking its day high on
    a minute with V31_EARN_VOL_MULT x the pause's volume, at a tight spread.
    For v31, v34, and v35's re-entry after a losing trade (V35_REENTRY_EARN).
  * V31_LEADER_WINDOW_MIN - leaders ranked on recent volume, not the whole day.
  * V35_IGNITION_FIRST_BARS / _LEADERS - v35's no-pullback first entry, held
    to a name's first minutes and to the top leader.
"""

from datetime import timedelta

import pytest

import bot
from helpers import breakout, raw_bar, run
from test_v35 import closed, climb


def tick(strat, s, price):
    s.last_price = price
    strat.note_trade(s, price, 100)
    run(strat.evaluate(s, price))
    s.day_high = max(s.day_high, price)


def entered(strat, s):
    return s.in_position and len(strat.broker.buys(s.symbol)) > 0


def bar_ago(strat, clock, minutes, close, volume=40_000, symbol="ABCD"):
    now = clock.now.astimezone(bot.timezone.utc)
    strat.offer_bar(raw_bar(symbol, now - timedelta(minutes=minutes),
                            close, close, close, close, volume))


def test_all_ship_off():
    assert bot.V31_EARN_LEADERS == 0
    assert bot.V31_LEADER_WINDOW_MIN == 0
    assert bot.V35_REENTRY_EARN is False
    assert bot.V35_IGNITION_PCT == 0
    assert bot.V35_IGNITION_FIRST_BARS == 0 and bot.V35_IGNITION_LEADERS == 0


@pytest.fixture
def tight(data):
    data.quotes[("ABCD", "bid")] = 10.55
    data.quotes[("ABCD", "ask")] = 10.56


@pytest.fixture
def earn_on(monkeypatch, tight):
    monkeypatch.setattr(bot, "V31_EARN_LEADERS", 1)
    monkeypatch.setattr(bot, "V31_VOL_RISING_MIN", 0.0)     # one rule at a time


def spiked_leader(strat, clock, *, last_volume=100_000, spike_now=False):
    """Spiked 8.00 -> 9.40 at 5am - shut out for the rest of the day - then a
    pause of 40,000-share minutes and a green minute to a 10.50 day high on
    `last_volume` shares. spike_now: also 9.00 sixteen minutes ago, so 10.56 is
    "up 15% in 15 minutes right now" (SAIQ's 4:20 and 4:30 breakouts)."""
    bar_ago(strat, clock, 300, 8.00)
    bar_ago(strat, clock, 285, 9.40)
    if spike_now:
        bar_ago(strat, clock, 16, 9.00)
    s = breakout(strat, clock)
    now = clock.now.astimezone(bot.timezone.utc)
    strat.offer_bar(raw_bar("ABCD", now, 10.00, 10.50, 9.95, 10.35, last_volume))
    s.hod_closed = 10.50
    return s


# ---- v31 ------------------------------------------------------------------------------

def test_off_a_shut_out_leader_stays_out(v31, clock, tight):
    s = spiked_leader(v31, clock)
    tick(v31, s, 10.56)
    assert not entered(v31, s)


@pytest.mark.usefixtures("earn_on")
def test_a_leader_through_its_high_on_volume_earns_its_way_back(v31, clock):
    s = spiked_leader(v31, clock)
    tick(v31, s, 10.56)
    assert entered(v31, s) and s.entry_kind == "hod"


@pytest.mark.usefixtures("earn_on")
def test_it_passes_the_up_15_percent_right_now_rule_too(v31, clock):
    s = spiked_leader(v31, clock, spike_now=True)
    tick(v31, s, 10.56)
    assert entered(v31, s)


def test_without_it_the_right_now_rule_still_stops_that_break(v31, clock, tight,
                                                              monkeypatch):
    monkeypatch.setattr(bot, "V31_SPIKE_HOD_OK", True)   # r30's switch alone
    s = spiked_leader(v31, clock, spike_now=True)
    tick(v31, s, 10.56)
    assert not entered(v31, s)


@pytest.mark.usefixtures("earn_on")
def test_a_break_on_dried_up_volume_is_a_fade_not_a_run(v31, clock):
    s = spiked_leader(v31, clock, last_volume=40_000)
    tick(v31, s, 10.56)
    assert not entered(v31, s)


@pytest.mark.usefixtures("earn_on")
def test_a_wide_spread_keeps_it_out(v31, clock, data):
    data.quotes[("ABCD", "bid")] = 10.80
    data.quotes[("ABCD", "ask")] = 11.60                 # SAIQ's book after its top
    s = spiked_leader(v31, clock)
    tick(v31, s, 10.56)
    assert not entered(v31, s)


@pytest.mark.usefixtures("earn_on")
def test_under_the_day_high_it_stays_out(v31, clock):
    s = spiked_leader(v31, clock)
    tick(v31, s, 10.54)                                  # 10.50 + 5c not reached
    assert not entered(v31, s)


@pytest.mark.usefixtures("earn_on")
def test_only_the_top_leader_may_earn_it(v31, clock):
    bar_ago(v31, clock, 3, 20.00, volume=900_000, symbol="BIGG")
    v31.qualified.add("BIGG")
    s = spiked_leader(v31, clock)
    assert v31.leader_rank("ABCD") == 2
    tick(v31, s, 10.56)
    assert not entered(v31, s)


# ---- v34 ------------------------------------------------------------------------------

@pytest.fixture
def v34(broker, data, clock):
    strat = bot.V34(broker, data)
    strat.day_start_equity = broker.eq
    return strat


def test_v34_off_a_shut_out_leader_stays_out(v34, clock, tight):
    s = spiked_leader(v34, clock)
    tick(v34, s, 10.56)
    assert not entered(v34, s)


@pytest.mark.usefixtures("earn_on")
def test_v34_a_leader_earns_its_way_back_on_the_breakout(v34, clock):
    s = spiked_leader(v34, clock)
    tick(v34, s, 10.56)
    assert entered(v34, s) and s.entry_kind == "hod"


@pytest.mark.usefixtures("earn_on")
def test_v34_on_dried_up_volume_it_stays_out(v34, clock):
    s = spiked_leader(v34, clock, last_volume=40_000)
    tick(v34, s, 10.56)
    assert not entered(v34, s)


# ---- v35: a loser comes back only by earning it -----------------------------------------

@pytest.fixture
def v35(broker, data, clock, monkeypatch):
    monkeypatch.setattr(bot, "V31_VOL_RISING_MIN", 0.0)
    strat = bot.V35(broker, data)
    strat.day_start_equity = broker.eq
    return strat


def heavy_minute_then_break(strat, clock, data, s, volume):
    """A minute of `volume` shares that stays under the day high, then a print
    6c over the high - with a tight quote there."""
    now = clock.now.astimezone(bot.timezone.utc) + timedelta(minutes=1)
    h = s.hod_closed
    strat.offer_bar(raw_bar("ABCD", now, h - 0.10, h, h - 0.15, h - 0.02, volume))
    price = round(max(s.hod_closed, s.v35_peak) + 0.06, 2)   # a cent past the 5c line
    data.quotes[("ABCD", "bid")] = price
    data.quotes[("ABCD", "ask")] = round(price * 1.002, 2)
    tick(strat, s, price)


def test_v35_off_a_loser_is_not_bought_back(v35, clock, data, monkeypatch):
    monkeypatch.setattr(bot, "V31_EARN_LEADERS", 1)
    s = closed(v35, clock, monkeypatch, win=False)
    heavy_minute_then_break(v35, clock, data, s, 400_000)
    assert len(v35.broker.buys("ABCD")) == 1


def test_v35_a_loser_earns_its_way_back_on_volume(v35, clock, data, monkeypatch):
    monkeypatch.setattr(bot, "V31_EARN_LEADERS", 1)
    monkeypatch.setattr(bot, "V35_REENTRY_EARN", True)
    s = closed(v35, clock, monkeypatch, win=False)
    heavy_minute_then_break(v35, clock, data, s, 400_000)
    assert len(v35.broker.buys("ABCD")) == 2


def test_v35_a_loser_on_quiet_volume_stays_out(v35, clock, data, monkeypatch):
    monkeypatch.setattr(bot, "V31_EARN_LEADERS", 1)
    monkeypatch.setattr(bot, "V35_REENTRY_EARN", True)
    s = closed(v35, clock, monkeypatch, win=False)
    heavy_minute_then_break(v35, clock, data, s, 40_000)
    assert len(v35.broker.buys("ABCD")) == 1


# ---- leaders by what is moving now ------------------------------------------------------

def test_leaders_by_the_recent_window(v31, clock, monkeypatch):
    """OLDD traded $8M two hours ago and nothing since; NEWW $2M in the last
    half hour."""
    bar_ago(v31, clock, 120, 10.00, volume=800_000, symbol="OLDD")
    bar_ago(v31, clock, 20, 10.00, volume=200_000, symbol="NEWW")
    v31.qualified.update({"OLDD", "NEWW"})
    assert v31.leader_rank("OLDD") == 1                  # the whole day
    monkeypatch.setattr(bot, "V31_LEADER_WINDOW_MIN", 45)
    v31.leader_cache = (-1, {})
    assert v31.leader_rank("NEWW") == 1


# ---- v35's ignition, held to the first minutes and the top leader -----------------------

@pytest.fixture
def ignition_on(monkeypatch):
    monkeypatch.setattr(bot, "V35_IGNITION_PCT", 0.10)


def first_candle(strat, clock, symbol="ABCD", pct=0.40, volume=150_000, minutes_before=0):
    """`minutes_before` quiet candles, then a candle up `pct` on heavy volume."""
    for m in range(minutes_before, 0, -1):
        bar_ago(strat, clock, m + 1, 3.49, symbol=symbol)
    now = clock.now.astimezone(bot.timezone.utc)
    strat.offer_bar(raw_bar(symbol, now, 3.49, 3.49 * (1 + pct) + 0.05, 3.49,
                            round(3.49 * (1 + pct), 2), volume))
    strat.qualified.add(symbol)
    return strat.st(symbol)


@pytest.mark.usefixtures("ignition_on")
def test_ignition_fires_on_a_first_candle(v35, clock):
    s = first_candle(v35, clock)
    assert v35.ignition(s) is not None


@pytest.mark.usefixtures("ignition_on")
def test_ignition_held_to_the_first_minutes(v35, clock, monkeypatch):
    monkeypatch.setattr(bot, "V35_IGNITION_FIRST_BARS", 3)
    early = first_candle(v35, clock, symbol="EARL", minutes_before=1)
    late = first_candle(v35, clock, symbol="LATE", minutes_before=6)
    assert v35.ignition(early) is not None
    assert v35.ignition(late) is None


@pytest.mark.usefixtures("ignition_on")
def test_ignition_held_to_the_top_leader(v35, clock, monkeypatch):
    monkeypatch.setattr(bot, "V35_IGNITION_LEADERS", 1)
    bar_ago(v35, clock, 2, 15.00, volume=900_000, symbol="BIGG")
    v35.qualified.add("BIGG")
    s = first_candle(v35, clock)
    assert v35.leader_rank("ABCD") == 2
    assert v35.ignition(s) is None


def test_climb_helper_is_untouched(v35, clock):
    """Importing test_v35's helpers must not change them."""
    s = climb(v35, clock)
    assert s.bars


# ---- one earned buy per new high (MI, 2026-10-05: three buys in 17 seconds) ---------------

@pytest.mark.usefixtures("earn_on")
def test_no_second_earned_buy_on_the_same_high(v31, clock):
    s = spiked_leader(v31, clock)
    tick(v31, s, 10.56)
    assert entered(v31, s)
    tick(v31, s, s.stop - 0.01)                          # out
    assert not s.in_position
    tick(v31, s, 10.60)                                  # over the same 10.50 high again
    assert len(v31.broker.buys("ABCD")) == 1


@pytest.mark.usefixtures("earn_on")
def test_a_higher_closed_high_earns_the_next_one(v31, clock, data):
    s = spiked_leader(v31, clock)
    tick(v31, s, 10.56)
    tick(v31, s, s.stop - 0.01)
    clock.now += timedelta(minutes=1)
    now = clock.now.astimezone(bot.timezone.utc)
    v31.offer_bar(raw_bar("ABCD", now, 10.40, 10.90, 10.35, 10.80, 300_000))
    assert s.hod_closed == pytest.approx(10.90)
    data.quotes[("ABCD", "bid")] = 10.96
    data.quotes[("ABCD", "ask")] = 10.97
    tick(v31, s, 10.96)
    assert len(v31.broker.buys("ABCD")) == 2


@pytest.mark.usefixtures("earn_on")
def test_a_spread_that_keeps_a_runner_out_is_logged(v31, clock, data, caplog):
    data.quotes[("ABCD", "bid")] = 10.50
    data.quotes[("ABCD", "ask")] = 10.80                 # 2.9%
    s = spiked_leader(v31, clock)
    with caplog.at_level("INFO"):
        tick(v31, s, 10.56)
    assert not entered(v31, s)
    assert any("but the spread is 2.9%" in r.getMessage() for r in caplog.records)
