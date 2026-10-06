"""
FAST_BUY - buying a runner the way the owner does on hot keys, only faster.

2026-10-05, the owner: "put a new order and a new order until it gets,
especially when the stock is flying". The old chase left each limit working
about 2 seconds; a fast stock's ask is gone by then. Each limit now works
FAST_BUY_WAIT seconds, its cancel is CONFIRMED, and the next goes out at the
new ask - never two orders live at once, so never more shares than asked.

The same day: NU sized at 300 shares ended at 394. Shares filled between the
last poll and the cancel, the position read lagged, and the chase sent them
again. Broker.send now reads the cancelled order until it is closed and
returns what really filled.
"""

import logging
from types import SimpleNamespace

import pytest

import bot
from helpers import breakout, run

TRIGGER = 10.01            # breakout() default: red bar opens at 10.00, + 1 tick


# ---- Broker.send: what filled is known once the cancel is done -------------------------

class RacingClient:
    """Alpaca's TradingClient, as Broker.send and buy() use it. Nothing fills
    while the order is polled; shares fill AS it is cancelled (a fill racing
    the cancel), the order shows pending_cancel once, then canceled. The
    position read lags one call behind."""

    def __init__(self, race=0.4, pending=1):
        self.race, self.pending = race, pending
        self.orders = {}
        self.held = 0
        self.reported = 0                       # what the lagging read shows

    def submit_order(self, req):
        oid = len(self.orders) + 1
        self.orders[oid] = {"qty": int(req.qty), "filled": 0, "status": "new",
                            "pending": 0, "limit": req.limit_price}
        return SimpleNamespace(id=oid)

    def get_order_by_id(self, oid):
        o = self.orders[oid]
        if o["status"] == "pending_cancel":
            if o["pending"] <= 0:
                o["status"] = "canceled"
            o["pending"] -= 1
        return SimpleNamespace(filled_qty=str(o["filled"]), filled_avg_price=None,
                               status=SimpleNamespace(value=o["status"]))

    def cancel_order_by_id(self, oid):
        o = self.orders[oid]
        if o["status"] != "new":
            return
        more = int(o["qty"] * self.race)
        o["filled"] += more
        self.held += more
        o["status"], o["pending"] = "pending_cancel", self.pending

    def get_orders(self, req):
        return [SimpleNamespace(id=k) for k, o in self.orders.items()
                if o["status"] == "new"]

    def get_open_position(self, symbol):
        shown, self.reported = self.reported, self.held
        if not shown:
            raise Exception("position does not exist")
        return SimpleNamespace(qty=shown, avg_entry_price=10.0)


def test_send_returns_what_filled_during_the_cancel(no_sleep):
    b = bot.Broker("key", "secret", True, "v31")
    b.client = RacingClient(race=0.4)
    assert run(b.send("NU", 300, bot.OrderSide.BUY, 15.15, 0.4)) == 120
    assert b.settled


def test_an_order_never_confirmed_closed_is_flagged(no_sleep):
    b = bot.Broker("key", "secret", True, "v31")
    b.client = RacingClient(race=0.4, pending=99)
    run(b.send("NU", 300, bot.OrderSide.BUY, 15.15, 0.4))
    assert not b.settled


@pytest.mark.parametrize("fast", [True, False])
def test_a_lagging_position_read_never_overfills(monkeypatch, data, no_sleep, fast):
    """NU, 2026-10-05: 300 asked, 394 held."""
    monkeypatch.setattr(bot, "FAST_BUY", fast)
    client = RacingClient(race=0.4)
    monkeypatch.setattr(bot, "TradingClient", lambda *a, **k: client)
    strat = bot.V31(bot.Broker("key", "secret", True, "v31"), data)
    run(strat.buy("NU", 300, 15.15))
    assert client.held <= 300


# ---- buy(): reload until filled ------------------------------------------------------

def test_reloads_until_filled(v31, broker):
    broker.fills = [0.0, 0.0, 0.5]              # two misses, then half, then the rest
    assert run(v31.buy("ABCD", 1000, 10.0)) == 1000
    assert [o[1] for o in broker.buys("ABCD")] == [1000, 1000, 1000, 500]
    assert broker.held["ABCD"] == 1000


def test_each_reload_is_priced_off_the_new_ask(v31, broker, data, monkeypatch):
    data.quotes[("ABCD", "ask")] = 10.00
    real = broker.send

    async def send(symbol, qty, side, limit, wait=None):
        data.quotes[("ABCD", "ask")] = round(data.quotes[("ABCD", "ask")] + 0.05, 2)
        broker.fills = [0.0] if len(broker.orders) < 2 else []
        return await real(symbol, qty, side, limit, wait)

    monkeypatch.setattr(broker, "send", send)
    run(v31.buy("ABCD", 1000, 10.0))
    limits = [o[3] for o in broker.buys("ABCD")]
    assert limits == [10.02, 10.07, 10.12]      # ask + 0.2%, ask moving up 5c a try


def test_never_bids_over_the_ceiling(v31, broker, data, caplog):
    data.quotes[("ABCD", "ask")] = 10.50          # 5% over a 10.00 trigger
    broker.fills = [0.0] * 20
    with caplog.at_level(logging.INFO):
        assert run(v31.buy("ABCD", 1000, 10.0)) == 0
    assert all(o[3] == 10.20 for o in broker.buys("ABCD"))   # 2% cap, held there
    line = next(r.getMessage() for r in caplog.records if "BUY SHORT" in r.getMessage())
    assert "wanted 1000, got 0" in line and "past the ceiling" in line


def test_gives_up_after_its_tries(v31, broker):
    broker.fills = [0.0] * 50
    run(v31.buy("ABCD", 1000, 10.0))
    assert len(broker.buys("ABCD")) == bot.FAST_BUY_TRIES


def test_no_order_on_top_of_one_that_never_closed(v31, broker, monkeypatch):
    real = broker.send

    async def send(*a):
        got = await real(*a)
        broker.settled = False
        return got

    broker.fills = [0.3]
    monkeypatch.setattr(broker, "send", send)
    run(v31.buy("ABCD", 1000, 10.0))
    assert len(broker.buys("ABCD")) == 1


def test_a_full_fill_logs_no_miss(v31, broker, caplog):
    with caplog.at_level(logging.INFO):
        assert run(v31.buy("ABCD", 1000, 10.0)) == 1000
    assert not any("BUY SHORT" in r.getMessage() for r in caplog.records)


# ---- paying up on a fast stock (off until the playbook's volume guard exists) ---------

def test_the_ceiling_is_the_old_two_percent_while_off(v31, clock):
    s = breakout(v31, clock)
    assert bot.FAST_BUY_SPEED_CAP == 0.0
    assert v31.buy_cap(s, 10.0) == bot.BUY_CHASE_CAP


def test_on_a_fast_stock_the_ceiling_grows_with_its_speed(v31, clock, monkeypatch):
    monkeypatch.setattr(bot, "FAST_BUY_SPEED_CAP", 1.0)
    s = breakout(v31, clock)
    monkeypatch.setattr(v31, "abr", lambda s: 0.60)          # 6% a minute on $10
    assert v31.buy_cap(s, 10.0) == pytest.approx(0.06)
    monkeypatch.setattr(v31, "abr", lambda s: 2.00)          # 20% a minute
    assert v31.buy_cap(s, 10.0) == bot.FAST_BUY_CAP_MAX
    monkeypatch.setattr(v31, "abr", lambda s: 0.05)          # a slow one
    assert v31.buy_cap(s, 10.0) == bot.BUY_CHASE_CAP


# ---- the quote check's half cent (off until switched on) -----------------------------

def tick(strat, s, price):
    s.last_price = price
    run(strat.evaluate(s, price))


def test_half_a_cent_under_the_trigger_still_refuses_while_off(v31, clock, data):
    """RETO, 4:06am 2026-10-05: ask 1.99, trigger 1.9993 - refused 9 times."""
    s = breakout(v31, clock)
    data.quotes[(s.symbol, "ask")] = TRIGGER - 0.005
    tick(v31, s, TRIGGER)
    assert v31.broker.orders == []


def test_with_a_tolerance_half_a_cent_under_enters(v31, clock, data, monkeypatch):
    monkeypatch.setattr(bot, "CONFIRM_TOLERANCE", 0.01)
    s = breakout(v31, clock)
    data.quotes[(s.symbol, "ask")] = TRIGGER - 0.005
    tick(v31, s, TRIGGER)
    assert s.in_position


def test_with_a_tolerance_a_real_gap_still_refuses(v31, clock, data, monkeypatch):
    monkeypatch.setattr(bot, "CONFIRM_TOLERANCE", 0.01)
    s = breakout(v31, clock)
    data.quotes[(s.symbol, "ask")] = TRIGGER - 0.05
    tick(v31, s, TRIGGER)
    assert v31.broker.orders == []
