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
    monkeypatch.setattr(bot, "V36_ADD_HOLD_SEC", 0.0)    # the hold: tested below
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
    monkeypatch.setattr(bot, "V36_RIP_SKIPS_HOLD", False)
    s = ripping(v36, clock)
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)                          # just arrived at the top
    v36.crowd_since["ABCD"] = time.time() - 121
    tick(v36, s, TRIGGER)
    assert entered(v36, s)


def test_a_stock_ripping_now_is_the_crowd_without_the_hold(v36, clock, monkeypatch):
    """AIXI 4:17am 2026-10-06: #1 by $1.8M the minute it ripped - the 2-minute
    hold let v36 buy only from 4:19, and by then the pattern was gone."""
    monkeypatch.setattr(bot, "V36_CROWD_HOLD_MIN", 2)
    s = ripping(v36, clock)                               # the rip: the last 2 minutes
    assert v36.ripping_now(s)
    tick(v36, s, TRIGGER)
    assert entered(v36, s)


def test_an_older_rip_still_waits_for_the_hold(v36, clock, monkeypatch):
    monkeypatch.setattr(bot, "V36_CROWD_HOLD_MIN", 2)
    s = ripping(v36, clock)
    now = clock.now.astimezone(bot.timezone.utc) + bot.timedelta(minutes=2)
    feed_bars(v36, "ABCD", now, [(10.20, 10.30, 10.15, 10.25, 90_000)] * 2)
    assert not v36.ripping_now(s)
    assert not v36.in_crowd(s)


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


def test_prints_between_the_bid_and_ask_are_set_aside(v36, clock, monkeypatch):
    """2026-10-06: 41% at the ask, 27% at the bid, 32% between - the owner's
    "green outweighing red": 41 of 68 = 60%, a buy."""
    monkeypatch.setattr(bot, "V36_TAPE_GREEN", 0.60)
    s = ripping(v36, clock)
    tape(v36, s, at_ask=41, at_bid=27, bid=10.40, ask=10.42)
    for _ in range(32):
        v36.tape_add(s, 10.41, 100)                       # between
    assert v36.tape_ok(s)
    monkeypatch.setattr(bot, "V36_TAPE_MID_ASIDE", False)
    assert not v36.tape_ok(s)                             # 41% of all: no


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

def test_the_accounts_run_v36_v37_v36b():
    """The owner, 10-06: v36 over v31's account, v37 over "V30-100k" (v34's),
    and v36 with r34.13's changes (v36b) over AUES (v35's) in place of v35."""
    slots = bot.account_classes({})
    assert slots["v31"] is bot.V36 and slots["v34"] is bot.V37
    assert slots["v35"] is bot.V36B
    assert bot.account_classes({"SLOT_V35": "v35"})["v35"] is bot.V35


def test_each_account_can_be_switched_or_turned_off():
    slots = bot.account_classes({"SLOT_V31": "v31", "SLOT_V34": "off"})
    assert slots["v31"] is bot.V31 and slots["v34"] is None


# ---- the run lives as long as its volume (the owner, 10-06: no clock) --------------

def later(strat, clock, s, rows):
    """More closed candles after the setup, the clock moved to their end."""
    from datetime import timedelta
    clock.now = clock.now + timedelta(minutes=len(rows))
    feed_bars(strat, s.symbol, clock.now.astimezone(bot.timezone.utc), rows)


def test_a_run_still_trading_heavily_40_minutes_on_is_still_bought(v36, clock):
    """A 15-minute window would have refused this pullback."""
    s = ripping(v36, clock, pullback=False)
    climb = [(10.40 + 0.01 * i, 10.45 + 0.01 * i, 10.38 + 0.01 * i, 10.43 + 0.01 * i,
              100_000) for i in range(40)]                         # 2.5x the base
    later(v36, clock, s, climb + [(10.83, 10.84, 10.70, 10.72, 90_000)])   # a red
    assert v36.alive(s)
    tick(v36, s, 10.84)
    assert entered(v36, s)


def test_when_the_volume_dies_the_run_is_over(v36, clock):
    s = ripping(v36, clock, pullback=False)
    quiet = [(10.40, 10.42, 10.38, 10.41, 30_000)] * 10           # under the base
    later(v36, clock, s, quiet + [(10.41, 10.42, 10.35, 10.36, 30_000)])
    assert not v36.alive(s)
    tick(v36, s, 10.42)
    assert not entered(v36, s)


def test_the_high_of_the_day_break_needs_the_volume_to_pick_up(v36, clock):
    s = ripping(v36, clock, pullback=False)
    flat = [(10.40, 10.42, 10.38, 10.41, 120_000)] * 6
    later(v36, clock, s, flat + [(10.41, 10.47, 10.40, 10.46, 125_000),
                                 (10.46, 10.52, 10.45, 10.51, 130_000)])   # 1.1x
    tick(v36, s, 10.60)
    assert not entered(v36, s)


# ---- every re-entry starts small again ---------------------------------------------

def test_a_re_entry_starts_small_and_adds_again(v36, clock, broker, monkeypatch):
    monkeypatch.setattr(bot, "V36_REENTRY_SPEED", 0.0)    # the speed has its own test
    monkeypatch.setattr(bot, "V36_STARTER_RISK", 0.0)     # "B": its own test
    s = bought(v36, clock)
    tick(v36, s, round(s.v36_first * 1.031, 2))
    assert s.v36_adds == 1
    run(v36.exit(s, "test"))
    later(v36, clock, s, [(10.80, 11.30, 10.79, 11.25, 300_000),
                          (11.25, 11.90, 11.24, 11.85, 400_000)])   # a new rip, a new high
    tick(v36, s, round(s.hod_closed + 0.03, 2))           # 10-07: not under HOD + 5c
    assert s.v36_entries == 1
    tick(v36, s, round(s.hod_closed + bot.V36_HOD_PLUS + 0.01, 2))
    assert entered(v36, s)
    assert s.v36_entries == 2 and s.v36_adds == 0
    assert s.shares * s.entry == pytest.approx(
        broker.eq * bot.V36_POSITION_PCT * bot.V36_STARTER, rel=0.1)


@pytest.mark.parametrize("speed, buys", [(0.05, False), (0.15, True)])
def test_a_re_entry_needs_the_speed(v36, clock, monkeypatch, speed, buys):
    """10-07: "the speed is not respected" - a re-entry needs the owner's speed."""
    s = bought(v36, clock)
    run(v36.exit(s, "test"))
    later(v36, clock, s, [(10.80, 11.30, 10.79, 11.25, 300_000),
                          (11.25, 11.90, 11.24, 11.85, 400_000)])
    monkeypatch.setattr(v36, "real_speed", lambda s, p: speed)
    tick(v36, s, round(s.hod_closed + bot.V36_HOD_PLUS + 0.01, 2))
    assert entered(v36, s) == buys


def test_one_buy_a_minute_still_holds_after_400_candles(v36, clock):
    """Candles are capped at 400 a name; counting them stopped all re-entries
    from about 10:40am. The check is by time."""
    s = ripping(v36, clock, pullback=False)
    later(v36, clock, s, [(10.40, 10.42, 10.38, 10.41, 60_000)] * 420)
    assert len(s.bars) == 400
    s.v36_entry_bar_ts = s.bars[-2].ts                    # bought a minute ago
    assert s.bars[-1].ts > s.v36_entry_bar_ts             # so a new buy may come


def test_the_adds_come_at_15_and_20_cents(v36, clock, broker):
    """The owner, 10-06: 3% of a $10 stock is 30 cents before the first add -
    the run may be over by then."""
    s = bought(v36, clock)
    first = s.v36_first
    assert v36.add_level(s, 0) == pytest.approx(first + 0.15)
    assert v36.add_level(s, 1) == pytest.approx(first + 0.20)
    tick(v36, s, round(first + 0.14, 2))
    assert s.v36_adds == 0
    tick(v36, s, round(first + 0.16, 2))
    assert s.v36_adds == 1
    tick(v36, s, round(first + 0.21, 2))
    assert s.v36_adds == 2


# ---- why not (2026-10-06: v36 made no trades and said nothing about why) ----------

def test_a_why_not_line_names_the_check_that_said_no(v36, clock, caplog, monkeypatch):
    import logging
    s = ripping(v36, clock, rip_volume=(60_000, 70_000))  # no rip
    with caplog.at_level(logging.INFO):
        tick(v36, s, TRIGGER)
        tick(v36, s, TRIGGER)                             # the same minute: once
    lines = [r.getMessage() for r in caplog.records if "WHY-NOT" in r.getMessage()]
    assert len(lines) == 1
    assert "ABCD" in lines[0] and "NO PATTERN" in lines[0] and "crowd #1" in lines[0]


def test_at_the_trigger_the_refusal_is_logged_with_the_tape(v36, clock, caplog,
                                                          monkeypatch):
    import logging
    monkeypatch.setattr(bot, "V36_TAPE_GREEN", 0.60)
    s = ripping(v36, clock)
    tape(v36, s, at_ask=30, at_bid=70)
    with caplog.at_level(logging.INFO):
        tick(v36, s, TRIGGER)
    line = next(r.getMessage() for r in caplog.records if "WHY-NOT" in r.getMessage())
    assert "NO TAPE" in line and "ask 30%" in line and "bid 70%" in line


def test_names_outside_the_crowd_are_not_logged(v36, clock, caplog):
    import logging
    s = ripping(v36, clock, rip_volume=(60_000, 70_000))
    for sym, vol in (("BIGA", 3_000_000), ("BIGB", 2_500_000), ("BIGC", 2_000_000)):
        busier(v36, clock, sym, vol)
    with caplog.at_level(logging.INFO):
        tick(v36, s, TRIGGER)
    assert not any("WHY-NOT ABCD" in r.getMessage() for r in caplog.records)


# ---- 2026-10-06: the adds go right after a runner ---------------------------------

def test_a_missed_add_tries_again(v36, clock, broker, monkeypatch):
    """APUS 1:49pm 10-06: both adds missed (asks past the limit) and the misses
    used up the add steps - it rode the rip with 56 shares instead of ~540."""
    monkeypatch.setattr(bot, "V36_ADD_RETRY_SEC", 0.0)
    s = bought(v36, clock)
    first = s.v36_first
    real_buy, calls = v36.buy, []

    async def buy(symbol, shares, ref, cap):
        calls.append(ref)
        if len(calls) == 1:
            return 0                                      # the ask ran past the limit
        return await real_buy(symbol, shares, ref, cap)
    monkeypatch.setattr(v36, "buy", buy)
    tick(v36, s, round(first * 1.031, 2))
    assert s.v36_adds == 0                                # a miss is not an add
    tick(v36, s, round(first * 1.041, 2))                 # the next new high
    assert s.v36_adds == 1 and len(calls) == 2


def test_an_add_counts_from_the_ask_when_prints_lag(v36, clock, data, monkeypatch):
    got = []

    async def buy(symbol, shares, ref, cap):
        got.append((ref, cap))
        return 0
    s = bought(v36, clock)
    monkeypatch.setattr(v36, "buy", buy)
    data.quotes[("ABCD", "ask")] = round(s.v36_first * 1.08, 2)   # the market ran
    tick(v36, s, round(s.v36_first * 1.031, 2))
    assert got and got[0][0] == data.quotes[("ABCD", "ask")]


def test_a_ripping_add_may_pay_up_to_half_the_minute(v36, clock, monkeypatch):
    got = []

    async def buy(symbol, shares, ref, cap):
        got.append(cap)
        return 0
    s = bought(v36, clock)
    monkeypatch.setattr(v36, "buy", buy)
    monkeypatch.setattr(v36, "ripping", lambda s: True)
    monkeypatch.setattr(v36, "move", lambda s, p: 0.16)  # up 16% in the minute
    tick(v36, s, round(s.v36_first * 1.031, 2))
    assert got and got[0] == pytest.approx(0.08)         # half of it


def test_the_add_fixes_are_on():
    assert bot.V36_ADD_RETRY and bot.V36_ADD_FROM_ASK and bot.V36_ADD_RIP_PAY == 0.10


# ---- 2026-10-06: the score at v36's entries, the candles for the first buys ----------

def test_the_score_can_stop_a_v36_buy(v36, clock, monkeypatch):
    monkeypatch.setattr(bot, "V36_SCORE_MIN", 15)
    s = ripping(v36, clock)
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)


def test_a_light_pullback_scores_as_a_pullback(v36, clock):
    """The red candle is v36's pattern: light (smaller body, less volume than
    the green before it) is in its favour, not a no-buy."""
    s = ripping(v36, clock)
    points, parts = v36.score(s, TRIGGER, pullback=True)
    assert points is not None and "candle 2" in parts
    assert v36.score(s, TRIGGER)[0] is None               # v37's way: red, no buy


def test_a_rejection_wick_is_no_v36_buy(v36, clock):
    """APUS 1:51pm 10-06: the red candle before the buy had a 69% top wick -
    the top of the blow-off. Bought 8.15, added 8.30, out 8.23."""
    s = ripping(v36, clock)
    b = s.bars[-1]
    s.bars[-1] = bot.Bar(b.ts, b.o, b.o + 0.60, b.l, b.c, b.v)
    points, why = v36.score(s, TRIGGER, pullback=True)
    assert points is None and "wick" in why


def test_after_two_buys_only_the_high_of_the_day(v36, clock, monkeypatch):
    monkeypatch.setattr(bot, "V36_SETUP_BUYS", 2)
    s = ripping(v36, clock)
    s.v36_entries = 1
    assert v36.candles_allowed(s)
    s.v36_entries = 2
    s.mom_high_ts = time.time() - 600                     # a new high 10 minutes ago
    assert not v36.candles_allowed(s)
    assert v36.hod_plus(s)[0] == pytest.approx(s.hod_closed + 0.05)
    s.mom_high_ts = time.time() - 3 * 3600                # asleep for 3 hours
    assert v36.candles_allowed(s)


def test_the_new_entry_rules_are_off_until_the_owner_decides():
    assert bot.V36_SCORE_MIN == 0
    assert bot.V36_SETUP_BUYS == 1      # 10-07: re-entries past the high of the day


# ---- 2026-10-06, to test: fewer bad starters, smaller losses, fresh exits ---------

def test_a_wick_veto_stops_a_buy_after_a_rejection(v36, clock, monkeypatch):
    """APUS 1:51pm 10-06: the candle before the buy had a 69% top wick."""
    s = ripping(v36, clock)
    b = s.bars[-1]
    s.bars[-1] = bot.Bar(b.ts, b.o, b.o + 0.60, b.l, b.c, b.v)
    monkeypatch.setattr(bot, "V36_WICK_VETO", 0.6)
    tick(v36, s, TRIGGER)
    assert not entered(v36, s)
    monkeypatch.setattr(bot, "V36_WICK_VETO", 0.0)
    tick(v36, s, TRIGGER)
    assert entered(v36, s)


def test_the_first_stop_can_be_capped(v36, clock, monkeypatch):
    monkeypatch.setattr(bot, "V36_MAX_STOP", 0.03)
    s = bought(v36, clock)
    assert s.stop >= TRIGGER * 0.97 - 1e-9                # not the pullback's low (10.15)


def test_fresh_exits_skip_an_old_print(v36, clock, monkeypatch):
    monkeypatch.setattr(bot, "V36_FRESH_EXITS", True)
    s = bought(v36, clock)
    s.last_print_ts = time.time() - 7                     # APUS 11:32: a 7-second-old print
    tick(v36, s, round(s.stop - 0.05, 2))
    assert s.in_position                                  # the next fresh print decides
    s.last_print_ts = time.time()
    tick(v36, s, round(s.stop - 0.05, 2))
    assert not s.in_position


def test_the_v36_candidates_are_off_until_tested():
    assert not bot.V36_WICK_VETO and not bot.V36_MAX_STOP and not bot.V36_FRESH_EXITS


# ---- v36b: v36 with those three, on its own account (the owner, 10-06) -------------

@pytest.fixture
def v36b(data, clock, monkeypatch):
    from helpers import FakeBroker
    monkeypatch.setattr(bot, "V36_TAPE_GREEN", 0.0)
    monkeypatch.setattr(bot, "V36_CROWD_HOLD_MIN", 0)
    strat = bot.V36B(FakeBroker(equity=100_000.0), data)
    strat.day_start_equity = strat.broker.eq
    return strat


def test_v36b_vetoes_the_wick_v36_buys_in_the_same_process(v36, v36b, clock):
    """Both run in one process on one data feed: the setting is v36b's own."""
    for strat in (v36, v36b):
        s = ripping(strat, clock)
        b = s.bars[-1]
        s.bars[-1] = bot.Bar(b.ts, b.o, b.o + 0.60, b.l, b.c, b.v)
        tick(strat, s, TRIGGER)
    assert entered(v36, v36.state["ABCD"])
    assert not entered(v36b, v36b.state["ABCD"])


def test_v36b_caps_the_first_stop_v36_does_not(v36, v36b, clock):
    """A deep pullback (to 9.95, 4.4% under the trigger): v36's stop sits
    under it, v36b's no more than 3% under the trigger."""
    for strat in (v36, v36b):
        s = ripping(strat, clock)
        b = s.bars[-1]
        s.bars[-1] = bot.Bar(b.ts, b.o, b.h, 9.95, b.c, b.v)
        tick(strat, s, TRIGGER)
        assert entered(strat, s)
    assert v36.state["ABCD"].stop < TRIGGER * 0.97
    assert v36b.state["ABCD"].stop >= TRIGGER * 0.97 - 1e-9


def test_v36b_waits_for_a_fresh_print_v36_does_not(v36, v36b, clock):
    for strat in (v36, v36b):
        s = bought(strat, clock)
        s.last_print_ts = time.time() - 7
        tick(strat, s, round(s.stop - 0.05, 2))
    assert not v36.state["ABCD"].in_position
    assert v36b.state["ABCD"].in_position


def test_v36b_log_lines_say_v36b(v36, v36b):
    assert v36b.log.process("[v36] ABCD STARTER", {})[0] == "[v36b] ABCD STARTER"
    assert v36b.log.process("[v31] ENTER ABCD", {})[0] == "[v36b] ENTER ABCD"
    assert v36.log.process("[v36] ABCD STARTER", {})[0] == "[v36] ABCD STARTER"


# ---- 10-07, live: the owner's rules, checked trade by trade ------------------------

def red_after_rip(v36, clock, low=RED_LOW, volume=80_000):
    s = ripping(v36, clock, pullback=False)
    later(v36, clock, s, [(RED_OPEN, RED_OPEN + 0.02, low, 10.20, volume)])
    return s


@pytest.mark.parametrize("failed_rip, buys", [(True, False), (False, True)])
def test_a_red_that_erases_the_rip_is_no_pullback(v36, clock, monkeypatch,
                                                  failed_rip, buys):
    """SPAI 8:09: the red fell $4.92 -> $4.41, under the rip candle's open
    ($4.58) - a failed rip, bought as a pullback. False = as it was."""
    monkeypatch.setattr(bot, "V36_FAILED_RIP", failed_rip)
    s = red_after_rip(v36, clock, low=9.85)               # the rip candle opened 9.90
    tick(v36, s, TRIGGER)
    assert entered(v36, s) == buys


@pytest.mark.parametrize("pullback_vol, buys", [(1.0, False), (0.0, True)])
def test_a_red_heavier_than_the_rip_is_selling(v36, clock, monkeypatch,
                                               pullback_vol, buys):
    """The playbook: the pullback is light - less volume than the green."""
    monkeypatch.setattr(bot, "V36_PULLBACK_VOL", pullback_vol)
    s = red_after_rip(v36, clock, volume=250_000)         # the rip's green: 200k
    tick(v36, s, TRIGGER)
    assert entered(v36, s) == buys


@pytest.mark.parametrize("no_cap, buys", [(True, True), (False, False)])
def test_the_leader_making_a_new_high_is_not_capped(v36, clock, monkeypatch,
                                                    no_cap, buys):
    """LPCN 7:21-7:35: "NO: 6 buys today" every minute while the #1 name ran
    through $3.50 to $3.99. False = as it was."""
    monkeypatch.setattr(bot, "V36_LEADER_NO_CAP", no_cap)
    monkeypatch.setattr(bot, "V36_REENTRY_SPEED", 0.0)    # the speed has its own test
    s = ripping(v36, clock)
    s.v36_entries = bot.V36_MAX_ENTRIES
    tick(v36, s, round(s.hod_closed + bot.V36_HOD_PLUS + 0.12, 2))   # clear of $10.50
    assert entered(v36, s) == buys


def test_whole_and_half_dollars_wait_for_5_cents_held(v36, monkeypatch):
    """BIYA 4:20 (an add @ $2.51), LPCN 7:18 ($3.42), SPAI 8:12 (an add @ $5.08):
    "natural resistance - wait for it to cross, about 5 cents, a moment"."""
    now = [1_000.0]
    monkeypatch.setattr(bot.time, "time", lambda: now[0])
    s = v36.st("BIYA")
    assert v36.at_level(s, 2.51) and v36.at_level(s, 2.48)
    assert not v36.at_level(s, 2.45)                      # clear of it: its own trigger
    v36.at_level(s, 2.52)
    now[0] += 1
    assert v36.at_level(s, 2.56)                          # past, 1s after: hold on
    now[0] += 3
    assert not v36.at_level(s, 2.57)                      # held: go


def test_no_add_at_a_level(v36, clock, monkeypatch):
    s = bought(v36, clock)
    monkeypatch.setattr(v36, "at_level", lambda s, p: True)
    tick(v36, s, round(s.v36_first + 0.16, 2))
    assert s.v36_adds == 0


def test_a_runner_rides_until_half_the_run_is_given_back(v36, clock, monkeypatch):
    """The owner: once it runs, don't cut it until it has given back half of
    its gain - in place of the floor at the average and the 10s leash."""
    monkeypatch.setattr(bot, "V36_RUNNER_HALF", True)
    s = bought(v36, clock)
    first = s.v36_first
    tick(v36, s, round(first + 0.16, 2))
    assert s.v36_adds == 1 and s.stop < first             # no floor at the average
    tick(v36, s, round(first + 0.40, 2))
    tick(v36, s, round(first + 0.21, 2))                  # 19 of 40 given back
    assert s.in_position
    tick(v36, s, round(first + 0.19, 2))                  # more than half
    assert not s.in_position and v36.closed_today[-1][5] == "half"


def test_a_print_off_the_quote_sells_nothing(v36, clock):
    s = bought(v36, clock)
    s.quote = (round(s.entry + 0.05, 2), round(s.entry + 0.06, 2), bot.time.time())
    tick(v36, s, round(s.stop - 0.30, 2))                 # 30c under the stop, not the market
    assert s.in_position


def test_the_10_07_rules_are_on():
    assert bot.V36_SETUP_BUYS == 1 and bot.V36_HOD_PLUS == 0.05
    assert bot.V36_LEADER_NO_CAP and bot.V36_FAILED_RIP and bot.V36_PULLBACK_VOL == 1.0
    assert bot.V36_LEVELS and bot.V36_LEVEL_PAST == 0.05
    assert not bot.V36_RUNNER_HALF and bot.V36_REENTRY_SPEED == 0.1


@pytest.mark.parametrize("chase, buys", [(0.05, False), (0.0, True)])
def test_no_buy_far_over_the_trigger(v36, clock, monkeypatch, chase, buys):
    """SXTC 8:17: bought @ $4.83 on a $2.77 new-high trigger - 74% over it,
    after the spike; stop $2.21. 0.0 = as it was."""
    monkeypatch.setattr(bot, "V36_CHASE_MAX", chase)
    s = ripping(v36, clock)
    tick(v36, s, round(TRIGGER * 1.32, 2))           # clear of $13.50
    assert entered(v36, s) == buys


def test_an_acceleration_counts_as_the_crowd(v36, clock, monkeypatch):
    """10-07: SXTC 8:15 - "NO CROWD" at the #1 gainer with $800k."""
    monkeypatch.setattr(bot, "V36_ACCEL", False)          # as it was
    s = v36.st("SXTC")
    t = bot.datetime(2026, 10, 7, 12, 0, tzinfo=bot.timezone.utc)
    s.bars = [bot.Bar(t, 10.0, 10.02, 9.98, 10.0, 1_000) for _ in range(30)]
    s.bars += [bot.Bar(t, 10.00, 10.20, 9.98, 10.15, 38_000),
               bot.Bar(t, 10.15, 10.80, 10.15, 10.70, 114_000),
               bot.Bar(t, 10.70, 11.60, 10.60, 11.55, 261_000)]
    assert not v36.in_crowd(s)
    monkeypatch.setattr(bot, "V36_ACCEL", True)
    assert v36.in_crowd(s)


def test_a_restart_remembers_the_high_of_the_day(v36, clock, monkeypatch):
    """SXTC 10-07 9:29:39: after the 9:20 restart v36 bought $3.23 as a "new
    high" on a day already up to $7.12 - it knew only the candles since then."""
    monkeypatch.setattr(bot, "V36_REENTRY_SPEED", 0.0)
    s = bought(v36, clock)
    run(v36.exit(s, "test"))
    v36.seed_high(s, 15.00)                               # the morning's spike
    assert s.hod_closed == 15.00 and s.day_high >= 15.00
    later(v36, clock, s, [(10.80, 11.30, 10.79, 11.25, 300_000),
                          (11.25, 11.90, 11.24, 11.85, 400_000)])
    tick(v36, s, 11.97)                                   # over today's candles only
    assert not entered(v36, s)
    assert v36.hod_plus(s)[0] == pytest.approx(15.05)


# ---- the add waits for the new high to hold (the owner, 10-07 10:55am) -----------------

def test_an_add_waits_for_the_high_to_hold_two_seconds(v36, clock, monkeypatch):
    """APUS 10:25:08: added at $9.56, the floor moved to the average, sold 5
    seconds later. Now the price must stay at or over the add level 2 seconds."""
    monkeypatch.setattr(bot, "V36_ADD_HOLD_SEC", 2.0)
    now = [5_000.0]
    monkeypatch.setattr(bot.time, "time", lambda: now[0])
    s = bought(v36, clock)
    level = v36.add_level(s, 0)
    tick(v36, s, round(level + 0.01, 2))                  # the new high: the clock starts
    assert s.v36_adds == 0
    now[0] += 1.0
    tick(v36, s, round(level + 0.02, 2))                  # 1 second: not yet
    assert s.v36_adds == 0
    now[0] += 1.1
    tick(v36, s, round(level + 0.02, 2))                  # held 2.1 seconds: add
    assert s.v36_adds == 1


def test_a_dip_under_the_new_high_starts_the_clock_again(v36, clock, monkeypatch):
    monkeypatch.setattr(bot, "V36_ADD_HOLD_SEC", 2.0)
    now = [5_000.0]
    monkeypatch.setattr(bot.time, "time", lambda: now[0])
    s = bought(v36, clock)
    level = v36.add_level(s, 0)
    tick(v36, s, round(level + 0.02, 2))                  # a new high: the clock starts
    now[0] += 1.5
    tick(v36, s, round(level - 0.01, 2))                  # back under it: did not hold
    now[0] += 1.0
    tick(v36, s, round(level + 0.02, 2))                  # back to it - not a NEW high
    assert s.v36_adds == 0
    tick(v36, s, round(level + 0.03, 2))                  # a new high: a new clock
    now[0] += 2.1
    tick(v36, s, round(level + 0.03, 2))                  # held 2.1 seconds: add
    assert s.v36_adds == 1


def test_dki_no_add_on_the_way_down(v36, clock, monkeypatch):
    """DKI 11:36:39: bought $2.74, ran to $3.52; the add came at $3.33 on the way
    down (the level long passed, the hold met) - average $3.13, sold at $3.06."""
    monkeypatch.setattr(bot, "V36_ADD_HOLD_SEC", 2.0)
    now = [5_000.0]
    monkeypatch.setattr(bot.time, "time", lambda: now[0])
    s = bought(v36, clock)
    level = v36.add_level(s, 0)
    peak = round(level + 0.40, 2)
    tick(v36, s, peak)                                    # the run's high
    for k in range(1, 6):                                 # falling back, over the level
        now[0] += 1.0
        tick(v36, s, round(peak - 0.04 * k, 2))
    assert s.v36_adds == 0


def test_the_add_hold_is_on():
    assert bot.V36_ADD_HOLD_SEC == 2.0 and bot.V36_FLOOR_AVG   # the owner, 10-07


def test_dki_the_crowd_counts_the_minutes_it_traded(v36, clock):
    """DKI 10:37 and 10:50: "crowd #- $0k" right after a volatility halt - the
    last 5 clock minutes were the halt. The last 5 minutes it TRADED count."""
    s = v36.st("DKI")
    v36.qualified.add("DKI")
    halt_start = clock.now.astimezone(bot.timezone.utc) - bot.timedelta(minutes=12)
    s.bars = [bot.Bar(halt_start - bot.timedelta(minutes=5 - i), 2.4, 2.9, 2.3, 2.8, 500_000)
              for i in range(5)]                          # $1.4M a minute, then halted
    assert v36.crowd_dollars("DKI") == pytest.approx(5 * 2.8 * 500_000)
    v36.crowd = (None, {})
    bot_trading = bot.V36_CROWD_TRADING
    try:
        bot.V36_CROWD_TRADING = False
        assert v36.crowd_dollars("DKI") == 0.0            # as it was: $0k
    finally:
        bot.V36_CROWD_TRADING = bot_trading


@pytest.mark.parametrize("fast, buys", [(True, True), (False, False)])
def test_biya_820_speed_lifts_the_buy_cap(v36, clock, monkeypatch, fast, buys):
    """BIYA 8:20: "NO: 6 buys today" all through $2.54 -> $33.96 (crowd #4)."""
    monkeypatch.setattr(bot, "V36_LEADER_NO_CAP", False)
    monkeypatch.setattr(bot, "V36_REENTRY_SPEED", 0.0)
    monkeypatch.setattr(v36, "speeding", lambda s, p: fast)
    s = ripping(v36, clock)
    s.v36_entries = bot.V36_MAX_ENTRIES
    tick(v36, s, round(s.hod_closed + bot.V36_HOD_PLUS + 0.12, 2))
    assert entered(v36, s) == buys


def test_speed_counts_as_the_crowd(v36, clock, monkeypatch):
    s = v36.st("BIYA")
    v36.qualified.add("BIYA")
    monkeypatch.setattr(v36, "speeding", lambda s, p: False)
    assert not v36.in_crowd(s)
    monkeypatch.setattr(v36, "speeding", lambda s, p: True)
    assert v36.in_crowd(s)


def test_the_big_move_rules_are_on():
    assert bot.V36_TREND_LIVE and bot.V36_CROWD_TRADING and bot.V36_FURIOUS
    assert bot.V37_ACCEL_FROM_HIGH


def test_premarket_has_no_halts_the_crowd_is_the_clock(v36, clock):
    """The owner, 10-07: no halts premarket - the halt rule is 9:30-4:00 only."""
    clock.now = bot.datetime(2026, 10, 1, 7, 0, tzinfo=bot.ET)
    s = v36.st("DKI")
    v36.qualified.add("DKI")
    t0 = clock.now.astimezone(bot.timezone.utc) - bot.timedelta(minutes=12)
    s.bars = [bot.Bar(t0 - bot.timedelta(minutes=5 - i), 2.4, 2.9, 2.3, 2.8, 500_000)
              for i in range(5)]
    assert v36.crowd_dollars("DKI") == 0.0                # 12 quiet minutes: no crowd


@pytest.mark.parametrize("fast, buys", [(True, True), (False, False)])
def test_running_furiously_the_filters_step_aside(v36, clock, monkeypatch, fast, buys):
    """The owner, 10-07: "MACD, the EMAs, VWAP - all of that has to be tossed aside
    in a movement like this"."""
    monkeypatch.setattr(v36, "speeding", lambda s, p: fast)
    monkeypatch.setattr(v36, "trend_ok", lambda s, p: False)      # no trend
    s = ripping(v36, clock)
    tick(v36, s, TRIGGER)
    assert entered(v36, s) == buys


def test_five_seconds_of_prints(v36):
    s = v36.st("BIYA")
    s.last_print_ts = 100.0
    s.v37_prints.extend([(94.0, 3.00, 1000), (96.0, 3.10, 20_000), (99.0, 3.50, 30_000)])
    move, dollars = v36.five_sec(s, 3.50)
    assert move == pytest.approx(3.50 / 3.00 - 1)
    assert dollars == pytest.approx(3.10 * 20_000 + 3.50 * 30_000)


# ---- 10-07 ~12:20 (the owner, on DKI 11:37: a first stop 16.6% away, -$71) --------

def deep_pullback(strat, clock, low):
    """The ripping setup with the red's low at `low` - a far chart stop."""
    s = ripping(strat, clock)
    b = s.bars[-1]
    s.bars[-1] = bot.Bar(b.ts, b.o, b.h, low, b.c, b.v)
    return s


def test_b_a_far_stop_buys_fewer_shares(v36, clock, broker, monkeypatch):
    """B: the starter is sized so its first stop costs at most 3% of a normal
    starter - $75 on this $100,000 account's $2,500 starter."""
    monkeypatch.setattr(bot, "V36_LEVEL_STOP", False)     # the chart stop alone
    s = deep_pullback(v36, clock, 9.92)                   # 4.7% under the trigger
    tick(v36, s, TRIGGER)
    assert entered(v36, s)
    budget = broker.eq * bot.V36_POSITION_PCT * bot.V36_STARTER * bot.V36_STARTER_RISK
    assert s.shares == int(budget / (TRIGGER - 9.92))
    assert s.shares * s.entry < 0.7 * broker.eq * bot.V36_POSITION_PCT * bot.V36_STARTER


def test_b_a_near_stop_keeps_the_whole_starter(v36, clock, broker):
    s = bought(v36, clock)                                # the red's low, 2.5% under
    assert s.shares * s.entry == pytest.approx(
        broker.eq * bot.V36_POSITION_PCT * bot.V36_STARTER, rel=0.1)


def test_the_stop_sits_just_under_the_whole_dollar_under_the_buy(v36, clock, broker):
    """The owner: "it goes under three, you sell immediately - you don't wait
    for 2.87"."""
    s = deep_pullback(v36, clock, 9.92)
    tick(v36, s, TRIGGER)                                 # bought 10.41: the line is $10
    assert s.v36_line == 10.0
    assert s.stop == pytest.approx(10.0 - bot.V36_LEVEL_GIVE)
    budget = broker.eq * bot.V36_POSITION_PCT * bot.V36_STARTER * bot.V36_STARTER_RISK
    assert s.shares == int(budget / (TRIGGER - (10.0 - bot.V36_LEVEL_GIVE)))   # sized on it


def test_a_chart_stop_nearer_than_the_level_stays(v36, clock):
    s = bought(v36, clock)                                # the red's low 10.15 > 9.95
    assert s.stop == pytest.approx(RED_LOW)


def no_adds(monkeypatch):
    monkeypatch.setattr(bot, "V36_ADD1_AT", 5.0)
    monkeypatch.setattr(bot, "V36_ADD2_AT", 6.0)
    monkeypatch.setattr(bot, "V36_LEASH_AT", 10.0)


def test_held_past_the_next_half_dollar_the_stop_moves_up(v36, clock, monkeypatch):
    no_adds(monkeypatch)
    now = [5_000.0]
    monkeypatch.setattr(bot.time, "time", lambda: now[0])
    s = bought(v36, clock)
    tick(v36, s, 10.56)                                   # past $10.50 by 6c: the clock
    now[0] += 2.0
    tick(v36, s, 10.58)
    assert s.v36_line == 10.0                             # 2 seconds: not yet
    now[0] += 1.1
    tick(v36, s, 10.57)                                   # held 3.1 seconds
    assert s.v36_line == 10.5
    assert s.stop == pytest.approx(10.5 - bot.V36_LEVEL_GIVE)
    tick(v36, s, 10.49)                                   # 1c under: not yet
    assert s.in_position
    tick(v36, s, 10.48)                                   # 2c under: out at once
    assert not s.in_position


def test_a_print_under_starts_the_level_clock_again(v36, clock, monkeypatch):
    no_adds(monkeypatch)
    now = [5_000.0]
    monkeypatch.setattr(bot.time, "time", lambda: now[0])
    s = bought(v36, clock)
    tick(v36, s, 10.56)
    now[0] += 2.5
    tick(v36, s, 10.53)                                   # under $10.55: did not hold
    now[0] += 1.0
    tick(v36, s, 10.56)
    assert s.v36_line == 10.0
    now[0] += 3.1
    tick(v36, s, 10.56)
    assert s.v36_line == 10.5


def test_furious_the_full_position_on_the_first_hit(v36, clock, broker, monkeypatch):
    """The owner: "I enter with a full position on the very first hit". The
    adds are done; the stop no more than 8% under."""
    monkeypatch.setattr(v36, "speeding", lambda s, p: True)
    s = deep_pullback(v36, clock, 9.92)
    tick(v36, s, TRIGGER)
    assert entered(v36, s) and s.v36_furious
    assert s.shares * s.entry == pytest.approx(broker.eq * bot.V36_POSITION_PCT, rel=0.06)
    assert s.v36_adds == len(v36.add_steps())
    assert s.stop >= TRIGGER * (1 - bot.V36_FURIOUS_STOP_MAX) - 1e-9


@pytest.mark.parametrize("fast, buys", [(True, True), (False, False)])
def test_furious_buys_at_a_level(v36, clock, monkeypatch, fast, buys):
    """At $10.48, 2c under $10.50: no buy - unless furious."""
    monkeypatch.setattr(v36, "speeding", lambda s, p: fast)
    s = ripping(v36, clock)
    tick(v36, s, 10.48)
    assert entered(v36, s) == buys


@pytest.mark.parametrize("fast, buys", [(True, True), (False, False)])
def test_furious_needs_no_candle_pattern(v36, clock, monkeypatch, fast, buys):
    """A new high over the last minute is the trigger."""
    monkeypatch.setattr(v36, "speeding", lambda s, p: fast)
    monkeypatch.setattr(v36, "pullback_after", lambda s, j: None)
    monkeypatch.setattr(v36, "breaking_high", lambda s, p: None)
    s = ripping(v36, clock)
    tick(v36, s, round(max(s.hod_closed, s.bars[-1].h) + 0.02, 2))
    assert entered(v36, s) == buys


def test_furious_skips_the_wick_veto(v36b, clock, monkeypatch):
    monkeypatch.setattr(v36b, "speeding", lambda s, p: True)
    s = ripping(v36b, clock)
    b = s.bars[-1]
    s.bars[-1] = bot.Bar(b.ts, b.o, b.o + 0.60, b.l, b.c, b.v)   # a 70% top wick
    tick(v36b, s, TRIGGER)
    assert entered(v36b, s)


def furious_bought(v36, clock, monkeypatch):
    monkeypatch.setattr(v36, "speeding", lambda s, p: True)
    monkeypatch.setattr(bot, "V36_LEVEL_STOP", False)     # the levels: their own tests
    no_adds(monkeypatch)
    s = ripping(v36, clock)
    tick(v36, s, TRIGGER)
    assert s.in_position and s.v36_furious
    return s


def test_furious_up_30c_then_30_percent_of_the_gain_back_is_out(v36, clock, monkeypatch):
    """The owner, 10-07 ~1pm: past 30 cents over the buy, close it on giving
    back 30% of the gain from the high."""
    s = furious_bought(v36, clock, monkeypatch)
    entry = s.entry
    tick(v36, s, round(entry + 0.50, 2))                  # the high: +50c
    tick(v36, s, round(entry + 0.36, 2))                  # 28% of it back: held
    assert s.in_position
    tick(v36, s, round(entry + 0.34, 2))                  # 32% back: out
    assert not s.in_position
    assert v36.closed_today[-1][5] == "giveback"


def test_furious_up_30c_never_back_under_the_buy(v36, clock, monkeypatch):
    """The owner: "up thirty cents and back to it - cut it off there, instead
    of a loss"."""
    monkeypatch.setattr(bot, "V36_FURIOUS_GIVEBACK", 0.0)
    s = furious_bought(v36, clock, monkeypatch)
    entry = s.entry
    tick(v36, s, round(entry + 0.31, 2))
    tick(v36, s, round(entry + 0.01, 2))
    assert s.in_position
    tick(v36, s, round(entry - 0.01, 2))
    assert not s.in_position


def test_furious_under_30c_only_the_stop_and_the_leash(v36, clock, monkeypatch):
    s = furious_bought(v36, clock, monkeypatch)
    entry = s.entry
    tick(v36, s, round(entry + 0.25, 2))                  # +25c: not yet
    tick(v36, s, round(entry - 0.05, 2))                  # back under the buy: held
    assert s.in_position


def test_a_furious_position_sells_deep_premarket(v36, clock, monkeypatch):
    monkeypatch.setattr(v36, "speeding", lambda s, p: True)
    s = ripping(v36, clock)
    tick(v36, s, TRIGGER)
    seen = []
    real = v36.sell

    async def sell(symbol, shares, ref, deep=False):
        seen.append(deep)
        return await real(symbol, shares, ref, deep=deep)
    monkeypatch.setattr(v36, "sell", sell)
    run(v36.exit(s, "test"))
    assert seen == [True]


def test_the_owner_s_10_07_stop_rules_are_on():
    assert bot.V36_STARTER_RISK == 0.03 and bot.V36_LEVEL_STOP
    assert bot.V36_LEVEL_GIVE == 0.02                     # "5.98 or 5.99" (the owner)
    assert bot.V36_FURIOUS_FULL and bot.V36_FURIOUS_ALL and bot.V37_FURIOUS_EXIT
    assert bot.V36_FURIOUS_EVEN_AT == 0.30 and bot.V36_FURIOUS_GIVEBACK == 0.30


def test_the_scanner_list_is_logged(caplog):
    """The owner, 10-07: save the scanner's names through the day for the replay."""
    eng = bot.Engine.__new__(bot.Engine)
    eng.roster, eng.roster_all_at = set(), 0.0
    picks = {"ABCD": 3.10, "EFGH": 7.25}
    with caplog.at_level("INFO"):
        eng.log_roster(picks, list(picks))
        eng.log_roster({"ABCD": 3.20}, ["ABCD"])
    text = caplog.text
    assert "ROSTER 2 names | in: ABCD 3.10 EFGH 7.25 | out: -" in text
    assert "ROSTER ALL 2: ABCD 3.10 EFGH 7.25" in text
    assert "ROSTER 1 names | in: - | out: EFGH" in text


def test_bought_at_6_15_the_stop_is_5_98_not_5_80(v36, clock, monkeypatch):
    """The owner, 10-07: bought at $6.15, up to $6.30, coming back - the stop
    ends at $5.98, not at a $5.80 chart low."""
    monkeypatch.setattr(bot, "V36_FAILED_RIP", False)     # the deep red is allowed here
    s = ripping(v36, clock, scale=0.59)                   # the setup near $6
    b = s.bars[-1]
    s.bars[-1] = bot.Bar(b.ts, b.o, b.h, 5.80, b.c, b.v)  # the chart's low: $5.80
    tick(v36, s, 6.15)
    assert s.in_position and s.v36_line == 6.0
    assert s.stop == pytest.approx(6.0 - bot.V36_LEVEL_GIVE)
    tick(v36, s, 6.30)
    tick(v36, s, 5.99)
    assert s.in_position                                  # 1c under: not yet
    tick(v36, s, 5.98)
    assert not s.in_position
