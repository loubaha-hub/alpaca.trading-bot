"""
Alpaca v24 (FINAL REVISION 2026-09-26), self-built scanner.

KEPT FROM v24's OWN DESIGN:
- Entry: three-candle pullback (green candle, then red candle, trigger
  = red candle's open + 1 cent).
- Up to 12 ranked positions, halving weight ladder (50/20/15/7.5/3.75...).
- BALANCING (reweighting among current holdings): every 5 minutes
  minimum (raised from 3 per the user's direction 2026-09-26), AND only
  if a holding's speed has changed >=20% since its last rebalance - BUT
  if a held stock is moving VERY fast (speed >= FAST_MOVE_OVERRIDE_SPEED,
  a placeholder tuned conservatively, review after seeing real logs),
  the 5-minute gate is bypassed and it rebalances immediately.
- SHUFFLING (swap in a new stock when book is full): the newcomer must
  be running >=10% faster than the current weakest holding.

CHANGED 2026-09-26: exit ladder now matches v27's final 3-tier flat
trailing design exactly (replacing v24's original 4-tier give-back
style): under 10% gain, 2% trail; 10% to 100% gain, 5% trail; over
100% gain, 10% trail.

FIXES PORTED FROM v30/v27 (all proven in live testing 2026-09-25/26):
1. AGGRESSIVE ADAPTIVE EXECUTION (aggressive_execute()) - every buy and
   sell checks REAL broker position first, cancels any stale working
   order before submitting a new one, prices anchored to the bid,
   step size adapts to real market speed between attempts. Always a
   LIMIT order (Alpaca rejects market orders outside 9:30-4:00 ET).
2. END-OF-DAY FLATTEN at 7:55 PM ET.
3. DAILY 10% HALT (v24 never had one before).
4. NO DUPLICATE ORDERS - structural.
5. WEEKEND/HOLIDAY AWARENESS via Alpaca's own market calendar.
6. CRASH/RESTART RECONCILIATION - seeds state from real broker
   positions on startup.
7. VOLUME FILTER - minimum 100,000 shares in the latest 1-min bar
   before any entry (v24 never had this before either).
8. CORRECTED SPEED FORMULA - price direction is the core signal,
   volume only ever amplifies/dampens it (0-2x), never flips its sign.
9. ADAPTIVE SPREAD FILTER - a calm stock stays tight near the base
   10-cent floor; a fast-moving stock's allowed spread widens to match
   its own recent real movement.
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
MAX_NAMES = 12
MAX_SPREAD = 0.10
DAILY_HALT_PCT = 0.10

BALANCE_MIN_GAP_SECONDS = 300
BALANCE_MIN_CHANGE = 0.20
FAST_MOVE_OVERRIDE_SPEED = 0.05
SHUFFLE_MIN_EDGE = 0.10

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
            state[symbol] = {
                "held": True, "entry": price, "peak": price, "shares": qty,
                "weight": 0.0, "last_speed": 0.0, "last_rebalance_ts": time.time(),
            }
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


def get_recent_bars(symbol, limit=15):
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


def three_candle_pullback(bars):
    if len(bars) < 2:
        return None
    prev, last = bars[-2], bars[-1]
    green = prev.close > prev.open
    red = last.close < last.open
    if green and red:
        return round(last.open + 0.01, 4)
    return None


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


def max_allowed_spread(bars):
    if len(bars) < 2:
        return MAX_SPREAD
    recent_move = abs(bars[-1].close - bars[-2].close)
    return max(MAX_SPREAD, recent_move * 1.5)


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


def weight_ladder(n):
    weights = [0.50, 0.20]
    remaining = 0.30
    while len(weights) < n:
        weights.append(remaining / 2)
        remaining = remaining / 2
    return weights[:n]


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


def place_buy(symbol, ask, weight, equity):
    dollars = equity * weight
    shares = int(dollars // ask)
    if shares <= 0:
        log(f"{symbol}: not enough allocated cash for even 1 share, skipping")
        return False
    ok = aggressive_execute(symbol, OrderSide.BUY, shares)
    if ok:
        state[symbol] = {
            "held": True, "entry": ask, "peak": ask, "shares": shares,
            "weight": weight, "last_speed": 0.0, "last_rebalance_ts": time.time(),
        }
    return ok


def place_sell(symbol, reason=""):
    ok = aggressive_execute(symbol, OrderSide.SELL, 0)
    log(f"place_sell({symbol}) {reason} -> {'closed' if ok else 'NOT fully closed'}")


def adjust_position(symbol, target_weight, equity):
    real_positions = get_real_positions()
    have = real_positions.get(symbol, 0)
    ask, _ = get_spread(symbol)
    if not ask:
        return
    target_shares = int((equity * target_weight) // ask)
    diff = target_shares - have
    if diff == 0:
        return
    if diff > 0:
        aggressive_execute(symbol, OrderSide.BUY, target_shares)
    else:
        cancel_open_orders(symbol)
        _, bid = get_spread(symbol)
        if bid:
            try:
                order = LimitOrderRequest(
                    symbol=symbol, qty=-diff, side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                    limit_price=round(bid * 0.995, 2),
                    extended_hours=True,
                )
                trading.submit_order(order)
                log(f"BALANCE-DOWN {symbol} {diff} shares toward weight {target_weight:.3f}")
            except Exception as e:
                log(f"adjust_position({symbol}) error: {e}")
    if symbol in state:
        state[symbol]["weight"] = target_weight
        state[symbol]["last_rebalance_ts"] = time.time()


def try_balance(equity):
    held_symbols = [s for s, v in state.items() if v.get("held")]
    if len(held_symbols) < 2:
        return

    now = time.time()
    speeds = {}
    for symbol in held_symbols:
        bars = get_recent_bars(symbol, limit=15)
        speeds[symbol] = speed(bars)

    ranked = sorted(held_symbols, key=lambda s: speeds[s], reverse=True)
    new_weights = weight_ladder(len(ranked))

    for i, symbol in enumerate(ranked):
        s = state[symbol]
        time_ok = (now - s.get("last_rebalance_ts", 0)) >= BALANCE_MIN_GAP_SECONDS
        moving_very_fast = abs(speeds[symbol]) >= FAST_MOVE_OVERRIDE_SPEED
        if moving_very_fast and not time_ok:
            log(f"{symbol}: moving very fast (speed {speeds[symbol]:.4f}) - "
                f"bypassing the 5-minute balance gate")
        time_ok = time_ok or moving_very_fast
        prev_speed = s.get("last_speed", 0.0)
        change_ok = abs(speeds[symbol] - prev_speed) >= BALANCE_MIN_CHANGE * max(abs(prev_speed), 1e-9)
        target_weight = new_weights[i]
        if time_ok and change_ok and abs(target_weight - s.get("weight", 0)) > 0.01:
            adjust_position(symbol, target_weight, equity)
        s["last_speed"] = speeds[symbol]


def try_shuffle(candidate_symbol, candidate_speed, equity):
    held_symbols = [s for s, v in state.items() if v.get("held")]
    if len(held_symbols) < MAX_NAMES:
        return False

    weakest_symbol, weakest_speed = None, None
    for hs in held_symbols:
        hbars = get_recent_bars(hs, limit=15)
        hsp = speed(hbars)
        if weakest_speed is None or hsp < weakest_speed:
            weakest_symbol, weakest_speed = hs, hsp

    if weakest_symbol is None:
        return False

    edge = candidate_speed - weakest_speed
    if edge >= SHUFFLE_MIN_EDGE:
        log(f"SHUFFLE: {candidate_symbol} (speed {candidate_speed:.4f}) replaces "
            f"{weakest_symbol} (speed {weakest_speed:.4f}), edge {edge:.4f}")
        place_sell(weakest_symbol, "replaced by faster newcomer")
        weights = weight_ladder(MAX_NAMES)
        ask, _ = get_spread(candidate_symbol)
        if ask:
            place_buy(candidate_symbol, ask, weights[-1], equity)
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

    try_balance(equity)

    held_count = sum(1 for s in state.values() if s.get("held"))

    for m in movers:
        symbol = m["symbol"]
        if symbol in state and state[symbol].get("held"):
            continue

        bars = get_recent_bars(symbol, limit=15)
        trigger = three_candle_pullback(bars)
        if trigger is None:
            continue

        if not bars or bars[-1].volume < MIN_BAR_VOLUME:
            continue

        ask, bid = get_spread(symbol)
        if ask is None or bid is None or ask <= 0:
            continue
        allowed_spread = max_allowed_spread(bars)
        if (ask - bid) > allowed_spread:
            log(f"{symbol}: spread ${ask-bid:.2f} too wide (allowed ${allowed_spread:.2f} "
                f"given recent movement), skipping")
            continue

        latest = bars[-1].close if bars else None
        if not (latest and latest >= trigger):
            continue

        sp = speed(bars)

        if held_count < MAX_NAMES:
            weights = weight_ladder(held_count + 1)
            if place_buy(symbol, ask, weights[held_count], equity):
                held_count += 1
        else:
            try_shuffle(symbol, sp, equity)


if __name__ == "__main__":
    log(f"Starting Alpaca v24 bot (FINAL REVISION) with SELF-BUILT SCANNER. paper={PAPER}")
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
