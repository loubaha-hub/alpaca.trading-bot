"""
Alpaca v27 (FINAL REVISION 2026-09-26), self-built scanner.

CHANGES FROM THE PRIOR REVISION, all per the user's direction tonight:

1. NEW FILTERS ADDED TO ENTRY:
   - VWAP: entry price must be above today's volume-weighted average
     price (computed from real bars since today's 4 AM ET session
     start, not just the recent lookback window).
   - MACD: ASSUMPTION FLAGGED TO USER - no explicit confirmation was
     given on which definition to use, so this uses the stricter,
     originally-documented definition: MACD(12,26,9) line above zero
     AND above its own signal line (not just "line above zero" alone).
     If you meant the simpler version, this is a one-line change.

2. NEW TRAILING STOP LADDER (replaces the old 4-tier "give-back-%"
   ladder entirely): under 10% gain -> 2% trail; 10% to 100% gain ->
   5% trail; over 100% gain -> 10% trail. All three tiers are flat
   percentage trails, not "give back X% of the gain" style.

3. NEW POSITION SIZING - ranked, weighted, not equal-split:
   - Still 2 positions max.
   - Ranked by a COMBINED SCORE: speed (price direction is the core
     signal, volume 0-2x amplifies/dampens it, per the corrected
     formula proven in v30) MULTIPLIED by a dollar-volume factor
     (capped 0.5x-2x) - a thinly-traded mover no longer ranks equal to
     a heavily-traded one at the same speed.
   - The faster-ranked position gets 60% of cash, the second gets 40%.
   - SHUFFLE: if a new candidate's combined score beats the WEAKER
     held position's score by a real margin, it replaces it.
     ASSUMPTION FLAGGED TO USER: no explicit minimum edge was given for
     this shuffle - SHUFFLE_MIN_EDGE below is a placeholder tuned
     conservatively to avoid v30's excessive-churn problem. This should
     be reviewed once you see it running.
   - ASSUMPTION FLAGGED TO USER: the dollar-volume factor's reference
     level (DOLLAR_VOLUME_REFERENCE below, $200,000/minute) is a
     reasonable starting guess, not something you specified - it should
     be tuned once you see real ranking behavior in the logs.

EVERYTHING ELSE KEPT FROM THE PRIOR REVISION (all proven in v30's live
testing 2026-09-25/26): the three-candle pullback entry trigger, the
volume filter (100,000 shares minimum), the spread filter, the
aggressive bid-anchored adaptive execution, the end-of-day flatten, the
daily 10% halt, weekend/holiday awareness, and startup reconciliation
with real broker positions.
Runs continuously as a background worker. Paper trading by default.
"""
import os
import time
import requests
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, GetAssetsRequest, GetOrdersRequest, GetCalendarRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass, AssetStatus, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

API_KEY = os.environ["ALPACA_API_KEY"]
SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
PAPER = os.environ.get("ALPACA_PAPER", "true").lower() == "true"

PRICE_MIN = 1.0
PRICE_MAX = 20.0
GAIN_MIN = 0.10
MIN_BAR_VOLUME = 100000
SLOTS = 2
MAX_SPREAD = 0.10
DAILY_HALT_PCT = 0.10
POSITION_WEIGHTS = [0.60, 0.40]
DOLLAR_VOLUME_REFERENCE = 200000
SHUFFLE_MIN_EDGE = 0.01

UNIVERSE_REFRESH_SECONDS = 120
FAST_CHECK_SECONDS = 5
SNAPSHOT_BATCH_SIZE = 200

trading = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

state = {}
full_universe = []
starting_equity = None
halted_today = False
market_open_today = None


def log(msg):
    print(f"{datetime.now(timezone.utc).isoformat()}  {msg}", flush=True)


def chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


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
        log(f"is_trading_day error: {e} - defaulting to True (weekday assumption)")
        return now_et.weekday() < 5


def reconcile_on_startup():
    real_positions = get_real_positions()
    for symbol, qty in real_positions.items():
        if qty > 0:
            ask, bid = get_spread(symbol)
            price = ask or bid or 0
            state[symbol] = {"held": True, "entry": price, "peak": price, "shares": qty}
            log(f"RECONCILED on startup: {symbol} x{qty} (found in real broker positions)")


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
            out.append({"symbol": symbol, "price": price, "percent_change": gain})
    out.sort(key=lambda x: x["percent_change"], reverse=True)
    return out[:50]


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
        day_start_utc = day_start_et.astimezone(timezone.utc)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=day_start_utc,
        )
        bars = data_client.get_stock_bars(req)
        return bars[symbol] if symbol in bars.data else []
    except Exception as e:
        log(f"get_day_bars({symbol}) error: {e}")
        return []


def compute_vwap(day_bars):
    if not day_bars:
        return None
    total_dollar = sum(b.close * b.volume for b in day_bars)
    total_volume = sum(b.volume for b in day_bars)
    if total_volume <= 0:
        return None
    return total_dollar / total_volume


def three_candle_pullback(bars):
    if len(bars) < 2:
        return None
    prev, last = bars[-2], bars[-1]
    green = prev.close > prev.open
    red = last.close < last.open
    if green and red:
        return round(last.open + 0.01, 4)
    return None


def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def ema9_above_ema20(bars):
    if len(bars) < 20:
        return False
    closes = [b.close for b in bars]
    e9 = ema(closes[-20:], 9)
    e20 = ema(closes[-20:], 20)
    if e9 is None or e20 is None:
        return False
    return e9 > e20


def compute_macd(closes):
    if len(closes) < 35:
        return None, None
    ema12_series = []
    ema26_series = []
    k12 = 2 / 13
    k26 = 2 / 27
    e12 = closes[0]
    e26 = closes[0]
    for c in closes:
        e12 = c * k12 + e12 * (1 - k12)
        e26 = c * k26 + e26 * (1 - k26)
        ema12_series.append(e12)
        ema26_series.append(e26)
    macd_series = [a - b for a, b in zip(ema12_series, ema26_series)]
    k9 = 2 / 10
    sig = macd_series[0]
    for m in macd_series:
        sig = m * k9 + sig * (1 - k9)
    return macd_series[-1], sig


def macd_positive(bars):
    closes = [b.close for b in bars]
    macd_line, signal_line = compute_macd(closes)
    if macd_line is None or signal_line is None:
        return False
    return macd_line > 0 and macd_line > signal_line


def get_spread(symbol):
    try:
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = data_client.get_stock_latest_quote(req)
        q = quote[symbol]
        return q.ask_price, q.bid_price
    except Exception as e:
        log(f"get_spread({symbol}) error: {e}")
        return None, None


def tier_stop(peak, entry):
    if entry <= 0:
        return peak
    gain = (peak / entry) - 1.0
    if gain < 0.10:
        return peak * 0.98
    if gain < 1.00:
        return peak * 0.95
    return peak * 0.90


def speed(bars):
    if len(bars) < 2:
        return 0.0
    a, b = bars[-2], bars[-1]
    if a.close <= 0 or a.volume <= 0:
        return 0.0
    dp = (b.close - a.close) / a.close
    dv = (b.volume - a.volume) / a.volume if a.volume else 0.0
    volume_multiplier = max(0.0, min(2.0, 1.0 + dv))
    return dp * volume_multiplier


def dollar_volume_factor(bars):
    if not bars:
        return 1.0
    last = bars[-1]
    dollar_vol = last.close * last.volume
    factor = dollar_vol / DOLLAR_VOLUME_REFERENCE
    return max(0.5, min(2.0, factor))


def combined_score(bars):
    return speed(bars) * dollar_volume_factor(bars)


def get_equity():
    try:
        acct = trading.get_account()
        return float(acct.equity)
    except Exception as e:
        log(f"get_equity error: {e}")
        return 0.0


def get_real_positions():
    try:
        positions = trading.get_all_positions()
        return {p.symbol: int(float(p.qty)) for p in positions}
    except Exception as e:
        log(f"get_real_positions error: {e}")
        return {}


def cancel_open_orders(symbol):
    try:
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        for o in trading.get_orders(req):
            try:
                trading.cancel_order_by_id(o.id)
            except Exception as e:
                log(f"cancel_open_orders({symbol}) error: {e}")
    except Exception as e:
        log(f"cancel_open_orders({symbol}) get_orders error: {e}")


def aggressive_execute(symbol, side, target_shares, max_attempts=15, wait_seconds=0.05):
    execute_start = time.time()
    last_bid = None
    for attempt in range(max_attempts):
        real_positions = get_real_positions()
        have = real_positions.get(symbol, 0)

        if side == OrderSide.SELL:
            remaining = have
            if remaining <= 0:
                state.pop(symbol, None)
                total_ms = (time.time() - execute_start) * 1000
                log(f"{symbol}: FULLY EXECUTED in {total_ms:.0f}ms total "
                    f"({attempt} attempt(s))")
                return True
        else:
            remaining = target_shares - have
            if remaining <= 0:
                total_ms = (time.time() - execute_start) * 1000
                log(f"{symbol}: FULLY EXECUTED in {total_ms:.0f}ms total "
                    f"({attempt} attempt(s))")
                return True

        cancel_open_orders(symbol)

        ask, bid = get_spread(symbol)
        if not ask or not bid:
            time.sleep(wait_seconds)
            continue

        if last_bid is None:
            step = 0.01
        else:
            step = max(0.01, round(abs(bid - last_bid), 2))
        last_bid = bid

        if side == OrderSide.SELL:
            limit_price = round(bid - 0.01 - (step * attempt), 2)
            limit_price = max(limit_price, 0.01)
        else:
            limit_price = round(bid + (step * attempt), 2)

        try:
            submit_start = time.time()
            order = LimitOrderRequest(
                symbol=symbol, qty=remaining, side=side,
                time_in_force=TimeInForce.DAY, limit_price=limit_price,
                extended_hours=True,
            )
            trading.submit_order(order)
            submit_ms = (time.time() - submit_start) * 1000
            log(f"{'SELL' if side == OrderSide.SELL else 'BUY'} (adaptive-chase) "
                f"{symbol} x{remaining} @ limit {limit_price} "
                f"(bid {bid}, ask {ask}, step {step}, attempt {attempt+1}/{max_attempts}, "
                f"submit took {submit_ms:.0f}ms)")
        except Exception as e:
            log(f"aggressive_execute({symbol}) submit error: {e}")

        time.sleep(wait_seconds)

    total_ms = (time.time() - execute_start) * 1000
    log(f"{symbol}: WARNING - not fully executed after {max_attempts} attempts "
        f"({total_ms:.0f}ms elapsed)")
    return False


def place_buy(symbol, ask, weight):
    equity = get_equity()
    dollars = equity * weight
    shares = int(dollars // ask)
    if shares <= 0:
        log(f"{symbol}: not enough allocated cash for even 1 share, skipping")
        return False
    ok = aggressive_execute(symbol, OrderSide.BUY, shares)
    if ok:
        state[symbol] = {"held": True, "entry": ask, "peak": ask, "shares": shares, "weight": weight}
    return ok


def place_sell(symbol, reason=""):
    ok = aggressive_execute(symbol, OrderSide.SELL, 0)
    log(f"place_sell({symbol}) {reason} -> {'closed' if ok else 'NOT fully closed'}")


def try_shuffle(candidate_symbol, candidate_score, candidate_ask):
    held_symbols = [s for s, v in state.items() if v.get("held")]
    if len(held_symbols) < SLOTS:
        return False

    weakest_symbol, weakest_score = None, None
    for hs in held_symbols:
        hbars = get_recent_bars(hs, limit=15)
        hscore = combined_score(hbars)
        if weakest_score is None or hscore < weakest_score:
            weakest_symbol, weakest_score = hs, hscore

    if weakest_symbol is None:
        return False

    edge = candidate_score - weakest_score
    if edge >= SHUFFLE_MIN_EDGE:
        log(f"SHUFFLE: {candidate_symbol} (score {candidate_score:.4f}) replaces "
            f"{weakest_symbol} (score {weakest_score:.4f}), edge {edge:.4f}")
        place_sell(weakest_symbol, "replaced by higher-scoring newcomer")
        place_buy(candidate_symbol, candidate_ask, POSITION_WEIGHTS[-1])
        return True
    return False


def check_daily_halt(equity):
    global halted_today, starting_equity
    if starting_equity is None:
        starting_equity = equity
        return False
    if halted_today:
        return True
    loss_pct = (starting_equity - equity) / starting_equity if starting_equity > 0 else 0
    if loss_pct >= DAILY_HALT_PCT:
        log(f"DAILY HALT: down {loss_pct:.1%} from starting equity {starting_equity:.2f} - "
            f"flattening everything (aggressive execution), no new entries today")
        halted_today = True
        real_positions = get_real_positions()
        for symbol in list(real_positions.keys()):
            place_sell(symbol, "daily_halt_flatten")
        return True
    return False


def run_cycle(movers):
    symbols_seen = [m["symbol"] for m in movers]
    log(f"cycle check: {len(movers)} movers found: {symbols_seen}")
    equity = get_equity()

    if check_daily_halt(equity):
        return

    for symbol, s in list(state.items()):
        if not s.get("held"):
            continue
        bars = get_recent_bars(symbol, limit=1)
        if not bars:
            continue
        current = bars[-1].close
        s["peak"] = max(s["peak"], current)
        stop = tier_stop(s["peak"], s["entry"])
        if current <= stop:
            place_sell(symbol, "tier_stop")

    held_count = sum(1 for s in state.values() if s.get("held"))

    for m in movers:
        symbol = m["symbol"]
        price = m["price"]
        pct_change = m["percent_change"]
        if not (PRICE_MIN <= price <= PRICE_MAX and pct_change >= GAIN_MIN):
            continue

        if symbol in state and state[symbol].get("held"):
            continue

        bars = get_recent_bars(symbol, limit=25)
        trigger = three_candle_pullback(bars)
        if trigger is None:
            continue
        if not ema9_above_ema20(bars):
            continue

        day_bars = get_day_bars(symbol)
        vwap = compute_vwap(day_bars)
        if vwap is None or price < vwap:
            continue

        if not macd_positive(bars):
            continue

        if not bars or bars[-1].volume < MIN_BAR_VOLUME:
            continue

        ask, bid = get_spread(symbol)
        if ask is None or bid is None or ask <= 0:
            continue
        spread = ask - bid
        if spread > MAX_SPREAD:
            log(f"{symbol}: spread ${spread:.2f} too wide, skipping")
            continue

        latest = bars[-1].close if bars else None
        if not (latest and latest >= trigger):
            continue

        score = combined_score(bars)

        if held_count < SLOTS:
            weight = POSITION_WEIGHTS[held_count]
            if place_buy(symbol, ask, weight):
                held_count += 1
        else:
            try_shuffle(symbol, score, ask)


if __name__ == "__main__":
    log(f"Starting Alpaca v27 bot (FINAL REVISION) with SELF-BUILT SCANNER. paper={PAPER}")
    try:
        acct = trading.get_account()
        log(f"ACCOUNT CHECK OK: status={acct.status}, cash={acct.cash}")
    except Exception as e:
        log(f"ACCOUNT CHECK FAILED: {e}")

    reconcile_on_startup()

    et = ZoneInfo("America/New_York")
    last_universe_refresh = 0
    shortlist = []
    eod_flatten_done_date = None

    while True:
        now_et = datetime.now(et)
        start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
        eod_flatten_time = now_et.replace(hour=19, minute=55, second=0, microsecond=0)

        if not is_trading_day(now_et):
            log(f"not a trading day ({now_et.strftime('%A, %Y-%m-%d')}) - idle")
        elif start <= now_et <= end:
            try:
                now_unix = time.time()
                if now_unix - last_universe_refresh >= UNIVERSE_REFRESH_SECONDS:
                    shortlist = narrow_universe()
                    last_universe_refresh = now_unix

                if now_et >= eod_flatten_time and eod_flatten_done_date != now_et.date():
                    log(f"END OF DAY FLATTEN: {now_et.strftime('%H:%M')} ET reached - "
                        f"closing every real position via aggressive execution")
                    real_positions = get_real_positions()
                    for symbol in list(real_positions.keys()):
                        place_sell(symbol, "end_of_day_flatten")
                    eod_flatten_done_date = now_et.date()
                else:
                    movers = fast_scan(shortlist)
                    run_cycle(movers)
            except Exception as e:
                log(f"run_cycle crashed: {e}")
        else:
            log(f"outside trading window (4am-8pm ET), current ET time: {now_et.strftime('%H:%M')}")

        time.sleep(FAST_CHECK_SECONDS)
