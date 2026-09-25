"""
Alpaca gap-and-go trading bot (v27 logic) with a SELF-BUILT SCANNER.
2026-09-25: replaces Alpaca's pre-computed "movers" screener endpoint,
which was found to return the same stale result for 47+ minutes at a
stretch. Instead: (1) periodically pull the tradable stock universe
and narrow it with a broader price/gain pass, (2) frequently pull
fresh snapshots for just that shortlist and compute gains ourselves.
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
SLOTS = 2
MAX_SPREAD = 0.10

UNIVERSE_REFRESH_SECONDS = 120   # re-narrow the shortlist every 2 minutes
FAST_CHECK_SECONDS = 5           # fresh gain check on the shortlist this often
SNAPSHOT_BATCH_SIZE = 200        # symbols per snapshot request

trading = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

state = {}  # symbol -> {"held": bool, "entry": float, "peak": float, "shares": int}
shortlist = []             # current narrowed candidate symbols
last_universe_refresh = 0  # unix time of last narrowing pass
full_universe = []         # all tradable US equity symbols (refreshed rarely)


def log(msg):
    print(f"{datetime.now(timezone.utc).isoformat()}  {msg}", flush=True)


def chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def get_full_universe():
    """Pull every tradable, active, plain US equity symbol. Excludes OTC
    and non-plain tickers (preferreds/warrants/units carry punctuation
    or extra letters we filter out downstream in narrow_universe)."""
    try:
        req = GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
        assets = trading.get_all_assets(req)
        symbols = [
            a.symbol for a in assets
            if a.tradable and a.exchange != "OTC" and a.symbol.isalpha()
        ]
        log(f"full universe refreshed: {len(symbols)} tradable plain-ticker symbols")
        return symbols
    except Exception as e:
        log(f"get_full_universe error: {e}")
        return []


def get_snapshots(symbols):
    """Batched snapshot pull. Returns {symbol: snapshot}."""
    result = {}
    for batch in chunked(symbols, SNAPSHOT_BATCH_SIZE):
        try:
            req = StockSnapshotRequest(symbol_or_symbols=batch)
            snaps = data_client.get_stock_snapshot(req)
            result.update(snaps)
        except Exception as e:
            log(f"get_snapshots batch error: {e}")
        time.sleep(0.1)  # be gentle between batches
    return result


def pct_gain_today(snap):
    """Our own gain calc: latest trade vs today's first bar open."""
    try:
        latest = snap.latest_trade.price if snap.latest_trade else None
        today_open = snap.daily_bar.open if snap.daily_bar else None
        if latest is None or today_open is None or today_open <= 0:
            return None, None
        gain = (latest - today_open) / today_open
        return latest, gain
    except Exception:
        return None, None


def narrow_universe():
    """LAYER 1: broad pass over the whole universe, done every
    UNIVERSE_REFRESH_SECONDS, to build a manageable shortlist."""
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
    """LAYER 2: fast, frequent, precise re-check on just the shortlist.
    Returns a list of dicts: {symbol, price, pct_change}, our own numbers."""
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


def passes_filter(price, pct_change):
    if price is None or pct_change is None:
        return False
    if not (PRICE_MIN <= price <= PRICE_MAX):
        return False
    if pct_change < GAIN_MIN:
        return False
    return True


def get_recent_bars(symbol, limit=5):
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
    """Green candle then red candle -> trigger = red candle's open + 1 cent."""
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
    gain = (peak / entry) - 1.0
    if gain < 0.10:
        return peak * 0.98
    if gain < 0.50:
        return peak * 0.90
    if gain < 3.00:
        return peak - 0.20 * (peak - entry)
    return peak - 0.10 * (peak - entry)


def get_cash():
    try:
        acct = trading.get_account()
        return float(acct.cash)
    except Exception as e:
        log(f"get_cash error: {e}")
        return 0.0


def get_real_positions():
    try:
        positions = trading.get_all_positions()
        return {p.symbol: int(float(p.qty)) for p in positions}
    except Exception as e:
        log(f"get_real_positions error: {e}")
        return {}


def place_buy(symbol, ask):
    cash = get_cash()
    slice_dollars = cash / SLOTS
    shares = int(slice_dollars // ask)
    if shares <= 0:
        log(f"{symbol}: not enough cash for even 1 share, skipping")
        return
    limit_price = round(ask * 1.005, 2)
    try:
        order = LimitOrderRequest(
            symbol=symbol, qty=shares, side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY, limit_price=limit_price,
            extended_hours=True,
        )
        trading.submit_order(order)
        log(f"BUY {symbol} x{shares} @ limit {limit_price}")
        state[symbol] = {"held": True, "entry": ask, "peak": ask, "shares": shares}
    except Exception as e:
        log(f"place_buy({symbol}) error: {e}")


def place_sell(symbol):
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
        log(f"SELL {symbol} x{have} @ limit {limit_price}")
        state.pop(symbol, None)
    except Exception as e:
        log(f"place_sell({symbol}) error: {e}")


def run_cycle(movers):
    symbols_seen = [m["symbol"] for m in movers]
    log(f"cycle check: {len(movers)} movers found: {symbols_seen}")

    held_count = sum(1 for s in state.values() if s.get("held"))

    for m in movers:
        symbol = m["symbol"]
        price = m["price"]
        pct_change = m["percent_change"]
        if not passes_filter(price, pct_change):
            continue

        if symbol in state and state[symbol].get("held"):
            bars = get_recent_bars(symbol, limit=1)
            if bars:
                current = bars[-1].close
                state[symbol]["peak"] = max(state[symbol]["peak"], current)
                stop = tier_stop(state[symbol]["peak"], state[symbol]["entry"])
                if current <= stop:
                    place_sell(symbol)
            continue

        if held_count >= SLOTS:
            continue

        bars = get_recent_bars(symbol, limit=25)
        trigger = three_candle_pullback(bars)
        if trigger is None:
            continue
        if not ema9_above_ema20(bars):
            continue

        ask, bid = get_spread(symbol)
        if ask is None or bid is None or ask <= 0:
            continue
        spread = ask - bid
        if spread > MAX_SPREAD:
            log(f"{symbol}: spread ${spread:.2f} too wide, skipping")
            continue

        latest = bars[-1].close if bars else None
        if latest and latest >= trigger:
            place_buy(symbol, ask)
            held_count += 1


if __name__ == "__main__":
    log(f"Starting Alpaca v27 bot with SELF-BUILT SCANNER. paper={PAPER}")
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

