# Doubling the account in one day — what it takes (BTC perp, 2023-01 → 2026-09)

Days analysed: 1367. Median largest intraday move from prior close: 1.89%; days where it exceeded 5%: 8.9%; exceeded 10%: 0.6%.
Even with perfect foresight of the day's best point, doubling needs leverage ≈ 1 / move: 53× on a median day.

Trend-following direction each day, leverage L, stop at double or liquidation:

| leverage | P(double) | P(liquidated) | median end equity | P(survive 5 days) | P(survive 20 days) | compounded daily growth |
|---|---|---|---|---|---|---|
| 1× | 0.0% | 0.0% | 0.998 | 100.0% | 100.0% | 0.9986 |
| 2× | 0.0% | 0.0% | 0.996 | 100.0% | 100.0% | 0.9967 |
| 5× | 0.0% | 0.0% | 0.990 | 100.0% | 100.0% | 0.9870 |
| 10× | 0.4% | 0.4% | 0.981 | 98.2% | 92.9% | 0.0000 |
| 20× | 4.9% | 4.5% | 0.961 | 79.3% | 39.5% | 0.0000 |
| 50× | 21.8% | 26.8% | 0.907 | 21.1% | 0.2% | 0.0000 |
| 100× | 35.2% | 46.2% | 0.615 | 4.5% | 0.0% | 0.0000 |

Reading: the leverage at which doubling becomes even occasionally possible is the leverage at which liquidation is more likely than doubling, and repeated attempts end in ruin with near certainty. The compounded growth column is 0 whenever any day liquidates — one wipe-out ends the game.
