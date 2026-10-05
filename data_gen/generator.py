"""Synthetic Data Generator for Cedar Hollow, ZZ.

Generates 1,200 properties, 36 months of sales, ground truth facts,
and the exact seeded demo properties specified in docs/09-synthetic-data.md.
"""
import os
import random
import json
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple
import pandas as pd
import numpy as np

SUBMARKETS = {
    "Old Town": {"zip": "99101", "base_price_sqft": 245.0, "annual_trend": 0.04, "downturn_recent": False},
    "Larkspur": {"zip": "99102", "base_price_sqft": 210.0, "annual_trend": 0.03, "downturn_recent": False},
    "Hilltop": {"zip": "99103", "base_price_sqft": 280.0, "annual_trend": 0.05, "downturn_recent": False},
    "Riverside": {"zip": "99104", "base_price_sqft": 230.0, "annual_trend": 0.06, "downturn_recent": True},
}

STREET_NAMES = [
    "Larkspur Ln", "Hilltop Rd", "Mill Race Dr", "Quarry St", "Wren Ct",
    "Oak Ridge Way", "Willow Creek Rd", "Pine Crest Ave", "Cedar Pass",
    "Valley View Ct", "Highland Terrace", "Meadow View Dr", "Sycamore St",
    "Riverbend Rd", "Copper Leaf Ct"
]

PROPERTY_TYPES = ["SFR", "TOWNHOME", "CONDO"]
PROPERTY_TYPE_WEIGHTS = [0.85, 0.10, 0.05]


def generate_market_indices(start_date: str = "2023-10-01", end_date: str = "2026-09-30") -> pd.DataFrame:
    """Generate monthly median $/sq ft market index per submarket over 36 months."""
    months = pd.date_range(start=start_date, end=end_date, freq="MS").strftime("%Y-%m").tolist()
    rows = []

    for submarket, info in SUBMARKETS.items():
        base = info["base_price_sqft"]
        annual_growth = info["annual_trend"]
        monthly_growth = (1.0 + annual_growth) ** (1 / 12) - 1.0

        current_val = base
        total_months = len(months)
        for i, m in enumerate(months):
            # Check for Riverside downturn in last 4 months (-9% over 4 months)
            if info["downturn_recent"] and (total_months - i) <= 4:
                drop_rate = (1.0 - 0.09) ** (1 / 4) - 1.0
                current_val *= (1.0 + drop_rate)
            else:
                current_val *= (1.0 + monthly_growth)
            
            rows.append({
                "submarket": submarket,
                "month_date": f"{m}-01",
                "median_price_per_sqft": round(current_val, 2),
                "is_forecast": False,
            })

        # Add 6 forecast months
        forecast_months = pd.date_range(start="2026-10-01", periods=6, freq="MS").strftime("%Y-%m").tolist()
        fc_val = current_val
        for fm in forecast_months:
            if info["downturn_recent"]:
                # Continuing negative or stagnant trend for Riverside
                fc_val *= 0.99
            else:
                fc_val *= (1.0 + monthly_growth)
            rows.append({
                "submarket": submarket,
                "month_date": f"{fm}-01",
                "median_price_per_sqft": round(fc_val, 2),
                "is_forecast": True,
            })

    return pd.DataFrame(rows)


def generate_world(seed: int = 20261005) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[Dict[str, Any]]]:
    """Generates 1,200 properties, sales history, ground truth facts, and document manifests."""
    random.seed(seed)
    np.random.seed(seed)

    properties: List[Dict[str, Any]] = []
    ground_truth_facts: List[Dict[str, Any]] = []
    sales: List[Dict[str, Any]] = []
    manifest: List[Dict[str, Any]] = []

    # Centroid: lat 35.50, lng -80.85
    submarket_offsets = {
        "Old Town": (0.015, -0.015),
        "Larkspur": (-0.010, -0.020),
        "Hilltop": (0.025, 0.010),
        "Riverside": (-0.020, 0.025),
    }

    submarket_list = list(SUBMARKETS.keys())
    submarket_weights = [0.30, 0.30, 0.20, 0.20]

    # Pre-generate 1,200 properties
    for i in range(1, 1201):
        prop_id = f"P-{i:06d}"
        
        # Check if this is a seeded demo property
        if i == 14:  # 14 Larkspur Ln (P-000014)
            submarket = "Larkspur"
            address_line = "14 Larkspur Ln"
            prop_type = "SFR"
            gla = 2080  # Ground truth after 2024 addition (840 sq ft added to 1240)
            beds = 4
            baths_full = 2
            baths_half = 1
            year_built = 1988
            lot_sqft = 9200
            pool = 0
            garage = 2
            cond = 3
            qual = 3
            last_reno = 2024
        elif i == 18:  # 18 Larkspur Ln (P-000018)
            submarket = "Larkspur"
            address_line = "18 Larkspur Ln"
            prop_type = "SFR"
            gla = 2150
            beds = 4
            baths_full = 2
            baths_half = 1
            year_built = 1990
            lot_sqft = 9500
            pool = 0
            garage = 2
            cond = 3
            qual = 3
            last_reno = 2018
        elif i == 22:  # 22 Hilltop Rd (P-000022)
            submarket = "Hilltop"
            address_line = "22 Hilltop Rd"
            prop_type = "SFR"
            gla = 2450
            beds = 4
            baths_full = 3
            baths_half = 0
            year_built = 2005
            lot_sqft = 12000
            pool = 1
            garage = 2
            cond = 2
            qual = 2
            last_reno = 2022
        elif i == 7:  # 7 Wren Ct, Riverside (P-000007)
            submarket = "Riverside"
            address_line = "7 Wren Ct"
            prop_type = "SFR"
            gla = 6800  # Out of distribution
            beds = 6
            baths_full = 5
            baths_half = 2
            year_built = 2015
            lot_sqft = 45000
            pool = 1
            garage = 4
            cond = 2
            qual = 1
            last_reno = 2023
        elif i == 31:  # 31 Mill Race Dr, Riverside (P-000031)
            submarket = "Riverside"
            address_line = "31 Mill Race Dr"
            prop_type = "SFR"
            gla = 1950
            beds = 3
            baths_full = 2
            baths_half = 0
            year_built = 1998
            lot_sqft = 8500
            pool = 0
            garage = 2
            cond = 3
            qual = 3
            last_reno = 2015
        else:
            submarket = random.choices(submarket_list, weights=submarket_weights)[0]
            street_num = random.randint(100, 999)
            street = random.choice(STREET_NAMES)
            address_line = f"{street_num} {street}"
            prop_type = random.choices(PROPERTY_TYPES, weights=PROPERTY_TYPE_WEIGHTS)[0]
            
            if prop_type == "CONDO":
                gla = int(np.random.normal(1100, 250))
                lot_sqft = 0
                pool = 1 if random.random() < 0.6 else 0
                garage = 1
            elif prop_type == "TOWNHOME":
                gla = int(np.random.normal(1600, 300))
                lot_sqft = int(np.random.normal(2500, 500))
                pool = 1 if random.random() < 0.2 else 0
                garage = 1 if random.random() < 0.4 else 2
            else:
                gla = int(np.random.normal(2100, 450))
                lot_sqft = int(np.random.normal(8500, 2000))
                pool = 1 if random.random() < 0.25 else 0
                garage = random.choice([1, 2, 2, 2, 3])

            gla = max(750, min(5000, gla))
            lot_sqft = max(0, lot_sqft)
            year_built = random.randint(1965, 2023)
            beds = max(1, min(6, int(round(gla / 550.0))))
            baths_full = max(1, min(4, int(round(gla / 700.0))))
            baths_half = 1 if (gla > 1800 and random.random() < 0.5) else 0
            cond = random.choices([1, 2, 3, 4, 5], weights=[0.05, 0.25, 0.50, 0.15, 0.05])[0]
            qual = random.choices([1, 2, 3, 4, 5], weights=[0.05, 0.25, 0.50, 0.15, 0.05])[0]
            last_reno = year_built if random.random() < 0.6 else random.randint(max(year_built, 2010), 2025)

        apn = f"CH-{i:04d}-{random.randint(100, 999)}"
        zip_code = SUBMARKETS[submarket]["zip"]
        base_lat, base_lng = 35.50 + submarket_offsets[submarket][0], -80.85 + submarket_offsets[submarket][1]
        lat = round(base_lat + np.random.normal(0, 0.005), 6)
        lng = round(base_lng + np.random.normal(0, 0.005), 6)

        prop_record = {
            "property_id": prop_id,
            "apn": apn,
            "address_line": address_line,
            "address_norm": address_line.upper().strip(),
            "city": "Cedar Hollow",
            "state": "ZZ",
            "zip": zip_code,
            "submarket": submarket,
            "geo": f"POINT({lng} {lat})",
            "lat": lat,
            "lng": lng,
            "property_type": prop_type,
            "gla_sqft": gla,
            "beds": beds,
            "baths_full": baths_full,
            "baths_half": baths_half,
            "baths_total": baths_full + 0.5 * baths_half,
            "year_built": year_built,
            "age_yrs": 2026 - year_built,
            "lot_sqft": lot_sqft,
            "pool": pool,
            "garage_spaces": garage,
            "condition_c": cond,
            "quality_q": qual,
            "last_reno_year": last_reno,
            "created_at": "2026-10-01 00:00:00",
        }
        properties.append(prop_record)

        # Ground truth facts
        gt_fields = [
            ("gla_sqft", float(gla), None, "sqft"),
            ("beds", float(beds), None, "count"),
            ("baths_full", float(baths_full), None, "count"),
            ("baths_half", float(baths_half), None, "count"),
            ("year_built", float(year_built), None, "year"),
            ("lot_sqft", float(lot_sqft), None, "sqft"),
            ("pool", float(pool), None, "binary"),
            ("garage_spaces", float(garage), None, "count"),
            ("condition_c", float(cond), f"C{cond}", "score"),
            ("quality_q", float(qual), f"Q{qual}", "score"),
        ]
        for fld, num_val, str_val, unit in gt_fields:
            ground_truth_facts.append({
                "property_id": prop_id,
                "field": fld,
                "value_numeric": num_val,
                "value_string": str_val,
                "unit": unit,
                "valid_from": "2026-01-01",
                "is_ground_truth": True,
            })

    df_properties = pd.DataFrame(properties)

    # Generate 36 months of sales ending 2026-09-30 (~1,800 arm's-length sales, ~150 off-market)
    start_date = date(2023, 10, 1)
    end_date = date(2026, 9, 30)
    total_days = (end_date - start_date).days

    m_indices = generate_market_indices()
    idx_map = {(row["submarket"], row["month_date"][:7]): row["median_price_per_sqft"] for _, row in m_indices.iterrows()}

    sale_count = 0
    # Generate seeded sale for 14 Larkspur: sold 2026-03-12
    prop14 = df_properties[df_properties["property_id"] == "P-000014"].iloc[0]
    # 2,080 sq ft * $220/sq ft (in 2026-03) + adjustments = ~$465,000
    sale_count += 1
    sales.append({
        "sale_id": f"S-{sale_count:06d}",
        "property_id": "P-000014",
        "sale_date": "2026-03-12",
        "price": 465000.0,
        "sale_type": "arms_length",
        "was_listed": True,
        "list_date": "2026-01-20",
        "estimate_shown_before_list": True,
        "submarket": "Larkspur",
        "gla_sqft": prop14["gla_sqft"],
        "beds": prop14["beds"],
        "baths_total": prop14["baths_total"],
        "age_yrs": prop14["age_yrs"],
        "lot_sqft": prop14["lot_sqft"],
        "pool": prop14["pool"],
        "garage_spaces": prop14["garage_spaces"],
        "condition_c": prop14["condition_c"],
        "quality_q": prop14["quality_q"],
        "price_per_sqft": round(465000.0 / prop14["gla_sqft"], 2),
    })

    # Generate general sales (~1,950 total)
    sampled_props = df_properties.sample(n=1950, replace=True, random_state=seed)
    for _, prop in sampled_props.iterrows():
        # Skip 14 Larkspur in random sales
        if prop["property_id"] == "P-000014":
            continue

        sale_day_offset = random.randint(0, total_days)
        sale_dt = start_date + timedelta(days=sale_day_offset)
        sale_month = sale_dt.strftime("%Y-%m")
        subm = prop["submarket"]

        m_price_sqft = idx_map.get((subm, sale_month), 230.0)

        # Hedonic valuation formula
        # Base price = gla * submarket index
        base_price = prop["gla_sqft"] * m_price_sqft
        # Adjustments
        bath_adj = (prop["baths_total"] - 2.0) * 15000.0
        bed_adj = (prop["beds"] - 3.0) * 10000.0
        pool_adj = prop["pool"] * 25000.0
        garage_adj = (prop["garage_spaces"] - 2) * 12000.0
        cond_adj = (3 - prop["condition_c"]) * 25000.0
        qual_adj = (3 - prop["quality_q"]) * 35000.0
        age_adj = -prop["age_yrs"] * 600.0

        clean_price = base_price + bath_adj + bed_adj + pool_adj + garage_adj + cond_adj + qual_adj + age_adj
        # Add 6% noise
        noise = np.random.normal(0, 0.06)
        final_price = round(clean_price * (1.0 + noise), -3)

        sale_type = "arms_length" if random.random() < 0.92 else "off_market"
        was_listed = True if sale_type == "arms_length" else False
        list_dt = (sale_dt - timedelta(days=random.randint(20, 60))).strftime("%Y-%m-%d") if was_listed else None
        shown_before_list = True if (was_listed and random.random() < 0.70) else False

        sale_count += 1
        sales.append({
            "sale_id": f"S-{sale_count:06d}",
            "property_id": prop["property_id"],
            "sale_date": sale_dt.strftime("%Y-%m-%d"),
            "price": float(final_price),
            "sale_type": sale_type,
            "was_listed": was_listed,
            "list_date": list_dt,
            "estimate_shown_before_list": shown_before_list,
            "submarket": subm,
            "gla_sqft": prop["gla_sqft"],
            "beds": prop["beds"],
            "baths_total": prop["baths_total"],
            "age_yrs": prop["age_yrs"],
            "lot_sqft": prop["lot_sqft"],
            "pool": prop["pool"],
            "garage_spaces": prop["garage_spaces"],
            "condition_c": prop["condition_c"],
            "quality_q": prop["quality_q"],
            "price_per_sqft": round(final_price / prop["gla_sqft"], 2),
        })

    df_sales = pd.DataFrame(sales)

    # Build Document Manifest and seeded cases
    # Documents: appraisal_legacy, appraisal_uad36, inspection, disclosure, hoa, public_record
    doc_id_counter = 0

    for _, prop in df_properties.iterrows():
        p_id = prop["property_id"]
        addr = prop["address_line"]
        subm = prop["submarket"]

        # All properties have a public_record entry
        doc_id_counter += 1
        pub_doc_id = f"DOC-PUB-{doc_id_counter:06d}"
        manifest.append({
            "doc_id": pub_doc_id,
            "uri": f"gs://takehome-gcp-landing/county_feed/public_record/{pub_doc_id}.csv",
            "property_hint": addr,
            "property_id": p_id,
            "doc_type": "public_record",
            "source_system": "county_feed",
            "effective_date": "2024-01-01",
            "is_scanned": False,
        })

    # Add specific seeded documents:
    # 1. 14 Larkspur Ln:
    #    - 2019 legacy appraisal with GLA = 1,240
    #    - 2025 inspection with narrative: "Rear two-story addition completed 2024 under permit #CH-24-0817, approx. 840 sq ft, finished, heated."
    doc_id_counter += 1
    doc_14_appraisal = f"DOC-APP-000014"
    manifest.append({
        "doc_id": doc_14_appraisal,
        "uri": f"gs://takehome-gcp-landing/los/appraisal_legacy/{doc_14_appraisal}.pdf",
        "property_hint": "14 Larkspur Ln",
        "property_id": "P-000014",
        "doc_type": "appraisal_legacy",
        "source_system": "los",
        "effective_date": "2019-06-15",
        "is_scanned": True,
        "special_case": "14_larkspur_legacy",
    })

    doc_id_counter += 1
    doc_14_insp = f"DOC-INS-000014"
    manifest.append({
        "doc_id": doc_14_insp,
        "uri": f"gs://takehome-gcp-landing/servicing/inspection/{doc_14_insp}.pdf",
        "property_hint": "14 Larkspur Lane",
        "property_id": "P-000014",
        "doc_type": "inspection",
        "source_system": "servicing",
        "effective_date": "2025-04-10",
        "is_scanned": False,
        "special_case": "14_larkspur_addition",
    })

    # 2. 22 Hilltop Rd:
    #    - Appraisal says 2,450 sq ft, county says 1,950 sq ft (G1 conflict)
    doc_id_counter += 1
    doc_22_app = f"DOC-APP-000022"
    manifest.append({
        "doc_id": doc_22_app,
        "uri": f"gs://takehome-gcp-landing/los/appraisal_legacy/{doc_22_app}.pdf",
        "property_hint": "22 Hilltop Rd",
        "property_id": "P-000022",
        "doc_type": "appraisal_legacy",
        "source_system": "los",
        "effective_date": "2025-08-20",
        "is_scanned": False,
        "special_case": "22_hilltop_conflict",
    })

    # Add remaining sample documents (appraisals, inspections, disclosures, hoa)
    sample_props = df_properties.sample(n=500, random_state=seed)
    for _, prop in sample_props.iterrows():
        if prop["property_id"] in ["P-000014", "P-000022"]:
            continue
        doc_id_counter += 1
        d_id = f"DOC-INS-{doc_id_counter:06d}"
        manifest.append({
            "doc_id": d_id,
            "uri": f"gs://takehome-gcp-landing/servicing/inspection/{d_id}.pdf",
            "property_hint": prop["address_line"],
            "property_id": prop["property_id"],
            "doc_type": "inspection",
            "source_system": "servicing",
            "effective_date": "2025-02-15",
            "is_scanned": random.random() < 0.20,
        })

    return df_properties, df_sales, pd.DataFrame(ground_truth_facts), manifest


def main():
    out_dir = Path("data_gen/out")
    out_dir.mkdir(parents=True, exist_ok=True)
    gt_dir = out_dir / "ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)

    print("Generating synthetic world for Cedar Hollow, ZZ (seed 20261005)...")
    df_props, df_sales, df_gt, manifest = generate_world(seed=20261005)

    df_props.to_parquet(gt_dir / "properties.parquet", index=False)
    df_sales.to_parquet(gt_dir / "sales.parquet", index=False)
    df_gt.to_parquet(gt_dir / "facts.parquet", index=False)

    df_props.to_csv(out_dir / "public_records.csv", index=False)
    df_sales.to_csv(out_dir / "sales.csv", index=False)

    with open(out_dir / "manifest.jsonl", "w", encoding="utf-8") as f:
        for row in manifest:
            f.write(json.dumps(row) + "\n")

    m_indices = generate_market_indices()
    m_indices.to_csv(out_dir / "market_index.csv", index=False)

    print(f"Generated {len(df_props)} properties, {len(df_sales)} sales, {len(manifest)} manifest documents.")
    print(f"Outputs written to {out_dir}")


if __name__ == "__main__":
    main()
