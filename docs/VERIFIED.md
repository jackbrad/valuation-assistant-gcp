# VERIFIED.md — Verified APIs, Models, and Runtime Environment

This document records the exact versions, options, and APIs verified for the Appraisal-Grade Valuation AI prototype.

## Verified Stack & Versions (as of Oct 2026)

| Component | Verified ID / Version | Status / Notes |
|---|---|---|
| Python Runtime | 3.12 (via `uv`) | Verified via local `/opt/homebrew/bin/python3` and `uv` package manager |
| Gemini Flash Model | `gemini-2.5-flash` | Current GA Flash model in Vertex AI (`us-central1`). Verified live with SDK. [Docs](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models) |
| Text Embedding Model | `text-embedding-005` | Current GA 768-dim text embedding model on Vertex AI (`us-central1`). Verified live with SDK. [Docs](https://cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings) |
| Document AI Processor | Layout Parser (`LAYOUT_PARSER_PROCESSOR`) | Location `us`, outputs spatial layout, tables, blocks, and reading order |
| BigQuery Location | `US` multi-region | Required for `US.vertex` Cloud Resource connection with Vertex AI |
| BigQuery Connection | `US.vertex` (`CLOUD_RESOURCE`) | Connection service account requires `roles/aiplatform.user` |
| Serving Tier | Cloud Run (service `val-valuation-app`) | Region `us-central1`, containerized FastAPI + Jinja2 |
| Event Subscriptions | Pub/Sub push to Cloud Run | Endpoints: `/_pubsub/flags`, `/_pubsub/corrections` with OIDC service account token |

## Key BigQuery SQL Verifications

1. **Object Tables over Cloud Storage:**
   ```sql
   CREATE EXTERNAL TABLE IF NOT EXISTS val_raw.landed_pdfs
   WITH CONNECTION `US.vertex`
   OPTIONS (
     object_metadata = 'SIMPLE',
     uris = ['gs://takehome-gcp-landing/*.pdf', 'gs://takehome-gcp-landing/*/*.pdf'],
     max_staleness = INTERVAL 1 DAY,
     metadata_cache_mode = 'MANUAL'
   );
   ```

2. **BigQuery Vector Search:**
   `VECTOR_SEARCH(TABLE val_core.chunks, 'embedding', ...)` works with brute force or index when row count allows. For property-scoped search, pre-filtering by `property_id` minimizes scan latency.

3. **BQML Model Syntax:**
   - Market Index: `OPTIONS(model_type='ARIMA_PLUS', time_series_timestamp_col='month_date', time_series_data_col='median_price_per_sqft', time_series_id_col='submarket')`
   - Comp Ranker: `OPTIONS(model_type='BOOSTED_TREE_CLASSIFIER', input_label_cols=['accepted'])`
   - Adjustment Grid: `OPTIONS(model_type='LINEAR_REG', input_label_cols=['price_time_adj'], l2_reg=1.0)`
   - AVM: `OPTIONS(model_type='BOOSTED_TREE_REGRESSOR', input_label_cols=['price_time_adj'])`
