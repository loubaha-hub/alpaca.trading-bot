"""
v31 ENTRY GATE - which ticks are allowed to open a position.

Each test starts from a setup that DOES enter (test_full_setup_enters) and
breaks exactly one condition, so a failure names the gate that changed.
"""

import pytest

import bot
from helpers import breakout, hold, raw_bar, run

TRIGGER = 10.01            # breakout() default: red bar opens at 10.00, + 1 tick


def tick(strat, s, price):
    s.last_price = price
    run(strat.evaluate(s, price))


def entered(strat, s):
    return s.in_position and len(strat.broker.buys(s.symbol)) > 0


def test_full_setup_enters(v31, clock):
    s = breakout(v31, clock)
    tick(v31, s, TRIGGER)
    assert entered(v31, s)
    assert s.entry == pytest.approx(v31.broker.avg_cost(s.symbol))
    assert s.traded_today


def test_trigger_is_red_bar_open_plus_one_tick(v31, clock):
    s = breakout(v31, clock, red_open=7.40, red_low=7.25)
    assert s.setup_level == pytest.approx(7.40 + bot.V31_ENTRY_TICK)
    assert s.setup_low == 7.25                           # the red bar's low


def test_print_below_trigger_does_not_enter(v31, clock):
    s = breakout(v31, clock)
    tick(v31, s, TRIGGER - 0.001)
    assert not entered(v31, s)


def test_print_far_above_trigger_still_enters(v31, clock):
    """There is no ceiling on how far past the trigger the print may be -
    sizing absorbs it through a wider risk-per-share."""
    s = breakout(v31, clock)
    tick(v31, s, 10.60)
    assert entered(v31, s)


# ---- the setup: green closes, then red closes --------------------------------

def test_no_setup_when_last_bar_is_green(v31, clock):
    s = breakout(v31, clock)
    now = clock.now.astimezone(bot.timezone.utc)
    v31.offer_bar(raw_bar(s.symbol, now, 9.90, 10.10, 9.88, 10.05, 40_000))
    assert not s.setup_ready
    tick(v31, s, 10.11)
    assert not entered(v31, s)


def test_setup_is_rebuilt_on_every_closed_bar(v31, clock):
    """A green-then-red setup is only good until the next bar closes."""
    s = breakout(v31, clock)
    now = clock.now.astimezone(bot.timezone.utc)
    v31.offer_bar(raw_bar(s.symbol, now, 9.80, 9.85, 9.70, 9.72, 40_000))  # red after red
    assert not s.setup_ready


# ---- volume: thin_ok ---------------------------------------------------------

def test_one_thin_bar_blocks_entry(v31, clock):
    s = breakout(v31, clock, bar_volume=40_000)
    s.bars[-2].v = bot.V31_BAR_SHARES_MIN - 1
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)


def test_three_bar_total_below_floor_blocks_entry(v31, clock):
    # 33k each: every bar clears 30k, the three together miss 100k
    s = breakout(v31, clock, bar_volume=33_000)
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)


def test_three_bar_total_at_floor_enters(v31, clock):
    s = breakout(v31, clock, bar_volume=34_000)
    tick(v31, s, TRIGGER)
    assert entered(v31, s)


# ---- speed -------------------------------------------------------------------

def test_too_few_prints_for_a_speed_blocks_entry(v31, clock):
    s = breakout(v31, clock, speed=None)
    assert v31.fast_speed(s) is None
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)


def test_falling_speed_blocks_entry(v31, clock):
    s = breakout(v31, clock, speed="down")
    assert v31.fast_speed(s) < 0
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)


# ---- the scanner list and the position count --------------------------------

def test_symbol_not_on_scanner_list_does_not_enter(v31, clock):
    s = breakout(v31, clock, qualified=False)
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)


def test_three_open_positions_block_a_fourth(v31, clock):
    for sym in ("AAA", "BBB", "CCC"):
        hold(v31, sym, 100, 5.0)
    s = breakout(v31, clock)
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)


def test_two_open_positions_allow_a_third(v31, clock):
    for sym in ("AAA", "BBB"):
        hold(v31, sym, 100, 5.0)
    s = breakout(v31, clock)
    tick(v31, s, TRIGGER)
    assert entered(v31, s)


# ---- the clock ---------------------------------------------------------------

@pytest.mark.parametrize("hour,minute,allowed", [
    (3, 59, False),          # before the 4:00am session
    (4, 0, True),
    (12, 0, True),
    (18, 59, True),
    (19, 0, False),          # FLATTEN_AT: no new positions once closing starts
    (19, 30, False),
])
def test_entry_window(v31, clock, hour, minute, allowed):
    s = breakout(v31, clock)
    clock.set(hour, minute)
    tick(v31, s, TRIGGER)
    assert entered(v31, s) is allowed


# ---- re-entry: a new day high plus the margin --------------------------------

@pytest.mark.usefixtures("hod_on")
def test_reentry_below_day_high_plus_5_cents_is_blocked(v31, clock):
    """r27: a name traded today re-enters at the day's high + 5 cents."""
    s = breakout(v31, clock)
    s.traded_today = True
    s.day_high = 10.50
    s.hod_closed = 10.50
    tick(v31, s, 10.54)
    assert not entered(v31, s)


def test_reentry_above_day_high_plus_margin_enters(v31, clock):
    s = breakout(v31, clock)
    s.traded_today = True
    s.day_high = 10.50
    tick(v31, s, 10.65)                  # margin at 10.65 is 0.1065
    assert entered(v31, s)


def test_first_entry_needs_no_new_day_high(v31, clock):
    s = breakout(v31, clock)
    s.day_high = 12.00                   # far above the trigger
    tick(v31, s, TRIGGER)
    assert entered(v31, s)


@pytest.mark.parametrize("price,margin", [
    (3.00, 0.05), (5.00, 0.05),          # flat 5 cents up to $5
    (10.00, 0.10), (20.00, 0.20),        # 1% from $5 to $20
    (35.00, 0.25), (75.00, 0.35),        # stepped above $20
    (150.00, 0.40),
])
def test_margin_for(price, margin):
    assert bot.margin_for(price) == pytest.approx(margin)


# ---- the quote has to back the print -----------------------------------------

def test_ask_below_trigger_blocks_entry(v31, clock, data):
    s = breakout(v31, clock)
    data.quotes[(s.symbol, "ask")] = TRIGGER - 0.02
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)
    assert v31.broker.orders == []       # nothing was sent at all


def test_ask_at_trigger_enters(v31, clock, data):
    s = breakout(v31, clock)
    data.quotes[(s.symbol, "ask")] = TRIGGER
    tick(v31, s, TRIGGER)
    assert entered(v31, s)


def test_no_quote_enters_on_the_print_alone(v31, clock):
    s = breakout(v31, clock)             # FakeData has no quote set
    tick(v31, s, TRIGGER)
    assert entered(v31, s)


def test_quote_confirm_off_ignores_a_low_ask(v31, clock, data, monkeypatch):
    monkeypatch.setattr(bot, "CONFIRM_ENTRY_WITH_QUOTE", False)
    s = breakout(v31, clock)
    data.quotes[(s.symbol, "ask")] = TRIGGER - 0.50
    tick(v31, s, TRIGGER)
    assert entered(v31, s)


# ---- the daily halt ----------------------------------------------------------

def test_no_entry_once_the_account_is_down_10_percent(v31, clock, broker):
    s = breakout(v31, clock)
    broker.eq = v31.day_start_equity * 0.90
    tick(v31, s, TRIGGER)
    assert not entered(v31, s)
    assert v31.halted_today


def test_entry_allowed_just_above_the_halt_line(v31, clock, broker):
    s = breakout(v31, clock)
    broker.eq = v31.day_start_equity * 0.901
    tick(v31, s, TRIGGER)
    assert entered(v31, s)


# ---- r26: the $1-$20 range is checked when buying, not only when scanning -----

@pytest.mark.parametrize("red_open,red_low,price,allowed", [
    (0.94, 0.90, 0.95, False),          # fell under $1 after qualifying
    (1.00, 0.95, 1.01, True),
    (20.20, 19.90, 20.21, False),       # ran above $20
    (19.90, 19.60, 19.91, True),
])
def test_price_range_at_entry(v31, clock, red_open, red_low, price, allowed):
    s = breakout(v31, clock, red_open=red_open, red_low=red_low)
    tick(v31, s, price)
    assert entered(v31, s) is allowed


# ---- r27: re-enter a runner at every new high of the day ----------------------
# The feature ships switched off (V31_HOD_REENTRY = False); these tests switch
# it on to keep checking that it works.

@pytest.fixture
def hod_on(monkeypatch):
    monkeypatch.setattr(bot, "V31_HOD_REENTRY", True, raising=False)


def no_setup(strat, clock, symbol="ABCD"):
    """A traded name whose last closed bar is green - no green/red setup."""
    s = breakout(strat, clock, symbol)
    now = clock.now.astimezone(bot.timezone.utc)
    strat.offer_bar(raw_bar(symbol, now, 10.00, 10.40, 9.95, 10.35, 40_000))
    assert not s.setup_ready
    s.traded_today = True
    s.day_high = 10.50
    s.hod_closed = 10.50                 # the highest closed bar: the resistance
    return s


@pytest.mark.usefixtures("hod_on")
def test_new_high_reentry_needs_no_setup(v31, clock):
    s = no_setup(v31, clock)
    tick(v31, s, 10.55)                  # 10.50 + 0.05
    assert entered(v31, s)


@pytest.mark.usefixtures("hod_on")
def test_new_high_reentry_stop_sits_under_the_old_high(v31, clock):
    s = no_setup(v31, clock)
    abr = v31.abr(s)
    tick(v31, s, 10.55)
    assert entered(v31, s)
    assert s.stop == pytest.approx(min(10.50 - max(abr, 0.01), s.entry * 0.99))
    assert s.stop < 10.50


@pytest.mark.usefixtures("hod_on")
def test_first_entry_still_needs_a_setup(v31, clock):
    s = no_setup(v31, clock)
    s.traded_today = False               # never traded today
    tick(v31, s, 10.60)
    assert not entered(v31, s)


def test_new_high_reentry_is_off_by_default(v31, clock):
    s = no_setup(v31, clock)
    tick(v31, s, 10.60)
    assert not entered(v31, s)


@pytest.mark.usefixtures("hod_on")
def test_new_high_reentry_still_needs_volume_and_speed(v31, clock):
    s = no_setup(v31, clock)
    s.bars[-1].v = bot.V31_BAR_SHARES_MIN - 1        # thin last bar
    tick(v31, s, 10.60)
    assert not entered(v31, s)


@pytest.mark.usefixtures("hod_on")
def test_new_high_reentry_fires_on_a_steady_climb(v31, clock):
    """The bug r27 first shipped with: measured against s.day_high, which rises
    with every print, a smooth climb never stood 5c above it. Measured against
    the highest closed bar, the climb breaks out."""
    s = no_setup(v31, clock)
    for p in [10.44, 10.47, 10.50, 10.52, 10.54, 10.56]:   # one cent-ish at a time
        s.last_price = p
        v31.note_trade(s, p, 100)
        run(v31.evaluate(s, p))
        s.day_high = max(s.day_high, p)                    # what tick_worker does
        if s.in_position:
            break
    assert entered(v31, s)


def test_reentry_above_day_high_plus_margin_still_enters_with_a_setup(v31, clock):
    """With new-high re-entry off, a traded name still re-enters through a
    green/red setup that also clears the day's high plus margin_for()."""
    s = breakout(v31, clock)
    s.traded_today = True
    s.day_high = 10.50
    tick(v31, s, 10.65)                  # margin at 10.65 is 0.1065
    assert entered(v31, s)
