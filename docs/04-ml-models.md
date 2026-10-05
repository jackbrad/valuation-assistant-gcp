# 04 — BQML models

Reference SQL: `sql/04_bqml_models.sql`. Cadence and thresholds in `config/settings.example.yaml`.

## 1. Market index — `val_ml.market_index_arima` (ARIMA_PLUS, monthly)

- Input: monthly median $/sq ft by submarket from arm's-length sales (`val_core.sales` × `property_features`), months with < 5 sales imputed from a 3-month rolling window.
- Historical index stored in `val_core.market_index` (smoothed actuals). `ML.FORECAST` 6 months ahead stored with `is_forecast = TRUE`.
- **Time adjustment** of a comp sold in month `m` to effective month `e`: `factor = index[e] / index[m]` (same submarket). If `e` is beyond the last actual, use the forecast.
- The forecast slope also feeds the circuit breaker as a trend signal.

## 2. Comp ranker — `val_ml.comp_ranker` (BOOSTED_TREE_CLASSIFIER, weekly)

- Training rows: `val_ops.comp_feedback` where the decision was approved (bootstrap rows from the generator are tagged `source='synthetic_bootstrap'`).
- Features: `dist_mi`, `months_since_sale`, `gla_diff_pct`, `beds_diff`, `baths_diff`, `age_diff_yrs`, `lot_diff_pct`, `condition_diff`, `quality_diff`, `same_submarket`, `pool_mismatch`.
- Label: `accepted`.
- Use: score candidates; rank by `predicted_accepted_probs` for TRUE.

## 3. Adjustment grid — `val_ml.adj_<submarket>` (LINEAR_REG per submarket, weekly)

- Label: `price_time_adj` (sale price time-adjusted to the latest month).
- Features (numeric, un-standardized so coefficients read as dollars): `gla_sqft`, `beds`, `baths_total`, `age_yrs`, `lot_sqft`, `pool` (0/1), `garage_spaces`, `condition_c`, `quality_q`.
- `OPTIONS(model_type='LINEAR_REG', input_label_cols=['price_time_adj'], l2_reg=1.0, enable_global_explain=TRUE)`.
- Read coefficients with `ML.WEIGHTS` into `val_ml.adjustment_grid (submarket, feature, dollars_per_unit, model_version)`. The UI shows this table as "the adjustment grid".
- Guardrail: clamp each coefficient to `[min,max]` in settings (e.g. GLA $40–$400 per sq ft) and log when clamped.

## 4. AVM — `val_ml.avm` (BOOSTED_TREE_REGRESSOR, monthly or on drift)

- Label: `price_time_adj`. Features: property features + `submarket` + `lat`, `lng`.
- **Time-based split**: `DATA_SPLIT_METHOD='CUSTOM'`, `DATA_SPLIT_COL='is_eval'` where `is_eval = sale_date >= cutoff` (cutoff default: 4 months before the latest sale).
- `ML.EXPLAIN_PREDICT(..., STRUCT(5 AS top_k_features))` for drivers.

## Promotion (champion/challenger) — `jobs/retrain.py`

A challenger replaces the champion only if all pass:
1. MdAPE on post-cutoff sales ≤ champion's MdAPE (and on the **unanchored** subset ≤ champion's).
2. No regression on `val_ops.gold_eval_set` (every past correction re-scored; the challenger's valuation for those properties must not move away from the corrected-fact valuation by more than tolerance).
3. Fairness: MdAPE spread across submarkets ≤ `promotion.max_submarket_mdape_spread`.
4. Record a row in `val_ml.model_eval_runs` for both models.

Model versions: create models with a version suffix (`avm_v20261003_1`) and maintain `val_ml.model_aliases (alias, model_name, promoted_at)` so the engine reads `champion`. Optionally register in Vertex AI Model Registry (`model_registry='VERTEX_AI'`, `vertex_ai_model_id`) — verify options.

## What feedback trains what

| Feedback | Effect | When |
|---|---|---|
| Approved fact correction | `property_features` rebuilt, affected valuations re-run | Immediately (revalue job) |
| Comp kept / rejected | `comp_feedback` rows → comp ranker | Weekly retrain |
| Adjustment disagreement (reviewer note with field) | Logged; submarket LINEAR_REG retrained on corrected features | Weekly |
| Value override | Stored on the review item; used in evaluation and gate tuning; **never** a label | — |
| Closed sale | AVM label; market index input | Monthly / on drift |

## Acceptance

- All four model families train in < 5 minutes total on synthetic data.
- Adjustment grid coefficients have plausible signs (GLA, baths, quality positive; age negative).
- AVM post-cutoff MdAPE on synthetic data between 4% and 9% overall, with Riverside visibly worse in the last 4 months (seeded downturn).

---

## Architectural Evolution: Google TimesFM vs. BQML ARIMA_PLUS

Google Research's **TimesFM** (Time Series Foundation Model, 200M parameter decoder-only transformer) represents the natural enterprise evolution for time-series trending and predictive risk monitoring.

### Where TimesFM Fits in the Target Architecture

```
BigQuery Core (val_core.sales)
         │
         ▼
Monthly Submarket $/SF Series + Macro Covariates (Fed rates, active inventory, DOM)
         │
         ▼
Vertex AI Model Garden / Endpoint (google/timesfm-1.0-200m)
         ▲
         │ (BigQuery Remote Model via takehome-gcp.US.vertex)
         ▼
1. Zero-shot market index trending in sparse / illiquid submarkets
2. Leading-indicator predictive drift detection (preemptively trips G2 before deed recordation)
3. Counterfactual cascade re-forecasting when historic sales are amended
```

### Comparative Tradeoff Matrix

| Dimension | Baseline: BQML `ARIMA_PLUS` (v1 Implementation) | Evolution: Google `TimesFM` on Vertex AI (Target v2) |
| :--- | :--- | :--- |
| **Execution Environment** | Pure in-database BigQuery serverless slots; zero data movement | Vertex AI Model Garden endpoint called via BigQuery Remote Connection |
| **Operational Cost** | Fractions of a cent per monthly retraining run; no idle infrastructure | Managed endpoint compute cost (CPU or T4 GPU, ~$0.08–$0.35/hr) |
| **Sparse / Illiquid Submarkets** | High variance when monthly sales < 10; requires 3-month rolling imputation | **Superior**: Pre-trained on 100B+ cross-domain time points; excels at zero-shot transfer |
| **Macro Covariates** | Univariate only (past $/SF trajectory) | **Multivariate**: Conditions on 30-year mortgage rates, inventory supply, and CPI |
| **Circuit Breaker Integration** | Reactive: Evaluates trailing 90-day closed deeds post-sale | **Predictive**: Forecasts inflection points 60–90 days ahead, tightening G2 proactively |
| **Regulatory & Examiner Acceptance** | High: Fannie Mae / Freddie Mac examiners are standardly familiar with ARIMA | Requires model risk governance (SR 11-7) validation package for foundation models |

### Strategic Recommendation for Customer Presentations
- **Phase 1 (MVP / Core Prototype):** Keep BQML `ARIMA_PLUS` for fast, zero-infra SQL-native execution and deterministic Fannie Mae explainability.
- **Phase 2 (Enterprise Scale):** Introduce TimesFM via Vertex AI Model Garden to solve low-liquidity submarket forecasting and power predictive circuit breakers.
