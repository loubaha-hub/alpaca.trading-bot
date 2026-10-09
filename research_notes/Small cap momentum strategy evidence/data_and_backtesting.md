# Data and honest backtesting for seconds-scale small-cap rules

Research date: 2026-10-09. How these notes were gathered: direct page fetches (WebFetch, curl) were blocked in this environment (DNS failure or proxy 403 for massive.com, databento.com, docs.alpaca.markets, papers.ssrn.com). Every finding below comes from web-search result text that quotes or summarizes the cited page. Where the search drew on a third-party or secondary page, the finding says so. Prices are "as seen 2026-10-09" in search results, and some of those snapshots are older. Check the vendor's pricing page before buying.

## 1. Where to get tick-level trade and quote (NBBO) history for US small caps, including premarket

### Takeaway
For a bot that acts within seconds, you need historical trades AND NBBO quotes, consolidated across all venues (SIP), covering 4:00-20:00 ET, and including stocks that were later delisted. Three affordable sources come close:
- **Alpaca SIP** ($99/mo; free if you accept a 15-minute lag), which the bot already uses.
- **Massive, formerly Polygon** (Advanced plan, $199/mo; quotes and flat files).
- **Databento** (pay per GB, or plans; the Nasdaq order book back to May 2018).

AlgoSeek is the institutional-grade option and is expensive. Kibot and FirstRate are cheap one-time purchases, but their coverage of premarket and of thin, short-lived tickers is unconfirmed or patchy.

### Cited Findings

**Massive (formerly Polygon.io)**
- **Plans:** Basic (free) has end-of-day data, 5 API calls/min and 2 years of history. Starter is $29/mo with 15-minute-delayed intraday data, unlimited calls and 5 years of history. Developer is $79/mo with 10 years of history, trades and second aggregates, still 15-minute delayed. Advanced is $199/mo: real-time, 20+ years of history, trades, quotes, second aggregates and flat files. Seen 2026-10-09. — [Massive stocks overview](https://massive.com/docs/rest/stocks/overview); [Massive stocks page](https://massive.com/stocks); third-party tier summary at [TradingToolsHub review](https://tradingtoolshub.com/review/polygon-io/)
- **Which plan has quotes:** the search summary tied NBBO quotes to Advanced only. Third-party sources disagree on whether Starter includes second aggregates or trades. — [TradingToolsHub](https://tradingtoolshub.com/review/polygon-io/); [Massive stocks overview](https://massive.com/docs/rest/stocks/overview)
- **Quotes endpoint:** it returns NBBO quotes for a ticker over a time range, with "the prevailing best bid/ask prices, sizes, exchanges, and timestamps". — [Massive Quotes docs](https://massive.com/docs/rest/stocks/trades-quotes/quotes)
- **Extended hours:** "Every extended-hours trade and quote is published, from 04:00 to 20:00 Eastern." There is no session parameter; you pass timestamps. Any Stocks plan includes extended hours: "The tier decides how recent the data can be, not whether extended hours are included." — [Massive KB: pre-market and after-hours](https://massive.com/knowledge-base/article/does-massive-offer-pre-market-and-after-hours-data)
- **Delisted tickers:**
  - The tickers endpoint returns active tickers only unless you ask; pass `active=false` to get delisted ones.
  - For a delisted ticker you can still get bars, trades, quotes, reference data and corporate actions from its trading life.
  - Nothing exists after the last trading day, and no "delisting event" record exists.

  — [Massive KB: delisted tickers](https://massive.com/knowledge-base/article/what-does-massive-do-with-delisted-tickers)
- **Flat files:** daily gzipped CSV files of trades, quotes and minute/day aggregates, downloaded with S3 tools from files.massive.com. They are on paid plans only; a 403 error means either the plan or an unsigned exchange agreement. — [Massive flat files overview](https://massive.com/docs/flat-files/stocks/overview); [Flat files quickstart](https://massive.com/docs/flat-files/quickstart)
- **Data-handling traps:**
  - REST and flat-file timestamps are in nanoseconds; WebSocket timestamps are in milliseconds.
  - Canceled trades stay in REST and flat files, marked with a correction value, and are left out of aggregate bars.

  — [Massive KB: timestamps](https://massive.com/knowledge-base/article/which-timestamps-are-returned-for-massives-stock-trades-and-nbbo-quotes)

**Databento**
- **Pay-per-use history:** historical data is billed per GB, "starting at $0.40/GB". The age of this figure is unclear. — [Databento equities page](https://databento.com/equities); [Databento usage-based pricing KB](https://docs.databento.com/knowledge-base/new-users/usage-based-pricing-and-data-credits)
- **January 2025 change:** live data was no longer sold on usage-based pricing and now needs a subscription. A new Standard plan cost $199/mo and included 7 years of OHLCV bars, 12 months of L0/L1 (trades and top-of-book quotes), and 1 month of L2 (MBP-10) and L3 (MBO) history. — [Databento blog, Jan 2025 pricing changes](https://databento.com/blog/upcoming-changes-to-pricing-plans-in-january-2025)
- **Plus plan:** a Databento post says the Plus plan price "will increase to $1,500/month". The search did not show which post or what date. — [Databento: Introducing US Equities](https://databento.com/blog/introducing-databento-us-equities)
- **Unverified 2026 figure:** one third-party comparison says a "June 2026 pricing update lists US Equities at $4,000/month", without naming the tier. I could not confirm it. — [FXMacroData vs Databento](https://fxmacrodata.com/articles/fxmacrodata-vs-databento)
- **Nasdaq TotalView-ITCH (XNAS.ITCH):** coverage starts 2018-05-01, with full order-by-order (MBO) and trade-plus-best-quote (TBBO) data. History is "continuously available on a T+1 basis". — [XNAS.ITCH dataset page](https://databento.com/datasets/XNAS.ITCH); [Databento blog: TotalView live](https://databento.com/blog/nasdaq-totalview-live)
- **Databento US Equities bundle:** marketed as having "zero license fees". Cboe EDGX depth has since been added. — [PR Newswire](https://www.prnewswire.com/news-releases/databento-launches-the-industrys-first-us-equities-bundle-with-zero-license-fees-301960067.html); [Databento blog: EDGX depth](https://databento.com/blog/real-time-cboe-edgx-depth-now-available-on-databento-us-equities)
- **Example cost:** one Hacker News user's cost-tool check showed a year of daily OHLCV for all symbols costing about $4.38 (EQUS.SUMMARY). That is anecdotal, and it covers daily bars, not ticks. — [Hacker News comment](https://news.ycombinator.com/item?id=45516154)

**Alpaca (the bot's current broker and data feed)**
- **Plans:** Algo Trader Plus is $99/mo with real-time data from all US exchanges (SIP). Both plans have history since 2016. Historical API limits are 10,000 calls/min (Plus) versus 200/min (Basic). Basic's only historical limit is that the latest 15 minutes are blocked. — [Alpaca: About Market Data API](https://docs.alpaca.markets/us/docs/about-market-data-api); [Alpaca Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
- **Tick-level history:** historical trades and quotes endpoints exist alongside bars. Alpaca recommends always setting `feed=sip` explicitly. — [Alpaca: Historical Stock Data](https://docs.alpaca.markets/us/docs/historical-stock-data-1); [Alpaca Learn: fetch historical data](https://alpaca.markets/learn/fetch-historical-data)
- **IEX feed:** an Alpaca staff forum answer says IEX data is "correct but incomplete" and should generally not drive live trading decisions. — [Alpaca forum: IEX or SIP](https://forum.alpaca.markets/t/iex-or-sip-with-a-free-account/17141)
- **How small IEX's share is:**
  - Cboe's market-share table for 2025-07-01 shows IEX at 3.08% of consolidated US equity volume (5-day average 2.54%), with 51.82% traded off-exchange (FINRA/TRF).
  - A later, undated Cboe snapshot shows IEX at 4.37%.

  — [Cboe volume summary 2025-07-01](https://www.cboe.com/us/equities/market_statistics/market/2025-07-01); [Cboe market statistics](https://www.cboe.com/us/equities/market_statistics)
- **Overnight feed:** Alpaca also offers a derived "overnight" feed (Blue Ocean ATS). It is described as cheaper and less accurate, with trades delayed 15 minutes and adjusted to the bid-ask spread. — [Alpaca Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)

**AlgoSeek**
- **Coverage:** full SIP feed (all trades and quotes from every exchange plus FINRA), collected at co-located servers. It covers every listed US equity since 2007, including delisted ones. One identifier (ASID) follows a security through ticker changes. — [AlgoSeek US Equities](https://algoseek.com/equity/)
- **Via QuantConnect:** QuantConnect hosts AlgoSeek US equities, "survivorship bias-free". Per that listing, OTC trades are not included. — [QuantConnect: AlgoSeek US Equities](https://www.quantconnect.com/data/algoseek-us-equities)
- **Pricing:** third-party estimates only: "rented ... from $1,500 a month" ([StockMarketStack](https://stockmarketstack.com/tools/tickdata)); Quantpedia rates it "$$$ (5k-10k)" ([Quantpedia tools list](https://quantpedia.com/links-tools/?category=historical-data)). No official price was found.

**Kibot**
- **Coverage:** all-stocks tick data for 18,000+ listed and delisted symbols since 2009. Tick data with bid/ask starts September 2009; minute data starts 1998-01-02. — [Kibot all-stocks tick data](https://www.kibot.com/historical-data/all-stocks-tick-data.html); [Kibot FAQ](https://www.kibot.com/faq.html)
- **Delisted gaps:** the FAQ says delisted coverage depends on liquidity at delisting, so "very thinly traded names and short-lived shell tickers are often not in the historical archive". This matters for low-float gappers. — [Kibot FAQ](https://www.kibot.com/faq.html)
- **Pricing:** two Kibot pages conflict: $5,940 one-time (tick) versus $9,000 one-time (tick plus bid/ask). — [Kibot tick](https://www.kibot.com/historical-data/all-stocks-tick-data.html); [Kibot tick + bid/ask](https://www.kibot.com/historical-data/all-stocks-tick-and-bid-ask-data.html); [Kibot buy page](https://www.kibot.com/buy.html)

**FirstRate Data**
- **Coverage:** 1-minute and longer bars for 16,314 tickers, including over 7,000 delisted, from January 2000. — [FirstRate Data home](https://firstratedata.com/)
- **Tick pricing:** $49.95 per US stock ticker. — [FirstRate tick pricing](https://firstratedata.com/a/2/tick-data-pricing)
- **Bundle:** a third-party listing puts the intraday bundle at $299-$399 one-time. — [NexusFi](https://nexusfi.com/d/data-providers/firstrate-data/); [FirstRate bundles](https://firstratedata.com/bundle/all)

### Inferences
- **Cheapest path that fits the bot:** the bot already runs on Alpaca SIP, so Alpaca's own historical SIP trades and quotes are the natural first source. Using the same vendor and the same consolidated feed in both replay and live removes one source of mismatch between backtest and live. The free plan's only historical limit is the last 15 minutes, which does not matter for backtests.
- **Never use IEX-only data for small caps.** IEX carries roughly 3-4% of consolidated volume, so an IEX-only replay would show wrong prints, wrong volume and a wrong best bid/ask.
- **Massive Advanced ($199/mo)** is the simplest bulk alternative. Its flat files give whole-market trades and NBBO quotes per day, 4:00-20:00, delisted tickers included.
- **Databento** gives the deepest view (the Nasdaq order book from 2018-05-01), but the Nasdaq book is one venue only. Plan prices appear to have changed several times; confirm them before buying.
- **Kibot and FirstRate** look poor for low-float gappers: thin and shell tickers are missing (Kibot says so), premarket coverage is unconfirmed, and FirstRate charges per ticker for ticks.

### Gaps
- No vendor pricing page could be opened directly; all prices come from search text and may be stale (Databento especially).
- I found no source confirming premarket coverage for AlgoSeek, Kibot or FirstRate.
- I found no source confirming that Alpaca's historical SIP trades and quotes include 4:00-9:30 premarket. Background knowledge (unverified here) says they do; check with one API call for a known premarket mover.
- Alpaca's exact historical trade/quote rate limits and the per-request page size for quotes were not confirmed.
- **IEX Cloud alternatives:** I retrieved no source. Background knowledge, unverified here: IEX Cloud shut down in 2024, so it is no longer an option.
- **Nasdaq TotalView direct from Nasdaq:** not researched beyond Databento's resale.

## 2. Why 1-minute-bar backtests mislead for seconds-scale rules, and what a tick replay needs

### Takeaway
A 1-minute bar shows four prices and hides the order they came in. So any rule whose stop and target can both be hit inside one minute, or whose entry depends on a seconds-level trigger, gets a guessed result. Bars also hide the bid-ask spread, the size available at the quote, the queue, halts and canceled prints. An honest replay feeds every trade and NBBO quote in time order and buys at the ask, sells at the bid. It also adds a delay between signal and fill, caps fills at the displayed size, and handles partial fills and halts.

### Cited Findings
- **Bars can't show which level traded first:** OHLC "cannot reveal intrabar ordering", so one simulator adopts "a conservative stop-first assumption". The same fix documents a related bug: a trade whose next bar crossed both its +7% target and its stop could be wrongly recorded as a later +2% exit. — [GitHub PR, tonycccccc/Quant #1](https://github.com/tonycccccc/Quant/pull/1)
- **Stop-first is a common default:** another engine counts a bar that touches both levels as a stop. — [trading_core PR #61](https://github.com/semdinsp/trading_core/pull/61)
- **Gaps at the open:** if a bar opens beyond the target, the fill is at the open, before any intrabar stop. — [librae issue #269](https://github.com/awwesomeman/librae/issues/269)
- **The outcome depends on the price path:** same bar, opposite results. A path 100 → 111 → 94 exits at the target (110); a path 100 → 94 → 111 exits at the stop (94). Only tick data can tell them apart. — [q_backend issue #39](https://github.com/GuilhermeFortuna/q_backend/issues/39); [q_core issue #14](https://github.com/GuilhermeFortuna/q_core/issues/14)
- **Real-world reports:** QuantConnect users report backtests executing both the stop and the target on the same trade. — [QuantConnect forum](https://www.quantconnect.com/forum/discussion/8190/the-backtesting-executes-both-the-stop-loss-and-the-take-profit-on-the-same-trade/)
- **"Bar magnifier" fix:** MultiCharts can replay a bar from ticks, seconds or minutes to see "how the price bar was formed and which of these orders was executed first". — [TradingCode on MultiCharts intrabar orders](https://www.tradingcode.net/multicharts/attributes/intrabarordergeneration/); see also [Medium: the intrabar accuracy problem](https://medium.com/@kojott/why-your-trading-backtests-might-lying-to-you-the-intrabar-accuracy-problem-68f8b7decdb3)
- **VectorBT Pro's assumption:** it treats the timing of most events as unknown, somewhere between the bar's open (best case) and close (worst case). — [PyQuant News: intraday backtesting with VectorBT Pro](https://www.pyquantnews.com/the-pyquant-newsletter/intraday-backtesting-with-vectorbt-pro)
- **What bar-level logic leaves out:** filling at the next bar's open or close "ignores intra-bar price moves, bid-ask spreads, and partial fills". Trailing stops based on intrabar highs and lows cannot be done accurately when each bar is one event. — [IBKR Campus: vector vs event-based backtesting](https://www.interactivebrokers.com/campus/ibkr-quant-news/a-practical-breakdown-of-vector-based-vs-event-based-backtesting/)
- **Premarket trades and quotes (LEAN docs):**
  - Pre- and post-market trades carry "Form T" condition codes, and liquidity "may be constrained ... resulting in wide bid-ask spreads".
  - Quotes can be flagged "suspicious" (far from other prices), and LEAN's quote bars drop them.

  — [QuantConnect: core data types](https://www.quantconnect.com/docs/v2/lean-engine/data-format/core-data-types)
- **Canceled and corrected trades:** they are kept in tick data but excluded from aggregate bars (Massive). A tick replay must apply corrections itself. — [Massive KB: timestamps and corrections](https://massive.com/knowledge-base/article/which-timestamps-are-returned-for-massives-stock-trades-and-nbbo-quotes)
- **What an event-driven simulator models (NautilusTrader):**
  - Replay of quote ticks, trade ticks, bars and order books at nanosecond resolution.
  - A FillModel with a "chance of filling a limit order when price touches it" and a "chance of one-tick slippage".
  - Optional "liquidity consumption", so fills use up the size available at a price.
  - Queue-position tracking, which "tracks the quantity ahead of a limit order at placement time" and needs trade data plus L2/L3 depth.
  - A static latency model that adds delays to order insert, update and cancel. Its values are assumptions to be calibrated from measurements.

  — [NautilusTrader backtesting docs](https://nautilustrader.io/docs/latest/concepts/backtesting/); [DeepWiki: Nautilus backtesting best practices](https://deepwiki.com/nautechsystems/nautilus_trader/6.6-backtesting-best-practices) (unofficial)
- **What even good simulators cannot see:** the official Nautilus docs note that queue tracking cannot observe how the simulated order itself would have changed the market (its counterfactual impact). — [NautilusTrader backtesting docs](https://nautilustrader.io/docs/latest/concepts/backtesting/)
- **How Alpaca's paper account fills:**
  - Paper trading fills against real-time NBBO quotes.
  - Order size is not checked against the size shown at the quote.
  - Queue position for resting limit orders is not tracked.
  - Partial fills are random, 10% of the time.
  - Market impact is not simulated.

  — [TradersPost: Alpaca paper trading, what the docs omit](https://blog.traderspost.io/article/alpaca-paper-trading)

### Inferences
- **The repo's replay has the same blind spots.** `replay/replay.py` runs on recorded 1-minute bars with invented fills and spreads, and the journal already says it is "kinder than the live market". Any rule that fires and exits within the same minute is effectively unjudgeable in it. The result depends on the stop-first versus target-first convention, not on the market.
- **Cheap diagnostic, before buying any data:**
  1. Count how many replayed trades have both stop and target (or entry and stop) inside one bar.
  2. Rerun the replay stop-first and then target-first.
  3. If the totals differ materially, the bar replay cannot judge that rule.
- **Minimum honest tick replay for this bot:**
  - Merge SIP trades and NBBO quotes into one time-ordered stream.
  - Trigger on the same events the live code sees.
  - Fill marketable buys at the ask and sells at the bid at signal time plus a measured delay (from the bot's own live logs: signal time vs. fill time).
  - Cap a fill at the displayed size, with the rest partial or unfilled.
  - Fill a resting limit only when price trades through it, not when it merely touches.
  - Never fill during an LULD halt. Reopen at the first post-halt quote.
  - Apply trade corrections and cancels.
  - Treat premarket spreads as wide by default.
- **Calibration:** check the tick replay against the bot's own live fills (Render logs saved in `replay/live/`). Per the owner's rule, live results outrank replays; the tick replay is a tool to rank rule ideas, not proof.

### Gaps
- I found no published study that measures, for small caps specifically, how far 1-minute-bar results differ from tick-replay results. The size of the bias has to be measured on the bot's own trades.
- I found no source on how vendors mark LULD halts in historical tick data (trading-status messages). That needs checking per vendor.
- Alpaca's official paper-trading page was not retrieved; the paper-fill details come from a third-party blog quoting it.

## 3. Tools and frameworks for event-driven tick backtesting (quotes, extended hours)

### Takeaway
- **NautilusTrader:** the strongest open-source fit for quote-aware, seconds-scale simulation, with a Databento adapter.
- **QuantConnect/LEAN:** handles tick trades and quotes with extended hours via AlgoSeek data, but the strategy has to be rewritten in its framework.
- **Backtrader, Zipline-reloaded and vectorbt:** essentially bar tools. Spreads are user-assumed, and quote and queue handling is weak or manual.
- **Lumibot:** little documentation found on tick or quote backtesting.

### Cited Findings
- **NautilusTrader: what it replays:** historical quote ticks, trade ticks, bars and order books at nanosecond resolution, across many venues and instruments in one run. — [NautilusTrader backtesting docs](https://nautilustrader.io/docs/latest/concepts/backtesting/); [GitHub: nautilus_trader](https://github.com/nautechsystems/nautilus_trader)
- **NautilusTrader: Databento adapter:**
  - It reads Databento files into Nautilus objects: L3 (MBO), L2 (MBP-10) and top-of-book quotes.
  - The docs recommend converting the files once into the Parquet catalog for faster repeat backtests.
  - The adapter has no execution client.
  - Imbalance and statistics data do not stream through the backtest engine.

  — [Nautilus Databento integration docs](https://nautilustrader.io/docs/latest/integrations/databento/); [GitHub docs/integrations/databento.md](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/integrations/databento.md)
- **NautilusTrader: recent bug:** a regression in 2.0.0rc6 filled twice the trade size when liquidity consumption plus a 50 ms latency model were on and an order was sent from `on_order_filled`. Pin and test versions. — [GitHub issue #5262](https://github.com/nautechsystems/nautilus_trader/issues/5262)
- **LEAN: extended hours are opt-in:** off by default; enabled with `AddEquity("SPY", extendedMarketHours: true)`. Extended-hours data only comes with minute, second or tick subscriptions; daily and hourly bars show regular hours only. — [QuantConnect: requesting US equity data](https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/us-equity/requesting-data); [QuantConnect: market hours](https://www.quantconnect.com/docs/v2/writing-algorithms/securities/market-hours)
- **LEAN: tick data:** tick resolution has both trade and quote ticks, split into trade and quote files by date. US equity data comes from AlgoSeek (trades and quotes after 2007) and QuantQuote (trades before 2007), so quotes exist only after 2007. — [LEAN Data/equity readme](https://github.com/QuantConnect/Lean/blob/master/Data/equity/readme.md); [QuantConnect: core data types](https://www.quantconnect.com/docs/v2/lean-engine/data-format/core-data-types)
- **Backtrader:**
  - Event-driven, processing data bar by bar or tick by tick.
  - Its broker applies a bid-ask spread the user specifies, not real quotes.
  - Last PyPI release reported as April 2023 (stable but unmaintained).

  — [quantrading.space comparison](https://quantrading.space/post.php?slug=backtesting-frameworks-python); [Pickuma benchmark](https://pickuma.com/for-dev/python-backtesting-frameworks-backtrader-vectorbt-zipline-2026/) (secondary blogs)
- **Zipline-reloaded:** described as "equity/daily-oriented, awkward for crypto or fine intraday". Data must first be loaded into its bundle format. — [Pickuma](https://pickuma.com/for-dev/python-backtesting-frameworks-backtrader-vectorbt-zipline-2026/); [waylandz framework comparison](https://waylandz.com/quant-book-en/Quant-Framework-Comparison/) (secondary)
- **vectorbt:**
  - Its maintainer says it "doesn't actually do any vectorized backtesting - it follows a sequential approach".
  - Tick data is possible but memory-heavy: 30 million points take about 200 MB per column, and order records can exhaust RAM.
  - The user must supply correct trade information at each tick; "flexible" simulation mode is the event-style option.
  - By default it does not model partial fills, slippage or queuing well.

  — [vectorbt discussion #274 (tick data)](https://github.com/polakowo/vectorbt/discussions/274); [vectorbt discussion #185 (accuracy vs event-driven)](https://github.com/polakowo/vectorbt/discussions/185); [QuantVPS vectorbt guide](https://www.quantvps.com/blog/vectorbt-essential-guide-for-quant-traders)
- **Lumibot:** listed as supporting live trading of stocks, options, futures and crypto from one codebase. No information was found on tick or quote backtesting. — [QuantVPS library comparison](https://www.quantvps.com/blog/best-python-backtesting-libraries-for-trading)
- **Common pattern:** use a fast vectorized tool for research and an event-driven or order-book tool for realism; Nautilus or a custom L2 simulator for microstructure work. — [Bullalert: NautilusTrader vs Backtrader vs VectorBT](https://bullalert.ai/blog/best-python-backtest-engines-2026/) (secondary)

### Inferences
- **Every framework means a rewrite.** The bot's rules live in `r34.py` (v31 base class, V34/V35 subclasses). Moving to Nautilus or LEAN means re-coding the rules there, and that creates a second copy of the rules that can drift from the live code.
- **The lowest-risk option keeps the live code.** The repo's existing replay already drives the live strategy code. Upgrading it to feed the same code a merged trades-plus-quotes stream, with the fill rules from section 2, keeps one copy of the strategy.
- **Nautilus is still worth it as a cross-check** for a few days, to calibrate the home-made fill logic.
- **Backtrader, Zipline and vectorbt** add little for seconds-scale small-cap rules, because spreads and fills would still be assumptions.

### Gaps
- Lumibot's backtesting data sources and quote handling were not found.
- Zipline-reloaded's minute or tick quote support was not confirmed from its own docs.
- No head-to-head study compares framework fill realism against live small-cap fills.

## 4. Methods to avoid overfitting: out-of-sample, walk-forward, deflated Sharpe, PBO, multiple testing, paper-to-live gaps

### Takeaway
Every extra rule, threshold or variant tried raises the odds that the "best" version won by luck. The honest defenses:
- Decide the rule in words before testing.
- Keep the number of variants tried small, and log all of them.
- Freeze the rule and test it on days never looked at, walking forward through time.
- Demand stronger evidence when many variants were tried (t of about 3 rather than 2; the deflated Sharpe ratio).
- Measure how often the in-sample winner falls below the middle of the pack out of sample (the probability of backtest overfitting).
- Treat paper and replay results as optimistic until live fills confirm them.

### Cited Findings
- **Probability of backtest overfitting (PBO):** Bailey, Borwein, López de Prado and Zhu argue that standard guards such as a hold-out test "tend to be unreliable and inaccurate in the context of investment backtests". They propose combinatorially symmetric cross-validation (CSCV), which splits the history into blocks and tries every train/test assignment to estimate how often the best in-sample setting does worse than the median out of sample. The paper is in the Journal of Computational Finance. — [SSRN 2326253](https://papers.ssrn.com/abstract=2326253); [Risk.net / J. Computational Finance](https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting); [eScholarship PDF](https://escholarship.org/content/qt4w1110bb/qt4w1110bb.pdf)
- **PBO in software:** the R package `pbo` implements CSCV/PBO. — [CRAN pbo README](https://packages.oit.ncsu.edu/cran/web/packages/pbo/readme/README.html); [pbo vignette](https://ftp.fau.de/cran/web/packages/pbo/vignettes/pbo.html)
- **Deflated Sharpe ratio (DSR):** Bailey and López de Prado (2014), Journal of Portfolio Management 40(5), pp. 94-107. It corrects a Sharpe ratio for "selection bias under multiple testing and non-normally distributed returns". — [SSRN 2460551](https://papers.ssrn.com/abstract=2460551). Online calculator: [daru.finance DSR calculator](https://daru.finance/projects/deflated-sharpe)
- **Minimum track record length (MinTRL):** Bailey and López de Prado (2012, "The Sharpe Ratio Efficient Frontier") ask how long a record must be before you can be confident the Sharpe ratio beats a threshold.
  - Formula: MinTRL = 1 + (1 − γ3·SR + ((γ4 − 1)/4)·SR²)·(Φ⁻¹(1−α)/SR)². SR is the per-period Sharpe ratio, γ3 is skew, γ4 is kurtosis.
  - Negative skew and fat tails lengthen the required record.
  - Worked example: an annual Sharpe of 2 versus a benchmark of 1 needs about 2.7 years of daily data.

  — [PortfolioOptimizer blog on PSR and MinTRL](https://portfoliooptimizer.io/blog/the-probabilistic-sharpe-ratio-bias-adjustment-confidence-intervals-hypothesis-testing-and-minimum-track-record-length/); [ResearchGate: The Sharpe ratio efficient frontier](https://www.researchgate.net/publication/308231636_The_Sharpe_ratio_efficient_frontier); [López de Prado slides](http://boston.qwafafew.org/wp-content/uploads/sites/4/2017/01/Lopez_de_Prado_Sharpe.pdf)
- **Minimum backtest length:** with a fixed amount of data, trying enough settings can always produce any target performance.
  - With 5 years of daily data, trying 45 or more independent variations makes it likely that the best one shows a Sharpe ratio of 1.0 or more by chance.
  - With 2 years of data, no more than about 7 variations should be tried.
  - The derivation assumes independent trials, so it is conservative for correlated variants.

  — [Stefan Jansen, ML for Trading: minimum backtest length and deflated SR](https://stefan-jansen.github.io/machine-learning-for-trading/08_ml4t_workflow/01_multiple_testing/); [Bailey et al., Statistical Overfitting and Backtest Performance (PDF)](https://sdm.lbl.gov/oapapers/ssrn-id2507040-bailey.pdf); [Bailey & Borwein, Backtest overfitting in financial markets (PDF)](https://www.davidhbailey.com/dhbpapers/overfit-tools-at.pdf)
- **Multiple testing (Harvey, Liu & Zhu):** because of extensive data mining, a new finding should clear t > 3.0, not the usual 2.0. The authors argue "most claimed research findings in financial economics are likely false". Published in Review of Financial Studies 29(1): 5-68. — [NBER w20592](https://nber.org/papers/w20592); [SSRN 2513152](https://papers.ssrn.com/abstract=2513152)
- **Walk-forward analysis (Pardo):** optimize on one window, freeze the settings, test on the next unseen segment, step forward, and join the out-of-sample segments into one equity curve.
  - Anchored windows (growing) favor stability; rolling windows (fixed length) favor adapting, and the rolling version is "appropriate for short-term trading".
  - Window lengths can themselves be tuned until a test passes.
  - Settings that wander wildly from window to window suggest the optimizer is chasing noise.

  — [LuxAlgo: walk-forward analysis](https://www.luxalgo.com/library/concept/walk-forward-analysis/) (secondary); [Algo Advantage podcast with Bob Pardo](https://algoadvantage.substack.com/p/035-bob-pardo-ii-building-trading); [quantstrat walk.forward](https://rdrr.io/github/braverock/quantstrat/man/walk.forward.html)
- **Combinatorial purged cross-validation (CPCV):** from López de Prado, Advances in Financial Machine Learning (2018), chapter 7. It produces many out-of-sample paths rather than walk-forward's single path, which gives a spread of out-of-sample results. — [fynance CPCV docs](https://fynance.readthedocs.io/en/latest/generated/fynance.data.combinatorial_purged_cv.html); [TradingStrategy.ai backtesting methodology](https://tradingstrategy.ai/docs/learn/backtesting.html)
- **Paper-to-live gap (Alpaca):**
  - An Alpaca forum answer says paper and live are "meant to be equivalent" but slippage in paper "is not entirely reflective of what might occur live".
  - Alpaca's learning material calls paper fills "idealized ... with no slippage or spread".
  - A third-party guide says the gap is widest "on exactly the low float names day traders target".

  — [Alpaca forum: slippage paper vs real](https://forum.alpaca.markets/t/slippage-paper-trading-vs-real-trading/2801); [Alpaca Learn: paper vs live](https://alpaca.markets/learn/paper-trading-vs-live-trading-a-data-backed-guide-on-when-to-start-trading-real-money); [TradersPost broker paper-trading comparison](https://blog.traderspost.io/article/broker-paper-trading-comparison); [Xeanvi Alpaca paper guide](https://xeanvi.com/blog/alpaca-paper-trading-guide)

### Inferences
- **The research backs the owner's rules** "No overfitting, no contradictions" and "test on days that were not used to design it". The Bailey et al. minimum-backtest-length result means each new threshold or filter tried on the same recorded days uses up evidence.
- **Practical log:** keep a dated list of every variant tried, including rejected ones. That count is the "number of trials" that the deflated Sharpe ratio and the t of about 3 depend on.
- **Day-level walk-forward:**
  1. Design on days 1-N.
  2. Freeze the rule in words (per `memory/checklist.md`).
  3. Test on the next block of days never looked at.
  4. Report gains, costs and trade counts per block.
- **Count days, not just trades:** small-cap gapper trades on the same day share one market mood, so trades are not independent. Judge both per entry (the owner's standard) and per day.
- **The "both sides" check** (losers removed vs. good moves blocked) is a form of out-of-sample comparison. It should be run on held-out days, not the days the filter was designed on.

### Gaps
- PBO and DSR were designed for return series and Sharpe ratios. I found no source applying them specifically to sparse intraday small-cap trade lists. Using per-day P&L as the "returns" is a reasonable adaptation, but it was not found in the literature.
- No figures were found for the typical paper-vs-live slippage on low-float premarket names; the bot's own live logs are the only reliable measure.

## 5. How many trades or days are needed to tell a real edge from noise (35-45% win rate, 2:1 payoff)

### Takeaway
At a 2:1 payoff the break-even win rate is 33.3%, so a 35-45% win rate is a thin edge of 0.05R to 0.35R per trade on a 1R risk. Roughly:
- A 40% win rate needs about 200 independent trades to reach the usual significance (t of about 2) and about 500 to reach the stricter t = 3 that applies once many variants have been tried.
- At 35%, it would take thousands of trades.
- Costs of 0.1R per trade (spread plus slippage) quadruple the trades needed at 40%, and wipe out the edge entirely at 35%.
- 100 trades pins the win rate down only to about ±10 percentage points.

### Cited Findings
- **Thresholds the counts are built on:**
  - Harvey, Liu & Zhu: once many specifications are tried, the significance hurdle should be t > 3.0, not 2.0. — [NBER w20592](https://nber.org/papers/w20592)
  - MinTRL: the number of observations needed grows with (Φ⁻¹(1−α)/SR)², so it rises with the square of 1/edge; skew and fat tails raise it further. — [PortfolioOptimizer blog on MinTRL](https://portfoliooptimizer.io/blog/the-probabilistic-sharpe-ratio-bias-adjustment-confidence-intervals-hypothesis-testing-and-minimum-track-record-length/)
- **My own calculation** (method: the t-statistic of mean trade P&L, n = (z × standard deviation / expectancy)²). It assumes independent trades that end at exactly +2R or −1R; costs are taken off both outcomes. No outside source; the arithmetic is reproducible.

| Win rate | Cost per trade | Expectancy per trade | Std dev per trade | Trades for t = 1.96 | Trades for t = 3 |
|---|---|---|---|---|---|
| 35% | 0 | +0.05R | 1.43R | ~3,150 | ~7,400 |
| 35% | 0.1R | −0.05R (no edge) | — | — | — |
| 40% | 0 | +0.20R | 1.47R | ~210 | ~490 |
| 40% | 0.1R | +0.10R | 1.47R | ~830 | ~1,940 |
| 45% | 0 | +0.35R | 1.49R | ~70 | ~165 |
| 45% | 0.1R | +0.25R | 1.49R | ~140 | ~320 |

- **How precisely a measured win rate is known** (true rate about 40%, my calculation, normal approximation):

| Trades | 95% range around the measured win rate |
|---|---|
| 50 | ±13.6 points |
| 100 | ±9.6 points |
| 200 | ±6.8 points |
| 400 | ±4.8 points |
| 1,000 | ±3.0 points |

### Inferences
- **What 100 trades can and can't show:** with 100 trades and a measured 40% win rate, the true rate could plausibly be anywhere from about 30% to 50%. That spans "losing after costs" to "strong edge". A few dozen trades cannot confirm a 2:1 strategy.
- **Comparing two rule versions** (old exit vs. new exit) needs more trades than proving one has an edge, unless both are run on the same signals (paired comparison). Replaying both versions on the same tick data is the cheapest way to get that pairing.
- **Trade count must include variants tried:** if 10 variants were tried, the bar is about t = 3 or a deflated Sharpe ratio, so the ~490-trade figure at 40% is the honest target, not ~210.
- **Converting to days** (illustrative only; the trades-per-day figure is assumed, not measured): at about 4 qualifying trades per day per account, ~210 trades is about 50 trading days and ~490 trades is about 120 trading days. Pooling the three accounts helps only when they run the same rule.
- **Real small-cap trades are messier than +2R/−1R.** Runners give occasional large wins and halts or gaps give larger-than-1R losses, so the spread of results is wider than modeled. That raises the counts above (consistent with the MinTRL finding that fat tails lengthen the required record).
- **Costs decide everything at these edges.** A 0.1R spread-plus-slippage cost is plausible for premarket low-float names; it would turn a 35% win-rate strategy from a small winner into a loser. This is why quote-aware fills (section 2) matter more than any other backtest improvement.

### Gaps
- I found no published source giving trade-count requirements specifically for 35-45% win-rate, 2:1 day-trading systems. The figures above are my own standard-statistics calculation and should be read as orders of magnitude.
- The bot's actual per-trade spread of results, correlation between trades on the same day, and real cost per trade in R were not measured here. They should be computed from the live logs and plugged into the same formula.
