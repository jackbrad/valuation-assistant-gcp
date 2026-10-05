"""Comp feedback generator for training the comp ranker BQML model."""
import random
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import numpy as np


def generate_comp_feedback(df_props: pd.DataFrame, df_sales: pd.DataFrame, n_samples: int = 6000, seed: int = 20261005) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)

    rows: List[Dict[str, Any]] = []
    prop_dict = df_props.set_index("property_id").to_dict(orient="index")

    # Sample random sales as candidates
    sample_sales = df_sales.sample(n=n_samples, replace=True, random_state=seed)

    for i, (_, sale) in enumerate(sample_sales.iterrows()):
        comp_prop_id = sale["property_id"]
        comp_prop = prop_dict.get(comp_prop_id)
        if not comp_prop:
            continue

        # Pick a subject in the same or nearby submarket
        subj_id = random.choice(list(prop_dict.keys()))
        subj = prop_dict[subj_id]

        dist_mi = round(random.uniform(0.1, 2.5), 2)
        months_since_sale = round(random.uniform(0.5, 18.0), 1)

        gla_diff_pct = abs(subj["gla_sqft"] - comp_prop["gla_sqft"]) / max(subj["gla_sqft"], 1)
        beds_diff = abs(subj["beds"] - comp_prop["beds"])
        baths_diff = abs(subj["baths_total"] - comp_prop["baths_total"])
        age_diff_yrs = abs(subj["age_yrs"] - comp_prop["age_yrs"])
        lot_diff_pct = abs(subj["lot_sqft"] - comp_prop["lot_sqft"]) / max(subj["lot_sqft"], 1)
        cond_diff = abs(subj["condition_c"] - comp_prop["condition_c"])
        qual_diff = abs(subj["quality_q"] - comp_prop["quality_q"])
        same_subm = 1 if subj["submarket"] == comp_prop["submarket"] else 0
        pool_mismatch = 1 if subj["pool"] != comp_prop["pool"] else 0

        # Appraiser rule:
        # accept if distance < 0.75 mi, |GLA diff| < 20%, |condition diff| <= 1, months since sale <= 6
        is_good = (
            dist_mi < 0.75 and
            gla_diff_pct < 0.20 and
            cond_diff <= 1 and
            months_since_sale <= 6.0 and
            same_subm == 1
        )

        # 10% noise
        if random.random() < 0.10:
            accepted = not is_good
        else:
            accepted = is_good

        rows.append({
            "feedback_id": f"FB-{i+1:06d}",
            "subject_property_id": subj_id,
            "comp_property_id": comp_prop_id,
            "comp_sale_id": sale["sale_id"],
            "dist_mi": dist_mi,
            "months_since_sale": months_since_sale,
            "gla_diff_pct": round(gla_diff_pct, 3),
            "beds_diff": beds_diff,
            "baths_diff": baths_diff,
            "age_diff_yrs": age_diff_yrs,
            "lot_diff_pct": round(lot_diff_pct, 3),
            "condition_diff": cond_diff,
            "quality_diff": qual_diff,
            "same_submarket": same_subm,
            "pool_mismatch": pool_mismatch,
            "accepted": accepted,
            "approved": True,
            "source": "synthetic_bootstrap",
            "created_at": "2026-09-30 00:00:00",
        })

    return pd.DataFrame(rows)


def main():
    out_dir = Path("data_gen/out")
    gt_dir = out_dir / "ground_truth"

    props_path = gt_dir / "properties.parquet"
    sales_path = gt_dir / "sales.parquet"

    if not props_path.exists() or not sales_path.exists():
        print("Run generator.py first!")
        return

    df_props = pd.read_parquet(props_path)
    df_sales = pd.read_parquet(sales_path)

    print("Generating 6,000 synthetic comp feedback decisions...")
    df_fb = generate_comp_feedback(df_props, df_sales, n_samples=6000)
    df_fb.to_csv(out_dir / "comp_feedback.csv", index=False)
    print(f"Generated {len(df_fb)} feedback rows (positive rate: {df_fb['accepted'].mean():.1%}).")
    print(f"Saved to {out_dir / 'comp_feedback.csv'}")


if __name__ == "__main__":
    main()
