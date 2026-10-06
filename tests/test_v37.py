"""
v37 - the simplest (the owner, 2026-10-06): where the crowd is, the moment it
rips. A tenth of a position, never more than 2 cents over the price seen; half
at +10 cents, full at +20 cents; out 2 cents under the buy, or once half of
the best gain is given back; again only at a new high of the day.
"""

import pytest

import bot
from helpers import feed_bars, run


@pytest.fixture
def now(monkeypatch):
    t = [1_790_000_000.0]
    monkeypatch.setattr(bot.time, "time", lambda: t[0])
    return t


@pytest.fixture
def v37(broker, data, clock, now):
    strat = bot.V37(broker, data)
    strat.day_start_equity = broker.eq
    return strat


def crowd(strat, clock, symbol, dollars_a_minute):
    """Five closed minutes trading this many dollars each, at $10."""
    utc = clock.now.astimezone(bot.timezone.utc)
    v = dollars_a_minute / 10.0
    feed_bars(strat, symbol, utc, [(10.0, 10.05, 9.95, 10.0, v)] * 5)
    strat.qualified.add(symbol)
    return strat.st(symbol)


def prints(strat, s, now, start, end, n=30, size=1_000, seconds=50):
    """n prints stepping from start to end over `seconds`."""
    for i in range(n):
        now[0] += seconds / n
        px = round(start + (end - start) * i / (n - 1), 4)
        s.last_price = px
        strat.note_trade(s, px, size)


def tick(strat, s, now, price, size=1_000):
    now[0] += 1
    s.last_price = price
    strat.note_trade(s, price, size)
    run(strat.evaluate(s, price))
    s.day_high = max(s.day_high, price)


def ripping(v37, clock, now, symbol="ABCD", start=10.00, end=10.35, size=1_000):
    s = crowd(v37, clock, symbol, 1_000_000)
    prints(v37, s, now, start, end, size=size)
    s.day_high = 10.05
    return s


def test_buys_a_starter_the_moment_it_rips(v37, clock, now, broker):
    s = ripping(v37, clock, now)
    tick(v37, s, now, 10.36)
    assert s.in_position
    assert s.shares * s.entry == pytest.approx(
        broker.eq * bot.V37_POSITION_PCT * bot.V37_STARTER, rel=0.05)


def test_never_more_than_2_percent_over_the_price_seen(v37, clock, now, data):
    """The owner, 10-06: "no more than two percent of the price itself"."""
    s = ripping(v37, clock, now)
    data.quotes[("ABCD", "ask")] = 10.80                   # the ask ran away
    tick(v37, s, now, 10.36)
    assert all(o[3] <= round(10.36 * 1.02, 2) + 1e-9 for o in v37.broker.buys("ABCD"))


def test_missed_it_tries_again_on_the_next_print_that_rips(v37, clock, now, broker):
    s = ripping(v37, clock, now)
    broker.fills = [0.0] * bot.FAST_BUY_TRIES             # the first chase gets nothing
    tick(v37, s, now, 10.36)
    assert not s.in_position
    tick(v37, s, now, 10.52)                              # still ripping, higher
    assert s.in_position


def test_not_fast_enough_no_buy(v37, clock, now):
    s = ripping(v37, clock, now, end=10.10)               # +1% in the minute
    tick(v37, s, now, 10.11)
    assert not s.in_position


def test_a_thin_rip_no_buy(v37, clock, now):
    s = ripping(v37, clock, now, size=100)                # $30k in the minute
    tick(v37, s, now, 10.36, size=100)
    assert not s.in_position


def test_only_where_the_crowd_is(v37, clock, now):
    s = ripping(v37, clock, now)
    crowd(v37, clock, "BIGA", 5_000_000)
    crowd(v37, clock, "BIGB", 4_000_000)
    tick(v37, s, now, 10.36)
    assert v37.crowd_rank("ABCD") == 3
    assert not s.in_position


def test_a_small_crowd_is_not_a_crowd(v37, clock, now):
    s = crowd(v37, clock, "ABCD", 100_000)               # $500k in five minutes
    prints(v37, s, now, 10.00, 10.35)
    tick(v37, s, now, 10.36)
    assert not s.in_position


def bought(v37, clock, now):
    s = ripping(v37, clock, now)
    tick(v37, s, now, 10.36)
    assert s.in_position
    return s


def test_no_tolerance_for_loss(v37, clock, now):
    s = bought(v37, clock, now)
    tick(v37, s, now, round(s.entry - 0.02, 2))
    assert not s.in_position
    assert v37.closed_today[-1][5] == "stop"


def test_adds_to_half_at_10_cents_and_full_at_20(v37, clock, now, broker):
    s = bought(v37, clock, now)
    first = s.v36_first
    full = broker.eq * bot.V37_POSITION_PCT
    tick(v37, s, now, round(first + 0.10, 2))
    assert s.v36_adds == 1
    assert s.shares * first == pytest.approx(0.5 * full, rel=0.05)
    tick(v37, s, now, round(first + 0.20, 2))
    assert s.v36_adds == 2
    assert s.shares * first == pytest.approx(full, rel=0.05)


def test_half_the_profit_gone_it_is_out(v37, clock, now, monkeypatch):
    monkeypatch.setattr(bot, "V37_ASK_PLUS", 0.0)         # fills at the price (the
    s = bought(v37, clock, now)                           # fake fills AT the limit)
    tick(v37, s, now, round(s.entry + 0.10, 2))           # add to half
    best = s.peak
    keep = s.entry + 0.5 * (best - s.entry)
    tick(v37, s, now, round(keep + 0.01, 2))
    assert s.in_position
    tick(v37, s, now, round(keep - 0.005, 3))
    assert not s.in_position
    assert v37.closed_today[-1][5] == "giveback"


def test_again_only_at_a_new_high_of_the_day(v37, clock, now):
    s = bought(v37, clock, now)
    tick(v37, s, now, 10.30)                              # stopped out
    assert not s.in_position
    prints(v37, s, now, 10.00, 10.33)                     # ripping again, under the high
    tick(v37, s, now, 10.34)
    assert not s.in_position
    tick(v37, s, now, round(s.day_high + 0.01, 2))        # through the high
    assert s.in_position


def test_no_more_than_two_at_once(v37, clock, now, monkeypatch):
    monkeypatch.setattr(bot, "V37_CROWD_TOP", 5)          # all three in the crowd
    for sym in ("AAA", "BBB", "CCC"):
        s = ripping(v37, clock, now, symbol=sym)
        v37.crowd = (-1, {})                              # recount the crowd now
        tick(v37, s, now, 10.36)
    assert len(v37.open_positions()) == 2


def test_the_days_top_gainer_counts_even_when_not_the_busiest(v37, clock, now):
    """The owner, 10-06: most picks are the day's top gainer with news."""
    s = ripping(v37, clock, now)
    crowd(v37, clock, "BIGA", 5_000_000)
    crowd(v37, clock, "BIGB", 4_000_000)
    s.ref_price = 5.00                                    # ABCD: +107% on the day
    for sym in ("BIGA", "BIGB"):
        st = v37.st(sym)
        st.ref_price, st.last_price = 9.50, 10.00        # +5%
    tick(v37, s, now, 10.36)
    assert v37.crowd_rank("ABCD") == 3 and v37.gainer_rank("ABCD") == 1
    assert s.in_position


def test_each_try_is_the_ask_plus_10_cents(v37, clock, now, data):
    """The owner's hot keys: "ask plus 10 cents" - filled at the best offers
    up to there."""
    s = ripping(v37, clock, now)
    data.quotes[("ABCD", "ask")] = 10.38
    tick(v37, s, now, 10.36)
    assert v37.broker.buys("ABCD")[0][3] == pytest.approx(10.48)


def test_a_furious_stock_may_cost_up_to_10_percent_more(v37, clock, now, data):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    prints(v37, s, now, 8.00, 10.00)                      # +25% in the minute
    s.day_high = 8.10
    assert v37.entry_cap(s, 10.00) == pytest.approx(bot.V37_ENTRY_MAX)
    data.quotes[("ABCD", "ask")] = 10.70                   # 7% over: still in reach
    tick(v37, s, now, 10.01)
    assert s.in_position
    assert v37.broker.buys("ABCD")[0][3] == pytest.approx(10.80)


def test_a_slower_stock_keeps_the_2_percent_ceiling(v37, clock, now):
    s = ripping(v37, clock, now)                          # +3.5% in the minute
    assert v37.entry_cap(s, 10.36) == pytest.approx(bot.V37_ENTRY_PCT)


def test_after_an_add_the_stop_follows_the_new_average(v37, clock, now):
    """An add filled over the price (ask + 10c) lifts the average above the
    high; the stop 2c under the FIRST buy would let the whole position lose."""
    s = bought(v37, clock, now)
    tick(v37, s, now, round(s.v36_first + 0.10, 2))       # add, filled at +10c more
    assert s.v36_adds == 1
    assert s.stop == pytest.approx(s.entry - bot.V37_STOP_CENTS)
    tick(v37, s, now, round(s.entry - 0.03, 2))
    assert not s.in_position
