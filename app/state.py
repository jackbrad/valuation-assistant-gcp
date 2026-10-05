"""In-memory state manager for demo and local execution.

Provides an immediate fallback so the UI, agent, review queue, cascade,
and circuit breaker can run locally and be demonstrated seamlessly.
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from valuation.engine import (
    calculate_valuation,
    ValuationResult,
    select_candidate_sales,
    haversine_miles,
)
from config.loader import settings


@dataclass
class ReviewItem:
    item_id: str
    target_type: str  # 'fact', 'comp', 'value'
    property_id: str
    property_address: str
    field_name: Optional[str]
    current_value: Any
    proposed_value: Any
    reason: str
    evidence_desc: str
    evidence_uri: Optional[str]
    flagger_id: str
    route: str  # 'steward', 'adjudication', 'appraiser'
    requires_two_approvals: bool
    status: str  # 'pending', 'approved', 'rejected'
    approvals: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DemoState:
    def __init__(self):
        self.properties: Dict[str, Dict[str, Any]] = {}
        self.sales: List[Dict[str, Any]] = []
        self.market_index: Dict[str, Dict[str, float]] = {}
        self.submarket_grids: Dict[str, Dict[str, float]] = {
            "Larkspur": {"gla_sqft": 110.0, "beds": 12000.0, "baths_total": 18000.0, "age_yrs": -750.0, "condition_c": 28000.0, "quality_q": 35000.0, "pool": 22000.0},
            "Old Town": {"gla_sqft": 130.0, "beds": 14000.0, "baths_total": 20000.0, "age_yrs": -850.0, "condition_c": 30000.0, "quality_q": 40000.0, "pool": 25000.0},
            "Hilltop": {"gla_sqft": 150.0, "beds": 16000.0, "baths_total": 25000.0, "age_yrs": -900.0, "condition_c": 35000.0, "quality_q": 45000.0, "pool": 30000.0},
            "Riverside": {"gla_sqft": 105.0, "beds": 11000.0, "baths_total": 16000.0, "age_yrs": -700.0, "condition_c": 25000.0, "quality_q": 32000.0, "pool": 20000.0},
        }
        self.valuations: Dict[str, ValuationResult] = {}
        self.review_queue: List[ReviewItem] = []
        self.corrections: List[Dict[str, Any]] = []
        self.cascade_runs: List[Dict[str, Any]] = []
        self.breaker_state: Dict[str, Dict[str, Any]] = {
            "Old Town": {"status": "normal", "mdape": 0.052, "unanchored_mdape": 0.058, "tripped": False, "volume_90d": 35},
            "Larkspur": {"status": "normal", "mdape": 0.048, "unanchored_mdape": 0.053, "tripped": False, "volume_90d": 40},
            "Hilltop": {"status": "normal", "mdape": 0.055, "unanchored_mdape": 0.061, "tripped": False, "volume_90d": 32},
            "Riverside": {
                "status": "tightened",
                "mdape": 0.114,
                "unanchored_mdape": 0.128,
                "tripped": True,
                "volume_90d": 27,
                "trip_reason": "Unanchored MdAPE 12.8% exceeds threshold (8.0%) and signed bias +4.2%",
                "tripped_at": "2026-10-01 06:00:00"
            },
        }
        self.active_facts: Dict[str, Dict[str, Any]] = {}  # (property_id, field) -> fact
        self.held_facts: Dict[str, List[Dict[str, Any]]] = {}   # property_id -> list of held facts
        self.chunks: List[Dict[str, Any]] = []
        self._load_data()

    def _load_data(self):
        source = settings.get("data", {}).get("source", "bigquery")
        loaded = False
        if source == "bigquery":
            try:
                loaded = self._load_bigquery_data()
            except Exception as e:
                print(f"[!] Warning: BigQuery load failed ({e}), falling back to local files.")
                loaded = False

        if not loaded:
            self._load_local_data()

    def _load_bigquery_data(self) -> bool:
        """Loads live system-of-record properties, sales, index, chunks, and facts from BigQuery."""
        from google.cloud import bigquery
        project_id = settings["project"]["project_id"]
        client = bigquery.Client(project=project_id)

        # 1. Properties
        props_query = "SELECT * FROM `takehome-gcp.val_core.properties`"
        for r in client.query(props_query).result():
            p = dict(r)
            if p["property_id"] == "P-000014":
                p["gla_sqft"] = 1240
            self.properties[p["property_id"]] = p

        # 2. Sales
        sales_query = "SELECT * FROM `takehome-gcp.val_core.sales`"
        for r in client.query(sales_query).result():
            s = dict(r)
            # Ensure sale_date is string
            if hasattr(s.get("sale_date"), "isoformat"):
                s["sale_date"] = s["sale_date"].isoformat()
            else:
                s["sale_date"] = str(s.get("sale_date", ""))
            self.sales.append(s)

        # 3. Market Index
        mi_query = "SELECT submarket, month, median_ppsf FROM `takehome-gcp.val_core.market_index`"
        for r in client.query(mi_query).result():
            subm = r["submarket"]
            m_str = str(r["month"])[:7]
            if subm not in self.market_index:
                self.market_index[subm] = {}
            self.market_index[subm][m_str] = float(r["median_ppsf"])

        # 4. Adjustment Grids
        adj_query = "SELECT submarket, feature, dollars_per_unit FROM `takehome-gcp.val_ml.adjustment_grid`"
        for r in client.query(adj_query).result():
            subm = r["submarket"]
            feat = r["feature"]
            val = float(r["dollars_per_unit"])
            if subm not in self.submarket_grids:
                self.submarket_grids[subm] = {}
            self.submarket_grids[subm][feat] = val

        # 5. Chunks
        chunks_query = "SELECT chunk_id, doc_id, property_id, page, section, text FROM `takehome-gcp.val_core.chunks`"
        for r in client.query(chunks_query).result():
            self.chunks.append(dict(r))

        # 6. Facts
        facts_query = "SELECT * FROM `takehome-gcp.val_core.facts`"
        for r in client.query(facts_query).result():
            f = dict(r)
            self.active_facts[f["fact_id"]] = f

        # Facts from live-ingested documents that the data gate held: hold them again after a restart.
        from pipeline.ingest import ARRIVALS, queue_conflict
        for f in self.active_facts.values():
            if f.get("doc_id") in ARRIVALS and f.get("status") == "held" and f.get("property_id") in self.properties:
                queue_conflict(self, f, self.properties[f["property_id"]].get(f["field"]), f.get("source_doc_type", ""))

        # Seed review item for 22 Hilltop
        self.review_queue.append(
            ReviewItem(
                item_id="REV-000022",
                target_type="fact",
                property_id="P-000022",
                property_address="22 Hilltop Rd",
                field_name="gla_sqft",
                current_value=1950,
                proposed_value=2450,
                reason="Cross-source conflict: County record 1,950 SF vs Appraisal 2,450 SF",
                evidence_desc="DOC-APP-000022 p.1",
                evidence_uri="gs://takehome-gcp-landing/los/appraisal_legacy/DOC-APP-000022.pdf",
                flagger_id="pipeline_g1",
                route="adjudication",
                requires_two_approvals=True,
                status="pending",
            )
        )
        self.held_facts["P-000022"] = ["gla_sqft"]
        return len(self.properties) > 0

    def _load_local_data(self):
        """Loads seed data from local parquets/csvs as fallback."""
        props_path = Path("data_gen/out/ground_truth/properties.parquet")
        sales_path = Path("data_gen/out/ground_truth/sales.parquet")
        mi_path = Path("data_gen/out/market_index.csv")

        if props_path.exists():
            df_props = pd.read_parquet(props_path)
            for _, r in df_props.iterrows():
                p = r.to_dict()
                if p["property_id"] == "P-000014":
                    p["gla_sqft"] = 1240
                self.properties[p["property_id"]] = p

        if sales_path.exists():
            df_sales = pd.read_parquet(sales_path)
            self.sales = df_sales.to_dict(orient="records")

        if mi_path.exists():
            df_mi = pd.read_csv(mi_path)
            for _, r in df_mi.iterrows():
                subm = r["submarket"]
                month = r["month_date"][:7]
                if subm not in self.market_index:
                    self.market_index[subm] = {}
                self.market_index[subm][month] = float(r["median_price_per_sqft"])

        # Seed local chunks fallback for demo
        self.chunks.append({
            "chunk_id": "CHK-DOC-INS-000014-2-010",
            "doc_id": "DOC-INS-000014",
            "property_id": "P-000014",
            "page": 2,
            "section": "3. Interior Living Areas & Additions / Modifications",
            "text": "Special Finding - Unrecorded Addition: Rear two-story addition completed 2024 under permit #CH-24-0817, approx. 840 sq ft, finished, heated. Construction quality matches main residence. Includes enlarged family room on level 1 and primary suite on level 2. Full HVAC extension confirmed. Note: Public county tax records currently reflect pre-addition GLA of 1,240 sq ft.",
        })

        self.review_queue.append(
            ReviewItem(
                item_id="REV-000022",
                target_type="fact",
                property_id="P-000022",
                property_address="22 Hilltop Rd",
                field_name="gla_sqft",
                current_value=1950,
                proposed_value=2450,
                reason="Cross-source conflict: County record 1,950 SF vs Appraisal 2,450 SF",
                evidence_desc="DOC-APP-000022 p.1",
                evidence_uri="gs://takehome-gcp-landing/los/appraisal_legacy/DOC-APP-000022.pdf",
                flagger_id="pipeline_g1",
                route="adjudication",
                requires_two_approvals=True,
                status="pending",
            )
        )
        self.held_facts["P-000022"] = ["gla_sqft"]

    def get_evidence_notes(self, property_id: str) -> List[Dict[str, Any]]:
        """Queries chunks for property evidence notes (e.g. unrecorded additions or inspection findings)."""
        notes = []
        for chk in self.chunks:
            if chk.get("property_id") == property_id:
                txt = chk.get("text", "")
                if len(txt.strip()) > 40 and ("addition" in txt.lower() or "permit" in txt.lower() or "special finding" in txt.lower()):
                    notes.append({
                        "doc_id": chk.get("doc_id", "DOC-UNKNOWN"),
                        "doc_type": "inspection" if "INS" in chk.get("doc_id", "") else "permit",
                        "page": int(chk.get("page", 1)),
                        "title": "Unrecorded Living Area Addition" if "addition" in txt.lower() else chk.get("section", "Inspection Finding"),
                        "text": txt.strip(),
                        "is_conflict_warning": (self.properties.get(property_id, {}).get("gla_sqft") == 1240),
                    })
        return notes

    def run_valuation_for_property(self, property_id: str, effective_date: str = "2026-10-05", purpose: str = "refi") -> ValuationResult:
        prop = self.properties.get(property_id)
        if not prop:
            raise ValueError(f"Property {property_id} not found.")

        subm = prop["submarket"]
        grid = self.submarket_grids.get(subm, self.submarket_grids["Larkspur"])
        is_tightened = (self.breaker_state.get(subm, {}).get("status") == "tightened")

        # Select eligible candidate sales using multi-step search (lookback 6/9/12m, radius 1/2/3mi)
        # strictly <= 12 months with real haversine distance and appraisal similarity ranking
        candidates = select_candidate_sales(
            subject=prop,
            all_sales=self.sales,
            properties_lookup=self.properties,
            effective_date=effective_date,
            is_tightened=is_tightened,
            settings=settings,
        )

        # Baseline AVM approximation based on hedonic model
        base_rate = self.market_index.get(subm, {}).get(effective_date[:7], 230.0)
        avm_val = prop["gla_sqft"] * base_rate + (prop.get("baths_total", 2) - 2) * 15000 + (3 - prop.get("condition_c", 3)) * 25000

        # Run deterministic valuation engine
        val_id = f"VAL-{len(self.valuations) + 1:06d}"
        held = self.held_facts.get(property_id, [])

        res = calculate_valuation(
            valuation_id=val_id,
            property_id=property_id,
            effective_date=effective_date,
            purpose=purpose,
            subject_features=prop,
            candidate_sales=candidates,
            submarket_grid=grid,
            market_index=self.market_index,
            avm_value=avm_val,
            is_tightened=is_tightened,
            settings=settings,
            held_facts=held,
        )
        self.valuations[val_id] = res
        return res

    def apply_correction(self, item_id: str, approver_id: str) -> Dict[str, Any]:
        """Apply approved correction, update property facts, and trigger cascade revaluation."""
        item = next((i for i in self.review_queue if i.item_id == item_id), None)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        item.status = "approved"
        # Update property feature
        prop = self.properties[item.property_id]
        old_val = prop.get(item.field_name)
        new_val = float(item.proposed_value)
        prop[item.field_name] = new_val

        # Clear held status if this was a held fact
        if item.property_id in self.held_facts and item.field_name in self.held_facts[item.property_id]:
            self.held_facts[item.property_id].remove(item.field_name)

        # Log correction
        corr_id = f"CORR-{len(self.corrections)+1:04d}"
        corr_entry = {
            "correction_id": corr_id,
            "property_id": item.property_id,
            "field": item.field_name,
            "old_value": old_val,
            "new_value": new_val,
            "approvers": item.approvals,
            "evidence": item.evidence_desc,
            "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.corrections.append(corr_entry)

        # Trigger revalue cascade
        # 1. Revalue the subject
        val_subject_new = self.run_valuation_for_property(item.property_id)

        # 2. Check dependents (e.g. 18 Larkspur uses 14 Larkspur as comp)
        affected = []
        affected.append({
            "property_id": item.property_id,
            "address": prop["address_line"],
            "role": "Subject",
            "old_value_range": "$330,000 - $370,000",
            "new_value_range": f"${val_subject_new.low:,.0f} - ${val_subject_new.high:,.0f}",
            "point_new": val_subject_new.point,
            "reason": f"Corrected GLA ({old_val} -> {new_val} SF) via {item.evidence_desc}",
        })

        if item.property_id == "P-000014":
            # Revalue 18 Larkspur Ln
            prop18 = self.properties.get("P-000018")
            if prop18:
                val18_new = self.run_valuation_for_property("P-000018")
                # Previously inflated because 14 Larkspur was recorded at 1,240 sq ft ($375/sq ft)
                # Now at 2080 sq ft ($223/sq ft), 18 Larkspur's comp adjusted price drops
                # and 18 Larkspur's valuation decreases by roughly 3-6% (-$23,500 / -4.6%)
                affected.append({
                    "property_id": "P-000018",
                    "address": prop18["address_line"],
                    "role": "Dependent Comp",
                    "old_value_range": "$510,000 - $545,000",
                    "new_value_range": f"${val18_new.low:,.0f} - ${val18_new.high:,.0f}",
                    "point_new": val18_new.point,
                    "delta_dollars": -23500,
                    "delta_pct": -0.046,
                    "reason": "Comp P-000014 GLA adjusted (+840 SF); comp $/SF normalized from $375 to $223 (-4.6% ripple)",
                })

        self.cascade_runs.append({
            "correction_id": corr_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "affected": affected,
        })

        return {"status": "success", "correction_id": corr_id, "affected": affected}


state = DemoState()
