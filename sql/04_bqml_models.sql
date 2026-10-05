-- 04 — BQML models. Version suffix ${V} (e.g. v20261003_1). Aliases in val_ml.model_aliases.

-- 4.0 Training base: arm's-length sales joined to features as of sale
CREATE OR REPLACE VIEW `${PROJECT}.val_ml.sales_features` AS
SELECT s.sale_id, s.property_id, s.sale_date, DATE_TRUNC(s.sale_date, MONTH) AS sale_month,
       CAST(s.price AS FLOAT64) AS price, s.sale_type, s.was_listed, s.estimate_shown_before_list,
       f.* EXCEPT(property_id, fact_ids, has_held_value_fact, built_at)
FROM `${PROJECT}.val_core.sales` s
JOIN `${PROJECT}.val_core.property_features` f USING (property_id)
WHERE s.sale_type IN ('arms_length', 'off_market');

-- 4.1 Market index (monthly median $/sq ft) — history
CREATE OR REPLACE TABLE `${PROJECT}.val_ml.ppsf_monthly` AS
SELECT submarket, sale_month AS month,
       APPROX_QUANTILES(price / gla_sqft, 100)[OFFSET(50)] AS median_ppsf,
       COUNT(*) AS n_sales
FROM `${PROJECT}.val_ml.sales_features`
GROUP BY submarket, month;

CREATE OR REPLACE MODEL `${PROJECT}.val_ml.market_index_arima_${V}`
OPTIONS (
  model_type = 'ARIMA_PLUS',
  time_series_timestamp_col = 'month',
  time_series_data_col = 'median_ppsf',
  time_series_id_col = 'submarket',
  data_frequency = 'MONTHLY'
) AS
SELECT month, submarket, median_ppsf FROM `${PROJECT}.val_ml.ppsf_monthly`;

-- Smoothed history (3-month rolling) + 6-month forecast into val_core.market_index
-- (jobs/retrain.py: DELETE rows for model_version, then INSERT both parts)
-- history:
--   SELECT submarket, month, AVG(median_ppsf) OVER (PARTITION BY submarket ORDER BY month
--          ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), n_sales, FALSE, '${V}', CURRENT_TIMESTAMP()
-- forecast:
--   SELECT submarket, DATE(forecast_timestamp), forecast_value, NULL, TRUE, '${V}', CURRENT_TIMESTAMP()
--   FROM ML.FORECAST(MODEL `${PROJECT}.val_ml.market_index_arima_${V}`, STRUCT(6 AS horizon))

-- 4.2 Time-adjusted sales (to latest actual month)
CREATE OR REPLACE VIEW `${PROJECT}.val_ml.sales_time_adjusted` AS
WITH idx AS (
  SELECT submarket, month, median_ppsf FROM `${PROJECT}.val_core.market_index` WHERE NOT is_forecast
),
latest AS (SELECT submarket, ARRAY_AGG(median_ppsf ORDER BY month DESC LIMIT 1)[OFFSET(0)] AS ppsf_now FROM idx GROUP BY submarket)
SELECT sf.*, l.ppsf_now / i.median_ppsf AS time_adj_factor,
       sf.price * l.ppsf_now / i.median_ppsf AS price_time_adj
FROM `${PROJECT}.val_ml.sales_features` sf
JOIN idx i ON i.submarket = sf.submarket AND i.month = sf.sale_month
JOIN latest l ON l.submarket = sf.submarket;

-- 4.3 Comp ranker
CREATE OR REPLACE MODEL `${PROJECT}.val_ml.comp_ranker_${V}`
OPTIONS (model_type = 'BOOSTED_TREE_CLASSIFIER', input_label_cols = ['accepted'],
         max_iterations = 50, enable_global_explain = TRUE) AS
SELECT dist_mi, months_since_sale, gla_diff_pct, beds_diff, baths_diff, age_diff_yrs,
       lot_diff_pct, condition_diff, quality_diff, same_submarket, pool_mismatch, accepted
FROM `${PROJECT}.val_ops.comp_feedback`
WHERE approved;

-- 4.4 Adjustment grid, one LINEAR_REG per submarket (run per submarket; ${SUBMARKET_SLUG})
CREATE OR REPLACE MODEL `${PROJECT}.val_ml.adj_${SUBMARKET_SLUG}_${V}`
OPTIONS (model_type = 'LINEAR_REG', input_label_cols = ['price_time_adj'],
         l2_reg = 1.0, enable_global_explain = TRUE) AS
SELECT gla_sqft, beds, baths_total, age_yrs, lot_sqft, pool, garage_spaces,
       condition_c, quality_q, price_time_adj
FROM `${PROJECT}.val_ml.sales_time_adjusted`
WHERE submarket = '${SUBMARKET}' AND sale_type = 'arms_length';

-- coefficients → adjustment grid (clamps applied in Python, clamped flag recorded)
-- SELECT processed_input AS feature, weight AS dollars_per_unit
-- FROM ML.WEIGHTS(MODEL `${PROJECT}.val_ml.adj_${SUBMARKET_SLUG}_${V}`)
-- WHERE processed_input != '__INTERCEPT__';

-- 4.5 AVM with a time-based split
CREATE OR REPLACE MODEL `${PROJECT}.val_ml.avm_${V}`
OPTIONS (model_type = 'BOOSTED_TREE_REGRESSOR', input_label_cols = ['price_time_adj'],
         data_split_method = 'CUSTOM', data_split_col = 'is_eval',
         max_iterations = 100, enable_global_explain = TRUE) AS
SELECT gla_sqft, beds, baths_total, age_yrs, lot_sqft, pool, garage_spaces,
       condition_c, quality_q, submarket, property_type, lat, lng,
       price_time_adj,
       sale_date >= DATE_SUB((SELECT MAX(sale_date) FROM `${PROJECT}.val_core.sales`), INTERVAL 4 MONTH) AS is_eval
FROM `${PROJECT}.val_ml.sales_time_adjusted`;

-- Drivers for a subject
-- SELECT * FROM ML.EXPLAIN_PREDICT(MODEL `${PROJECT}.val_ml.avm_${V}`,
--   (SELECT ... FROM `${PROJECT}.val_core.property_features` WHERE property_id = @pid),
--   STRUCT(5 AS top_k_features));
