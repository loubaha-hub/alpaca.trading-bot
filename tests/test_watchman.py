"""
watchman.py - the separate program that watches every account and can stop
everything. Nothing here touches the network: the accounts, the phone, Render
and Claude are fakes, and the clock is a number the tests move.
"""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("watchman", REPO / "watchman.py")
wm = importlib.util.module_from_spec(_spec)
sys.modules["watchman"] = wm
_spec.loader.exec_module(wm)

MONDAY_10AM = datetime(2026, 10, 5, 10, 0, tzinfo=wm.ET).timestamp()


# ---- fakes ----------------------------------------------------------------------------

class Clock:
    def __init__(self, t=MONDAY_10AM):
        self.t = t

    def __call__(self):
        return self.t

    def at(self, hour, minute=0, day=5):
        self.t = datetime(2026, 10, day, hour, minute, tzinfo=wm.ET).timestamp()


def pos(symbol, qty, price):
    return SimpleNamespace(symbol=symbol, qty=str(qty), market_value=str(qty * price),
                           current_price=str(price), avg_entry_price=str(price),
                           side="long" if qty > 0 else "short")


class Account:
    """One paper account. `events` is shared, so tests can check the ORDER of
    what happened across accounts and Render."""

    def __init__(self, events, name, equity=10_000.0, last_equity=None,
                 positions=(), fills=True):
        self.events = events
        self.name = name
        self.eq = equity
        self.last_eq = equity if last_equity is None else last_equity
        self.held = list(positions)
        self.fills = fills                 # a closing order fills at once
        self.orders = []
        self.down = False
        self.status = "ACTIVE"
        self.blocked = False
        self.is_open = True

    def get_account(self):
        if self.down:
            raise ConnectionError("timed out")
        return SimpleNamespace(equity=str(self.eq), last_equity=str(self.last_eq),
                               status=self.status, trading_blocked=self.blocked,
                               account_blocked=False)

    def get_all_positions(self):
        if self.down:
            raise ConnectionError("timed out")
        return list(self.held)

    def cancel_orders(self):
        self.events.append(("cancel", self.name))

    def submit_order(self, order):
        self.events.append(("order", self.name, order.symbol))
        self.orders.append(order)
        if self.fills:
            self.held = [p for p in self.held if p.symbol != order.symbol]
        else:
            self.fills = True              # this one rests; the next sweep fills

    def get_clock(self):
        return SimpleNamespace(is_open=self.is_open)


class Quotes:
    def __init__(self, quotes):
        self.quotes = quotes

    def get_stock_latest_quote(self, req):
        bid, ask = self.quotes[req.symbol_or_symbols]
        return {req.symbol_or_symbols: SimpleNamespace(bid_price=bid, ask_price=ask)}


class Phone:
    command_topic = "cmd"
    kill_code = "secret"

    def __init__(self):
        self.sent = []

    def send(self, title, message, priority=wm.NORMAL, stop_button=True):
        self.sent.append(SimpleNamespace(title=title, message=message,
                                         priority=priority, stop_button=stop_button))

    def titles(self):
        return [m.title for m in self.sent]

    def alerts(self):
        return [m for m in self.sent if "Watchman" not in m.title]


class Render:
    def __init__(self, events):
        self.events = events
        self.suspended = False
        self.health = True
        self.critical = []

    def service(self):
        return {"suspended": "suspended" if self.suspended else "not_suspended"}

    def suspend(self):
        self.events.append(("suspend",))
        self.suspended = True

    def last_health(self, now, minutes):
        return now if self.health else None

    def critical_since(self, since, now):
        rows, self.critical = self.critical, []
        return rows


class Claude:
    def __init__(self):
        self.fired = []

    def fire(self, text):
        self.fired.append(text)


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setattr(wm, "DRY_RUN", False)
    clock = Clock()
    events = []
    accounts = {n: Account(events, n) for n in ("v31", "v34", "v35")}
    quotes = Quotes({"ABCD": (5.00, 5.02), "WXYZ": (0.80, 0.81)})
    watches = [wm.Watch(n, a, quotes) for n, a in accounts.items()]
    phone, render, claude = Phone(), Render(events), Claude()

    def sleep(s):
        clock.t += s

    w = wm.Watchman(watches, phone, render, claude, kill_code="secret",
                    clock=clock, sleep=sleep)
    return SimpleNamespace(w=w, clock=clock, events=events, acct=accounts,
                           phone=phone, render=render, claude=claude, sleep=sleep)


def step(world, seconds=5):
    world.w.step()
    world.clock.t += seconds


# ---- a quiet day ----------------------------------------------------------------------

def test_a_quiet_day_sends_only_the_start_message(world):
    for _ in range(20):
        step(world)
    assert world.phone.titles() == ["[paper] Watchman started"]
    assert world.claude.fired == []


def test_the_on_duty_message_comes_at_355am_with_the_stop_button(world):
    world.clock.at(3, 50)
    step(world)
    world.clock.at(3, 55)
    step(world)
    duty = [m for m in world.phone.sent if "on duty" in m.title]
    assert len(duty) == 1 and duty[0].stop_button


# ---- the day's baseline, as the engine reads it ---------------------------------------

def test_before_4am_the_baseline_is_live_equity(world):
    """2026-10-01, 12am: last_equity was still Tuesday's 22,649 while the account
    held 20,264. The engine read -10.5% and halted (fixed in r32). So must not we."""
    world.clock.at(0, 5)
    a = world.acct["v31"]
    a.eq, a.last_eq = 20_264.0, 22_649.0
    step(world)
    assert world.phone.alerts() == []
    assert world.w.watches[0].baseline == pytest.approx(20_264.0)


def test_after_4am_a_restart_still_measures_from_last_equity(world):
    a = world.acct["v31"]
    a.eq, a.last_eq = 9_400.0, 10_000.0
    step(world)
    assert any("v31 down 6.0% today" in t for t in world.phone.titles())


# ---- the alerts -----------------------------------------------------------------------

def test_down_5_percent_alerts_once_then_again_each_2_percent_more(world):
    """A slow slide - ten minutes between moves, so the fast-drop rule stays
    out of it."""
    a = world.acct["v34"]
    for eq in (9_800.0, 9_600.0, 9_500.0, 9_450.0):
        a.eq = eq
        step(world, 600)
    assert len(world.phone.alerts()) == 1
    for eq in (9_350.0, 9_290.0):
        a.eq = eq
        step(world, 600)
    downs = [m.title for m in world.phone.alerts()]
    assert downs == ["[paper] v34 down 5.0% today", "[paper] v34 down 7.1% today"]


def test_a_fast_drop_alerts_even_above_the_daily_line(world):
    a = world.acct["v35"]
    step(world)
    a.eq = 9_650.0                                     # -3.5% in 5 seconds
    step(world)
    assert any("v35 fell 3.5% in 5 min" in t for t in world.phone.titles())
    assert not any("down" in t for t in world.phone.titles())


def test_one_position_over_half_the_account_alerts(world):
    world.acct["v31"].held = [pos("ABCD", 1_200, 5.00)]      # $6,000 of $10,000
    step(world)
    assert any("ABCD is 60% of the account" in t for t in world.phone.titles())


def test_positions_still_held_after_8pm_alert(world):
    world.clock.at(20, 30)
    world.acct["v35"].held = [pos("ABCD", 100, 5.00)]
    step(world)
    assert any("v35 still holds 1 position(s) outside the session" in t
               for t in world.phone.titles())


def test_an_account_alpaca_has_restricted_is_urgent(world):
    world.acct["v31"].blocked = True
    step(world)
    hit = [m for m in world.phone.sent if "restricted" in m.title]
    assert hit and hit[0].priority == wm.URGENT


def test_an_unreachable_account_alerts_after_a_minute_not_before(world):
    step(world)
    world.acct["v34"].down = True
    for _ in range(11):                                # 55 seconds
        step(world)
    assert not any("can't see" in t for t in world.phone.titles())
    step(world)
    step(world)
    assert any("v34: can't see the account" in t for t in world.phone.titles())


def test_the_engine_going_silent_is_urgent_and_repeats_every_30_min(world):
    world.render.health = False
    world.clock.t += 6 * 60                            # past the 5 minute grace
    for _ in range(12 * 10):                           # 10 minutes of checks
        step(world)
    silent = [m for m in world.phone.sent if "gone silent" in m.title]
    assert len(silent) == 1 and silent[0].priority == wm.URGENT
    world.clock.t += 30 * 60
    step(world)
    assert len([m for m in world.phone.sent if "gone silent" in m.title]) == 2


def test_the_engines_critical_lines_reach_the_phone(world):
    world.render.critical = [(datetime.now(timezone.utc),
                              "2026-10-05 10:00:00,000 CRITICAL [v31] DAILY HALT at "
                              "equity 17000.00 (baseline 19124.40, limit 17211.96)")]
    step(world)
    assert any("Engine: [v31] DAILY HALT" in t for t in world.phone.titles())


def test_a_suspended_engine_is_reported_once_not_as_silent(world):
    world.render.suspended = True
    world.render.health = False
    world.clock.t += 6 * 60
    for _ in range(30):
        step(world, 60)
    titles = world.phone.titles()
    assert sum("suspended" in t for t in titles) == 1
    assert not any("silent" in t for t in titles)


def test_claude_is_woken_by_serious_alerts_at_most_every_15_minutes(world):
    step(world)
    world.acct["v31"].eq = 9_400.0
    step(world)
    world.acct["v34"].eq = 9_400.0
    step(world)
    assert len(world.claude.fired) == 1
    world.clock.t += 15 * 60
    world.acct["v35"].eq = 9_400.0
    step(world)
    assert len(world.claude.fired) == 2


# ---- STOP EVERYTHING -------------------------------------------------------------------

def test_the_hard_line_stops_the_engine_first_then_cancels_then_sells(world):
    a = world.acct["v31"]
    a.held = [pos("ABCD", 300, 5.00)]
    world.acct["v35"].held = [pos("WXYZ", 1_000, 0.80)]
    step(world)
    a.eq = 8_700.0                                     # -13%: the engine's halt failed
    step(world)
    kinds = [e[0] for e in world.events]
    assert kinds[0] == "suspend"
    assert kinds.index("cancel") < kinds.index("order")
    assert ("order", "v31", "ABCD") in world.events
    assert ("order", "v35", "WXYZ") in world.events
    assert world.render.suspended
    last = world.phone.sent[-1]
    assert last.title == "[paper] STOPPED - every account is flat"
    assert last.priority == wm.URGENT
    assert any("STOPPED" in text for text in world.claude.fired)


def test_stop_never_buys_a_long_position(world):
    world.acct["v31"].held = [pos("ABCD", 300, 5.00)]
    world.w.stop_everything("test")
    assert all(o.side == wm.OrderSide.SELL for o in world.acct["v31"].orders)


def test_in_the_regular_session_stop_sells_at_market(world):
    world.acct["v31"].held = [pos("ABCD", 300, 5.00)]
    world.w.stop_everything("test")
    order = world.acct["v31"].orders[0]
    assert isinstance(order, wm.MarketOrderRequest) and order.qty == 300


def test_outside_it_stop_sells_with_a_limit_5_percent_through_the_bid(world):
    for a in world.acct.values():
        a.is_open = False
    world.acct["v31"].held = [pos("ABCD", 300, 5.00)]
    world.acct["v34"].held = [pos("WXYZ", 1_000, 0.80)]
    world.w.stop_everything("test")
    abcd = world.acct["v31"].orders[0]
    wxyz = world.acct["v34"].orders[0]
    assert isinstance(abcd, wm.LimitOrderRequest) and abcd.extended_hours
    assert abcd.limit_price == pytest.approx(4.75)       # $5.00 bid - 5%
    assert wxyz.limit_price == pytest.approx(0.76)       # four decimals under $1


def test_stop_sweeps_again_until_flat(world):
    a = world.acct["v31"]
    a.held = [pos("ABCD", 300, 5.00)]
    a.fills = False                                   # the first sell rests
    world.w.stop_everything("test")
    assert [e for e in world.events if e[0] == "order"] == [("order", "v31", "ABCD")] * 2
    assert world.phone.sent[-1].title == "[paper] STOPPED - every account is flat"


def test_stop_reports_what_it_could_not_sell(world, monkeypatch):
    monkeypatch.setattr(wm, "KILL_PASSES", 3)
    a = world.acct["v31"]
    a.held = [pos("ABCD", 300, 5.00)]
    a.submit_order = lambda order: world.events.append(("order", "v31", order.symbol))
    world.w.stop_everything("test")
    last = world.phone.sent[-1]
    assert last.title == "[paper] STOP: STILL HOLDING POSITIONS"
    assert "v31 still holds ABCD" in last.message
    assert last.stop_button                            # tap again to retry


def test_the_stop_button_needs_the_code(world):
    world.acct["v31"].held = [pos("ABCD", 300, 5.00)]
    world.w.command("KILL guess")
    assert not world.render.suspended and world.events == []
    assert any("wrong code" in t for t in world.phone.titles())
    world.w.command("KILL secret")
    assert world.render.suspended
    assert ("order", "v31", "ABCD") in world.events


def test_status_answers_without_touching_anything(world):
    step(world)
    world.w.command("STATUS secret")
    assert world.phone.sent[-1].title == "[paper] Status"
    assert world.events == []


def test_one_stop_a_day_from_the_hard_line(world):
    a = world.acct["v31"]
    a.eq = 8_700.0
    step(world)
    step(world)
    assert sum(e == ("suspend",) for e in world.events) == 1


def test_a_dry_run_touches_nothing(world, monkeypatch):
    monkeypatch.setattr(wm, "DRY_RUN", True)
    world.acct["v31"].held = [pos("ABCD", 300, 5.00)]
    world.w.stop_everything("rehearsal")
    assert world.events == [] and not world.render.suspended
    assert world.phone.sent[0].title.endswith("DRY RUN, nothing is being done")
    assert "v31 would sell: ABCD" in world.phone.sent[-1].message


# ---- the outside world ---------------------------------------------------------------

class Http:
    def __init__(self, payload=None):
        self.calls = []
        self.payload = payload or {}

    def _resp(self):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: self.payload)

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return self._resp()

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self._resp()


def test_every_alert_carries_a_one_tap_stop_button():
    http = Http()
    wm.Ntfy("https://ntfy.sh", "alerts", "cmd", "secret", http=http).send("t", "m", 5)
    body = http.calls[0][2]["json"]
    action = body["actions"][0]
    assert body["topic"] == "alerts" and body["priority"] == 5
    assert action["action"] == "http" and action["method"] == "POST"
    assert action["url"] == "https://ntfy.sh/cmd" and action["body"] == "KILL secret"


def test_no_stop_button_until_the_command_topic_and_code_are_set():
    http = Http()
    wm.Ntfy("https://ntfy.sh", "alerts", http=http).send("t", "m")
    assert "actions" not in http.calls[0][2]["json"]


def test_render_timestamps_with_nanoseconds_parse():
    ts = wm.parse_ts("2026-10-05T05:52:38.261280787Z")
    assert ts == datetime(2026, 10, 5, 5, 52, 38, 261280, tzinfo=timezone.utc)


def test_claude_is_woken_through_the_routine_fire_endpoint():
    http = Http()
    wm.ClaudeRoutine("trig_123", "tok", http=http).fire("v31 down 6%")
    method, url, kw = http.calls[0]
    assert url == "https://api.anthropic.com/v1/claude_code/routines/trig_123/fire"
    assert kw["json"] == {"text": "v31 down 6%"}
    assert kw["headers"]["Authorization"] == "Bearer tok"


def test_the_watchman_never_opens_a_market_data_stream():
    """Alpaca allows one data connection per login and the engine holds it."""
    source = (REPO / "watchman.py").read_text()
    code = source.split('"""', 2)[2]                   # past the docstring
    assert "StockDataStream" not in code and "alpaca.data.live" not in code
