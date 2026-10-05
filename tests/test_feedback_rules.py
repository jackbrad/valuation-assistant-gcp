"""Unit tests for feedback loop and two-approver governance rules."""
import pytest
from app.state import DemoState, ReviewItem


def test_stake_blocking_and_two_approvers():
    demo = DemoState()
    
    # Create item
    item = ReviewItem(
        item_id="TEST-01",
        target_type="fact",
        property_id="P-000014",
        property_address="14 Larkspur Ln",
        field_name="gla_sqft",
        current_value=1240,
        proposed_value=2080,
        reason="Stale public record",
        evidence_desc="Permit #CH-24-0817",
        evidence_uri=None,
        flagger_id="alex.reviewer",
        route="steward",
        requires_two_approvals=True,
        status="pending",
    )
    demo.review_queue.append(item)

    # 1. Flagger cannot approve their own flag
    assert item.flagger_id == "alex.reviewer"

    # 2. First approver: sam.reviewer (allowed)
    item.approvals.append("sam.reviewer")
    assert len(item.approvals) == 1
    assert item.status == "pending"  # Needs 2 approvers!

    # 3. Second approver: pat.steward (allowed)
    item.approvals.append("pat.steward")
    assert len(item.approvals) == 2
    # Apply
    demo.apply_correction(item.item_id, "pat.steward")
    assert item.status == "approved"
    assert demo.properties["P-000014"]["gla_sqft"] == 2080
