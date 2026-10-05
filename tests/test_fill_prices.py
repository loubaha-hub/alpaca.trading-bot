"""
r34.1 - an exit is booked at what the sale REALLY got, and names the print that
triggered it: price, size, condition codes and how old the print was.

2026-10-05, 4:06am ET: a QTEX print at 1.27 threw v31 and v34 out on the crash
guard while QTEX traded 1.40-1.52 (Webull's one-minute bars); its last 1.27 had
been at 4:02. The shares sold near 1.44 and the accounts barely moved, but the
EXIT lines said "@ 1.2700", -$311.68 and -$179.52 - and v35 decides whether to
buy a name back by whether its last trade there made money.
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import bot
from helpers import hold, run


def phantom(strat, data, *, bid=1.45, print_px=1.27, conds=("@", "U"), age=240):
    """QTEX held from 1.4309; the market bids 1.45; the last print says 1.27."""
    s = hold(strat, "QTEX", 1937, 1.4309)
    data.quotes[("QTEX", "bid")] = bid
    s.last_price, s.last_size, s.last_conds = print_px, 100, conds
    s.last_print_ts = time.time() - age
    return s


def test_an_exit_is_booked_at_the_sale_price_not_the_trigger_print(v31, data):
    s = phantom(v31, data)
    run(v31.exit(s, "crash"))
    sym, entry, exit_px, sold, pl, why = v31.closed_today[-1]
    assert (sym, sold, why) == ("QTEX", 1937, "crash")
    assert exit_px == pytest.approx(1.44)        # the sell limit, 1.45 x 0.995
    assert pl == pytest.approx((1.44 - 1.4309) * 1937)
    assert pl > 0                                # a winner, as the account saw it


def test_the_exit_line_shows_the_sale_price_and_the_print_behind_it(v31, data, caplog):
    s = phantom(v31, data)
    with caplog.at_level(logging.INFO):
        run(v31.exit(s, "crash"))
    line = next(r.getMessage() for r in caplog.records
                if "EXIT crash QTEX" in r.getMessage())
    assert "QTEX 1937 @ 1.4400" in line
    assert re.search(r"trigger print 1\.2700 x 100 cond \['@', 'U'\], 2[34]\d\.\ds old",
                     line), line
    assert "P/L +17.63" in line


def test_without_a_fill_price_the_exit_falls_back_to_the_print(v31, data, monkeypatch):
    s = phantom(v31, data)
    monkeypatch.setattr(v31.broker, "take_fill_price", lambda symbol: 0.0)
    run(v31.exit(s, "crash"))
    assert v31.closed_today[-1][2] == pytest.approx(1.27)


def test_fills_from_before_the_sale_are_not_counted_in_it(v31, data):
    """A partial buy left on the broker's record must not average into the
    sale price."""
    s = phantom(v31, data)
    v31.broker.fill_log["QTEX"] = [(500, 9.99)]
    run(v31.exit(s, "crash"))
    assert v31.closed_today[-1][2] == pytest.approx(1.44)


def test_v35_reads_the_real_result_when_deciding_to_buy_back(broker, data, clock):
    """The re-entry-after-a-winner rule reads closed_today's P/L."""
    v35 = bot.V35(broker, data)
    v35.day_start_equity = broker.eq
    s = phantom(v35, data)
    run(v35.exit(s, "crash"))
    assert v35.closed_today[-1][4] > 0


# ---- the broker remembers what each order really got ----------------------------------

class Client:
    """Alpaca's TradingClient, as far as Broker.send uses it."""

    def __init__(self, fills):
        self.fills = list(fills)                  # (filled_qty, filled_avg_price)

    def submit_order(self, req):
        return SimpleNamespace(id=len(self.fills))

    def get_order_by_id(self, oid):
        qty, avg = self.fills[0]
        return SimpleNamespace(filled_qty=str(qty), filled_avg_price=avg,
                               status="OrderStatus.FILLED")

    def cancel_order_by_id(self, oid):
        self.fills.pop(0)


def test_broker_send_remembers_each_fills_real_price():
    b = bot.Broker("key", "secret", True, "v31")
    b.client = Client([(1000, "1.4412"), (500, "1.4300")])
    assert run(b.send("QTEX", 1500, bot.OrderSide.SELL, 1.44)) == 1000   # partial
    assert run(b.send("QTEX", 500, bot.OrderSide.SELL, 1.43)) == 500
    assert b.take_fill_price("QTEX") == pytest.approx((1000 * 1.4412 + 500 * 1.43) / 1500)
    assert b.take_fill_price("QTEX") == 0.0       # taken: the next sale starts clean


def test_an_order_with_no_fill_leaves_no_price():
    b = bot.Broker("key", "secret", True, "v31")
    b.client = Client([(0, None)])
    assert run(b.send("QTEX", 100, bot.OrderSide.SELL, 1.44)) == 0
    assert b.take_fill_price("QTEX") == 0.0


# ---- the print's own time, from the stream to the exit line ---------------------------

def test_the_stream_hands_each_prints_time_to_the_strategy(v31):
    data = bot.MarketData.__new__(bot.MarketData)
    data.trade_sinks = [v31.offer_tick]
    at = datetime(2026, 10, 5, 8, 2, 0, tzinfo=timezone.utc)
    trade = SimpleNamespace(symbol="QTEX", price=1.27, size=100,
                            conditions=["@", "U"], timestamp=at)

    async def go():
        await data._on_trade(trade)
        worker = asyncio.create_task(v31.tick_worker())
        while not v31.queue.empty():
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        worker.cancel()

    run(go())
    s = v31.st("QTEX")
    assert s.last_price == pytest.approx(1.27)
    assert s.last_conds == ("@", "U")
    assert s.last_print_ts == pytest.approx(at.timestamp())


def test_a_print_without_a_time_says_so(v31):
    s = v31.st("QTEX")
    s.last_price, s.last_size, s.last_conds = 1.27, 100, ()
    assert v31.print_text(s) == "print 1.2700 x 100 cond -, age unknown"
