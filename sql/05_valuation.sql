-- 05 — Valuation inputs. The math itself lives in valuation/engine.py (pure, unit-tested).

-- 5.1 Candidate comps for a subject (parameters: @pid, @eff_date, @radius_m, @lookback_months)
WITH subject AS (
  SELECT p.property_id, p.geo, p.submarket, p.property_type, f.*
    EXCEPT(property_id, submarket, property_type, fact_ids, has_held_value_fact, built_at)
  FROM `${PROJECT}.val_core.properties` p
  JOIN `${PROJECT}.val_core.property_features` f USING (property_id)
  WHERE p.property_id = @pid
)
SELECT
  s.sale_id, s.property_id AS comp_property_id, s.sale_date, CAST(s.price AS FLOAT64) AS price,
  ST_DISTANCE(p.geo, subj.geo) / 1609.34 AS dist_mi,
  DATE_DIFF(@eff_date, s.sale_date, DAY) / 30.44 AS months_since_sale,
  f.gla_sqft, f.beds, f.baths_total, f.age_yrs, f.lot_sqft, f.pool, f.garage_spaces,
  f.condition_c, f.quality_q, p.submarket,
  SAFE_DIVIDE(f.gla_sqft - subj.gla_sqft, subj.gla_sqft) AS gla_diff_pct,
  f.beds - subj.beds AS beds_diff,
  f.baths_total - subj.baths_total AS baths_diff,
  f.age_yrs - subj.age_yrs AS age_diff_yrs,
  SAFE_DIVIDE(f.lot_sqft - subj.lot_sqft, subj.lot_sqft) AS lot_diff_pct,
  f.condition_c - subj.condition_c AS condition_diff,
  f.quality_q - subj.quality_q AS quality_diff,
  p.submarket = subj.submarket AS same_submarket,
  f.pool != subj.pool AS pool_mismatch
FROM `${PROJECT}.val_core.sales` s
JOIN `${PROJECT}.val_core.properties` p ON p.property_id = s.property_id
JOIN `${PROJECT}.val_core.property_features` f ON f.property_id = s.property_id
CROSS JOIN subject subj
WHERE s.sale_type = 'arms_length'
  AND p.property_type = subj.property_type
  AND s.property_id != subj.property_id
  AND s.sale_date < @eff_date
  AND s.sale_date >= DATE_SUB(@eff_date, INTERVAL @lookback_months MONTH)
  AND ST_DWITHIN(p.geo, subj.geo, @radius_m);

-- 5.2 Rank candidates with the champion comp ranker
-- SELECT sale_id, (SELECT prob FROM UNNEST(predicted_accepted_probs) WHERE label) AS rank_score
-- FROM ML.PREDICT(MODEL `${PROJECT}.val_ml.<champion comp_ranker>`, (<5.1>));

-- 5.3 Time factor for each comp: index[eff_month] / index[sale_month] (forecast row if needed)
-- 5.4 Adjustment grid: SELECT feature, dollars_per_unit FROM val_ml.adjustment_grid
--     WHERE submarket = @submarket AND model_name = <champion adj model>
-- 5.5 AVM point + drivers: ML.PREDICT / ML.EXPLAIN_PREDICT on the subject's features

-- 5.6 Dependents of a corrected property (cascade)
-- Latest valuation per subject where the corrected property is the subject or a used comp
WITH latest AS (
  SELECT * EXCEPT(rn) FROM (
    SELECT v.*, ROW_NUMBER() OVER (PARTITION BY property_id, purpose ORDER BY created_at DESC) AS rn
    FROM `${PROJECT}.val_core.valuations` v
    WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_days DAY)
      AND purpose != 'frozen_prelist'
  ) WHERE rn = 1
)
SELECT l.valuation_id, l.property_id, l.effective_date, l.purpose, 'subject' AS relation
FROM latest l WHERE l.property_id = @corrected_pid
UNION DISTINCT
SELECT l.valuation_id, l.property_id, l.effective_date, l.purpose, 'comp_dependent'
FROM latest l
JOIN `${PROJECT}.val_core.valuation_comps` c USING (valuation_id)
WHERE c.comp_property_id = @corrected_pid AND c.used;
