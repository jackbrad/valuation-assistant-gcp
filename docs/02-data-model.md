# 02 — Data model

Full DDL: `sql/01_datasets_and_tables.sql`. This page explains intent and rules.

## Datasets

| Dataset | Holds |
|---|---|
| `val_raw` | Object table over landing bucket, raw parser output, raw Gemini extraction, extraction cache |
| `val_core` | Properties, documents, facts, golden record, property features, chunks, sales, market index, valuations |
| `val_ml` | BQML models, training views, evaluation runs, model registry mirror |
| `val_ops` | Flags, review items, decisions, corrections, comp feedback, gold eval set, breaker state, cascade runs |

## Core entities

- **properties** — one row per real-world property. `property_id` (`P-000123`), `apn`, address, `submarket` (one of `Riverside`, `Old Town`, `Larkspur`, `Hilltop`), `geo GEOGRAPHY`, `property_type` (`SFR`, `CONDO`, `TOWNHOME`).
- **documents** — one row per source file. `doc_type`: `appraisal_legacy`, `appraisal_uad36`, `inspection`, `disclosure`, `hoa`, `public_record`. `source_system` simulates the silo (`los`, `servicing`, `dms`, `county_feed`, `mls_feed`).
- **facts** — the atomic, cited, bitemporal unit. One row per (property, field, source). Fields use UAD 3.6-style names (see field list below).
  - Valid time: `valid_from` = the document's effective date.
  - Transaction time: `recorded_at` (insert time) and `retired_at` (NULL while current).
  - `status`: `active`, `held` (G1), `rejected`.
  - `extractor`: `docai`, `gemini`, `feed`, `correction`.
  - Citation: `doc_id`, `page`, `bbox JSON` (nullable for feeds).
- **golden_record** (view) — the current best value per (property, field): status `active`, `retired_at IS NULL`, highest `source_precedence`, then latest `valid_from`, then highest `confidence`. Precedence: `correction` 100 > `appraisal_uad36` 80 > `inspection` 70 > `appraisal_legacy` 60 > `disclosure` 50 > `public_record` 40 > `hoa` 30.
- **property_features** (table, rebuilt per property on change) — wide features for modeling: `gla_sqft`, `beds`, `baths`, `year_built`, `lot_sqft`, `pool`, `garage_spaces`, `condition_c` (1–6, UAD C1–C6), `quality_q` (1–6), `last_reno_year`, plus `fact_ids ARRAY<STRING>` for lineage.
- **chunks** — narrative text chunks with `embedding ARRAY<FLOAT64>`, `doc_id`, `page`, `property_id`, `section`.
- **sales** — closed sales: `sale_id`, `property_id`, `sale_date`, `price`, `sale_type` (`arms_length`, `off_market`), `was_listed`, `list_date`, `estimate_shown_before_list BOOL` (drives the unanchored set).
- **market_index** — monthly median $/sq ft per submarket (historical, smoothed) plus forecast rows (`is_forecast`).
- **valuations** — append-only. `valuation_id`, `property_id`, `effective_date`, `purpose` (`refi`, `purchase`, `review`, `frozen_prelist`), `point`, `low`, `high`, `confidence`, `sales_comp_value`, `avm_value`, `gate_result` (`shown`, `routed_to_appraiser`), `gate_reasons ARRAY<STRING>`, `drivers JSON`, `model_versions JSON`, `supersedes_valuation_id`, `trigger` (`user`, `cascade`, `backfill`), `created_at`.
- **valuation_comps** — one row per comp used: `valuation_id`, `comp_sale_id`, `comp_property_id`, `rank_score`, `distance_mi`, `time_adj_factor`, `adjustments JSON` (feature → dollars), `adjusted_price`, `weight`. Drives the cascade query.

## Ops entities

- **flags** — raw "This is wrong" submissions. `target_type`: `fact`, `comp`, `value`.
- **review_items** — the queue. `source`: `flag`, `g1_hold`, `random_sample`. `route`: `steward`, `adjudication`, `appraiser`. `requires_two_approvals BOOL`.
- **review_decisions** — one row per approver decision; distinct-approver rule enforced in app and checked by a SQL assertion.
- **corrections** — append-only log of applied changes with old/new values, approvers, lineage to the flag and evidence.
- **comp_feedback** — reviewer keeps/rejects a comp, with subject-vs-candidate feature diffs (training data for the comp ranker).
- **gold_eval_set** — every approved correction becomes a test case.
- **model_eval_runs** — every evaluation (promotion checks, breaker runs).
- **breaker_state** — current state per submarket (`normal` | `tightened`).
- **cascade_runs** — what each correction re-valued.

## Field list (facts.field)

`gla_sqft`, `beds`, `baths_full`, `baths_half`, `year_built`, `lot_sqft`, `pool`, `garage_spaces`, `condition_c`, `quality_q`, `last_reno_year`, `roof_age_yrs`, `hoa_fee_monthly`, `foundation_issue`, `water_damage_disclosed`, `zoning`.

**Value-moving fields** (two approvals required): `gla_sqft`, `beds`, `baths_full`, `baths_half`, `condition_c`, `quality_q`, `pool`, `lot_sqft`, `year_built`.
