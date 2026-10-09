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

        def get_stock_bars(self, req):              # the day's high before the read
            calls.append(("B", req.start, req.end))
            end = req.end if req.end.tzinfo else req.end.replace(tzinfo=timezone.utc)
            return {req.symbol_or_symbols: [
                {"t": raw_t(end - timedelta(minutes=3)), "o": 7.0, "h": 7.5, "l": 6.9, "c": 7.1, "v": 1000},
                {"t": raw_t(end - timedelta(seconds=30)), "o": 7.0, "h": 9.9, "l": 6.9, "c": 7.1, "v": 1}]}

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
    assert len([c for c in calls if c[0] != "B"]) == 6
    # the day's high before the read: 4:00 to the window's start, the minute still
    # forming at the start left out
    utc = lambda d: (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    assert [(utc(c[1]), utc(c[2])) for c in calls if c[0] == "B"] == [
        (datetime(2026, 10, 8, 4, 0, tzinfo=bot.ET).timestamp(), (T0 - timedelta(seconds=30)).timestamp())]
    assert "SECDUMP HOD 2026-10-08 BIAF 08:09:11: the day's high before the read 7.5000" in caplog.text
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
    monkeypatch.setattr(bot, "SEC_DUMP_DAYS", ("2026-10-06", "2026-10-07", "2026-10-08"))
    monkeypatch.setattr(bot, "SEC_DUMP_MISSED", ())
    monkeypatch.setattr(bot, "SEC_DUMP_RUNNER_DAYS", ())
    seen = []

    class Data:
        async def dump_seconds(self, buys, runs=()):
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
    assert len([c for c in calls if c[0] != "B"]) == 12           # 6 minutes
    allT = [r for b in got.values() for r in b["T"]]
    allS = [r for b in got.values() for r in b["S"]]
    assert len(allS) == 360
    assert min(r[0] for r in allT) == 270_000 and max(r[0] for r in allT) < 360_000


def test_missed_stocks_are_read_on_any_day(monkeypatch):
    """SEC_DUMP_MISSED (10-09): a stock no bot bought (NTCL), or a moment whose
    read was lost (an earlier day), is read around the moment named, the same
    way as a buy - whatever SEC_DUMP_DAYS holds."""
    seen = []

    class Data:
        async def dump_seconds(self, buys, runs=()):
            seen.extend(buys)

    async def dump_history(first, last):
        return []

    monkeypatch.setattr(bot, "SEC_DUMP_RUNNER_DAYS", ())

    eng = object.__new__(bot.Engine)
    eng.data = Data()
    eng.strategies = [SimpleNamespace(name="v36", dump_history=dump_history)]
    monkeypatch.setattr(bot, "SEC_DUMP_MISSED", (("2026-10-09 08:30:23", "NTCL"),
                                                 ("2026-10-08 07:00:00", "OLD")))
    monkeypatch.setattr(bot, "SEC_DUMP_DAYS", ("2026-10-09",))
    run(eng.sec_dump())
    assert seen == [(datetime(2026, 10, 9, 8, 30, 23, tzinfo=bot.ET).timestamp(), "NTCL"),
                    (datetime(2026, 10, 8, 7, 0, 0, tzinfo=bot.ET).timestamp(), "OLD")]


# ---- the day's top runners (10-09) ------------------------------------------

D7 = "2026-10-07"


def at(hm, day=D7):
    return datetime.fromisoformat("%sT%s" % (day, hm)).replace(tzinfo=bot.ET)


def bar(t, low, high, vol=1_000_000, close=None):
    return {"t": raw_t(t), "o": low, "h": high, "l": low, "c": close or high, "v": vol}


def test_best_run_is_the_biggest_rise_within_the_span():
    m = lambda hm: at(hm).timestamp()
    bars = [(m("04:00"), 1.0, 1.1), (m("06:00"), 2.0, 2.2), (m("08:00"), 2.1, 7.0),
            (m("08:30"), 5.0, 6.0), (m("14:00"), 6.5, 9.5)]
    # 1.0 at 4:00 to 9.5 at 14:00 is bigger, but ten hours apart: the run is
    # 2.0 (6:00) -> 7.0 (8:00), inside 150 minutes
    r = bot._best_run(bars, 150 * 60)
    assert r[1:] == (2.0, m("06:00"), 7.0, m("08:00")) and abs(r[0] - 3.5) < 1e-9
    assert bot._best_run([], 60)[0] == 0.0


def fake_bars(minute, hourly):
    """minute {sym: [bars]}; hourly {sym: [bars]}. Records the requests."""
    calls = []

    class Hist:
        def get_stock_bars(self, req):
            syms = req.symbol_or_symbols
            syms = [syms] if isinstance(syms, str) else list(syms)
            hour = req.timeframe.value == "1Hour"
            calls.append(("H" if hour else "M", tuple(syms)))
            src = hourly if hour else minute
            return {s: src[s] for s in syms if s in src}

    md = object.__new__(bot.MarketData)
    md.hist_raw, md.feed = Hist(), bot.DataFeed.SIP
    return md, calls


def test_runners_found_from_the_hourly_bars_and_read_around_the_run(caplog, monkeypatch):
    monkeypatch.setattr(bot, "SEC_DUMP_RPM", 0)
    monkeypatch.setattr(bot, "RUNNER_TOP", 2)
    hourly = {
        "BIYA": [bar(at("04:00"), 1.7, 2.0), bar(at("08:00"), 2.4, 33.96)],
        "SXTC": [bar(at("07:00"), 1.9, 2.2), bar(at("08:00"), 2.1, 7.07)],
        "PFAI": [bar(at("09:00"), 2.3, 2.5), bar(at("11:00"), 3.0, 5.0)],
        "FLAT": [bar(at("09:00"), 3.0, 3.2)],
        "TINY": [bar(at("08:00"), 0.20, 0.90)],              # never reaches $1
        "THIN": [bar(at("08:00"), 2.0, 6.0, vol=100)],       # $600 traded
    }
    minute = {
        "BIYA": [bar(at("07:50"), 2.4, 2.5), bar(at("08:20"), 2.54, 33.96)],
        "SXTC": [bar(at("08:14"), 2.1, 2.2), bar(at("08:16"), 6.5, 7.07)],
        "PFAI": [bar(at("09:45"), 2.22, 2.3), bar(at("11:20"), 4.0, 4.5)],
        "VIVK": [bar(at("07:00"), 1.0, 1.1)],
    }
    md, calls = fake_bars(minute, hourly)
    runs = run(md.find_runners(D7, sorted(hourly) + ["VIVK"], ["VIVK"]))
    assert [(d, s, round(a), round(b)) for d, s, a, b in runs] == [
        (D7, "BIYA", at("07:50").timestamp() - 600, at("08:20").timestamp() + 1800),
        (D7, "SXTC", at("08:14").timestamp() - 600, at("08:16").timestamp() + 1800)]
    # one hourly request for the list; minute bars only for the hourly runners and the named
    assert calls[0] == ("H", tuple(sorted(hourly) + ["VIVK"]))
    assert sorted(c[1][0] for c in calls if c[0] == "M") == ["BIYA", "PFAI", "SXTC", "VIVK"]
    assert "SECDUMP RUNNER 2026-10-07 BIYA x14.15 2.4000 at 07:50 -> 33.9600 at 08:20" in caplog.text
    assert "PFAI x2.03" in caplog.text and "not read (top 2 done)" in caplog.text
    assert "VIVK x1.10" in caplog.text and "not read (under the bar)" in caplog.text


def test_runner_windows_join_the_buys_on_the_same_stock(caplog, monkeypatch):
    monkeypatch.setattr(bot, "SEC_DUMP_BEFORE", 30)
    monkeypatch.setattr(bot, "SEC_DUMP_AFTER", 60)
    monkeypatch.setattr(bot, "SEC_DUMP_RPM", 0)
    md, calls = fake_data()
    t = T0.timestamp()
    run(md.dump_seconds([(t, "BIAF")], [("2026-10-08", "BIAF", t + 60, t + 180),
                                         ("2026-10-08", "DKI", t, t + 120)]))
    assert "SECDUMP plan: 1 buys, 2 windows, 6 minutes to read, 2 runs" in caplog.text
    assert "SECDUMP 2026-10-08 BIAF 08:09:11-08:12:41: 1 buys (08:09:41.000)" in caplog.text
    assert "SECDUMP 2026-10-08 DKI 08:09:41-08:11:41: 0 buys ()" in caplog.text
    dki = [b for k, b in blobs(caplog).items() if k[0] == "DKI"]
    assert dki and all(not b["T"] and not b["Q"] and b["S"] for b in dki)   # rows only, no ticks


def test_engine_reads_the_runners_of_each_day(monkeypatch):
    seen = {}

    class Data:
        async def find_runners(self, day, symbols, names):
            seen.setdefault("find", []).append((day, symbols, names))
            return [(day, "BIYA", 1.0, 2.0)] if day == D7 else []

        async def dump_seconds(self, buys, runs=()):
            seen["runs"] = runs

    async def dump_history(first, last):
        return []

    assets = [SimpleNamespace(symbol=s, tradable=t) for s, t in
              (("BIYA", True), ("BRK.B", True), ("NOPE", False), ("SXTC", True), ("WARRW", True))]
    eng = object.__new__(bot.Engine)
    eng.data = Data()
    eng.strategies = [SimpleNamespace(name="v36", dump_history=dump_history)]
    eng.assets_client = SimpleNamespace(get_all_assets=lambda req: assets)
    monkeypatch.setattr(bot, "SEC_DUMP_DAYS", ("2026-10-09",))
    monkeypatch.setattr(bot, "SEC_DUMP_MISSED", ())
    monkeypatch.setattr(bot, "SEC_DUMP_RUNNER_DAYS", ("2026-10-06", D7))
    monkeypatch.setattr(bot, "SEC_DUMP_RUNNER_NAMES", ((D7, "BIYA"), ("2026-10-09", "VIVK")))
    run(eng.sec_dump())
    assert seen["find"] == [("2026-10-06", ["BIYA", "SXTC"], []), (D7, ["BIYA", "SXTC"], ["BIYA"])]
    assert seen["runs"] == [(D7, "BIYA", 1.0, 2.0)]
