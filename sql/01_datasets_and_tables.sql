-- 01 — Datasets and tables
-- Placeholders substituted by scripts/run_sql.py: ${PROJECT}, ${BQ_LOCATION}, ${LANDING_BUCKET}

CREATE SCHEMA IF NOT EXISTS `${PROJECT}.val_raw`  OPTIONS (location = '${BQ_LOCATION}');
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.val_core` OPTIONS (location = '${BQ_LOCATION}');
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.val_ml`   OPTIONS (location = '${BQ_LOCATION}');
CREATE SCHEMA IF NOT EXISTS `${PROJECT}.val_ops`  OPTIONS (location = '${BQ_LOCATION}');

-- ---------- val_raw ----------
-- Object table over landed PDFs (connection created by Terraform: ${BQ_LOCATION}.vertex)
CREATE EXTERNAL TABLE IF NOT EXISTS `${PROJECT}.val_raw.landed_pdfs`
WITH CONNECTION `${PROJECT}.${BQ_LOCATION}.vertex`
OPTIONS (
  object_metadata = 'SIMPLE',
  uris = ['gs://${LANDING_BUCKET}/*'],
  max_staleness = INTERVAL 1 DAY,
  metadata_cache_mode = 'MANUAL'
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_raw.manifest` (
  doc_id STRING NOT NULL, uri STRING NOT NULL, property_hint STRING, doc_type STRING,
  source_system STRING, effective_date DATE, is_scanned BOOL
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_raw.field_candidates` (
  candidate_id STRING NOT NULL, doc_id STRING NOT NULL, page INT64, field STRING,
  raw_label STRING, raw_value STRING, value_numeric FLOAT64, value_string STRING,
  bbox JSON, confidence FLOAT64, extractor STRING, prompt_version STRING, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_raw.text_blocks` (
  block_id STRING NOT NULL, doc_id STRING NOT NULL, page INT64, section STRING, text STRING,
  extractor STRING, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_raw.gemini_cache` (
  cache_key STRING NOT NULL, doc_id STRING, page INT64, response JSON, created_at TIMESTAMP
);

-- ---------- val_core ----------
CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.properties` (
  property_id STRING NOT NULL, apn STRING, address_line STRING, address_norm STRING,
  city STRING, state STRING, zip STRING, submarket STRING, geo GEOGRAPHY,
  property_type STRING, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.documents` (
  doc_id STRING NOT NULL, property_id STRING, uri STRING, doc_type STRING, source_system STRING,
  effective_date DATE, page_count INT64, is_scanned BOOL, parse_method STRING,
  parse_confidence FLOAT64, resolution_method STRING, ingested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.field_map` (
  doc_type STRING, raw_label STRING, field STRING, unit STRING
);

-- Bitemporal facts. Only allowed UPDATE: set retired_at on a superseded row.
CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.facts` (
  fact_id STRING NOT NULL, property_id STRING NOT NULL, field STRING NOT NULL,
  value_numeric FLOAT64, value_string STRING, unit STRING,
  doc_id STRING, page INT64, bbox JSON, source_doc_type STRING,
  extractor STRING, confidence FLOAT64,
  status STRING,                -- active | held | rejected
  hold_reasons ARRAY<STRING>,
  valid_from DATE, recorded_at TIMESTAMP, retired_at TIMESTAMP,
  superseded_by STRING, correction_id STRING, demo_run_id STRING
)
CLUSTER BY property_id, field;

CREATE OR REPLACE VIEW `${PROJECT}.val_core.golden_record` AS
WITH ranked AS (
  SELECT f.*,
    CASE f.extractor WHEN 'correction' THEN 100 ELSE
      CASE f.source_doc_type
        WHEN 'appraisal_uad36' THEN 80 WHEN 'inspection' THEN 70 WHEN 'appraisal_legacy' THEN 60
        WHEN 'disclosure' THEN 50 WHEN 'public_record' THEN 40 WHEN 'hoa' THEN 30 ELSE 0 END
    END AS source_precedence
  FROM `${PROJECT}.val_core.facts` f
  WHERE f.status = 'active' AND f.retired_at IS NULL
)
SELECT * EXCEPT(rn) FROM (
  SELECT r.*, ROW_NUMBER() OVER (PARTITION BY property_id, field
    ORDER BY source_precedence DESC, valid_from DESC, confidence DESC, recorded_at DESC) AS rn
  FROM ranked r
) WHERE rn = 1;

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.property_features` (
  property_id STRING NOT NULL, submarket STRING, property_type STRING, lat FLOAT64, lng FLOAT64,
  gla_sqft FLOAT64, beds INT64, baths_full INT64, baths_half INT64, baths_total FLOAT64,
  year_built INT64, age_yrs INT64, lot_sqft FLOAT64, pool INT64, garage_spaces INT64,
  condition_c INT64, quality_q INT64, last_reno_year INT64,
  fact_ids ARRAY<STRING>, has_held_value_fact BOOL, built_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.chunks` (
  chunk_id STRING NOT NULL, doc_id STRING, property_id STRING, page INT64, section STRING,
  text STRING, embedding ARRAY<FLOAT64>, pii_findings INT64, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.sales` (
  sale_id STRING NOT NULL, property_id STRING NOT NULL, sale_date DATE, price NUMERIC,
  sale_type STRING, was_listed BOOL, list_date DATE, estimate_shown_before_list BOOL
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.market_index` (
  submarket STRING, month DATE, median_ppsf FLOAT64, n_sales INT64,
  is_forecast BOOL, model_version STRING, built_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.valuations` (
  valuation_id STRING NOT NULL, property_id STRING NOT NULL, effective_date DATE, purpose STRING,
  point NUMERIC, low NUMERIC, high NUMERIC, confidence FLOAT64,
  sales_comp_value NUMERIC, avm_value NUMERIC,
  gate_result STRING, gate_reasons ARRAY<STRING>, breaker_state STRING,
  drivers JSON, model_versions JSON, fact_ids ARRAY<STRING>,
  supersedes_valuation_id STRING, trigger STRING, requested_by STRING,
  demo_run_id STRING, created_at TIMESTAMP
)
CLUSTER BY property_id;

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_core.valuation_comps` (
  valuation_id STRING NOT NULL, comp_sale_id STRING, comp_property_id STRING,
  rank_score FLOAT64, distance_mi FLOAT64, months_since_sale FLOAT64, time_adj_factor FLOAT64,
  time_adj_price NUMERIC, adjustments JSON, gross_adj_pct FLOAT64, net_adj_pct FLOAT64,
  adjusted_price NUMERIC, weight FLOAT64, used BOOL, drop_reason STRING
)
CLUSTER BY comp_property_id;

-- ---------- val_ops ----------
CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ops.flags` (
  flag_id STRING NOT NULL, created_at TIMESTAMP, user_id STRING, user_role STRING, has_stake BOOL,
  target_type STRING, target_id STRING, property_id STRING, valuation_id STRING, field STRING,
  current_value STRING, proposed_value STRING, reason_code STRING, reason_text STRING,
  evidence_uris ARRAY<STRING>, evidence_doc_refs ARRAY<STRUCT<doc_id STRING, page INT64>>,
  demo_run_id STRING
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ops.review_items` (
  review_id STRING NOT NULL, created_at TIMESTAMP, source STRING, flag_id STRING,
  fact_ids ARRAY<STRING>, valuation_id STRING, property_id STRING, field STRING,
  route STRING, requires_two_approvals BOOL, summary STRING, demo_run_id STRING
);

-- Status is derived from decisions; never updated in place.
CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ops.review_decisions` (
  decision_id STRING NOT NULL, review_id STRING NOT NULL, reviewer_id STRING, reviewer_role STRING,
  reviewer_has_stake BOOL, decision STRING, notes STRING, value_opinion NUMERIC,
  decided_at TIMESTAMP, demo_run_id STRING
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ops.corrections` (
  correction_id STRING NOT NULL, review_id STRING, flag_id STRING, property_id STRING, field STRING,
  old_fact_id STRING, new_fact_id STRING, old_value STRING, new_value STRING,
  approver_ids ARRAY<STRING>, flagger_id STRING, evidence_uris ARRAY<STRING>,
  applied_at TIMESTAMP, demo_run_id STRING
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ops.comp_feedback` (
  feedback_id STRING NOT NULL, valuation_id STRING, subject_property_id STRING, comp_sale_id STRING,
  dist_mi FLOAT64, months_since_sale FLOAT64, gla_diff_pct FLOAT64, beds_diff INT64,
  baths_diff FLOAT64, age_diff_yrs INT64, lot_diff_pct FLOAT64, condition_diff INT64,
  quality_diff INT64, same_submarket BOOL, pool_mismatch BOOL,
  accepted BOOL, reason_code STRING, reviewer_id STRING, source STRING,
  approved BOOL, created_at TIMESTAMP, demo_run_id STRING
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ops.gold_eval_set` (
  property_id STRING, field STRING, true_value STRING, correction_id STRING, added_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ops.signoffs` (
  signoff_id STRING, valuation_id STRING, user_id STRING, user_role STRING, has_stake BOOL,
  decision STRING, notes STRING, signed_at TIMESTAMP, demo_run_id STRING
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ops.cascade_runs` (
  cascade_id STRING, correction_id STRING, valuation_id_old STRING, valuation_id_new STRING,
  property_id STRING, relation STRING,              -- subject | comp_dependent
  point_old NUMERIC, point_new NUMERIC, low_old NUMERIC, high_old NUMERIC,
  low_new NUMERIC, high_new NUMERIC, gate_old STRING, gate_new STRING,
  ran_at TIMESTAMP, demo_run_id STRING
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ops.breaker_state` (
  submarket STRING, state STRING, reasons ARRAY<STRING>, metrics JSON,
  changed_at TIMESTAMP, acknowledged_by STRING, demo_run_id STRING
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ml.model_eval_runs` (
  run_id STRING, model_name STRING, model_version STRING, role STRING, -- champion | challenger | breaker
  submarket STRING, as_of DATE, window_days INT64, subset STRING,      -- all | unanchored
  n INT64, mdape FLOAT64, pct_within_10 FLOAT64, signed_bias FLOAT64, passed BOOL, notes STRING,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ml.model_aliases` (
  alias STRING, family STRING, model_name STRING, promoted_at TIMESTAMP, promoted_by STRING
);

CREATE TABLE IF NOT EXISTS `${PROJECT}.val_ml.adjustment_grid` (
  submarket STRING, feature STRING, dollars_per_unit FLOAT64, clamped BOOL,
  model_name STRING, built_at TIMESTAMP
);
