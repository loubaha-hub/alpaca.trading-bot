"""The news and borrow log (r34.36): information only. The owner, 10-08: Alpaca
publishes hard to borrow and the news - "just let them go into the log"; news
that looks good often fizzles. Nothing here may change a trade."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import bot
from helpers import run


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(bot, "NEWS_RPM", 0)
    bot.BORROW.clear()
    bot.NEWS.clear()
    bot.NEWS_FROM.clear()
    yield
    bot.BORROW.clear()
    bot.NEWS.clear()
    bot.NEWS_FROM.clear()


def story(sid, syms, et, headline, summary=""):
    t = et.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": sid, "symbols": syms, "created_at": t, "headline": headline,
            "summary": summary, "source": "benzinga"}


class News:
    """NewsClient(raw_data=True): stories filtered as the service does."""

    def __init__(self, stories):
        self.stories, self.asked = stories, []

    def get_news(self, req):
        syms = req.symbols.split(",")
        self.asked.append((syms, req.start, req.end, req.limit))
        out = [s for s in self.stories if set(s["symbols"]) & set(syms)
               and datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")) >= req.start
               and (req.end is None or datetime.fromisoformat(
                   s["created_at"].replace("Z", "+00:00")) <= req.end)]
        return {"news": sorted(out, key=lambda s: s["created_at"], reverse=True)[:req.limit]}


def engine(stories, roster=()):
    eng = object.__new__(bot.Engine)
    eng.news_client = News(stories)
    eng.news_day, eng.news_ids, eng.news_last, eng.news_next_at = None, set(), 0.0, 0.0
    eng.borrow_seen, eng.borrow_day = {}, None
    eng.roster = set(roster)
    return eng


def test_flags_match_word_starts_only():
    assert bot.news_flags("XYZ Announces Pricing of $5M Registered Direct Offering") == ["offering"]
    assert bot.news_flags("Board approves 1-for-20 Reverse Stock Split") == ["reverse split"]
    assert bot.news_flags("Industrial output rises") == []          # "trial" inside a word
    assert bot.news_flags("FDA grants clearance") == ["fda / trial"]
    assert bot.news_flags("") == []


def test_news_since_is_the_last_weekday_close():
    from datetime import date
    assert bot.news_since(date(2026, 10, 9)) == datetime(2026, 10, 8, 16, 0, tzinfo=bot.ET)
    assert bot.news_since(date(2026, 10, 5)) == datetime(2026, 10, 2, 16, 0, tzinfo=bot.ET)


def test_borrow_from_the_asset_list_and_the_log(caplog, clock):
    eng = engine([])
    a = lambda s, etb, sh: SimpleNamespace(symbol=s, easy_to_borrow=etb, shortable=sh)
    eng.note_borrow([a("FLYE", False, True), a("DKI", True, True), a("NOSH", False, False)])
    assert bot.borrow_text("FLYE") == "hard to borrow"
    assert bot.borrow_text("NOSH") == "not shortable"
    assert bot.borrow_text("DKI") == "easy to borrow"
    assert bot.borrow_text("ZZZ") == "borrow unknown"
    eng.log_borrow(["FLYE", "DKI", "NOSH"])
    assert ("BORROW in: hard to borrow: FLYE | not shortable: NOSH | easy to borrow: DKI"
            in caplog.text)
    caplog.clear()
    eng.log_borrow(["FLYE", "DKI"])                                # nothing new
    assert "BORROW" not in caplog.text
    eng.note_borrow([a("FLYE", True, True), a("DKI", True, True)])
    eng.log_borrow(["FLYE", "DKI"])
    assert "BORROW change: FLYE hard to borrow -> easy to borrow" in caplog.text


def test_a_names_first_check_reaches_back_to_yesterdays_close(caplog, clock):
    clock.now = datetime(2026, 10, 9, 7, 30, tzinfo=bot.ET)
    old = story("1", ["FLYE"], datetime(2026, 10, 8, 15, 0, tzinfo=bot.ET), "Too old")
    a = story("2", ["FLYE", "DKI"], datetime(2026, 10, 8, 18, 5, tzinfo=bot.ET),
              "FLYE and DKI sign a collaboration")
    b = story("3", ["FLYE"], datetime(2026, 10, 9, 7, 10, tzinfo=bot.ET),
              "FLYE Announces Pricing of $4M Offering")
    eng = engine([old, a, b], roster={"FLYE", "DKI", "QUIET"})
    run(eng.news_check())
    assert eng.news_client.asked[0][1] == datetime(2026, 10, 8, 16, 0, tzinfo=bot.ET)
    assert "Too old" not in caplog.text
    assert "NEWS DKI FLYE 10-08 18:05" in caplog.text and "| deal" in caplog.text
    assert "NEWS FLYE 10-09 07:10 (20m ago) [benzinga] FLYE Announces Pricing of $4M Offering | offering" in caplog.text
    assert "NEWS none since 10-08 16:00: QUIET" in caplog.text
    assert [h for _, _, h, _ in bot.NEWS["FLYE"]] == ["FLYE and DKI sign a collaboration",
                                                      "FLYE Announces Pricing of $4M Offering"]
    line = bot.context_line("FLYE", now=clock.now.timestamp())
    assert line.startswith("borrow unknown | 2 headlines since 10-08 16:00 (deal, offering)")
    assert "07:10 20m ago: FLYE Announces Pricing" in line
    assert bot.context_line("QUIET") == "borrow unknown | no news since 10-08 16:00"
    assert bot.context_line("NEW") == "borrow unknown | news not read yet"

    # a minute later: each story once; a later name gets the shared story
    caplog.clear()
    clock.now = datetime(2026, 10, 9, 7, 31, tzinfo=bot.ET)
    c = story("4", ["DKI"], datetime(2026, 10, 9, 7, 30, 30, tzinfo=bot.ET), "DKI halted")
    eng.news_client.stories.append(c)
    eng.roster.add("LATE")
    eng.news_client.stories.append(story("5", ["LATE", "FLYE"],
                                         datetime(2026, 10, 9, 6, 0, tzinfo=bot.ET), "Movers"))
    run(eng.news_check())
    assert "NEWS DKI 10-09 07:30 (0m ago) [benzinga] DKI halted | halt" in caplog.text
    assert "NEWS LATE 10-09 06:00" in caplog.text               # FLYE's check is from 7:15
    assert "Pricing" not in caplog.text and "collaboration" not in caplog.text
    asked = eng.news_client.asked[-2:]
    assert asked[0][0] == ["LATE"] and asked[1][0] == ["DKI", "FLYE", "QUIET"]
    assert asked[1][1] == datetime(2026, 10, 9, 7, 15, tzinfo=bot.ET)   # 15 min overlap


def test_a_new_day_starts_over(clock):
    clock.now = datetime(2026, 10, 9, 7, 30, tzinfo=bot.ET)
    eng = engine([story("1", ["FLYE"], datetime(2026, 10, 9, 7, 0, tzinfo=bot.ET), "x")],
                 roster={"FLYE"})
    run(eng.news_check())
    assert bot.NEWS["FLYE"]
    clock.now = datetime(2026, 10, 12, 4, 1, tzinfo=bot.ET)
    eng.news_client.stories = []
    run(eng.news_check())
    assert "FLYE" not in bot.NEWS
    assert bot.NEWS_FROM["FLYE"] == datetime(2026, 10, 9, 16, 0, tzinfo=bot.ET).timestamp()


def test_the_context_line_at_an_opening_buy_only(caplog, v31, broker, data, no_sleep):
    data.quotes[("ABCD", "ask")] = 10.0
    bot.NEWS_FROM["ABCD"] = 0.0
    assert run(v31.buy("ABCD", 100, 10.0)) == 100
    assert "[v31] CONTEXT ABCD: borrow unknown | no news since" in caplog.text
    caplog.clear()
    assert run(v31.buy("ABCD", 100, 10.0)) == 100                  # an add: no line
    assert "CONTEXT" not in caplog.text


def test_a_broken_context_never_stops_a_buy(v31, data, no_sleep, monkeypatch):
    data.quotes[("ABCD", "ask")] = 10.0
    monkeypatch.setattr(bot, "context_line", lambda s: 1 / 0)
    assert run(v31.buy("ABCD", 100, 10.0)) == 100


def test_the_one_time_read_of_past_headlines(caplog, monkeypatch, no_sleep):
    t = datetime(2026, 10, 7, 6, 42, 10, tzinfo=bot.ET).timestamp()

    def strat(name, fills):
        async def dump_history(first, last):
            assert (first, last) == ("2026-10-01", "2026-10-09")
            return fills
        return SimpleNamespace(name=name, dump_history=dump_history)

    eng = engine([story("9", ["LPCN"], datetime(2026, 10, 7, 6, 30, tzinfo=bot.ET),
                        "LPCN receives FDA approval"),
                  story("8", ["LPCN"], datetime(2026, 10, 7, 21, 0, tzinfo=bot.ET), "after 8pm")])
    eng.strategies = [strat("v36", [(t, "LPCN", "buy", 100, 3.0), (t + 60, "LPCN", "sell", 100, 3.2),
                                    (t - 30, "LPCN", "buy", 10, 2.9)]),
                      strat("v37", [(t + 5, "LPCN", "buy", 10, 3.0),
                                    (t - 86400, "MI", "buy", 10, 1.0)])]
    run(eng.news_dump())
    assert "NEWSDUMP plan: 2 stock-days bought, 2026-10-01..2026-10-08" in caplog.text
    assert ("NEWSDUMP 2026-10-07 LPCN: 1 headlines from 10-06 16:00, first buy 06:41:40, "
            "borrow unknown (now)") in caplog.text
    assert "NEWSDUMP 2026-10-07 LPCN 10-07 06:30 [benzinga] LPCN receives FDA approval | fda / trial" in caplog.text
    assert "after 8pm" not in caplog.text
    assert "NEWSDUMP 2026-10-06 MI: 0 headlines from 10-05 16:00" in caplog.text
    assert "NEWSDUMP done: 2 of 2 stock-days" in caplog.text
