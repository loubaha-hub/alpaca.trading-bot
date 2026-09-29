"""
Alpaca v31 (2026-09-28), self-built scanner. RUNNER DESIGN, FULL PACKAGE. PAPER TESTED ONLY - never run live.

GOAL: 1-2 stocks a day run 50-300%+; lose little on the many false starts, capture as much of the real
runs as possible, protect gains once they are made.

PRIORITY (redesigned 2026-09-28, evening, after a real case of buying into a flat stock): a stock must
  be GENUINELY RUNNING RIGHT NOW to be bought, at all, for any reason. Support/resistance levels never
  trigger a buy by themselves anymore - they only block an entry, or refine one that already qualifies.

ENTRY (either ONE of two triggers fires it, price must be above the forming bar's own open):
  (a) LEADER (top 3 by 3-minute dollar volume) + a volume spike (last closed bar >= 2x the average of
      the 10 before it) + price breaking above that bar's high.
  (b) THREE-CANDLE PULLBACK: a green bar, then a red bar, then price crosses back above the red bar's
      open + 1 cent (open to any eligible candidate, not leaders-only). This is the one to trust most:
      let the first minute's move happen, wait for the pullback (the red candle), then join as it turns
      green again, with the red candle's low as the risk-defining exit.
  Candidates must also: be near today's high (within 3%), pass the thin-volume filter, have positive
  speed, and NOT be within 3% below the 200-day EMA or the prior day's high (a real ceiling overhead -
  skipped entirely). A support bounce (within 3% above the 200-day EMA or the prior day's high) no
  longer starts a trade on its own - see CEILINGS below for where it still matters.
  News (see below) can boost ranking or be required; never required by default.

ENTRY FILTER (changed 2026-09-28, evening): the 4 intraday checks (9-EMA>20-EMA, price>9-EMA,
  price>VWAP, MACD positive) now BLOCK the entry unless all 4 are known AND favorable - this was size-
  only earlier today; it is now all-or-nothing, on request, after a real case where a mixed reading let
  a losing entry through. Known tradeoff: this can leave the bot quiet, the same way it did on the
  original v27, whenever these checks lack enough history or a genuine pullback briefly dips them.
SIZING: the first buy is a small, risk-sized probe (loses ~0.5% of equity if it hits its stop, capped at
  10% of equity). The FAST WATCHER (up to ~10 checks/sec) adds at +3/6/10/20/40/80/150% gain, building a
  genuine runner up to 80% of equity in one stock (cash only, no margin).

EXIT: the entry stop (the pattern's low) holds until the trade is up 8%; then a ladder trails 8% (to
  +25% gain), 6% (to +75%), 4% (above +75%) below the peak. FLUSH RULE: the whole position sells at once
  if price is 3% below its own last-15-second high on 2 checks in a row, even before the ladder would
  fire. Sells start under the bid (3 cents or 1%, whichever is larger) and chase for up to 12 seconds
  with no price cap; a sell can never exceed what is actually held (no shorting).

CEILINGS (a 50-cent/$1/$5/$10 round number - the step scales with price - the 200-day EMA, or the prior
  day's high): a held position trims to 40% within 10 cents below any of these, trims further to 20% if
  it chops there instead of clearing it. RESTORING (back to 70% at 5 cents clear, 100% at 10 cents clear,
  or straight to 100% if already past both by the next check) now ALSO requires the stock to be
  genuinely running right now (positive speed AND within 3% of its own day's high) - clearing the level
  alone is no longer enough. This is the fix for a real case where a stock chopping most of the
  afternoon kept getting bought back to full size just for poking past a round number.

STAGNATION (new 2026-09-28): while held, if a position's speed reads flat or negative for 3 minutes
  straight, it is trimmed to half; for 8 minutes straight, it is closed entirely - rather than waiting
  for a price-based stop that a quiet, directionless stock may never actually reach. This is the fast
  watcher's highest priority: checked before the ceiling logic and before any add.

KNOWN REPEAT-FLIERS: set KNOWN_REPEAT_TICKERS in Render's Environment tab (comma-separated symbols; no
  code change or redeploy of the other services needed - only this one restarts). A tagged symbol gets
  half-size entries/adds, a firm 20% position cap instead of 80%, and reverts to the ORIGINAL tight
  ladder (2% under +10%, 5% to +100%, 10% above) instead of the wide one above.

RE-ENTRY: after any exit, only above the day's high + 5 cents (resets every morning). A symbol bought at
  least once today stays followed for the REST OF THE DAY even once its price moves above $20 - the
  scanner's $1-$20 window only decides which brand-new names get a first look.

NEWS: every 2 minutes, one call fetches headlines (last 6 hours) for the whole shortlist. NEWS_MODE
  "boost" (default): stocks with fresh news rank first among the leaders; "require": only those can be
  entered; "off": ignored. A failed news feed just means no flags that pass - never stops the bot.

SAFETY NETS (all run inside the fast watcher, not the slow entry loop):
  - DAILY HALT: a loss of 10% (then 5%, then 2.5% after halted days) from the day's starting equity
    flattens everything and stops entries for the day; three halted days in a row stops the bot until a
    manual restart (which also resets the day's baseline).
  - ACCOUNT FLOOR: equity below $25,500 (15% under the $30,000 account) flattens everything and stops
    trading - a restart CANNOT reset this one.
  - While halted or under the floor, the watcher keeps re-selling any remaining position every few
    seconds until it is actually gone.
  - 7:55 PM ET: flatten everything once, and no new entries after it. The watcher itself only runs
    4:00 AM-8:00 PM ET on trading days.

SPEED: the entry loop pauses 0.25 seconds during the session (was 5), fetches all candidates' bars in
  ONE request, and caches equity/positions briefly. Every order chase re-reads what it actually filled
  from the order itself (never the lagging positions list), so nothing is ever bought or sold twice, and
  a sell can never be sized larger than what is truly held. The log reports EQUITY every minute and LOOP
  SPEED every 30 seconds so real timing can be checked against these numbers.

NOT YET IN: squeeze detection, Level 2 / order-book proxies, add-speed tied to price (nickel-by-nickel)
  rather than percentage gain - flagged for a future round, not built.
ASSUMPTIONS TO TUNE AFTER REAL LOGS: FLUSH_DROP_PCT/WINDOW, SPIKE_MULT, RISK_PER_TRADE, ADD_STEPS,
  LEADER_TOP_N, the soft-filter size table, NEWS_MODE, the caution multipliers, CHANGE_LO/HI.
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
ACCOUNT_FLOOR = None            # hard floor in dollars: below it everything is sold and nothing is bought (None = off)
LADDER_SWITCH_PCT = 0.02        # gain at which the entry stop (red bar's low) hands off to the trailing ladder
NEAR_LEVEL_PCT = 0.03           # how close counts as "near" a key level (200-day EMA, prior-day high)
CAUTION_LADDER_SWITCH_PCT = 0.02   # a KNOWN REPEAT-FLIER always uses this tight switch, whatever the
# strategy's normal setting is - these names give back gains as fast as they make them, sometimes faster
CAUTION_TICKERS = {s.strip().upper() for s in os.environ.get("KNOWN_REPEAT_TICKERS", "").split(",") if s.strip()}
# Symbols known (from experience) to spike and give back the whole move, often several times a month.
# Set this in Render's Environment tab (comma-separated, e.g. "ABCD,WXYZ") - no code change or redeploy of
# the other services needed; only the one service you edit restarts. Empty by default.


def is_caution_ticker(symbol):
    return symbol.upper() in CAUTION_TICKERS


ROUND_LEVEL_STEP = 0.50         # psychological round-number levels every 50 cents (low-priced stocks watch these)
ROUND_LEVEL_WATCH = 0.10        # start trimming a held position within 10 cents BELOW a ceiling

UNIVERSE_REFRESH_SECONDS = 120
FAST_CHECK_SECONDS = 0.25       # pause between entry passes during the session (was 5 seconds)
IDLE_SECONDS = 5.0              # pause when the market is closed
SNAPSHOT_BATCH_SIZE = 200
WATCH_INTERVAL = 0.10           # position watcher: up to ~10 checks a second (limited by the call time)
WATCH_POS_REFRESH = 1.5         # how often the watcher re-reads real positions
FLUSH_DROP_PCT = 0.03           # FLUSH RULE: sell everything if the price is 3% below its last-15-seconds high...
FLUSH_WINDOW_SEC = 15
FLUSH_CONFIRM_TICKS = 2         # ...on 2 checks in a row (one odd print never triggers it)
BUY_CHASE_SECONDS = 6           # how long a buy keeps chasing
SELL_CHASE_SECONDS = 12         # how long a sell keeps chasing
CHASE_MIN_INTERVAL = 0.25       # never faster than 4 attempts a second (Alpaca limits order calls)
MAX_CHASE_ATTEMPTS = 60
FIRST_EXIT_OFFSET_MIN = 0.03    # sell orders start at least 3 cents (or 1%) under the bid
FIRST_EXIT_OFFSET_PCT = 0.01
EQUITY_LOG_SECONDS = 60
CYCLE_LOG_SECONDS = 30

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


_last_logged = {}


def log_every(key, seconds, msg):
    """Log a message at most once per `seconds` for the same key."""
    now = time.time()
    if now - _last_logged.get(key, 0) >= seconds:
        _last_logged[key] = now
        log(msg)


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


def get_recent_bars_many(symbols, limit=15):
    """Recent 1-minute bars for MANY stocks in ONE request (falls back to one
    request per stock if the batch call fails)."""
    if not symbols:
        return {}
    try:
        req = StockBarsRequest(
            symbol_or_symbols=list(symbols),
            timeframe=TimeFrame.Minute,
            start=datetime.now(timezone.utc) - timedelta(minutes=limit + 5),
            limit=10000,
        )
        bars = data_client.get_stock_bars(req)
        return {s: (bars.data[s][-limit:] if s in bars.data else []) for s in symbols}
    except Exception as e:
        log(f"get_recent_bars_many error: {e} - falling back to one request per stock")
        return {s: get_recent_bars(s, limit=limit) for s in symbols}


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
        return None                       # not enough history - unknown, not unfavorable
    closes = [b.close for b in done]
    e9 = ema(closes[-20:], 9)
    e20 = ema(closes[-20:], 20)
    if e9 is None or e20 is None:
        return None
    return e9 > e20


def above_9ema(done, price):
    if len(done) < 9:
        return None
    e9 = ema([b.close for b in done[-9:]], 9)
    return None if e9 is None else price >= e9


def compute_vwap(day_bars):
    if not day_bars:
        return None
    total_volume = sum(b.volume for b in day_bars)
    if total_volume <= 0:
        return None
    return sum(b.close * b.volume for b in day_bars) / total_volume


def compute_macd(closes):
    """Standard MACD(12,26,9). Returns (macd_line, signal_line) or (None, None)
    if there isn't enough history yet."""
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
        return None                       # not enough history - unknown
    return macd_line > 0 and macd_line > signal_line


_daily_cache = {}


def get_daily_bars(symbol, limit=210):
    """~210 calendar days of DAILY bars (enough for a 200-day EMA)."""
    try:
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=datetime.now(timezone.utc) - timedelta(days=int(limit * 1.6) + 10),
        )
        bars = data_client.get_stock_bars(req)
        rows = bars[symbol] if symbol in bars.data else []
        return rows[-limit:] if rows else []
    except Exception as e:
        log(f"get_daily_bars({symbol}) error: {e}")
        return []


def daily_levels(symbol, ttl_seconds=3600):
    """{'ema200': .., 'prior_high': ..} from DAILY bars, cached for an hour
    (these barely move intraday, so there is no reason to refetch every pass).
    Either value is None if there isn't enough daily history yet (e.g. a new
    listing) - callers must treat None as 'unknown', never as a level to defend."""
    now = time.time()
    c = _daily_cache.get(symbol)
    if c and now - c[0] < ttl_seconds:
        return c[1]
    daily = get_daily_bars(symbol)
    et = ZoneInfo("America/New_York")
    today = datetime.now(et).date()
    closed_days = [b for b in daily if b.timestamp.astimezone(et).date() < today]
    ema200 = ema([b.close for b in closed_days[-200:]], 200) if len(closed_days) >= 200 else None
    prior_high = closed_days[-1].high if closed_days else None
    levels = {"ema200": ema200, "prior_high": prior_high}
    _daily_cache[symbol] = (now, levels)
    return levels


def round_level_step(price):
    """The round-number spacing scales with price, so it stays a MEANINGFUL
    psychological level at any price a runner reaches: 50 cents under $20 (the
    original small-cap range), $1 from $20-$50, $5 from $50-$200, $10 above
    that. Without this, a $0.50 step would fire on a $120 stock roughly every
    0.4% - noise, not a real level."""
    if price < 20:
        return 0.50
    if price < 50:
        return 1.00
    if price < 200:
        return 5.00
    return 10.00


def next_round_level(price, step=None):
    """The nearest round-number level strictly above price (e.g. price 1.43 ->
    1.50; price 62 -> 65, using the $5 step for that price band)."""
    import math
    step = step if step is not None else round_level_step(price)
    n = math.floor(round(price / step, 6)) + 1
    return round(n * step, 2)


def nearest_ceiling(symbol, price):
    """The closest known resistance sitting ABOVE price right now: the next
    50-cent round number, the 200-day EMA, or the prior day's high, whichever
    is nearest. Always returns a level (the round number always exists)."""
    candidates = [next_round_level(price)]
    levels = daily_levels(symbol)
    for lv in (levels.get("ema200"), levels.get("prior_high")):
        if lv and lv > price:
            candidates.append(lv)
    return min(candidates)


def level_gate(price, level):
    """How PRICE sits relative to a key level (the 200-day EMA, the prior day's
    high): 'block' if price is below the level and within NEAR_LEVEL_PCT of it
    (a real ceiling right overhead - skip the entry); 'bounce' if price is
    above the level and within NEAR_LEVEL_PCT of it (testing it as support -
    a place to buy or add, expecting the crowd to defend it); None otherwise
    (too far from the level either way, or the level is unknown)."""
    if not level or level <= 0 or not price:
        return None
    if price < level:
        return "block" if (level - price) / level <= NEAR_LEVEL_PCT else None
    return "bounce" if (price - level) / level <= NEAR_LEVEL_PCT else None


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


_cache = {}


def get_equity_cached(max_age=5.0):
    """Account equity, re-read at most every `max_age` seconds."""
    now = time.time()
    c = _cache.get("equity")
    if c and now - c[0] < max_age:
        return c[1]
    e = get_equity()
    if e > 0:
        _cache["equity"] = (now, e)
    return e


def cached_positions(max_age=1.0):
    """Positions for the entry loop and the watcher: at most one call per
    `max_age` seconds (Alpaca limits order-side calls). The chase never uses
    this - it always reads fresh. Returns None if there is no data at all."""
    now = time.time()
    c = _cache.get("positions")
    if c and now - c[0] < max_age:
        return c[1]
    d = get_positions_detail()
    if d is not None:
        _cache["positions"] = (now, d)
        return d
    return c[1] if c else None


def invalidate_positions():
    _cache.pop("positions", None)


def get_real_positions_cached(max_age=1.0):
    d = cached_positions(max_age)
    return None if d is None else {s: v[0] for s, v in d.items()}


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
def _order_progress(order_id):
    """(shares filled, finished?) for one of OUR orders, read from the order itself
    (immediate) instead of from the positions list, which lags behind fills."""
    try:
        o = trading.get_order_by_id(order_id)
        filled = int(float(o.filled_qty or 0))
        status = str(getattr(o.status, "value", o.status)).lower()
        return filled, status in ("filled", "canceled", "expired", "rejected", "done_for_day")
    except Exception as e:
        log(f"order lookup failed ({order_id}): {e}")
        return None, False


def aggressive_execute(symbol, side, target_shares, max_attempts=MAX_CHASE_ATTEMPTS, wait_seconds=0.05,
                       max_seconds=None):
    """BUY: target_shares = holding to reach. SELL: target_shares = holding to
    sell DOWN to (0 = full exit). Keeps chasing for a TIME limit (buys 6 s, sells
    12 s), never faster than 4 attempts a second. Every attempt: cancel the stale
    order, read what our last order REALLY filled (from the order itself, not the
    lagging positions list - this stops double buys and oversells), re-read the
    market, and submit for exactly what is left. Buys chase upward (never above
    2% over the current ask). Sells start a few cents under the bid and chase
    downward with no cap, so an exit always gets out."""
    if max_seconds is None:
        max_seconds = SELL_CHASE_SECONDS if side == OrderSide.SELL else BUY_CHASE_SECONDS
    try:
        return _chase(symbol, side, target_shares, max_attempts, wait_seconds, max_seconds)
    finally:
        invalidate_positions()


def _chase(symbol, side, target_shares, max_attempts, wait_seconds, max_seconds):
    t0 = time.time()
    last_bid = None
    start_have = None          # position when the chase began
    filled_total = 0           # shares our own orders have filled since then (read from the orders)
    last_order_id = None
    last_submit = 0.0
    attempt = -1
    while attempt + 1 < max_attempts and time.time() - t0 < max_seconds:
        attempt += 1
        if side == OrderSide.BUY and symbol in selling:
            cancel_open_orders(symbol)         # an exit has started on this stock - stop buying it
            log(f"{symbol}: buy chase abandoned, a sell is in progress")
            return False
        pace = CHASE_MIN_INTERVAL - (time.time() - last_submit)
        if pace > 0:
            time.sleep(pace)
        if cancel_open_orders(symbol):
            time.sleep(0.1)                    # let the cancel land before counting fills
        if last_order_id is not None:          # what did our last order really fill?
            for _ in range(4):
                filled, finished = _order_progress(last_order_id)
                if filled is None or finished:
                    break
                time.sleep(0.05)
            if filled is not None:
                filled_total += filled
            last_order_id = None
        pos_have = get_position_qty(symbol)
        if pos_have is None:                   # failed call - never assume 'closed'
            time.sleep(wait_seconds)
            continue
        if start_have is None:
            start_have = pos_have
        if side == OrderSide.SELL:
            have = min(pos_have, start_have - filled_total)
            remaining = have - target_shares
        else:
            have = max(pos_have, start_have + filled_total)
            remaining = target_shares - have
        if remaining <= 0:
            log(f"{symbol}: FULLY EXECUTED in {(time.time() - t0) * 1000:.0f}ms ({attempt} attempt(s))")
            return True
        ask, bid = get_spread(symbol)
        if not ask or not bid:
            time.sleep(wait_seconds)
            continue
        move = 0.0 if last_bid is None else abs(bid - last_bid)   # how far the market just moved
        last_bid = bid
        if side == OrderSide.SELL:
            first_offset = max(FIRST_EXIT_OFFSET_MIN, FIRST_EXIT_OFFSET_PCT * bid)
            price = max(0.01, round(bid - first_offset - 0.01 * attempt - move, 2))
        else:
            price = round(bid + 0.01 * attempt + move, 2)
            price = min(price, round(ask * (1 + CHASE_CAP_PCT), 2))
        try:
            t1 = time.time()
            order = trading.submit_order(LimitOrderRequest(
                symbol=symbol, qty=remaining, side=side, time_in_force=TimeInForce.DAY,
                limit_price=price, extended_hours=True))
            last_order_id = getattr(order, "id", None)
            last_submit = time.time()
            log(f"{'SELL' if side == OrderSide.SELL else 'BUY'} (chase) {symbol} x{remaining} @ {price} "
                f"(bid {bid} ask {ask} attempt {attempt + 1} submit {(time.time() - t1) * 1000:.0f}ms)")
        except Exception as e:
            log(f"aggressive_execute({symbol}) submit error: {e}")
        time.sleep(wait_seconds)
    if side == OrderSide.BUY:
        cancel_open_orders(symbol)             # never leave a stale buy resting
    log(f"{symbol}: WARNING - not fully executed after {attempt + 1} attempts "
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
def active_stop(entry, peak, red_low, caution=False):
    """Entry stop = the red bar's low, until the trade is up LADDER_SWITCH_PCT
    (or CAUTION_LADDER_SWITCH_PCT for a known repeat-flier); after that the
    trailing ladder (tier_stop) takes over. red_low None = ladder only."""
    switch = CAUTION_LADDER_SWITCH_PCT if caution else LADDER_SWITCH_PCT
    if red_low is not None and entry > 0 and peak < entry * (1 + switch):
        return red_low
    return tier_stop(peak, entry, caution)


def on_watch_tick(sym, price, qty, st):
    """Hook called by the watcher for every held stock on every check (a strategy
    can override it, e.g. to add to a winner within a fraction of a second)."""
    pass


def position_watcher(stop_event=None, session_fn=None):
    """Own thread. Watches every REAL position from Alpaca (so a late fill or a
    restart is covered too) on the live last-trade price, up to ~10 times a
    second, independent of the entry scan. It sells the WHOLE position the
    instant (a) the stop is hit, or (b) the FLUSH RULE fires: the price is 3%
    below its last-15-seconds high on 2 checks in a row. The sell chase runs in
    its own thread so the other positions keep being watched."""
    sold_at = {}
    pos = {}
    hist = {}                  # symbol -> [(time, price)] over the last FLUSH_WINDOW_SEC
    flush_hits = {}
    session = session_fn or in_session
    while stop_event is None or not stop_event.is_set():
        try:
            if not session():
                time.sleep(5.0)
                continue
            check_daily_halt(get_equity_cached(max_age=1.0))          # the safety net lives in the fast loop
            halted_mode = guard["halted"] or guard["stopped"] or guard.get("floor_hit", False)
            fresh = cached_positions(max_age=WATCH_POS_REFRESH)
            if fresh is not None:
                pos = {s: v for s, v in fresh.items() if v[0] > 0}
                with state_lock:
                    for s in list(state.keys()):
                        recent = time.time() - state[s].get("touched", 0) < 20     # just bought: positions may still lag
                        if s not in pos and s not in buying and s not in selling and not recent:
                            state.pop(s, None)
            if not pos:
                time.sleep(0.25)
                continue
            prices = get_live_prices(list(pos.keys()))
            t = time.time()
            for sym, (qty, avg) in pos.items():
                price = prices.get(sym)
                if not price:
                    continue
                h = hist.setdefault(sym, [])
                h.append((t, price))
                while h and h[0][0] < t - FLUSH_WINDOW_SEC:
                    h.pop(0)
                recent_high = max(p for _, p in h)
                with state_lock:
                    st = state.setdefault(sym, {})
                    st["entry"] = avg
                    st["peak"] = max(st.get("peak", max(avg, price)), price)
                    peak = st["peak"]
                    stop = active_stop(avg, peak, st.get("red_low"), is_caution_ticker(sym))
                    busy = sym in selling
                    st_copy = dict(st)
                flush = price <= recent_high * (1 - FLUSH_DROP_PCT)
                flush_hits[sym] = flush_hits.get(sym, 0) + 1 if flush else 0
                cooled = time.time() - sold_at.get(sym, 0) > 3.0
                if halted_mode and not busy and cooled:                # halted: keep selling until the position is gone
                    log_every("halt_flatten:" + sym, 10, f"HALTED: selling {sym} (still held)")
                    sold_at[sym] = time.time()
                    sell_async(sym, "halt_flatten")
                elif not busy and cooled and (price <= stop or flush_hits[sym] >= FLUSH_CONFIRM_TICKS):
                    why = "stop" if price <= stop else "FLUSH"
                    log(f"WATCHER {why}: {sym} price {price} (stop {stop:.4f}, 15s high {recent_high:.4f}, "
                        f"entry {avg:.4f}, peak {peak:.4f}) - selling everything")
                    sold_at[sym] = time.time()
                    flush_hits[sym] = 0
                    sell_async(sym, why)
                elif not busy:
                    on_watch_tick(sym, price, qty, st_copy)
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
    """Two safety nets. (1) DAILY HALT: a loss of 10% (then 5%, then 2.5% after
    halted days) from the day's starting equity flattens everything and stops
    trading for the day. (2) ACCOUNT FLOOR: equity below a fixed dollar amount
    flattens everything and stops trading - it does not depend on the day's
    baseline, so a restart cannot reset it. Returns True while trading is stopped."""
    reason = None
    with guard_lock:
        if guard["stopped"]:
            return True
        if equity <= 0:                                   # a failed read never changes the state
            return guard["halted"] or guard.get("floor_hit", False)
        if ACCOUNT_FLOOR and equity < ACCOUNT_FLOOR:
            if guard.get("floor_hit"):
                return True
            guard["floor_hit"] = True
            reason = f"ACCOUNT FLOOR: equity {equity:,.2f} is below the floor of {ACCOUNT_FLOOR:,.2f}"
        else:
            guard["floor_hit"] = False
            if guard["baseline"] is None:
                return False
            if guard["halted"]:
                return True
            thr = HALT_THRESHOLDS[min(guard["streak"], 2)]
            loss = (guard["baseline"] - equity) / guard["baseline"]
            if loss < thr:
                return False
            guard["halted"] = True
            reason = f"DAILY HALT: down {loss:.1%} from {guard['baseline']:.2f} (limit {thr:.1%})"
    log(f"{reason} - flattening everything, no new entries")
    for sym, q in get_real_positions().items():
        if q > 0:
            sell_async(sym, "halt_flatten")
    return True


def reconcile_on_startup():
    pos = get_positions_detail() or {}
    for sym, (q, avg) in pos.items():
        if q > 0:
            log(f"RECONCILED on startup: {sym} x{q} @ avg {avg:.4f} (the watcher will protect it)")


# ================= v31-specific: leaders only, volume-spike breakout, probe + adds =================
STRATEGY_NAME = "v31"
ACCOUNT_FLOOR = 25500.0            # hard floor for the $30,000 account (15% down): below it, sell everything and stop
MAX_NAMES = 3                      # at most 3 positions - leaders only
LEADER_TOP_N = 3                   # only the top 3 by 3-minute dollar volume may be entered
SPIKE_MULT = 2.0                   # last closed bar volume >= 2x the average of the 10 bars before it
SPIKE_LOOKBACK = 10
RISK_PER_TRADE = 0.005             # a stop-out on the probe costs about 0.5% of equity
MIN_STOP_DIST_PCT = 0.01           # never size off a stop closer than 1% of the price
PROBE_MAX_PCT = 0.10               # the first, risk-sized probe is never more than 10% of equity
MAX_POSITION_PCT = 0.80            # a real runner can be built up to 80% of equity in one stock (cash only, no margin)
LADDER_SWITCH_PCT = 0.08           # a real run gets 8% of room before the trailing ladder takes over (was 2%)
# (gain from the first entry, size of the add as a multiple of the probe) - lets a genuine runner
# keep being built all the way toward the 80% cap (the cap itself, applied in do_add, is what stops it
# there - these multiples don't need to add up to exactly 80%)
ADD_STEPS = [(0.03, 1.00), (0.06, 1.00), (0.10, 1.00), (0.20, 2.00), (0.40, 2.00), (0.80, 3.00), (1.50, 3.00)]
SOFT_FILTER_SIZE = {4: 1.00, 3: 0.85, 2: 0.65, 1: 0.45, 0: 0.45}   # probe size by how many of the 4
# intraday checks (9-EMA>20-EMA, price>9-EMA, price>VWAP, MACD positive) currently favor the trade -
# these never block an entry, they only make the first probe smaller when the picture is mixed
CAUTION_SIZE_MULT = 0.50            # a known repeat-flier's probe/adds are sized at half, on top of everything else
CAUTION_MAX_POSITION_PCT = 0.20     # and its position is capped at 20% of equity, not the usual 80%
CEILING_TRIM_TO_PCT = 0.40          # first approach to a ceiling: trim down to 40% of the current size
CEILING_JITTERY_TRIM_TO_PCT = 0.20  # chopping at the ceiling instead of clearing it: trim down to 20%
CEILING_CLEAR_MARGIN = 0.05         # 5 cents clear -> first restore step (was 2 cents)
CEILING_RESTORE_STEP2_MARGIN = 0.10 # 10 cents clear -> second restore step, straight to full size
CEILING_RESTORE_STEP1_PCT = 0.30    # step 1 adds this fraction of the ORIGINAL size back (e.g. 40% -> 70%)
STAGNATION_TRIM_SEC = 180            # speed flat/negative for 3 minutes straight while held -> trim to 50%
STAGNATION_EXIT_SEC = 480            # ...for 8 minutes straight -> close the position entirely
STAGNATION_CHECK_SEC = 15            # how often the stagnation timer is actually re-evaluated (throttled)
stagnation_state = {}                # symbol -> {"weak_since": ts or None, "last_check": ts, "trimmed": bool}
ceiling_state = {}                  # symbol -> {"level","pre_trim_qty","stage","restore_step","retreated","was_in_zone"}
NEWS_MODE = "boost"                # "off" | "boost" (stocks with fresh news rank first among the leaders) | "require" (only stocks with fresh news can be entered)
NEWS_WINDOW_MIN = 360              # a headline counts as fresh for 6 hours
NEWS_REFRESH_SECONDS = 120         # the screener re-reads the news for the whole shortlist every 2 minutes (one call)
news_cache = {}                    # symbol -> (headline, created_at)
comeback_floor = {}
touched_today = set()               # every symbol bought at least once today - followed all day even
# if it later trades above PRICE_MAX (a stock that ran from $19 to $45 and got stopped out should stay
# on the radar for the rest of the day, not fall off just because it is no longer a fresh $1-$20 candidate)
adding = set()                     # stocks with an add in progress (one at a time per stock)
_news_client = None
_last_news_refresh = 0.0


def on_new_day():
    comeback_floor.clear()                     # yesterday's high must not block today's re-entries
    ceiling_state.clear()
    touched_today.clear()
    stagnation_state.clear()


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
    ceiling_state.pop(symbol, None)                        # a fresh entry later should not inherit stale ceiling state
    stagnation_state.pop(symbol, None)
    high = get_day_high(symbol)
    if high:
        comeback_floor[symbol] = round(high + 0.05, 4)     # re-enter only above the day's high + 5c


def tier_stop(peak, entry, caution=False):
    """The 8%-of-room ladder: under LADDER_SWITCH_PCT the ENTRY stop (the
    spike's low) still applies - see active_stop(). Once past that: 8% trail
    from LADDER_SWITCH_PCT to +25%, 6% from +25% to +75%, 4% above +75%. Lets
    a volatile stock's ordinary noise breathe early, then locks in more of a
    genuinely big run as it develops. A KNOWN REPEAT-FLIER (caution=True)
    falls back to the original, tighter ladder instead: 2% under +10%, 5%
    from +10% to +100%, 10% above +100% - these names are known to give the
    whole move back, sometimes faster than they made it."""
    if entry <= 0:
        return peak
    gain = (peak / entry) - 1.0
    if caution:
        if gain < 0.10:
            return peak * 0.98
        if gain < 1.00:
            return peak * 0.95
        return peak * 0.90
    if gain < 0.25:
        return peak * 0.92
    if gain < 0.75:
        return peak * 0.94
    return peak * 0.96


def three_candle_pullback(done):
    """Two CLOSED bars: green, then red. Returns (trigger, red_bar_low) or None.
    The entry fires when the LIVE price crosses above trigger (red open + 1c)."""
    if len(done) < 2:
        return None
    prev, last = done[-2], done[-1]
    if prev.close > prev.open and last.close < last.open:
        return round(last.open + 0.01, 4), last.low
    return None


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


def soft_filter_score(done, day_bars, price):
    """How many of the 4 intraday checks currently favor the trade (9-EMA above
    20-EMA, price above its own 9-EMA, price above VWAP, MACD positive). A
    check that cannot be computed yet (not enough bars) counts toward neither
    side, so an early-session trade is never penalized for data it can't have.
    Returns (favorable, checkable) - never blocks, only used to size the probe."""
    checks = [
        ema9_above_ema20(done),
        above_9ema(done, price),
        (None if not day_bars else price >= (compute_vwap(completed_bars(day_bars)) or price)),
        macd_positive(done),
    ]
    known = [c for c in checks if c is not None]
    favorable = sum(1 for c in known if c)
    return favorable, len(known)


def probe_shares(equity, ask, stop_low, size_mult=1.0, cap_mult=1.0):
    """Size the probe so hitting the stop costs ~0.5% of equity times the
    soft-filter size multiplier (a wide stop means fewer shares), never more
    than 10% of equity. `cap_mult` (used for a known repeat-flier) shrinks
    BOTH the risk-based size and the 10% cap together, so it is a real overall
    exposure cut - unlike size_mult, which only ever softens the risk side and
    was never meant to touch the hard 10% ceiling."""
    dist = max(ask - stop_low, MIN_STOP_DIST_PCT * ask)
    by_risk = (RISK_PER_TRADE * size_mult * cap_mult * equity) / dist
    by_cap = (PROBE_MAX_PCT * cap_mult * equity) / ask
    return int(min(by_risk, by_cap))


def place_buy(symbol, ask, stop_low, size_mult=1.0, cap_mult=1.0):
    equity = get_equity()
    shares = probe_shares(equity, ask, stop_low, size_mult, cap_mult)
    if shares <= 0:
        log(f"{symbol}: probe too small for even 1 share, skipping")
        return False
    with state_lock:
        buying.add(symbol)
        state.setdefault(symbol, {}).update(red_low=stop_low, touched=time.time())   # entry stop = the spike candle's low
    try:
        ok = aggressive_execute(symbol, OrderSide.BUY, shares)
    finally:
        with state_lock:
            buying.discard(symbol)
    if ok:
        with state_lock:
            state.setdefault(symbol, {}).update(first_entry=ask, probe_shares=shares, adds_done=[], touched=time.time())
        touched_today.add(symbol)
    return ok


def do_add(sym, i, price, qty, equity):
    """One add: +3% adds a full probe, +6% adds 75% of a probe, +10% adds 50% -
    the adds shrink as the trail widens - and never past 30% of equity."""
    step, mult = ADD_STEPS[i]
    try:
        with state_lock:
            probe = state.get(sym, {}).get("probe_shares", 0)
        fresh = get_position_qty(sym)                     # a fresh read, so the target is never based on a stale count
        q = fresh if fresh is not None else qty
        cap_pct = CAUTION_MAX_POSITION_PCT if is_caution_ticker(sym) else MAX_POSITION_PCT
        target = min(q + int(probe * mult), int(cap_pct * equity // price))
        log(f"ADD {sym} step {i + 1} (price {price}): {q} -> {target} shares")
        if target > q:
            aggressive_execute(sym, OrderSide.BUY, target)
    finally:
        with state_lock:
            adding.discard(sym)


def add_async(sym, i, price, qty, equity):
    threading.Thread(target=do_add, args=(sym, i, price, qty, equity), daemon=True).start()


def do_trim(sym, target, reason):
    try:
        aggressive_execute(sym, OrderSide.SELL, target)
        log(f"CEILING {reason}: {sym} trimmed to {target} shares")
    finally:
        with state_lock:
            adding.discard(sym)


def do_restore(sym, target):
    try:
        fresh = get_position_qty(sym)
        q = fresh if fresh is not None else 0
        if target > q:
            aggressive_execute(sym, OrderSide.BUY, target)
            log(f"CEILING cleared: {sym} restored to {target} shares")
    finally:
        with state_lock:
            adding.discard(sym)


def stock_is_running(sym, price):
    """The core gate: is this stock ACTUALLY moving right now, confirmed by
    volume, and near its own day's high - not just having poked a few cents
    past a technical level while otherwise going nowhere. Used to decide
    whether a ceiling restore should rebuild a position back to full size."""
    done = completed_bars(get_recent_bars(sym, limit=15))
    if not done:
        return False
    if speed(done, price, day_max_volume(sym)) <= 0:
        return False
    day_bars = completed_bars(get_day_bars(sym))
    if not day_bars:
        return True                          # can't check the day's high yet - don't block on missing data alone
    day_high = max(b.high for b in day_bars)
    return price >= day_high * (1 - NEAR_HIGH_PCT)


def check_ceiling(sym, price, qty):
    """Trim a held position as it nears a ceiling (a 50-cent round number, the
    200-day EMA, or the prior day's high): to 40% on the first approach, to 20%
    if it chops there instead of clearing it. Restoring is two steps: 5 cents
    clear adds back to 70% of the original size, 10 cents clear (or a move that
    already reaches 10 cents by the time this runs - a fast mover doesn't wait
    for the first step) completes the restore to 100%. Runs on every fast-
    watcher tick; touches nothing until price is actually within
    ROUND_LEVEL_WATCH of a level. Returns True if it handled this tick (an add
    should not also fire on the same tick)."""
    with state_lock:
        cs = dict(ceiling_state.get(sym, {}))
    level = cs.get("level") or nearest_ceiling(sym, price)

    if cs.get("stage") in ("trimmed", "jittery"):
        pre = cs.get("pre_trim_qty", qty)

        # a restore only rebuilds size if the stock is ALSO genuinely running right now -
        # clearing the level alone is not enough (this is what let NVTS get bought back on
        # 2026-09-28 while it was flat/drifting for most of the afternoon)
        if price >= level + CEILING_RESTORE_STEP2_MARGIN and stock_is_running(sym, price):
            with state_lock:
                ceiling_state.pop(sym, None)
                if sym in adding:
                    return True
                adding.add(sym)
            threading.Thread(target=do_restore, args=(sym, pre), daemon=True).start()
            return True

        if price >= level + CEILING_CLEAR_MARGIN and stock_is_running(sym, price):
            if cs.get("restore_step", 0) < 1:                   # step 1 fires once
                target = int(pre * min(1.0, CEILING_TRIM_TO_PCT + CEILING_RESTORE_STEP1_PCT))
                with state_lock:
                    ceiling_state[sym] = dict(cs, level=level, restore_step=1)
                    if sym in adding:
                        return True
                    adding.add(sym)
                threading.Thread(target=do_restore, args=(sym, target), daemon=True).start()
            return True

        if cs.get("restore_step", 0) >= 1:
            return True    # already restoring, sitting between the two steps - nothing new this tick

        if price < level - ROUND_LEVEL_WATCH:                    # dropped well clear of the zone without clearing
            if cs.get("was_in_zone"):
                with state_lock:
                    ceiling_state[sym] = dict(cs, retreated=True)
            return False

        # still inside the watch zone, below the clear margin, restore not yet started
        if cs.get("retreated") and cs.get("stage") != "jittery":
            with state_lock:
                if sym in adding:
                    return True
                adding.add(sym)
                ceiling_state[sym] = dict(cs, stage="jittery", retreated=False, was_in_zone=True)
            target = max(1, int(pre * CEILING_JITTERY_TRIM_TO_PCT))
            threading.Thread(target=do_trim, args=(sym, target, "jittery")).start()
            return True
        return True   # already trimmed for this level and waiting - nothing new to do this tick

    if price < level - ROUND_LEVEL_WATCH:
        return False

    # not yet trimmed, and inside the watch zone (within ROUND_LEVEL_WATCH below the level)
    with state_lock:
        if sym in adding:
            return True
        adding.add(sym)
        ceiling_state[sym] = {"level": level, "pre_trim_qty": qty, "stage": "trimmed", "was_in_zone": True}
    target = max(1, int(qty * CEILING_TRIM_TO_PCT))
    threading.Thread(target=do_trim, args=(sym, target, "approaching")).start()
    return True


def do_stagnation_trim(sym, target):
    try:
        aggressive_execute(sym, OrderSide.SELL, target)
        log(f"STAGNATION: {sym} trimmed to {target} shares (flat for {STAGNATION_TRIM_SEC // 60}+ min)")
    finally:
        with state_lock:
            adding.discard(sym)


def do_stagnation_exit(sym):
    try:
        place_sell(sym, "stagnation")
    finally:
        with state_lock:
            adding.discard(sym)


def check_stagnation(sym, price, qty):
    """While held, if the stock has been flat or losing speed for a sustained
    stretch, trim it (STAGNATION_TRIM_SEC) and eventually close it
    (STAGNATION_EXIT_SEC) instead of waiting for a price-based stop to be
    hit - a move that has stopped happening is itself a reason to reduce risk.
    Throttled to once every STAGNATION_CHECK_SEC (needs a fresh bars read)."""
    now = time.time()
    ss = stagnation_state.setdefault(sym, {"weak_since": None, "last_check": 0, "trimmed": False})
    if now - ss["last_check"] < STAGNATION_CHECK_SEC:
        return False
    ss["last_check"] = now
    done = completed_bars(get_recent_bars(sym, limit=15))
    if not done:
        return False
    if speed(done, price, day_max_volume(sym)) > 0:
        ss["weak_since"] = None
        ss["trimmed"] = False
        return False
    if ss["weak_since"] is None:
        ss["weak_since"] = now
        return False
    weak_for = now - ss["weak_since"]
    if weak_for >= STAGNATION_EXIT_SEC:
        with state_lock:
            if sym in adding:
                return True
            adding.add(sym)
        stagnation_state.pop(sym, None)
        threading.Thread(target=do_stagnation_exit, args=(sym,), daemon=True).start()
        return True
    if weak_for >= STAGNATION_TRIM_SEC and not ss["trimmed"]:
        target = max(1, qty // 2)
        with state_lock:
            if sym in adding:
                return True
            adding.add(sym)
        ss["trimmed"] = True
        threading.Thread(target=do_stagnation_trim, args=(sym, target), daemon=True).start()
        return True
    return False


def on_watch_tick(sym, price, qty, st):
    """Called by the fast watcher for every held stock on every check (up to ~10
    a second). Priority order: (1) STAGNATION - a position that has gone quiet
    gets trimmed/closed first, since that is risk reduction; (2) CEILING - trim
    near a level, restore once through AND genuinely running again; (3) the
    gain-based add ladder, only on ticks neither of the above acted on."""
    if "first_entry" not in st or sym in buying:     # leftovers and late fills get neither
        return
    if sym not in adding and check_stagnation(sym, price, qty):
        return
    if sym not in adding and check_ceiling(sym, price, qty):
        return
    if sym in adding:
        return
    gain = price / st["first_entry"] - 1.0
    for i, (step, mult) in enumerate(ADD_STEPS):
        if i in st.get("adds_done", []) or gain < step:
            continue
        with state_lock:
            if sym in adding:
                return
            adding.add(sym)
            state.setdefault(sym, {}).setdefault("adds_done", []).append(i)
        add_async(sym, i, price, qty, get_equity_cached())
        return


def run_cycle(movers):
    log_every("cycle", CYCLE_LOG_SECONDS, f"cycle check: {len(movers)} movers found: {[m['symbol'] for m in movers]}")
    if guard["stopped"]:
        log_every("stopped", 60, "STOPPED: three halted days in a row - restart the service manually to resume")
        return
    equity = get_equity_cached()
    if check_daily_halt(equity):
        return
    real = get_real_positions_cached()
    if real is None:                                   # positions unknown: skip this pass rather than guess
        return
    held_count = len([s for s, q in real.items() if q > 0]) + len(buying)
    if NEWS_MODE != "off":
        refresh_news([m["symbol"] for m in movers])

    # pass 1: everything near its high and not already held, then ONE request for all their bars.
    # a symbol touched at least once today is followed for the REST OF THE DAY even once it trades
    # above PRICE_MAX - the scanner's own filter only decides which FRESH names are worth a first look.
    movers_by_symbol = {m["symbol"]: m for m in movers}
    stale_touched = [s for s in touched_today if s not in movers_by_symbol and real.get(s, 0) == 0]
    if stale_touched:
        snaps = get_snapshots(stale_touched)
        for symbol, snap in snaps.items():
            try:
                price = snap.latest_trade.price if snap.latest_trade else None
                day_high = snap.daily_bar.high if snap.daily_bar else None
                today_open = snap.daily_bar.open if snap.daily_bar else None
            except Exception:
                continue
            if not price or not today_open or today_open <= 0:
                continue
            movers_by_symbol[symbol] = {"symbol": symbol, "price": price,
                                        "percent_change": (price - today_open) / today_open, "day_high": day_high}

    eligible = []
    for m in movers_by_symbol.values():
        symbol, price = m["symbol"], m["price"]
        if not near_high(m):
            continue
        if real.get(symbol, 0) > 0 or symbol in buying or symbol in selling:
            continue
        floor = comeback_floor.get(symbol)
        if floor is not None and price < floor:
            continue
        eligible.append(m)
    bars_map = get_recent_bars_many([m["symbol"] for m in eligible], limit=70)   # 70: enough for MACD's 35

    cands = []
    for m in eligible:
        symbol, price = m["symbol"], m["price"]
        raw = bars_map.get(symbol, [])
        done = completed_bars(raw)
        if not thin_ok(done):
            continue
        if speed(done, price, day_max_volume(symbol)) <= 0:
            continue
        levels = daily_levels(symbol)
        ema_gate = level_gate(price, levels["ema200"])
        high_gate = level_gate(price, levels["prior_high"])
        if ema_gate == "block" or high_gate == "block":     # a real ceiling right overhead - skip this candidate entirely
            continue
        cands.append({"symbol": symbol, "price": price, "raw": raw, "done": done,
                      "dv3": dollar_volume_3(done), "bounce": (ema_gate == "bounce" or high_gate == "bounce"),
                      "news": news_cache.get(symbol) if NEWS_MODE != "off" else None})

    # pass 2: leaders only - the top 3 by 3-minute dollar volume (stocks with fresh news first in "boost" mode)
    if NEWS_MODE == "require":
        cands = [c for c in cands if c["news"]]
    cands.sort(key=lambda c: (bool(c["news"]) if NEWS_MODE == "boost" else False, c["dv3"]), reverse=True)
    leaders = cands[:LEADER_TOP_N]
    if leaders:
        key = "leaders:" + ",".join(sorted(c["symbol"] for c in leaders))
        log_every(key, CYCLE_LOG_SECONDS,
                  f"leaders: {[(c['symbol'], round(c['dv3']), 'NEWS' if c['news'] else '') for c in leaders]}")

    # pass 3: an entry fires from EITHER trigger -
    #   (a) LEADER + volume spike + breakout above the last bar's high, or
    #   (b) the three-candle pullback (any eligible candidate, not leaders-only), or
    #   (c) a BOUNCE off the 200-day EMA or the prior day's high (support being defended)
    # - as long as the current bar is trading green. The probe is sized down when the 4 intraday
    # checks (9/20-EMA, 9-EMA, VWAP, MACD) do not currently favor the trade - they never block it.
    leader_symbols = {c["symbol"] for c in leaders}
    for c in cands:
        if held_count >= MAX_NAMES:
            break
        symbol, price, done, raw = c["symbol"], c["price"], c["done"], c["raw"]
        cur = forming_bar(raw)
        if cur is not None and price <= cur.open:            # the entry bar must be trading green
            continue

        # ENTRY: only a stock genuinely running right now can be bought - the spike
        # breakout or the three-candle pullback. Support/resistance levels (c["bounce"])
        # are NOT a trigger by themselves anymore - they only block (level_gate "block",
        # already applied above) or refine an ALREADY-qualifying entry.
        stop_low = None
        trigger_kind = None
        if symbol in leader_symbols and volume_spike(done) and price > done[-1].high:
            stop_low = min(b.low for b in done[-2:])
            trigger_kind = "spike breakout"
        else:
            pattern = three_candle_pullback(done)
            if pattern is not None and price >= pattern[0]:
                stop_low = pattern[1]
                trigger_kind = "three-candle pullback"
        if stop_low is None:
            continue

        ask, bid = get_spread(symbol)
        if ask is None or bid is None or ask <= 0 or ask - bid > MAX_SPREAD:
            continue
        day_bars = get_day_bars(symbol)
        favorable, checkable = soft_filter_score(done, day_bars, price)
        if checkable < 4 or favorable < checkable:      # ANY unmet or not-yet-available check blocks the entry now
            continue
        size_mult = 1.00
        caution = is_caution_ticker(symbol)
        cap_mult = CAUTION_SIZE_MULT if caution else 1.0
        headline = c["news"][0] if c["news"] else None
        log(f"ENTRY SIGNAL {symbol}: {trigger_kind}, price {price}, stop {stop_low}, "
            f"soft filters {favorable}/{checkable} favorable"
            f"{f', KNOWN REPEAT-FLIER - sized at {cap_mult:.0%}' if caution else ''}, headline: {headline}")
        if place_buy(symbol, ask, stop_low, size_mult, cap_mult):
            held_count += 1


def main_loop(max_iterations=None, now_fn=None, sleep_fn=time.sleep):
    et = ZoneInfo("America/New_York")
    last_universe_refresh = 0
    shortlist = []
    eod_done_date = None
    n = 0
    pass_ms = []               # duration of each entry pass, for the loop-speed log
    while max_iterations is None or n < max_iterations:
        n += 1
        pause = IDLE_SECONDS
        now_et = now_fn() if now_fn else datetime.now(et)
        start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
        eod_time = now_et.replace(hour=19, minute=55, second=0, microsecond=0)

        if not is_trading_day(now_et):
            log(f"not a trading day ({now_et.strftime('%A, %Y-%m-%d')}) - idle")
        elif start <= now_et <= end:
            pause = FAST_CHECK_SECONDS
            try:
                equity_now = get_equity_cached()
                roll_day(now_et, equity_now)
                base = guard["baseline"]
                if base:
                    thr = HALT_THRESHOLDS[min(guard["streak"], 2)]
                    log_every("equity", EQUITY_LOG_SECONDS,
                              f"EQUITY {equity_now:,.2f} (day baseline {base:,.2f}, "
                              f"{100 * (equity_now - base) / base:+.2f}%, halt at -{thr:.1%})")
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
                    t_pass = time.time()
                    run_cycle(fast_scan(shortlist))
                    pass_ms.append((time.time() - t_pass) * 1000)
                    if len(pass_ms) >= 1:
                        log_every("loop_speed", CYCLE_LOG_SECONDS,
                                  f"LOOP SPEED: {len(pass_ms)} passes since the last report, "
                                  f"average {sum(pass_ms) / len(pass_ms):.0f} ms, slowest {max(pass_ms):.0f} ms")
                        if time.time() - _last_logged.get("loop_speed", 0) < 1:
                            pass_ms.clear()
            except Exception as e:
                log(f"main loop error: {e}")
        else:
            log(f"outside trading window (4am-8pm ET), current ET time: {now_et.strftime('%H:%M')}")

        sleep_fn(pause)


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
