# 09 — Synthetic data generator (`data_gen/`)

Deterministic (`--seed 20261005`). Writes ground truth to `data_gen/out/ground_truth/*.parquet` and loads it to `val_raw.ground_truth` for accuracy checks.

## World

- Town **Cedar Hollow, ZZ**; ZIPs 99101–99104; centroid lat 35.50, lng −80.85 (fictional placement; nothing references a real place).
- Four submarkets with distinct price levels and trends:

| Submarket | ZIP | $/sq ft (start) | Trend over 36 months |
|---|---|---|---|
| Old Town | 99101 | 245 | +4%/yr steady |
| Larkspur | 99102 | 210 | +3%/yr steady |
| Hilltop | 99103 | 280 | +5%/yr steady |
| Riverside | 99104 | 230 | +6%/yr, then **−9% over the last 4 months** |

- 1,200 properties (85% SFR, 10% townhome, 5% condo). Street names from a fixed fictional list (Larkspur Ln, Hilltop Rd, Mill Race Dr, Quarry St, Wren Ct, …). APNs `CH-####-###`.
- Features drawn per submarket; price = hedonic function + submarket index + noise (σ 6%). Condition drives price strongly (that's the point of the story).
- 36 months of sales ending **2026-09-30**: ~1,800 arm's-length sales, ~150 off-market. `estimate_shown_before_list` TRUE for 70% of listed sales.

## Documents per property (only a subset of properties gets each type)

| Doc type | Count | Variants |
|---|---|---|
| `appraisal_legacy` (pre-2026 form-style, comp grid that sometimes spans pages) | 500 | 30% scanned (rasterized, rotated ±2°, noise, JPEG q=55) |
| `appraisal_uad36` (structured XML + PDF) | 120 | clean |
| `inspection` (narrative findings, condition, roof, foundation, additions) | 400 | 20% scanned |
| `disclosure` (checkbox form: water damage, foundation, permits) | 300 | 40% scanned, checkboxes hand-marked style |
| `hoa` (dues, special assessments) | 120 | clean |
| `public_record` | all | CSV feed, not PDF (goes straight to facts with `extractor='feed'`) |

Each document's fields are drawn from ground truth, then perturbed realistically: wrong labels ("GLA" vs "Above Grade Living Area"), units ("2,080 SF", "2080 sq. ft."), occasional typos (2% of numeric fields off by a digit — these should be caught by G1 cross-source checks).

## Seeded demo cases (must exist exactly)

1. **14 Larkspur Ln** (`P-000014`, Larkspur, SFR). Ground truth GLA **2,080** after a permitted 840 sq ft addition in 2024. County record and 2019 legacy appraisal say **1,240**. The 2025 inspection narrative on page 2: "Rear two-story addition completed 2024 under permit #CH-24-0817, approx. 840 sq ft, finished, heated." No document gives 2,080 as a structured field. Sold 2026-03-12 for a price consistent with 2,080 sq ft. Requested now for a **refi**.
2. **18 Larkspur Ln** (`P-000018`) — a neighbor whose current valuation uses 14 Larkspur's March 2026 sale as a comp. Because 14 Larkspur is recorded at 1,240 sq ft, its sale looks expensive per sq ft and inflates 18 Larkspur's value. After the GLA correction, 18 Larkspur's value should **drop** by roughly 3–6%.
3. **22 Hilltop Rd** — appraisal says 2,450 sq ft, county says 1,950 → G1 conflict, appears in the review queue as `adjudication`.
4. **7 Wren Ct, Riverside** — an unusual 6,800 sq ft property → G2 routes to appraiser (out of distribution).
5. **31 Mill Race Dr, Riverside** — ordinary property in the tightened market → valuation shows tightened G2 thresholds after the breaker runs.

## Bootstrap training data

- `comp_feedback`: 6,000 synthetic reviewer decisions from an "appraiser-like" rule plus 10% noise (accept if distance < 0.75 mi, |GLA diff| < 20%, |condition diff| ≤ 1, months since sale ≤ 6). Tag `source='synthetic_bootstrap'`.
- Frozen pre-list estimates for every historical sale (computed after the first AVM train; the generator leaves a hook `make backfill-frozen`).

## Outputs

`data_gen/out/pdfs/<source_system>/<doc_type>/<doc_id>.pdf`, `manifest.jsonl`, `public_records.csv`, `sales.csv`, `ground_truth/*.parquet`. `make data` uploads PDFs and manifest to the landing bucket and loads CSVs to BigQuery.
