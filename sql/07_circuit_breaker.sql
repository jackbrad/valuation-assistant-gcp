-- 07 — Circuit breaker metrics (parameters: @as_of, @window_days)

WITH frozen AS (
  SELECT v.property_id, CAST(v.point AS FLOAT64) AS estimate, v.effective_date, v.created_at
  FROM `${PROJECT}.val_core.valuations` v
  WHERE v.purpose = 'frozen_prelist'
),
scored AS (
  SELECT p.submarket, s.sale_id, s.sale_date, CAST(s.price AS FLOAT64) AS price, f.estimate,
    (f.estimate - CAST(s.price AS FLOAT64)) / CAST(s.price AS FLOAT64) AS pct_err,
    (s.sale_type = 'off_market' OR NOT IFNULL(s.estimate_shown_before_list, TRUE)) AS unanchored
  FROM `${PROJECT}.val_core.sales` s
  JOIN `${PROJECT}.val_core.properties` p USING (property_id)
  -- the frozen estimate made just before listing (or 30 days before an off-market sale)
  JOIN frozen f
    ON f.property_id = s.property_id
   AND f.effective_date = COALESCE(DATE_SUB(s.list_date, INTERVAL 1 DAY), DATE_SUB(s.sale_date, INTERVAL 30 DAY))
),
windowed AS (
  SELECT *, sale_date > DATE_SUB(@as_of, INTERVAL @window_days DAY) AS in_window,
         sale_date BETWEEN DATE_SUB(@as_of, INTERVAL 12 + 3 MONTH) AND DATE_SUB(@as_of, INTERVAL @window_days DAY) AS in_baseline
  FROM scored WHERE sale_date <= @as_of
)
SELECT submarket,
  COUNTIF(in_window) AS n_all,
  COUNTIF(in_window AND unanchored) AS n_unanchored,
  APPROX_QUANTILES(IF(in_window, ABS(pct_err), NULL), 100)[OFFSET(50)] AS mdape_all,
  APPROX_QUANTILES(IF(in_window AND unanchored, ABS(pct_err), NULL), 100)[OFFSET(50)] AS mdape_unanchored,
  APPROX_QUANTILES(IF(in_window, pct_err, NULL), 100)[OFFSET(50)] AS signed_bias,
  SAFE_DIVIDE(COUNTIF(in_window AND ABS(pct_err) <= 0.10), COUNTIF(in_window)) AS pct_within_10,
  APPROX_QUANTILES(IF(in_baseline AND unanchored, ABS(pct_err), NULL), 100)[OFFSET(50)] AS baseline_mdape_unanchored
FROM windowed
GROUP BY submarket;

-- jobs/breaker.py applies the trip rules from settings, adds the forecast-slope check from
-- val_core.market_index (is_forecast), writes val_ml.model_eval_runs (role='breaker') and
-- val_ops.breaker_state, and logs `breaker_tripped` as structured JSON for the alert policy.
