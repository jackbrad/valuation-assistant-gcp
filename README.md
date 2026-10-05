# Valuation assistant on Google Cloud

A prototype property valuation assistant that answers questions from unstructured documents (appraisals, inspections, and permits) with page-level citations, and computes values with statistical models instead of the language model.

All data is synthetic. The prototype is set in a fictional town, Cedar Hollow.

## The problem

Valuation evidence often lives in PDFs spread across systems that don't share data. For one property in the sample data, the county record lists 1,240 sq ft of living area, while page 2 of an inspection report documents an 840 sq ft addition. Standard retrieval-augmented generation (RAG) can retrieve that text, but it loses layout and page references, doesn't check documents against the system of record, and leaves arithmetic to the model.

## What the prototype does

- **Ingests documents.** Document AI Layout Parser splits each PDF into sections, tables, and pages. Gemini extracts typed facts, each with its page and a source quote.
- **Checks data quality.** A fact that conflicts with the system of record is held and sent to a review queue instead of being used.
- **Retrieves with citations.** Chunks and `text-embedding-005` vectors are stored in BigQuery and searched with `VECTOR_SEARCH`.
- **Answers through an agent.** A Gemini agent calls tools to find the property, search its documents, and run the valuation engine. Every number in an answer comes from a tool output.
- **Values with statistical models.** The engine adjusts comparable sales with per-neighborhood regression rates from BigQuery ML, blends the result with a price model, and withholds the value when its safety checks fail.
- **Governs changes.** Correcting a value-moving fact requires evidence and two independent approvers. The person who flagged the fact and anyone with a stake in the loan can't approve it.
- **Explains itself.** Each answer shows the issues found, a six-step walkthrough of the calculation, the documents reviewed, and the agent's tool calls.

## Architecture

```
Cloud Storage (landing bucket)
  -> Document AI Layout Parser          sections, tables, page numbers
  -> Gemini 2.5 Flash                   typed facts with page and source quote
  -> Data quality gate                  conflicts held for review
  -> text-embedding-005                 768-dimension vectors
  -> BigQuery                           facts, chunks, vectors, sales, BigQuery ML models
  -> Cloud Run (FastAPI)                Gemini agent + valuation engine + review workflow
```

| Google Cloud service | Use |
|---|---|
| Cloud Storage | Landing bucket for source documents |
| Document AI | Layout Parser processor |
| Vertex AI | `gemini-2.5-flash` (extraction and agent), `text-embedding-005` (embeddings) |
| BigQuery | Datasets `val_raw`, `val_core`, `val_ml`, `val_ops`; `VECTOR_SEARCH` |
| BigQuery ML | ARIMA_PLUS market index, linear regression adjustment rates, boosted tree price model |
| Cloud Run | Web app and API |

## Repository layout

| Path | Contents |
|---|---|
| `agent/` | Gemini agent, tools, and BigQuery vector retrieval |
| `app/` | FastAPI app, templates, static assets, and explainability |
| `valuation/` | Deterministic valuation engine and risk gates |
| `pipeline/` | Batch document pipeline and single-document ingestion |
| `sql/` | Reference BigQuery SQL |
| `scripts/` | Provisioning, seeding, model training, and deployment |
| `data_gen/` | Synthetic data and PDF generators |
| `jobs/` | Drift monitoring job |
| `infra/terraform/` | Terraform module (reference) |
| `clearline/` | UI design system |
| `docs/` | Architecture and design specifications |
| `docs/customer/` | Scope, design decisions, model selection, cost estimate, and FAQ |
| `tests/` | Unit and integration tests |

## Get started

### Prerequisites

- A Google Cloud project with billing enabled
- The Google Cloud CLI, authenticated with `gcloud auth application-default login`
- Python 3.12 and [uv](https://docs.astral.sh/uv/)

### Set up and run

1. In `config/settings.yaml`, set your project ID, region, and Document AI processor (see `config/settings.example.yaml` for every option).
1. Install dependencies:

   ```
   make setup
   ```

1. Enable APIs and create buckets, datasets, and topics:

   ```
   make infra
   ```

1. Generate synthetic data and load it:

   ```
   make data
   ```

1. Parse the demo documents and train the BigQuery ML models:

   ```
   make pipeline
   make models
   ```

1. Run the app locally at `http://localhost:8000`:

   ```
   make app
   ```

1. Optional: deploy to Cloud Run:

   ```
   make deploy
   ```

Run the tests with `make test`.

## Try it

| Property | What it shows |
|---|---|
| 14 Larkspur Ln | Documents show an addition the county record misses; the value is withheld until the fact is corrected |
| 18 Larkspur Ln | A clean case with a value shown; an unparsed inspection can be ingested live from the app |
| 22 Hilltop Rd | Sources disagree on living area, so the fact is on hold |
| 31 Mill Race Dr | Stricter checks after simulated market drift |
| 7 Wren Ct | An unusual house with no usable comparable sales |

## Limitations

This is a prototype. It uses synthetic data, demo users instead of real authentication, in-memory review state on a single instance, and a formula in place of the trained price model in the app. See `docs/customer/` for the full list of what's out of scope and what a production deployment needs.
