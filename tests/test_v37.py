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
        broker.eq * bot.V37_SOLO_PCT * bot.V37_STARTER, rel=0.05)


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
    full = broker.eq * bot.V37_SOLO_PCT
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


def test_no_daily_limit_on_buys(v37, clock, now):
    """The owner, 2026-10-06: no limit on buys per stock per day - 10 a day
    locked v37 out of AIXI's and SDEV's second legs."""
    s = bought(v37, clock, now)
    s.v36_entries = 50
    tick(v37, s, now, 10.30)                              # stopped out
    assert not s.in_position
    tick(v37, s, now, round(s.day_high + 0.01, 2))        # through the high
    assert s.in_position
    assert s.v36_entries == 51


def test_touching_the_high_is_not_a_new_high(v37, clock, now):
    """AIXI, 4:17am 2026-10-06: three buys in 8 seconds, all on 2.80."""
    s = bought(v37, clock, now)
    tick(v37, s, now, 10.30)                              # stopped out
    assert not s.in_position
    prints(v37, s, now, 10.00, 10.33)                     # ripping again
    tick(v37, s, now, s.day_high)                         # AT the high
    assert not s.in_position
    tick(v37, s, now, round(s.day_high + 0.01, 2))        # above it
    assert s.in_position


def old(s, now, seconds):
    """The next tick's print traded `seconds` before it is read."""
    s.last_print_ts = now[0] + 1 - seconds                # tick() adds 1 second


def test_no_buy_on_an_old_print(v37, clock, now):
    """AIXI, 4:18:14am 2026-10-06: a "new high" at 3.30, 40s+ old, filled at
    3.06 - the market had moved on while the prints queued."""
    s = ripping(v37, clock, now)
    old(s, now, 5)
    tick(v37, s, now, 10.36)
    assert not s.in_position
    old(s, now, 0.5)
    tick(v37, s, now, 10.37)
    assert s.in_position


def test_no_add_on_an_old_print(v37, clock, now):
    s = bought(v37, clock, now)
    first = s.v36_first
    old(s, now, 5)
    tick(v37, s, now, round(first + 0.10, 2))
    assert s.v36_adds == 0
    old(s, now, 0)
    tick(v37, s, now, round(first + 0.11, 2))
    assert s.v36_adds == 1


def test_speed_is_timed_by_when_the_prints_traded(v37, clock, now):
    """Thirty prints that traded over three minutes, read in three seconds
    (a queue drained after an order), are not a 3% move in 60 seconds."""
    s = crowd(v37, clock, "ABCD", 1_000_000)
    for i in range(30):
        now[0] += 0.1
        s.last_print_ts = now[0] - 6 * (29 - i)           # traded 6s apart
        px = round(10.00 + 0.35 * i / 29, 4)
        s.last_price = px
        v37.note_trade(s, px, 1_000)
    assert not v37.fast(s, 10.35)


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


# ---- size: 40% alone, 25% each for two --------------------------------------------

def test_alone_a_full_position_is_40_percent(v37, clock, now, broker):
    s = bought(v37, clock, now)
    tick(v37, s, now, round(s.v36_first + 0.10, 2))
    tick(v37, s, now, round(s.v36_first + 0.20, 2))
    assert s.shares * s.v36_first == pytest.approx(0.40 * broker.eq, rel=0.05)


def two(v37, clock, now, monkeypatch):
    """A at a full 40%, then B ripping beside it."""
    monkeypatch.setattr(bot, "V37_CROWD_TOP", 5)
    monkeypatch.setattr(bot, "V37_ASK_PLUS", 0.0)
    a = bought(v37, clock, now)
    tick(v37, a, now, round(a.v36_first + 0.10, 2))
    tick(v37, a, now, round(a.v36_first + 0.20, 2))
    b = ripping(v37, clock, now, symbol="BBBB")
    v37.crowd = (-1, {})
    tick(v37, b, now, 10.36)
    assert b.in_position
    return a, b


def pct(s, broker):
    return s.shares * s.last_price / broker.eq


def test_beside_a_40_percent_one_the_second_gets_what_is_left(v37, clock, now,
                                                            broker, monkeypatch):
    """The owner: 1%, then 5%, then 10% - 40 and 10 is 50."""
    a, b = two(v37, clock, now, monkeypatch)
    assert pct(a, broker) == pytest.approx(0.40, rel=0.06)
    assert pct(b, broker) == pytest.approx(0.01, rel=0.2)
    tick(v37, b, now, round(b.v36_first + 0.10, 2))
    assert pct(b, broker) == pytest.approx(0.05, rel=0.15)
    tick(v37, b, now, round(b.v36_first + 0.20, 2))
    assert pct(a, broker) + pct(b, broker) == pytest.approx(0.50, abs=0.02)


def test_if_the_second_keeps_running_both_end_at_25(v37, clock, now, broker,
                                                   monkeypatch):
    a, b = two(v37, clock, now, monkeypatch)
    tick(v37, b, now, round(b.v36_first + 0.10, 2))
    tick(v37, b, now, round(b.v36_first + 0.20, 2))
    assert pct(a, broker) > 0.35                          # not trimmed yet
    tick(v37, b, now, round(b.v36_first + 0.30, 2))       # it keeps running
    assert pct(a, broker) == pytest.approx(0.25, abs=0.015)
    assert pct(b, broker) == pytest.approx(0.25, abs=0.015)
    assert v37.closed_today[-1][5] == "make-room"


# ---- proposed 2026-10-06 (off until the owner decides): the leash sized to the speed --

@pytest.fixture
def leash(monkeypatch):
    monkeypatch.setattr(bot, "V37_STOP_SPEED", True)
    monkeypatch.setattr(bot, "V37_GIVEBACK_ARM", 0.03)
    monkeypatch.setattr(bot, "V37_ASK_PLUS", 0.0)          # fills at the price


def test_a_two_cent_wiggle_no_longer_shakes_it_out(v37, clock, now, leash):
    """IPDN, 8:11am 2026-10-06: seven buys at real new highs, each out within
    1-3 seconds on the 2c stop while the stock rose 10%."""
    s = bought(v37, clock, now)
    assert s.stop == pytest.approx(s.entry * (1 - bot.V37_STOP_MIN))
    tick(v37, s, now, round(s.entry - 0.05, 2))
    assert s.in_position
    tick(v37, s, now, round(s.stop - 0.01, 2))
    assert not s.in_position
    assert v37.closed_today[-1][5] == "stop"


def test_a_furious_stock_gets_a_longer_leash_up_to_8_percent(v37, clock, now, leash):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    prints(v37, s, now, 10.00, 11.40)                     # +14% in under a minute
    s.day_high = 10.05
    tick(v37, s, now, 11.45)
    assert s.in_position
    assert s.v37_stop_pct == pytest.approx(bot.V37_STOP_SHARE * (11.45 / 10.00 - 1))
    prints(v37, s, now, 10.00, 13.40)                     # +34%: capped
    assert v37.stop_pct(s, 13.45) == bot.V37_STOP_MAX


def test_half_the_gain_only_once_up_3_percent(v37, clock, now, leash, monkeypatch):
    monkeypatch.setattr(bot, "V37_ADD1_CENTS", 99.0)      # no adds: the average
    monkeypatch.setattr(bot, "V37_ADD2_CENTS", 99.0)      # stays the buy
    s = bought(v37, clock, now)
    e = s.entry
    tick(v37, s, now, round(e * 1.02, 2))                 # +2%: not armed
    tick(v37, s, now, round(e * 1.005, 2))                # gave back three quarters
    assert s.in_position
    tick(v37, s, now, round(e * 1.04, 2))                 # +4%: armed
    tick(v37, s, now, round(e * 1.019, 2))                # more than half back
    assert not s.in_position
    assert v37.closed_today[-1][5] == "giveback"


def test_after_an_add_the_stop_keeps_its_distance_under_the_average(v37, clock, now,
                                                                     leash):
    s = bought(v37, clock, now)
    pct = s.v37_stop_pct
    tick(v37, s, now, round(s.v36_first + 0.10, 2))       # add to half
    assert s.v36_adds == 1
    assert s.stop == pytest.approx(max(s.v36_first * (1 - pct), s.entry * (1 - pct)))


# ---- every buy above the real high of the day, even after a restart ----------------

def test_even_the_first_buy_needs_a_new_high_of_the_day(v37, clock, now):
    """IPDN, 8:11am 2026-10-06: after a restart, three buys (5.64, 5.69,
    5.83) on a day already up to 5.83."""
    s = ripping(v37, clock, now)
    s.day_high = 10.50                                    # the morning's high
    tick(v37, s, now, 10.36)                              # ripping, but under it
    assert not s.in_position
    tick(v37, s, now, 10.50)                              # at it
    assert not s.in_position
    tick(v37, s, now, 10.51)                              # through it
    assert s.in_position


class Bars:
    """MarketData.bars_between, as day_high_since_open uses it."""

    def __init__(self, highs, refuse_recent=False):
        self.highs, self.refuse_recent, self.asked = highs, refuse_recent, []

    async def bars_between(self, symbol, start, end):
        self.asked.append((start, end))
        if self.refuse_recent and len(self.asked) == 1:
            raise Exception("subscription does not permit querying recent SIP data")
        return [(start, 1.0, 100.0, h) for h in self.highs]


def at_et(hour, minute):
    return bot.datetime(2026, 10, 6, hour, minute, tzinfo=bot.ET).astimezone(
        bot.timezone.utc)


def test_the_day_high_comes_from_the_bars_since_4am():
    data = Bars([5.20, 5.83, 5.64])
    assert run(bot.day_high_since_open(data, "IPDN", at_et(8, 10))) == 5.83
    start, end = data.asked[0]
    assert start.astimezone(bot.ET).hour == 4 and start.astimezone(bot.ET).minute == 0


def test_refused_recent_bars_it_asks_again_without_them():
    data = Bars([5.83], refuse_recent=True)
    assert run(bot.day_high_since_open(data, "IPDN", at_et(8, 10))) == 5.83
    assert data.asked[1][1] == at_et(8, 10) - bot.timedelta(minutes=16)


def test_before_4am_there_is_no_day_high_yet():
    data = Bars([5.83])
    assert run(bot.day_high_since_open(data, "IPDN", at_et(3, 59))) == 0.0
    assert data.asked == []


# ---- proposed 2026-10-06 (off until the owner decides): flying means volume rising --

@pytest.fixture
def volume_rule(monkeypatch):
    monkeypatch.setattr(bot, "V37_VOL_RULE", True)


def minutes(v37, clock, now, vols, size=10_000):
    """Closed minutes on these share volumes at $10, then a rip whose last 60
    seconds trade 30 x `size` shares."""
    utc = clock.now.astimezone(bot.timezone.utc)
    feed_bars(v37, "ABCD", utc, [(10.0, 10.05, 9.95, 10.0, v) for v in vols])
    v37.qualified.add("ABCD")
    s = v37.st("ABCD")
    prints(v37, s, now, 10.00, 10.35, size=size)
    s.day_high = 10.05
    return s


def test_no_buy_after_three_candles_of_falling_volume(v37, clock, now, volume_rule):
    """IPDN 8:11-8:13am 2026-10-06: 497k, 446k, 242k - then a buy at 8:14:29."""
    s = minutes(v37, clock, now, [100_000, 100_000, 90_000, 80_000, 70_000])
    tick(v37, s, now, 10.36)
    assert not s.in_position


def test_rising_volume_buys(v37, clock, now, volume_rule):
    s = minutes(v37, clock, now, [100_000, 100_000, 70_000, 80_000, 90_000])
    tick(v37, s, now, 10.36)
    assert s.in_position


def test_no_buy_while_this_minute_trades_less_than_the_last(v37, clock, now,
                                                            volume_rule):
    s = minutes(v37, clock, now, [100_000, 100_000, 70_000, 80_000, 400_000])
    tick(v37, s, now, 10.36)                              # 300k now, 400k before
    assert not s.in_position


def test_no_buy_without_volume_well_over_the_minutes_before(v37, clock, now,
                                                            volume_rule):
    s = minutes(v37, clock, now, [250_000, 250_000, 150_000, 200_000, 290_000])
    tick(v37, s, now, 10.36)                              # 300k: not 1.5 x 212k
    assert not s.in_position


def test_out_when_the_volume_dries_up(v37, clock, now, volume_rule, monkeypatch):
    monkeypatch.setattr(bot, "V37_VOL_EXIT", 0.5)
    monkeypatch.setattr(bot, "V37_ASK_PLUS", 0.0)
    s = minutes(v37, clock, now, [100_000, 100_000, 70_000, 80_000, 90_000])
    tick(v37, s, now, 10.36)
    assert s.in_position
    now[0] += 45                                          # the rip's prints age out
    tick(v37, s, now, 10.37, size=100)
    assert not s.in_position
    assert v37.closed_today[-1][5] == "volume-gone"
