"""Tests specifically verifying acceptance criteria for FIXES.md P0 items."""
import pytest
from app.state import DemoState, ReviewItem
from fastapi.testclient import TestClient
from app.main import app


def test_p0_comp_distances_varied():
    """P0 Item 1: 14 Larkspur comps show varied haversine distances between 0.1 and 3 mi."""
    demo = DemoState()
    val = demo.run_valuation_for_property("P-000014")
    assert len(val.comps) >= 6
    distances = [c.distance_mi for c in val.comps]
    assert all(d > 0.0 for d in distances), f"Found 0.0 distance: {distances}"
    assert any(0.1 <= d <= 3.0 for d in distances)
    assert len(set(distances)) > 1, f"Expected varied distances, got {distances}"


def test_p0_comp_eligibility_no_2023_sales():
    """P0 Item 2: Lookback window strictly <= 12 months. No 2023 sales in 14 Larkspur grid."""
    demo = DemoState()
    val = demo.run_valuation_for_property("P-000014")
    for c in val.comps:
        assert not c.sale_date.startswith("2023"), f"Comp {c.comp_sale_id} has 2023 sale date: {c.sale_date}"
        assert c.sale_date >= "2025-10-05", f"Comp {c.comp_sale_id} is older than 12 months: {c.sale_date}"


def test_p0_18_larkspur_shown_with_ge_4_comps_and_conf_ge_60():
    """P0 Item 3: 18 Larkspur produces a shown valuation with >= 4 comps and confidence >= 60%."""
    demo = DemoState()
    val = demo.run_valuation_for_property("P-000018")
    assert val.gate_result == "shown"
    usable = [c for c in val.comps if not c.dropped]
    assert len(usable) >= 4, f"Expected >= 4 usable comps, got {len(usable)}"
    assert val.confidence >= 0.60, f"Expected confidence >= 60%, got {val.confidence}"
    # Weights should sum to 1.0 (100%)
    active_weights = sum(c.weight for c in val.comps)
    assert pytest.approx(active_weights, abs=1e-3) == 1.0


def test_p0_range_width_and_divergence_not_duplicate():
    """P0 Item 4: Range width and comp/AVM divergence are distinct formulas and distinct values."""
    demo = DemoState()
    val = demo.run_valuation_for_property("P-000014")
    range_width = (val.high - val.low) / val.point
    div = abs(val.sales_comp_value - val.avm_value) / val.point
    assert abs(range_width - div) > 0.05, f"Range width ({range_width:.1%}) and div ({div:.1%}) are suspiciously identical!"


def test_p0_ripple_direction_downward():
    """P0 Item 5: Correcting 14 Larkspur from 1,240 to 2,080 causes dependent 18 Larkspur to drop by 3-6%."""
    demo = DemoState()
    # Baseline for 18 Larkspur before correction
    val18_before = demo.run_valuation_for_property("P-000018")
    
    # Flag on 14 Larkspur
    item = ReviewItem(
        item_id="REV-DEMO-14",
        target_type="fact",
        property_id="P-000014",
        property_address="14 Larkspur Ln",
        field_name="gla_sqft",
        current_value=1240,
        proposed_value=2080,
        reason="Stale data — addition on p.2 of inspection",
        evidence_desc="DOC-INS-000014 p.2 + Permit #CH-24-0817",
        evidence_uri=None,
        flagger_id="alex.reviewer",
        route="steward",
        requires_two_approvals=True,
        status="pending",
        approvals=["sam.reviewer", "pat.steward"],
    )
    demo.review_queue.append(item)
    res = demo.apply_correction("REV-DEMO-14", "pat.steward")
    assert res["status"] == "success"

    comp_aff = next(a for a in res["affected"] if a["property_id"] == "P-000018")
    assert comp_aff["delta_pct"] < 0, "Expected 18 Larkspur value to go DOWN, not up!"
    assert -0.06 <= comp_aff["delta_pct"] <= -0.03, f"Expected 3-6% drop, got {comp_aff['delta_pct']:.1%}"


def test_p0_hide_point_estimate_when_routed():
    """P0 Item 6: Hide point estimate when G2 routes to appraiser."""
    client = TestClient(app)
    # 7 Wren Ct in Riverside routes to appraiser
    resp = client.get("/ask?q=7+Wren+Ct&user=alex.reviewer")
    assert resp.status_code == 200
    assert "Needs an appraiser" in resp.text
    assert "Point withheld" in resp.text


def test_p0_model_health_real_90d_counts():
    """P0 Item 7: Trailing 90-day transactions is real (134 total, 40 Larkspur, 35 Old Town, etc.)."""
    client = TestClient(app)
    resp = client.get("/health?user=alex.reviewer")
    assert resp.status_code == 200
    assert "based on 40 sales in the last 90 days" in resp.text
    assert "1,949" not in resp.text


def test_withheld_value_never_reaches_the_model():
    """When the engine routes to an appraiser, the agent's tool output has no range or point."""
    from agent.appraisal_agent import build_tools
    _, _, _, run_valuation = build_tools()
    routed = run_valuation("P-000014")
    assert routed["gate_result"] == "appraiser"
    assert "range_low" not in routed and "range_high" not in routed
    assert routed["point_estimate"] is None
    shown = run_valuation("P-000018")
    assert shown["gate_result"] == "shown"
    assert shown["range_low"] < shown["point_estimate"] < shown["range_high"]


def test_data_gate_holds_conflicting_document_fact():
    """A parsed fact that disagrees with the county record is held, queued, and blocks the value (G1 -> G2)."""
    from app.state import DemoState
    from app import explain
    from pipeline.ingest import queue_conflict

    s = DemoState()
    s.held_facts.pop("P-000018", None)
    s.review_queue = [i for i in s.review_queue if i.property_id != "P-000018"]
    assert s.run_valuation_for_property("P-000018").gate_result == "shown"

    fact = {"property_id": "P-000018", "field": "condition_c", "value_numeric": 4.0, "value_string": "C4",
            "doc_id": "DOC-INS-001640", "page": 2}
    queue_conflict(s, fact, s.properties["P-000018"]["condition_c"], "inspection")

    item = s.review_queue[0]
    assert item.flagger_id == "pipeline_g1" and item.requires_two_approvals
    assert "C3 vs inspection report C4" in item.reason
    v = s.run_valuation_for_property("P-000018")
    assert v.gate_result == "routed_to_appraiser"
    assert any("condition_c" in r for r in v.gate_reasons)
