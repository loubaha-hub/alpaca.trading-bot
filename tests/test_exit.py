"""
THE EXIT - the owner, 2026-10-07: "the exit is the key - get out very quick,
at any price".

SXTC that morning, 9:30:16: v36's stop sent a limit sell that did not fill in
the opening seconds. Its cancel was not confirmed, and the chase sent eight
more sells in about four seconds - every one refused, the shares held for the
first - then did it all again, logging "unprotected", for 5.7 minutes while
SXTC fell from $3.03 to $2.85. Now: from 9:30 to 4:00 a sell goes out at
market, and a sell never goes out on top of our own working order.
"""

import logging
from types import SimpleNamespace

import pytest

import bot
from helpers import run


def at(clock, h, mi=0):
    clock.now = bot.datetime(2026, 10, 7, h, mi, tzinfo=bot.ET)


def holding(broker, sym="SXTC", n=133, px=3.23):
    broker.held[sym] = float(n)
    broker.cost[sym] = n * px


def test_a_stop_sells_at_market_in_regular_hours(v31, broker, clock):
    at(clock, 9, 30)
    holding(broker)
    assert run(v31.sell("SXTC", 133, 3.03)) == 133
    assert broker.market_orders == [("SXTC", 133, bot.OrderSide.SELL)]


@pytest.mark.parametrize("h, mi", [(7, 0), (9, 29), (16, 0), (19, 30)])
def test_outside_regular_hours_a_sell_is_a_limit(v31, broker, clock, h, mi):
    at(clock, h, mi)
    holding(broker)
    assert run(v31.sell("SXTC", 133, 3.03)) == 133
    assert broker.market_orders == []
    assert [o[2] for o in broker.orders] == [bot.OrderSide.SELL]


def test_no_sell_on_top_of_our_own_working_order(v31, broker, clock):
    """SXTC 9:30:22: 8 sells refused in 4 seconds. Now it waits, then one sell."""
    at(clock, 9, 30)
    holding(broker)
    broker.working = 3                          # the cancel takes a while
    assert run(v31.sell("SXTC", 133, 3.03)) == 133
    assert len(broker.orders) == 1 and broker.working == 0   # sent only once clear


def test_a_cancel_that_never_closes_sends_nothing_on_top(v31, broker, clock, caplog):
    at(clock, 9, 30)
    holding(broker)
    broker.working = 99
    with caplog.at_level(logging.CRITICAL):
        assert run(v31.sell("SXTC", 133, 3.03)) == 0
    assert broker.orders == []
    assert "STILL HOLDING" in caplog.text


def test_a_refused_market_order_falls_back_to_a_limit(v31, broker, clock, monkeypatch):
    at(clock, 12, 0)
    holding(broker)

    async def refused(symbol, qty, side, ref=0.0, wait=None):
        broker.market_orders.append((symbol, qty, side))
        broker.market_refused = True
        return 0
    monkeypatch.setattr(broker, "send_market", refused)
    assert run(v31.sell("SXTC", 133, 3.03)) == 133
    assert len(broker.market_orders) == 1 and len(broker.orders) == 1


@pytest.mark.parametrize("h, mi, ok", [(9, 28, True), (9, 29, False), (9, 30, False),
                                       (9, 31, True)])
def test_no_new_buys_around_the_opening_auction(clock, h, mi, ok):
    """SXTC 9:29:39: v36 bought 21 seconds before the open."""
    at(clock, h, mi)
    assert bot.entries_allowed() is ok


# ---- the real Broker -------------------------------------------------------------

class Client:
    """Alpaca's TradingClient as send_market and wait_clear use it."""

    def __init__(self, working=0):
        self.reqs, self.working = [], working

    def submit_order(self, req):
        self.reqs.append(req)
        return SimpleNamespace(id=1)

    def get_order_by_id(self, oid):
        q = self.reqs[-1].qty
        return SimpleNamespace(filled_qty=str(q), filled_avg_price="2.95",
                               status=SimpleNamespace(value="filled"))

    def cancel_order_by_id(self, oid):
        pass

    def get_orders(self, req):
        if self.working > 0:
            self.working -= 1
            return [SimpleNamespace(id=1)]
        return []


def test_send_market_is_a_market_order(no_sleep):
    b = bot.Broker("key", "secret", True, "v36")
    b.client = Client()
    assert run(b.send_market("SXTC", 133, bot.OrderSide.SELL, 3.0)) == 133
    req = b.client.reqs[0]
    assert isinstance(req, bot.MarketOrderRequest)
    assert req.time_in_force == bot.TimeInForce.DAY and not req.extended_hours
    assert not b.market_refused
    assert b.take_fill_price("SXTC") == pytest.approx(2.95)


@pytest.mark.parametrize("working, clear", [(3, True), (999, False)])
def test_wait_clear_waits_for_our_cancelled_order(no_sleep, working, clear):
    b = bot.Broker("key", "secret", True, "v36")
    b.client = Client(working=working)
    assert run(b.wait_clear("SXTC")) is clear


class PartialClient(Client):
    """A market order that fills in pieces, as a crashing stock's bids do."""

    def __init__(self, steps):
        super().__init__()
        self.steps, self.cancels = list(steps), 0

    def get_order_by_id(self, oid):
        q = self.reqs[-1].qty
        if self.cancels:                                  # cancelled: what filled stays
            return SimpleNamespace(filled_qty=str(self.got), filled_avg_price="7.29",
                                   status=SimpleNamespace(value="canceled"))
        self.got = self.steps.pop(0) if self.steps else q
        return SimpleNamespace(filled_qty=str(self.got), filled_avg_price="7.29",
                               status=SimpleNamespace(value="filled" if self.got >= q
                                                      else "partially_filled"))

    def cancel_order_by_id(self, oid):
        self.cancels += 1


def test_a_market_sell_is_left_to_fill(no_sleep):
    """SXTC 10-07 1:40pm: each market sell was cancelled after its first partial
    fill and sent again - 7.5 seconds and three orders to get out."""
    b = bot.Broker("key", "secret", True, "v37")
    b.client = PartialClient([100, 300, 500])
    assert run(b.send_market("SXTC", 625, bot.OrderSide.SELL, 7.3)) == 625
    assert b.client.cancels == 0 and len(b.client.reqs) == 1


def test_a_limit_buy_still_stops_at_a_partial_fill(no_sleep):
    b = bot.Broker("key", "secret", True, "v37")
    b.client = PartialClient([100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100,
                              100, 100, 100, 100])
    assert run(b.send("SXTC", 625, bot.OrderSide.BUY, 7.95, 0.5)) == 100
    assert b.client.cancels == 1
