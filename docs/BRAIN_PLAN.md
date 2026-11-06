# The brain: evidence, analyst, market brief, scorecard

This is the plan for turning the assistant from a rules screener into an analyst that reasons over evidence every night and is measured against its own record. It follows the hard rules in `CLAUDE.md`: numbers come from code, the model reasons and writes, nothing it says changes a computed level or date, and every verdict is scored later.

## Why

The rules verdict (Buy / Watch / Avoid, and Add / Hold / Trim / Exit for holdings) is explainable but shallow: it cannot notice that a stock is falling despite great results, that promoters are selling into a rally, or that the whole market has turned risk-off. A good analyst notices those things from evidence. The brain does that, in a fixed method, and the scorecard tells us whether it adds value over the plain rules.

## The method the analyst must follow (Sherlock)

1. **Observe.** List only facts from the evidence pack, each with its figure and date.
2. **What is odd.** Anomalies: price versus fundamentals divergence, volume without news, delivery % falling in a rally, promoter selling or pledging, insider buying, results delayed, auditor change, sector moving without the stock.
3. **Two stories.** The bull case and the bear case, each as a causal chain.
4. **Try to kill both.** What evidence would prove each wrong; is it present, absent, or unknown.
5. **Verdict.** Direction (up / down / sideways) over the next 20 sessions, an action in the same vocabulary as the rules verdict, confidence low / medium / high, the trigger that flips it, and the one thing the analyst most wants to know.

The output is JSON (`AnalystView` in the contract). Every number in it must exist in the evidence pack; an automatic audit rejects the view otherwise and the model is asked once more with the offending numbers listed.

## Pipeline, every trading day at 18:30 IST

```
bhavcopy (exists) → mark positions (exists)
  → pull sources: announcements, results calendar, bulk/block deals, insider trades,
    shareholding + pledges (quarterly), FII/DII flows, indices + VIX, global cues, news headlines
  → point-in-time quarterly results from NSE/BSE filings (with filing date)
  → market brief: regime, breadth, flows, sectors, one paragraph (deterministic facts + model paragraph)
  → evidence pack per stock in every pick list + today's algo suggestions + open positions
  → analyst view per pack (Claude Opus 5.5, extended thinking, web search allowed for news only)
  → verdict log: rules verdict and analyst view both recorded with today's close
  → scorecard marks: every logged verdict re-marked at 20 / 40 / 60 sessions
```

Each step is idempotent per day and cached on disk, so a re-run costs nothing and a failure in one source never blocks the others. A missing source is reported in the pack as "unavailable", never faked.

## Sources

| Data | Source | Module |
|---|---|---|
| Announcements, results calendar, board meetings | NSE corporate announcements API; BSE announcements RSS as fallback | `engine/data/sources/announcements.py` |
| Bulk and block deals | NSE APIs | `sources/deals.py` |
| Insider trades (PIT), SAST | NSE APIs | `sources/insider.py` |
| Shareholding pattern, promoter pledge | NSE APIs, quarterly | `sources/shareholding.py` |
| FII / DII flows, indices, India VIX, advance/decline | NSE APIs | `sources/market.py` |
| Global cues: S&P 500, crude, USD/INR, US 10Y | yfinance | `sources/global_cues.py` |
| News headlines | Google News RSS per company, ET Markets and Moneycontrol RSS | `sources/news.py` |
| Point-in-time quarterly results | NSE corporate financial results (XBRL/JSON) with filing date; BSE fallback | `sources/results.py` |

Rules for pullers: one function `pull(day) -> list[dict]` per source, browser-like session with throttling, cached under `data/cache/sources/<source>/<day>.json`, errors recorded in `source_pulls`, never raise past the job. Scraping Screener, Tickertape or Trendlyne is not allowed.

## Scorecard

Every verdict is logged with its date, source (`rules` or `analyst`), action, direction, level and the close that day. The daily job marks each logged verdict at 20, 40 and 60 sessions. A verdict is **right** when the price change matches its direction: up means close higher, down means close lower, sideways means within ±5 %. The scorecard page shows hit rate by source, by action, by signal and by month, and lists the worst misses. This is the proof the manager sees.

## Build order

1. Sources + point-in-time results (backend). 2. Evidence pack + market brief (backend). 3. Analyst view + audit + verdict log + scorecard (backend). 4. Frontend: market brief banner and page, analyst view in the dialog, scorecard page, overnight changes. 5. Backtest uses point-in-time results when available (removes the biggest caveat).

## Cost

Roughly ₹2 to ₹5 per analyst view with thinking on. 50 stocks a night is a few hundred rupees a month. Sources are free; EODHD (paid) is the fallback if the filings parser proves unreliable.
