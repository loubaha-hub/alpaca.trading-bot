
"""
Alpaca gap-and-go trading bot (v27 logic), rebuilt clean 2026-09-24.
Runs continuously as a background worker. Paper trading by default.
"""
import os
import time
import requests
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

API_KEY = os.environ["ALPACA_API_KEY"]
SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
PAPER = os.environ.get("ALPACA_PAPER", "true").lower() == "true"

PRICE_MIN = 1.0
PRICE_MAX = 20.0
GAIN_MIN = 0.10
SLOTS = 2
MAX_SPREAD = 0.10

trading = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

state = {}  # symbol -> {"held": bool, "entry": float, "peak": float, "shares": int}


def log(msg):
    print(f"{datetime.now(timezone.utc).isoformat()}  {msg}", flush=True)


def get_movers():
    """Fetch today's top gaining stocks from Alpaca's screener endpoint."""
    url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers"
    headers = {"APCA-API-KEY-ID": API_KEY, "APCA-API-SECRET-KEY": SECRET_KEY}
    try:
        r = requests.get(url, headers=headers, params={"top": 50}, timeout=10)
        r.raise_for_status()
        return r.json().get("gainers", [])
    except Exception as e:
        log(f"get_movers error: {e}")
        return []


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


def get_spread(symbol):
    try:
        from alpaca.data.requests import StockLatestQuoteRequest
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = data_client.get_stock_latest_quote(req)
        q = quote[symbol]
        return q.ask_price, q.bid_price
    except Exception as e:
        log(f"get_spread({symbol}) error: {e}")
        return None, None
        


def tier_stop(peak, entry):
    """Corrected exit ladder, verified 2026-09-24."""
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

def run_cycle():
    movers = get_movers()
    log(f"cycle check: {len(movers)} movers found")
    

    held_count = sum(1 for s in state.values() if s.get("held"))

    for m in movers:
        symbol = m.get("symbol")
        price = m.get("price")
        pct_change = m.get("percent_change")
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

        bars = get_recent_bars(symbol, limit=3)
        trigger = three_candle_pullback(bars)
        if trigger is None:
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
    log(f"Starting Alpaca v27 bot. paper={PAPER}")
    try:
        acct = trading.get_account()
        log(f"ACCOUNT CHECK OK: status={acct.status}, cash={acct.cash}")
    except Exception as e:
        log(f"ACCOUNT CHECK FAILED: {e}")
    et = ZoneInfo("America/New_York")
    while True:
        now_et = datetime.now(et)
        start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
        if start <= now_et <= end:
            try:
                run_cycle()
            except Exception as e:
                log(f"run_cycle crashed: {e}")
        else:
            log(f"outside trading window (4am-8pm ET), current ET time: {now_et.strftime('%H:%M')}")
        time.sleep(60)

