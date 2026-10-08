"""SEC_DUMP (10-08): a read-only, one-off read of the market around every buy of
the three accounts on given days - every print near each buy, one row a second
for the whole window - written to the log in zlib + base64 lines."""
import base64
import json
import zlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import bot
from helpers import run

T0 = datetime(2026, 10, 8, 8, 9, 41, tzinfo=bot.ET)


def raw_t(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "123Z"


def fake_data(fail_minute=None):
    calls = []

    class Hist:
        def get_stock_trades(self, req):
            calls.append(("T", req.start, req.end))
            if sum(c[0] == "T" for c in calls) == (fail_minute or 0) + 1 and fail_minute is not None:
                raise RuntimeError("refused")
            out, t = [], req.start
            while t < req.end:                      # a print every 250 ms
                out.append({"t": raw_t(t), "p": 7.0 + (t - req.start).seconds / 100,
                            "s": 100, "c": ["@"] if t.microsecond else ["@", "T", "I"]})
                t += timedelta(milliseconds=250)
            return {req.symbol_or_symbols: out}

        def get_stock_quotes(self, req):
            calls.append(("Q", req.start, req.end))
            out, t = [], req.start
            while t < req.end:                      # a quote every 500 ms, changing each second
                b = 6.98 + (t - req.start).seconds / 100
                out.append({"t": raw_t(t), "bp": b, "ap": b + 0.02, "bs": 1, "as": 2})
                t += timedelta(milliseconds=500)
            return {req.symbol_or_symbols: out}

    md = object.__new__(bot.MarketData)
    md.hist_raw, md.feed = Hist(), bot.DataFeed.SIP
    return md, calls


def blobs(caplog):
    """The SECDUMP data lines put back together: {(sym, window, minute): dict}."""
    parts = {}
    for r in caplog.records:
        m = r.getMessage()
        if not m.startswith("SECDUMP 20"):
            continue
        f = m.split(" ")
        if len(f) == 7 and "/" in f[5]:
            parts.setdefault((f[2], f[3], int(f[4])), {})[int(f[5].split("/")[0])] = f[6]
    return {k: json.loads(zlib.decompress(base64.b64decode("".join(p[i] for i in sorted(p)))))
            for k, p in parts.items()}


def test_epoch_reads_nanoseconds():
    t = bot._epoch("2026-10-08T12:09:41.762123456Z")
    assert abs(t - (datetime(2026, 10, 8, 12, 9, 41, tzinfo=timezone.utc).timestamp() + 0.762123456)) < 1e-6


def test_seconds_and_ticks_near_the_buy(caplog, monkeypatch):
    monkeypatch.setattr(bot, "SEC_DUMP_BEFORE", 30)
    monkeypatch.setattr(bot, "SEC_DUMP_AFTER", 150)
    monkeypatch.setattr(bot, "SEC_DUMP_RPM", 0)
    md, calls = fake_data()
    run(md.dump_seconds([(T0.timestamp(), "BIAF")]))
    got = blobs(caplog)
    assert sorted(k[2] for k in got) == [0, 60, 120]               # 30s before + 150s, a minute a read
    assert len(calls) == 6
    allT = [r for b in got.values() for r in b["T"]]
    allS = [r for b in got.values() for r in b["S"]]
    # ticks only from 30s before the buy to SEC_DUMP_TICKS (60s) after it
    assert allT and min(r[0] for r in allT) == 0 and max(r[0] for r in allT) < 90_000
    assert len(allT) == 90 * 4
    # one row a second for the whole window; the "I" (odd lot) print does not count
    assert len(allS) == 180
    first = allS[0]
    assert first[0] == 0 and first[6] == 3                       # 4 prints, 1 not counted
    assert first[7] == 6.98 and first[8] == 7.0 and first[9] == 6.98
    assert "SECDUMP 2026-10-08 BIAF 08:09:11-08:12:11: 1 buys (08:09:41.000)" in caplog.text
    assert "SECDUMP done: 1 windows" in caplog.text
    assert all(len(r.getMessage()) < bot.TICK_DUMP_CHARS + 200 for r in caplog.records)


def test_overlapping_buys_share_one_window(caplog, monkeypatch):
    monkeypatch.setattr(bot, "SEC_DUMP_BEFORE", 30)
    monkeypatch.setattr(bot, "SEC_DUMP_AFTER", 60)
    monkeypatch.setattr(bot, "SEC_DUMP_RPM", 0)
    md, calls = fake_data()
    t = T0.timestamp()
    run(md.dump_seconds([(t, "BIAF"), (t + 40, "BIAF"), (t + 40, "BIAF"), (t + 500, "BIAF")]))
    assert "SECDUMP plan: 4 buys, 2 windows" in caplog.text
    assert "2 buys (08:09:41.000 08:10:21.000)" in caplog.text


def test_a_refused_minute_is_logged_and_the_rest_goes_on(caplog, monkeypatch):
    monkeypatch.setattr(bot, "SEC_DUMP_BEFORE", 30)
    monkeypatch.setattr(bot, "SEC_DUMP_AFTER", 150)
    monkeypatch.setattr(bot, "SEC_DUMP_RPM", 0)
    md, _ = fake_data(fail_minute=1)
    monkeypatch.setattr(bot.asyncio, "sleep", _no_sleep)
    run(md.dump_seconds([(T0.timestamp(), "BIAF")]))
    assert "SECDUMP 2026-10-08 BIAF 08:09:11 minute 1: refused" in caplog.text
    assert sorted(k[2] for k in blobs(caplog)) == [0, 120]
    assert "1 minutes lost" in caplog.text


async def _no_sleep(*a, **k):
    return None


def test_engine_reads_every_accounts_buys_on_the_days(caplog, monkeypatch):
    seen = []

    class Data:
        async def dump_seconds(self, buys):
            seen.extend(buys)

    def strat(name, fills):
        async def dump_history(first, last):
            assert (first, last) == ("2026-10-06", "2026-10-09")
            return fills
        return SimpleNamespace(name=name, dump_history=dump_history)

    t = T0.timestamp()
    eng = object.__new__(bot.Engine)
    eng.data = Data()
    eng.strategies = [strat("v36", [(t, "BIAF", "buy", 100, 7.99), (t + 9, "BIAF", "sell", 100, 8.1)]),
                      strat("v37", [(t + 1, "CHR", "buy", 10, 2.0),
                                    (t - 86400 * 3, "OLD", "buy", 1, 1.0)])]
    run(eng.sec_dump())
    assert sorted(seen) == [(t, "BIAF"), (t + 1, "CHR")]


def test_rows_from_five_minutes_before_ticks_from_thirty_seconds(caplog, monkeypatch):
    monkeypatch.setattr(bot, "SEC_DUMP_BEFORE", 300)
    monkeypatch.setattr(bot, "SEC_DUMP_AFTER", 60)
    monkeypatch.setattr(bot, "SEC_DUMP_RPM", 0)
    md, calls = fake_data()
    run(md.dump_seconds([(T0.timestamp(), "BIAF")]))
    got = blobs(caplog)
    assert len(calls) == 12                                       # 6 minutes
    allT = [r for b in got.values() for r in b["T"]]
    allS = [r for b in got.values() for r in b["S"]]
    assert len(allS) == 360
    assert min(r[0] for r in allT) == 270_000 and max(r[0] for r in allT) < 360_000
