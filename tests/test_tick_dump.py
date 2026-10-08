"""TICK_DUMP (10-08): a read-only, one-off read of every trade and quote in
given windows, written to the log in packed lines."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import bot
from helpers import run


def fake_data(n_trades=400, n_quotes=300, fail=False):
    t0 = datetime(2026, 10, 8, 8, 9, 11, tzinfo=bot.ET)

    class Hist:
        def get_stock_trades(self, req):
            if fail:
                raise RuntimeError("refused")
            return SimpleNamespace(data={req.symbol_or_symbols: [
                SimpleNamespace(timestamp=t0 + timedelta(milliseconds=10 * i),
                                price=7.0 + i / 1000, size=100, conditions=["@", "T"])
                for i in range(n_trades)]})

        def get_stock_quotes(self, req):
            return SimpleNamespace(data={req.symbol_or_symbols: [
                SimpleNamespace(timestamp=t0 + timedelta(milliseconds=5 * i),
                                bid_price=6.9 + (i // 2) / 100, ask_price=7.0 + (i // 2) / 100,
                                bid_size=1, ask_size=2)
                for i in range(n_quotes)]})

    md = object.__new__(bot.MarketData)
    md.hist, md.feed = Hist(), bot.DataFeed.SIP
    return md


def test_every_trade_and_each_quote_change_into_the_log(caplog):
    md = fake_data()
    run(md.dump_ticks("2026-10-08", (("BIAF", "08:09:11", "08:15:00"),)))
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("TICKDUMP")]
    t_rows = [row for m in lines if " T " in m for row in json.loads(m.split(" ", 6)[6])]
    q_rows = [row for m in lines if " Q " in m for row in json.loads(m.split(" ", 6)[6])]
    assert len(t_rows) == 400 and t_rows[1] == [10, 7.001, 100.0, "@T"]
    assert len(q_rows) == 150                             # each change once
    assert all(len(m) < bot.TICK_DUMP_CHARS + 200 for m in lines)
    assert "400 trades, 150 quotes" in caplog.text and "TICKDUMP done: 1 windows" in caplog.text


def test_a_refused_read_is_logged_and_the_rest_goes_on(caplog):
    md = fake_data(fail=True)
    run(md.dump_ticks("2026-10-08", (("BIAF", "08:09:11", "08:15:00"),
                                     ("NCT", "11:46:10", "11:52:00"))))
    assert "TICKDUMP BIAF 08:09:11-08:15:00: refused" in caplog.text
    assert "TICKDUMP done: 2 windows" in caplog.text
