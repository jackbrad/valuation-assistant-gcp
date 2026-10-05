"""Explainability for the chat side panel. Deterministic: built only from the
engine's ValuationResult, the property record, extracted facts and the
document manifest. Gemini never writes any of this.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.state import state
from app.users import name as user_name
from config.loader import settings

MANIFEST = Path(__file__).resolve().parent.parent / "data_gen/out/manifest.jsonl"

DOC_TYPES = {
    "public_record": "County record",
    "appraisal_legacy": "Prior appraisal",
    "inspection": "Inspection report",
    "permit": "Building permit",
}
SOURCE_SYSTEMS = {
    "county_feed": "County data feed",
    "los": "Loan origination system",
    "servicing": "Loan servicing",
    "evidence": "Uploaded evidence",
}
FEATURES = {
    "gla_sqft": ("Living area", "sq ft"),
    "beds": ("Bedrooms", ""),
    "baths_total": ("Bathrooms", ""),
    "age_yrs": ("Age", "yrs"),
    "condition_c": ("Condition (1 best – 6 worst)", ""),
    "quality_q": ("Build quality (1 best – 6 worst)", ""),
    "pool": ("Pool", ""),
    "lot_sqft": ("Lot size", "sq ft"),
    "garage_spaces": ("Garage spaces", ""),
}


@lru_cache(maxsize=1)
def _manifest() -> Dict[str, List[Dict[str, Any]]]:
    by_property: Dict[str, List[Dict[str, Any]]] = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text().splitlines():
            doc = json.loads(line)
            by_property.setdefault(doc["property_id"], []).append(doc)
    return by_property


def documents_on_file(property_id: str, retrieved: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every document we hold for the property, newest first, with the pages
    we parsed and the passages retrieval actually used."""
    parsed_pages: Dict[str, set] = {}
    for c in state.chunks:
        if c.get("property_id") == property_id:
            parsed_pages.setdefault(c["doc_id"], set()).add(int(c.get("page", 1)))

    docs = {d["doc_id"]: dict(d) for d in _manifest().get(property_id, [])}
    for doc_id in parsed_pages:  # documents only known from the chunks table (e.g. the permit)
        docs.setdefault(doc_id, {"doc_id": doc_id, "doc_type": "permit" if "PERMIT" in doc_id else "document",
                                 "source_system": "evidence", "effective_date": ""})

    out = []
    for doc in docs.values():
        hits = [r for r in retrieved if r.get("doc_id") == doc["doc_id"]]
        out.append({
            "doc_id": doc["doc_id"],
            "type": DOC_TYPES.get(doc.get("doc_type"), doc.get("doc_type", "Document")),
            "source": SOURCE_SYSTEMS.get(doc.get("source_system"), doc.get("source_system", "")),
            "date": doc.get("effective_date", ""),
            "is_record": doc.get("doc_type") == "public_record",
            "parsed_pages": sorted(parsed_pages.get(doc["doc_id"], [])),
            "can_ingest": doc["doc_id"] in _arrivals() and not parsed_pages.get(doc["doc_id"]),
            "used": [{"page": h["page"], "text": h["text"], "similarity": h.get("similarity")} for h in hits],
        })
    # Documents the answer used first (best match first), then other parsed docs, then the county record.
    out.sort(key=lambda d: (not d["used"], -max((u["similarity"] or 0) for u in d["used"]) if d["used"] else 0, d["is_record"]))
    return out


def issues(property_id: str, valuation: Optional[Any]) -> List[Dict[str, Any]]:
    """Data problems found by comparing document facts with the county record."""
    prop = state.properties.get(property_id, {})
    found: List[Dict[str, Any]] = []

    facts = [f for f in state.active_facts.values() if f.get("property_id") == property_id]

    # 0. Corrections already approved for this property.
    corrected = {c["field"] for c in state.corrections if c["property_id"] == property_id}
    for c in state.corrections:
        if c["property_id"] == property_id:
            label = FEATURES.get(c["field"], (c["field"], ""))[0]
            found.append({
                "level": "success",
                "title": f"{label} corrected: {float(c['old_value']):,.0f} → {float(c['new_value']):,.0f}",
                "detail": f"Approved by {' and '.join(user_name(a) for a in c['approvers'])} on {c['applied_at']}. The valuation above uses the corrected value.",
                "cites": _cites(c.get("evidence", "")),
                "action": "",
            })

    # 1. Documents describe living area the county record doesn't include.
    additions = [f for f in facts if f.get("field") == "unrecorded_addition_sqft" and f.get("value_numeric")]
    pending = {i.field_name for i in state.review_queue if i.property_id == property_id and i.status == "pending"}
    if additions and "gla_sqft" not in corrected:
        size = int(additions[0]["value_numeric"])
        found.append({
            "level": "danger",
            "title": "Living area may be understated",
            "detail": f"The county record shows {int(prop.get('gla_sqft', 0)):,} sq ft. "
                      f"{_count(len(additions), 'document')} describe an addition of {size:,} sq ft that the record doesn't include.",
            "cites": [{"doc_id": f["doc_id"], "page": int(f["page"])} for f in additions],
            "action": "A reviewer flagged this; it's waiting in the review queue." if "gla_sqft" in pending
                      else "Flag the living area for correction with these pages as evidence.",
            "flag": None if "gla_sqft" in pending else {
                "property_id": property_id,
                "field": "gla_sqft",
                "label": "Living area",
                "current": f"{int(prop.get('gla_sqft', 0)):,} sq ft (county record)",
                "evidence": "; ".join(f"{f['doc_id']} p.{int(f['page'])}" for f in additions),
            },
        })

    # 2. Extracted facts that disagree with the record on the same field.
    for f in facts:
        field = f.get("field")
        # An approved correction supersedes older document values; pending ones are reported below.
        if field in corrected or field in pending:
            continue
        if field in FEATURES and f.get("value_numeric") is not None and prop.get(field) is not None:
            if abs(float(f["value_numeric"]) - float(prop[field])) > 0.5:
                label = FEATURES[field][0].split(" (")[0]
                found.append({
                    "level": "danger",
                    "title": f"{label} doesn't match the county record",
                    "detail": f"Record: {float(prop[field]):,.0f}. Document: {f['value_numeric']:,.0f}.",
                    "cites": [{"doc_id": f["doc_id"], "page": int(f["page"])}],
                    "action": "Confirm which source is right before relying on the value.",
                })

    # 3. Facts held by the data quality gate (cross-source conflicts found during ingestion).
    for item in state.review_queue:
        if item.property_id == property_id and item.status == "pending" and item.flagger_id == "pipeline_g1":
            label = FEATURES.get(item.field_name, (item.field_name, ""))[0].split(" (")[0]
            doc_id, _, page = item.evidence_desc.partition(" p.")
            found.append({
                "level": "danger",
                "title": f"{label} is on hold: sources disagree",
                "detail": f"{_sentence(item.reason.removeprefix('Cross-source conflict: '))}. The value is withheld until "
                          "two reviewers resolve it in the review queue.",
                "cites": [{"doc_id": doc_id, "page": int(page or 1)}],
                "action": "Resolve in the review queue; the value stays withheld until then.",
            })

    # 4. Documents on file that haven't been parsed yet.
    unparsed = [d for d in _manifest().get(property_id, [])
                if d["doc_type"] != "public_record" and not any(c["doc_id"] == d["doc_id"] for c in state.chunks)]
    if unparsed:
        found.append({
            "level": "warning",
            "title": f"{_count(len(unparsed), 'document')} on file not parsed yet",
            "detail": ", ".join(f"{DOC_TYPES.get(d['doc_type'], d['doc_type'])} {d['doc_id']}" for d in unparsed)
                      + ". The answer can't use what hasn't been parsed.",
            "cites": [],
            "action": "Run the ingestion pipeline on these documents.",
        })

    # 5. Market-drift safety switch for this neighborhood.
    breaker = state.breaker_state.get(prop.get("submarket", ""), {})
    if breaker.get("tripped"):
        found.append({
            "level": "warning",
            "title": f"Stricter checks in {prop['submarket']}",
            "detail": "Recent valuations here have been less accurate than usual, so the limits below are tighter.",
            "cites": [],
            "action": "",
        })
    return found


def calculation(valuation_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """The inputs and arithmetic behind the engine's value, for the expandable section."""
    v = state.valuations.get(valuation_id or "")
    if not v:
        return None
    prop = state.properties.get(v.property_id, {})
    alpha = settings.get("reconcile", {}).get("alpha_sales_comp", 0.70)
    g2 = settings.get("g2", {}).get("tightened" if v.is_tightened else "normal", {})

    subject = [
        {"label": FEATURES[k][0], "value": prop.get(k), "unit": FEATURES[k][1], "source": "County record"}
        for k in FEATURES if prop.get(k) is not None
    ]

    used = [c for c in v.comps if not c.dropped and c.weight > 0]
    used.sort(key=lambda c: c.weight, reverse=True)
    comps = [{
        "address": state.properties.get(c.comp_property_id, {}).get("address_line", c.comp_property_id),
        "property_id": c.comp_property_id,
        "sale_date": str(c.sale_date)[:10],
        "distance_mi": c.distance_mi,
        "sale_price": c.sale_price,
        "time_adj": c.time_adj_price - c.sale_price,
        "adjustments": [{"label": FEATURES.get(k, (k, ""))[0], "dollars": d} for k, d in c.adjustments.items() if abs(d) >= 1],
        "net_adj": c.net_adj_dollars,
        "adjusted_price": c.adjusted_price,
        "weight": c.weight,
    } for c in used]
    excluded = [c for c in v.comps if c not in used]

    range_width = (v.high - v.low) / v.point if v.point else 0.0
    divergence = abs(v.sales_comp_value - v.avm_value) / v.point if v.point else 0.0
    min_comps = g2.get("min_comps", 3)
    checks = [
        {"label": "Comparable sales used", "value": str(len(used)), "limit": f"at least {min_comps}", "ok": len(used) >= min_comps},
        {"label": "Range width", "value": f"{range_width:.1%}", "limit": f"at most {g2.get('max_range_width', 0.2):.0%}", "ok": range_width <= g2.get("max_range_width", 0.2)},
        {"label": "Comparable sales vs. price model", "value": f"{divergence:.1%}", "limit": f"at most {g2.get('max_divergence', 0.1):.0%}", "ok": divergence <= g2.get("max_divergence", 0.1)},
    ]
    held = state.held_facts.get(v.property_id, [])
    checks.append({"label": "Facts on hold", "value": ", ".join(FEATURES.get(h, (h, ""))[0] for h in held) or "none",
                   "limit": "none", "ok": not held})

    comps_cfg = settings.get("comps", {})
    submarket = prop.get("submarket", "")
    grid = state.submarket_grids.get(submarket, {})
    ppsf = state.market_index.get(submarket, {}).get(v.effective_date[:7])
    rates = [
        {"label": FEATURES.get(k, (k, ""))[0],
         "rate": f"${abs(r):,.0f} per {'sq ft' if k == 'gla_sqft' else 'year' if k == 'age_yrs' else 'grade' if k in ('condition_c', 'quality_q') else 'unit'}"}
        for k, r in grid.items() if abs(r) >= 1
    ]

    return {
        "submarket": submarket,
        "method": {
            "radius_mi": [round(m / 1609.34) for m in comps_cfg.get("radius_m_steps", [1609, 3219, 4828])],
            "lookback_months": max(comps_cfg.get("lookback_months_steps", [6, 9, 12])),
            "candidates": len(v.comps),
            "max_used": comps_cfg.get("max_used", 6),
            "max_gross_adj_pct": comps_cfg.get("max_gross_adj_pct", 0.25),
            "rates": rates,
            "median_ppsf": ppsf,
        },
        "valuation_id": v.valuation_id,
        "effective_date": v.effective_date,
        "subject": subject,
        "comps": comps,
        "excluded_count": len(excluded),
        "excluded_reasons": _group_exclusions(excluded, comps_cfg.get("max_gross_adj_pct", 0.25)),
        "sales_comp_value": v.sales_comp_value,
        "avm_value": v.avm_value,
        "alpha": alpha,
        "point": v.point,
        "low": v.low,
        "high": v.high,
        "shown": v.gate_result == "shown",
        "checks": checks,
    }


def _group_exclusions(excluded: List[Any], max_gross: float) -> List[str]:
    too_different = sum(1 for c in excluded if c.dropped)
    lower_ranked = len(excluded) - too_different
    out = []
    if too_different:
        out.append(f"{too_different} needed more than {max_gross:.0%} of their price in adjustments, so they're too different to compare")
    if lower_ranked:
        out.append(f"{lower_ranked} were less similar than the sales used")
    return out


def _count(n: int, noun: str) -> str:
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four"}
    return f"{words.get(n, n)} {noun}{'' if n == 1 else 's'}"


def _cites(evidence: str) -> List[Dict[str, Any]]:
    """'DOC-A p.2; DOC-B p.1' -> [{'doc_id': 'DOC-A', 'page': 2}, ...]"""
    import re
    return [{"doc_id": d, "page": int(p)} for d, p in re.findall(r"(DOC-[A-Z0-9-]+) p\.(\d+)", evidence or "")]


def _arrivals() -> set:
    from pipeline.ingest import ARRIVALS
    return ARRIVALS


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]
