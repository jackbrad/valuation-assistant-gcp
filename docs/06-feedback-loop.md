# 06 — Human-in-the-loop feedback

## Capture

Every fact row, comp row and the value card in the UI has a **"This is wrong"** action. The form collects: target (fact / comp / value), proposed correct value (typed per field), reason (pick list + free text), evidence (file upload to `gs://<proj>-evidence/<flag_id>/…` or a reference to an existing `doc_id` + page), the flagger's user id and role, and whether they have a stake in the transaction (demo: derived from the user profile).

`POST /api/flags` writes `val_ops.flags` (status `new`) and publishes to Pub/Sub `flags`. Fallback when `events.use_pubsub=false`: call the handler directly.

## Routing (`/_pubsub/flags` handler → `val_ops.review_items`)

| Condition | Route |
|---|---|
| Fact flagged, the source page shows a different value than stored (extraction error) | `steward` |
| Fact flagged, another active source disagrees | `adjudication` |
| Fact flagged with new evidence newer than the stored fact (stale data) | `steward`, evidence required |
| Comp or adjustment flagged | `appraiser` |
| Value flagged | `appraiser` |

The pipeline adds two more sources: `g1_hold` (from G1) and `random_sample` (weekly, `feedback.random_sample_per_week` confident valuations, chosen uniformly, so reviewers also see cases the gates passed — fixes selection bias, and it's the AVM rule's random-sample testing).

`requires_two_approvals = TRUE` when the field is value-moving (docs/02), or target is comp/value.

## Approval rules (enforced in app **and** asserted in SQL)

- Approver ≠ flagger. Approvers must be distinct users. No approver may have a stake.
- Evidence is required to approve a value-moving correction.
- One rejection closes the item as rejected (with notes).
- Value overrides: approving records the reviewer's opinion on the review item and creates **no** fact and **no** training label.

`sql/06_feedback.sql` contains an assertion query that must return zero rows: any applied correction lacking two distinct, non-flagger, no-stake approvers.

## Apply (on final approval)

1. Insert `val_ops.corrections` (append-only).
2. Insert a new fact (`extractor='correction'`, `confidence=1.0`, citation = the evidence doc/page) and set `retired_at` on the superseded fact.
3. Insert into `val_ops.gold_eval_set`.
4. If target was a comp: insert `comp_feedback` (accepted=false) for that valuation's subject/comp pair.
5. Publish `corrections` → revalue.

## Re-value cascade (`jobs/revalue.py`, also callable inline for the demo)

1. Rebuild `property_features` for the corrected property.
2. Find affected valuations: the latest valuation per subject where subject = corrected property, plus the latest valuation per subject where `valuation_comps.comp_property_id` = corrected property, created within `cascade.lookback_days` (default 180).
3. Re-run each with the same `effective_date` and `purpose`, `trigger='cascade'`, `supersedes_valuation_id` set.
4. Write `val_ops.cascade_runs (correction_id, valuation_id_old, valuation_id_new, point_old, point_new, gate_old, gate_new)`.
5. Emit a structured log line `cascade_complete` with counts.

The UI shows a "What changed" panel: each affected valuation, old vs. new range, and which comp or fact changed.

## Comp feedback

Each comp row has Keep / Reject (reason pick list: `too far`, `different condition`, `different style`, `non-arm's-length`, `other`). Writes `val_ops.comp_feedback` with feature diffs. A Reject on a comp used in a shown valuation also creates an `appraiser` review item.

## Acceptance

- Demo flow (docs/12) works end to end in < 60 s from second approval to updated valuations on screen.
- The SQL assertion returns zero rows after the demo.
- A loan-officer user (has stake) cannot approve; the UI explains why.
