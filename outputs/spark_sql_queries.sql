-- Spark SQL queries used in notebook 04 (run against Parquet views produced by notebook 03)

-- top_products_per_category
WITH prod_rev AS (
    SELECT product_id, product_name, category_id, category_name,
           SUM(item_net_revenue) AS net_revenue, SUM(quantity) AS units
    FROM transaction_items
    GROUP BY product_id, product_name, category_id, category_name
), ranked AS (
    SELECT *, RANK() OVER (PARTITION BY category_id ORDER BY net_revenue DESC) AS rnk
    FROM prod_rev
)
SELECT category_name, rnk, product_id, product_name, ROUND(net_revenue, 2) AS net_revenue, units
FROM ranked WHERE rnk <= 3
ORDER BY category_name, rnk;

-- daily_revenue_ma
WITH daily AS (
    SELECT txn_date, COUNT(*) AS orders, SUM(total) AS revenue
    FROM transactions WHERE is_valid
    GROUP BY txn_date
)
SELECT txn_date, orders, ROUND(revenue, 2) AS revenue,
       ROUND(AVG(revenue) OVER (ORDER BY txn_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS revenue_ma7,
       ROUND((revenue - LAG(revenue, 7) OVER (ORDER BY txn_date)) / LAG(revenue, 7) OVER (ORDER BY txn_date) * 100, 1) AS wow_growth_pct
FROM daily ORDER BY txn_date;

-- rfm
WITH base AS (
    SELECT user_id, MAX(txn_date) AS last_order, COUNT(*) AS frequency, SUM(total) AS monetary
    FROM transactions WHERE is_valid GROUP BY user_id
), ref AS (SELECT MAX(txn_date) AS ref_date FROM transactions),
rfm AS (
    SELECT b.user_id, DATEDIFF(r.ref_date, b.last_order) AS recency_days, b.frequency, ROUND(b.monetary, 2) AS monetary
    FROM base b CROSS JOIN ref r
), scored AS (
    SELECT *,
           NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,    -- recent = high score
           NTILE(5) OVER (ORDER BY frequency)         AS f_score,
           NTILE(5) OVER (ORDER BY monetary)          AS m_score
    FROM rfm
)
SELECT *, CASE WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
               WHEN f_score >= 4                  THEN 'Loyal'
               WHEN r_score >= 4                  THEN 'Recent'
               WHEN r_score <= 2 AND f_score <= 2 THEN 'At risk'
               ELSE 'Regular' END AS segment
FROM scored;

-- funnel_by_device
SELECT device_type,
       COUNT(*)                                                    AS sessions,
       SUM(CASE WHEN viewed_product_page THEN 1 ELSE 0 END)        AS viewed_product,
       SUM(CASE WHEN has_cart THEN 1 ELSE 0 END)                   AS added_to_cart,
       SUM(CASE WHEN reached_checkout THEN 1 ELSE 0 END)           AS reached_checkout,
       SUM(CASE WHEN is_purchased THEN 1 ELSE 0 END)               AS purchased,
       ROUND(100.0 * SUM(CASE WHEN is_purchased THEN 1 ELSE 0 END) / COUNT(*), 2) AS purchase_rate_pct,
       ROUND(100.0 * SUM(CASE WHEN conversion_status_raw = 'converted' THEN 1 ELSE 0 END) / COUNT(*), 2) AS raw_converted_pct
FROM sessions GROUP BY device_type ORDER BY sessions DESC;

-- category_conversion
WITH v AS (SELECT category_id, COUNT(*) AS product_views FROM page_views
           WHERE page_type = 'product_detail' AND category_id IS NOT NULL GROUP BY category_id),
c AS (SELECT p.category_id, COUNT(*) AS cart_adds FROM cart_items ci JOIN products p ON ci.product_id = p.product_id GROUP BY p.category_id),
s AS (SELECT category_id, SUM(quantity) AS units_sold, SUM(item_net_revenue) AS net_revenue, SUM(est_gross_profit) AS est_gross_profit
      FROM transaction_items GROUP BY category_id)
SELECT cat.category_name, v.product_views, c.cart_adds, s.units_sold,
       ROUND(100.0 * c.cart_adds / v.product_views, 2) AS view_to_cart_pct,
       ROUND(s.net_revenue, 0) AS net_revenue, ROUND(s.est_gross_profit, 0) AS est_gross_profit
FROM categories cat JOIN v ON cat.category_id = v.category_id JOIN c ON cat.category_id = c.category_id JOIN s ON cat.category_id = s.category_id
ORDER BY net_revenue DESC;

-- product_views_vs_sales
WITH v AS (SELECT product_id, COUNT(*) AS views FROM page_views WHERE page_type = 'product_detail' AND product_id IS NOT NULL GROUP BY product_id),
     s AS (SELECT product_id, SUM(quantity) AS units_sold, SUM(item_net_revenue) AS net_revenue FROM transaction_items GROUP BY product_id)
SELECT p.product_id, p.product_name, p.category_name, p.current_price,
       COALESCE(v.views, 0) AS views, COALESCE(s.units_sold, 0) AS units_sold, ROUND(COALESCE(s.net_revenue, 0), 2) AS net_revenue
FROM products p LEFT JOIN v ON p.product_id = v.product_id LEFT JOIN s ON p.product_id = s.product_id
ORDER BY views DESC;

-- hour_dow
WITH t AS (SELECT dow_num, day_of_week, hour, COUNT(*) AS sessions FROM sessions GROUP BY dow_num, day_of_week, hour),
     r AS (SELECT dayofweek(txn_date) AS dow_num, hour(txn_ts) AS hour, COUNT(*) AS orders, SUM(total) AS revenue
           FROM transactions WHERE is_valid GROUP BY dayofweek(txn_date), hour(txn_ts))
SELECT t.dow_num, t.day_of_week, t.hour, t.sessions, COALESCE(r.orders, 0) AS orders, ROUND(COALESCE(r.revenue, 0), 2) AS revenue
FROM t LEFT JOIN r ON t.dow_num = r.dow_num AND t.hour = r.hour
ORDER BY t.dow_num, t.hour;

-- payment_status_pivot
SELECT * FROM (SELECT payment_method, status, total FROM transactions WHERE is_valid)
PIVOT (ROUND(SUM(total), 0) FOR status IN ('completed', 'processing', 'shipped', 'delivered'))
ORDER BY payment_method;

-- country_revenue
SELECT u.country, COUNT(DISTINCT u.user_id) AS buyers, COUNT(*) AS orders,
       ROUND(SUM(t.total), 0) AS revenue, ROUND(AVG(t.total), 2) AS avg_order_value
FROM transactions t JOIN users u ON t.user_id = u.user_id
WHERE t.is_valid GROUP BY u.country ORDER BY revenue DESC LIMIT 15;

-- xsys_engagement_vs_spend
WITH j AS (
    SELECT m.user_id, m.country, m.orders, m.total_spent, h.sessions, h.total_seconds, h.total_page_views,
           NTILE(3) OVER (ORDER BY h.sessions) AS eng_tercile
    FROM mongo_users m JOIN hbase_engagement h ON m.user_id = h.user_id
)
SELECT CASE eng_tercile WHEN 1 THEN '1 - low engagement' WHEN 2 THEN '2 - medium' ELSE '3 - high engagement' END AS engagement,
       COUNT(*) AS users, ROUND(AVG(sessions), 1) AS avg_sessions, ROUND(AVG(total_seconds) / 60, 1) AS avg_minutes_browsing,
       ROUND(AVG(orders), 2) AS avg_orders, ROUND(AVG(total_spent), 2) AS avg_spend,
       ROUND(SUM(CASE WHEN orders > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS pct_buyers
FROM j GROUP BY eng_tercile ORDER BY eng_tercile;

-- xsys_lapsing_buyers
WITH ref AS (SELECT MAX(last_session_ts) AS now_ts FROM hbase_engagement)
SELECT m.user_id, m.country, m.orders, ROUND(m.total_spent, 2) AS total_spent,
       DATE(m.last_purchase) AS last_purchase, DATE(h.last_session_ts) AS last_session,
       DATEDIFF(r.now_ts, h.last_session_ts) AS days_since_last_visit
FROM mongo_users m JOIN hbase_engagement h ON m.user_id = h.user_id CROSS JOIN ref r
WHERE m.orders >= 3 AND DATEDIFF(r.now_ts, h.last_session_ts) >= 3
ORDER BY m.total_spent DESC;

