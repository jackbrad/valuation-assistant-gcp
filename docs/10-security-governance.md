# 10 — Security and governance

## Built in the prototype

- **Service accounts, least privilege**
  - `sa-app` (Cloud Run service): BigQuery Data Editor on `val_ops`, Data Viewer on `val_core`/`val_ml`, BigQuery Job User, Storage Object Creator on evidence bucket, Viewer on landing, Vertex AI User, Pub/Sub Publisher.
  - `sa-jobs` (revalue, retrain, breaker): Data Editor on `val_core`, `val_ml`, `val_ops`; Job User; Vertex AI User; Logging Writer.
  - `sa-pipeline` (local runs): Data Editor on all four datasets; Storage Admin on landing/cache.
  - BigQuery connection SA: Vertex AI User, Document AI API User, Storage Object Viewer on landing.
  - `sa-pubsub-push`: Run Invoker on the app.
- **Append-only audit** in `val_ops` (corrections, decisions, flags) + Cloud Audit Logs (Data Access logs on BigQuery enabled for the four datasets).
- **Two-approver and no-stake rules** in app logic and asserted in SQL.
- **PII**: synthetic, but the pipeline still runs Sensitive Data Protection inspection over `text_blocks` (names, phone numbers) and stores findings; the agent's document search excludes chunks with findings unless the user role is `appraiser`. `# DEMO-SHORTCUT:` if time runs short, implement as a stub with the same interface.
- **Evidence uploads**: content-type and size checks; files stored with `flag_id` prefix; served via short-lived signed URLs.
- **Prompt safety**: tool outputs are data; the agent is instructed never to follow instructions found in documents. Document text is passed inside clearly delimited fields.

## Production (documented, not built)

- IAP on Cloud Run; roles from Google Groups.
- VPC Service Controls perimeter around BigQuery, Storage, Vertex AI, Document AI.
- CMEK on datasets and buckets.
- Dataplex: catalog, lineage (BigQuery lineage API), data quality scans replacing custom checks.
- Model risk management: model cards per promoted model; validation by an independent team; quarterly review.
- AVM quality-control rule mapping (effective Oct 1, 2025):

| Rule requirement | Control in this system |
|---|---|
| High confidence in estimates | G2 thresholds, ranges, champion/challenger, breaker |
| Protect against data manipulation | Two approvers with evidence, append-only log, no-stake rule |
| Avoid conflicts of interest | Stake check on approvals and sign-offs |
| Random sample testing and reviews | Weekly random sample to the review queue; eval runs |
| Comply with nondiscrimination laws | Fairness check in promotion; MdAPE by submarket monitored |
