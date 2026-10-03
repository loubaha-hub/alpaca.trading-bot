"""
THE DAY ROLL - the halt baseline at midnight. Found in the live logs, fixed in
r32.py.

The day rolls at midnight ET, and at midnight Alpaca's last_equity is still
the close of the day BEFORE yesterday. On 2026-10-02 v31 rolled against
Wednesday's 22,649.31 with 20,263.54 in the account (Thursday's close), read
-10.5%, halted at 12:00am and never traded from 4am. Same on 10-01.
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

import bot
from helpers import FakeData

THU_CLOSE = 20_263.54
WED_CLOSE = 22_649.31          # what last_equity still says at midnight


class AccountClient:
    """Stands in for alpaca's TradingClient.get_account."""

    def __init__(self, equity, last_equity):
        self.equity = equity
        self.last_equity = last_equity

    def get_account(self):
        return SimpleNamespace(equity=str(self.equity),
                               last_equity=str(self.last_equity))


def real_broker(equity, last_equity):
    b = bot.Broker.__new__(bot.Broker)
    b.client = AccountClient(equity, last_equity)
    b.paper = True
    b.label = "v31"
    b._eq = 0.0
    b._eq_at = 0.0
    b.baseline_source = bot.DAY_BASELINE
    return b


def at(clock, y, mo, d, h, mi=0):
    clock.now = datetime(y, mo, d, h, mi, tzinfo=bot.ET)


@pytest.mark.parametrize("hour,minute", [(0, 0), (0, 1), (2, 30), (3, 59)])
def test_before_4am_the_baseline_is_the_live_equity(clock, hour, minute):
    at(clock, 2026, 10, 2, hour, minute)
    b = real_broker(THU_CLOSE, WED_CLOSE)
    assert asyncio.run(b.day_baseline()) == pytest.approx(THU_CLOSE)
    assert b.baseline_source == "equity before 4am"


def test_weekend_baseline_is_the_live_equity(clock):
    # Saturday 2026-10-03 midnight rolled against Thursday's close while
    # Friday's was in the account.
    at(clock, 2026, 10, 3, 0, 0)
    b = real_broker(19_124.40, 20_256.44)
    assert asyncio.run(b.day_baseline()) == pytest.approx(19_124.40)


@pytest.mark.parametrize("hour", [4, 10, 15, 19])
def test_in_session_a_restart_still_uses_last_equity(clock, hour):
    """The restart-proof rule stays: a noon restart after a 17% loss must not
    read the day as flat."""
    at(clock, 2026, 10, 2, hour)
    b = real_broker(equity=17_000.0, last_equity=THU_CLOSE)
    assert asyncio.run(b.day_baseline()) == pytest.approx(THU_CLOSE)
    assert b.baseline_source == "last_equity"


def test_no_live_equity_falls_back_to_last_equity(clock):
    at(clock, 2026, 10, 2, 1, 0)
    b = real_broker(equity=0, last_equity=THU_CLOSE)
    assert asyncio.run(b.day_baseline()) == pytest.approx(THU_CLOSE)


@pytest.mark.parametrize("cls", [bot.V31, bot.V34])
def test_midnight_roll_after_a_halted_day_does_not_halt(clock, cls):
    """Friday 2026-10-02 12:00am, replayed: Thursday ended halted at -10.5%.
    The new day must start at 0%, free to trade at 4am."""
    at(clock, 2026, 10, 1, 23, 59)
    strat = cls(real_broker(THU_CLOSE, WED_CLOSE), FakeData())
    strat.day = datetime(2026, 10, 1).date()
    strat.halted_today = True                 # Thursday really did halt
    strat.day_start_equity = 22_649.31

    at(clock, 2026, 10, 2, 0, 0)
    asyncio.run(strat.roll_day())

    assert strat.day == datetime(2026, 10, 2).date()
    assert strat.day_start_equity == pytest.approx(THU_CLOSE)
    assert not strat.halted_today
    limit = strat.day_start_equity * (1 - strat.halt_threshold())
    assert THU_CLOSE > limit                  # risk_loop's test: no halt
    assert asyncio.run(strat.halted()) is False

    at(clock, 2026, 10, 2, 4, 0)
    assert bot.entries_allowed()
