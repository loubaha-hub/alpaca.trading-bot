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
def v37(broker, data, clock, now, monkeypatch):
    # The tests below each test one rule; the volume rule and the stop sized
    # to the speed are tested with their own fixtures (volume_rule, leash).
    monkeypatch.setattr(bot, "V37_VOL_RULE", False)
    monkeypatch.setattr(bot, "V37_STOP_SPEED", False)
    monkeypatch.setattr(bot, "V37_REBUY_WAIT", 0.0)      # tested on its own below
    monkeypatch.setattr(bot, "V37_SPEED_MIN", 0.0)       # the speed: tested below
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


def test_again_only_at_a_new_high_of_the_day(v37, clock, now, monkeypatch):
    monkeypatch.setattr(bot, "V37_CONFIRM_BY_BUY", ())      # confirmation: tested below
    s = bought(v37, clock, now)
    tick(v37, s, now, 10.30)                              # stopped out
    assert not s.in_position
    prints(v37, s, now, 10.00, 10.33)                     # ripping again, under the high
    tick(v37, s, now, 10.34)
    assert not s.in_position
    tick(v37, s, now, round(s.day_high + 0.01, 2))        # through the high
    assert s.in_position


def test_no_daily_limit_on_buys(v37, clock, now, monkeypatch):
    monkeypatch.setattr(bot, "V37_CONFIRM_BY_BUY", ())      # confirmation: tested below
    """The owner, 2026-10-06: no limit on buys per stock per day - 10 a day
    locked v37 out of AIXI's and SDEV's second legs."""
    s = bought(v37, clock, now)
    s.v36_entries = 50
    tick(v37, s, now, 10.30)                              # stopped out
    assert not s.in_position
    tick(v37, s, now, round(s.day_high + 0.01, 2))        # through the high
    assert s.in_position
    assert s.v36_entries == 51


def test_touching_the_high_is_not_a_new_high(v37, clock, now, monkeypatch):
    monkeypatch.setattr(bot, "V37_CONFIRM_BY_BUY", ())      # confirmation: tested below
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


def test_a_runner_on_10x_8x_7x_its_normal_volume_still_buys(v37, clock, now,
                                                            volume_rule):
    assert bot.V37_VOL_FADE == 0.70                       # the owner's floor
    """The owner, 2026-10-06: volume 10x, 8x, 7x its normal, candles green,
    price running - "I would have bought there"."""
    normal = [10_000] * 25
    s = minutes(v37, clock, now, normal + [10_000, 10_000, 100_000, 80_000, 70_000],
                size=2_400)                               # 72k now: 7x normal
    tick(v37, s, now, 10.36)
    assert s.in_position


def test_no_buy_on_volume_that_is_normal_for_the_stock(v37, clock, now, volume_rule):
    s = minutes(v37, clock, now, [100_000] * 30, size=5_000)   # 150k: 1.5x normal
    tick(v37, s, now, 10.36)
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


def test_less_volume_but_a_faster_price_still_buys(v37, clock, now, volume_rule,
                                                   monkeypatch):
    monkeypatch.setattr(bot, "V37_VOL_PRICE", True)       # off by default
    """The owner, 2026-10-06: the last candle on less volume than the first
    two, but the price going up faster - the buyers are winning: buy."""
    normal = [10_000] * 25
    utc = clock.now.astimezone(bot.timezone.utc)
    feed_bars(v37, "ABCD", utc, [(10.0, 10.05, 9.95, 10.0, v) for v in normal]
              + [(10.0, 10.05, 9.95, 10.0, 10_000), (10.0, 10.05, 9.95, 10.0, 10_000),
                 (9.70, 9.85, 9.70, 9.80, 100_000),       # +1% on 100k
                 (9.80, 9.95, 9.80, 9.90, 80_000),
                 (9.90, 10.00, 9.90, 9.99, 70_000)])
    v37.qualified.add("ABCD")
    s = v37.st("ABCD")
    prints(v37, s, now, 10.00, 10.35, size=1_500)         # 45k: under half of 100k,
    s.day_high = 10.05                                    # but +3.5% in a minute
    tick(v37, s, now, 10.36)
    assert s.in_position


def test_less_volume_and_a_price_that_stalls_does_not_buy(v37, clock, now,
                                                          volume_rule):
    """IPDN 8:13am 2026-10-06: 242k after 497k, a red candle - no buy."""
    normal = [10_000] * 25
    utc = clock.now.astimezone(bot.timezone.utc)
    feed_bars(v37, "ABCD", utc, [(10.0, 10.05, 9.95, 10.0, v) for v in normal]
              + [(10.0, 10.05, 9.95, 10.0, 10_000), (10.0, 10.05, 9.95, 10.0, 10_000),
                 (9.00, 10.00, 9.00, 9.95, 100_000),      # +10.6% on 100k
                 (9.95, 10.00, 9.90, 9.98, 80_000),
                 (9.98, 10.00, 9.95, 9.99, 70_000)])
    v37.qualified.add("ABCD")
    s = v37.st("ABCD")
    prints(v37, s, now, 10.00, 10.35, size=1_500)         # 45k, +3.5%: slower
    s.day_high = 10.05
    tick(v37, s, now, 10.36)
    assert not s.in_position


def test_an_odd_lot_raises_the_high_but_never_buys(v37, clock, now):
    """IPDN 8:35am 2026-10-06: the chart's high 7.10 was an odd lot; v37 bought
    a round lot at 6.97 as "a new high"."""
    s = ripping(v37, clock, now)
    v37.note_skipped(s, 10.50, ("@", "I"))                # 12 shares at 10.50
    assert s.day_high == 10.50
    assert not s.in_position                              # it bought nothing
    tick(v37, s, now, 10.40)                              # a round lot under it
    assert not s.in_position
    tick(v37, s, now, 10.51)                              # above it
    assert s.in_position


def test_an_out_of_sequence_print_does_not_raise_the_high(v37, clock, now):
    s = ripping(v37, clock, now)
    v37.note_skipped(s, 10.50, ("@", "I", "Z"))           # odd lot AND out of sequence
    assert s.day_high == 10.05


def test_under_70_percent_of_the_busiest_minute_no_buy(v37, clock, now, volume_rule):
    """The owner, 2026-10-06: below 70% of the candles before, the stock is
    getting ready to come down."""
    normal = [10_000] * 25
    s = minutes(v37, clock, now, normal + [10_000, 10_000, 100_000, 80_000, 70_000],
                size=2_200)                               # 66k: 66% of 100k
    tick(v37, s, now, 10.36)
    assert not s.in_position


# ---- confirmation: a re-buy, or a break out of a sideways stretch --------------------

def candle(v37, clock, close, high=None, volume=50_000):
    """One more closed 1-minute candle."""
    utc = clock.now.astimezone(bot.timezone.utc)
    feed_bars(v37, "ABCD", utc, [(close - 0.02, high or close + 0.01, close - 0.03,
                                  close, volume)])


def test_a_re_buy_waits_for_a_candle_to_close_above_the_old_high(v37, clock, now,
                                                                 monkeypatch):
    """The owner, 2026-10-06: "the second buy, third buy - give it one or two
    more candles and the price going up before we buy"."""
    monkeypatch.setattr(v37, "fast", lambda s, p: True)
    s = bought(v37, clock, now)
    s.v36_entries = 3                                     # the next buy: the 4th
    tick(v37, s, now, 10.30)                              # sold
    old = s.v37_old_high
    assert old == s.day_high
    tick(v37, s, now, round(old + 0.02, 2))               # through it: not yet
    assert not s.in_position
    candle(v37, clock, round(old + 0.03, 2))              # one candle closes above it
    tick(v37, s, now, round(s.day_high + 0.01, 2))
    assert not s.in_position                              # one is not enough
    candle(v37, clock, round(s.day_high + 0.02, 2))       # the second
    tick(v37, s, now, round(s.day_high + 0.01, 2))        # and a new high: buy
    assert s.in_position


def test_a_candle_closing_back_under_the_old_high_does_not_confirm(v37, clock, now,
                                                                   monkeypatch):
    monkeypatch.setattr(v37, "fast", lambda s, p: True)
    s = bought(v37, clock, now)
    s.v36_entries = 3                                     # the next buy: the 4th
    tick(v37, s, now, 10.30)
    old = s.v37_old_high
    candle(v37, clock, round(old - 0.02, 2), high=round(old + 0.05, 2))   # a wick over
    tick(v37, s, now, round(s.day_high + 0.01, 2))
    assert not s.in_position


def test_extraordinary_volume_does_not_wait(v37, clock, now, monkeypatch):
    monkeypatch.setattr(v37, "fast", lambda s, p: True)
    s = bought(v37, clock, now)
    s.v36_entries = 3                                     # the next buy: the 4th
    tick(v37, s, now, 10.30)
    prints(v37, s, now, 10.20, 10.34, size=10_000)        # 300k: more than any minute
    tick(v37, s, now, round(s.day_high + 0.01, 2))
    assert s.in_position


def test_a_break_after_5_minutes_sideways_waits(v37, clock, now):
    """IPDN 8:21-8:35am 2026-10-06: under 6.97 for 15 minutes, then through
    it on volume it had already traded twice - "I would not have traded that"."""
    s = crowd(v37, clock, "ABCD", 1_000_000)
    s.v36_entries = 3                                     # a later run
    s.v37_high_ts = now[0] - 400                          # the last high: 6+ min ago
    prints(v37, s, now, 10.00, 10.35)
    s.day_high = max(s.day_high, 10.05)
    assert s.v37_old_high == 10.05                        # the sideways ceiling
    tick(v37, s, now, 10.36)
    assert not s.in_position
    candle(v37, clock, 10.37)                             # one candle
    candle(v37, clock, 10.40)                             # two: confirmed
    tick(v37, s, now, round(s.day_high + 0.01, 2))
    assert s.in_position


def test_a_fresh_run_does_not_wait(v37, clock, now):
    s = bought(v37, clock, now)                           # the first buy, mid-run
    assert s.in_position


def test_4_minutes_sideways_is_still_a_fresh_run(v37, clock, now):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    s.v37_high_ts = now[0] - 240
    prints(v37, s, now, 10.00, 10.35)
    s.day_high = max(s.day_high, 10.05)
    tick(v37, s, now, 10.36)
    assert s.in_position


def test_a_red_candle_over_the_old_high_does_not_confirm(v37, clock, now,
                                                         monkeypatch):
    """"The price still going up": the confirming candle closes green."""
    monkeypatch.setattr(v37, "fast", lambda s, p: True)
    s = bought(v37, clock, now)
    s.v36_entries = 3                                     # the next buy: the 4th
    tick(v37, s, now, 10.30)
    old = s.v37_old_high
    utc = clock.now.astimezone(bot.timezone.utc)
    feed_bars(v37, "ABCD", utc, [(old + 0.10, old + 0.12, old + 0.01, old + 0.03, 50_000)])
    tick(v37, s, now, round(s.day_high + 0.01, 2))
    assert not s.in_position


def test_the_second_buy_of_the_day_does_not_wait(v37, clock, now, monkeypatch):
    """The owner, 2026-10-06: "the first one and the second one, no way -
    that's where the money is"."""
    monkeypatch.setattr(v37, "fast", lambda s, p: True)
    s = bought(v37, clock, now)                           # the 1st
    tick(v37, s, now, 10.30)                              # sold
    tick(v37, s, now, round(s.v37_old_high + 0.02, 2))    # the 2nd: at once
    assert s.in_position


def test_the_third_buy_waits_one_candle(v37, clock, now, monkeypatch):
    monkeypatch.setattr(v37, "fast", lambda s, p: True)
    s = bought(v37, clock, now)
    s.v36_entries = 2                                     # the next buy: the 3rd
    tick(v37, s, now, 10.30)
    old = s.v37_old_high
    tick(v37, s, now, round(old + 0.02, 2))
    assert not s.in_position
    candle(v37, clock, round(old + 0.03, 2))              # one candle is enough
    tick(v37, s, now, round(s.day_high + 0.01, 2))
    assert s.in_position


def test_the_released_settings():
    """2026-10-06, replayed on every recorded day before release: the owner's
    rules - volume 2x normal with a 70% floor, the stop sized to the speed,
    confirmation 0-0-1-2 - 63% won with fills 0.2% worse, every day up."""
    assert bot.V37_VOL_RULE and bot.V37_VOL_REL == 2.0 and bot.V37_VOL_FADE == 0.70
    assert bot.V37_STOP_SPEED and not bot.V37_GIVEBACK_ARM
    assert bot.V37_CONFIRM_BY_BUY == (0, 0, 1, 2)


def test_the_speed_rule_is_held_off():
    """2026-10-06, the owner: keep "up 3% in a minute" and hold off on the
    speed rule (0.1+: 69 trades instead of 112 in the replay) - too few
    trades to judge from. The speed is logged on every buy meanwhile."""
    assert bot.V37_SPEED_MIN == 0.0 and bot.V37_FAST_PCT == 0.03


# ---- a re-buy right after a sale (the owner, 2026-10-06) -----------------------------

@pytest.fixture
def rebuy_wait(monkeypatch):
    monkeypatch.setattr(bot, "V37_REBUY_WAIT", 60.0)
    monkeypatch.setattr(bot, "V37_CONFIRM_BY_BUY", ())
    monkeypatch.setattr(bot, "V37_ASK_PLUS", 0.0)


def test_no_re_buy_within_a_minute_of_the_sale(v37, clock, now, rebuy_wait, monkeypatch):
    """65 of 2026-10-06's trades were bought back within 15 seconds of selling."""
    monkeypatch.setattr(v37, "fast", lambda s, p: True)
    s = bought(v37, clock, now)
    tick(v37, s, now, 10.30)                              # sold
    sold = s.v37_sold_px
    tick(v37, s, now, round(s.day_high + 0.01, 2))        # a new high, seconds later
    assert not s.in_position
    now[0] += 61
    tick(v37, s, now, round(s.day_high + 0.01, 2))        # a minute on: the rules as usual
    assert s.in_position
    assert sold > 0


def test_a_30_cent_jump_buys_back_at_once(v37, clock, now, rebuy_wait, monkeypatch):
    monkeypatch.setattr(v37, "fast", lambda s, p: True)
    s = bought(v37, clock, now)
    tick(v37, s, now, 10.30)
    tick(v37, s, now, round(s.v37_sold_px + 0.29, 2))     # not yet 30c
    assert not s.in_position
    tick(v37, s, now, round(s.v37_sold_px + 0.31, 2))     # "really cruising"
    assert s.in_position


def test_on_a_cheap_stock_the_jump_is_10_percent(v37, clock, now, rebuy_wait):
    s = bought(v37, clock, now)
    s.v37_sold_ts, s.v37_sold_px = now[0], 1.00
    assert v37.too_soon(s, 1.09)                          # 9c on a $1 stock: wait
    assert not v37.too_soon(s, 1.11)                      # 11c: 10% - buy
    s.v37_sold_px = 6.00
    assert v37.too_soon(s, 6.29) and not v37.too_soon(s, 6.31)   # $6: 30c


def test_a_stop_never_fires_on_an_old_print(v37, clock, now):
    """2026-10-06: 13 "stops" sold above the buy - each fired on a print
    tens of seconds old while the market was higher."""
    s = bought(v37, clock, now)
    old(s, now, 6)
    tick(v37, s, now, round(s.stop - 0.05, 2))            # under the stop, 6s old
    assert s.in_position
    old(s, now, 0)
    tick(v37, s, now, round(s.stop - 0.05, 2))            # the same, fresh
    assert not s.in_position


# ---- the owner's speed: (P2 - P1) / P1 x (V2 / V1) ----------------------------------

def windows(v37, s, now, p1, v1, p2, v2):
    """A minute of prints at p1 (v1 shares), then the last minute at p2 (v2
    shares) - each window's prints clear of the boundary between them."""
    T = now[0] + 200
    for k, (price, vol) in enumerate(((p1, v1), (p2, v2))):
        for i in range(10):
            now[0] = T - 115 + 60 * k + 6 * i
            s.last_price = price
            v37.note_trade(s, price, vol / 10)
    now[0] = T


def test_speed_is_the_price_move_times_the_volume_change(v37, clock, now):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    windows(v37, s, now, 10.00, 10_000, 11.00, 10_000)     # +10%, equal volume
    assert v37.speed(s, 11.00) == pytest.approx(0.10, abs=0.002)
    t = crowd(v37, clock, "EFGH", 1_000_000)
    windows(v37, t, now, 10.00, 10_000, 10.50, 20_000)     # +5%, double volume
    assert v37.speed(t, 10.50) == pytest.approx(0.10, abs=0.002)


def test_with_speed_on_a_slow_rise_is_not_flying(v37, clock, now, monkeypatch):
    monkeypatch.setattr(bot, "V37_SPEED_MIN", 0.10)
    s = crowd(v37, clock, "ABCD", 1_000_000)
    windows(v37, s, now, 10.00, 30_000, 10.30, 30_000)     # +3%, equal volume: 0.03
    s.day_high = 10.05
    assert v37.fast(s, 10.31)                              # flying by the old rule
    assert not v37.flying(s, 10.31)                        # not by the owner's speed
    windows(v37, s, now, 10.31, 30_000, 10.95, 60_000)     # +6%, double volume: 0.12
    assert v37.flying(s, 10.95)


def test_astronomical_volume_with_little_price_move_is_flying(v37, clock, now):
    """The owner: the price moved a little but the volume is twenty times
    bigger - "the stock is about to take off": 1% x 20 = 0.20."""
    s = crowd(v37, clock, "ABCD", 1_000_000)
    windows(v37, s, now, 10.00, 5_000, 10.10, 100_000)
    assert v37.speed(s, 10.10) == pytest.approx(0.20, abs=0.003)


def test_a_falling_price_is_never_flying(v37, clock, now, monkeypatch):
    monkeypatch.setattr(bot, "V37_SPEED_MIN", 0.10)
    s = crowd(v37, clock, "ABCD", 1_000_000)
    windows(v37, s, now, 10.00, 10_000, 9.90, 200_000)     # down 1% on 20x volume
    assert v37.speed(s, 9.90) < 0
    assert not v37.flying(s, 9.90)


def test_with_speed_on_it_buys_a_rip_on_rising_volume(v37, clock, now, monkeypatch):
    """The whole path, not just flying(): +6% on double the volume (0.12)
    over the day's high buys; the same rise on flat volume (0.06) does not."""
    monkeypatch.setattr(bot, "V37_SPEED_MIN", 0.10)
    s = crowd(v37, clock, "ABCD", 1_000_000)
    windows(v37, s, now, 10.00, 30_000, 10.60, 30_000)
    s.day_high = 10.30
    tick(v37, s, now, 10.61, size=100)
    assert not s.in_position
    t = crowd(v37, clock, "EFGH", 1_000_000)
    windows(v37, t, now, 10.00, 30_000, 10.60, 60_000)
    t.day_high = 10.30
    tick(v37, t, now, 10.61, size=100)
    assert t.in_position


# ---- proposed 2026-10-06 (off until the owner decides): a grace after the buy -------

@pytest.fixture
def grace(monkeypatch):
    monkeypatch.setattr(bot, "V37_GRACE_SECONDS", 15.0)
    monkeypatch.setattr(bot, "V37_STOP_SPEED", True)       # the 3-8% stop
    monkeypatch.setattr(bot, "V37_ASK_PLUS", 0.0)          # fills at the price
    monkeypatch.setattr(bot, "V37_ADD1_CENTS", 99.0)       # no adds: the average
    monkeypatch.setattr(bot, "V37_ADD2_CENTS", 99.0)       # stays the buy


def test_in_the_grace_a_wiggle_does_not_sell(v37, clock, now, grace):
    """APUS 11:36am 10-06: bought 7.47, peak 7.48, sold 4s later by "half
    the gain" - a cent of noise."""
    s = bought(v37, clock, now)
    e = s.entry
    tick(v37, s, now, round(e + 0.04, 2))
    tick(v37, s, now, round(e - 0.03, 2))                 # all the gain back, and more
    assert s.in_position


def test_in_the_grace_the_stop_still_sells(v37, clock, now, grace):
    s = bought(v37, clock, now)
    tick(v37, s, now, round(s.stop - 0.01, 2))
    assert not s.in_position
    assert v37.closed_today[-1][5] == "stop"


def test_after_the_grace_half_the_gain_counts_again(v37, clock, now, grace):
    s = bought(v37, clock, now)
    e = s.entry
    tick(v37, s, now, round(e + 0.20, 2))                 # the best: +20c, in the grace
    now[0] = s.entry_at + 16
    tick(v37, s, now, round(e + 0.12, 2))                 # still over half: kept
    assert s.in_position
    tick(v37, s, now, round(e + 0.09, 2))                 # under half of +20c: out
    assert not s.in_position
    assert v37.closed_today[-1][5] == "giveback"


def test_forget_counts_only_the_gain_after_the_grace(v37, clock, now, grace, monkeypatch):
    monkeypatch.setattr(bot, "V37_GRACE_FORGET", True)
    s = bought(v37, clock, now)
    e = s.entry
    tick(v37, s, now, round(e + 0.20, 2))                 # a spike inside the grace
    now[0] = s.entry_at + 16
    tick(v37, s, now, round(e + 0.04, 2))                 # the gain after it: +4c
    assert s.in_position                                  # the spike is forgotten
    tick(v37, s, now, round(e + 0.01, 2))                 # under half of +4c: out
    assert not s.in_position
    assert v37.closed_today[-1][5] == "giveback"


def test_the_grace_is_off_until_the_owner_decides():
    assert bot.V37_GRACE_SECONDS == 0.0 and not bot.V37_GRACE_FORGET


# ---- proposed 2026-10-06 (off until the owner decides): buy only while RUNNING -------

@pytest.fixture
def running(monkeypatch):
    monkeypatch.setattr(bot, "V37_MOMENTUM", True)


def candles(s, rows, quiet=1_000):
    """30 quiet minutes, then `rows` (o, h, l, c, v), the last one just closed."""
    t = bot.datetime(2026, 10, 6, 14, 0, tzinfo=bot.timezone.utc)
    s.bars = [bot.Bar(t, 10.0, 10.02, 9.98, 10.0, quiet) for _ in range(30)]
    s.bars += [bot.Bar(t, *r) for r in rows]


STAIRS = [(10.00, 10.10, 9.99, 10.09, 5_000), (10.09, 10.20, 10.05, 10.19, 6_000),
          (10.19, 10.32, 10.15, 10.31, 7_000)]         # green, full, rising, busy


def test_a_staircase_with_the_crowd_is_running(v37, clock, now, running):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, STAIRS)
    assert v37.not_running(s) == ""


def test_a_wick_on_the_candle_before_is_not_running(v37, clock, now, running):
    """The owner: "if it has a wick, the momentum is fizzling out"."""
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, STAIRS[:2] + [(10.19, 10.40, 10.15, 10.25, 7_000)])
    assert "wick" in v37.not_running(s)


def test_green_bodies_getting_smaller_is_not_running(v37, clock, now, running):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, STAIRS[:2] + [(10.19, 10.24, 10.17, 10.23, 7_000)])   # 4c after 10c
    assert "shrinking" in v37.not_running(s)


def test_a_red_candle_before_is_not_running(v37, clock, now, running):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, STAIRS[:2] + [(10.19, 10.22, 10.10, 10.12, 7_000)])
    assert "red" in v37.not_running(s)


def test_one_burst_out_of_quiet_is_not_running(v37, clock, now, running):
    """APUS 1:49pm 10-06: 134k, 124k, 47k shares a minute, then a 9% jump on
    608k - bought at 8.05, sold at 7.89 four seconds later."""
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, [(10.00, 10.10, 9.99, 10.09, 1_000), (10.09, 10.20, 10.05, 10.19, 1_200),
                (10.19, 10.32, 10.15, 10.31, 9_000)])
    assert "volume not staying up" in v37.not_running(s)


def test_a_true_rip_skips_the_checks(v37, clock, now, running):
    """XHG 9:39am 10-06: the minute before closed red, but 2.4M shares traded
    in a minute after 1.9M - more than any minute of its day."""
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, STAIRS[:2] + [(10.19, 10.22, 10.10, 10.12, 7_000)])
    prints(v37, s, now, 10.12, 10.40, size=1_000)          # 30,000 in the last minute
    assert v37.ripping(s)
    assert v37.not_running(s) == ""


def bought_unless_not_running(v37, clock, now, symbol):
    """Up 3.5% in a minute on $300k+, over the day's high, after a red
    candle on 50k shares - every old rule passes."""
    s = crowd(v37, clock, symbol, 1_000_000)
    candles(s, STAIRS[:2] + [(10.19, 10.22, 10.10, 10.12, 50_000)], quiet=40_000)
    s.day_high = 10.05
    prints(v37, s, now, 10.00, 10.35, size=1_000)
    tick(v37, s, now, 10.36)
    return s


def test_not_running_blocks_the_buy(v37, clock, now, monkeypatch):
    assert bought_unless_not_running(v37, clock, now, "ABCD").in_position
    monkeypatch.setattr(bot, "V37_MOMENTUM", True)
    assert not bought_unless_not_running(v37, clock, now, "EFGH").in_position


def test_steady_pays_little_over_the_price(v37, clock, now, monkeypatch):
    """The owner, 10-06: paying 2% over the price seen (APUS 8.05 vs 7.89) is
    for a stock that is ripping, not one going up steadily."""
    monkeypatch.setattr(bot, "V37_STEADY_PAY", 0.005)
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, STAIRS)
    prints(v37, s, now, 10.00, 10.40, size=10)             # +4%, a quiet minute
    assert v37.entry_cap(s, 10.40) == 0.005
    prints(v37, s, now, 10.40, 10.80, size=1_000)          # busier than any minute
    assert v37.entry_cap(s, 10.80) >= bot.V37_ENTRY_PCT


def test_running_and_steady_pay_are_off_until_the_owner_decides():
    assert not bot.V37_MOMENTUM and not bot.V37_STEADY_PAY


# ---- a restart remembers the day (2026-10-06) ------------------------------------------

def apus_morning(broker):
    """APUS 10-06 before the 10:21am release: bought 9:51 and 10:22, sold both."""
    t = lambda h, m, s: at_et(h, m).timestamp() + s
    broker.day_fills = [(t(9, 51, 39), "APUS", "buy", 84, 6.5352),
                        (t(9, 51, 52), "APUS", "sell", 84, 6.49),
                        (t(10, 22, 27), "APUS", "buy", 50, 6.8086),
                        (t(10, 22, 28), "APUS", "buy", 28, 6.81),     # same buy, 2nd order
                        (t(10, 22, 31), "APUS", "sell", 78, 6.7374)]


def test_a_restart_remembers_todays_buys_and_the_last_sale(v37, broker):
    """The 10:21 release forgot both: the 3rd and 4th buys (11:33, 11:36)
    waited for no candles. Now the 3rd waits for 1, above the old high."""
    apus_morning(broker)
    v37.data = Bars([6.97])                               # the high when it sold
    run(v37.restore_today())
    s = v37.st("APUS")
    assert s.v36_entries == 2                             # two buys, not three orders
    assert v37.confirm_bars(s) == 1
    assert s.v37_old_high == 6.97
    assert s.v37_sold_px == 6.7374
    assert not v37.confirmed(s)                           # no green candle over 6.97 yet


def test_adds_are_not_new_buys(v37, broker):
    t = at_et(9, 0).timestamp()
    broker.day_fills = [(t, "ABCD", "buy", 10, 10.0), (t + 30, "ABCD", "buy", 10, 10.1),
                        (t + 60, "ABCD", "sell", 20, 10.3), (t + 600, "ABCD", "buy", 10, 10.5)]
    v37.data = Bars([10.4])
    run(v37.restore_today())
    s = v37.st("ABCD")
    assert s.v36_entries == 2                             # bought twice; once added
    assert s.v37_sold_px == 10.3


def test_nothing_from_the_broker_changes_nothing(v37, broker):
    run(v37.restore_today())
    assert v37.st("APUS").v36_entries == 0


def test_the_broker_reads_todays_fills_page_by_page():
    from types import SimpleNamespace as NS
    t0 = at_et(9, 0)

    def order(i, qty):
        at = t0 + bot.timedelta(seconds=i)
        return NS(symbol="ABCD", side=bot.OrderSide.BUY, filled_qty=str(qty),
                  filled_avg_price="10.0", filled_at=at if qty else None, submitted_at=at)

    pages = [[order(1000 - i, 1) for i in range(500)], [order(5, 2), order(4, 0)]]

    class Client:
        asked = []

        def get_orders(self, req):
            self.asked.append(req.until)
            return pages[len(self.asked) - 1]

    b = object.__new__(bot.Broker)
    b.client, b.label = Client(), "test"
    got = run(b.fills_today())
    assert len(got) == 501                                # the unfilled order left out
    assert got[0][0] < got[-1][0] and got[0][2] == "buy"  # oldest first
    assert Client.asked[1] is not None                    # the second page asked for


# ---- proposed 2026-10-06 (off): the signs weighed, not pass/fail -------------------

def test_a_clean_staircase_scores_high(v37, clock, now):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, STAIRS)
    s.ema9, s.ema20, s.ema12, s.ema26 = 10.2, 10.1, 10.2, 10.1
    s.vwap_pv, s.vwap_v = 10.0, 1.0
    points, parts = v37.score(s, 10.35)
    assert points == 11, parts


def test_two_thirds_up_with_a_wick_is_still_favourable(v37, clock, now):
    """The owner: "sometimes they are not all close to the top - two thirds
    up, some wick - you look at other factors and you can still enter"."""
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, STAIRS[:2] + [(10.19, 10.40, 10.15, 10.31, 7_000)])   # wick 36%
    points, parts = v37.score(s, 10.41)
    assert points is not None and "candle 1" in parts


def test_a_huge_wick_on_the_last_candle_is_almost_a_stop(v37, clock, now):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, STAIRS[:2] + [(10.19, 10.60, 10.15, 10.24, 7_000)])   # wick 80%
    points, why = v37.score(s, 10.61)
    assert points is None and "huge" in why


def test_irregular_bodies_are_fine_steadily_shrinking_are_not(v37, clock, now):
    s = crowd(v37, clock, "ABCD", 1_000_000)
    candles(s, [(10.00, 10.21, 9.99, 10.20, 5_000), (10.20, 10.31, 10.18, 10.30, 6_000),
                (10.30, 10.46, 10.28, 10.45, 7_000)])              # 20c, 10c, 15c
    assert "bodies 1" in v37.score(s, 10.47)[1]
    candles(s, [(10.00, 10.21, 9.99, 10.20, 5_000), (10.20, 10.31, 10.18, 10.30, 6_000),
                (10.30, 10.36, 10.28, 10.35, 7_000)])              # 20c, 10c, 5c
    assert "bodies 0" in v37.score(s, 10.37)[1]


def test_the_score_is_off_until_the_owner_decides():
    assert bot.V37_SCORE_MIN == 0
