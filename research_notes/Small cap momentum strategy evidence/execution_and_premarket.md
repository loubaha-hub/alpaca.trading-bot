# Execution quality and trading costs for low-priced, volatile US small caps: premarket (4:00-9:30 ET) vs regular hours

*How these notes were made (2026-10-09): the sandbox's network policy blocked direct page fetches (docs.alpaca.markets, sec.gov, nasdaq.com, alpaca.markets all refused), so every external finding below comes from web-search result summaries of the cited pages, not from reading the full papers or PDFs. Exact figures should be checked against the originals before they are quoted as final. Where a number comes from a secondary or low-quality source, it says so. Findings from this repository's own trading log are cited to `memory/journal.md`; note that those "live" results are Alpaca **paper** fills on live market data.*

## 1. Premarket vs regular-hours liquidity: spreads, depth, volatility, price discovery

### Takeaway
Every measured study finds outside-regular-hours trading costs are a multiple of daytime costs: quoted and effective spreads about 3-4x wider, and price impact about 3-6x larger. The causes are fewer trades, more informed traders per trade (adverse selection) and fewer market makers. Premarket now carries a large and growing share of off-hours volume, and sub-dollar stocks have become a big part of premarket volume. However, no study found here measures premarket spreads or depth specifically for low-priced small caps. The academic numbers come from 1999-2000 Nasdaq data or from the overnight session.

### Cited Findings
**Academic: the classic after-hours studies (Nasdaq, 1999-2000 data, before decimal prices)**
- Barclay & Hendershott (2003, *Review of Financial Studies*) find that low after-hours volume still produces "significant, albeit inefficient, price discovery". Liquidity (non-informed) trading is what makes daytime price discovery efficient. — [IDEAS/RePEc abstract](https://ideas.repec.org/a/oup/rfinst/v16y2003i4p1041-1073.html); [author PDF](https://faculty.haas.berkeley.edu/hender/after_hours_price_discovery.pdf)
- In the same paper, individual pre-open trades carry more information than daytime trades. Before the open, price changes are larger, reflect more private information and are less noisy than after the close. Only about 4% of Nasdaq volume traded after hours in their sample. — [summary page](https://academicnewsletter.sufe.edu.cn/info/355647); [IDEAS](https://ideas.repec.org/a/oup/rfinst/v16y2003i4p1041-1073.html)
- A later summary of this work: the pre-open has the most price discovery per trade, and the probability of informed trading (PIN) is "much higher during the preopen than during the trading session". — [Barclay & Hendershott PDF, as summarized in search](https://faculty.haas.berkeley.edu/hender/after_hours_price_discovery.pdf)
- Barclay & Hendershott (2004, *Journal of Finance*, "Liquidity externalities and adverse selection: evidence from trading after hours"):
  - after hours there are less than 1/20 as many trades per unit of time as during the day;
  - quoted and effective spreads are 3-4 times larger;
  - the authors attribute this to greater adverse selection and order persistence, not to higher dealer profits.
  — [summary page](https://academicnewsletter.sufe.edu.cn/info/361191); [Wikipedia: Extended-hours trading](https://en.wikipedia.org/wiki/Extended-hours_trading)
- A Nasdaq research article cites Barclay & Hendershott (2003) as finding extended-hours (4 p.m.-9:30 a.m.) trading costs 4-5 times regular hours. This conflicts slightly with the 3-4x spread figure in the 2004 paper; the multiple depends on the measure. — [Nasdaq, "Looking all day: data on 24-hour trading"](https://www.nasdaq.com/articles/looking-all-day-data-24-hour-trading)
- A 2000 press report on the same research (1999 data): for the 250 most-traded Nasdaq stocks, the spread was about 0.48% in the day session and close to 50 cents on a $50 stock (about 1%) after hours. These figures are historical only. — [Deseret News, 2000](https://www.deseret.com/2000/2/13/19490661/after-hours-trading-can-be-costly/)

**Academic: newer work (overnight session, 2024-2025)**
- Eaton, Shkilko & Werner, "Nocturnal Trading" (working paper, 2025) covers 8 p.m.-4 a.m. trading in US stocks and ETPs:
  - effective spreads at night are worse than in regular hours, but realized spreads (the liquidity provider's profit) are "about the same or better";
  - price impacts are "at least three to four times greater" than in regular hours, partly driven by large positive (buy-side) order imbalances;
  - activity is dominated by a single trading platform, with liquidity supplied by only two market makers.
  — [SSRN 5181159](https://ssrn.com/abstract=5181159); [AFA program copy](https://afajof.org/management/viewp.php?n=162176); [U. Tennessee copy](https://haslam.utk.edu/wp-content/uploads/2024/11/Eaton-Paper.pdf)
- Nasdaq's summary of the same research puts effective spreads on retail orders at about 3 times regular hours and price impact at about 6 times. The summary adds that daytime protections (the Order Protection Rule, Rule 605 execution-quality reports, competition) "are not in force during extended hours". This 6x conflicts with the paper's own "at least 3-4x", and versions of the paper differ. — [Nasdaq](https://www.nasdaq.com/articles/looking-all-day-data-24-hour-trading); compare [AFA version](https://afajof.org/management/viewp.php?n=162176)

**Regulator and exchange data**
- The SEC investor bulletin says there is generally "less trading interest and less price competition" after hours, which may raise trading costs, and that there may be no market makers actively making markets in most stocks. — [SEC Investor Bulletin: After-Hours Trading](https://www.sec.gov/files/afterhourtrading.pdf)
- NYSE extended-hours volume figures:
  - extended hours were over 11% of all US equity trading (over 1.7 billion shares a day) as of January 2025, up from just over 5% in Q1 2019;
  - Q2 2025 set records: over 2 billion shares and $62 billion a day, 11.5% of all US equity trading;
  - premarket was 59% of off-hours trading in Q2 2025 (52% in Q1 2025, 44% in 2024), compared with the post-market's over 83% share in Q1 2019.
  — [NYSE Research, "The early bird gets the worm"](https://nyse.com/research/insights/the-early-bird-gets-the-worm-a-new-normal-in-off-hours-us-equities-trading); [NYSE Q2 2025 Extended Hours Trading Review](https://beta.nyse.com/publicdocs/nyse/NYSE_Research_Q2_2025_Extended_Hours_Trading_Review.pdf)
- Rosenblatt, August 2025: premarket average daily volume (ADV) was 0.91 billion shares and post-market 0.72 billion, together 9.97% of total volume including extended hours; September 2025 was 10.07%. Overnight ATS volume is reported inside "pre-market", which inflates that session. — [Rosenblatt Aug 2025](https://www.rblt.com/market-structure-reports/us-securities-volumes-august-2025); [Rosenblatt Sep 2025](https://www.rblt.com/market-structure-reports/us-securities-volumes-september-2025)
- Cboe data on premarket:
  - sub-dollar securities grew from 5% of premarket volume at the start of 2023 to almost 20% by the end of 2024, and ETFs from 8% to almost 25%;
  - Cboe's EDGX has run 4-7 a.m. trading since March 2021 and is the second-largest early-hours exchange;
  - EDGX routes to better-priced venues in early hours although no rule requires it, and routing is about 15% of EDGX's 4-7 a.m. volume since 2023.
  — [Cboe Insights, "Early Birds and Night Owls"](https://www.cboe.com/insights/posts/early-birds-and-night-owls-how-extended-trading-hours-are-reshaping-u-s-equities-markets-/); sub-dollar figure as summarized in [search of the same post](https://www.cboe.com/insights/posts/early-birds-and-night-owls-how-extended-trading-hours-are-reshaping-u-s-equities-markets-/)
- Cboe received SEC approval for 23x5 trading on EDGX and targets go-live in December 2026, pending industry readiness. — [Cboe Insights, "Expanding Market Access"](https://www.cboe.com/insights/posts/expanding-market-access-why-cboe-plans-to-launch-near-24-x-5-u-s-equities-trading-this-year/); [Crypto Briefing](https://cryptobriefing.com/extended-trading-hours-us-equities/)
- Nasdaq has filed to extend its trading hours to 23 hours a day, five days a week. — [Federal Register, Jan 13 2026](https://www.federalregister.gov/documents/2026/01/13/2026-00416/self-regulatory-organizations-the-nasdaq-stock-market-llc-notice-of-filing-of-proposed-rule-change)

**Practitioner sources (lower quality, no measured data)**
- Benzinga says small-cap stocks often do not have enough volume for premarket trading unless there is major news. — [Benzinga Pro guide](https://www.benzinga.com/pro/blog/complete-guide-pre-market-trading)
- Schwab warns that lower volume premarket may mean a lower chance of execution, wider spreads and greater price swings. — [Schwab](https://www.schwab.com/stocks/extended-hours-trading)
- Guides claim liquidity builds toward the open, and that 8:00-9:30 is the most liquid part of the premarket. These are illustrative claims, not measured. — [StockAlarm guide](https://pro.stockalarm.io/blog/pre-market-after-hours-trading)

### Inferences
- **Premarket fills will cost more.** For a momentum bot entering in the premarket, the base case is that each fill costs a multiple of what the same order costs after 9:30. The likely multiple is about 3-4x the spread and more in price impact, larger still for a thin, low-priced name.
- **Premarket may still hold the edge.** The same studies say pre-open prices carry more information per trade. The owner's preference for premarket leaders is consistent with that, but the bot pays for it in spread.
- **The cost falls as the open nears.** Liquidity and the number of participants rise toward 9:30, so the cost of the same order should fall from 4 a.m. to 9:30. A bot should probably expect its worst fills in the first hours (4-7 a.m.).
- **Premarket prints are a weak price reference.** Sub-dollar names now make up about a fifth of premarket volume, so much of that volume is in exactly the cheap, thin names this bot trades. A premarket print can be one small trade between two people, so a last-trade price is not a reliable price to act on.

### Gaps
- No study found that measures premarket (4:00-9:30) quoted or effective spreads, or depth at the best bid and offer, for low-priced (under $10) or small-cap US stocks. Barclay & Hendershott used 1999-2000 Nasdaq data, when prices were quoted in sixteenths; "Nocturnal Trading" covers 8 p.m.-4 a.m. and likely large stocks and ETFs.
- The NYSE Q2 2025 review and the Cboe post may contain spread or depth tables; they could not be opened in full here.
- The exact multiple (3x, 3-4x, 4-5x or 6x) differs between sources and versions.

## 2. Extended-hours order rules and what they do to a bot (limit-only, no stops, thin books, routing); stop-losses as limit orders when the bid gaps

### Takeaway
At Alpaca, every extended-hours order must be a limit order (time in force day or GTC, with `extended_hours=true`). Stop and stop-limit orders are rejected, so any premarket stop has to be built in the bot: watch the price, then send a limit sell. Such a sell fills only if a bid at or above its limit exists. When the bid gaps below the stop, a limit at the stop price does not fill, and the position stays open while the price falls. Price protection across trading venues does not apply outside regular hours, and premarket trades are only reviewed as "clearly erroneous" if they are at least 20% away from the last trade (for stocks up to $25). So a fill at an extreme price can stand, and some extreme fills can later be cancelled.

### Cited Findings
**Alpaca's rules**
- Only limit orders with time in force `day` or `gtc` are accepted for extended hours, with the boolean `extended_hours` set to true. Other order types and time-in-force values are rejected. Older doc versions said day only, before GTC was supported. — [Alpaca docs: Placing Orders](https://docs.alpaca.markets/docs/orders-at-alpaca); [older v1.1 page](https://docs.alpaca.markets/us/v1.1/docs/orders-at-alpaca)
- Alpaca's sessions are:
  - overnight 8:00 p.m.-4:00 a.m. ET, Sunday-Friday;
  - pre-market 4:00-9:30 a.m. ET;
  - after-hours 4:00-8:00 p.m. ET.

  A DAY order placed overnight stays live through the next day's regular and after-hours sessions and is cancelled at 8 p.m. if unfilled. — [Alpaca docs](https://docs.alpaca.markets/docs/orders-at-alpaca); [Alpaca Learn: 24/5 trading](https://alpaca.markets/learn/how-to-trade-us-stocks-24_5-overnight-with-python-and-alpaca)
- Users report the error "stop_limit orders are not eligible for extended hours trading". The workaround users describe is to watch the price over a websocket and submit a limit order when the stop price is hit. — [Alpaca forum: Allowing premarket STOP LIMIT orders](https://forum.alpaca.markets/t/allowing-premarket-stop-limit-orders/18645)
- Alpaca's price-increment rule: at or above $1.00, prices may have at most 2 decimals; under $1.00, at most 4. Orders with finer prices are rejected (error 42210000, "sub-penny increment does not meet minimum pricing criteria"). — [Alpaca docs v1.4.2](https://docs.alpaca.markets/us/v1.4.2/docs/orders-at-alpaca)
- Alpaca links to its Extended Hours Trading Risk Disclosure, citing thinner liquidity. — [Alpaca Learn: trading 4am-8pm](https://alpaca.markets/learn/how-to-enable-stock-market-trading-from-4-am-to-8-pm-et/)

**Market-wide rules outside regular hours**
- The Order Protection Rule (Reg NMS Rule 611, against trading through a better price on another venue) protects displayed quotes during regular trading hours; outside them there is no inter-market price protection. The second statement comes from an informal forum post. On June 11, 2026 the SEC voted to *propose* rescinding Rule 611; that proposal is not final. — [FlexTrade on Rule 611](https://flextrade.com/order-protection-rule/); [Alpaca forum: extended hours development](https://forum.alpaca.markets/t/extend-hours-trading-development/9380); [WilmerHale, June 2026](https://www.wilmerhale.com/en/sitecore/content/whlaunch/home/research/news-publications/20260617-the-sec-takes-aim-at-the-trade-through-rule)
- Cboe's EDGX does route early-hours orders to better-priced venues even though no rule requires it. Some venues may not. — [Cboe Insights](https://www.cboe.com/insights/posts/early-birds-and-night-owls-how-extended-trading-hours-are-reshaping-u-s-equities-markets-/)
- **Clearly erroneous trade thresholds** (how far a trade must be from the reference price before it can be reviewed and cancelled):

  | Stock price | Regular hours | Pre-market / post-market |
  |---|---|---|
  | $0-$25 | 10% | 20% |
  | $25-$50 | 5% | 10% |
  | over $50 | 3% | 6% |

  - The reference price is generally the last consolidated trade just before the trade under review.
  - The session is set by the trade's execution time.
  - The numerical guidelines apply to pre-market and post-market trades and to stocks not covered by LULD.

  — [Nasdaq Clearly Erroneous filing page](https://nasdaqtrader.com/trader.aspx?id=ceform); [Federal Register, Oct 2009](https://www.govinfo.gov/content/pkg/FR-2009-10-08/pdf/E9-24250.pdf); [SEC exhibit](https://www.sec.gov/file/exhibit-5-2548)
- LULD price bands do not run outside 9:30-4:00 (see section 4). The LULD Operating Committee says it intends to file separately to add price bands for overnight hours. — [LULD 2025 Annual Report](https://cdn.luldplan.com/reports/LULD-2025-Annual-Report.pdf); [luldplan.com](https://luldplan.com/)

**How stop orders behave in a gap**
- A standard sell stop becomes a market order once triggered; its main risk is slippage. A stop-limit becomes a limit order and "may never execute" if the price gaps through. In a worked example, a stock gaps from $48.10 to $46.80 against a $47.75 limit; the order stays unfilled while the price keeps falling. Gaps are most common on news, at earnings, in extreme volatility and in thin stocks. This source is an exam-prep site summarizing FINRA guidance; FINRA's own page was not retrieved. — [Achievable (FINRA SIE prep), stop orders](https://achievable.me/exams/finra-sie/insights/stop-orders-avoid-costly-trading-mistakes/); [Achievable, stop-limits](https://achievable.me/exams/finra-sie/insights/how-stop-limits-can-lead-to-safer-trades-in-any-market/)

**This bot's own record (Alpaca paper fills on live data)**
- On 10-08, in 12 trades the bid was already under the stop at the moment of the fill, costing -$1,519. Cause: a fast buy paid up to the ask + 20c while the stop sat 10c under the fill. BIAF at 8:06:44 paid $7.49 with the bid at $6.82 and was sold 8 ms later. — [memory/journal.md](../../memory/journal.md)
- Also on 10-08, 46 trades took over 2 seconds or 2+ orders to sell. Premarket limit sells were cancelled and re-sent about every second. — [memory/journal.md](../../memory/journal.md)
- The bot's premarket stop was moved to the live market (the midpoint of bid and ask) "because a premarket spread can be wider than a 10c stop". — [memory/journal.md](../../memory/journal.md)

### Inferences
- **A premarket stop is a trigger plus a sell order.** It can be measured from the last trade, the bid or the midpoint, and the sell can be a limit at the stop, a limit some distance below the bid, or a repeated reprice-and-resend loop. A limit at the stop price gives price control but no fill certainty: in a gap it leaves the position open. A sell priced below the bid (a marketable limit with a cap) bounds the worst price and usually fills, but in a thin premarket book it may sweep several price levels.
- **A stop distance narrower than the spread makes no sense.** If the spread at entry is wider than the stop distance (10c on a $5-8 stock is often narrower than the premarket spread), the position is "stopped" the moment it is bought. The bot's F2 losses look like this. A pre-trade check comparing the spread with the stop distance follows directly from the mechanics.
- **Extreme prints can cut both ways.** The clearly erroneous threshold doubles to 20% in the premarket and LULD bands are absent, so a single print 10-19% away from the last trade can stand in the premarket. A bot that reads the last trade can be triggered by such a print. A fill more than 20% away can later be cancelled, which could leave a position the bot thinks it no longer holds, or the reverse.
- **One venue can matter more than one quote.** With no trade-through protection, a single exchange's thin book can matter more than the national best bid and offer (NBBO). How Alpaca routes premarket orders to each venue therefore affects fills.

### Gaps
- Alpaca's exact extended-hours routing (which ECNs or market makers receive premarket orders, and whether they route between venues) was not found. Alpaca's Rule 606 reports might show it but could not be opened.
- No data was found on how often a premarket limit stop fails to fill, or on typical overshoot past the stop, for low-priced stocks. The bot's own fill logs are the best available source.

## 3. Market vs marketable limit vs passive limit orders for fast-moving small caps: adverse selection, fill rates, partial fills, paying over the ask, the cost of chasing

### Takeaway
Classic studies find that limit orders placed at or better than the quote cost less on average than market orders, even after a penalty for orders that never fill. But limit orders are adversely selected: they fill when better-informed traders are on the other side. On a breakout, that means a passive buy fills mostly when the move fails. Marketable limit orders look more expensive than market orders in raw averages, because people use them in fast, wide markets. Retail market orders in regular hours get real price improvement from wholesalers, but the same order executes at very different prices at different brokers. All of this evidence is from large or average stocks in regular hours; nothing was found for chasing small-cap breakouts in the premarket.

### Cited Findings
**Limit orders vs market orders**
- Harris & Hasbrouck (1996, JFQA, NYSE SuperDOT orders): limit orders priced at or better than the prevailing quote outperform market orders, even after a penalty for unexecuted orders and after counting market-order price improvement. Using SuperDOT to supply liquidity against the specialist without regard to conditions does not appear profitable. — [Cambridge abstract](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/market-vs-limit-orders-the-superdot-evidence-on-order-submission-strategy/5DB9EB63B964E4F619ED90BF6B08B690); [IDEAS](https://ideas.repec.org/a/cup/jfinqa/v31y1996i02p213-231_00.html)
- Peterson & Sirri (2002, JFQA, "Order Submission Strategy and the Curious Case of Marketable Limit Orders"):
  - the unconditional trading costs of marketable limit orders are "significantly greater" than those of market orders;
  - the difference is a selection effect, because traders choose the order type based on market conditions and stock characteristics;
  - the average trader picks the order type with the lower conditional cost.
  — [IDEAS](https://ideas.repec.org/a/cup/jfinqa/v37y2002i02p221-241_00.html); [author PDF](https://faculty.babson.edu/wp-content/uploads/2024/01/limit-orders-JFQA-june-2002.pdf)
- Linnainmaa (2010, *Journal of Finance*, all individual investors in Finland): limit orders are price-contingent and "suffer from adverse selection". They tend to fill when informed traders are on the other side. This alone can produce apparent individual-investor "mistakes" such as poor post-trade returns. — [IDEAS](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1473-1506.html); [commentary, J. R. Varma](https://www.jrvarma.in/blog/Y2012/orderflow-limit-orders.html)

**Retail market orders in regular hours**
- Dyhrberg, Shkilko & Werner ("The Retail Execution Quality Landscape", *Journal of Financial Economics* 2025):
  - wholesalers' price improvement on retail orders was about 24% of the quoted spread in the full sample and 47% in an average S&P 500 stock;
  - exchanges gave 3% and 5%;
  - the authors estimate wholesaler intermediation saves retail investors close to $1 billion a month.

  Figures differ between versions of the paper. — [AFA program copy](https://afajof.org/management/viewp.php?n=13580); [AEA 2024 copy](https://aeaweb.org/conference/2024/program/paper/5Gtsa7ra); [CEPR DP](https://ideas.repec.org/p/cpr/ceprdp/19364.html)
- Schwarz, Barber, Huang, Jorion & Odean ("The 'Actual Retail Price' of Equity Trades", *Journal of Finance* 2025):
  - they placed about 85,000 simultaneous small market orders through six accounts at five brokers over about six months;
  - mean round-trip execution cost ranged from 0.07% to 0.46% by account, excluding commissions;
  - the spread between brokers came from wholesalers giving different prices to different brokers for the same trades, not from differences in payment for order flow.

  The study covered market orders only. — [SSRN 4189239](https://papers.ssrn.com/abstract=4189239); [IDEAS (JF 2025)](https://ideas.repec.org/a/bla/jfinan/v80y2025i5p2507-2541.html); [WashU Olin news](https://olin.washu.edu/about/news-and-media/news/2022/10/study-finds-astonishing-differences-in-brokers-pricing-of-stock-trades.php)

**How Alpaca paper fills treat each order type**
- A paper buy limit fills only when the ask is at or below the limit (a sell limit when the bid is at or above it). Queue position for resting limit orders is not simulated: a passive limit fills as soon as the price touches it, while a live order would wait behind earlier orders. The queue point comes from a third-party blog. — [Alpaca forum, staff reply](https://forum.alpaca.markets/t/paper-trading-fill-delays-of-50-260-seconds-limit-orders-filled-minutes-after-price-crossed/18223); [TradersPost](https://blog.traderspost.io/article/alpaca-paper-trading)

**This bot's own timing and entries**
- Live decision-to-fill is about 1.3 s for v36 and v36b. A sale takes 0.2-0.8 s to send and 0.9-3.9 s to fill on paper. — [memory/journal.md](../../memory/journal.md)
- Fast buys pay up to the ask + 20c, which produced the F2 losses in section 2. — [memory/journal.md](../../memory/journal.md)

### Inferences
- **Passive limits are adversely selected on breakouts.** A resting buy below the market on a breakout fills mostly when the breakout fails, the Linnainmaa effect. The trades it misses are the runners. Passive entry therefore improves the average fill price on the trades it gets but changes *which* trades it gets, toward the losers. Any test of passive entries must count the missed winners.
- **A capped marketable limit is the standard middle ground.** A buy limit at the ask plus a small cap bounds how much the bot pays over the ask. If the price runs past the cap the order does not fill. That is a missed trade, not a loss, but the cap has to be wide enough to fill on real breakouts.
- **The cap should scale with the stock's spread.** A fixed 20c over the ask is a very different bet on a $2 stock and a $10 stock, and relative to a 2c spread versus a 50c spread.
- **Paper fills flatter passive orders.** Because Alpaca paper fills a resting limit as soon as the price touches it, paper results will make passive or "pegged" entries look better than they are live.
- **Price improvement is not a premarket assumption.** The 24-47% of the spread retail market orders get back applies in regular hours. No source showed wholesalers giving similar improvement premarket, and the "Nocturnal Trading" evidence points the other way.

### Gaps
- No study was found on order-type choice or the cost of chasing for small caps, low-priced stocks or premarket sessions. All the order-type evidence comes from NYSE or large stocks, or from Finnish retail data.
- No measured fill rates or partial-fill frequencies for real (not paper) limit orders in premarket small caps were found.

## 4. LULD halts, Reg SHO / SSR (Rule 201) and clearly erroneous rules: how they change execution risk for small-cap intraday trading

### Takeaway
LULD price bands only run 9:30-4:00. For Tier 2 (small) stocks they are 10% above $3 and 20% for $0.75-$3, doubled from 3:35-4:00 for stocks at or below $3. When a stock sits at a band for 15 seconds, a 5-minute halt follows on every venue. It can be extended in 5-minute steps, and the stock reopens in an auction whose collars allow a large gap. During a halt nothing can be sold, and stops are meaningless. In the premarket there are no LULD bands at all; the only backstop there is the wider 20% clearly erroneous rule. The short-sale circuit breaker (Rule 201) is triggered only in regular hours, but it then restricts short sales for the rest of that day and all of the next, premarket included.

### Cited Findings
**LULD band levels and timing**
- Tier 2 stocks priced $0.75-$3.00 have a 20% band, and Tier 2 covers all NMS stocks outside Tier 1 except rights and warrants. Tier 1 (S&P 500, Russell 1000, some ETFs) uses 5% above $3; Tier 2 uses 10% above $3. — [FINRA Regulatory Notice 13-12](https://finra.org/rules-guidance/notices/13-12); [Oppenheimer LULD summary](https://www.oppenheimer.com/_assets/docs/legal/limit-up-limit-down.pdf); [HeyGoTrade summary](https://www.heygotrade.com/en/blog/limit-up-limit-down-rules-luld-trading-halts/)
- LULD Amendment 18, effective February 24, 2020, changed when bands double:
  - it removed the doubling between 9:30 and 9:45 for all securities;
  - it removed the 3:35-4:00 doubling for Tier 2 stocks above $3.00;
  - Tier 1 and Tier 2 stocks at or below $3.00 still have doubled bands from 3:35 to 4:00 (so 40% for a $0.75-$3 Tier 2 stock, by arithmetic).

  Several secondary sources still describe the old 9:30-9:45 doubling. — [Cboe LULD FAQ, Amendment 18 update](https://www.cboe.com/document/tech-spec/content/technical-specifications/cboe-limit-updown-faq/luld-amendment-18-update)
- The LULD Plan applies in regular trading hours, 9:30 a.m.-4:00 p.m. ET, when price bands are in effect. The search summary did not say which of these pages the quote came from. — [luldplan.com](https://luldplan.com/); [Oppenheimer LULD summary](https://www.oppenheimer.com/_assets/docs/legal/limit-up-limit-down.pdf); [Investor.gov bulletin on volatility measures](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/measures)

**How a pause works**
- Limit State: the national best bid or offer sits exactly on a band. If it is not cleared within 15 seconds, the listing exchange declares a 5-minute Trading Pause that applies to all exchanges and off-exchange venues. If the listing exchange cannot reopen (for example, because of an order imbalance outside its auction collars), the pause extends in 5-minute steps. — [Nasdaq LULD FAQ](https://m.nasdaqtrader.com/content/MarketRegulation/LULD_FAQ.pdf); [Cboe LULD FAQ](https://www.cboe.com/document/tech-spec/content/technical-specifications/cboe-limit-updown-faq/general-questions)
- Amendment 12 (2017): other venues may no longer resume trading on their own after 10 minutes. They wait until the listing exchange reopens and new bands are published.
- Reopening auction collars:
  - the reference is the band last in a Limit State;
  - the lower collar is 5% below it (or $0.15 for stocks under $3);
  - the upper collar is the upper band, set there "to address mean price reversion".

  — [NYSE ETF Fact Sheet, Amendment 12](https://www.nyse.com/publicdocs/nyse/products/etp-funds/ETF_Fact_Sheet_Amendment_12.pdf); [NYSE LULD 12 testing](https://www.nyse.com/publicdocs/nyse/markets/nyse/NYSE_Group_LULD_12_testing.pdf)
- A comment letter to the SEC notes that not all orders reach the listing exchange's reopening auction, "sometimes resulting in less than stellar reopening results". — [SEC comment letter, File 265-29](https://sec.gov/comments/265-29/26529-81.pdf)

**How often pauses happen**
- SEC DERA staff white paper:
  - compared with the earlier single-stock circuit breakers, LULD brought more Trading Pauses for Tier 2 securities and fewer for Tier 1;
  - most pauses in both tiers came from "SRO-defined liquidity gaps", that is, from thin books rather than price moves alone;
  - Tier 1 had pauses on 18% of sample days (as summarized).

  A second DERA paper found pause frequency fell by more than 75% after Amendment 10, most for Tier 2. — [SEC DERA LULD white paper](https://www.sec.gov/file/dera-luld-white-paperpdf); [DERA, Amendment 10](https://www.sec.gov/dera/staff-papers/white-papers/dera_wp_effect_of_amendment_10_of_luld_pilot_plan); [DERA, Moise & Flaherty 2017](https://www.sec.gov/dera/staff-papers/white-papers/10mar17moiseflahertyluld)
- On August 24, 2015, 66% of LULD halts were limit-up, and 88% came as prices recovered and bands tightened at 9:45. This is the argument that led to removing the opening doubling. — [STA comment letter, 2019](https://securitytraders.org/wp-content/uploads/LULD-Amendment-18-ETF-Comment-Letter-20190130.pdf)
- The 2025 LULD annual report (submitted May 5, 2026) says limit states, pauses and straddle states are distributed by tier and ETP status; the totals could not be extracted. — [LULD 2025 Annual Report](https://cdn.luldplan.com/reports/LULD-2025-Annual-Report.pdf)

**Short-sale circuit breaker (Rule 201)**
- Rule 201 is triggered when a stock falls 10% or more from the prior day's close. The restriction then lasts the rest of that day and the following day. While it is in force, short sales may execute only above the current national best bid. — [SEC press release 2010-26](https://www.sec.gov/news/press/2010/2010-26.htm); [WilmerHale 2010](https://wilmerhale.com/insights/publications/the-new-short-sale-price-test-looking-ahead-to-compliance-march-12-2010)
- Per SEC staff FAQ:
  - the trigger is determined only during regular trading hours, 9:30-4:00, using regular-session trades, so a premarket drop alone does not trigger it;
  - once triggered, the restriction applies "at all times when quotation information... is available", which includes the next day's premarket;
  - there is no limit on how often it can re-trigger.

  — [SEC Division of Trading and Markets, Rule 201 FAQ](https://www.sec.gov/files/divisions/marketreg/rule201faq.htm)

**Clearly erroneous rules**
- The premarket clearly erroneous threshold is 20% for stocks up to $25 (see section 2). — [Nasdaq CE filing page](https://nasdaqtrader.com/trader.aspx?id=ceform)

### Inferences
- **A halt traps an open position.** For a long-only momentum bot, the main LULD risk is being in a position when a limit-down pause starts. Nothing can be sold for at least 5 minutes, and the reopening price can be far below. The lower collar is only 5% below the band, but the auction can extend in 5-minute steps and step down. Limit-up pauses are the common case in ripping small caps. A buy order resting at the moment of a limit-up pause either sits through the halt or joins the reopening auction, depending on venue and order type.
- **The 3:35-4:00 window is riskier for cheap stocks.** Stocks at or below $3 get 40% bands then, so a bigger move is allowed before any pause.
- **The premarket has no circuit breaker.** A low-float stock can move 50-100% in minutes with no pause. Halts there are news or regulatory halts only. The only backstop is the 20% clearly erroneous review, and only for trades that far from the last trade.
- **SSR does not limit a long-only bot.** It matters only indirectly: on the day after a 10% drop, short sellers cannot hit the bid, which practitioners believe changes intraday dynamics. No measured evidence was found for that here.

### Gaps
- No study was found on price behaviour after LULD pauses (continuation vs reversal) for small or low-priced stocks. The DERA white paper may contain one; it could not be opened.
- The Tier 2 band below $0.75 was not confirmed in this pass. It is believed to be the lesser of $0.15 or 75%; verify in [FINRA Notice 13-12](https://finra.org/rules-guidance/notices/13-12) or the LULD Plan.
- How Alpaca handles orders that arrive during a halt, and whether resting orders join the reopening auction, was not found.
- Counts of 2024-2025 LULD pauses by price tier could not be extracted from the annual report.

## 5. Payment for order flow, retail broker routing (Alpaca), and how paper fills differ from live fills, especially in illiquid names

### Takeaway
Alpaca routes orders to wholesale market makers (Virtu, Citadel, Jane Street, G1) and is paid by them. Its own 606 report says payment for order flow and price improvement come out of the same pool. Academic work finds wholesalers do improve on the quoted price in regular hours, but by different amounts for different brokers. Alpaca's paper trading fills against the live national best bid and offer but does not check order size against displayed size, does not simulate queue position, market impact or price improvement, and adds random partial fills about 10% of the time. Paper fills in thin, low-priced names are therefore likely optimistic on size and on passive fills. They may be pessimistic on price improvement for marketable orders in regular hours.

### Cited Findings
**Alpaca's routing and payment for order flow**
- Alpaca's Rule 606 reports (2025-2026) name Virtu, Citadel, Jane Street and G1 Execution Services. They state that payment for order flow and price improvement come "from the same pool", the market maker's expected profit on Alpaca customer orders, which is an inherent conflict. Alpaca earns revenue from third-party liquidity providers based on the order flow they execute. Rates are "largely similar" across providers but can differ by execution price and marketability. — [Alpaca 606 2026Q2](https://files.alpaca.markets/disclosures/library/SEC+606a1+-+2026Q2.pdf); [2026Q1](https://files.alpaca.markets/disclosures/library/SEC+606a1+-+2026Q1.pdf); [2025Q4](https://files.alpaca.markets/disclosures/library/SEC+606a1+-+2025Q4.pdf)
- Wholesalers give real price improvement in regular hours: 24% of the quoted spread overall, 47% in an average S&P 500 stock. — [Dyhrberg, Shkilko & Werner, AFA copy](https://afajof.org/management/viewp.php?n=13580)
- Execution prices for the same market order differ between brokers by 0.07%-0.46% round trip. Differences in payment for order flow do not explain this. — [Schwarz et al., SSRN](https://papers.ssrn.com/abstract=4189239)
- Virtu says about 40% of the retail flow it handles interacts with public or lit markets. This is a firm's self-description in an SEC comment letter. — [SEC comment letter](https://www.sec.gov/comments/4-913/4913-1037339-3444086.pdf)

**Disclosure and protections in extended hours**
- A 2026 comment letter asks the SEC to require separate Rule 605 and 606 reports for extended hours, implying the current reports do not cover it well. It says exchanges and the consolidated price feed (SIP) are expected to begin overnight operations on December 6, 2026. — [SEC comment letter S7-2026-20](https://www.sec.gov/comments/S7-2026-20/s7202620-820899-2503568.pdf)
- Nasdaq's summary: the protections retail orders get in the day session (Order Protection Rule, Rule 605, competition) are not in force during extended hours. — [Nasdaq](https://www.nasdaq.com/articles/looking-all-day-data-24-hour-trading)

**How Alpaca paper trading fills**
- Alpaca's docs say paper trading is a simulation that may differ from live trading. The list of what it does not account for begins with "market impact of your orders". — [Alpaca docs: Paper Trading](https://docs.alpaca.markets/docs/paper-trading)
- The full list, as reported by a third party: market impact, information leakage, slippage from latency, queue position for non-marketable limit orders, price improvement, regulatory fees and dividends. — [TradersPost blog](https://blog.traderspost.io/article/broker-paper-trading-comparison); [TradersPost, Alpaca paper trading](https://blog.traderspost.io/article/alpaca-paper-trading)
- Paper fills follow quote marketability: a buy limit fills only when the ask is at or below the limit. When an order becomes eligible, about 10% of the time it gets a partial fill of random size and the rest is re-evaluated. Alpaca staff describe this as intentional. — [Alpaca forum: partial fills](https://forum.alpaca.markets/t/alpaca-paper-trading-partial-order-fill/2683); [Alpaca forum: market order fill delay](https://forum.alpaca.markets/t/paper-trading-market-orders-fill-delay/18681)
- Order size is not compared with displayed size at the best bid and offer. One user's buy of more than twice the stock's traded volume filled in full. — [Alpaca forum](https://forum.alpaca.markets/t/alpaca-paper-trading-partial-order-fill/2683)
- Alpaca staff say paper and live slippage are meant to be similar but may differ in either direction, depending on liquidity, size and order type. In live trading, orders "generally fill at the quote prices but sometimes can be a bit better". — [Alpaca forum: slippage paper vs real](https://forum.alpaca.markets/t/slippage-paper-trading-vs-real-trading/2801)
- Users report paper limit fills arriving 50-260 seconds after the price crossed; staff attributed this to the partial-fill simulation. Market-on-open and market-on-close paper orders fill at the quote, not in the opening or closing auction. — [Alpaca forum: fill delays](https://forum.alpaca.markets/t/paper-trading-fill-delays-of-50-260-seconds-limit-orders-filled-minutes-after-price-crossed/18223); [Alpaca forum: paid account fills](https://forum.alpaca.markets/t/does-a-paid-account-give-more-accurate-paper-market-fills/14303)
- Paper-only account holders are entitled only to IEX market data, not the full consolidated feed (SIP). — [Alpaca support: paper vs live](https://alpaca.markets/support/difference-paper-live-trading); as summarized in [search](https://docs.alpaca.markets/docs/paper-trading)
- Third-party platforms add their own fill models. For example, TradersPost's default fills paper market orders at the midpoint, which it says flatters results by about half the spread. That is TradersPost's model, not Alpaca's. — [TradersPost](https://blog.traderspost.io/article/paper-trading-vs-live-results)

**This bot's own record**
- The bot's three accounts are Alpaca paper accounts: the journal refers to "paper fills" and to a real-money account that has not opened yet. Paper fills were "slower than the 0.5s order window". — [memory/journal.md](../../memory/journal.md); [CLAUDE.md](../../CLAUDE.md)

### Inferences
- **The bot's "live" results are paper fills on live quotes.** They fill $1,000-$10,000 orders against the national best bid and offer without checking whether that much size is displayed. In a premarket book that may show a few hundred shares at the ask, a real order for, say, 1,500 shares at $5 could sweep several levels or fill only in part. On size, real-money results are likely to be worse than paper results.
- **Passive orders will look better on paper than live.** Paper fills a resting limit as soon as the price touches it, ignoring the queue.
- **Marketable orders in regular hours may do slightly better live.** Wholesalers' price improvement is not simulated. The evidence for improvement in thin small caps, and for any improvement premarket, is weak.
- **Paper partial fills and delays are not the market's.** The random partial fills and odd delays come from the simulator and should not be read as market signals. They do not predict where live fills will be partial.
- **The bot's own feed is not the paper-only limit.** The bot uses a SIP data connection (per [CLAUDE.md](../../CLAUDE.md)), so the IEX-only limit for paper-only accounts may not apply to its signals. Paper fills are still simulated against the quote the simulator sees.

### Gaps
- No published comparison of Alpaca paper vs live fills for low-priced or small-cap stocks, or for the premarket, was found.
- Alpaca's 606 reports were not opened in full, so the routing percentages per venue and the payment-for-order-flow rates (including for orders under $1 and extended-hours orders) are not recorded here.
- Whether Alpaca routes premarket orders to wholesalers or directly to ECNs, and to which ones, was not found.

## 6. Measured slippage numbers for retail momentum traders in small caps

### Takeaway
No peer-reviewed study was found that measures per-trade slippage for retail momentum or day traders in small caps. The closest measured numbers are:
- 0.07%-0.46% round trip for small retail market orders across brokers, in regular hours and probably mostly liquid names;
- extended-hours spreads 3-4x and price impact 3-6x regular-hours levels;
- practitioner model assumptions of 25-100 basis points per side for $1-10 small caps.

This bot's own paper log is the most specific evidence available. It shows about 0.6% of spread per trade, and spread plus paying over the ask equal to about 70-80% of three days' losses.

### Cited Findings
**Measured or academic**
- Small retail market orders cost 0.07% to 0.46% round trip across brokers, excluding commissions (85,000 trades). — [Schwarz et al., JF 2025](https://ideas.repec.org/a/bla/jfinan/v80y2025i5p2507-2541.html); [SSRN](https://papers.ssrn.com/abstract=4189239)
- After-hours quoted and effective spreads are 3-4x daytime levels (Barclay & Hendershott 2004). Overnight price impact is at least 3-4x (Eaton, Shkilko & Werner), or about 6x per Nasdaq's summary. — [summary of B&H 2004](https://academicnewsletter.sufe.edu.cn/info/361191); [AFA, Nocturnal Trading](https://afajof.org/management/viewp.php?n=162176); [Nasdaq](https://www.nasdaq.com/articles/looking-all-day-data-24-hour-trading)
- A working paper (Hagströmer, via a Scribd copy) finds the standard effective spread overstates the cost by up to 96% for low-priced stocks, because the tick is large relative to price. Verify against the original. — [Scribd copy](https://www.scribd.com/document/424367337/hft)
- Rule 605 effective spread is measured from the midpoint at order entry to the execution price, doubled. Fidelity's published statistics cover market orders of 100-1,999 shares. Rule 605 statistics exclude odd lots and do not match dollar trade size well. — [Fidelity execution statistics](https://capitalmarkets.fidelity.com/trade-execution-quality/statistics); [Nasdaq, "Would 605 work better in dollars?"](https://www.nasdaq.com/articles/would-605-work-better-in-dollars-2021-09-16)
- Eaton, Green, Roseman & Wu (JFE 2022): in stocks heavily traded by retail investors, Robinhood outages *reduced* order imbalances, *raised* liquidity and *lowered* volatility; outages at traditional brokers did the opposite. The authors attribute this to herding by inexperienced investors creating inventory risk for market makers. This bears on the cost of trading in the retail "hot" stocks a momentum bot targets. — [SSRN 3776874](https://papers.ssrn.com/abstract=3776874); [IDEAS](https://ideas.repec.org/a/eee/jfinec/v146y2022i2p502-528.html)
- Institutional evidence, large traders, not small caps:
  - Frazzini, Israel & Moskowitz, using about $1.7 trillion of AQR's live executions, find real trading costs far below earlier academic estimates and momentum scalable;
  - Lesmond, Schill & Zhou (2004) found no net-of-cost momentum return using TAQ data;
  - a tradable momentum benchmark built from fund holdings lags its paper factor by 2-4% a year.

  — [SSRN 3229719](https://papers.ssrn.com/abstract=3229719); [NBER draft](https://conference.nber.org/conf_papers/f68262/f68262.pdf); [AEA 2019 paper](https://topcat.aeaweb.org/conference/2019/preliminary/paper/YKhtHiNN); [Review of Finance](https://academic.oup.com/rof/article/29/1/103/7755053)

**Practitioner estimates (low quality, model assumptions rather than measurements)**
- One transaction-cost guide sets a slippage floor of 25-100 basis points per side for small caps priced $1-10 with $100M-$1B market caps, versus 5-15 for mid caps, and calls the common 5 bp backtest default "fiction" below mid cap. — [skills.cat transaction-cost guide](https://skills.cat/skills/jefrnc/quant-llm-skills/transaction-cost-modeling)
- A $0.02 spread on a $2 stock is 100 basis points before any market impact. — [skills.cat](https://skills.cat/skills/jefrnc/quant-llm-skills/transaction-cost-modeling)
- For scalpers, $0.08 of combined entry and exit slippage against a $0.10 target leaves almost no edge. TradingView's strategy tester assumes zero slippage by default. — [Day Trading Toolkit](https://daytradingtoolkit.com/beginners-guide/understanding-slippage-fill-prices); [PickMyTrade](https://blog.pickmytrade.io/tradingview-strategy-tester-ai-optimize-for-real-world-results/)

**This bot's own record (Alpaca paper fills, live data, 2026-10-06 to 10-08)**
- "each [trade] pays ~0.6% in spread on these stocks". — [memory/journal.md](../../memory/journal.md)
- Spread plus paying over the ask were about 70-80% of v36/v36b's losses and more than v37's whole loss over 3 days. — [memory/journal.md](../../memory/journal.md)
- BIAF: $7.49 paid with the bid at $6.82, about 9% under the fill. Replayed at its stop prices, BIAF would have cost v36 -$157 instead of -$516; "the damage was the fills". — [memory/journal.md](../../memory/journal.md)
- Replay sensitivity: the 10-07 replay loses on 9:30-4 for v36 (-$2,022) at fills 0.2% worse. The journal records that replay fills are kinder than live. — [memory/journal.md](../../memory/journal.md)

### Inferences
- **The cost per trade is large compared with the edge.** On a $5 stock with a 5c spread (1%), one round trip that crosses the spread costs about 1%, before any paying over the ask or overshoot past a stop (simple arithmetic, not sourced data). Against a 10c stop (2%) and typical gains of a few percent, that cost is large. This matches the bot's own finding that costs were most of its losses. It supports trading fewer, higher-conviction entries (the owner's "1, 2 or 3 trades a day").
- **The published numbers are lower bounds.** They come from regular hours, larger stocks or institutional traders. Premarket small-cap costs should be assumed several times higher. The bot's own fill logs, kept per trade with the bid, ask, last trade and fill, are the best way to measure them. Replays should apply a cost per trade at least as large as the measured live average (about 0.6% spread plus paying over the ask), not 0.2%.

### Gaps
- No academic or regulatory source was found with measured slippage for retail day or momentum traders in small or low-priced stocks in the premarket. Barber/Odean-style day-trader studies (Taiwan, Brazil) measure net returns, not per-trade slippage, and were not checked here.
- Rule 605 reports from wholesalers could give regular-hours effective spreads for stocks under $5 at retail sizes, but they would have to be pulled and filtered by price; this was not done.
- The SEC's 2024 tick-size and access-fee changes to Rules 610 and 612 (a $0.005 tick for some stocks, a 10-mil fee cap) are mostly about tick-constrained, liquid stocks. Their compliance date was moved to November 2, 2026, and possibly again to 2027; the 2027 date is unconfirmed. They are unlikely to change much for wide-spread small caps. — [SEC fact sheet 34-101070](https://sec.gov/files/34-101070-fact-sheet.pdf); [SIFMA, May 2026](https://www.sifma.org/advocacy/letters/supplemental-request-for-immediate-extension-of-tick-size-and-access-fee-compliance-dates); [FindKnowDo (unconfirmed 2027)](https://www.findknowdo.com/node/660563)
