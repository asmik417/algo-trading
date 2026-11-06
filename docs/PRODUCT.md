# Product: AI Trade Assistant (paper-trading strategy lab)

Personal project for three people: the developer, their manager and the MD. No clients, no other companies, no real money. The goal is a tool that **suggests stocks under a trader's own parameters, tracks every suggestion with fake money, and grades its own accuracy** so the parameters and the algo improve over time.

## The loop the product exists to run

1. A trader (or CA) opens **Account** and sets the parameters the algo screens on. Saved as a named profile. The active profile is chosen from the account dropdown in the sidebar.
2. **Stocks → Algo Suggested** lists the stocks the algo picks under the active profile, with a score, stage and signal. Clicking a stock opens a dialog with:
   - why it was listed (reasons built from computed numbers, narrated in plain English),
   - its analysis over time (price chart with moving averages, score breakdown, fundamentals),
   - the **right price and right time to buy** (three entry levels and a timing note),
   - a **planned exit**: target price, stop-loss, holding horizon and planned exit date,
   - the disclaimer: *"This plan may vary with news and live market updates."*
3. **Stocks → Explore** shows every NSE stock, searchable like Groww, with the same dialog available on demand ("analyse under my parameters").
4. **Tracker** simulates ₹10,000 (configurable per profile) invested on the suggestion day in every stock the user chooses to track. The daily job marks each position to market, closes it on stop or target, and flags it as *due* when the planned exit date arrives. Extending or shortening the horizon **requires a reason**, which is logged, so we can later see whether extensions helped.
5. **Loss Analysis** lists every closed losing position until it has a review: tagged reasons, the mistake, the lesson, and the parameter or algo change it suggests. Tag counts per profile show what keeps going wrong.
6. **Backtest** replays a strategy over past dates with the engine blind to anything after each scan date, simulates every pick with the Tracker's rules, and reports win rate, expectancy, drawdown, breakdowns and auto-tagged loss patterns. It is how parameters get tested in hours instead of months; the Tracker then confirms on live data.

## Success metrics the UI must surface

- Win rate per profile (closed positions with positive P&L ÷ closed positions).
- Average gain on winners, average loss on losers, total paper P&L.
- How often the target was hit vs the stop vs horizon expiry.
- How many extensions were made and how many of them ended better than closing on the original date.
- Pending loss reviews (discipline metric).

## Out of scope for this phase

Real orders, broker APIs, SEBI algo registration, authentication beyond the profile dropdown, mobile apps.

## Vocabulary

| Term | Meaning |
|---|---|
| Profile | A named set of screening parameters, owned by one person. Acts as the "account". |
| Run | One execution of the algo for one profile on one trading day. |
| Suggestion | One stock in a run's output, with its plan frozen at suggestion time. |
| Position | A paper trade opened from a suggestion (or a symbol) with the profile's paper capital. |
| Mark | The daily valuation of an open position at that day's close. |
| Event | An audit entry on a position: open, extend, shorten, due, close, note. |
| Review | The loss-analysis entry for a closed losing position. |
| Stage | Where a stock is in its setup: Fundamental Change → Quiet Accumulation → Volume Expansion → Breakout → Momentum → Extended. |
| Signal | User-facing label: Early Setup, Developing, Breakout Confirmed, Extended, Weak. |
