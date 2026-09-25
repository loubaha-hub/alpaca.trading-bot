"""
Alpaca v30-v2 ("speed book", revised), built on the same SELF-BUILT
SCANNER as v27/v24 (2026-09-25).
Design, finalized with the user 2026-09-25:
- Entry: buy the moment a stock crosses +10% today (no three-candle
  pattern needed - the whole point is catching a move like MSGY early,
  which v27/v24's pattern-based entry would have missed).
- 4 positions at a time, ranked by SPEED (not price appreciation).
  Sizing is a HARD DOLLAR CAP per rank, not a percentage of equity -
  fastest gets up to $25,000, next $12,500, then $6,250, then $3,125,
  regardless of how large the account is (added 2026-09-25 specifically
  to keep position sizes controlled on the $100k account).
- Shuffle: if all 4 slots are full and a new candidate is running FASTER
  (by speed, not price) than the current weakest holding, it replaces it.
  No minimum edge threshold was specified for this one (unlike v24's
  10% rule) - any positive speed edge triggers the swap.
- Exit: two tiers -
  (a) per-position TIERED trailing stop: below 5% gain from entry,
      trail very tight at 0.5% below peak (tightened 2026-09-25 given
      the larger position sizes); once gain reaches 5% or more, loosen
      to 5% below peak so a real runner has room to breathe.
  (b) ACCOUNT-LEVEL: if the day's total loss reaches 10% of starting
      equity, flatten everything and stop opening new positions for
      the rest of the day.
- Re-entry: a stock that was stopped out can only be bought again once
  it trades back above its own actual DAY'S HIGH (so far) + 5 cents -
  not just the peak we happened to see while we held it.
Runs continuously as a background worker. Paper trading by default.
"""
import os
import time
import requests
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass, AssetStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

API_KEY = os.environ["ALPACA_API_KEY"]
SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
PAPER = os.environ.get("ALPACA_PAPER", "true").lower() == "true"

PRICE_MIN = 1.0
PRICE_MAX = 20.0
GAIN_MIN = 0.10
MAX_NAMES = 4
MAX_SPREAD = 0.10
DAILY_HALT_PCT = 0.10
POSITION_CAPS = [25000, 12500, 6250, 3125]

UNIVERSE_REFRESH_SECONDS = 120
FAST_CHECK_SECONDS = 5
SNAPSHOT_BATCH_SIZE = 200

trading = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

state = {}
full_universe = []
comeback_floor = {}
starting_equity = None
halted_today = False


def log(msg):
    print(f"{datetime.now(timezone.utc).isoformat()}  {msg}", flush=True)


def chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


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


def speed(bars):
    if len(bars) < 2:
        return 0.0
    a, b = bars[-2], bars[-1]
    if a.close <= 0 or a.volume <= 0:
        return 0.0
    dp = (b.close - a.close) / a.close
    dv = (b.volume - a.volume) / a.volume if a.volume else 0.0
    return dp * dv


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
    if gain < 0.05:
        return peak * 0.995
    return peak * 0.95


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


def place_buy(symbol, ask, dollars):
    shares = int(dollars // ask)
    if shares <= 0:
        log(f"{symbol}: not enough allocated cash for even 1 share, skipping")
        return False
    limit_price = round(ask * 1.005, 2)
    try:
        order = LimitOrderRequest(
            symbol=symbol, qty=shares, side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY, limit_price=limit_price,
            extended_hours=True,
        )
        trading.submit_order(order)
        log(f"BUY {symbol} x{shares} @ limit {limit_price} (${dollars:.0f} target)")
        state[symbol] = {"held": True, "entry": ask, "peak": ask, "shares": shares}
        return True
    except Exception as e:
        log(f"place_buy({symbol}) error: {e}")
        return False


def get_day_high(symbol):
    try:
        req = StockSnapshotRequest(symbol_or_symbols=[symbol])
        snaps = data_client.get_stock_snapshot(req)
        snap = snaps.get(symbol)
        if snap and snap.daily_bar:
            return snap.daily_bar.high
    except Exception as e:
        log(f"get_day_high({symbol}) error: {e}")
    return None


def place_sell(symbol, reason=""):
    real_positions = get_real_positions()
    have = real_positions.get(symbol, 0)
    if have <= 0:
        log(f"{symbol}: broker shows 0 shares, nothing to sell")
        state.pop(symbol, None)
        return
    _, bid = get_spread(symbol)
    limit_price = round((bid or 0) * 0.995, 2)
    try:
        order = LimitOrderRequest(
            symbol=symbol, qty=have, side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY, limit_price=limit_price,
            extended_hours=True,
        )
        trading.submit_order(order)
        log(f"SELL {symbol} x{have} @ limit {limit_price} {reason}")
        day_high = get_day_high(symbol)
        if day_high:
            comeback_floor[symbol] = round(day_high + 0.05, 4)
        state.pop(symbol, None)
    except Exception as e:
        log(f"place_sell({symbol}) error: {e}")


def rebalance_weights(equity):
    held_symbols = [s for s, v in state.items() if v.get("held")]
    if not held_symbols:
        return
    speeds = {}
    for symbol in held_symbols:
        bars = get_recent_bars(symbol, limit=15)
        speeds[symbol] = speed(bars)
    ranked = sorted(held_symbols, key=lambda s: speeds[s], reverse=True)
    real_positions = get_real_positions()
    for i, symbol in enumerate(ranked):
        cap = POSITION_CAPS[i] if i < len(POSITION_CAPS) else POSITION_CAPS[-1]
        ask, _ = get_spread(symbol)
        if not ask:
            continue
        have = real_positions.get(symbol, 0)
        target_shares = int(cap // ask)
        diff = target_shares - have
        if diff == 0:
            continue
        try:
            if diff > 0:
                order = LimitOrderRequest(
                    symbol=symbol, qty=diff, side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY, limit_price=round(ask * 1.005, 2),
                    extended_hours=True,
                )
                trading.submit_order(order)
                log(f"REWEIGHT-UP {symbol} +{diff} toward ${cap:.0f} cap (rank {i+1})")
            else:
                order = LimitOrderRequest(
                    symbol=symbol, qty=-diff, side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY, limit_price=round(ask * 0.995, 2),
                    extended_hours=True,
                )
                trading.submit_order(order)
                log(f"REWEIGHT-DOWN {symbol} {diff} toward ${cap:.0f} cap (rank {i+1})")
        except Exception as e:
            log(f"rebalance_weights({symbol}) error: {e}")


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

    if candidate_speed > weakest_speed:
        log(f"SHUFFLE: {candidate_symbol} (speed {candidate_speed:.4f}) replaces "
            f"{weakest_symbol} (speed {weakest_speed:.4f})")
        place_sell(weakest_symbol, "replaced by faster newcomer")
        ask, _ = get_spread(candidate_symbol)
        if ask:
            place_buy(candidate_symbol, ask, POSITION_CAPS[-1])
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
            f"flattening everything, no new entries for the rest of today")
        halted_today = True
        for symbol in list(state.keys()):
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
            place_sell(symbol, "tiered_trailing_stop")

    held_count = sum(1 for s in state.values() if s.get("held"))

    for m in movers:
        symbol = m["symbol"]
        price = m["price"]
        if symbol in state and state[symbol].get("held"):
            continue

        floor = comeback_floor.get(symbol)
        if floor is not None and price < floor:
            continue

        ask, bid = get_spread(symbol)
        if ask is None or bid is None or ask <= 0:
            continue
        if (ask - bid) > MAX_SPREAD:
            continue

        bars = get_recent_bars(symbol, limit=15)
        sp = speed(bars)

        if held_count < MAX_NAMES:
            initial_cap = POSITION_CAPS[-1]
            if place_buy(symbol, ask, initial_cap):
                held_count += 1
        else:
            try_shuffle(symbol, sp, equity)

    if held_count >= 1:
        rebalance_weights(equity)


if __name__ == "__main__":
    log(f"Starting Alpaca v30-v2 bot with SELF-BUILT SCANNER. paper={PAPER}")
    try:
        acct = trading.get_account()
        log(f"ACCOUNT CHECK OK: status={acct.status}, cash={acct.cash}")
    except Exception as e:
        log(f"ACCOUNT CHECK FAILED: {e}")

    et = ZoneInfo("America/New_York")
    last_universe_refresh = 0
    shortlist = []

    while True:
        now_et = datetime.now(et)
        start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)

        if start <= now_et <= end:
            try:
                now_unix = time.time()
                if now_unix - last_universe_refresh >= UNIVERSE_REFRESH_SECONDS:
                    shortlist = narrow_universe()
                    last_universe_refresh = now_unix

                movers = fast_scan(shortlist)
                run_cycle(movers)
            except Exception as e:
                log(f"run_cycle crashed: {e}")
        else:
            log(f"outside trading window (4am-8pm ET), current ET time: {now_et.strftime('%H:%M')}")

        time.sleep(FAST_CHECK_SECONDS)
