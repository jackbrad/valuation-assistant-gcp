"""Unit tests for G1 and G2 risk gates."""
import pytest
from valuation.gates import evaluate_g1, evaluate_g2
from config.loader import settings


def test_g1_confidence_hold():
    # Confidence 0.65 is below default 0.80
    res = evaluate_g1(
        field_name="gla_sqft",
        value_numeric=2000.0,
        value_string=None,
        confidence=0.65,
        existing_facts=[],
        settings=settings,
    )
    assert res.status == "held"
    assert any("Confidence" in r for r in res.reasons)


def test_g1_cross_source_conflict_22_hilltop():
    # County record says 1,950 sq ft
    active_county_fact = {
        "fact_id": "F-COUNTY-01",
        "field": "gla_sqft",
        "value_numeric": 1950.0,
        "status": "active",
        "retired_at": None,
    }
    # Appraisal says 2,450 sq ft (> 5% difference)
    res = evaluate_g1(
        field_name="gla_sqft",
        value_numeric=2450.0,
        value_string=None,
        confidence=0.95,
        existing_facts=[active_county_fact],
        settings=settings,
    )
    assert res.status == "held"
    assert res.is_conflict is True
    assert res.competing_fact_id == "F-COUNTY-01"
    assert any("Cross-source conflict" in r for r in res.reasons)


def test_g2_normal_vs_tightened():
    subject = {"gla_sqft": 2000}
    # 4 comps: acceptable in normal mode (min 3), but trips in tightened mode (min 5)
    g2_normal = evaluate_g2(
        usable_comps_count=4,
        candidate_comps_count=10,
        point_estimate=400000.0,
        range_low=380000.0,
        range_high=420000.0,  # width = 40k / 400k = 10% (ok in both)
        sales_comp_value=400000.0,
        avm_value=410000.0,   # div = 10k / 400k = 2.5% (ok in both)
        subject_features=subject,
        submarket_distributions={"gla_p1": 800, "gla_p99": 4500},
        held_value_moving_facts=[],
        is_tightened=False,
        settings=settings,
    )
    assert g2_normal.gate_result == "shown"

    g2_tightened = evaluate_g2(
        usable_comps_count=4,
        candidate_comps_count=10,
        point_estimate=400000.0,
        range_low=380000.0,
        range_high=420000.0,
        sales_comp_value=400000.0,
        avm_value=410000.0,
        subject_features=subject,
        submarket_distributions={"gla_p1": 800, "gla_p99": 4500},
        held_value_moving_facts=[],
        is_tightened=True,
        settings=settings,
    )
    assert g2_tightened.gate_result == "routed_to_appraiser"
    assert any("Insufficient usable comps" in r for r in g2_tightened.reasons)


def test_g2_out_of_distribution_7_wren():
    # 7 Wren Ct has 6,800 sq ft, which is above 99th percentile
    subject = {"gla_sqft": 6800}
    g2_res = evaluate_g2(
        usable_comps_count=5,
        candidate_comps_count=10,
        point_estimate=950000.0,
        range_low=900000.0,
        range_high=1000000.0,
        sales_comp_value=950000.0,
        avm_value=940000.0,
        subject_features=subject,
        submarket_distributions={"gla_p1": 800, "gla_p99": 4500},
        held_value_moving_facts=[],
        is_tightened=False,
        settings=settings,
    )
    assert g2_res.gate_result == "routed_to_appraiser"
    assert any("out of distribution" in r for r in g2_res.reasons)
