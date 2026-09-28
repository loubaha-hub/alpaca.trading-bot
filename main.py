"""
Alpaca v31 (2026-09-28), self-built scanner. FIRST VERSION OF THE RUNNER DESIGN - UNTESTED IN THE MARKET.
IDEA: 1-2 stocks a day run big; lose little on the false starts and ride the runners.
1. LEADERS ONLY: among the scanner's stocks (up 10%, near the day's high, thin-safe, price rising),
   rank by 3-minute dollar volume; only the top 3 may be entered. At most 3 positions.
2. NEWS IN THE SCREENER: every 2 minutes one call fetches headlines (last 6 hours) for the whole shortlist.
   NEWS_MODE "boost" (default): stocks with fresh news rank first among the leaders; "require": only stocks
   with fresh news can be entered; "off": ignored. If the news feed fails, there are simply no news flags.
   TRIGGER: the last closed bar's volume is >= 2x the average of the 10 bars before it, and the live
   price breaks above that bar's high while the current bar is trading green.
3. PROBE, THEN ADD: the first buy is a small probe sized so that hitting its stop costs about 0.5% of
   equity (a wide stop means fewer shares; never over 10% of equity). As the stock proves itself it
   adds: at +3% a full probe, at +6% 75% of a probe, at +10% 50% of a probe (adds shrink as the trail
   widens), never past 30% of equity in one stock.
4. EXIT: the low of the last 2 closed bars is the entry stop until the trade is up 2%; then the
   ladder: 2% trail under +10%, 5% from +10% to +100%, 10% above +100%.
5. RE-ENTRY: after an exit, only above the day's high + 5 cents (resets every morning).
NOT YET IN: squeeze mode, prior-day high, 200-day average, Level 2.
SHARED BEHAVIOUR (all three strategies, rebuilt 2026-09-28):
- SCANNER unchanged: up 10% from today's open, $1-$20, refreshed every 2 minutes,
  entries checked on an ~8-second cycle.
- STILL MOVING: the live price must be within 3% of today's high (a stock that jumped
  and faded off its high is skipped).
- THIN FILTER: each of the last 3 CLOSED bars >= 30,000 shares AND >= 100,000 together.
- SPEED = (live price - last closed bar's close) / that close, must be positive,
  times a volume factor = LEVEL (30,000 -> ~0.001 ... today's highest bar volume ->
  1.9999, straight scale) x CHANGE (this bar vs previous bar, limited to 0.7-1.3).
- POSITION WATCHER: its own thread, ~4 checks a second on the live last-trade price,
  reading Alpaca's REAL positions (so late fills and restarts are covered). The
  instant a stop is hit the sell chase starts in its own thread.
- CHASE: every attempt reads the real position, cancels the stale order, re-reads the
  market and prices from the NEWEST quote for exactly the shares left. Buys chase
  upward (never above 2% over the current ask); sells chase downward, no cap.
  Always limit orders (market orders are rejected outside 9:30-4:00 ET).
- DAILY HALT: baseline = equity at the first pass of each trading day. 10% loss
  flattens everything and stops trading for the day. After a halted day the next
  day's limit is 5%, then 2.5%; a third halted day in a row stops the bot until it
  is restarted manually. A manual restart at any time resumes with a fresh baseline
  (the streak lives in memory - a crash or redeploy also resets it).
- 7:55 PM ET: flatten everything once; NO new entries after 7:55 PM. The position
  watcher only works 4:00 AM-8:00 PM ET on trading days (idle overnight and on weekends).
ASSUMPTIONS TO REVIEW AFTER REAL LOGS: SPIKE_MULT (2.0), RISK_PER_TRADE (0.5%), ADD_STEPS,
LEADER_TOP_N (3), NEWS_MODE and NEWS_WINDOW_MIN (6 hours), CHANGE_LO/HI (0.7/1.3).
Runs continuously as a background worker. Paper trading by default.
"""
import os
import time
import threading
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, GetAssetsRequest, GetOrdersRequest, GetCalendarRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass, AssetStatus, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest, StockLatestQuoteRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame

API_KEY = os.environ["ALPACA_API_KEY"]
SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
PAPER = os.environ.get("ALPACA_PAPER", "true").lower() == "true"

# ---------------- shared settings ----------------
PRICE_MIN = 1.0
PRICE_MAX = 20.0
GAIN_MIN = 0.10                 # scanner: up 10% from today's open
MAX_SPREAD = 0.10
THIN_BAR_MIN = 30000            # each of the last 3 closed bars
THIN_TOTAL_MIN = 100000         # all 3 together
LEVEL_BASE = 30000              # volume level that scores ~0
CHANGE_LO = 0.7                 # volume-change factor limits (tunable)
CHANGE_HI = 1.3
CHASE_CAP_PCT = 0.02            # buys never priced more than 2% above the CURRENT ask
NEAR_HIGH_PCT = 0.03            # 'still moving': live price within 3% of today's high
HALT_THRESHOLDS = [0.10, 0.05, 0.025]   # by number of halted days in a row
UNIVERSE_REFRESH_SECONDS = 120
FAST_CHECK_SECONDS = 5
SNAPSHOT_BATCH_SIZE = 200
WATCH_INTERVAL = 0.25           # position watcher: ~4 checks a second
WATCH_POS_REFRESH = 2.0         # how often the watcher re-reads real positions

trading = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

state = {}                      # symbol -> {"entry","peak","red_low","weight",...}
state_lock = threading.RLock()
selling = set()                 # symbols with a sell in progress (one order stream per stock)
buying = set()
full_universe = []
market_open_today = None
guard = {"day": None, "baseline": None, "halted": False, "streak": 0, "stopped": False}
guard_lock = threading.Lock()


def log(msg):
    print(f"{datetime.now(timezone.utc).isoformat()}  {msg}", flush=True)


def chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def on_position_closed(symbol):
    pass


def on_new_day():
    pass


def is_trading_day(now_et):
    global market_open_today
    if market_open_today is not None and market_open_today[0] == now_et.date():
        return market_open_today[1]
    try:
        req = GetCalendarRequest(start=now_et.date(), end=now_et.date())
        cal = trading.get_calendar(req)
        is_open = len(cal) > 0
        market_open_today = (now_et.date(), is_open)
        return is_open
    except Exception as e:
        log(f"is_trading_day error: {e} - defaulting to weekday assumption")
        return now_et.weekday() < 5


def in_session():
    """True only on a trading day between 4:00 AM and 8:00 PM ET. The watcher
    stays idle outside it (nothing can be traded overnight, and it would only
    spam orders at stale prices)."""
    now_et = datetime.now(ZoneInfo("America/New_York"))
    if not is_trading_day(now_et):
        return False
    start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
    end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
    return start <= now_et <= end


# ---------------- scanner (unchanged design) ----------------
def get_full_universe():
    try:
        req = GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
        assets = trading.get_all_assets(req)
        symbols = [a.symbol for a in assets if a.tradable and a.exchange != "OTC" and a.symbol.isalpha()]
        log(f"full universe refreshed: {len(symbols)} tradable plain-ticker symbols")
        return symbols
    except Exception as e:
        log(f"get_full_universe error: {e}")
        return []


def get_snapshots(symbols):
    result = {}
    for batch in chunked(symbols, SNAPSHOT_BATCH_SIZE):
        try:
            req = StockSnapshotRequest(symbol_or_symbols=batch)
            snaps = data_client.get_stock_snapshot(req)
            result.update(snaps)
        except Exception as e:
            log(f"get_snapshots batch error: {e}")
        time.sleep(0.1)
    return result


def pct_gain_today(snap):
    try:
        latest = snap.latest_trade.price if snap.latest_trade else None
        today_open = snap.daily_bar.open if snap.daily_bar else None
        if latest is None or today_open is None or today_open <= 0:
            return None, None
        return latest, (latest - today_open) / today_open
    except Exception:
        return None, None


def narrow_universe():
    global full_universe
    if not full_universe:
        full_universe = get_full_universe()
    if not full_universe:
        return []
    candidates = []
    snaps = get_snapshots(full_universe)
    for symbol, snap in snaps.items():
        price, gain = pct_gain_today(snap)
        if price is None or gain is None:
            continue
        if PRICE_MIN <= price <= PRICE_MAX and gain >= GAIN_MIN:
            candidates.append(symbol)
    log(f"universe narrowed: {len(candidates)} candidates out of {len(full_universe)}")
    return candidates


def fast_scan(symbols):
    if not symbols:
        return []
    snaps = get_snapshots(symbols)
    out = []
    for symbol, snap in snaps.items():
        price, gain = pct_gain_today(snap)
        if price is None or gain is None:
            continue
        if PRICE_MIN <= price <= PRICE_MAX and gain >= GAIN_MIN:
            day_high = snap.daily_bar.high if snap.daily_bar else None
            out.append({"symbol": symbol, "price": price, "percent_change": gain, "day_high": day_high})
    out.sort(key=lambda x: x["percent_change"], reverse=True)
    return out[:50]


def near_high(m):
    """Still moving: the live price is within 3% of today's high (a stock that
    jumped and faded off its high is out). No day-high data = do not block."""
    dh = m.get("day_high")
    return (not dh) or m["price"] >= dh * (1 - NEAR_HIGH_PCT)


# ---------------- market data ----------------
def get_recent_bars(symbol, limit=25):
    try:
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=datetime.now(timezone.utc) - timedelta(minutes=limit + 5),
        )
        bars = data_client.get_stock_bars(req)
        rows = bars[symbol] if symbol in bars.data else []
        return rows[-limit:] if rows else []
    except Exception as e:
        log(f"get_recent_bars({symbol}) error: {e}")
        return []


def get_day_bars(symbol):
    try:
        et = ZoneInfo("America/New_York")
        now_et = datetime.now(et)
        day_start_et = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=day_start_et.astimezone(timezone.utc),
        )
        bars = data_client.get_stock_bars(req)
        return bars[symbol] if symbol in bars.data else []
    except Exception as e:
        log(f"get_day_bars({symbol}) error: {e}")
        return []


def completed_bars(bars):
    """Only bars whose minute has closed (drops the minute still forming)."""
    now_min = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return [b for b in bars if b.timestamp < now_min]


def forming_bar(bars):
    now_min = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    for b in reversed(bars):
        if b.timestamp >= now_min:
            return b
    return None


def get_live_prices(symbols):
    """Last-trade price for many symbols in ONE call."""
    if not symbols:
        return {}
    try:
        req = StockLatestTradeRequest(symbol_or_symbols=list(symbols))
        trades = data_client.get_stock_latest_trade(req)
        return {s: float(t.price) for s, t in trades.items() if t is not None and t.price}
    except Exception as e:
        log(f"get_live_prices error: {e}")
        return {}


def get_spread(symbol):
    try:
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = data_client.get_stock_latest_quote(req)
        q = quote[symbol]
        return q.ask_price, q.bid_price
    except Exception as e:
        log(f"get_spread({symbol}) error: {e}")
        return None, None


# ---------------- thin-stock filter, volume factor, speed ----------------
def thin_ok(done):
    """The last 3 closed MINUTES: each >= 30,000 shares and >= 100,000 together.
    A minute with no bar means no trades, so the 3 bars must be consecutive
    minutes and recent (a stock that skipped a minute is thin)."""
    if len(done) < 3:
        return False
    last3 = done[-3:]
    if last3[-1].timestamp - last3[0].timestamp != timedelta(minutes=2):
        return False
    now_min = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if now_min - last3[-1].timestamp > timedelta(minutes=2):
        return False
    vols = [b.volume for b in last3]
    return all(v >= THIN_BAR_MIN for v in vols) and sum(vols) >= THIN_TOTAL_MIN


_day_max_cache = {}


def day_max_volume(symbol, day_bars=None, ttl=30):
    """Highest single closed-bar volume this stock has traded today."""
    now = time.time()
    cached = _day_max_cache.get(symbol)
    if day_bars is None and cached and now - cached[0] < ttl:
        return cached[1]
    if day_bars is None:
        day_bars = get_day_bars(symbol)
    vmax = max([b.volume for b in completed_bars(day_bars)], default=0)
    _day_max_cache[symbol] = (now, vmax)
    return vmax


def level_factor(v, vmax):
    """30,000 -> ~0.001 ... today's highest bar volume -> 1.9999, straight scale."""
    if vmax <= LEVEL_BASE:
        return 1.0
    x = (v - LEVEL_BASE) / (vmax - LEVEL_BASE)
    return max(0.001, min(1.9999, 0.001 + 1.9989 * x))


def change_factor(v, vprev):
    """This bar's volume vs the previous bar's: 1 = unchanged, >1 rising, <1 falling."""
    if vprev <= 0:
        return 1.0
    return max(CHANGE_LO, min(CHANGE_HI, v / vprev))


def volume_factor(done, vmax):
    if not done:
        return 1.0
    v = done[-1].volume
    vprev = done[-2].volume if len(done) >= 2 else v
    return level_factor(v, vmax) * change_factor(v, vprev)


def speed(done, live_price, vmax):
    """Price change from the last CLOSED bar's close to the live price (must be
    positive to count), multiplied by the volume factor (level x change)."""
    if not done or not live_price:
        return 0.0
    last = done[-1]
    if last.close <= 0:
        return 0.0
    dp = (live_price - last.close) / last.close
    if dp <= 0:
        return dp
    return dp * volume_factor(done, vmax)


# ---------------- account and positions ----------------
def get_equity():
    try:
        return float(trading.get_account().equity)
    except Exception as e:
        log(f"get_equity error: {e}")
        return 0.0


def get_positions_detail():
    """{symbol: (qty, avg_entry_price)}, or None if the call FAILED (never
    confuse a failed call with 'no positions')."""
    try:
        return {p.symbol: (int(float(p.qty)), float(p.avg_entry_price)) for p in trading.get_all_positions()}
    except Exception as e:
        log(f"get_positions_detail error: {e}")
        return None


def get_real_positions():
    d = get_positions_detail()
    return {} if d is None else {s: v[0] for s, v in d.items()}


def get_position_qty(symbol):
    d = get_positions_detail()
    if d is None:
        return None
    return d.get(symbol, (0, 0.0))[0]


def cancel_open_orders(symbol):
    n = 0
    try:
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        for o in trading.get_orders(req):
            try:
                trading.cancel_order_by_id(o.id)
                n += 1
            except Exception as e:
                log(f"cancel_open_orders({symbol}) error: {e}")
    except Exception as e:
        log(f"cancel_open_orders({symbol}) get_orders error: {e}")
    return n


# ---------------- execution: the chase ----------------
def aggressive_execute(symbol, side, target_shares, max_attempts=15, wait_seconds=0.05):
    """BUY: target_shares = holding to reach. SELL: target_shares = holding to
    sell DOWN to (0 = full exit). Every attempt: read the real position, cancel
    the stale order, re-read the market, price from the NEWEST quote, submit for
    exactly what is left. Buys chase upward (never above 2% over the current
    ask); sells chase downward with no cap so an exit always gets out."""
    t0 = time.time()
    last_bid = None
    for attempt in range(max_attempts):
        if side == OrderSide.BUY and symbol in selling:
            cancel_open_orders(symbol)         # an exit has started on this stock - stop buying it
            log(f"{symbol}: buy chase abandoned, a sell is in progress")
            return False
        have = get_position_qty(symbol)
        if have is None:                       # failed call - never assume 'closed'
            time.sleep(wait_seconds)
            continue
        remaining = (have - target_shares) if side == OrderSide.SELL else (target_shares - have)
        if remaining <= 0:
            log(f"{symbol}: FULLY EXECUTED in {(time.time() - t0) * 1000:.0f}ms ({attempt} attempt(s))")
            return True
        if cancel_open_orders(symbol):
            time.sleep(0.1)                    # let the cancel land before re-submitting
        ask, bid = get_spread(symbol)
        if not ask or not bid:
            time.sleep(wait_seconds)
            continue
        move = 0.0 if last_bid is None else abs(bid - last_bid)   # how far the market just moved
        last_bid = bid
        if side == OrderSide.SELL:
            price = max(0.01, round(bid - 0.01 - 0.01 * attempt - move, 2))
        else:
            price = round(bid + 0.01 * attempt + move, 2)
            price = min(price, round(ask * (1 + CHASE_CAP_PCT), 2))
        try:
            t1 = time.time()
            trading.submit_order(LimitOrderRequest(
                symbol=symbol, qty=remaining, side=side, time_in_force=TimeInForce.DAY,
                limit_price=price, extended_hours=True))
            log(f"{'SELL' if side == OrderSide.SELL else 'BUY'} (chase) {symbol} x{remaining} @ {price} "
                f"(bid {bid} ask {ask} attempt {attempt + 1}/{max_attempts} submit {(time.time() - t1) * 1000:.0f}ms)")
        except Exception as e:
            log(f"aggressive_execute({symbol}) submit error: {e}")
        time.sleep(wait_seconds)
    if side == OrderSide.BUY:
        cancel_open_orders(symbol)             # never leave a stale buy resting
    log(f"{symbol}: WARNING - not fully executed after {max_attempts} attempts "
        f"({(time.time() - t0) * 1000:.0f}ms)")
    return False


def begin_sell(symbol):
    with state_lock:
        if symbol in selling:
            return False
        selling.add(symbol)
        return True


def end_sell(symbol):
    with state_lock:
        selling.discard(symbol)


def place_sell(symbol, reason="", target_shares=0):
    if not begin_sell(symbol):
        log(f"{symbol}: a sell is already in progress, skipping ({reason})")
        return False
    try:
        ok = aggressive_execute(symbol, OrderSide.SELL, target_shares)
        if ok and target_shares == 0:
            with state_lock:
                state.pop(symbol, None)
            on_position_closed(symbol)
        log(f"place_sell({symbol}) {reason} -> {'done' if ok else 'NOT fully done'}")
        return ok
    finally:
        end_sell(symbol)


def sell_async(symbol, reason=""):
    threading.Thread(target=place_sell, args=(symbol, reason), daemon=True).start()


# ---------------- stops and the position watcher ----------------
def active_stop(entry, peak, red_low):
    """Entry stop = the red bar's low, until the trade is up 2%; after that the
    trailing ladder (tier_stop) takes over. red_low None = ladder only."""
    if red_low is not None and entry > 0 and peak < entry * 1.02:
        return red_low
    return tier_stop(peak, entry)


def position_watcher(stop_event=None, session_fn=None):
    """Own thread. Watches every REAL position from Alpaca (so a late fill or a
    restart is covered too) on the live last-trade price, ~4 times a second,
    independent of the entry scan. The instant a stop is hit, the sell chase
    starts in its own thread so the other positions keep being watched."""
    last_refresh = 0.0
    sold_at = {}
    pos = {}
    session = session_fn or in_session
    while stop_event is None or not stop_event.is_set():
        try:
            if not session():
                time.sleep(5.0)
                continue
            now = time.time()
            if now - last_refresh >= WATCH_POS_REFRESH:
                fresh = get_positions_detail()
                if fresh is not None:
                    pos = {s: v for s, v in fresh.items() if v[0] > 0}
                    last_refresh = now
                    with state_lock:
                        for s in list(state.keys()):
                            if s not in pos and s not in buying and s not in selling:
                                state.pop(s, None)
            if not pos:
                time.sleep(0.5)
                continue
            prices = get_live_prices(list(pos.keys()))
            for sym, (qty, avg) in pos.items():
                price = prices.get(sym)
                if not price:
                    continue
                with state_lock:
                    st = state.setdefault(sym, {})
                    st["entry"] = avg
                    st["peak"] = max(st.get("peak", max(avg, price)), price)
                    peak = st["peak"]
                    stop = active_stop(avg, peak, st.get("red_low"))
                    busy = sym in selling
                if price <= stop and not busy and time.time() - sold_at.get(sym, 0) > 3.0:
                    log(f"WATCHER: {sym} price {price} <= stop {stop:.4f} (entry {avg:.4f}, peak {peak:.4f}) - selling")
                    sold_at[sym] = time.time()
                    sell_async(sym, "stop")
            time.sleep(WATCH_INTERVAL)
        except Exception as e:
            log(f"watcher error: {e}")
            time.sleep(1.0)


# ---------------- daily halt: 10% / 5% / 2.5%, three in a row stops the bot ----------------
def roll_day(now_et, equity):
    if equity <= 0:
        return
    with guard_lock:
        today = now_et.date()
        if guard["day"] == today:
            return
        if guard["day"] is not None:
            guard["streak"] = guard["streak"] + 1 if guard["halted"] else 0
        guard["day"] = today
        guard["halted"] = False
        guard["baseline"] = equity
        if guard["streak"] >= 3:
            guard["stopped"] = True
        streak = guard["streak"]
    on_new_day()
    thr = HALT_THRESHOLDS[min(streak, 2)]
    log(f"NEW DAY {today}: baseline equity {equity:.2f}, halt threshold {thr:.1%}, "
        f"halted days in a row {streak}{' - BOT STOPPED, restart manually' if streak >= 3 else ''}")


def check_daily_halt(equity):
    with guard_lock:
        if guard["stopped"]:
            return True
        if guard["baseline"] is None or equity <= 0:
            return False
        if guard["halted"]:
            return True
        thr = HALT_THRESHOLDS[min(guard["streak"], 2)]
        loss = (guard["baseline"] - equity) / guard["baseline"]
        if loss < thr:
            return False
        guard["halted"] = True
        baseline = guard["baseline"]
    log(f"DAILY HALT: down {loss:.1%} from {baseline:.2f} (limit {thr:.1%}) - flattening everything, "
        f"no new entries for the rest of today")
    for sym, q in get_real_positions().items():
        if q > 0:
            sell_async(sym, "daily_halt")
    return True


def reconcile_on_startup():
    pos = get_positions_detail() or {}
    for sym, (q, avg) in pos.items():
        if q > 0:
            log(f"RECONCILED on startup: {sym} x{q} @ avg {avg:.4f} (the watcher will protect it)")


# ================= v31-specific: leaders only, volume-spike breakout, probe + adds =================
STRATEGY_NAME = "v31"
MAX_NAMES = 3                      # at most 3 positions - leaders only
LEADER_TOP_N = 3                   # only the top 3 by 3-minute dollar volume may be entered
SPIKE_MULT = 2.0                   # last closed bar volume >= 2x the average of the 10 bars before it
SPIKE_LOOKBACK = 10
RISK_PER_TRADE = 0.005             # a stop-out on the probe costs about 0.5% of equity
MIN_STOP_DIST_PCT = 0.01           # never size off a stop closer than 1% of the price
PROBE_MAX_PCT = 0.10               # the probe is never more than 10% of equity
MAX_POSITION_PCT = 0.30            # one stock is never more than 30% of equity
# (gain from the first entry, size of the add as a multiple of the probe): adds SHRINK as the trail widens
ADD_STEPS = [(0.03, 1.00), (0.06, 0.75), (0.10, 0.50)]
NEWS_MODE = "boost"                # "off" | "boost" (stocks with fresh news rank first among the leaders) | "require" (only stocks with fresh news can be entered)
NEWS_WINDOW_MIN = 360              # a headline counts as fresh for 6 hours
NEWS_REFRESH_SECONDS = 120         # the screener re-reads the news for the whole shortlist every 2 minutes (one call)
news_cache = {}                    # symbol -> (headline, created_at)
comeback_floor = {}
_news_client = None
_last_news_refresh = 0.0


def on_new_day():
    comeback_floor.clear()                     # yesterday's high must not block today's re-entries


def get_day_high(symbol):
    try:
        snaps = data_client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=[symbol]))
        snap = snaps.get(symbol)
        if snap and snap.daily_bar:
            return snap.daily_bar.high
    except Exception as e:
        log(f"get_day_high({symbol}) error: {e}")
    return None


def on_position_closed(symbol):
    high = get_day_high(symbol)
    if high:
        comeback_floor[symbol] = round(high + 0.05, 4)     # re-enter only above the day's high + 5c


def tier_stop(peak, entry):
    """Ladder: 2% trail under +10%; 5% from +10% to +100%; 10% above +100%."""
    if entry <= 0:
        return peak
    gain = (peak / entry) - 1.0
    if gain < 0.10:
        return peak * 0.98
    if gain < 1.00:
        return peak * 0.95
    return peak * 0.90


def refresh_news(symbols, force=False):
    """News in the SCREENER: one call for the whole shortlist every 2 minutes.
    Fills news_cache with each stock's newest headline from the last 6 hours.
    Any failure just leaves the cache empty (no news flags), never stops the bot."""
    global _news_client, _last_news_refresh
    now = time.time()
    if not symbols or (not force and now - _last_news_refresh < NEWS_REFRESH_SECONDS):
        return
    _last_news_refresh = now
    try:
        from alpaca.data.historical.news import NewsClient
        from alpaca.data.requests import NewsRequest
        if _news_client is None:
            _news_client = NewsClient(API_KEY, SECRET_KEY)
        wanted = set(symbols)
        start = datetime.now(timezone.utc) - timedelta(minutes=NEWS_WINDOW_MIN)
        result = _news_client.get_news(NewsRequest(symbols=",".join(sorted(wanted)), start=start, limit=50))
        items = result.data.get("news", []) if hasattr(result, "data") else []
        found = {}
        for n in items:
            for sym in (n.symbols or []):
                if sym in wanted and (sym not in found or n.created_at > found[sym][1]):
                    found[sym] = (n.headline, n.created_at)
        news_cache.clear()
        news_cache.update(found)
        log(f"news refreshed: {len(found)} of {len(wanted)} shortlist stocks have a headline in the last {NEWS_WINDOW_MIN} min")
    except Exception as e:
        log(f"news feed unavailable: {e}")


def volume_spike(done):
    """Last closed bar's volume >= 2x the average of the 10 bars before it."""
    if len(done) < SPIKE_LOOKBACK + 1:
        return False
    prior = [b.volume for b in done[-(SPIKE_LOOKBACK + 1):-1]]
    avg = sum(prior) / len(prior)
    return avg > 0 and done[-1].volume >= SPIKE_MULT * avg


def dollar_volume_3(done):
    return sum(b.close * b.volume for b in done[-3:])


def probe_shares(equity, ask, stop_low):
    """Size the probe so hitting the stop costs ~0.5% of equity (a wide stop means
    fewer shares), never more than 10% of equity."""
    dist = max(ask - stop_low, MIN_STOP_DIST_PCT * ask)
    by_risk = (RISK_PER_TRADE * equity) / dist
    by_cap = (PROBE_MAX_PCT * equity) / ask
    return int(min(by_risk, by_cap))


def place_buy(symbol, ask, stop_low):
    equity = get_equity()
    shares = probe_shares(equity, ask, stop_low)
    if shares <= 0:
        log(f"{symbol}: probe too small for even 1 share, skipping")
        return False
    with state_lock:
        buying.add(symbol)
        state.setdefault(symbol, {})["red_low"] = stop_low      # entry stop = the spike candle's low
    try:
        ok = aggressive_execute(symbol, OrderSide.BUY, shares)
    finally:
        with state_lock:
            buying.discard(symbol)
    if ok:
        with state_lock:
            state.setdefault(symbol, {}).update(first_entry=ask, probe_shares=shares, adds_done=[])
    return ok


def try_adds(equity, real):
    """Add to a winner as it proves itself: +3% adds a full probe, +6% adds 75% of
    a probe, +10% adds 50% - so the adds shrink as the trail widens. One add per
    stock per pass, and never past 30% of equity."""
    held = [s for s, q in real.items() if q > 0 and s not in selling and s not in buying]
    if not held:
        return
    prices = get_live_prices(held)
    for s in held:
        with state_lock:
            st = dict(state.get(s, {}))
        price = prices.get(s)
        if not price or "first_entry" not in st:          # late fills and leftovers get no adds
            continue
        gain = price / st["first_entry"] - 1.0
        for i, (step, mult) in enumerate(ADD_STEPS):
            if i in st.get("adds_done", []) or gain < step:
                continue
            q = real[s]
            target = min(q + int(st["probe_shares"] * mult), int(MAX_POSITION_PCT * equity // price))
            log(f"ADD {s} step {i + 1} (gain {gain:.1%}): {q} -> {target} shares")
            if target > q:
                aggressive_execute(s, OrderSide.BUY, target)
            with state_lock:
                state.setdefault(s, {}).setdefault("adds_done", []).append(i)
            break


def run_cycle(movers):
    log(f"cycle check: {len(movers)} movers found: {[m['symbol'] for m in movers]}")
    if guard["stopped"]:
        log("STOPPED: three halted days in a row - restart the service manually to resume")
        return
    equity = get_equity()
    if check_daily_halt(equity):
        return
    real = get_real_positions()
    try_adds(equity, real)
    held_count = len([s for s, q in real.items() if q > 0]) + len(buying)
    if NEWS_MODE != "off":
        refresh_news([m["symbol"] for m in movers])

    # pass 1: everything that is thin-safe, near its high and going up
    cands = []
    for m in movers:
        symbol, price = m["symbol"], m["price"]
        if not near_high(m):
            continue
        if real.get(symbol, 0) > 0 or symbol in buying or symbol in selling:
            continue
        floor = comeback_floor.get(symbol)
        if floor is not None and price < floor:
            continue
        raw = get_recent_bars(symbol, limit=15)
        done = completed_bars(raw)
        if not thin_ok(done):
            continue
        if speed(done, price, day_max_volume(symbol)) <= 0:
            continue
        cands.append({"symbol": symbol, "price": price, "raw": raw, "done": done,
                      "dv3": dollar_volume_3(done), "news": news_cache.get(symbol) if NEWS_MODE != "off" else None})

    # pass 2: leaders only - the top 3 by 3-minute dollar volume (stocks with fresh news first in "boost" mode)
    if NEWS_MODE == "require":
        cands = [c for c in cands if c["news"]]
    cands.sort(key=lambda c: (bool(c["news"]) if NEWS_MODE == "boost" else False, c["dv3"]), reverse=True)
    leaders = cands[:LEADER_TOP_N]
    if leaders:
        log(f"leaders: {[(c['symbol'], round(c['dv3']), 'NEWS' if c['news'] else '') for c in leaders]}")

    # pass 3: a leader with a volume spike that is breaking above the last bar's high gets a probe
    for c in leaders:
        if held_count >= MAX_NAMES:
            break
        symbol, price, done = c["symbol"], c["price"], c["done"]
        if not volume_spike(done):
            continue
        if price <= done[-1].high:
            continue
        cur = forming_bar(c["raw"])
        if cur is not None and price <= cur.open:            # the entry bar must be trading green
            continue
        ask, bid = get_spread(symbol)
        if ask is None or bid is None or ask <= 0 or ask - bid > MAX_SPREAD:
            continue
        stop_low = min(b.low for b in done[-2:])
        headline = c["news"][0] if c["news"] else None
        log(f"ENTRY SIGNAL {symbol}: leader, volume spike, breakout at {price}, stop {stop_low}, headline: {headline}")
        if place_buy(symbol, ask, stop_low):
            held_count += 1


def main_loop(max_iterations=None, now_fn=None, sleep_fn=time.sleep):
    et = ZoneInfo("America/New_York")
    last_universe_refresh = 0
    shortlist = []
    eod_done_date = None
    n = 0
    while max_iterations is None or n < max_iterations:
        n += 1
        now_et = now_fn() if now_fn else datetime.now(et)
        start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
        eod_time = now_et.replace(hour=19, minute=55, second=0, microsecond=0)

        if not is_trading_day(now_et):
            log(f"not a trading day ({now_et.strftime('%A, %Y-%m-%d')}) - idle")
        elif start <= now_et <= end:
            try:
                roll_day(now_et, get_equity())
                if now_et >= eod_time:
                    # 7:55 PM ET: flatten once, and NO new entries after it
                    if eod_done_date != now_et.date():
                        log(f"END OF DAY FLATTEN: {now_et.strftime('%H:%M')} ET - closing every real position")
                        for sym, q in get_real_positions().items():
                            if q > 0:
                                sell_async(sym, "end_of_day_flatten")
                        eod_done_date = now_et.date()
                else:
                    now_unix = time.time()
                    if now_unix - last_universe_refresh >= UNIVERSE_REFRESH_SECONDS:
                        shortlist = narrow_universe()
                        last_universe_refresh = now_unix
                    run_cycle(fast_scan(shortlist))
            except Exception as e:
                log(f"main loop error: {e}")
        else:
            log(f"outside trading window (4am-8pm ET), current ET time: {now_et.strftime('%H:%M')}")

        sleep_fn(FAST_CHECK_SECONDS)


if __name__ == "__main__":
    log(f"Starting Alpaca {STRATEGY_NAME} bot (REBUILT 2026-09-28: position watcher, chase, halt ladder). paper={PAPER}")
    try:
        acct = trading.get_account()
        log(f"ACCOUNT CHECK OK: status={acct.status}, cash={acct.cash}")
    except Exception as e:
        log(f"ACCOUNT CHECK FAILED: {e}")

    reconcile_on_startup()
    threading.Thread(target=position_watcher, name="watcher", daemon=True).start()
    main_loop()
  
