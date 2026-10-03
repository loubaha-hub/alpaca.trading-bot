"""
v32 (r33) - buy EVERY scanner name, one equal slot each (1/50th of the
account), cut what does not hold, keep what does - on v31's machinery for the
rest.

Tests marked "r32:" name what the old v32 did instead. They cannot run
against r32.py: its v32 kept no bars, so the liquid-name setup below cannot be
built for it. test_switches_off_... shows r32's rules with every switch off.
"""

from datetime import timedelta

import pytest

import bot
from helpers import breakout, hold, run

PRICE = 10.00
SLOT_SHARES = int(bot.SIMPLE_SLOT / PRICE)     # $600 at $10: 60


@pytest.fixture
def v32(broker, data, clock):
    strat = bot.V32(broker, data)
    strat.day_start_equity = broker.eq
    return strat


def ready(strat, clock, symbol="ABCD", **kw):
    """A liquid scanner name, three 40k-share bars, nothing spiking."""
    return breakout(strat, clock, symbol, **kw)


def tick(strat, s, price):
    s.last_price = price
    strat.note_trade(s, price, 100)
    run(strat.evaluate(s, price))


def entered(strat, s):
    return s.in_position and len(strat.broker.buys(s.symbol)) > 0


# ---- the first entry --------------------------------------------------------------

def test_a_liquid_scanner_name_is_bought_on_its_first_tick(v32, clock, broker):
    s = ready(v32, clock)
    tick(v32, s, PRICE)
    assert entered(v32, s)
    assert [o[1] for o in broker.buys(s.symbol)] == [SLOT_SHARES]


def test_a_name_not_on_the_scanner_list_is_not_bought(v32, clock):
    s = ready(v32, clock, qualified=False)
    tick(v32, s, PRICE)
    assert not entered(v32, s)


def test_a_thin_name_is_not_bought(v32, clock):
    """r32: every scanner name was bought on its first print, however thin -
    the stop then filled 1-2% under where it sat."""
    s = ready(v32, clock, bar_volume=20_000)
    tick(v32, s, PRICE)
    assert not entered(v32, s)


def test_a_name_that_just_spiked_is_not_chased(v32, clock, data):
    """r32: no chase check - it bought names already up 20% in minutes."""
    now = clock.now.astimezone(bot.timezone.utc)
    data.history["ABCD"] = [(now - timedelta(minutes=30), 7.90),
                            (now - timedelta(minutes=17), 8.20)]
    s = ready(v32, clock)
    tick(v32, s, PRICE)
    assert not entered(v32, s)


def test_the_price_range_is_checked_at_the_buy(v32, clock):
    """r32: no $1-$20 check when buying."""
    s = ready(v32, clock, red_open=20.20, red_low=19.90)
    tick(v32, s, 20.21)
    assert not entered(v32, s)


def test_no_buying_once_the_day_is_closing(v32, clock):
    s = ready(v32, clock)
    clock.set(19, 30)
    tick(v32, s, PRICE)
    assert not entered(v32, s)


def test_a_small_float_buys_half(v32, clock, broker, monkeypatch):
    monkeypatch.setattr(bot, "FLOATS", {"ABCD": 2_000_000})
    s = ready(v32, clock)
    tick(v32, s, PRICE)
    assert [o[1] for o in broker.buys(s.symbol)] == [SLOT_SHARES // 2]


def test_never_past_the_exposure_cap(v32, clock, broker):
    """r32: 50 slots of 1/50th each are 100% of the account, over the 95% cap."""
    hold(v32, "BIG", 9_500, 10.0)                    # $95,000 of $100,000
    s = ready(v32, clock)
    tick(v32, s, PRICE)
    assert not entered(v32, s)


def test_the_entry_is_what_was_paid(v32, clock, broker, data):
    """r32: the triggering print was the entry."""
    s = ready(v32, clock)
    data.quotes[(s.symbol, "ask")] = 10.03
    tick(v32, s, PRICE)
    assert s.entry == pytest.approx(broker.avg_cost(s.symbol))
    assert s.entry != pytest.approx(PRICE)


# ---- the stop ---------------------------------------------------------------------

def test_the_stop_is_1_percent_under_the_entry(v32, clock):
    """r32: a penny under the bid - an unchanged market stopped it out."""
    s = ready(v32, clock)
    tick(v32, s, PRICE)
    assert s.stop == pytest.approx(s.entry * 0.99)


def test_a_print_through_the_stop_closes_it(v32, clock, broker):
    s = ready(v32, clock)
    tick(v32, s, PRICE)
    tick(v32, s, s.stop - 0.01)
    assert not s.in_position
    assert v32.closed_today[-1][-1] == "stop"


def test_a_winner_is_held(v32, clock):
    """Keep what holds: no trim, no trail - a +30% name is still held."""
    s = ready(v32, clock)
    tick(v32, s, PRICE)
    tick(v32, s, 13.00)
    assert s.in_position and s.shares == SLOT_SHARES


# ---- re-entries -------------------------------------------------------------------

def stopped_out(strat, clock):
    s = ready(strat, clock)
    tick(strat, s, PRICE)
    tick(strat, s, s.stop - 0.01)
    assert not s.in_position and s.traded_today
    return s


def test_a_reentry_needs_a_new_day_high(v32, clock):
    """r32: back in 2c over the FIRST entry, all day - up to 23 round trips in
    one name, each one paying the spread and the slip."""
    s = stopped_out(v32, clock)
    tick(v32, s, PRICE + 0.02)                       # r32's re-entry level
    assert len(v32.broker.buys(s.symbol)) == 1
    level = s.hod_closed + bot.margin_for(10.16)     # 10.05 + 1%
    tick(v32, s, round(level + 0.005, 2))
    assert entered(v32, s)
    assert len(v32.broker.buys(s.symbol)) == 2


def test_the_ask_has_to_back_a_reentry(v32, clock, data):
    s = stopped_out(v32, clock)
    data.quotes[(s.symbol, "ask")] = 10.10           # under the 10.15 level
    tick(v32, s, 10.16)
    assert len(v32.broker.buys(s.symbol)) == 1


def test_a_reentry_counts(v32, clock):
    s = stopped_out(v32, clock)
    tick(v32, s, 10.16)
    assert s.v32_trips == 2


# ---- the daily halt -----------------------------------------------------------------

def test_v32_halts_at_10_percent_down(v32):
    """r32: no halt at all - it lost 35% of its account on 2026-10-02."""
    assert v32.halt_threshold() == pytest.approx(0.10)


def test_the_environment_can_set_the_halt(v32, monkeypatch):
    monkeypatch.setenv("V32_HALT_PCT", "5")
    assert v32.halt_threshold() == pytest.approx(0.05)


def test_no_new_names_once_halted(v32, clock, broker):
    v32.day_start_equity = broker.eq / 0.85          # already down 15%
    s = ready(v32, clock)
    tick(v32, s, PRICE)
    assert not entered(v32, s)


# ---- every switch off is r32's v32 --------------------------------------------------

@pytest.fixture
def r32_rules(monkeypatch):
    for name, value in (("V32_DAILY_HALT", 0.0), ("V32_FIXES", False),
                        ("V32_REENTRY_HIGH", False), ("V32_THIN_OK", False),
                        ("V32_NO_CHASE", False), ("V32_VOL_RISING", False),
                        ("V32_STOP_PCT", 0.0), ("V32_FLOAT_SIZING", False)):
        monkeypatch.setattr(bot, name, value)


def test_switches_off_rebuy_2c_over_the_first_entry(v32, clock, data, r32_rules):
    data.quotes[("ABCD", "bid")] = PRICE
    s = ready(v32, clock, bar_volume=20_000)         # thin: bought anyway
    tick(v32, s, PRICE)
    assert entered(v32, s)
    assert s.stop == pytest.approx(bot.simple_stop(PRICE))
    tick(v32, s, s.stop - 0.01)
    tick(v32, s, PRICE + 0.02)
    assert len(v32.broker.buys(s.symbol)) == 2
