# 07 — Circuit breaker

Reference SQL: `sql/07_circuit_breaker.sql`. Job: `jobs/breaker.py` (Cloud Run job, daily via Scheduler; `make breaker` runs it once).

## Why

A published estimate can move the sale price, so scoring the live estimate lets the model grade its own homework. And a turning market is exactly when an automated valuation does the most damage. The breaker scores what the model said **before** the market saw anything, against what actually sold.

## Inputs

- **Frozen estimates**: `val_core.valuations` with `purpose='frozen_prelist'`. The generator backfills one per sale (the AVM's estimate as of the day before `list_date`, or 30 days before `sale_date` for off-market). In production these are snapshotted daily for every active listing.
- **Unanchored set**: sales where `estimate_shown_before_list = FALSE` or `sale_type = 'off_market'`.

## Metrics (per submarket, trailing `breaker.window_days`, default 90)

- `mdape_all`, `mdape_unanchored`, `pct_within_10`, `n`.
- `signed_bias` = median((estimate − sale) / sale) — positive means we're over-valuing, the dangerous direction.
- Baseline = the same metrics over the prior 12 months.

## Trip rule (any)

- `mdape_unanchored > breaker.mdape_abs_threshold` (0.08), with `n ≥ breaker.min_n` (15);
- `mdape_unanchored > breaker.mdape_ratio_threshold × baseline` (1.5×);
- `signed_bias > breaker.max_overvaluation_bias` (0.04);
- the market index forecast slope over the next 3 months < `breaker.forecast_drop_threshold` (−3%).

## Actions on trip

1. Upsert `val_ops.breaker_state` → `tightened`, with reasons and metrics.
2. G2 reads tightened thresholds for that submarket immediately.
3. Log `breaker_tripped` (structured) → log-based metric → Cloud Monitoring alert policy (email to the demo owner).
4. Enqueue an early retrain (`jobs/retrain.py --reason=breaker --submarket=…`).

Reset to `normal` only when metrics are back under thresholds for 30 consecutive days **and** a human acknowledges (`POST /api/breaker/{submarket}/ack`).

## Seeded scenario

Riverside prices fall ~9% over the last 4 months of data while the other submarkets stay flat. The AVM trained on the earlier period over-values Riverside, so the breaker trips for Riverside only.

## Acceptance

- `make breaker` trips Riverside, leaves others `normal`, writes `model_eval_runs` rows, and a valuation for a Riverside property afterward shows tightened G2 reasons.
