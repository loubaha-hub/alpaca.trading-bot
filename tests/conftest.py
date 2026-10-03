"""
Loads the bot under test and provides the fakes every test shares.

WHICH FILE IS TESTED
  The bot gets a new file name every revision (r22.py, r23.py, ...). The tests
  always load the NEWEST one - the highest rNN.py in the repo root - so a new
  revision is tested without touching this file. To test a specific file:
      BOT_FILE=r22.py pytest
  The file in use is printed at the top of every run, with its VERSION string.

  Test modules reach it with `import bot`.

NOTHING HERE TOUCHES THE NETWORK
  Strategies take their broker and market data as arguments, so tests hand
  them FakeBroker and FakeData (tests/helpers.py) instead of Alpaca clients.
"""

import importlib.util
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# Settings the bot reads from the environment at import time. Cleared so the
# tests see the shipped defaults whatever the developer's shell has exported.
_BOT_ENV = ("CONFIRM_ENTRY_WITH_QUOTE", "DAY_BASELINE", "SIMPLE_STOP_REF",
            "SIMPLE_REENTRY_TICK", "BOOK_SECONDS", "PROBE_LOG", "ORPHAN_MODE",
            "V32_HALT_PCT", "V33_HALT_PCT", "V34_HALT_PCT")


def bot_path() -> Path:
    chosen = os.environ.get("BOT_FILE")
    if chosen:
        p = Path(chosen)
        return p if p.is_absolute() else REPO / p
    revisions = [(int(m.group(1)), p) for p in REPO.glob("r*.py")
                 if (m := re.fullmatch(r"r(\d+)\.py", p.name))]
    if not revisions:
        raise RuntimeError("no rNN.py file in %s to test" % REPO)
    return max(revisions)[1]


def _load_bot():
    path = bot_path()
    for name in _BOT_ENV:
        os.environ.pop(name, None)
    spec = importlib.util.spec_from_file_location("bot", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bot"] = module
    spec.loader.exec_module(module)
    return module


bot = _load_bot()


def pytest_report_header(config):
    return "bot under test: %s (VERSION %s)" % (bot_path().name, bot.VERSION)


# ---- fixtures ----------------------------------------------------------------

class Clock:
    """Stands in for the bot's datetime. Every datetime.now() inside the bot
    returns the time set here, converted to whatever zone was asked for."""

    def __init__(self, start: datetime):
        self.now = start
        clock = self

        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return clock.now.astimezone(tz) if tz else clock.now

        self.cls = FrozenDatetime

    def set(self, hour: int, minute: int = 0):
        self.now = self.now.replace(hour=hour, minute=minute)


@pytest.fixture
def clock(monkeypatch):
    """10:00am ET on Thursday 2026-10-01 unless a test moves it."""
    c = Clock(datetime(2026, 10, 1, 10, 0, tzinfo=bot.ET))
    monkeypatch.setattr(bot, "datetime", c.cls)
    return c


@pytest.fixture
def no_sleep(monkeypatch):
    """The real order code waits between polls. Tests do not."""
    import asyncio
    real = asyncio.sleep

    async def instant(_delay=0, result=None):
        return await real(0, result)

    monkeypatch.setattr(asyncio, "sleep", instant)


@pytest.fixture
def broker():
    from helpers import FakeBroker
    return FakeBroker(equity=100_000.0)


@pytest.fixture
def data():
    from helpers import FakeData
    return FakeData()


@pytest.fixture
def v31(broker, data, clock):
    """A v31 strategy on a fresh $100,000 account, day already started."""
    strat = bot.V31(broker, data)
    strat.day_start_equity = broker.eq
    return strat
