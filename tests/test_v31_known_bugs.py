"""
KNOWN v31 BUGS - each test states what SHOULD happen, and fails today.

Every test here is marked xfail(strict=True). That means:
  * today it fails, and the run reports it as "xfailed" - expected
  * the day a fix makes it pass, the run FAILS with "XPASS(strict)"
    -> delete the @known_bug line in the same change as the fix

So this file is the to-do list, and it cannot go stale.
"""

import asyncio
import time
from types import SimpleNamespace

import pytest

import bot
from helpers import breakout, feed_trades, hold, run


def known_bug(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


# ---- buy() can end up holding more than it asked for -------------------------

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
        return SimpleNamespace(qty=self.held)

    def still_working(self):
        return sum(o["qty"] - o["filled"] for o in self.orders.values() if o["open"])

    def market_fills_the_rest(self):
        while self.still_working():
            self._trade()


@known_bug("Broker.send returns on the first partial fill without cancelling the "
           "rest of the order (r23.py:465). buy() then sends another order for "
           "the remainder while the first is still working, and never cancels "
           "either. Likeliest cause of the QTEX 35%-of-equity starter.")
def test_buy_leaves_no_order_working_that_could_overfill(monkeypatch, data, no_sleep):
    client = WorkingOrdersClient()
    monkeypatch.setattr(bot, "TradingClient", lambda *a, **k: client)
    strat = bot.V31(bot.Broker("key", "secret", True, "v31"), data)

    run(strat.buy("ABCD", 1000, 10.0))
    client.market_fills_the_rest()

    assert client.held <= 1000


@known_bug("buy() counts a failed share-count read as 'nothing filled' "
           "(r23.py:979) and re-sends the FULL size on top of what already "
           "filled.")
def test_buy_survives_one_failed_position_read(v31, broker):
    broker.fills = [0.4]               # first order: 400 of 1,000
    broker.qty_fails_on = {3}          # the read right after it fails
    run(v31.buy("ABCD", 1000, 10.0))
    assert broker.held["ABCD"] <= 1000


# ---- two tasks acting on one position at once --------------------------------

@known_bug("add() runs from the tick handler (r23.py:1297) AND the rebalance "
           "(r23.py:1501), which are separate tasks. Both size the add from the "
           "same share count. Depending on timing either both buy (the account "
           "goes to 40%) or the second buy() counts the first one's fill as its "
           "own (here: broker 2,500 shares, memory 4,000). The `entering` guard "
           "covers only first entries, which can never overlap.")
def test_tick_add_and_rebalance_add_at_once(v31, broker):
    s = hold(v31, "AAA", 1000, 10.0)                 # $10,000 = 10%
    feed_trades(v31, "AAA", 9.0, 10.0)               # strong speed

    async def together():
        await asyncio.gather(v31.add(s, 10.0), v31.periodic())

    run(together())
    assert broker.held["AAA"] * 10.0 <= 25_000 * 1.001
    assert s.shares == broker.held["AAA"]


@known_bug("buy() and sell() both measure progress by the change in the broker's "
           "share count, so when an exit (tick task) and a rebalance add "
           "(periodic task) run on one name at once, each counts the other's "
           "fills as its own. Going flat from 1,000 shares here took 6 orders: "
           "4,000 bought and 5,000 sold, paying the spread on all of it.")
def test_exit_racing_an_add_does_not_churn(v31, broker):
    s = hold(v31, "AAA", 1000, 10.0, stop=9.50)
    feed_trades(v31, "AAA", 9.0, 10.0)

    async def together():
        await asyncio.gather(v31.periodic(), v31.exit(s, "flush"))

    run(together())
    bought = sum(o[4] for o in broker.buys("AAA"))
    assert bought <= 1500                            # the one add it planned


# ---- the entry is the trigger print, not what was paid -----------------------

@known_bug("The entry is recorded as the triggering print (r23.py:1375), but "
           "buy() may pay up to 2% above it. P/L and stop distance are measured "
           "from a price the account never paid.")
def test_entry_is_what_was_paid(v31, clock, data, broker):
    s = breakout(v31, clock)
    data.quotes[(s.symbol, "ask")] = 10.16          # market ran 1.5% past the print
    s.last_price = 10.01
    run(v31.evaluate(s, 10.01))
    assert s.in_position
    assert s.entry == pytest.approx(broker.avg_cost(s.symbol))


@known_bug("Sizing and the stop are worked out from the trigger print, so a fill "
           "above it risks more than 1% of equity: here $1,333 instead of $1,000.")
def test_loss_at_the_stop_from_the_real_fill_is_at_most_1_percent(v31, clock, data, broker):
    s = breakout(v31, clock, red_low=9.50)          # risk-sized: 1,960 shares
    data.quotes[(s.symbol, "ask")] = 10.16
    s.last_price = 10.01
    run(v31.evaluate(s, 10.01))
    paid = broker.avg_cost(s.symbol)
    assert broker.held[s.symbol] * (paid - s.stop) <= 0.01 * 100_000


@known_bug("add() never updates s.entry to the new average cost, so every P/L "
           "after an add is computed from the first fill only.")
def test_add_moves_the_entry_to_the_average_cost(v31, broker):
    s = hold(v31, "AAA", 1000, 12.0, entry=10.0)
    feed_trades(v31, "AAA", 11.0, 12.0)
    run(v31.add(s, 12.0))
    assert broker.held["AAA"] > 1000                # the add happened
    assert s.entry == pytest.approx(broker.avg_cost("AAA"))


# ---- the rebalance sells, and does not book it -------------------------------

@known_bug("After a restart the adopted position has no prints in memory, so its "
           "speed reads as zero, its rebalance target is $0, and the first "
           "rebalance (due immediately: last_rebalance starts at 0) sells it.")
def test_adopted_position_survives_the_first_rebalance(v31, broker):
    broker.held["AAA"], broker.cost["AAA"] = 500.0, 2_500.0
    run(v31.reconcile("startup"))
    assert v31.st("AAA").adopted
    run(v31.periodic())
    assert broker.held["AAA"] == 500


@known_bug("When the rebalance sells a position out entirely it goes through "
           "sell(), not exit(): no EXIT line, nothing in closed_today, and the "
           "old entry and stop stay in memory.")
def test_a_position_closed_by_the_rebalance_is_booked(v31, broker):
    s = hold(v31, "AAA", 1000, 10.0, stop=9.50)
    s.entry_at = time.time() - 600
    feed_trades(v31, "AAA", 10.0, 9.8)              # speed turned negative
    run(v31.periodic())
    if broker.held["AAA"] == 0:
        assert [c[0] for c in v31.closed_today] == ["AAA"]
        assert s.entry == 0 and s.stop == 0
