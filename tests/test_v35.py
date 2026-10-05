"""
v35 (r34) - the leaders' pullback. Only the day's top names by dollar volume;
buy 1c over the last red candle's open after a green one; above VWAP and the
9 EMA, 9 over 20, MACD over zero; out under the reds' low or on a close under
the 9 EMA while the trade is young; a long leash once it is up 10%; one add
at +5% with the stop to the new average.

The rising-volume rule is v31's and has its own tests; it is off here so each
test changes one thing.
"""

import time

import pytest

import bot
from helpers import feed_bars, hold, run

GREEN_TOP = 10.40
RED_OPEN = 10.20                     # the last red candle's open
RED_LOW = 10.05
TRIGGER = RED_OPEN + bot.V31_ENTRY_TICK


@pytest.fixture
def v35(broker, data, clock, monkeypatch):
    monkeypatch.setattr(bot, "V31_VOL_RISING_MIN", 0.0)
    strat = bot.V35(broker, data)
    strat.day_start_equity = broker.eq
    return strat


def climb(strat, clock, symbol="ABCD", *, volume=40_000, last_red=(RED_OPEN, RED_LOW)):
    """Twenty rising candles, a green one to GREEN_TOP, then two reds - the
    pullback. EMA9 over EMA20, price over VWAP, MACD over zero."""
    now = clock.now.astimezone(bot.timezone.utc)
    rows = []
    for i in range(20):
        o = 8.00 + 0.10 * i
        rows.append((o, o + 0.12, o - 0.02, o + 0.10, volume))
    rows.append((10.00, GREEN_TOP + 0.05, 9.98, GREEN_TOP, volume))           # green
    rows.append((GREEN_TOP, GREEN_TOP + 0.02, 10.15, 10.25, volume))         # red
    o, low = last_red
    rows.append((o, o + 0.02, low, low + 0.05, volume))                     # red
    feed_bars(strat, symbol, now, rows)
    strat.qualified.add(symbol)
    return strat.st(symbol)


def tick(strat, s, price):
    s.last_price = price
    strat.note_trade(s, price, 100)
    run(strat.evaluate(s, price))
    s.day_high = max(s.day_high, price)           # what tick_worker does after


def entered(strat, s):
    return s.in_position and len(strat.broker.buys(s.symbol)) > 0


# ---- the entry -------------------------------------------------------------------

def test_the_pullback_is_found(v35, clock):
    s = climb(v35, clock)
    assert v35.pullback(s) == (pytest.approx(TRIGGER), pytest.approx(RED_LOW))


def test_buys_1c_over_the_last_red_candles_open(v35, clock):
    s = climb(v35, clock)
    tick(v35, s, TRIGGER - 0.01)
    assert not entered(v35, s)
    tick(v35, s, TRIGGER)
    assert entered(v35, s)


def test_the_stop_is_under_the_reds_low(v35, clock):
    s = climb(v35, clock)
    tick(v35, s, TRIGGER)
    assert s.stop <= RED_LOW + 1e-9
    assert s.stop <= s.entry * 0.99 + 1e-9           # and never nearer than 1%


def test_no_pullback_no_buy(v35, clock):
    s = climb(v35, clock, last_red=(10.25, 10.20))
    s.bars[-1].c = s.bars[-1].o + 0.05                 # the last candle closed green
    tick(v35, s, 10.50)
    assert not entered(v35, s)


def test_only_the_days_leaders(v35, clock):
    for sym in ("BIG1", "BIG2"):
        climb(v35, clock, sym, volume=400_000)
    s = climb(v35, clock, "ABCD")
    assert v35.leader_rank("ABCD") == 3
    tick(v35, s, TRIGGER)
    assert not entered(v35, s)


def test_under_vwap_no_buy(v35, clock):
    s = climb(v35, clock)
    s.vwap_pv, s.vwap_v = 11.0 * 1_000_000, 1_000_000  # VWAP 11.00, over the price
    tick(v35, s, TRIGGER)
    assert not entered(v35, s)


def test_ema9_under_ema20_no_buy(v35, clock):
    s = climb(v35, clock)
    s.ema9, s.ema20 = 9.0, 9.5
    tick(v35, s, TRIGGER)
    assert not entered(v35, s)


def test_macd_under_zero_no_buy(v35, clock):
    s = climb(v35, clock)
    s.ema12, s.ema26 = 9.0, 9.5
    tick(v35, s, TRIGGER)
    assert not entered(v35, s)


def test_not_enough_room_under_the_prior_days_high(v35, clock):
    """The prior day's high has to be at least 2x the risk above the trigger."""
    s = climb(v35, clock)
    risk = TRIGGER - min(RED_LOW, TRIGGER * 0.99)
    s.prev_high = TRIGGER + 1.5 * risk
    tick(v35, s, TRIGGER)
    assert not entered(v35, s)


def test_room_enough_buys(v35, clock):
    s = climb(v35, clock)
    risk = TRIGGER - min(RED_LOW, TRIGGER * 0.99)
    s.prev_high = TRIGGER + 2.5 * risk
    tick(v35, s, TRIGGER)
    assert entered(v35, s)


def test_a_big_float_is_not_bought(v35, clock, monkeypatch):
    monkeypatch.setattr(bot, "FLOATS", {"ABCD": 50_000_000})
    s = climb(v35, clock)
    tick(v35, s, TRIGGER)
    assert not entered(v35, s)


def test_a_wide_spread_is_not_bought(v35, clock, data):
    s = climb(v35, clock)
    data.quotes[("ABCD", "bid")] = 10.00
    data.quotes[("ABCD", "ask")] = 10.25                 # 2.5% wide
    tick(v35, s, TRIGGER)
    assert not entered(v35, s)


def test_a_name_traded_today_is_not_bought_on_a_pullback(v35, clock):
    s = climb(v35, clock)
    s.traded_today = True
    tick(v35, s, TRIGGER)
    assert not entered(v35, s)


def test_no_buying_once_the_day_is_closing(v35, clock):
    s = climb(v35, clock)
    clock.set(19, 30)
    tick(v35, s, TRIGGER)
    assert not entered(v35, s)


# ---- the exits -------------------------------------------------------------------

def bought(strat, clock):
    s = climb(strat, clock)
    tick(strat, s, TRIGGER)
    assert entered(strat, s)
    s.entry_at = clock.now.timestamp() - 30
    return s


def test_out_under_the_reds_low(v35, clock):
    s = bought(v35, clock)
    tick(v35, s, s.stop - 0.01)
    assert not s.in_position
    assert v35.closed_today[-1][-1] == "stop"


def test_a_young_trade_is_out_on_a_close_under_ema9(v35, clock):
    s = bought(v35, clock)
    now = clock.now.astimezone(bot.timezone.utc)
    close = s.ema9 - 0.05
    feed_bars(v35, "ABCD", now + bot.timedelta(minutes=1),
              [(10.22, 10.24, close - 0.01, close, 40_000)])
    assert s.ema_break
    tick(v35, s, max(close, s.stop + 0.01))
    assert not s.in_position
    assert v35.closed_today[-1][-1] == "under-ema9"


def test_up_10_percent_the_long_leash_ignores_ema9(v35, clock):
    s = bought(v35, clock)
    tick(v35, s, s.entry * 1.11)
    assert s.armed
    s.ema_break = True
    tick(v35, s, s.entry * 1.10)
    assert s.in_position


def test_the_long_leash_trails_the_high(v35, clock):
    s = bought(v35, clock)
    tick(v35, s, s.entry * 1.20)
    trail = s.trail_stop
    assert trail > s.entry
    tick(v35, s, trail - 0.01)
    assert not s.in_position
    assert v35.closed_today[-1][-1] == "trail"


def test_one_add_at_plus_5_percent_on_a_new_high(v35, clock, broker):
    s = bought(v35, clock)
    first = s.shares
    tick(v35, s, round(s.entry * 1.06, 2))
    assert s.v35_added
    assert len(broker.buys("ABCD")) == 2
    assert s.shares > first
    assert s.stop == pytest.approx(s.entry)             # the new average


def test_only_one_add(v35, clock, broker):
    s = bought(v35, clock)
    tick(v35, s, round(s.entry * 1.06, 2))
    tick(v35, s, round(s.entry * 1.09, 2))
    assert len(broker.buys("ABCD")) == 2


def test_the_add_never_passes_40_percent(v35, clock, broker):
    s = bought(v35, clock)
    price = round(s.entry * 1.06, 2)
    tick(v35, s, price)
    assert s.shares * price <= 0.40 * broker.eq + price


# ---- re-entry on a new high ------------------------------------------------------

def closed(strat, clock, monkeypatch, win=True):
    """One trade in and out - a winner out on the trail, or a loser out on the
    stop. No add, so the sizes stay simple."""
    monkeypatch.setattr(bot, "V35_ADD_AT", 0.0)
    s = bought(strat, clock)
    if win:
        tick(strat, s, s.entry * 1.20)
        tick(strat, s, s.trail_stop - 0.01)
    else:
        tick(strat, s, s.stop - 0.01)
    assert not s.in_position
    assert (strat.closed_today[-1][4] > 0) == win
    return s


def test_back_in_5c_over_the_high_after_a_winner(v35, clock, monkeypatch):
    s = closed(v35, clock, monkeypatch)
    high = max(s.hod_closed, s.v35_peak)
    tick(v35, s, round(high + 0.04, 2))
    assert len(v35.broker.buys("ABCD")) == 1
    tick(v35, s, round(high + 0.05, 2))
    assert entered(v35, s) and len(v35.broker.buys("ABCD")) == 2


def test_the_reentry_stop_is_at_the_broken_high(v35, clock, monkeypatch):
    s = closed(v35, clock, monkeypatch)
    high = max(s.hod_closed, s.v35_peak)
    tick(v35, s, round(high + 0.05, 2))
    assert s.stop == pytest.approx(min(high, s.entry * 0.99))


def test_no_reentry_under_the_last_trades_peak(v35, clock, monkeypatch):
    """The peak printed inside the minute is not in a closed candle yet - the
    re-entry still has to clear it."""
    s = closed(v35, clock, monkeypatch)
    assert s.v35_peak > s.hod_closed
    tick(v35, s, round(s.hod_closed + 0.10, 2))
    assert len(v35.broker.buys("ABCD")) == 1


def test_no_reentry_after_a_loser(v35, clock, monkeypatch):
    s = closed(v35, clock, monkeypatch, win=False)
    tick(v35, s, round(max(s.hod_closed, s.v35_peak) + 0.50, 2))
    assert len(v35.broker.buys("ABCD")) == 1


# ---- the daily halt -------------------------------------------------------------------

def test_v35_halts_at_10_percent_down(v35):
    assert v35.halt_threshold() == pytest.approx(0.10)


def test_the_environment_can_set_the_halt(v35, monkeypatch):
    monkeypatch.setenv("V35_HALT_PCT", "5")
    assert v35.halt_threshold() == pytest.approx(0.05)


# ---- the self-check -------------------------------------------------------------------

def violations(caplog):
    return [r for r in caplog.records if "SELF-CHECK VIOLATION" in r.getMessage()]


def test_self_check_holds_v35_to_its_own_40_percent_cap(v35, caplog):
    """A starter plus its add is allowed up to 40% of the account. Against the
    generic 25% cap the replay logged 149 false CRITICALs on 2026-10-02."""
    hold(v35, "ABCD", 3_800, 10.00)                    # $38,000 of $100,000
    run(v35.self_check())
    assert violations(caplog) == []


def test_self_check_still_flags_v35_past_its_cap(v35, caplog):
    hold(v35, "ABCD", 4_500, 10.00)                    # 45%: over 40% + 3% slack
    run(v35.self_check())
    assert len(violations(caplog)) == 1
