"""
v31 REGRESSIONS - bugs found in r23.py, fixed in r24.py. Each test states what
must happen and names what used to happen instead, so a fix cannot quietly
come undone.

To record a NEW known bug before fixing it, write the test the same way and
mark it @pytest.mark.xfail(strict=True, reason="..."). It then shows as
"xfailed" until the fix lands, and the strict setting makes the run fail the
moment it starts passing - remove the marker in the same change as the fix.
"""

import asyncio
import time
from types import SimpleNamespace

import pytest

import bot
from helpers import breakout, feed_trades, hold, run


# ---- buy() never ends up holding more than it asked for ----------------------

class WorkingOrdersClient:
    """Stands in for alpaca's TradingClient. A limit order fills a slice of its
    size every time any order is polled, and keeps working until cancelled -
    a resting order in a market that is still trading."""

    def __init__(self, slice_=0.3):
        self.slice = slice_
        self.orders = {}
        self.held = 0

    def _trade(self):
        for o in self.orders.values():
            if o["open"]:
                more = min(o["qty"] - o["filled"], max(1, int(o["qty"] * self.slice)))
                o["filled"] += more
                self.held += more
                if o["filled"] >= o["qty"]:
                    o["open"] = False

    def submit_order(self, req):
        oid = len(self.orders) + 1
        self.orders[oid] = {"qty": int(req.qty), "filled": 0, "open": True}
        return SimpleNamespace(id=oid)

    def get_order_by_id(self, oid):
        self._trade()
        o = self.orders[oid]
        return SimpleNamespace(filled_qty=o["filled"],
                               status="OrderStatus.FILLED" if not o["open"] else "OrderStatus.NEW")

    def cancel_order_by_id(self, oid):
        self.orders[oid]["open"] = False

    def get_orders(self, req):
        return [SimpleNamespace(id=k) for k, o in self.orders.items() if o["open"]]

    def get_open_position(self, symbol):
        if not self.held:
            raise Exception("position does not exist")
        return SimpleNamespace(qty=self.held, avg_entry_price=10.0)

    def still_working(self):
        return sum(o["qty"] - o["filled"] for o in self.orders.values() if o["open"])

    def market_fills_the_rest(self):
        while self.still_working():
            self._trade()


def test_buy_leaves_no_order_working_that_could_overfill(monkeypatch, data, no_sleep):
    """r23: Broker.send returned on the first partial fill without cancelling
    the rest, buy() sent another order for the remainder, and both kept
    filling - 1,000 asked, 1,890 held. Likeliest cause of QTEX at 35%."""
    client = WorkingOrdersClient()
    monkeypatch.setattr(bot, "TradingClient", lambda *a, **k: client)
    strat = bot.V31(bot.Broker("key", "secret", True, "v31"), data)

    run(strat.buy("ABCD", 1000, 10.0))
    assert client.still_working() == 0
    client.market_fills_the_rest()
    assert client.held <= 1000


def test_buy_survives_one_failed_position_read(v31, broker):
    """r23: a failed share-count read counted as 'nothing filled' and the
    FULL size was re-sent on top of a 400-share partial - 1,400 held."""
    broker.fills = [0.4]               # first order: 400 of 1,000
    broker.qty_fails_on = {3}          # the read right after it fails
    got = run(v31.buy("ABCD", 1000, 10.0))
    assert broker.held["ABCD"] == 1000
    assert got == 1000


def test_buy_does_not_buy_blind(v31, broker):
    """r23: an unreadable STARTING count was taken as 0, so anything already
    held was counted as a new fill."""
    broker.qty_fails_on = {1}
    assert run(v31.buy("ABCD", 1000, 10.0)) == 0
    assert broker.orders == []


def test_sell_survives_one_failed_position_read(v31, broker):
    """Same rule on the way out: a trim of 500 must not become 800 because
    one read in the middle failed."""
    hold(v31, "AAA", 2500, 10.0)
    broker.fills = [0.6]               # first sell: 300 of 500
    broker.qty_fails_on = {3}
    run(v31.sell("AAA", 500, 10.0))
    assert broker.held["AAA"] == 2000


# ---- two tasks acting on one position at once --------------------------------

def test_tick_add_and_rebalance_add_at_once(v31, broker):
    """r23: add() runs from the tick handler AND the rebalance, separate tasks.
    Both sized from the same share count: either both bought (40% of the
    account) or the second counted the first one's fill as its own (broker
    2,500 shares, memory 4,000)."""
    s = hold(v31, "AAA", 1000, 10.0)                 # $10,000 = 10%
    feed_trades(v31, "AAA", 9.0, 10.0)               # strong speed

    async def together():
        await asyncio.gather(v31.add(s, 10.0), v31.periodic())

    run(together())
    assert broker.held["AAA"] * 10.0 <= 25_000 * 1.001
    assert s.shares == broker.held["AAA"]


def test_exit_racing_an_add_does_not_churn(v31, broker):
    """r23: buy() and sell() each counted the other's fills as their own.
    Closing 1,000 shares took 6 orders: 4,000 bought, 5,000 sold."""
    s = hold(v31, "AAA", 1000, 10.0, stop=9.50)
    feed_trades(v31, "AAA", 9.0, 10.0)

    async def together():
        await asyncio.gather(v31.periodic(), v31.exit(s, "flush"))

    run(together())
    bought = sum(o[4] for o in broker.buys("AAA"))
    assert bought <= 1500                            # at most the one add
    assert broker.held["AAA"] == s.shares


def test_reconcile_leaves_an_order_in_flight_alone(v31, broker):
    """Reconciliation runs on its own clock. If it corrects the share count
    while an add is mid-fill, the add then adds its fill on top - counted
    twice. r24 skips a name whose lock is held."""
    s = hold(v31, "AAA", 1000, 10.0)
    feed_trades(v31, "AAA", 9.0, 10.0)
    fill = broker.send

    async def fill_then_reconcile(*order):
        got = await fill(*order)
        await v31.reconcile("periodic")     # lands after the fill, before add() books it
        return got

    broker.send = fill_then_reconcile
    run(v31.add(s, 10.0))
    assert s.shares == broker.held["AAA"]


# ---- the entry is what was paid ----------------------------------------------

def test_entry_is_what_was_paid(v31, clock, data, broker):
    """r23 recorded the triggering print as the entry, though buy() may pay
    up to 2% more. P/L and the stop were measured from a price never paid."""
    s = breakout(v31, clock)
    data.quotes[(s.symbol, "ask")] = 10.16          # market ran 1.5% past the print
    s.last_price = 10.01
    run(v31.evaluate(s, 10.01))
    assert s.in_position
    assert s.entry == pytest.approx(broker.avg_cost(s.symbol))


def test_loss_at_the_stop_from_the_real_fill_is_at_most_1_percent(v31, clock, data, broker):
    """r23 sized from the print, so a fill above it risked $1,333, not $1,000."""
    s = breakout(v31, clock, red_low=9.50)
    data.quotes[(s.symbol, "ask")] = 10.16
    s.last_price = 10.01
    run(v31.evaluate(s, 10.01))
    paid = broker.avg_cost(s.symbol)
    assert broker.held[s.symbol] * (paid - s.stop) <= 0.01 * 100_000


def test_add_moves_the_entry_to_the_average_cost(v31, broker):
    """r23 never updated the entry after an add, so P/L ignored the add."""
    s = hold(v31, "AAA", 1000, 12.0, entry=10.0)
    feed_trades(v31, "AAA", 11.0, 12.0)
    run(v31.add(s, 12.0))
    assert broker.held["AAA"] > 1000                # the add happened
    assert s.entry == pytest.approx(broker.avg_cost("AAA"))


# ---- the rebalance -----------------------------------------------------------

def test_adopted_position_survives_the_first_rebalance(v31, broker):
    """r23: after a restart the adopted position had no prints in memory, its
    speed read as zero, its target as $0, and the first rebalance - due the
    moment the process starts - sold it."""
    broker.held["AAA"], broker.cost["AAA"] = 500.0, 2_500.0
    run(v31.reconcile("startup"))
    assert v31.st("AAA").adopted
    run(v31.periodic())
    assert broker.held["AAA"] == 500


def test_a_position_closed_by_the_rebalance_is_booked(v31, broker):
    """r23 sold around exit(): no EXIT line, nothing in closed_today, and the
    old entry and stop left in memory."""
    s = hold(v31, "AAA", 1000, 10.0, stop=9.50)
    s.entry_at = time.time() - 600
    feed_trades(v31, "AAA", 10.0, 9.8)              # speed turned negative
    run(v31.periodic())
    assert broker.held["AAA"] == 0
    assert [c[0] for c in v31.closed_today] == ["AAA"]
    assert s.entry == 0 and s.stop == 0


def test_a_partial_trim_is_booked_too(v31, broker):
    s = hold(v31, "AAA", 3000, 10.0)                # 30%, above the 25% target
    s.entry_at = time.time() - 600
    feed_trades(v31, "AAA", 9.0, 10.0)
    run(v31.periodic())
    assert broker.held["AAA"] == 2500
    assert v31.closed_today and v31.closed_today[0][3] == 500
    assert s.shares == 2500 and s.entry == 10.0
