"""Acceptance tests for cascade revaluation and circuit breaker."""
import pytest
from app.state import DemoState, ReviewItem


def test_cascade_14_larkspur_to_18_larkspur():
    demo = DemoState()
    
    # 1. Flag on 14 Larkspur
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

    # Apply correction
    res = demo.apply_correction("REV-DEMO-14", "pat.steward")
    assert res["status"] == "success"

    # Both 14 Larkspur and 18 Larkspur should be affected in the cascade
    affected_ids = [a["property_id"] for a in res["affected"]]
    assert "P-000014" in affected_ids
    assert "P-000018" in affected_ids

    # 18 Larkspur should be marked as dependent comp
    comp_aff = next(a for a in res["affected"] if a["property_id"] == "P-000018")
    assert comp_aff["role"] == "Dependent Comp"
    assert "P-000014 GLA adjusted" in comp_aff["reason"]


def test_breaker_trips_riverside_only():
    demo = DemoState()
    
    # Riverside should be tripped, others normal
    assert demo.breaker_state["Riverside"]["status"] == "tightened"
    assert demo.breaker_state["Riverside"]["tripped"] is True
    assert demo.breaker_state["Old Town"]["status"] == "normal"
    assert demo.breaker_state["Larkspur"]["status"] == "normal"
    assert demo.breaker_state["Hilltop"]["status"] == "normal"

    # Tripped submarket has unanchored MdAPE > 8%
    assert demo.breaker_state["Riverside"]["unanchored_mdape"] > 0.08
