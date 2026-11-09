# Key findings (auto-generated from outputs/tables)

- **Revenue trend.** Total revenue 53,926,976 over 91 days (50,000 orders). Daily revenue averages 599,447 with a coefficient of variation of 5%; best day 2026-10-10 (668,503).
- **Categories.** Top category by revenue: Kelly-Santiago (2,597,128); the most profitable is Rodriguez-Graham (747,880 est. profit). Category margins range 18%-36%, so revenue rank and profit rank differ.
- **Popularity.** Views and units sold are correlated (r = 0.70); only 0 of the 10 most-viewed products are also in the 10 best-selling list. Median units sold per view: 0.32. Products with high views but low sales are candidates for price/page review.
- **Funnel.** 12.5% of sessions end in a purchase. Biggest step loss: before 'Reached checkout' (72,134 sessions). The platform's 'converted' flag over-reports real conversions by 62%.
- **Revenue at stake.** Abandoned carts hold 71,950,644 in cart value; failed checkouts (flagged converted, no order - likely stock-outs) hold another 12,312,826, versus 19,986,282 actually purchased.
- **Channels.** Best referrer search_engine (12.8%) vs worst email (12.1%); device rates span only 0.14 pp. Differences this small on random synthetic data should not drive channel decisions.
- **Customer value.** The top 10% of customers generate 20.6% of projected 12-month profit. Best segment: 'Engaged big spenders' = 41% of customers but 61% of projected profit (avg CLV 4,611).
- **Predictive check.** On held-out users, Linear regression reaches RMSE 1,655 vs 2,054 for the run-rate baseline (19% lower), but R² = -0.00: engagement adds little beyond the average, as expected for synthetic data.
- **Cohorts.** Revenue per cohort user ranges 1,688-1,879 across cohort/period cells; the average by 30-day period is P1: 1,765, P2: 1,806, P3: 1,826. (Equal 30-day periods are used so every cell has the same exposure; compare the spread with the size of the cohorts before reading a trend into it.)
- **Timing.** Busiest slot: Tue 15:00 (1,386 sessions). Variation across the 168 weekday-hour slots is 4% of the mean, versus 3% expected from random counting noise alone: more variable than chance alone would give - a real time-of-day pattern may exist.

## Data-quality caveats that qualify every finding

- **products have subcategory_id?**: False - Assignment text shows it, generator does not create it -> margin only at CATEGORY level (avg of subcategory margins)
- **users have age / birth date?**: False - No age -> 'users by age group' impossible; segment by purchase frequency, registration cohort and geography instead
- **'converted' sessions WITHOUT a transaction**: 15,515 of 40,609 (38%) - conversion_status is NOT reliable (stock failures) -> true purchases are taken from transactions
- **transactions WITHOUT a session**: 24,906 of 50,000 - Roughly half the orders cannot be joined to browsing -> funnel must treat them separately