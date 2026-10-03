"""
v31 TAPE (r29) - LOG ONLY. Every print is marked a buy (at or above the ask),
a sell (at or below the bid) or between, against a quote at most 2 seconds
old; otherwise by the tick rule. The split is logged at entries, trims, exits
and once a minute per open position. Nothing trades on it - the last tests
here pin that down.
"""

import logging
import time

import pytest

import bot
from helpers import breakout, hold, run

T = 1_000_000.0                       # a fixed clock for tape_add / tape_split


def marks(s):
    return [side for _t, _size, side, _q in s.tape]


# ---- marking each print ----------------------------------------------------------

def test_quote_rule_at_the_ask_bid_and_between(v31):
    s = v31.st("ABCD")
    s.quote = (9.98, 10.00, T)
    for price in (10.00, 10.05, 9.98, 9.95, 9.99):
        v31.tape_add(s, price, 100, now=T + 1)
    assert marks(s) == [1, 1, -1, -1, 0]
    assert all(q for *_x, q in s.tape)


def test_a_stale_quote_falls_back_to_the_tick_rule(v31):
    s = v31.st("ABCD")
    s.quote = (9.98, 10.00, T)
    v31.tape_add(s, 9.98, 100, now=T + 3)                 # quote 3s old
    v31.tape_add(s, 9.99, 100, now=T + 3)                 # uptick
    assert marks(s) == [0, 1]                             # first print: no direction yet
    assert not any(q for *_x, q in s.tape)


def test_tick_rule_up_down_and_same_price(v31):
    s = v31.st("ABCD")
    for price in (10.00, 10.01, 10.01, 10.00, 10.00):
        v31.tape_add(s, price, 100, now=T)
    assert marks(s) == [0, 1, 1, -1, -1]


def test_split_by_window(v31):
    s = v31.st("ABCD")
    v31.tape_add(s, 10.00, 300, now=T)                    # first print: no direction
    v31.tape_add(s, 10.01, 600, now=T + 250)              # uptick, no quote: buy
    s.quote = (9.98, 10.00, T + 291)                      # fresh for 2 seconds
    v31.tape_add(s, 10.00, 700, now=T + 291)              # at the ask: buy
    v31.tape_add(s, 9.98, 200, now=T + 292)               # at the bid: sell
    v31.tape_add(s, 9.99, 100, now=T + 293)               # inside: between
    assert v31.tape_split(s, 10, now=T + 295) == (700, 200, 100, 1000, 1.0)
    assert v31.tape_split(s, 60, now=T + 295) == (1300, 200, 100, 1600, 1000 / 1600)
    assert v31.tape_split(s, 300, now=T + 295)[3] == 1900


def test_prints_older_than_five_minutes_are_dropped(v31):
    s = v31.st("ABCD")
    v31.tape_add(s, 10.00, 100, now=T)
    v31.tape_add(s, 10.01, 100, now=T + 301)
    assert len(s.tape) == 1


def test_text(v31):
    s = v31.st("ABCD")
    now = time.time()
    s.quote = (9.98, 10.00, now)
    v31.tape_add(s, 10.00, 3_000, now=now)
    v31.tape_add(s, 9.98, 1_000, now=now)
    assert v31.tape_text(s, now=now) == (
        "tape 60s: buy 75% sell 25% between 0% of 4,000 sh (100% by quote) | "
        "5m: buy 75% sell 25% between 0% of 4,000 sh (100% by quote)")
    assert v31.tape_text(v31.st("EMPTY")) == "tape 60s: no prints | 5m: no prints"


# ---- the stream -------------------------------------------------------------------

def test_offer_tick_marks_against_the_quote_on_arrival(v31):
    v31.offer_quote("ABCD", 9.98, 10.00)
    v31.offer_tick("ABCD", 10.00, 500)
    assert marks(v31.st("ABCD")) == [1]
    assert v31.queue.qsize() == 1                         # and still queued for trading


def test_non_qualifying_prints_stay_off_the_tape(v31):
    bad = next(iter(bot.NON_QUALIFYING_CONDS))
    v31.offer_tick("ABCD", 10.00, 500, (bad,))
    assert len(v31.st("ABCD").tape) == 0


def test_a_crossed_or_empty_quote_is_ignored(v31):
    v31.offer_quote("ABCD", 10.01, 10.00)
    v31.offer_quote("ABCD", 0.0, 10.00)
    assert v31.st("ABCD").quote == ()


# ---- what gets logged ------------------------------------------------------------

def test_entry_logs_the_tape(v31, clock, caplog):
    s = breakout(v31, clock)
    caplog.set_level(logging.INFO, logger="engine")
    s.last_price = 10.01
    run(v31.evaluate(s, 10.01))
    assert s.in_position
    assert any("ABCD tape 60s" in r.getMessage() and "(buying)" in r.getMessage()
               for r in caplog.records)


def test_exit_logs_the_tape_with_the_reason(v31, caplog):
    s = hold(v31, "AAA", 1000, 10.0)
    caplog.set_level(logging.INFO, logger="engine")
    run(v31.exit(s, "trail"))
    assert any("AAA tape" in r.getMessage() and "(selling: trail)" in r.getMessage()
               for r in caplog.records)


def test_open_positions_log_the_tape_once_a_minute(v31, caplog):
    hold(v31, "AAA", 1000, 10.0)
    caplog.set_level(logging.INFO, logger="engine")
    run(v31.periodic())
    run(v31.periodic())
    lines = [r for r in caplog.records if r.getMessage().startswith("[v31] TAPE AAA")]
    assert len(lines) == 1


# ---- quotes are asked for the names v31 buys ---------------------------------------

class QuoteData:
    def __init__(self, data):
        self.inner, self.watched = data, []

    def __getattr__(self, name):
        return getattr(self.inner, name)

    async def watch_quotes(self, symbols):
        self.watched += list(symbols)


def test_buying_a_name_streams_its_quotes(v31, clock, data):
    v31.data = QuoteData(data)
    s = breakout(v31, clock)
    s.last_price = 10.01
    run(v31.evaluate(s, 10.01))
    assert v31.data.watched == ["ABCD"]


def test_tape_quotes_off(v31, clock, data, monkeypatch):
    monkeypatch.setattr(bot, "TAPE_QUOTES", "off")
    v31.data = QuoteData(data)
    s = breakout(v31, clock)
    s.last_price = 10.01
    run(v31.evaluate(s, 10.01))
    assert v31.data.watched == []


# ---- log only: nothing trades on it ---------------------------------------------

@pytest.mark.parametrize("side_price", [9.98, 10.00])     # all sells / all buys
def test_the_tape_changes_no_entry(v31, clock, broker, side_price):
    s = breakout(v31, clock)
    v31.offer_quote("ABCD", 9.98, 10.00)
    for _ in range(50):
        v31.offer_tick("ABCD", side_price, 10_000)
    s.last_price = 10.01
    run(v31.evaluate(s, 10.01))
    assert [o[1] for o in broker.buys("ABCD")] == [2172]


def test_the_tape_changes_no_exit(v31, broker):
    s = hold(v31, "AAA", 1000, 10.0)
    v31.offer_quote("AAA", 9.98, 10.00)
    for _ in range(50):
        v31.offer_tick("AAA", 9.98, 10_000)                # heavy selling
    s.last_price = 10.0
    run(v31.evaluate(s, 10.0))
    assert broker.held["AAA"] == 1000
