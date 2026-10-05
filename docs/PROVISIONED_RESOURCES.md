# Provisioned Google Cloud Resources

This document provides a complete inventory and audit record of all Google Cloud infrastructure and resources provisioned for the **Appraisal-Grade Valuation AI** prototype in project `takehome-gcp`.

Last updated: **October 3, 2026**  
Provisioning mechanism: **Google Cloud Python SDK Automation** (`scripts/setup_infra.py`, `scripts/enable_apis.py`, `scripts/seed.py`, `scripts/build_features.py`)

---

## 1. Project Identification & Identity

| Parameter | Value | Notes |
|---|---|---|
| **GCP Project ID** | `takehome-gcp` | Evaluation sandbox |
| **Project Number** | `281362663093` | Automatically resolved |
| **Primary Region** | `us-central1` | Regional compute & serverless |
| **BigQuery Location** | `US` (Multi-region) | Required for BQ ML & Agent Platform integration |
| **DocAI Location** | `us` (Multi-region) | Document AI layout parsing |
| **Service Account** | `id-valuation-ai-sa@takehome-gcp.iam.gserviceaccount.com` | Primary deployment identity |

---

## 2. Enabled GCP Service APIs

The following APIs were programmatically enabled via Service Usage API:

1. `bigquery.googleapis.com` — BigQuery data warehouse and analytics engine.
2. `storage.googleapis.com` — Cloud Storage object storage.
3. `documentai.googleapis.com` — Document AI Layout Parser processor.
4. `aiplatform.googleapis.com` — Agent Platform foundation models and Gemini endpoints.
5. `bigqueryconnection.googleapis.com` — BigQuery Cloud Resource connections.
6. `pubsub.googleapis.com` — Event-driven pub/sub messaging.
7. `run.googleapis.com` — Cloud Run managed container execution.
8. `cloudresourcemanager.googleapis.com` — IAM policy management.

---

## 3. Cloud Storage (GCS) Buckets

| Bucket Name | Location | Storage Class | Contents & Purpose |
|---|---|---|---|
| `gs://takehome-gcp-landing` | `US` | Standard | Ingested source PDFs organized by silo (`los/`, `servicing/`, `county_feed/`). Indexed by BigQuery Object Tables. |
| `gs://takehome-gcp-evidence` | `US` | Standard | User-uploaded review evidence (e.g. building permits, contractor receipts). |
| `gs://takehome-gcp-cache` | `US` | Standard | Content-addressed SHA-256 cache for DocAI and Gemini calls. |

### Uploaded Demo Seed Files in `takehome-gcp-landing`:
* `gs://takehome-gcp-landing/servicing/inspection/DOC-INS-000014.pdf` (2-page report with addition narrative on p. 2)
* `gs://takehome-gcp-landing/los/appraisal_legacy/DOC-APP-000014.pdf` (Legacy form with stale 1,240 sq ft GLA)
* `gs://takehome-gcp-landing/evidence/DOC-PERMIT-CH-24-0817.pdf` (Permit for 840 sq ft addition)
* `gs://takehome-gcp-landing/los/appraisal_legacy/DOC-APP-000022.pdf` (22 Hilltop appraisal with 2,450 sq ft conflicting record)

---

## 4. BigQuery Architecture

### Datasets (Location: `US` Multi-Region)

| Dataset | Fully Qualified ID | Purpose |
|---|---|---|
| `val_raw` | `takehome-gcp.val_raw` | Landing object table, raw parser outputs, and Gemini extraction cache. |
| `val_core` | `takehome-gcp.val_core` | System of record: properties, bitemporal facts, golden records, sales, features. |
| `val_ml` | `takehome-gcp.val_ml` | BQML models, training views, time-adjusted sales, and adjustment grids. |
| `val_ops` | `takehome-gcp.val_ops` | Governance: flags, review items, approvals, corrections audit log, breaker state. |

### BigQuery Cloud Resource Connection

* **Connection ID:** `takehome-gcp.US.vertex`
* **Resource Name:** `projects/281362663093/locations/us/connections/vertex`
* **Connection Service Account:** `bqcx-281362663093-8wgc@gcp-sa-bigquery-condel.iam.gserviceaccount.com`
* **IAM Roles Granted to Connection SA:**
  * `roles/aiplatform.user` (Enables BQ to invoke Agent Platform models)
  * `roles/documentai.viewer` (Enables BQ to invoke Document AI processors)
  * `roles/storage.objectViewer` (Enables BQ object tables over GCS landing bucket)

### Seed Data Loaded into BigQuery:
* `takehome-gcp.val_core.properties`: **1,200 properties** across 4 submarkets (Old Town, Larkspur, Hilltop, Riverside).
* `takehome-gcp.val_core.sales`: **1,949 arm's-length and off-market sales** over 36 historical months.
* `takehome-gcp.val_core.property_features`: Pre-computed analytical features for modeling and comps.
* `takehome-gcp.val_core.market_index`: Monthly median $/sq ft time-series plus 6-month forecast.
* `takehome-gcp.val_ops.comp_feedback`: **6,000 synthetic reviewer decisions** (for comp ranker training).

---

## 5. Document AI Processors

| Processor Name | Processor ID / Full Path | Type | Location | Status |
|---|---|---|---|---|
| `val-layout-parser` | `projects/281362663093/locations/us/processors/c745df858c6e37e0` | `LAYOUT_PARSER_PROCESSOR` | `us` | **Active / Enabled** |

* Used to parse unstructured PDF layouts, extract spatial tables, and retain exact bounding boxes for UI citations.

---

## 6. Pub/Sub Event Topics

| Topic Name | Full Topic Path | Purpose |
|---|---|---|
| `flags` | `projects/takehome-gcp/topics/flags` | Ingests "This is wrong" flag submissions from UI. |
| `corrections` | `projects/takehome-gcp/topics/corrections` | Broadcasts approved corrections to trigger the revaluation cascade. |

---

## 7. BQML Models Specification

| Model Name | Type | Label | Training Source | Status |
|---|---|---|---|---|
| `market_index_arima_v1` | `ARIMA_PLUS` | `median_ppsf` | `val_ml.ppsf_monthly` | **Trained & Active** |
| `comp_ranker_v1` | `BOOSTED_TREE_CLASSIFIER` | `accepted` | `val_ops.comp_feedback` | **Trained & Active** |
| `adj_larkspur_v1` | `LINEAR_REG` | `price_time_adj` | `val_ml.sales_time_adjusted` | **Trained & Active** |
| `adj_old_town_v1` | `LINEAR_REG` | `price_time_adj` | `val_ml.sales_time_adjusted` | **Trained & Active** |
| `adj_hilltop_v1` | `LINEAR_REG` | `price_time_adj` | `val_ml.sales_time_adjusted` | **Trained & Active** |
| `adj_riverside_v1` | `LINEAR_REG` | `price_time_adj` | `val_ml.sales_time_adjusted` | **Trained & Active** |
| `avm_v1` | `BOOSTED_TREE_REGRESSOR` | `price_time_adj` | `val_ml.sales_time_adjusted` (with custom time split) | **Trained & Active** |

---

## 8. Python SDK Provisioning Scripts Reference

All provisioning is reproducible via the following committed scripts:
* `scripts/check_gcp.py` — Verifies authentication and default project.
* `scripts/enable_apis.py` — Enables all required Google Cloud APIs.
* `scripts/setup_infra.py` — Creates GCS buckets, BigQuery datasets, and Pub/Sub topics.
* `scripts/run_sql.py` — Runs parameterized SQL DDL against BigQuery.
* `scripts/seed.py` — Uploads PDFs to GCS and loads CSVs into BigQuery.
* `scripts/build_features.py` — Builds analytical property features in BigQuery.
* `scripts/train_models.py` — Trains the BQML models suite in BigQuery.
* `scripts/demo_reset.py` — Resets demo state to initial baseline for rehearsing.
