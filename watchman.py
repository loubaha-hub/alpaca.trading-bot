"""
Watchman - a second program on Render that watches every trading account and
can stop everything. It never buys.

WHY IT EXISTS
  The engine (r34.py) has good guards - the -10% halt that sells everything,
  the size self-check, the dead-tape exit, reconciliation against the broker -
  but they only write to the log, and they live INSIDE the engine. Nobody hears
  about a problem unless they read the log, and if the engine crashes or
  freezes, its guards stop with it. A guard cannot report its own death.

  The watchman is a separate process. Every 5 seconds through the session it
  reads each account from Alpaca, once a minute it reads the engine's own log
  on Render, and when something is wrong it puts it on your phone (ntfy) within
  seconds - and wakes a Claude routine to work out what happened.

WHAT IT CAN DO TO THE ACCOUNTS: LOOK, AND STOP EVERYTHING
  STOP EVERYTHING runs when you tap the button on any alert, or on its own when
  an account is down WATCH_KILL_PCT on the day - past the engine's own halt, so
  the engine's halt has failed. In this order:
    1. suspend the engine on Render, so nothing can buy again
    2. cancel every open order in every account
    3. sell every position in every account - market orders 9:30am-4pm; outside
       that, limit orders WATCH_KILL_SLIPPAGE through the bid, because Alpaca
       takes only limit orders in extended hours. Swept again every few
       seconds, re-priced, until flat.
  It never opens a position. Nothing restarts until a person resumes the engine
  on Render.

WHAT IT MUST NEVER DO
  Open a market-data websocket. Alpaca allows ONE per login and the engine
  holds it (r34.py, WHY ONE PROCESS). Everything here is plain REST: two calls
  per account per check, well inside Alpaca's per-account request limit.

ENVIRONMENT VARIABLES
  Accounts - the engine's own names; an account without keys is skipped
    ALPACA_API_KEY / ALPACA_SECRET_KEY   v31
    V32_API_KEY    / V32_SECRET_KEY      v32
    V33_API_KEY    / V33_SECRET_KEY      v34 (v34 trades v33's account)
    V35_API_KEY    / V35_SECRET_KEY      v35
    ALPACA_PAPER   "1" paper (default) or "0" live - as the engine
    ALPACA_FEED    "sip" (default) or "iex" - quotes to price the STOP sells
  Your phone
    NTFY_TOPIC          the topic you subscribe to in the ntfy app (required)
    NTFY_COMMAND_TOPIC  where the STOP button sends - not the same topic
    WATCH_KILL_CODE     a secret word every STOP / STATUS command must carry
    NTFY_SERVER         default https://ntfy.sh
    NTFY_TOKEN          an ntfy access token, when the topics are protected
  The engine on Render - without all three, STOP cannot suspend the engine and
  the engine's log is not watched
    RENDER_API_KEY, RENDER_SERVICE_ID (the engine), RENDER_OWNER_ID (workspace)
  Claude - optional: every serious alert wakes a Claude Code routine
    CLAUDE_ROUTINE_ID, CLAUDE_ROUTINE_TOKEN
  Thresholds - percentages; 0 turns a rule off
    WATCH_WARN_PCT 5, then every WATCH_WARN_STEP 2 more    WATCH_KILL_PCT 12
    WATCH_FAST_DROP_PCT 3 within WATCH_FAST_DROP_MINUTES 5
    WATCH_POSITION_PCT 50 (one name)    WATCH_EXPOSURE_PCT 100 (all names)
    WATCH_KILL_SLIPPAGE 5
    WATCH_CHECK_SECONDS 5 (4am-8pm ET weekdays), WATCH_IDLE_SECONDS 60 (other)
    WATCH_DRY_RUN "1": STOP only says what it would do - for a first trial

TO TURN IT ON - built and tested, not deployed
  1. Install ntfy on the phone; subscribe to NTFY_TOPIC (a long random name -
     on ntfy.sh anyone who knows a topic's name can read or post to it).
  2. Render: a new Background Worker from this repo, start command
     `python watchman.py`, the variables above typed into its Environment.
     A commit to main redeploys BOTH services - merge outside trading hours.
  3. A Claude Code routine with an API trigger; its id and token as above.
  4. A first day with WATCH_DRY_RUN=1: check the alerts arrive and press STOP
     once, then remove WATCH_DRY_RUN.
  Moving money out of an account looks like a loss to every rule here, and a
  big enough withdrawal crosses the hard line: suspend the watchman first.
  STOP from anywhere, no alert needed - bookmark this one link:
     <NTFY_SERVER>/<NTFY_COMMAND_TOPIC>/publish?message=KILL+<WATCH_KILL_CODE>
"""

import json
import logging
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

VERSION = "watchman-1"
ET = ZoneInfo("America/New_York")
SESSION = ((4, 0), (20, 0))                 # the engine's session, ET
ON_DUTY_AT = (3, 55)                        # the morning "on duty" message


def env_float(name, default):
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else float(default)


def env_pct(name, default):
    return env_float(name, default) / 100.0


CHECK_SECONDS = env_float("WATCH_CHECK_SECONDS", 5)
IDLE_SECONDS = env_float("WATCH_IDLE_SECONDS", 60)
WARN_PCT = env_pct("WATCH_WARN_PCT", 5)
WARN_STEP = env_pct("WATCH_WARN_STEP", 2)
KILL_PCT = env_pct("WATCH_KILL_PCT", 12)    # past the engine's own -10% halt
FAST_DROP_PCT = env_pct("WATCH_FAST_DROP_PCT", 3)
FAST_DROP_SECONDS = env_float("WATCH_FAST_DROP_MINUTES", 5) * 60
POSITION_PCT = env_pct("WATCH_POSITION_PCT", 50)  # no strategy is built past 40%
EXPOSURE_PCT = env_pct("WATCH_EXPOSURE_PCT", 100)  # the engine caps itself at 95%
KILL_SLIPPAGE = env_pct("WATCH_KILL_SLIPPAGE", 5)
DRY_RUN = os.getenv("WATCH_DRY_RUN", "0").strip().lower() in ("1", "true", "yes", "on")

BLIND_SECONDS = 60              # an account unreadable this long -> alert
ENGINE_CHECK_SECONDS = 60       # how often the engine's log is read
HEARTBEAT_MINUTES = 5           # the engine logs a "health" line every minute
REPEAT_SECONDS = 30 * 60        # a standing problem is re-sent at most this often
CLAUDE_WAKE_SECONDS = 15 * 60   # Claude is woken at most this often (STOP: always)
KILL_PASSES = 24                # STOP sweeps the accounts up to this many times,
KILL_PASS_SECONDS = 5           # this far apart - two minutes to get flat

ACCOUNTS = (("v31", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
            ("v32", "V32_API_KEY", "V32_SECRET_KEY"),
            ("v34", "V33_API_KEY", "V33_SECRET_KEY"),
            ("v35", "V35_API_KEY", "V35_SECRET_KEY"))

URGENT, HIGH, NORMAL = 5, 4, 3              # ntfy priorities

log = logging.getLogger("watchman")


def in_session(now: datetime) -> bool:
    return now.weekday() < 5 and SESSION[0] <= (now.hour, now.minute) < SESSION[1]


def nothing_traded_today(now: datetime) -> bool:
    """As r34.py: midnight-4am ET and weekends, live equity IS the day's start
    (Alpaca's last_equity is still a day behind then)."""
    return now.weekday() >= 5 or (now.hour, now.minute) < SESSION[0]


def num(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def enum_text(x) -> str:
    return str(getattr(x, "value", x) or "").lower()


def parse_ts(s: str) -> datetime:
    """Render's timestamps carry nanoseconds; datetime takes six digits."""
    s = re.sub(r"(\.\d{6})\d+", r"\1", s.replace("Z", "+00:00"))
    return datetime.fromisoformat(s)


def tick(price: float) -> float:
    """Alpaca accepts pennies at $1 and up, four decimals below."""
    return round(price, 2) if price >= 1 else round(price, 4)


# ----------------------------------------------------------------------------
# THE OUTSIDE WORLD - each behind a small class, so tests can hand in fakes
# ----------------------------------------------------------------------------

class Ntfy:
    """Alerts to the phone, and the STOP button's way back."""

    def __init__(self, server, topic, command_topic="", kill_code="", token="",
                 http=requests):
        self.server = server.rstrip("/")
        self.topic = topic
        self.command_topic = command_topic
        self.kill_code = kill_code
        self.token = token
        self.http = http

    def auth(self):
        return {"Authorization": "Bearer %s" % self.token} if self.token else {}

    def send(self, title, message, priority=NORMAL, stop_button=True):
        body = {"topic": self.topic, "title": title, "message": message,
                "priority": priority}
        if stop_button and self.command_topic and self.kill_code:
            # An "http" action: the tap itself posts the command. No app opens,
            # no page loads - one tap and STOP is on its way.
            action = {"action": "http", "label": "STOP EVERYTHING",
                      "url": "%s/%s" % (self.server, self.command_topic),
                      "method": "POST", "body": "KILL %s" % self.kill_code,
                      "clear": True}
            if self.token:
                action["headers"] = self.auth()
            body["actions"] = [action]
        r = self.http.post(self.server + "/", json=body, headers=self.auth(),
                           timeout=10)
        r.raise_for_status()

    def commands(self):
        """Every message posted to the command topic from now on. Blocks; ntfy
        sends a keepalive about every 45 seconds, so a silent minute and a half
        means the connection is dead and the caller reconnects."""
        url = "%s/%s/json" % (self.server, self.command_topic)
        with self.http.get(url, stream=True, headers=self.auth(),
                           timeout=(10, 90)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                if event.get("event") == "message":
                    yield event.get("message", "")


class RenderAPI:
    """The engine's service on Render: suspend it, and read its log."""

    BASE = "https://api.render.com/v1"

    def __init__(self, api_key, service_id, owner_id, http=requests):
        self.headers = {"Authorization": "Bearer %s" % api_key,
                        "Accept": "application/json"}
        self.service_id = service_id
        self.owner_id = owner_id
        self.http = http

    def service(self) -> dict:
        r = self.http.get("%s/services/%s" % (self.BASE, self.service_id),
                          headers=self.headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def suspend(self):
        r = self.http.post("%s/services/%s/suspend" % (self.BASE, self.service_id),
                           headers=self.headers, timeout=15)
        r.raise_for_status()

    def logs(self, start, end, *, text=None, level=None, direction="backward",
             limit=20):
        params = {"ownerId": self.owner_id, "resource": [self.service_id],
                  "startTime": start.astimezone(timezone.utc).isoformat(),
                  "endTime": end.astimezone(timezone.utc).isoformat(),
                  "direction": direction, "limit": limit}
        if text:
            params["text"] = [text]
        if level:
            params["level"] = [level]
        r = self.http.get(self.BASE + "/logs", params=params,
                          headers=self.headers, timeout=15)
        r.raise_for_status()
        return [(parse_ts(row["timestamp"]), row.get("message", ""))
                for row in r.json().get("logs", [])]

    def last_health(self, now, minutes):
        """When the engine last logged its once-a-minute health line, or None
        if it has not in `minutes`."""
        rows = self.logs(now - timedelta(minutes=minutes), now,
                         text="*health*", limit=1)
        return rows[0][0] if rows else None

    def critical_since(self, since, now):
        return self.logs(since, now, level="critical", direction="forward",
                         limit=50)


class ClaudeRoutine:
    """Wakes a Claude Code routine with the alert as its input. The routine's
    own prompt says what to do with it (read the engine's log, check the
    accounts, report). Routines are a research preview: the beta header is
    dated and the API may change - check it when turning this on."""

    def __init__(self, routine_id, token, http=requests):
        self.url = ("https://api.anthropic.com/v1/claude_code/routines/%s/fire"
                    % routine_id)
        self.token = token
        self.http = http

    def fire(self, text):
        r = self.http.post(self.url, json={"text": text[:4000]}, timeout=15,
                           headers={"Authorization": "Bearer %s" % self.token,
                                    "anthropic-version": "2023-06-01",
                                    "anthropic-beta":
                                        "experimental-cc-routine-2026-04-01"})
        r.raise_for_status()


# ----------------------------------------------------------------------------
# ONE ACCOUNT
# ----------------------------------------------------------------------------

@dataclass
class Watch:
    name: str
    trading: object                          # alpaca TradingClient
    data: object = None                      # alpaca StockHistoricalDataClient
    day: object = None                       # the date baseline belongs to
    baseline: float = 0.0                    # equity at the start of the day
    equity: float = 0.0
    positions: list = field(default_factory=list)
    history: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_ok: float = 0.0                     # when Alpaca last answered
    warned: int = 0                          # down-on-the-day levels sent today

    def day_pct(self) -> float:
        return self.equity / self.baseline - 1 if self.baseline > 0 else 0.0


def holding(positions, most=5) -> str:
    if not positions:
        return "No positions."
    parts = ["%s %s ($%s)" % (p.symbol, p.qty, format(abs(num(p.market_value)), ",.0f"))
             for p in positions[:most]]
    more = " and %d more" % (len(positions) - most) if len(positions) > most else ""
    return "Holding " + ", ".join(parts) + more + "."


# ----------------------------------------------------------------------------
# THE WATCHMAN
# ----------------------------------------------------------------------------

class Watchman:

    def __init__(self, watches, phone, render=None, claude=None, *, paper=True,
                 kill_code="", feed=DataFeed.SIP, clock=time.time,
                 sleep=time.sleep):
        self.watches = watches
        self.phone = phone
        self.render = render
        self.claude = claude
        self.mode = "paper" if paper else "LIVE"
        self.kill_code = kill_code
        self.feed = feed
        self.clock = clock
        self.sleep = sleep
        self.started = clock()
        self.today = None
        self.sent = {}                       # alert key -> when it went out
        self.stopped = False                 # STOP has run today
        self.stop_lock = threading.Lock()
        self.last_wake = 0.0
        self.last_engine = 0.0
        self.engine_log_from = None
        self.announced = False
        self.duty_day = None

    def now(self) -> datetime:
        return datetime.fromtimestamp(self.clock(), ET)

    # ---- telling people -----------------------------------------------------

    def tell(self, title, message, priority=NORMAL, stop_button=True):
        title = "[%s] %s" % (self.mode, title)
        log.warning("%s - %s", title, message)
        try:
            self.phone.send(title, message, priority, stop_button)
        except Exception as e:
            log.error("phone alert failed: %s", e)

    def alert(self, key, priority, title, message, repeat=None) -> bool:
        """Sent once a day per key - or, with `repeat`, again after that many
        seconds while the problem stands. HIGH and URGENT also wake Claude."""
        t = self.clock()
        last = self.sent.get(key)
        if last is not None and (repeat is None or t - last < repeat):
            return False
        self.sent[key] = t
        self.tell(title, message, priority)
        if priority >= HIGH:
            self.wake_claude("[%s] %s\n%s" % (self.mode, title, message))
        return True

    def wake_claude(self, text, force=False):
        if not self.claude:
            return
        t = self.clock()
        if not force and t - self.last_wake < CLAUDE_WAKE_SECONDS:
            return
        self.last_wake = t
        try:
            self.claude.fire(text)
        except Exception as e:
            log.error("could not wake Claude: %s", e)

    def summary(self) -> str:
        rows = []
        for w in self.watches:
            rows.append("%s %s (%+.1f%% today), %d position(s)"
                        % (w.name, format(w.equity, ",.2f"), 100 * w.day_pct(),
                           len(w.positions)))
        return "\n".join(rows) or "No accounts."

    # ---- one pass -----------------------------------------------------------

    def step(self) -> float:
        """Check everything once. Returns how long to wait before the next."""
        now = self.now()
        if self.today != now.date():
            self.today = now.date()
            self.sent.clear()
            self.stopped = False
        for w in self.watches:
            self.check_account(w, now)
        self.check_engine(now)
        self.on_duty(now)
        return CHECK_SECONDS if in_session(now) else IDLE_SECONDS

    def on_duty(self, now):
        """A message at start-up and every weekday at 3:55am - so there is
        always a recent notification with the STOP button on the phone."""
        due = (now.weekday() < 5 and (now.hour, now.minute) >= ON_DUTY_AT
               and self.duty_day != now.date())
        if not self.announced:
            self.announced = True
            if due:                     # started after 3:55 - this is today's
                self.duty_day = now.date()
            self.tell("Watchman started", self.summary(), NORMAL)
        elif due:
            self.duty_day = now.date()
            self.tell("Watchman on duty", self.summary(), NORMAL)

    def check_account(self, w, now):
        t = self.clock()
        try:
            acct = w.trading.get_account()
            positions = w.trading.get_all_positions()
        except Exception as e:
            dark = t - (w.last_ok or self.started)
            if dark >= BLIND_SECONDS:
                self.alert("%s:blind" % w.name, HIGH,
                           "%s: can't see the account" % w.name,
                           "Alpaca hasn't answered for %d+ min: %s"
                           % (dark // 60, e), repeat=REPEAT_SECONDS)
            return
        w.last_ok = t
        equity = num(acct.equity)
        if w.day != now.date() or w.baseline <= 0:
            w.day = now.date()
            w.baseline = (equity if nothing_traded_today(now)
                          else num(getattr(acct, "last_equity", 0)) or equity)
            w.warned = 0
            w.history.clear()
        w.equity = equity
        w.positions = list(positions)
        w.history.append((t, equity))
        if equity > 0:
            self.rules(w, acct, now)

    def rules(self, w, acct, now):
        t = self.clock()
        loss = -w.day_pct()
        positions = w.positions

        # The hard line: past the engine's own halt, so its halt has failed.
        if KILL_PCT and loss >= KILL_PCT and not self.stopped:
            self.stop_everything("%s is down %.1f%% on the day - past the %.0f%% "
                                 "hard line" % (w.name, 100 * loss, 100 * KILL_PCT))
            return

        if WARN_PCT and loss >= WARN_PCT:
            level = 1 + (int((loss - WARN_PCT) / WARN_STEP) if WARN_STEP else 0)
            if level > w.warned:
                w.warned = level
                self.alert("%s:down%d" % (w.name, level), HIGH,
                           "%s down %.1f%% today" % (w.name, 100 * loss),
                           "Equity %s against %s at the start of the day. %s"
                           % (format(w.equity, ",.2f"), format(w.baseline, ",.2f"),
                              holding(positions)))

        if FAST_DROP_PCT:
            recent = [e for ts, e in w.history if t - ts <= FAST_DROP_SECONDS]
            peak = max(recent)
            drop = 1 - w.equity / peak if peak > 0 else 0.0
            if drop >= FAST_DROP_PCT:
                self.alert("%s:fast" % w.name, HIGH,
                           "%s fell %.1f%% in %d min" % (w.name, 100 * drop,
                                                         FAST_DROP_SECONDS // 60),
                           "From %s to %s. %s" % (format(peak, ",.2f"),
                                                  format(w.equity, ",.2f"),
                                                  holding(positions)),
                           repeat=REPEAT_SECONDS)

        total = 0.0
        for p in positions:
            value = abs(num(p.market_value))
            total += value
            if POSITION_PCT and value > w.equity * POSITION_PCT:
                self.alert("%s:big:%s" % (w.name, p.symbol), HIGH,
                           "%s: %s is %.0f%% of the account"
                           % (w.name, p.symbol, 100 * value / w.equity),
                           "%s shares, $%s. No strategy is built to hold more "
                           "than 40%% in one name." % (p.qty, format(value, ",.0f")))
        if EXPOSURE_PCT and total > w.equity * EXPOSURE_PCT:
            self.alert("%s:exposure" % w.name, HIGH,
                       "%s holds %.0f%% of its equity" % (w.name, 100 * total / w.equity),
                       "The engine caps itself at 95%%. %s" % holding(positions))

        if positions and not in_session(now):
            self.alert("%s:after" % w.name, HIGH,
                       "%s still holds %d position(s) outside the session"
                       % (w.name, len(positions)),
                       "The engine closes everything from 7pm. %s" % holding(positions))

        flags = [f for f in ("trading_blocked", "account_blocked")
                 if getattr(acct, f, False)]
        status = enum_text(getattr(acct, "status", "active"))
        if flags or status != "active":
            self.alert("%s:blocked" % w.name, URGENT,
                       "%s: Alpaca has restricted the account" % w.name,
                       "Status %s %s" % (status.upper(), " ".join(flags)))

    def check_engine(self, now):
        """Once a minute: is the engine alive, and has it logged anything
        CRITICAL - a halt, a self-check violation, a broker it cannot reach?"""
        if not self.render:
            return
        t = self.clock()
        if t - self.last_engine < ENGINE_CHECK_SECONDS:
            return
        self.last_engine = t
        try:
            service = self.render.service()
            if enum_text(service.get("suspended")) == "suspended":
                if not self.stopped:
                    self.alert("engine:suspended", NORMAL,
                               "The engine is suspended on Render",
                               "Nothing is trading. Resume it on Render when ready.")
                return
            up_for = t - self.started
            if (up_for > HEARTBEAT_MINUTES * 60
                    and self.render.last_health(now, HEARTBEAT_MINUTES) is None):
                self.alert("engine:silent", URGENT, "The engine has gone silent",
                           "No health line from the trading engine on Render for "
                           "%d+ minutes - it may have crashed or frozen. Positions "
                           "are unguarded until it is back." % HEARTBEAT_MINUTES,
                           repeat=REPEAT_SECONDS)
            start = self.engine_log_from or now - timedelta(seconds=ENGINE_CHECK_SECONDS)
            self.engine_log_from = now
            for _, line in self.render.critical_since(start, now):
                said = line.split("CRITICAL", 1)[-1].strip()
                kind = re.sub(r"[\d.,%$@=]+", "#", said)[:50]
                self.alert("engine:%s" % kind, HIGH, "Engine: %s" % said[:80],
                           line[-400:], repeat=REPEAT_SECONDS)
        except Exception as e:
            log.error("render: %s", e)
            self.alert("render:blind", NORMAL, "Can't read the engine on Render",
                       str(e)[:300], repeat=REPEAT_SECONDS)

    # ---- STOP EVERYTHING ----------------------------------------------------

    def command(self, text):
        """A message on the command topic: 'KILL <code>' or 'STATUS <code>'."""
        parts = (text or "").strip().split()
        if not parts or parts[0].upper() not in ("KILL", "STOP", "STATUS"):
            return
        verb = parts[0].upper()
        code = parts[1] if len(parts) > 1 else ""
        if not self.kill_code or code != self.kill_code:
            self.alert("command:badcode", HIGH, "A command arrived with the wrong code",
                       "'%s' reached the command topic without the right code and "
                       "was ignored. If that was not you, change WATCH_KILL_CODE "
                       "and the topic names." % verb, repeat=REPEAT_SECONDS)
            return
        if verb == "STATUS":
            self.tell("Status", self.summary(), NORMAL)
            return
        self.stop_everything("you pressed STOP")

    def stop_everything(self, reason):
        if not self.stop_lock.acquire(blocking=False):
            return                      # one STOP at a time; it finishes the job
        try:
            self.stopped = True
            dry = " - DRY RUN, nothing is being done" if DRY_RUN else ""
            self.tell("STOPPING EVERYTHING" + dry, "Why: %s" % reason, URGENT,
                      stop_button=False)
            engine = self.stop_engine()
            left = self.flatten()
            if DRY_RUN:
                title = "STOP rehearsed (dry run)"
                lines = [engine] + ["%s would sell: %s" % (k, ", ".join(v))
                                    for k, v in left.items()]
            elif left:
                title = "STOP: STILL HOLDING POSITIONS"
                lines = [engine] + ["%s still holds %s - close by hand"
                                    % (k, ", ".join(v)) for k, v in left.items()]
            else:
                title = "STOPPED - every account is flat"
                lines = [engine, "Every order cancelled, every position sold."]
            lines.append("Why: %s. Nothing restarts until the engine is resumed "
                         "on Render." % reason)
            report = "\n".join(lines)
            self.tell(title, report, URGENT, stop_button=bool(left) and not DRY_RUN)
            self.wake_claude("[%s] %s\n%s" % (self.mode, title, report), force=True)
        finally:
            self.stop_lock.release()

    def stop_engine(self) -> str:
        if not self.render:
            return "Engine NOT stopped - no Render key. Suspend it on Render by hand."
        if DRY_RUN:
            return "Would suspend the engine on Render."
        try:
            self.render.suspend()
            return "Engine suspended on Render - nothing can buy."
        except Exception as e:
            return ("COULD NOT SUSPEND THE ENGINE (%s) - suspend it on Render "
                    "by hand." % e)

    def flatten(self) -> dict:
        """Cancel every order and sell every position, every account, until
        flat or out of passes. Returns {account: [symbols still held]}."""
        left = {}
        for _ in range(KILL_PASSES):
            market_open = self.market_open()
            left = {}
            for w in self.watches:
                held = self.flatten_account(w, market_open)
                if held:
                    left[w.name] = held
            if not left or DRY_RUN:
                break
            self.sleep(KILL_PASS_SECONDS)
        return left

    def flatten_account(self, w, market_open) -> list:
        try:
            if not DRY_RUN:
                w.trading.cancel_orders()
            positions = w.trading.get_all_positions()
        except Exception as e:
            log.error("[%s] STOP could not read the account: %s", w.name, e)
            return ["(account unreadable)"]
        if not positions:
            return []
        if not DRY_RUN:
            self.sleep(1)               # let the cancels release the shares
        for p in positions:
            try:
                order = self.closing_order(w, p, market_open)
                if DRY_RUN:
                    log.warning("[%s] dry run - would send %s", w.name, order)
                else:
                    w.trading.submit_order(order)
            except Exception as e:
                log.error("[%s] STOP could not close %s: %s", w.name, p.symbol, e)
        return [p.symbol for p in positions]

    def closing_order(self, w, p, market_open):
        qty = abs(num(p.qty))
        qty = int(qty) if qty == int(qty) else qty
        short = num(p.qty) < 0 or enum_text(getattr(p, "side", "")) == "short"
        side = OrderSide.BUY if short else OrderSide.SELL     # closes, never opens
        if market_open:
            return MarketOrderRequest(symbol=p.symbol, qty=qty, side=side,
                                      time_in_force=TimeInForce.DAY)
        bid, ask = self.quote(w, p.symbol)
        ref = ((ask if short else bid) or num(getattr(p, "current_price", 0))
               or num(getattr(p, "avg_entry_price", 0)))
        if ref <= 0:
            raise ValueError("no price to sell %s at" % p.symbol)
        price = ref * (1 + KILL_SLIPPAGE) if short else ref * (1 - KILL_SLIPPAGE)
        return LimitOrderRequest(symbol=p.symbol, qty=qty, side=side,
                                 time_in_force=TimeInForce.DAY,
                                 limit_price=tick(price), extended_hours=True)

    def market_open(self) -> bool:
        """The regular session, from Alpaca's clock. Unknown -> False: limit
        orders work in every session, market orders only 9:30-4."""
        try:
            return bool(self.watches[0].trading.get_clock().is_open)
        except Exception:
            return False

    def quote(self, w, symbol):
        try:
            q = w.data.get_stock_latest_quote(
                StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=self.feed))[symbol]
            return num(q.bid_price), num(q.ask_price)
        except Exception:
            return 0.0, 0.0

    # ---- running ------------------------------------------------------------

    def listen(self):
        while True:
            try:
                for text in self.phone.commands():
                    self.command(text)
            except Exception as e:
                log.error("command stream: %s - reconnecting", e)
            self.sleep(5)

    def run(self):
        log.info("%s up | %s | %s | check %ss in session, %ss outside | warn %.0f%%, "
                 "hard line %s | STOP %s | engine %s | Claude %s%s",
                 VERSION, self.mode, ", ".join(w.name for w in self.watches),
                 CHECK_SECONDS, IDLE_SECONDS, 100 * WARN_PCT,
                 "%.0f%%" % (100 * KILL_PCT) if KILL_PCT else "off",
                 "armed" if self.phone.command_topic and self.kill_code else
                 "NOT ARMED (no NTFY_COMMAND_TOPIC / WATCH_KILL_CODE)",
                 "watched" if self.render else "NOT watched (no Render key)",
                 "wakes on alerts" if self.claude else "not connected",
                 " | DRY RUN" if DRY_RUN else "")
        if self.phone.command_topic and self.kill_code:
            threading.Thread(target=self.listen, daemon=True).start()
        while True:
            try:
                wait = self.step()
            except Exception as e:
                log.exception("check failed: %s", e)
                wait = CHECK_SECONDS
            self.sleep(wait)


def build() -> Watchman:
    paper = os.getenv("ALPACA_PAPER", "1").strip().lower() in (
        "1", "true", "t", "yes", "y", "on")
    feed = DataFeed.IEX if os.getenv("ALPACA_FEED", "sip").strip().lower() == "iex" \
        else DataFeed.SIP
    watches = []
    for name, key_var, secret_var in ACCOUNTS:
        key, secret = os.getenv(key_var), os.getenv(secret_var)
        if not key or not secret:
            log.info("%s: no keys (%s) - not watched", name, key_var)
            continue
        watches.append(Watch(name, TradingClient(key, secret, paper=paper),
                             StockHistoricalDataClient(key, secret)))
    if not watches:
        raise SystemExit("No account keys - nothing to watch.")
    kill_code = os.getenv("WATCH_KILL_CODE", "").strip()
    phone = Ntfy(os.getenv("NTFY_SERVER", "https://ntfy.sh"), os.environ["NTFY_TOPIC"],
                 os.getenv("NTFY_COMMAND_TOPIC", "").strip(), kill_code,
                 os.getenv("NTFY_TOKEN", "").strip())
    render_vars = [os.getenv(v, "").strip() for v in
                   ("RENDER_API_KEY", "RENDER_SERVICE_ID", "RENDER_OWNER_ID")]
    render = RenderAPI(*render_vars) if all(render_vars) else None
    claude_vars = [os.getenv(v, "").strip() for v in
                   ("CLAUDE_ROUTINE_ID", "CLAUDE_ROUTINE_TOKEN")]
    claude = ClaudeRoutine(*claude_vars) if all(claude_vars) else None
    return Watchman(watches, phone, render, claude, paper=paper,
                    kill_code=kill_code, feed=feed)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    build().run()
