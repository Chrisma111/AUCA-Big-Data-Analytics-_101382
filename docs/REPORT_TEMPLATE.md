# Technical Report – skeleton (target 6–8 pages, export to PDF)
> Write each section **in your own words** from your own run; the bullets say *what evidence to paste and from where*.
> Fill every `[…]` with numbers from your run (they differ by SCALE and by the day you generated the data).

## 1. Introduction & objectives (¼ page)
Problem (multi-model analytics on e-commerce data), the three technologies, dataset size you actually used (`SCALE=[…]`: [users] users, [products] products, [sessions] sessions, [orders] orders, 90 days).

## 2. System architecture (1 page)
* Diagram: notebook 05 intro (MongoDB ↔ Spark ↔ HBase) – redraw it as a figure.
* One sentence per component: *what it stores, why that engine*.
* Data flow: generator → JSON → (Mongo | HBase | Parquet) → Spark → CSV → charts.

## 3. Data modeling and rationale (1½ pages)  — *Part 1, 35 % "Technology & design" criterion*
### 3.1 MongoDB
Table: collection | embedded vs referenced | why | query it serves. Use the 5 rules in notebook 01. Mention: dates → `datetime`; `cart_contents` dynamic keys → array (attribute pattern); denormalised `category_id` on items; `$merge`d `purchase_summary`; 9 indexes + the `explain` result (docs examined with/without index: [..] vs [..]).
### 3.2 HBase
Row-key tables from notebook 02: `user#reverse_ts#session` and `product#date`; column families; reverse timestamp; zero padding; hot-spotting/salting/pre-split discussion; prefix-vs-full-scan timing ([..] ms vs [..] s).
### 3.3 Why this data is in MongoDB vs HBase
Comparison table (access pattern, query flexibility, scaling, consistency, write path, what each is bad at).

## 4. Spark processing pipelines (1 page)  — *Part 2*
Pipeline diagram (notebook 03 top). Cleaning rules + `data_quality_report.csv` table. Recommendation method (support/confidence/lift) **and the null-model finding** (affinity not distinguishable from chance). Cohort method incl. the exposure-fair 30-day periods. Spark SQL: list 3–4 representative queries (window functions, NTILE, PIVOT, cross-system join) – full text in `outputs/spark_sql_queries.sql`. Optimisation table + measured numbers (Step 8).

## 5. Integrated analytics (1 page)  — *Part 3*
For **each** of the two queries: business question → data sources (which system) → processing steps (where Spark joins) → why these technologies → performance. State whether MongoDB/HBase were **live or simulated** in your run.

## 6. Results, visualizations & insights (1½ pages)  — *Part 4, 30 % "Analytics quality"*
Embed `outputs/figures/01…08` (at least 4; pick the ones you discuss). Use `outputs/key_findings.md` for the numbers. Give 4–5 **actionable recommendations**, each tied to a figure (list at the end of notebook 06).

## 7. Scalability (½ page)
Spark (add executors, Parquet partitioning by date, shuffle partitions, `hdfs://`/`s3://`); MongoDB (sharding key choice e.g. `user_id`, hashed; index memory); HBase (regions, pre-splits, salting; per-user read latency independent of table size). Be explicit: you ran `SCALE=[…]`, the 2 M-session generation needs 15+ GB RAM because the generator holds everything in memory – streaming generation would fix it.

## 8. Technology selection justification (¼ page)
One table: task → technology → reason (key lookups/time-series → HBase; flexible aggregations on nested docs → MongoDB; full scans, joins across sources, ML → Spark).

## 9. Methodology notes (¼ page)
Net revenue = item subtotal × (total / order subtotal); margin = category average; CLV formula + assumptions (retention [0.90], discount [0.01]) + time-split validation; KMeans k by silhouette; funnel stages strict.

## 10. Limitations & future work (½ page)  — *Innovation & critical thinking, 10 %*
* No `subcategory_id` on products → margins only per category; no age → no age-group segmentation.
* `conversion_status` over-reports conversions by [..]%; ~[..]% of orders have no session.
* Synthetic uniform-random behaviour: co-view lift ≈ null model, flat cohorts/timing, R² ≈ 0 – the *pipelines* are valid, the *business conclusions* are not transferable.
* Only 90 days → churn cannot be observed; CLV rests on assumptions (sensitivity: [..]).
* Single-node Docker; connector-based reads (Mongo-Spark, HBase-Spark) and a streaming path (Spark Structured Streaming → HBase counters) are future work.
