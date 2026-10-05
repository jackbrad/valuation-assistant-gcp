# 05 — Valuation engine, G2 and the agent

## Valuation engine (`valuation/engine.py`, `valuation/bq.py`, `valuation/gates.py`)

Pure functions for the math (unit-tested without GCP); `bq.py` fetches inputs.

`value(property_id, effective_date, purpose, requested_by) -> ValuationResult`

1. **Subject**: load `property_features` + the facts behind them (citations).
2. **Candidates** (`sql/05_valuation.sql`): arm's-length sales of the same `property_type`, `ST_DWITHIN(geo, subject_geo, radius_m)`, `sale_date` within `lookback_months` before `effective_date`, excluding the subject's own sale on or after `effective_date`. Expand radius/lookback per settings until ≥ `g2.min_candidates` or the max is reached.
3. **Rank**: `ML.PREDICT` with the champion comp ranker; take the top `comps.max_used` (default 6).
4. **Time-adjust** each comp price with the market index factor.
5. **Adjust** each comp: `adj_f = coef_f × (subject_f − comp_f)` for each feature, using the subject's submarket grid. `adjusted_price = time_adj_price + Σ adj_f`. Compute `gross_adj_pct = Σ|adj_f| / time_adj_price` and `net_adj_pct`.
6. **Weight**: `w = 1 / (0.05 + gross_adj_pct)`, normalized. Drop comps with `gross_adj_pct > comps.max_gross_adj_pct` (default 0.25) before weighting, and record why.
7. **Sales-comparison value** = Σ w × adjusted_price.
8. **AVM value** via `ML.PREDICT`; **drivers** via `ML.EXPLAIN_PREDICT`.
9. **Reconcile**: `point = α × sales_comp + (1 − α) × avm` (α default 0.7). Range from the weighted 10th–90th percentile of adjusted comp prices, widened by `|sales_comp − avm| / 2`, never narrower than `±range.min_half_width_pct` (3%).
10. **Confidence** (0–1) = function of comp count, mean similarity, range width, divergence. Document the formula in code.
11. **G2**, then persist to `val_core.valuations` + `val_core.valuation_comps` (append-only).

### G2 — value gate (`gates.py`)

Route to an appraiser (`gate_result='routed_to_appraiser'`, the UI shows **no point estimate**, only the reasons and evidence) if any:
- usable comps < `g2.min_comps` (3; 5 when the submarket breaker is `tightened`);
- `(high − low) / point > g2.max_range_width` (0.20; 0.12 when tightened);
- `|sales_comp − avm| / point > g2.max_divergence` (0.10; 0.06 when tightened);
- subject out of distribution: any key feature outside the 1st–99th percentile of the submarket's training data, or GLA outside ±40% of every used comp;
- any held (G1) fact on a value-moving field for the subject.

Always return the reasons list, even when shown.

### G3 — decision gate

The app never auto-approves a loan or an offer. A valuation used for a decision needs an explicit "Sign off" by a user with role `appraiser`, recorded in `val_ops.signoffs`. Users with `has_stake=true` for that property cannot sign off.

## Agent (`agent/`)

ADK `Agent` with Gemini Flash (latest GA). Run in-process from FastAPI using the ADK `Runner` with an in-memory session service (per browser session). Capture tool-call results from the event stream so the UI renders the evidence panel from tool output, not from model text.

### Tools (`agent/tools.py`) — thin wrappers over `valuation/` and SQL

| Tool | Returns |
|---|---|
| `resolve_property(query: str)` | up to 5 candidates `{property_id, address, submarket}` |
| `get_property_facts(property_id: str)` | golden-record facts with `{field, value, source_doc_type, doc_id, page, fact_id, status}`; held facts flagged |
| `search_documents(property_id: str, question: str, k: int = 5)` | chunks with `{text, doc_id, page, section, distance}` via `VECTOR_SEARCH` filtered to the property (then neighbors if asked) |
| `run_valuation(property_id: str, effective_date: str, purpose: str)` | full `ValuationResult` incl. gate result, comps, adjustments, drivers, `valuation_id` |
| `get_comp_grid(valuation_id: str)` | comps with adjustments per feature, weights |
| `get_adjustment_grid(submarket: str)` | current coefficients |

### System instruction (`agent/prompts.py`) — key rules

- You assist licensed appraisal reviewers. You never state a number that is not in a tool result. If asked to compute, call a tool.
- Cite every fact as `[doc_id p.N]`.
- If `gate_result` is `routed_to_appraiser`, do not give a value. Explain the reasons in plain language and list the evidence an appraiser should look at.
- Always present a value as a range with confidence, then the point estimate.
- Surface held facts and document narrative that may contradict a structured fact (e.g. an addition mentioned in an inspection when GLA hasn't changed). Use `search_documents` proactively for condition, additions, renovations, damage.
- Never give lending, legal or investment advice; the reviewer decides.

### Demo-critical behavior

For `14 Larkspur Ln`, the agent must surface the inspection narrative about the 2024 addition next to the GLA of 1,240 and suggest the reviewer verify GLA. That's what prompts the flag in the demo. Test it (`tests/test_agent_larkspur.py`, marked `gcp`).

## Acceptance

- `run_valuation` for every seeded demo property returns in < 6 s.
- Engine unit tests cover: time adjustment, adjustment math, weighting, range, every G2 rule, tightened thresholds.
- Agent answers for 5 scripted questions contain no numbers absent from tool results (test: extract numbers from the answer, assert each appears in captured tool output).
