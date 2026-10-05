# 01 — Architecture

## Flow

```
Siloed sources ──▶ Cloud Storage (landing/<source>/) ──▶ BigQuery object table
                                                           │
                      ML.PROCESS_DOCUMENT (Doc AI Layout Parser)
                                                           │ low confidence / scans / checkboxes
                                         AI.GENERATE (Gemini, typed output_schema)
                                                           │
                         clean + resolve to property_id + map to UAD 3.6 field names
                                                           │
                                  G1 data gate ── held ──▶ review queue
                                                           │ passed
     BigQuery core: facts (bitemporal) → golden_record → property_features, chunks+embeddings, sales
                                                           │
     BQML: market_index (ARIMA_PLUS) · comp_ranker (BOOSTED_TREE_CLASSIFIER)
           adj_<submarket> (LINEAR_REG) · avm (BOOSTED_TREE_REGRESSOR) · ML.EXPLAIN_PREDICT
                                                           │
     Valuation engine (deterministic Python + SQL) ──▶ G2 value gate ──▶ ADK agent (Gemini) ──▶ Web app
                                                                                                 │
                                    G3: human sign-off on money decisions (UI, not automated)    │
                                                                                                 ▼
     "This is wrong" ─▶ Pub/Sub flags ─▶ review queue ─▶ 2 approvals ─▶ corrections ─▶ Pub/Sub corrections
                                                                                          │
                                       revalue job: new fact, retire old, re-value subject + dependents
                                                                                          │
                              comp_feedback / gold_eval_set ──▶ retrain job (champion/challenger)

     breaker job (daily): frozen estimates vs closed sales by submarket ──▶ breaker_state ──▶ G2 thresholds
```

## GCP services

| Service | Use |
|---|---|
| Cloud Storage | `gs://<proj>-landing` (source PDFs by source system), `gs://<proj>-evidence` (reviewer uploads), `gs://<proj>-cache` |
| BigQuery | Datasets `val_raw`, `val_core`, `val_ml`, `val_ops`; object table; `VECTOR_SEARCH`; GIS |
| BigQuery connection | `US.vertex` (CLOUD_RESOURCE) for remote models (Document AI, Gemini, embeddings) |
| Document AI | Layout Parser processor, location `us` |
| Agent Platform | Gemini (via BigQuery remote model and via ADK), text embeddings, Model Registry for BQML models |
| Cloud Run | Service `valuation-app`; jobs `revalue`, `retrain`, `breaker` |
| Pub/Sub | Topics `flags`, `corrections`; push subscriptions to `valuation-app` (`/_pubsub/flags`, `/_pubsub/corrections`) with OIDC auth |
| Cloud Scheduler | `breaker` daily 06:00 ET; `retrain` weekly Sun 02:00 ET |
| Artifact Registry | Container images |
| Cloud Logging / Monitoring | Structured logs; alert policy on `breaker_tripped` log metric |
| Secret Manager | Only if needed; ADC everywhere else |

Region: `us-central1` for Cloud Run, Pub/Sub, Scheduler. BigQuery and its connection: multi-region `US`. Document AI: `us`.

## Environments

One project, one environment (`demo`). Terraform variables: `project_id`, `region`, `bq_location`, `docai_location`, `name_prefix`.

## Why these choices (keep consistent with the deck)

- BigQuery is system of record **and** ML platform: no data movement, SQL skills in-house, serverless.
- `VECTOR_SEARCH` is the vector database for the prototype. Production consumer scale would add AlloyDB or Vector Search in Agent Platform as a serving tier (documented, not built).
- Document AI first, Gemini only for low-confidence pages: cheaper and repeatable.
- Valuation math is deterministic: reproducible and auditable.
- Time-series modeling: BQML `ARIMA_PLUS` is used for the v1 prototype's market index time adjustments (zero data movement, serverless SQL execution). The enterprise target architecture incorporates Google's **TimesFM** (Model Garden in Agent Platform) via BigQuery Remote Connection for sparse submarket cold-starts, macro covariate conditioning (mortgage rates), and predictive circuit breakers (see `docs/04-ml-models.md`).
