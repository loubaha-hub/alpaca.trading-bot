"""
v31 POSITION SIZING - how many shares a starter and an add buy, and where the
entry stop goes.

All on a $100,000 account, trigger 10.01 (red bar open 10.00 + 1 tick).

THE SHAPE OF IT, as the code stands:
  shares = 1% of equity / risk-per-share, risk-per-share floored at 1% of price
  then capped at 25% of equity, and at whatever room is left under 95% total.

  With a 1% floor the risk formula asks for up to 100% of equity, so the 25%
  cap is what sets the size whenever the stop is within 4% of the price. Only
  wider stops are sized by risk. Both regimes are pinned below.
"""

import pytest

import bot
from helpers import breakout, feed_trades, hold, run

TRIGGER = 10.01
CAP_SHARES = 2497                  # int(25,000 / 10.01)


def enter(strat, clock, price=TRIGGER, **setup):
    s = breakout(strat, clock, **setup)
    s.last_price = price
    run(strat.evaluate(s, price))
    return s


def order_sizes(broker, symbol="ABCD"):
    return [o[1] for o in broker.buys(symbol)]


# ---- the starter -------------------------------------------------------------

@pytest.mark.parametrize("red_low,shares", [
    (9.99, CAP_SHARES),            # 0.2% away -> 1% floor -> cap
    (9.75, CAP_SHARES),            # 2.6% away -> risk asks 3846 -> cap
    (9.65, CAP_SHARES),            # 3.6% away -> risk asks 2777 -> cap
    (9.50, 1960),                  # 5.1% away -> risk sizes it, under the cap
    (9.00, 990),                   # 10.1%
    (8.00, 497),                   # 20.1%
])
def test_starter_size(v31, clock, broker, red_low, shares):
    s = enter(v31, clock, red_low=red_low)
    assert order_sizes(broker) == [shares]
    assert s.shares == shares


@pytest.mark.parametrize("red_low", [9.99, 9.75, 9.50, 9.00, 8.00])
def test_starter_never_above_25_percent_of_equity(v31, clock, red_low):
    s = enter(v31, clock, red_low=red_low)
    assert s.shares * TRIGGER <= 0.25 * 100_000


@pytest.mark.parametrize("red_low", [9.99, 9.75, 9.50, 9.00, 8.00])
def test_loss_at_the_stop_is_at_most_1_percent(v31, clock, red_low):
    """Measured from the trigger, which is what the bot records as the entry."""
    s = enter(v31, clock, red_low=red_low)
    assert s.shares * (s.entry - s.stop) <= 0.01 * 100_000 + 1e-6


def test_one_percent_floor_applies_to_sizing(v31, clock, broker, monkeypatch):
    """The floor is invisible at the shipped 1% risk (the cap always wins), so
    lower the risk until the floor is what decides. A 2-cent stop would ask
    for 10,000 shares; floored at 1% of price it asks for 1,998."""
    monkeypatch.setattr(bot, "V31_RISK_PER_TRADE", 0.002)
    enter(v31, clock, red_low=9.99)
    assert order_sizes(broker) == [1998]


# ---- the entry stop ----------------------------------------------------------

def test_stop_at_red_bar_low_when_it_is_more_than_1_percent_away(v31, clock):
    s = enter(v31, clock, red_low=9.50)
    assert s.stop == 9.50


def test_stop_floored_1_percent_under_entry_when_red_low_is_closer(v31, clock):
    """IBRX, 2026-09-30: a 1-cent stop was a coin toss. Sizing and the stop
    use the same 1% floor."""
    s = enter(v31, clock, red_low=9.99)
    assert s.stop == pytest.approx(TRIGGER * 0.99)


def test_state_after_a_fill(v31, clock):
    s = enter(v31, clock)
    assert s.entry == TRIGGER
    assert s.peak == TRIGGER
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
    assert order_sizes(broker) == [1498]        # int(15,000 / 10.01)


def test_room_counts_other_positions_at_their_last_price(v31, clock, broker):
    a = hold(v31, "AAA", 4000, 10.0, entry=5.0)  # bought at 5, now worth $40,000
    hold(v31, "BBB", 4000, 10.0)
    assert a.last_price == 10.0
    enter(v31, clock, red_low=9.75)
    assert order_sizes(broker) == [1498]


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
    assert order_sizes(broker, "AAA") == [1500]
    assert s.shares == 2500


def test_add_never_past_25_percent_for_a_follower(v31, broker):
    speeding(v31, "AAA", 1000, 10.0, 9.0, 10.0)
    b = speeding(v31, "BBB", 1000, 10.0, 9.9, 10.0)  # targeted at 75%
    run(v31.add(b, 10.0))
    assert b.shares * 10.0 <= 25_000


def test_add_limited_by_room(v31, broker):
    hold(v31, "BBB", 8000, 10.0)                     # $80,000
    s = speeding(v31, "AAA", 1000, 10.0, 9.0, 10.0)  # $10,000 -> $5,000 room
    run(v31.add(s, 10.0))
    assert order_sizes(broker, "AAA") == [500]


def test_add_does_nothing_at_the_cap(v31, broker):
    s = speeding(v31, "AAA", 2500, 10.0, 9.0, 10.0)  # already 25%
    run(v31.add(s, 10.0))
    assert broker.buys("AAA") == []
