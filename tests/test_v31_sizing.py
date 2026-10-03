"""
v31 POSITION SIZING - how many shares a starter and an add buy, and where the
entry stop goes.

All on a $100,000 account, trigger 10.01 (red bar open 10.00 + 1 tick).

THE SHAPE OF IT:
  Everything is worked out for the WORST price buy() may pay - the print plus
  BUY_CHASE_CAP (2%), 10.2102 here - so no fill can break either limit.

  shares = 1% of equity / risk-per-share (worst price - red bar low, floored
  at 1%), then capped at 25% of equity and at the room left under 95% total.

  The 25% cap sets the size when the red bar's low is within about 2% of the
  print; wider stops are sized by risk. Both regimes are pinned below.
"""

import pytest

import bot
from helpers import breakout, feed_trades, hold, run

TRIGGER = 10.01
WORST = TRIGGER * 1.02             # the most buy() may pay
CAP_SHARES = 2448                  # int(25,000 / 10.2102)
PAID = 10.03                       # FakeBroker fill with no quote: 10.01 * 1.002


def enter(strat, clock, price=TRIGGER, **setup):
    s = breakout(strat, clock, **setup)
    s.last_price = price
    run(strat.evaluate(s, price))
    return s


def order_sizes(broker, symbol="ABCD"):
    return [o[1] for o in broker.buys(symbol)]


# ---- the starter -------------------------------------------------------------

@pytest.mark.parametrize("red_low,shares", [
    (9.99, CAP_SHARES),            # risk asks 4541 -> cap
    (9.75, 2172),                  # risk 0.4602/share, under the cap
    (9.65, 1785),
    (9.50, 1408),
    (9.00, 826),
    (8.00, 452),
])
def test_starter_size(v31, clock, broker, red_low, shares):
    s = enter(v31, clock, red_low=red_low)
    assert order_sizes(broker) == [shares]
    assert s.shares == shares


@pytest.mark.parametrize("red_low", [9.99, 9.75, 9.50, 9.00, 8.00])
def test_starter_never_above_25_percent_of_equity(v31, clock, red_low):
    s = enter(v31, clock, red_low=red_low)
    assert s.shares * WORST <= 0.25 * 100_000


@pytest.mark.parametrize("red_low", [9.99, 9.75, 9.50, 9.00, 8.00])
def test_loss_at_the_stop_is_at_most_1_percent(v31, clock, red_low):
    """Measured from the entry, which is what the account paid."""
    s = enter(v31, clock, red_low=red_low)
    assert s.shares * (s.entry - s.stop) <= 0.01 * 100_000 + 1e-6


def test_one_percent_floor_applies_to_sizing(v31, clock, broker, monkeypatch):
    """With the 2% chase allowance the worst price is always more than 1% above
    the red bar's low, so the floor only shows with no chase allowed, and
    with the risk lowered until the cap no longer wins. A 2-cent stop would
    then ask for 10,000 shares; floored at 1% of price it asks for 1,998."""
    monkeypatch.setattr(bot, "BUY_CHASE_CAP", 0.0)
    monkeypatch.setattr(bot, "V31_RISK_PER_TRADE", 0.002)
    enter(v31, clock, red_low=9.99)
    assert order_sizes(broker) == [1998]


# ---- the entry stop ----------------------------------------------------------

def test_stop_at_red_bar_low_when_it_is_more_than_1_percent_away(v31, clock):
    s = enter(v31, clock, red_low=9.50)
    assert s.stop == 9.50


def test_stop_floored_1_percent_under_entry_when_red_low_is_closer(v31, clock):
    """IBRX, 2026-09-30: a 1-cent stop was a coin toss. Sizing and the stop
    use the same 1% floor, measured from what was paid."""
    s = enter(v31, clock, red_low=9.99)
    assert s.stop == pytest.approx(PAID * 0.99)


def test_state_after_a_fill(v31, clock):
    s = enter(v31, clock)
    assert s.entry == pytest.approx(PAID)        # what was paid, not the print
    assert s.peak == pytest.approx(PAID)
    assert s.trail_stop == 0.0
    assert not s.armed
    assert not s.adopted
    assert s.traded_today
    assert s.entry_at > 0


# ---- room under the 95% exposure ceiling -------------------------------------

def test_starter_shrinks_to_the_room_left(v31, clock, broker):
    hold(v31, "AAA", 4000, 10.0)                # $40,000
    hold(v31, "BBB", 4000, 10.0)                # $40,000 -> $15,000 of room
    enter(v31, clock, red_low=9.75)
    assert order_sizes(broker) == [1469]        # int(15,000 / 10.2102)


def test_room_counts_other_positions_at_their_last_price(v31, clock, broker):
    a = hold(v31, "AAA", 4000, 10.0, entry=5.0)  # bought at 5, now worth $40,000
    hold(v31, "BBB", 4000, 10.0)
    assert a.last_price == 10.0
    enter(v31, clock, red_low=9.75)
    assert order_sizes(broker) == [1469]


def test_no_room_no_order(v31, clock, broker):
    hold(v31, "AAA", 5000, 10.0)                # $50,000
    hold(v31, "BBB", 4500, 10.0)                # $45,000 -> 95%, no room
    s = enter(v31, clock)
    assert broker.buys("ABCD") == []
    assert not s.in_position


# ---- too small to bother -----------------------------------------------------

def test_under_100_dollars_no_order(v31, clock, broker):
    broker.eq = v31.day_start_equity = 300.0    # cap is 7 shares = $70
    s = enter(v31, clock)
    assert broker.orders == []
    assert not s.in_position


def test_zero_equity_no_order(v31, clock, broker):
    broker.eq = v31.day_start_equity = 0.0
    s = enter(v31, clock)
    assert broker.orders == []
    assert not s.in_position


# ---- adds --------------------------------------------------------------------

def speeding(strat, symbol, shares, price, start, end):
    s = hold(strat, symbol, shares, price)
    feed_trades(strat, symbol, start, end)
    return s


def test_target_for_a_lone_position_is_25_percent(v31):
    speeding(v31, "AAA", 1000, 10.0, 9.0, 10.0)
    assert run(v31.target_dollars("AAA")) == pytest.approx(25_000)


def test_target_is_zero_without_speed(v31):
    hold(v31, "AAA", 1000, 10.0)                # no prints recorded
    assert run(v31.target_dollars("AAA")) == 0.0


def test_target_gives_non_leaders_the_leaders_excess(v31):
    """CURRENT BEHAVIOUR, pinned so a change to it is deliberate. The leader
    is cut to 25% and the other names share the remaining 75% - so a lone
    follower is TARGETED at 75%, three times the leader. add() re-caps every
    name at 25%, so this does not over-size anything today."""
    speeding(v31, "AAA", 1000, 10.0, 9.0, 10.0)     # fast
    speeding(v31, "BBB", 1000, 10.0, 9.9, 10.0)     # slow
    assert run(v31.target_dollars("AAA")) == pytest.approx(25_000)
    assert run(v31.target_dollars("BBB")) == pytest.approx(75_000)


def test_add_tops_up_to_25_percent(v31, broker):
    s = speeding(v31, "AAA", 1000, 10.0, 9.0, 10.0)  # $10,000 = 10%
    run(v31.add(s, 10.0))
    assert order_sizes(broker, "AAA") == [1470]      # $15,000 at worst 10.20
    assert s.shares == 2470


def test_add_never_past_25_percent_for_a_follower(v31, broker):
    speeding(v31, "AAA", 1000, 10.0, 9.0, 10.0)
    b = speeding(v31, "BBB", 1000, 10.0, 9.9, 10.0)  # targeted at 75%
    run(v31.add(b, 10.0))
    assert b.shares * 10.0 <= 25_000


def test_add_limited_by_room(v31, broker):
    hold(v31, "BBB", 8000, 10.0)                     # $80,000
    s = speeding(v31, "AAA", 1000, 10.0, 9.0, 10.0)  # $10,000 -> $5,000 room
    run(v31.add(s, 10.0))
    assert order_sizes(broker, "AAA") == [490]       # $5,000 at worst 10.20


def test_add_does_nothing_at_the_cap(v31, broker):
    s = speeding(v31, "AAA", 2500, 10.0, 9.0, 10.0)  # already 25%
    run(v31.add(s, 10.0))
    assert broker.buys("AAA") == []


# ---- r28: size by float ---------------------------------------------------------
# Floats under 5M shares buy half: the risk budget and the 25% cap alike.

@pytest.fixture
def floats(monkeypatch):
    table = {}
    monkeypatch.setattr(bot, "FLOATS", table)
    return table


@pytest.mark.parametrize("float_shares,shares", [
    (3_000_000, 1086),             # under 5M: half of 2172
    (4_999_999, 1086),
    (5_000_000, 2172),             # 5M and up: full size
    (40_000_000, 2172),
])
def test_starter_size_by_float(v31, clock, broker, floats, float_shares, shares):
    floats["ABCD"] = float_shares
    enter(v31, clock, red_low=9.75)
    assert order_sizes(broker) == [shares]


def test_a_capped_starter_halves_too(v31, clock, broker, floats):
    """The risk maths asks for more than the cap; the cap is what halves."""
    floats["ABCD"] = 1_000_000
    enter(v31, clock, red_low=9.99)
    assert order_sizes(broker) == [CAP_SHARES // 2]


def test_a_small_float_risks_half(v31, clock, floats):
    floats["ABCD"] = 2_000_000
    s = enter(v31, clock, red_low=9.50)
    assert s.shares * (s.entry - s.stop) <= 0.005 * 100_000 + 1e-6


def test_a_name_not_in_the_float_file_is_full_size(v31, clock, broker, floats):
    floats["OTHER"] = 1_000_000
    enter(v31, clock, red_low=9.75)
    assert order_sizes(broker) == [2172]


def test_unknown_floats_can_be_sized_down(v31, clock, broker, floats, monkeypatch):
    monkeypatch.setattr(bot, "V31_FLOAT_UNKNOWN_MULT", 0.5)
    enter(v31, clock, red_low=9.75)
    assert order_sizes(broker) == [1086]


def test_float_sizing_switched_off(v31, clock, broker, floats, monkeypatch):
    monkeypatch.setattr(bot, "V31_FLOAT_SIZING", False)
    floats["ABCD"] = 1_000_000
    enter(v31, clock, red_low=9.75)
    assert order_sizes(broker) == [2172]


def test_half_of_a_tiny_order_is_not_sent(v31, clock, broker, floats):
    """Halving can take an order under MIN_TRADE_DOLLARS; then nothing is sent."""
    floats["ABCD"] = 1_000_000
    broker.eq = v31.day_start_equity = 700.0      # 15 shares by risk, half 7 = $70
    s = enter(v31, clock)
    assert broker.orders == []
    assert not s.in_position


def test_load_floats(tmp_path):
    f = tmp_path / "floats.csv"
    f.write_text("symbol,price,float_shares\n"
                 "abcd,2.5,3000000\n"
                 "EFGH,4,\n"                 # no number: skipped
                 "IJKL,1,n/a\n"              # not a number: skipped
                 "MNOP,9,12500000.0\n")
    assert bot.load_floats(f) == {"ABCD": 3_000_000, "MNOP": 12_500_000}
    assert bot.load_floats(tmp_path / "missing.csv") == {}
