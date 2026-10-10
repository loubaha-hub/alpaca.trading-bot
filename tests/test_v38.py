"""
v38 - the speed strategy (the owner, 10-09 / 10-10; memory/words_v38.md): one
entry, the owner's speed; no high of the day, no candle pattern, no crowd, no
float limit; a limit at the ask + a cushion that grows with the speed; 10% /
25% at +10c / 50% at +20c; the floor at the last 1-minute candle's low (3c to
10%); nothing sold on the way up, the thirds once full; after the day is down
$500 smaller sizes and a separate top-up lot; two stocks at once.
"""

import logging

import pytest

import bot
from helpers import feed_bars, run


@pytest.fixture
def now(monkeypatch):
    t = [1_790_000_000.0]
    monkeypatch.setattr(bot.time, "time", lambda: t[0])
    return t


@pytest.fixture
def v38(broker, data, clock, now, monkeypatch):
    clock.set(7, 0)                                      # premarket unless a test moves it
    monkeypatch.setattr(bot, "V38_SEED_HISTORY", False)  # tested on its own below
    strat = bot.V38(broker, data)
    strat.day_start_equity = broker.eq
    return strat


def candles(strat, clock, symbol, low=9.90, n=3, red=False):
    """n closed minutes at $10 (the last one's low `low`), $1M each."""
    utc = clock.now.astimezone(bot.timezone.utc)
    rows = [(10.0, 10.05, 9.95, 10.02, 100_000)] * (n - 1)
    rows.append((10.02, 10.06, low, 9.98 if red else 10.04, 100_000))
    feed_bars(strat, symbol, utc, rows)
    strat.qualified.add(symbol)
    return strat.st(symbol)


def prints(strat, s, now, start, end, n, size, seconds):
    for i in range(n):
        now[0] += seconds / n
        px = round(start + (end - start) * i / max(1, n - 1), 4)
        s.last_price = px
        strat.note_trade(s, px, size)


def speeding(strat, clock, now, data, symbol="ABCD", base=10.00, top=10.40,
             before=3_000, after=30_000, low=9.90, red=False, quote=True):
    """A minute at `base` on `before` shares a print, then a minute rising to
    `top` on `after` shares a print (10 prints each) - move x ratio is the
    speed: +4% x 10 = 0.40 by default."""
    s = candles(strat, clock, symbol, low=low, red=red)
    prints(strat, s, now, base, base, 10, before, 59)
    prints(strat, s, now, base, top, 10, after, 59)
    if quote:
        data.quotes[(symbol, "bid")] = round(top - 0.01, 2)
        data.quotes[(symbol, "ask")] = top
    return s


def tick(strat, s, now, price, size=1_000):
    now[0] += 1
    s.last_price = price
    strat.note_trade(s, price, size)
    run(strat.evaluate(s, price))
    s.day_high = max(s.day_high, price)


# ---- the entry ---------------------------------------------------------------

def test_buys_on_the_speed_alone_far_under_the_high_of_the_day(v38, clock, now, data):
    """BIYA 10-07 8:20:37 - $2.65 under the 4am high of $3.10: the day's high
    blocked v36; v38 has no level."""
    s = speeding(v38, clock, now, data)
    s.day_high = s.hod_closed = 15.00
    tick(v38, s, now, 10.41)
    assert s.in_position and s.v38_kind == "speed"


def test_first_buy_is_ten_percent_of_the_account(v38, clock, now, data, broker):
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    assert s.shares * s.entry == pytest.approx(0.10 * broker.eq, rel=0.02)


def test_not_fast_enough_no_buy(v38, clock, now, data):
    s = speeding(v38, clock, now, data, top=10.10)       # +1%: under the 3% move
    tick(v38, s, now, 10.11)
    assert not s.in_position


def test_no_volume_rise_no_buy(v38, clock, now, data):
    s = speeding(v38, clock, now, data, before=30_000)   # +4% x 1 = 0.04
    tick(v38, s, now, 10.41)
    assert not s.in_position


def test_thin_no_buy(v38, clock, now, data):
    s = speeding(v38, clock, now, data, before=200, after=2_000)   # ~$200k a minute
    tick(v38, s, now, 10.41, size=100)
    assert not s.in_position


def test_last_candle_red_no_buy(v38, clock, now, data):
    s = speeding(v38, clock, now, data, red=True)
    tick(v38, s, now, 10.41)
    assert not s.in_position


def test_no_float_limit(v38, clock, now, data, monkeypatch):
    """WFF 10-09 (38.5M float, +$16,195 with the minute-wide floor): v36's
    20M limit would have kept it out."""
    monkeypatch.setattr(bot, "FLOATS", {"ABCD": 40_000_000})
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    assert s.in_position


def test_the_price_band_starts_at_fifty_cents(v38, clock, now, data):
    s = speeding(v38, clock, now, data, symbol="PENY", base=0.60, top=0.625,
                 before=30_000, after=600_000, low=0.59)
    tick(v38, s, now, 0.626, size=50_000)
    assert s.in_position
    s2 = speeding(v38, clock, now, data, symbol="SUBF", base=0.40, top=0.418,
                  before=30_000, after=600_000, low=0.39)
    tick(v38, s2, now, 0.419, size=50_000)
    assert not s2.in_position


def test_not_on_the_scanners_list_no_buy(v38, clock, now, data):
    s = speeding(v38, clock, now, data)
    v38.qualified.discard("ABCD")
    tick(v38, s, now, 10.41)
    assert not s.in_position


def test_a_wide_spread_no_buy(v38, clock, now, data):
    s = speeding(v38, clock, now, data)
    data.quotes[("ABCD", "bid")] = 10.20                 # 20c under the ask
    tick(v38, s, now, 10.41)
    assert not s.in_position


def test_sessions_setting(v38, clock, now, data, monkeypatch):
    """Real money: premarket only (V38_SESSIONS)."""
    monkeypatch.setattr(bot, "V38_SESSIONS", ("PRE",))
    clock.set(10, 0)
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    assert not s.in_position


# ---- the buy: the ask + the speed's cushion ------------------------------------

@pytest.mark.parametrize("speed,ask,cents", [
    (0.35, 3.00, 0.02), (0.60, 3.00, 0.05), (1.20, 3.00, 0.10), (2.50, 10.00, 0.20),
    (2.50, 3.00, 0.15),                                  # never over 5% of the price
    (0.35, 0.50, 0.02), (2.50, 0.60, 0.03)])
def test_the_cushion_scale(speed, ask, cents):
    assert bot.v38_cushion(speed, ask) == pytest.approx(cents)


def test_limit_prices_round_up_to_a_tick():
    assert bot.v38_price(2.0201) == 2.03
    assert bot.v38_price(10.40) == 10.40
    assert bot.v38_price(0.52341) == 0.5235


def test_the_first_buy_is_a_limit_at_the_ask_plus_the_cushion(v38, clock, now, data, broker):
    s = speeding(v38, clock, now, data)                  # speed 0.40: 2c
    tick(v38, s, now, 10.41)
    assert broker.buys("ABCD")[0][3] == pytest.approx(10.42)


def test_a_missed_buy_reprices_at_the_new_ask(v38, clock, now, data, broker):
    s = speeding(v38, clock, now, data)
    broker.fills = [0.0]                                 # the first order gets nothing
    tick(v38, s, now, 10.41)
    assert s.in_position and len(broker.buys("ABCD")) == 2


def test_the_first_buy_stops_past_the_safety_net(v38, clock, now, data, broker, monkeypatch):
    s = speeding(v38, clock, now, data)
    broker.fills = [0.0] * bot.V38_BUY_TRIES
    original = broker.send

    async def send(symbol, qty, side, limit, wait=None):
        data.quotes[(symbol, "ask")] = round(data.quotes[(symbol, "ask")] * 1.06, 2)
        data.quotes[(symbol, "bid")] = data.quotes[(symbol, "ask")] - 0.01
        return await original(symbol, qty, side, limit, wait)
    monkeypatch.setattr(broker, "send", send)
    tick(v38, s, now, 10.41)
    assert not s.in_position
    assert len(broker.buys("ABCD")) <= 3                 # 10.40 -> 11.02 -> 11.68: past +10%


# ---- the floor -----------------------------------------------------------------

def test_the_floor_is_the_last_candles_low(v38, clock, now, data):
    s = speeding(v38, clock, now, data, low=9.90)
    tick(v38, s, now, 10.41)
    assert s.stop == pytest.approx(9.90)


def test_the_floor_is_never_closer_than_3_cents(v38, clock, now, data):
    s = speeding(v38, clock, now, data, low=10.41)
    tick(v38, s, now, 10.41)
    assert s.stop == pytest.approx(s.entry - 0.03)


def test_the_floor_is_never_more_than_10_percent_under(v38, clock, now, data):
    s = speeding(v38, clock, now, data, low=8.00)
    tick(v38, s, now, 10.41)
    assert s.stop == pytest.approx(s.entry * 0.90)


def test_a_print_at_the_floor_sells_everything(v38, clock, now, data):
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    tick(v38, s, now, 9.89)
    assert not s.in_position


def test_the_market_at_the_floor_sells(v38, clock, now, data):
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    s.quote = (9.85, 9.90, now[0] + 1)                  # the middle under the floor
    tick(v38, s, now, 10.00)
    assert not s.in_position


# ---- the ease-in and the thirds ---------------------------------------------------

def test_adds_at_10_and_20_cents_to_25_and_50_percent(v38, clock, now, data, broker):
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    first = s.v38_first
    data.quotes[("ABCD", "ask")] = round(first + 0.10, 2)
    tick(v38, s, now, first + 0.10)
    assert s.v38_stage == 2
    assert s.shares * first == pytest.approx(0.25 * broker.eq, rel=0.03)
    data.quotes[("ABCD", "ask")] = round(first + 0.20, 2)
    tick(v38, s, now, first + 0.20)
    assert s.v38_stage == 3
    assert s.shares * s.entry == pytest.approx(0.50 * broker.eq, rel=0.03)


def test_after_an_add_the_floor_keeps_its_distance_under_the_average(v38, clock, now, data):
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    dist = s.entry - s.stop
    data.quotes[("ABCD", "ask")] = round(s.v38_first + 0.10, 2)
    tick(v38, s, now, s.v38_first + 0.10)
    assert s.stop == pytest.approx(s.entry - dist)


def full(v38, clock, now, data):
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    for step in (0.10, 0.20):
        data.quotes[("ABCD", "ask")] = round(s.v38_first + step, 2)
        tick(v38, s, now, s.v38_first + step)
    assert s.v38_stage == 3
    return s


def test_nothing_is_sold_on_the_way_up(v38, clock, now, data):
    s = full(v38, clock, now, data)
    shares = s.shares
    for px in (11.0, 12.0, 13.0, 14.0, 15.0):
        tick(v38, s, now, px)
    assert s.shares == shares


def test_the_thirds_off_the_peak(v38, clock, now, data):
    s = full(v38, clock, now, data)
    for px in (15.0, 20.0, 25.0):
        tick(v38, s, now, px)
    whole = s.shares
    tick(v38, s, now, 20.00)                             # 20% off $25
    assert s.shares == pytest.approx(whole - round(whole / 3), abs=1)
    tick(v38, s, now, 16.00)                             # not 40% yet
    assert s.v38_tier == 1
    tick(v38, s, now, 15.00)                             # 40% off
    assert s.v38_tier == 2
    assert s.shares == pytest.approx(whole - 2 * round(whole / 3), abs=2)
    tick(v38, s, now, 12.50)                             # 50% off - the rest
    assert not s.in_position


def test_the_floor_comes_first_when_it_is_over_a_third(v38, clock, now, data):
    """The floor (~10.07) is over 40% off a $16 peak ($9.60): whichever comes
    first - a drop to $9.60 sells everything at the floor."""
    s = full(v38, clock, now, data)
    for px in (12.0, 14.0, 16.0):
        tick(v38, s, now, px)
    tick(v38, s, now, 12.80)                             # 20% off $16: a third
    assert s.v38_tier == 1 and s.in_position
    tick(v38, s, now, 9.60)
    assert not s.in_position


# ---- two at once, the day's loss, the top-up -----------------------------------------

def test_two_stocks_at_once_a_third_is_not_bought(v38, clock, now, data, caplog):
    for sym in ("AAAA", "BBBB"):
        s = speeding(v38, clock, now, data, symbol=sym)
        tick(v38, s, now, 10.41)
        assert s.in_position
    s3 = speeding(v38, clock, now, data, symbol="CCCC")
    with caplog.at_level(logging.INFO):
        tick(v38, s3, now, 10.41)
    assert not s3.in_position
    assert "NO ROOM CCCC" in caplog.text


def test_after_the_day_is_down_500_the_sizes_shrink(v38, clock, now, data, broker):
    broker.eq = v38.day_start_equity - 600
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    assert s.v38_small
    assert s.shares * s.entry == pytest.approx(0.05 * broker.eq, rel=0.02)


def small_full(v38, clock, now, data, broker):
    broker.eq = v38.day_start_equity - 600
    s = full(v38, clock, now, data)
    assert s.v38_small and s.shares * s.entry == pytest.approx(0.25 * broker.eq, rel=0.03)
    return s


def test_the_top_up_is_a_separate_lot_to_50_percent(v38, clock, now, data, broker):
    s = small_full(v38, clock, now, data, broker)
    starter = s.shares
    px = round(s.v38_avg * 1.31, 2)
    data.quotes[("ABCD", "ask")] = px
    tick(v38, s, now, px)
    assert s.v38_top_sh > 0 and s.shares == starter + s.v38_top_sh
    assert s.shares * px == pytest.approx(0.50 * broker.eq, rel=0.05)
    assert s.v38_top_floor == pytest.approx(s.v38_top_px * 0.90)


def test_at_the_top_up_floor_only_the_top_up_is_sold(v38, clock, now, data, broker):
    s = small_full(v38, clock, now, data, broker)
    starter = s.shares
    px = round(s.v38_avg * 1.31, 2)
    data.quotes[("ABCD", "ask")] = px
    tick(v38, s, now, px)
    tick(v38, s, now, round(s.v38_top_floor - 0.01, 2))
    assert s.in_position and s.shares == starter and not s.v38_top_sh


def test_no_top_up_at_full_size(v38, clock, now, data):
    s = full(v38, clock, now, data)
    tick(v38, s, now, round(s.v38_avg * 1.35, 2))
    assert not s.v38_top_sh


# ---- the chug, the halt, the slot, the self-check, a restart --------------------------

def test_the_chug_buys_in_regular_hours(v38, clock, now, data, monkeypatch):
    clock.set(11, 0)
    utc = clock.now.astimezone(bot.timezone.utc)
    rows = [(10.0 + 0.06 * i, 10.06 + 0.06 * i, 9.98 + 0.06 * i, 10.05 + 0.06 * i, 30_000)
            for i in range(20)]
    feed_bars(v38, "CHUG", utc, rows)
    v38.qualified.add("CHUG")
    s = v38.st("CHUG")
    prints(v38, s, now, 11.20, 11.21, 10, 1_000, 59)     # no speed: a slow climb
    prints(v38, s, now, 11.21, 11.24, 10, 1_000, 59)
    data.quotes[("CHUG", "bid")], data.quotes[("CHUG", "ask")] = 11.25, 11.26
    tick(v38, s, now, 11.26)
    assert s.in_position and s.v38_kind == "chug"


def test_no_chug_in_premarket(v38, clock, now, data):
    utc = clock.now.astimezone(bot.timezone.utc)
    rows = [(10.0 + 0.06 * i, 10.06 + 0.06 * i, 9.98 + 0.06 * i, 10.05 + 0.06 * i, 30_000)
            for i in range(20)]
    feed_bars(v38, "CHUG", utc, rows)
    v38.qualified.add("CHUG")
    s = v38.st("CHUG")
    prints(v38, s, now, 11.20, 11.24, 20, 1_000, 118)
    data.quotes[("CHUG", "bid")], data.quotes[("CHUG", "ask")] = 11.25, 11.26
    tick(v38, s, now, 11.26)
    assert not s.in_position


def test_the_daily_shut_off_sells_and_stops(v38, clock, now, data, broker):
    s = speeding(v38, clock, now, data)
    tick(v38, s, now, 10.41)
    broker.eq = v38.day_start_equity * 0.89              # -11%
    tick(v38, s, now, 10.45)
    assert not s.in_position and v38.halted_today


def test_the_slot_runs_v38():
    assert bot.account_classes({"SLOT_V31": "v38"})["v31"] is bot.V38
    assert bot.account_classes({"SLOT_V35": "V38"})["v35"] is bot.V38


def test_a_full_position_is_no_self_check_violation(v38, clock, now, data, caplog):
    s = full(v38, clock, now, data)
    with caplog.at_level(logging.CRITICAL):
        run(v38.self_check())
    assert "VIOLATION" not in caplog.text


def test_a_restart_takes_the_position_over(v38, broker):
    broker.held["ABCD"] = 1_000.0
    broker.cost["ABCD"] = 10_000.0
    run(v38.reconcile("startup"))
    s = v38.st("ABCD")
    assert s.in_position and s.v38_stage == 3
    assert s.stop == pytest.approx(9.00)                 # 10% under


def test_the_last_two_minutes_are_read_for_a_new_name(v38, clock, now, data, monkeypatch):
    monkeypatch.setattr(bot, "V38_SEED_HISTORY", True)
    t0 = now[0]

    async def recent_trades(symbol, seconds):
        return ([(t0 - 110 + i, 10.00, 3_000, ()) for i in range(10)]
                + [(t0 - 50 + 5 * i, 10.00 + 0.04 * i, 30_000, ()) for i in range(10)])

    async def recent_bars(symbol, minutes):
        return [(t0 - 180, 10.0, 10.05, 9.95, 10.02, 100_000),
                (t0 - 120, 10.02, 10.06, 9.90, 10.04, 100_000)]
    data.recent_trades, data.recent_bars = recent_trades, recent_bars
    v38.qualified.add("NEWN")
    run(v38.seed_history(["NEWN"]))
    s = v38.st("NEWN")
    assert len(s.v37_speed_prints) == 20 and len(s.bars) == 2
    assert v38.v38_fast(s, 10.37)                        # the speed can fire at once
