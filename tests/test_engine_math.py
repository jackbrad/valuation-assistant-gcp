"""Unit tests for deterministic valuation math and comp adjustments."""
import pytest
from valuation.engine import calculate_valuation, compute_time_adjustment
from config.loader import settings


def test_time_adjustment():
    market_index = {
        "Larkspur": {
            "2025-01": 200.0,
            "2025-06": 210.0,
            "2026-01": 220.0,
            "2026-10": 230.0,
        }
    }
    # Comp sold in 2025-01, effective 2026-10 -> 230 / 200 = 1.15
    factor = compute_time_adjustment("2025-01-15", "2026-10-05", "Larkspur", market_index)
    assert pytest.approx(factor, rel=1e-3) == 1.15

    # Same month -> factor = 1.0
    factor_same = compute_time_adjustment("2026-10-01", "2026-10-05", "Larkspur", market_index)
    assert pytest.approx(factor_same, rel=1e-3) == 1.0


def test_valuation_math_reconciliation_and_range():
    subject = {
        "property_id": "P-TEST",
        "submarket": "Larkspur",
        "gla_sqft": 2000,
        "beds": 3,
        "baths_total": 2.0,
        "age_yrs": 10,
        "condition_c": 3,
        "quality_q": 3,
    }

    candidate_sales = [
        {
            "sale_id": "S-01",
            "property_id": "P-COMP1",
            "price": 400000,
            "sale_date": "2026-09-01",
            "distance_mi": 0.3,
            "gla_sqft": 1900,  # 100 sq ft smaller -> +$10k
            "beds": 3,
            "baths_total": 2.0,
            "age_yrs": 10,
            "condition_c": 3,
            "quality_q": 3,
        },
        {
            "sale_id": "S-02",
            "property_id": "P-COMP2",
            "price": 420000,
            "sale_date": "2026-09-10",
            "distance_mi": 0.4,
            "gla_sqft": 2100,  # 100 sq ft larger -> -$10k
            "beds": 3,
            "baths_total": 2.0,
            "age_yrs": 10,
            "condition_c": 3,
            "quality_q": 3,
        },
        {
            "sale_id": "S-03",
            "property_id": "P-COMP3",
            "price": 410000,
            "sale_date": "2026-09-15",
            "distance_mi": 0.5,
            "gla_sqft": 2000,  # exact match -> $0 adj
            "beds": 3,
            "baths_total": 2.0,
            "age_yrs": 10,
            "condition_c": 3,
            "quality_q": 3,
        },
    ]

    submarket_grid = {"gla_sqft": 100.0}
    market_index = {"Larkspur": {"2026-09": 100.0, "2026-10": 100.0}}
    avm_value = 412000.0

    res = calculate_valuation(
        valuation_id="VAL-001",
        property_id="P-TEST",
        effective_date="2026-10-05",
        purpose="refi",
        subject_features=subject,
        candidate_sales=candidate_sales,
        submarket_grid=submarket_grid,
        market_index=market_index,
        avm_value=avm_value,
        is_tightened=False,
        settings=settings,
    )

    # All adjusted comp prices:
    # Comp 1: 400k + (2000-1900)*100 = 410k
    # Comp 2: 420k + (2000-2100)*100 = 410k
    # Comp 3: 410k + 0 = 410k
    # Sales comp value should be exactly 410k!
    assert res.sales_comp_value == 410000.0
    # Reconciled: 0.7 * 410k + 0.3 * 412k = 287k + 123.6k = 410,600
    assert res.point == 410600.0
    assert res.low < res.point < res.high
    assert res.confidence > 0.5
    assert res.gate_result == "shown"
