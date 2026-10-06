"""
v36 - the owner's playbook (memory/playbook.md, memory/rules.md).

Where the crowd is now; a rip on real money; the green-red pattern after it
(or the high of the day breaking); the owner's four filters; the tape at least
60% at the ask; a tenth of a position to start, adding as it moves, the floor
to breakeven after each add; the short 10-second leash once added to; a long
leash once up 10%; back in as long as it runs, one buy a minute.

Most tests turn the tape check and the crowd's two-minute hold off, so each
changes one thing; both have their own tests.
"""

import time

import pytest

import bot
from helpers import feed_bars, run

RED_OPEN = 10.40
RED_LOW = 10.15
TRIGGER = RED_OPEN + bot.V31_ENTRY_TICK


@pytest.fixture
def v36(broker, data, clock, monkeypatch):
    monkeypatch.setattr(bot, "V36_TAPE_GREEN", 0.0)
    monkeypatch.setattr(bot, "V36_CROWD_HOLD_MIN", 0)
    strat = bot.V36(broker, data)
    strat.day_start_equity = broker.eq
    return strat


def ripping(strat, clock, symbol="ABCD", *, rip_volume=(150_000, 200_000),
            base_volume=40_000, rip_top=(9.90, 10.40), wick=0.05,
            pullback=True, scale=1.0):
    """Twenty rising candles on base_volume, then the rip - two greens from
    9.60 to rip_top[1] on rip_volume - then (pullback) one red from RED_OPEN
    to a RED_LOW low. Above VWAP and the 9 EMA, 9 over 20, MACD over zero.
    scale multiplies every price (a cheaper, thinner stock)."""
    now = clock.now.astimezone(bot.timezone.utc)
    k = scale
    rows = []
    for i in range(20):
        o = 8.00 + 0.08 * i
        rows.append((o * k, (o + 0.10) * k, (o - 0.02) * k, (o + 0.08) * k, base_volume))
    mid, top = rip_top
    rows.append((9.60 * k, (mid + 0.02) * k, 9.58 * k, mid * k, rip_volume[0]))          # green
    rows.append((mid * k, (top + wick) * k, (mid - 0.05) * k, top * k, rip_volume[1]))  # green
    if pullback:
        rows.append((RED_OPEN * k, (RED_OPEN + 0.02) * k, RED_LOW * k, 10.20 * k, 80_000))  # red
    feed_bars(strat, symbol, now, rows)
    strat.qualified.add(symbol)
    return strat.st(symbol)


def tick(strat, s, price):
    s.last_price = price
    strat.note_trade(s, price, 100)
    run(strat.evaluate(s, price))
    s.day_high = max(s.day_high, price)


def entered(strat, s):
    return s.in_position and len(strat.broker.buys(s.symbol)) > 0


# ---- the buy ---------------------------------------------------------------------

def test_the_rip_is_found(v36, clock):
    s = ripping(v36, clock)
    assert v36.rip(s) == len(s.bars) - 2              # the second green


def test_buys_a_starter_a_tenth_of_a_full_position(v36, clock, broker):
    s = ripping(v36, clock)
    tick(v36, s, TRIGGER - 0.01)
    assert not entered(v36, s)
    tick(v36, s, TRIGGER)
    assert entered(v36, s)
    value = s.shares * s.entry
    assert value == pytest.approx(broker.eq * bot.V36_POSITION_PCT * bot.V36_STARTER, rel=0.06)
    assert s.stop <= RED_LOW + 1e-9


def test_no_rip_no_buy(v36, clock):
    s = ripping(v36, clock, rip_volume=(60_000, 70_000))   # 1.5x the minutes before
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)


def test_a_thin_stock_is_left_alone_however_fast(v36, clock):
    """"Stay away from that one ... period" - the rip minutes on $40k each."""
    s = ripping(v36, clock, rip_volume=(15_000, 20_000), base_volume=4_000)
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)


def test_a_long_upper_wick_is_no_rip(v36, clock):
    s = ripping(v36, clock, wick=0.80)                   # retreated from its high
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)


def test_a_big_float_is_left_alone(v36, clock, monkeypatch):
    monkeypatch.setitem(bot.FLOATS, "ABCD", 60_000_000)
    s = ripping(v36, clock)
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)


def test_never_banned_for_running(v36, clock):
    """The rip itself is +8% in two minutes and the climb +30% in twenty -
    what v31's no-chase rule banned for the day."""
    s = ripping(v36, clock)
    assert not hasattr(v36, "chased_today") or s.symbol not in v36.chased_today
    tick(v36, s, TRIGGER)
    assert entered(v36, s)


def test_the_high_of_the_day_breaking_on_stacking_greens(v36, clock):
    s = ripping(v36, clock, pullback=False)
    level = s.hod_closed + bot.margin_for(10.45)
    tick(v36, s, level - 0.01)
    assert not entered(v36, s)
    tick(v36, s, round(level + 0.005, 4))
    assert entered(v36, s)
    assert s.entry_kind == "hod"


# ---- where the crowd is ------------------------------------------------------------

def busier(strat, clock, symbol, volume):
    now = clock.now.astimezone(bot.timezone.utc)
    feed_bars(strat, symbol, now, [(10.0, 10.1, 9.9, 10.05, volume)] * 5)
    strat.qualified.add(symbol)


def test_only_where_the_crowd_is(v36, clock):
    s = ripping(v36, clock)
    busier(v36, clock, "BIGA", 2_000_000)
    busier(v36, clock, "BIGB", 1_500_000)
    tick(v36, s, TRIGGER)
    assert v36.crowd_rank("ABCD") == 3
    assert not entered(v36, s)


def test_the_crowd_must_hold_a_couple_of_minutes(v36, clock, monkeypatch):
    monkeypatch.setattr(bot, "V36_CROWD_HOLD_MIN", 2)
    s = ripping(v36, clock)
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)                          # just arrived at the top
    v36.crowd_since["ABCD"] = time.time() - 121
    tick(v36, s, TRIGGER)
    assert entered(v36, s)


# ---- the tape ----------------------------------------------------------------------

def tape(strat, s, at_ask, at_bid, bid=10.40, ask=10.41):
    s.quote = (bid, ask, time.time())
    for _ in range(at_ask):
        strat.tape_add(s, ask, 100)
    for _ in range(at_bid):
        strat.tape_add(s, bid, 100)


def test_the_tape_mostly_green_buys(v36, clock, monkeypatch):
    monkeypatch.setattr(bot, "V36_TAPE_GREEN", 0.60)
    s = ripping(v36, clock)
    tape(v36, s, at_ask=70, at_bid=30)
    tick(v36, s, TRIGGER)
    assert entered(v36, s)


def test_the_tape_mostly_red_does_not(v36, clock, monkeypatch):
    """10-05: all seven of v31's buys into a mostly-selling tape lost."""
    monkeypatch.setattr(bot, "V36_TAPE_GREEN", 0.60)
    s = ripping(v36, clock)
    tape(v36, s, at_ask=45, at_bid=55)
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)


# ---- adding as it moves ------------------------------------------------------------

def bought(v36, clock):
    s = ripping(v36, clock)
    tick(v36, s, TRIGGER)
    assert entered(v36, s)
    return s


def test_adds_to_half_then_full_as_it_moves(v36, clock, broker):
    s = bought(v36, clock)
    first = s.v36_first
    full = broker.eq * bot.V36_POSITION_PCT
    tick(v36, s, round(first * 1.031, 2))
    assert s.v36_adds == 1
    assert s.shares * first == pytest.approx(0.5 * full, rel=0.08)
    tick(v36, s, round(first * 1.061, 2))
    assert s.v36_adds == 2
    assert s.shares * first == pytest.approx(full, rel=0.08)


def test_after_an_add_the_floor_is_breakeven(v36, clock):
    s = bought(v36, clock)
    tick(v36, s, round(s.v36_first * 1.031, 2))
    assert s.stop == pytest.approx(s.entry)


def test_no_add_without_a_new_high(v36, clock):
    s = bought(v36, clock)
    tick(v36, s, round(s.v36_first * 1.08, 2))           # up, a new high: add 1
    assert s.v36_adds == 1
    tick(v36, s, round(s.v36_first * 1.065, 2))          # up 6.5% but under the high
    assert s.v36_adds == 1


# ---- the leash ---------------------------------------------------------------------

def ten(v36, s, *candles, start):
    """Feed 10-second candles (o, h, l, c) as prints, one candle per bucket."""
    for i, (o, h, l, c) in enumerate(candles):
        t = start + 10 * i
        for px in (o, h, l, c):
            v36.ten_add(s, px, t + 1)
    v36.ten_add(s, candles[-1][3], start + 10 * len(candles) + 1)   # closes the last


def test_the_starter_alone_has_room(v36, clock):
    """A tenth of a position: only the red's low takes it out."""
    s = bought(v36, clock)
    start = (int(time.time()) // 10 + 2) * 10
    ten(v36, s, (10.50, 10.52, 10.45, 10.50), (10.50, 10.51, 10.44, 10.48),
        (10.48, 10.48, 10.30, 10.31), start=start)
    tick(v36, s, 10.31)
    assert s.in_position


def test_once_added_to_a_red_10_second_candle_under_the_lows_exits(v36, clock):
    s = bought(v36, clock)
    tick(v36, s, round(s.v36_first * 1.031, 2))
    assert s.v36_adds == 1
    start = (int(time.time()) // 10 + 3) * 10            # past the grace
    ten(v36, s, (10.90, 10.93, 10.87, 10.91), (10.91, 10.92, 10.86, 10.89),
        (10.89, 10.89, 10.78, 10.80), start=start)       # above the breakeven floor
    assert s.ten_break and s.stop < 10.80
    tick(v36, s, 10.80)
    assert not s.in_position
    assert v36.closed_today[-1][5] == "10s"


def test_a_small_red_patch_inside_a_run_does_not(v36, clock):
    """"You hold up through that little bout"."""
    s = bought(v36, clock)
    tick(v36, s, round(s.v36_first * 1.031, 2))
    start = (int(time.time()) // 10 + 3) * 10
    ten(v36, s, (10.75, 10.78, 10.72, 10.76), (10.76, 10.79, 10.73, 10.78),
        (10.78, 10.78, 10.74, 10.75), start=start)       # red, but above the lows
    assert not s.ten_break


def test_a_long_leash_once_up_ten_percent(v36, clock):
    s = bought(v36, clock)
    tick(v36, s, round(s.v36_first * 1.11, 2))
    assert s.armed


# ---- again, and again --------------------------------------------------------------

def test_one_buy_a_minute(v36, clock):
    s = bought(v36, clock)
    run(v36.exit(s, "test"))
    tick(v36, s, TRIGGER)
    assert not s.in_position                            # same minute, same setup


def test_no_more_than_the_days_entries(v36, clock, monkeypatch):
    s = ripping(v36, clock)
    s.v36_entries = bot.V36_MAX_ENTRIES
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)


# ---- which account -----------------------------------------------------------------

def test_v36_takes_v34s_account_and_v31_stays_the_yardstick():
    slots = bot.account_classes("v34")
    assert slots["v31"] is bot.V31 and slots["v34"] is bot.V36
    assert slots["v35"] is bot.V35


def test_v36_can_take_v31s_account_instead_or_stay_off():
    assert bot.account_classes("v31")["v31"] is bot.V36
    off = bot.account_classes("off")
    assert bot.V36 not in off.values()
