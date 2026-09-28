"""
Alpaca v27 (REBUILT 2026-09-28), self-built scanner.
ENTRY: two CLOSED bars, green then red. During the NEXT bar, when the live price crosses
above the red bar's open + 1 cent (and that bar is trading green), plus: 9-EMA above
20-EMA, price above VWAP, MACD(12,26,9) above zero and above its signal line, spread
<= 10c.
ENTRY STOP: the red bar's low, until the trade is up 2%; then the trailing ladder:
2% trail under +10%, 5% from +10% to +100%, 10% above +100%.
SIZE: 2 positions; the stronger (speed x dollar-volume) holds 60%, the weaker 40%.
Re-split at most every 5 minutes (sooner if a stock moves very fast). A stronger
newcomer replaces the weakest and takes the 60% if it outranks the survivor.
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
- 7:55 PM ET: flatten everything once; NO new entries after 7:55 PM.
ASSUMPTIONS TO REVIEW AFTER REAL LOGS: CHANGE_LO/HI (0.7/1.3), FAST_MOVE_OVERRIDE_SPEED
(0.05), SHUFFLE_MIN_EDGE, DOLLAR_VOLUME_REFERENCE (v27).
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


def position_watcher(stop_event=None):
    """Own thread. Watches every REAL position from Alpaca (so a late fill or a
    restart is covered too) on the live last-trade price, ~4 times a second,
    independent of the entry scan. The instant a stop is hit, the sell chase
    starts in its own thread so the other positions keep being watched."""
    last_refresh = 0.0
    sold_at = {}
    pos = {}
    while stop_event is None or not stop_event.is_set():
        try:
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


# ================= v27-specific =================
STRATEGY_NAME = "v27"
SLOTS = 2
POSITION_WEIGHTS = [0.60, 0.40]          # stronger stock gets 60%
DOLLAR_VOLUME_REFERENCE = 200000         # assumption - tune after real logs
SHUFFLE_MIN_EDGE = 0.01                  # assumption - tune after real logs
BALANCE_MIN_GAP_SECONDS = 300            # re-split 60/40 at most every 5 minutes...
FAST_MOVE_OVERRIDE_SPEED = 0.05          # ...unless a stock is moving very fast (assumption)


def three_candle_pullback(done):
    """Two CLOSED bars: green, then red. Returns (trigger, red_bar_low) or None.
    The entry fires when the LIVE price crosses above trigger (red open + 1c)."""
    if len(done) < 2:
        return None
    prev, last = done[-2], done[-1]
    if prev.close > prev.open and last.close < last.open:
        return round(last.open + 0.01, 4), last.low
    return None


def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def ema9_above_ema20(done):
    if len(done) < 20:
        return False
    closes = [b.close for b in done]
    e9 = ema(closes[-20:], 9)
    e20 = ema(closes[-20:], 20)
    return e9 is not None and e20 is not None and e9 > e20


def compute_macd(closes):
    if len(closes) < 35:
        return None, None
    k12, k26, k9 = 2 / 13, 2 / 27, 2 / 10
    e12 = e26 = closes[0]
    macd_series = []
    for c in closes:
        e12 = c * k12 + e12 * (1 - k12)
        e26 = c * k26 + e26 * (1 - k26)
        macd_series.append(e12 - e26)
    sig = macd_series[0]
    for m in macd_series:
        sig = m * k9 + sig * (1 - k9)
    return macd_series[-1], sig


def macd_positive(done):
    macd_line, signal_line = compute_macd([b.close for b in done])
    if macd_line is None or signal_line is None:
        return False
    return macd_line > 0 and macd_line > signal_line


def compute_vwap(day_bars):
    total_volume = sum(b.volume for b in day_bars)
    if total_volume <= 0:
        return None
    return sum(b.close * b.volume for b in day_bars) / total_volume


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


def dollar_volume_factor(done):
    if not done:
        return 1.0
    dollar_vol = done[-1].close * done[-1].volume
    return max(0.5, min(2.0, dollar_vol / DOLLAR_VOLUME_REFERENCE))


def combined_score(done, live_price, vmax):
    return speed(done, live_price, vmax) * dollar_volume_factor(done)


def place_buy(symbol, ask, weight, red_low):
    equity = get_equity()
    shares = int(equity * weight // ask)
    if shares <= 0:
        log(f"{symbol}: allocation too small for even 1 share, skipping")
        return False
    with state_lock:
        buying.add(symbol)
        state.setdefault(symbol, {})["red_low"] = red_low     # so the watcher has the stop from the first fill
    try:
        ok = aggressive_execute(symbol, OrderSide.BUY, shares)
    finally:
        with state_lock:
            buying.discard(symbol)
    if ok:
        with state_lock:
            state.setdefault(symbol, {}).update(weight=weight, last_rebalance_ts=time.time())
    return ok


def score_held(held):
    prices = get_live_prices(held)
    scores, speeds = {}, {}
    for s in held:
        done = completed_bars(get_recent_bars(s, limit=15))
        vmax = day_max_volume(s)
        speeds[s] = speed(done, prices.get(s), vmax)
        scores[s] = speeds[s] * dollar_volume_factor(done)
    return prices, scores, speeds


def try_shuffle(candidate, cand_score, cand_ask, cand_red_low, real):
    held = [s for s, q in real.items() if q > 0]
    if len(held) < SLOTS:
        return False
    prices, scores, speeds = score_held(held)
    weakest = min(held, key=lambda s: scores[s])
    if cand_score - scores[weakest] < SHUFFLE_MIN_EDGE:
        return False
    survivors = [s for s in held if s != weakest]
    weight = POSITION_WEIGHTS[0] if all(cand_score >= scores[s] for s in survivors) else POSITION_WEIGHTS[-1]
    log(f"SHUFFLE: {candidate} (score {cand_score:.4f}) replaces {weakest} (score {scores[weakest]:.4f}), weight {weight:.0%}")
    if place_sell(weakest, "replaced by stronger newcomer"):
        place_buy(candidate, cand_ask, weight, cand_red_low)
    return True


def try_rebalance(equity, real):
    """Two holdings: the stronger one holds 60%, the weaker 40%. Re-split at most
    every 5 minutes (sooner only if a stock is moving very fast), and only when
    the two scores differ by a real margin."""
    held = [s for s, q in real.items() if q > 0 and s not in selling]
    if len(held) < 2:
        return
    prices, scores, speeds = score_held(held)
    ranked = sorted(held, key=lambda s: scores[s], reverse=True)[:SLOTS]
    if abs(scores[ranked[0]] - scores[ranked[1]]) < SHUFFLE_MIN_EDGE:
        return
    now = time.time()
    plan = []
    for i, s in enumerate(ranked):
        price = prices.get(s)
        with state_lock:
            st = dict(state.get(s, {}))
        if not price or "weight" not in st:
            continue
        w = POSITION_WEIGHTS[i]
        if abs(w - st["weight"]) <= 0.01:
            continue
        gap_ok = now - st.get("last_rebalance_ts", 0) >= BALANCE_MIN_GAP_SECONDS
        if not (gap_ok or abs(speeds[s]) >= FAST_MOVE_OVERRIDE_SPEED):
            continue
        plan.append((s, int(equity * w // price), w))
    for s, target, w in plan:                    # trims first, so cash is free for the adds
        if target < real[s]:
            log(f"REBALANCE trim {s} to {target} shares ({w:.0%})")
            place_sell(s, "rebalance trim", target_shares=target)
    for s, target, w in plan:
        if target > real[s] and s not in selling:
            log(f"REBALANCE add {s} to {target} shares ({w:.0%})")
            aggressive_execute(s, OrderSide.BUY, target)
    with state_lock:
        for s, target, w in plan:
            if s in state:
                state[s].update(weight=w, last_rebalance_ts=now)


def run_cycle(movers):
    log(f"cycle check: {len(movers)} movers found: {[m['symbol'] for m in movers]}")
    if guard["stopped"]:
        log("STOPPED: three halted days in a row - restart the service manually to resume")
        return
    equity = get_equity()
    if check_daily_halt(equity):
        return
    real = get_real_positions()
    try_rebalance(equity, real)
    held_count = len([s for s, q in real.items() if q > 0]) + len(buying)

    for m in movers:
        symbol, price = m["symbol"], m["price"]
        if not (PRICE_MIN <= price <= PRICE_MAX and m["percent_change"] >= GAIN_MIN):
            continue
        if not near_high(m):
            continue
        if real.get(symbol, 0) > 0 or symbol in buying or symbol in selling:
            continue

        raw = get_recent_bars(symbol, limit=70)          # 70 so MACD has its 35 bars
        done = completed_bars(raw)
        pattern = three_candle_pullback(done)
        if pattern is None:
            continue
        trigger, red_low = pattern
        if price < trigger:                              # live price must cross red open + 1c
            continue
        cur = forming_bar(raw)
        if cur is not None and price <= cur.open:        # the entry bar must be trading green
            continue
        if not thin_ok(done):
            continue
        if not ema9_above_ema20(done):
            continue
        day_bars = get_day_bars(symbol)
        vwap = compute_vwap(completed_bars(day_bars))
        if vwap is None or price < vwap:
            continue
        if not macd_positive(done):
            continue
        vmax = day_max_volume(symbol, day_bars)
        if speed(done, price, vmax) <= 0:
            continue
        ask, bid = get_spread(symbol)
        if ask is None or bid is None or ask <= 0:
            continue
        if ask - bid > MAX_SPREAD:
            log(f"{symbol}: spread ${ask - bid:.2f} too wide, skipping")
            continue
        score = combined_score(done, price, vmax)

        if held_count < SLOTS:
            if place_buy(symbol, ask, POSITION_WEIGHTS[min(held_count, SLOTS - 1)], red_low):
                held_count += 1
        else:
            try_shuffle(symbol, score, ask, red_low, real)


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
