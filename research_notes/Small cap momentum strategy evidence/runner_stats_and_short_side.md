# Low-float small-cap "runners": day-one statistics, what predicts continuation vs fade, dilution, and the short-side fade

Research date: 2026-10-09. Method note: the egress proxy blocked direct page fetches for almost every
site (smallcaplab.com, tradezella.com, ssrn/university PDFs and others returned DNS errors or 403),
so every figure below comes from search-engine extracts of the named page, not from reading the full
page or paper. Numbers marked "vendor" or "practitioner" were not independently checked. Academic
figures are from abstracts or reputable summaries; check the published tables before relying on an
exact number.

Source quality legend used below: [ACADEMIC] peer-reviewed or working paper; [REGULATOR] SEC / FINRA /
exchange / LULD plan; [VENDOR] a firm that sells data, scanners, courses or a strategy; [PRACTITIONER]
a trader's blog or Substack; [PRESS] news or law-firm summary.

---

## 1. How do day-one small-cap gappers behave (close vs open / premarket high / VWAP; when is the high of day)?

### Takeaway
No peer-reviewed study measures this for US low-float gappers. The two largest public samples (both
vendor/practitioner) agree on the direction: most stocks that gap 50%+ close below their regular-hours
open (about 65-71%), the average one trades more than 20% below the open at some point, but only a
small minority give back the whole gap. Academic work on "attention" stocks explains why: retail buying
pushes the opening print up, and it reverses during the day.

### Cited Findings
**Large-sample vendor / practitioner counts (gaps of 50%+)**
- [VENDOR] SmallCapLab tracks every stock that gapped 50% or more at the open: about 2,999 events since January 2022. — [SmallCapLab data](https://www.smallcaplab.com/data)
- [VENDOR] SmallCapLab dashboard, period averages: 65.6% of gap-up stocks closed below their regular-hours open; only 3.9% "round-tripped" (closed below the prior day's close); the average low of day was -22.2% from the open. — [SmallCapLab research](https://www.smallcaplab.com/research)
- [VENDOR] Same dashboard: premarket-high (PMH) break rate averaged 42.2% (share of gappers that traded above their premarket high during regular hours); "HOD collapse" (broke above the PMH and then closed below the open) averaged 14.1%; median move from the open to the high of day about 34%. — [SmallCapLab research](https://www.smallcaplab.com/research)
- [VENDOR] By gap size, the 100-150% bucket had a PMH break rate near 42% and "averages 32% HOD-to-close drop"; the page concludes that "larger gaps extend further intraday but also collapse harder." — [SmallCapLab research](https://www.smallcaplab.com/research)
- [VENDOR] SmallCapLab also publishes a "% of gappers that closed below VWAP" metric and a time-of-day table (one row reads 59.6% in the 10:00-10:30 window rising to 99.9% after 13:00), but the search extract did not make clear what the table measures (cumulative vs per-window, and of what), and the VWAP figure itself was not retrieved. The page showed several placeholder-looking "today 100.0%" values. SmallCapLab sells a systematic small-cap SHORT strategy, so it has a commercial interest in fade statistics. — [SmallCapLab research](https://www.smallcaplab.com/research); [SmallCapLab data](https://www.smallcaplab.com/data)
- [PRACTITIONER] Stonks Capital (Spikeet data): of 3,685 stocks that gapped up more than 50% since 2008, 70.8% closed red (below the open). — [Stonks Capital, "Why I Short Small Caps (Even Though it Sucks)"](https://stonkscapital.substack.com/p/why-i-short-small-caps-even-though)
- [PRACTITIONER] Same author, gaps >50% with premarket dollar volume >$200K since 2008: 3,636 instances; outcomes fall into three groups: fade from the open, squeezes of varying size, and stocks that keep running into the close (the reason the test needs a stop). — [Stonks Capital, "The Science of Shorting"](https://stonkscapital.substack.com/p/the-science-of-shorting-using-backtesting)
- [VENDOR/course] Steven Dux material summarised by Tradezella: average post-open push of roughly 30-35% on floats of about 1-2 million shares vs about 20-25% on floats of 5-10 million; average fade of about 26% from the intraday high on "clean" gap-up shorts (24-25% practical after entry). These are the author's observations, not a published dataset. — [Tradezella, Steven Dux small-cap short strategy](https://www.tradezella.com/strategies/small-cap-short-strategy)

**Academic evidence on why the open is high and the day fades**
- [ACADEMIC] Berkman, Koch, Tuttle & Zhang (JFQA 2012), "Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open": a strong tendency for positive overnight returns followed by intraday reversals; the reversal comes from an opening price that is high relative to intraday prices; concentrated in stocks that recently drew retail attention, stronger for hard-to-value and costly-to-arbitrage stocks and when retail sentiment is high; for retail traders buying high-attention stocks near the open, the implicit cost "frequently exceed[s] the effective half spread." — [Cambridge/JFQA](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/paying-attention-overnight-returns-and-the-hidden-cost-of-buying-at-the-open/F9AAD159B512C651F09D5D52011D88E0); [IDEAS record](https://ideas.repec.org/a/cup/jfinqa/v47y2012i04p715-741_00.html)
- [ACADEMIC] Aboody, Even-Tov, Lehavy & Trueman (JFQA 2018): high overnight returns are a firm-level retail-sentiment measure; they persist in the short term (more so for hard-to-value firms) and reverse over the longer term (press coverage: next 12 months); the effect is magnified in stocks with fewer institutional and more individual holders. — [Aboody et al. PDF (UCLA Anderson)](https://anderson-review.ucla.edu/wp-content/uploads/2021/03/Aboody-et-al_overnight_returns_and_firmspecific_investor_sentiment_JFQA2018.pdf); [IDEAS](https://ideas.repec.org/a/cup/jfinqa/v53y2018i02p485-505_00.html)
- [ACADEMIC] Barber, Huang, Odean & Schwarz, "Attention Induced Trading and Returns: Evidence from Robinhood Users": average 5-day abnormal returns of -3% for the stocks Robinhood users buy most each day and -6% for the most extreme herding events; the app's "Top Movers" list (20 stocks) concentrates attention; UC Davis summary: the top bought stocks fall about 5% over the next month and extreme herding events reverse about 9%; the effect is more pronounced after Covid. — [Paper PDF (SSRN id3715077 copy)](https://www.smallake.kr/wp-content/uploads/2020/12/SSRN-id3715077.pdf); [UC Davis summary](https://www.ucdavis.edu/curiosity/blog/what-effect-brokerage-robinhood-having-stock-market)

**Timing of volatility within the day**
- [REGULATOR] SEC DERA staff paper (Moise & Flaherty, 2017): a large number of LULD events fall in Tier 2 (smaller, less liquid) securities, and a disproportionate share of limit states and pauses occur at the beginning of the trading day (first 15 minutes). — [SEC DERA white paper](https://www.sec.gov/dera/staff-papers/white-papers/10mar17moiseflahertyluld)

### Inferences
- Base rate for the long side: buying a 50%+ gapper at or after the 9:30 open is buying into a two-thirds probability of a red regular session (vendor 65.6%, practitioner 70.8%, different periods and filters, same direction). The average gapper still gives a ~34% open-to-high push (vendor median), so the money on the long side is in the timing of the first push, not in holding to the close.
- "Close below open" is not "round trip": only ~4% close below the prior close (vendor). Most of the day-one gain usually survives the day even when the session is red. This matters for multi-day setups (day two).
- Berkman/Aboody/Barber all point to retail attention as the reason the open is rich; the premarket session (when the owner's playbook says the move happens) is where that attention is being built, and the open is where it is cashed.
- The SmallCapLab "HOD collapse" of 14% (break PMH then close below open) suggests that a premarket-high break at the open is not a reliable continuation signal on its own: only ~42% of gappers break the PMH at all, and about a third of those that do (14.1/42.2) end red.

### Gaps
- No academic or regulator dataset gives the share of US low-float gappers (20%+, 50%+, 100%+) that close above/below the premarket high or VWAP, or the distribution of the time of the high of day. Only one vendor (SmallCapLab) publishes such figures, its methodology was not retrievable, and its page showed inconsistent values.
- No public numbers were found for the 20%+ gap threshold specifically (all public samples use 50%+).
- Float-bucketed and price-bucketed fade rates: not found in any public source. The repository's own replay data (`replay/data/`) would be the right place to measure these directly.

---

## 2. What predicts continuation vs fade?

### Takeaway
The best academic evidence is about *information*: big moves backed by real, fundamental news tend to
drift on; big moves without news (or driven by promotion) tend to reverse. Short-sale constraints,
retail attention and low institutional ownership all predict *later* underperformance, but they also
make a stock harder and riskier to short. Float, relative volume and float rotation are used by every
practitioner but have no published large-sample test. Promotional "ramp-and-dump" names (tiny, often
foreign-based IPOs) and reverse-split names are the best-documented fade categories.

### Cited Findings
**News vs no news**
- [ACADEMIC] Savor (JFE 2012), "Stock Returns After Major Price Shocks: The Impact of Information": using analyst reports as the proxy for information, large price moves with information are followed by drift; moves without information reverse. Drift appears only when the price move and the analyst recommendation change have the same sign. — [UPenn repository](https://repository.upenn.edu/handle/20.500.14332/34495)
- [ACADEMIC] Govindaraj, Livnat, Savor & Zhao, "Large Price Changes and Subsequent Returns": when analysts revise forecasts right after a large shock, prices show momentum; shocks without prompt revisions reverse, attributed to liquidity/noise traders. (Secondary summary.) — [Alpha Architect](https://alphaarchitect.com/2013/03/follow-the-trend-and-the-sell-side/)
- [ACADEMIC] Baars & Mohrschladt (JEBO 2021): after a stock's maximum daily return there are immediate price reversals and no lottery-preference price pressure; the MAX effect reverses (i.e. continuation) when the MAX return was caused by an earnings announcement. — [Univ. Münster record](https://cris-portal.uni-muenster.de/portal/en/publication/80040415)

**Volume / turnover**
- [ACADEMIC] Gervais, Kaniel & Mingelgrin (JF 2001), "The High-Volume Return Premium": stocks with unusually high (low) volume over a day or a week tend to rise (fall) over the following month; explained by a visibility effect. — [Wharton working paper PDF](https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/04/9901.pdf)
- [ACADEMIC] Conrad, Hameed & Niden (JF 1994): high-transaction securities show weekly price reversals; low-transaction securities show positive autocorrelation (continuation). — [IDEAS](https://ideas.repec.org/a/bla/jfinan/v49y1994i4p1305-29.html)
- [PRACTITIONER] Ross Cameron "5 pillars" as coded in a third-party TradingView script (not an official Warrior Trading source): relative volume of at least 5x the 30-day average, already up at least 10%, a news catalyst, price $1-$20, float at most 10 million shares (5 million for "ultra-aggressive" traders). No win rates or continuation statistics were found from Warrior Trading. — [TradingView "Ross Cameron 5 Pillars Filter"](https://kr.tradingview.com/script/mbqMf3pF-Ross-Cameron-5-Pillars-Filter)
- [VENDOR/course] Dux material: skip a short when float rotation is above roughly 15x without a clear momentum shift; lower floats push further after the open (see section 1). — [Tradezella, Dux strategy](https://www.tradezella.com/strategies/small-cap-short-strategy)

**Short-sale constraints, institutional ownership, disagreement (Miller 1977)**
- [ACADEMIC] Miller (1977): with short-sale constraints, divergence of opinion leads to higher prices and lower future returns, and the effect should be stronger where constraints bind (as summarised by Doukas et al. 2006, who also note the literature "is remarkable for its inability to converge"). — [Doukas et al., JFQA 2006 PDF](https://www.efmaefm.org/0DOUKAS/publications/pdf/JFQA(41)2006.pdf)
- [ACADEMIC] Diether, Malloy & Scherbina (JF 2002): higher dispersion in analysts' forecasts predicts lower future returns, most pronounced in small stocks and past losers. — [Kellogg PDF](https://www.kellogg.northwestern.edu/faculty/mcdonald/ftp/practicum/papers/dms3.pdf)
- [ACADEMIC] Nagel (JFE 2005): the underperformance of high-turnover, high-volatility, high-dispersion and high market-to-book stocks is most pronounced among stocks with low institutional ownership (his proxy for binding short-sale constraints), holding size fixed. — [Abstract (SUFE newsletter)](https://academicnewsletter.sufe.edu.cn/info/357572)
- [ACADEMIC] Asquith, Pathak & Ritter (JFE 2005): stocks with high short interest and low institutional ownership underperformed by 215 bp/month equal-weighted (significant) but only 39 bp/month value-weighted (insignificant), 1988-2002; for most stocks the constraints are unlikely to bind. — [Ritter's site PDF](https://site.warrington.ufl.edu/ritter/files/2015/04/Short-interest-institutional-ownership-and-stock-returns-2005-08.pdf)
- [ACADEMIC] Engelberg, Reed & Ringgenberg (JF 2018), "Short-Selling Risk": loan fees rise sharply when past returns are in the top or bottom quartile; loan supply falls when past returns are high, "precisely when it is costliest for a short-seller"; stocks with more short-selling risk have lower returns, less price efficiency and less short selling; median loan is open about 65 days. — [Wharton PDF](https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/03/riggenberg.pdf); return figures (0.58%/month low-risk vs -0.49%/month high-risk quintile) from a secondary summary — [Swedroe, ETF.com](https://www.etf.com/sections/index-investor-corner/swedroe-risks-short-selling)

**Promotion, ramp-and-dump and foreign small caps**
- [REGULATOR] FINRA: ramp-and-dump schemes have most often involved IPOs raising under $25 million, issuing fewer than 20 million shares, valued under $100 million, mostly with operations abroad; victims are recruited via text, DMs, WhatsApp/WeChat/Telegram groups; limited float makes the stock more volatile and harder to sell. — [FINRA, "This On-Ramp Could Lead You to a Dump"](https://www.finra.org/investors/insights/ramp-and-dump-schemes)
- [REGULATOR] FINRA Regulatory Notice 22-25 (Nov 2022): nominee accounts buy into small-cap IPOs and then run manipulative limit-order and trading activity that ends with shares sold to retail investors, some of them social-media scam victims. — [FINRA RN 22-25](https://www.finra.org/sites/default/files/2022-11/Regulatory-Notice-22-25.pdf)
- [REGULATOR/PRESS] SEC trading suspensions from 26 Sept 2025: QMMM Holdings had surged nearly 1,000% in under three weeks after social-media touts; the SEC orders cited "recommendations made to investors by unknown persons via social media"; one law firm counts 14 suspensions since Sept 2025, all of foreign issuers on Nasdaq/NYSE; Cooley counts nine Asia-based Nasdaq issuers between 26 Sept and 22 Oct 2025. — [Securities Lawyer 101](https://www.securitieslawyer101.com/2025/sec-trading-suspensions-of-qmmm-sdm-new-sec-cross-border-task-force/); [Cooley](https://investigations.cooley.com/2025/10/28/sec-intensifies-oversight-of-foreign-companies-that-participate-in-u-s-capital-markets/)
- [PRESS] After the 10-business-day SEC suspensions lapsed, Nasdaq/NYSE kept trading halted indefinitely pending information requests; a Nasdaq analysis found 143 of 151 China-based companies listed Aug 2022-Apr 2025 would not qualify under the tougher standards now in place. — [Bloomberg Law](https://news.bloomberglaw.com/bloomberg-government-news/sec-foreign-firm-suspension-blitz-spurs-monthslong-trading-halts)

**Reverse splits**
- [ACADEMIC] Kim, Klein & Rosenfeld (Financial Management 2008), >1,600 firms: significantly negative abnormal returns over the three years after the reverse-split month, poor operating performance, and the stocks are "very difficult to sell short." — [IDEAS](https://ideas.repec.org/a/bla/finmgt/v37y2008i2p173-192.html)
- [ACADEMIC, conflicting] An IAES conference paper (1,930 NYSE/AMEX/NASDAQ firms, split factors of at least 1:2): negative, significant abnormal returns in the effective month, but positive, significant CARs over months +1 to +36 for small firms. — [IAES abstract](https://iaes.confex.com/iaes/72am/webprogram/Paper6539.html)
- [ACADEMIC, student] Utah State master's project (2021): negative 20-day CARs after reverse splits, particularly for heavily shorted firms. — [USU Digital Commons](https://digitalcommons.usu.edu/gradreports/1533)

**Biotech / FDA**
- [PRESS] Verastem fell as much as 21% on more than 4x normal volume after its first approval, having risen 191% that year: the "sell the news" pattern after a first approval. — [Motley Fool](https://www.fool.com/investing/2018/09/25/why-verastem-inc-stock-is-crashing-today.aspx)
- [PRESS] Ardelyx fell after FDA approval; one stated reason was fear the company would use the price jump to issue new shares. — [Motley Fool](https://www.fool.com/investing/2019/09/13/why-ardelyx-shares-are-sinking-today.aspx)
- [ACADEMIC] Large-pharma study, 1989-2008: only 10 of 1,721 FDA new-drug approvals were linked to abnormally large returns (large firms; anticipation). — [Univ. of Western Ontario](https://ir.lib.uwo.ca/undergradawards_2018/18)
- [ACADEMIC, non-US] Korean study (2024): FDA approval announcements produce abnormal price gains, larger for small firms than mid/large. — [Sogang University](https://scholarworks.sogang.ac.kr/item/83d93ebe-e223-4ca2-9d56-e90906de437d)

### Inferences
- Savor and Baars & Mohrschladt give a market reason for the owner's "news first" filter: a move backed by hard information (earnings, a binding contract, an approval that was not priced in) is the case where academic evidence shows continuation; a move with no verifiable news, a promotional PR, or social-media chatter is the case where reversal is the norm.
- Red flags for fade, per regulators: tiny recent IPO (< $25M raised, < 20M shares, < $100M value), foreign-based (China/HK/SE Asia), social-media driven, no fundamental news. These are also the names most likely to be halted for days or weeks by the SEC/exchange (a risk for any open position, long or short).
- Reverse-split names: the long-run evidence is mostly negative and they are hard to short; the day-one "effective-date squeeze" is a float effect, not a value signal. No public study measures the effective-date intraday move.
- Float, relative volume and float rotation are practitioner conventions without published continuation statistics; any threshold the bot uses should be checked on the repository's own recorded days rather than borrowed from course material.
- High-volume / visibility (Gervais et al.) predicts continuation over a month for ordinary stocks, while high turnover in short-sale-constrained, low-institution stocks predicts underperformance (Nagel). For low-float runners the second setting is the relevant one.

### Gaps
- No published large-sample test of float size, float rotation, relative volume, price level or premarket time-of-gap as predictors of same-day continuation in US low-float gappers.
- No study found on the "reverse split effective-date" low-float run or on contract/deal PRs specifically.
- The 2026 Princeton thesis using minute-level data on FDA approvals and complete response letters (2010-2024) was found but its results were not retrievable. — [Princeton thesis record](https://theses-dissertations.princeton.edu/entities/publication/bd23f089-38e8-4418-98ad-0d470d265e28)

---

## 3. Dilution: how often do runners raise money on or after the run, and what does it do to price?

### Takeaway
Small issuers can sell stock into a spike quickly (shelf registrations, at-the-market programs, registered
direct offerings with warrants). Practitioner data say offerings often come right after a spike and knock
20-30% off on announcement; academic work shows long-run underperformance after such deals. No public
source gives a reliable "probability of an offering within N days of a run."

### Cited Findings
- [ACADEMIC] Billett, Floros & Garfinkel (JFQA 2019), "At-the-Market Offerings": ATMs (shares "dribbled out" into the secondary market without an underwritten deal) became possible in 2008 when smaller firms gained access to shelf registration; by 2016 their incidence was 63% and proceeds 26% of those of seasoned equity offerings; 65% of ATM proceeds are stockpiled as cash vs 84% for SEOs. — [IDEAS](https://ideas.repec.org/a/cup/jfinqa/v54y2019i03p1263-1283_00.html); [CFA Institute digest](https://rpc.cfainstitute.org/research/cfa-digest/2020/06/dig-v50-n6-2)
- [ACADEMIC] Kennesaw State working paper on registered direct offerings (1,170 RDOs, 2008-2021, PlacementTracker; excludes issuers below $5M market cap or $1 price, which the authors say biases results toward milder outcomes because the smallest issuers use RDOs more): no-warrant RDOs had average market-adjusted returns of -4.44% in year one, -16.99% over two years and -25.59% over three years; RDOs got less negative announcement reactions than confidentially marketed public offerings. — [Kennesaw State PDF](https://www.kennesaw.edu/coles/research/docs/fall-2024/fall-24-04.pdf)
- [VENDOR] DilutionTracker analysed over 1,300 offerings, defining a "spike" as a >50% intraday move; it reports that offerings are often preceded by a spike, that offerings push the price down 20-30% on announcement on average, and that higher warrant coverage means worse dilution and price reaction (chart values not retrievable; article about five years old). — [DilutionTracker knowledge base](https://knowledge.dilutiontracker.com/en/articles/5722415-offerings-investment-bank-tiers-and-why-it-matters-for-small-cap-stocks); 20-30% figure also repeated in a review — [The Stock Dork review](https://www.thestockdork.com/?p=255335)
- [PRACTITIONER] "The stock typically reacts the day of the announcement — often gapping down at the open if the announcement came after hours." — [DilutionWatch explainer](https://dilutionwatch.com/articles/dilution-impact-on-stock-price.html)
- [PRACTITIONER/consulting] Reported dilution in many small offerings understates actual dilution because issuers rely on stale financial data. — [SLCG](https://www.slcg.com/resources/blog/703)
- [PRESS] Example terms: China SXT's $12M registered direct included warrants for up to nine shares per warrant; Haoxi Health's $6.5M RDO paired common with nearly 17 million pre-funded warrants at $0.25. — [Yahoo Finance, China SXT](https://finance.yahoo.com/markets/stocks/articles/china-sxt-pharmaceuticals-announces-12-144409864.html); [Yahoo Finance, Haoxi](https://finance.yahoo.com/sectors/healthcare/articles/registered-direct-offering-raises-dilution-150023885.html)
- [PRACTITIONER, unverified] WOK reportedly signed a $200M ATM in Nov 2025, about 1,000x its market cap, and sold into demand. Single secondary source; not checked against SEC filings. — [BIT Knowledge Hub](https://www.bit.com/knowledge-hub/the-atm-dilution-trap)
- [PRESS] Ardelyx's post-approval drop was partly attributed to fear of a share sale after the jump. — [Motley Fool](https://www.fool.com/investing/2019/09/13/why-ardelyx-shares-are-sinking-today.aspx)

### Inferences
- Dilution is a mechanical reason runners fade: a company with an effective shelf or ATM can add supply into the very demand that created the spike. A live ATM or fresh shelf (S-3/S-1/F-3) is a known, checkable fact, so per the owner's rule ("a loss from something known and predictable is a defect") it belongs in the entry checks for any position held past the first push or overnight.
- After-hours offering announcements produce gap-downs at the next open, which is a specific risk for overnight longs in runners.

### Gaps
- No public, verified statistic on how often a 50%+ runner files or prices an offering within 1/5/20 trading days. DilutionTracker's chart has it but the values were not retrievable.
- No academic study found on intraday price impact of ATM usage during a spike.

---

## 4. The short-side fade of parabolic gappers: is there a documented edge, and what are the practical limits?

### Takeaway
High win rates for fading big gappers are well documented in practitioner backtests (about 70% close red),
and academic work agrees that hard-to-borrow, attention-driven stocks earn low subsequent returns. But
(a) the strongest academic evidence says much of the anomaly profit is eaten by borrow costs, spreads and
commissions, (b) the losses are fat-tailed (squeezes, halts), (c) live results from practitioners are
weaker than their backtests, and (d) the stocks are usually hard to borrow, so the trade may be
unavailable or costly. No published, cost-inclusive, peer-reviewed backtest of shorting US low-float
gappers was found.

### Cited Findings
**Practitioner / vendor backtests**
- [PRACTITIONER] Short at the open, cover at the close, wide stop, borrow modelled at $0.01/share, 5% of a $10K account per trade, gaps >50% with >$200K premarket volume since 2008 (3,636 trades); the headline expectancy was not retrievable; a commenter found a 70% gap / 30% stop variant gave a worse equity curve. "Short locates are hard to simulate." — [Stonks Capital, "The Science of Shorting"](https://stonkscapital.substack.com/p/the-science-of-shorting-using-backtesting) (and [comments](https://stonkscapital.substack.com/p/the-science-of-shorting-using-backtesting/comments))
- [PRACTITIONER] Live results from the same author: March 2025 account down $4,350; tradable gaps fell from 74 in February to 45 in March; later post: "all three of my signals made the same core bet," so they failed together. — [Stonks Capital March 2025 recap](https://stonkscapital.substack.com/p/march-2025-recap); [Stonks Capital, "The Day All My Uncorrelated Signals Failed Together"](https://stonkscapital.substack.com/p/the-day-all-my-uncorrelated-signals)
- [VENDOR] Concretum Group "Identifying Stocks to Fade" (paywalled, May 2026): January 2012 - mid-May 2026, gross of costs: CAGR about 98%, Sharpe about 2.08, maximum drawdown about 67%; selection rules not visible. — [Concretum Group](https://concretumgroup.substack.com/p/identifying-stocks-to-fade)
- [ACADEMIC, thesis] University of Turku thesis, US 2011-2024: a gap-reversal long-short strategy earns a large, significant gross alpha, but after estimated bid-ask spreads and commissions the net alpha is clearly negative; the reversal is strongest in small, illiquid stocks. — [Turku thesis PDF](https://www.utupub.fi/bitstreams/88057d2a-1ee8-4c05-9592-c535a21b502c/download)
- [ACADEMIC] Stübinger & Schneider (JRFM 2019): overnight-gap mean reversion in S&P 500 stocks, 51.47% p.a., Sharpe 2.38 after transaction costs (large caps; not transferable to low-float names). — [FAU record](https://open.fau.de/handle/openfau/11837)
- [PRACTITIONER] SMB Training gap study: restricting to gaps of 20 bp - 5% gave about 5,822 trades with a 72% win ratio; suggests avoiding very large gaps. — [SMB Training, Gap Study (3/3)](https://www.smbtraining.com/blog/gap-study-33)
- [PRACTITIONER, overfit example] A TradingView "Gapper SHORT Signal" advertises an 81.8% win rate built on 166 gappers over 70 trading days. — [TradingView](https://kr.tradingview.com/script/WuHhPb6z-Gapper-SHORT-Signal)
- [VENDOR] Kris Verma's playbook on Tradezella: in recent years, higher volume and more participants make failed fades more likely to squeeze before falling. — [Tradezella, small-cap shorting playbook](https://www.tradezella.com/strategies/shorting-strategy)

**Academic: hard-to-borrow / short-sale constraints and returns, with and without costs**
- [ACADEMIC] Muravyev, Pearson & Pollet, "Anomalies and Their Short-Sale Costs" (JF 2025): across 162 anomalies, average long-short return about 0.14-0.15%/month before short-sale costs, all from the short leg; about -0.01% to -0.02% after borrow fees; anomalies are not profitable even before fees if high-fee observations (12% of stock-dates) are excluded; typical fee 0.375%/yr with a long right tail; sample excluded stocks below $1 or $50M market cap. — [WealthManagement summary](https://www.wealthmanagement.com/equities/do-short-sale-costs-explain-anomaly-returns); [CXO Advisory](https://cxoadvisory.com/short-selling/shorting-costs-kill-stock-return-anomalies)
- [ACADEMIC] Drechsler & Drechsler, "The Shorting Premium and Asset Pricing Anomalies" (NBER w20282): cheap-minus-expensive-to-short portfolio earned 1.43%/month gross, 0.91% net of fees, 1.53% four-factor alpha (Jan 2004 - Oct 2012); eight major anomalies including MAX "effectively disappear" in the 80% of stocks with low fees and are greatly amplified among high-fee stocks. — [NBER](https://www.nber.org/papers/w20282); [CXO summary](https://www.cxoadvisory.com/short-selling/shorting-fee-as-a-stock-return-predictor/)
- [ACADEMIC] Engelberg, Evans, Leonard, Reed & Ringgenberg, "The Loan Fee Anomaly: A Short Seller's Best Ideas" (Management Science 2025): loan fees are the strongest cross-sectional predictor among 102 anomalies, 4.01%/month long-short in the published version (1.17% in the working paper). — [Counterpoint Funds summary](https://counterpointfunds.com/?p=22649)
- [ACADEMIC] 1926-1933 US stock-lending data (Jones & Lamont): stocks that were expensive to short or that entered the loan market had high valuations and low subsequent returns. — [Swedroe, ETF.com](https://www.etf.com/sections/index-investor-corner/swedroe-short-selling-has-its-uses)
- [VENDOR/asset manager] Dimensional, 14 lending markets, 2011-2018: high-fee stocks underperform over the next several days, more so in small caps; persistence of high-fee status is not predictable and "exploitation frictions are high." — [Dimensional](https://www.dimensional.com/us-en/insights/securities-lending-fees-as-a-short-term-driver-of-stock-returns)

**Market-structure limits: SSR (Rule 201), LULD halts, squeezes, borrow availability**
- [REGULATOR] Rule 201 (SSR) is triggered when a stock falls 10% or more from the prior day's close; it then restricts short sales to prices above the national best bid for the rest of that day and the next day. — [SEC adopting release 34-61595](https://www.sec.gov/rules/final/2010/34-61595fr.pdf)
- [ACADEMIC] Barardehi, Bird, Karolyi & Ruchti, "Are Short-Selling Restrictions Effective?" (Management Science 2025): comparing stocks just either side of the -10% trigger in the same hour, Rule 201 lowers short-sale volume 8% and raises daily returns 35 bp, and the price effect does not reverse after the restriction lifts. — [IDEAS](https://ideas.repec.org/a/inm/ormnsc/v71y2025i5p3829-3851.html)
- [REGULATOR] LULD (9:30-4:00 ET only): Tier 2 bands are 10% for stocks above $3.00, 20% for $0.75-$3.00, and the lesser of $0.15 or 75% below $0.75; bands double from 3:35-4:00 pm for Tier 2 stocks at or below $3.00; bands move with a 5-minute average reference price; a limit state not resolved in 15 seconds becomes a 5-minute pause that the listing market can extend another 5 minutes on an imbalance. — [FINRA, Guardrails for Market Volatility](https://www.finra.org/investors/insights/guardrails-market-volatility); [Nasdaq LULD FAQ](https://m.nasdaqtrader.com/content/MarketRegulation/LULD_FAQ.pdf)
- [REGULATOR] SEC DERA (Hughes): LULD Amendment 10 cut trading pauses by more than 75%, with the biggest drop in Tier 2 and in the first 30 minutes. — [SEC DERA white paper](https://www.sec.gov/dera/staff-papers/white-papers/dera_wp_effect_of_amendment_10_of_luld_pilot_plan)
- [ACADEMIC] Loan fees jump and loan supply shrinks after extreme past returns (Engelberg, Reed & Ringgenberg, above) — i.e. borrow gets scarce and expensive exactly on runner days. — [Wharton PDF](https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/03/riggenberg.pdf)
- [PRESS] Squeeze tail example: DryShips (DRYS) was halted after gaining more than 2,000% in a matter of days in the post-election squeeze wave (the article dates from November 2016). — [Benzinga](https://www.benzinga.com/amp/content/8719057)
- [BROKER] Alpaca docs: opening shorts only in easy-to-borrow (ETB) securities; an open short order in a stock that moves ETB→HTB overnight is cancelled before the open; existing shorts that turn HTB accrue a daily borrow fee and can be recalled; HTB rates are not provided via the API. — [Alpaca docs, Margin and Short Selling](https://docs.alpaca.markets/docs/margin-and-short-selling)
- [BROKER] Alpaca has since announced hard-to-borrow short selling with API locates (check availability, control locate cost, then short); a June 2026 summary lists it as new. Launch date and fee schedule not confirmed. — [Alpaca blog, HTB trading with locates](https://alpaca.markets/blog/htb-trading-api-locates/); [Alpaca, ETB borrow fees eliminated](https://alpaca.markets/blog/zero-borrow-fees-on-short-selling-etb-stock-shares-alpaca-trading-api/)

**Backtest-quality warnings**
- [ACADEMIC] Survivorship bias in small-cap backtests is material: a study of India's small-cap index found that a backtest using only current constituents silently excluded 1,185 stocks. Vendor and practitioner gapper samples above do not say whether delisted symbols are included. — [arXiv 2603.19380](https://arxiv.org/pdf/2603.19380)

**Who actually makes money trading this way (context for vendor claims)**
- [ACADEMIC] Chague, De-Losso & Giovannetti, "Day Trading for a Living?": of 19,646 Brazilians who day-traded index futures for at least 300 days (2013-2015), 97% lost money and only 0.4% earned more than a bank teller's wage; no evidence of learning. — [FGV repository](https://repositorio.fgv.br/items/e87d04fc-4b4c-4a56-ab5a-1c84c1afde1b/full)
- [ACADEMIC] Barber, Lee, Liu & Odean (Taiwan, full exchange records): fewer than 3% of day traders predictably earn profits net of costs. — [Barber et al. PDF, Haas](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf); [CXO summary](https://www.cxoadvisory.com/individual-investing/do-day-traders-make-money/)

### Inferences
- A ~70% "closes red" rate is not an edge by itself: the payoff is short a right-skewed distribution (many modest wins, rare 100%+ squeezes and multi-pause halts). The Stonks Capital and Turku results both say the edge is fragile after realistic stops, borrow and spread costs, and the live record was weaker than the backtest - consistent with the owner's rule that live results outrank replays.
- SSR mostly does not bind on day one of a gap-up (the stock is far above the prior close); it binds on day two or later once a runner falls 10% below the prior close, which is when "first red day" shorts are taken. LULD pauses can trap a short (or a long) for 5-10 minutes at a time during 9:30-4:00; there are no LULD pauses in premarket, where moves are unbounded.
- For this bot specifically: day-one low-float runners are often hard to borrow (not measured here; follows from the loan-supply evidence above), and under Alpaca's ETB-only rule a non-ETB name cannot be shorted at all; the newer HTB/locate API would add a per-trade locate cost that must be counted before any short-side test is judged. The academic evidence (Muravyev et al.; Drechsler) says the fee is roughly the size of the anomaly.
- The academic "hard-to-borrow stocks underperform" results are monthly, cross-sectional and mostly exclude sub-$1 / sub-$50M stocks; they do not show an intraday edge in shorting day-one runners.
- Reading vendor numbers: SmallCapLab sells a short-side product, Dux/Warrior-style figures come from course marketing, and Stonks Capital reports its own strategy; samples, filters and delisting treatment are undisclosed. Single-ticker stats and short-window indicators (166 gappers, 70 days) are cherry-picks. "Eight-figure trader" stories sit beside academic findings that 97% of persistent day traders lose (Brazil) and fewer than 3% are predictably profitable (Taiwan). Gross results (Concretum 98% CAGR, 67% drawdown) are not net results (Turku: net alpha negative in small illiquid stocks).
- The base-rate fade evidence is still useful for the long side: it argues for taking long profits into the first push and not holding a big gapper into the afternoon without a fresh reason.

### Gaps
- No peer-reviewed, cost-inclusive backtest of shorting US low-float day-one gappers (20%+/50%+/100%+) with realistic locate fees, locate availability, LULD pauses and squeeze stops.
- No public data on typical locate costs (per share or annualised) for day-one runners; no data on how often locates are unavailable.
- No study isolating Rule 201's effect on micro-caps specifically.
- The LULD Plan 2025 annual report (pauses by tier, price and time of day) exists but its tables were not retrievable. — [LULD 2025 Annual Report](https://cdn.luldplan.com/reports/LULD-2025-Annual-Report.pdf)

---

## 5. Long-run returns of extreme daily winners ("MAX", lottery stocks) and pump-and-dump schemes

### Takeaway
Stocks with extreme one-day gains underperform afterwards (the MAX effect, >1%/month decile spread),
most likely from overreaction rather than lottery preference, and the effect lives in hard-to-short stocks.
Promotion-driven small-cap spikes (social-media pumps, ramp-and-dumps) reverse within days, and
regulators have shown repeatedly that the run-up is often engineered.

### Cited Findings
- [ACADEMIC] Bali, Cakici & Whitelaw (JFE 2011), "Maxing Out": stocks with the highest maximum daily return in the past month earn lower future returns; the raw and risk-adjusted return difference between lowest and highest MAX deciles exceeds 1% per month; NYSE/AMEX/NASDAQ, July 1962 - Dec 2005; robust to size, book-to-market, momentum, short-term reversal, liquidity and skewness; controlling for MAX reverses the idiosyncratic-volatility puzzle. — [NBER w14804](https://www.nber.org/papers/w14804.pdf); [Alpha Architect summary](https://alphaarchitect.com/hot-off-the-jfe-press-maxing-out-your-returns/)
- [ACADEMIC] Gorman, Akhtar, Durand & Gould (Critical Finance Review 2022): post-MAX underperformance is general and does not depend on a stock being "lottery-like" ex ante; event-study patterns fit overreaction; a look-ahead-free "first MAX in 21 days" test gives the same conclusion. Their additional analysis shows CAARs for high-MAX stocks of -4.02 over days +1 to +5 vs -0.26 for the control group (units not stated in the extract; check Table 6). — [Critical Finance Review](https://nowpublishers.com/article/Details/CFR-0123); [working paper PDF](https://cfr.ivo-welch.info/published/papers/gorman2021could.pdf); [robustness results](https://ddfe.curtin.edu.au/w1ve-5r50/FirstMaxIn21days_EventStudyResults.pdf)
- [ACADEMIC] Baars & Mohrschladt (2021): immediate price reversals after the MAX day; the effect reverses when the MAX return came from an earnings announcement. — [Univ. Münster record](https://cris-portal.uni-muenster.de/portal/en/publication/80040415)
- [ACADEMIC] The MAX anomaly is among those that "effectively disappear" in low-fee stocks and are amplified in high-fee (hard-to-short) stocks. — [CXO summary of Drechsler & Drechsler](https://www.cxoadvisory.com/short-selling/shorting-fee-as-a-stock-return-predictor/)
- [ACADEMIC] Renault, "Market Manipulation and Suspicious Stock Recommendations on Social Media": unusual spikes of $TICKER tweets about small-cap stocks (activity > prior 7-day mean + 2 SD, at least 20 tweets from 20 users) coincide with a large event-day price rise followed by a sharp reversal over the next trading week; the reversal is stronger when the tweets come from stock promoters; controls for press releases, sentiment and firm characteristics. A secondary summary (Oct 2014 - Sep 2015) gives about +6.5% abnormal return on the event day and -2.5% over the next five days vs the NASDAQ MicroCap index (not verified against the paper). — [Renault paper (readkong copy)](https://www.readkong.com/page/market-manipulation-and-suspicious-stock-recommendations-on-2842714); [CXO Advisory summary](https://www.cxoadvisory.com/?p=30149)
- [REGULATOR] SEC enforcement pattern (allegations): promoters build demand, sell into it, and "once the promotional efforts stopped, demand subsided and prices dropped." — [Constantine Cannon summary of 2014 SEC case](https://constantinecannon.com/?p=12630); [SEC litigation release LR-23953 (2017 case)](https://www.sec.gov/litigation/litreleases/2017/lr23953.htm)
- [REGULATOR] ASIC Report 732 reviewed a series of 2020-21 pump-and-dump events in listed micro-caps with a high impact on traded prices (Australia; findings tables not retrieved). — [ASIC REP 732](https://download.asic.gov.au/media/1o1adudd/rep732-published-14-july-2022.pdf)
- [ACADEMIC] Longer-horizon after-run underperformance in related settings: high overnight-return (sentiment) stocks underperform over the following year (Aboody et al., section 1); no-warrant RDO issuers lose ~25.6% market-adjusted over three years (section 3); reverse-split firms show negative 3-year abnormal returns (section 2). — [Aboody et al.](https://anderson-review.ucla.edu/wp-content/uploads/2021/03/Aboody-et-al_overnight_returns_and_firmspecific_investor_sentiment_JFQA2018.pdf); [Kennesaw RDO paper](https://www.kennesaw.edu/coles/research/docs/fall-2024/fall-24-04.pdf); [Kim, Klein & Rosenfeld](https://ideas.repec.org/a/bla/finmgt/v37y2008i2p173-192.html)

### Inferences
- The multi-day to multi-month drift after extreme winners is negative on average, but it is concentrated in the stocks that are hardest and most expensive to short; for a long-only intraday bot the practical lesson is "do not hold runners for days without a fundamental reason," not "short them."
- Promotion-driven spikes reverse within about a week (Renault) and regulators now suspend such names for weeks; holding a promoted small cap overnight carries both reversal risk and halt/suspension risk.
- Earnings- and analyst-confirmed moves are the documented exception where continuation is the norm (Savor; Baars & Mohrschladt).

### Gaps
- No academic study isolates US stocks that rose 50%+ or 100%+ in a single day and tracks next-day / next-5-day returns by float, price and news type; the MAX literature uses monthly portfolios across all stocks.
- Kumar (2009) and other "lottery stock" demand papers were not retrieved in this pass.
- Academic pump-and-dump studies of the spam era (e.g. Frieder & Zittrain; Böhme & Holz) and Aggarwal & Wu (2006) on manipulation cases were not retrieved; their magnitudes are not included here.

