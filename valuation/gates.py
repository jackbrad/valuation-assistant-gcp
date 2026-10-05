"""Risk gates implementation for Appraisal AI.

G1: Data validation and cross-source conflict gate.
G2: Valuation confidence, divergence, and distribution gate.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class G1Result:
    status: str  # 'active', 'held', 'rejected'
    reasons: List[str] = field(default_factory=list)
    is_conflict: bool = False
    competing_fact_id: Optional[str] = None


@dataclass
class G2Result:
    gate_result: str  # 'shown' or 'routed_to_appraiser'
    reasons: List[str] = field(default_factory=list)
    is_tightened: bool = False


def evaluate_g1(
    field_name: str,
    value_numeric: Optional[float],
    value_string: Optional[str],
    confidence: float,
    existing_facts: List[Dict[str, Any]],
    settings: Dict[str, Any],
) -> G1Result:
    """Evaluate candidate fact against G1 rules:
    1. Confidence threshold check.
    2. Numerical range check.
    3. Cross-source conflict check against active facts for the same property + field.
    """
    g1_cfg = settings.get("g1", {})
    min_conf = g1_cfg.get("min_confidence", 0.80)
    ranges = g1_cfg.get("ranges", {})
    tolerances = g1_cfg.get("tolerance", {})

    reasons: List[str] = []

    # 1. Confidence check
    if confidence < min_conf:
        reasons.append(f"Confidence {confidence:.2f} is below G1 minimum {min_conf:.2f}")

    # 2. Range check for numeric fields
    if value_numeric is not None and field_name in ranges:
        min_val, max_val = ranges[field_name]
        if not (min_val <= value_numeric <= max_val):
            reasons.append(
                f"Field '{field_name}' value {value_numeric} outside allowed range [{min_val}, {max_val}]"
            )

    # 3. Cross-source conflict check
    is_conflict = False
    competing_id = None

    for f in existing_facts:
        if f.get("field") == field_name and f.get("status") == "active" and f.get("retired_at") is None:
            # Check numerical tolerance
            if value_numeric is not None and f.get("value_numeric") is not None:
                existing_val = float(f["value_numeric"])
                tol_pct = tolerances.get(field_name)
                if tol_pct is not None:
                    # Percentage tolerance check (e.g. 0.05 for 5%)
                    if abs(value_numeric - existing_val) / max(existing_val, 1.0) > tol_pct:
                        is_conflict = True
                        competing_id = f.get("fact_id")
                        reasons.append(
                            f"Cross-source conflict on '{field_name}': candidate {value_numeric} vs active {existing_val} (tolerance {tol_pct*100:.0f}%)"
                        )
                elif field_name == "year_built":
                    tol_yrs = tolerances.get("year_built", 1)
                    if abs(value_numeric - existing_val) > tol_yrs:
                        is_conflict = True
                        competing_id = f.get("fact_id")
                        reasons.append(
                            f"Cross-source conflict on 'year_built': candidate {value_numeric} vs active {existing_val} (> {tol_yrs} yr difference)"
                        )
                elif int(value_numeric) != int(existing_val):
                    # Exact integer match required
                    is_conflict = True
                    competing_id = f.get("fact_id")
                    reasons.append(
                        f"Cross-source integer mismatch on '{field_name}': candidate {value_numeric} vs active {existing_val}"
                    )
            elif value_string is not None and f.get("value_string") is not None:
                if str(value_string).strip().lower() != str(f["value_string"]).strip().lower():
                    is_conflict = True
                    competing_id = f.get("fact_id")
                    reasons.append(
                        f"Cross-source string mismatch on '{field_name}': candidate '{value_string}' vs active '{f['value_string']}'"
                    )

    if reasons:
        return G1Result(status="held", reasons=reasons, is_conflict=is_conflict, competing_fact_id=competing_id)
    return G1Result(status="active", reasons=[])


def evaluate_g2(
    usable_comps_count: int,
    candidate_comps_count: int,
    point_estimate: float,
    range_low: float,
    range_high: float,
    sales_comp_value: float,
    avm_value: float,
    subject_features: Dict[str, Any],
    submarket_distributions: Optional[Dict[str, Any]],
    held_value_moving_facts: List[str],
    is_tightened: bool,
    settings: Dict[str, Any],
) -> G2Result:
    """Evaluate valuation against G2 rules:
    1. Minimum usable comps.
    2. Range width <= max_range_width.
    3. Divergence between sales_comp and AVM <= max_divergence.
    4. Out-of-distribution subject features.
    5. Any held G1 facts on value-moving fields.
    """
    g2_cfg = settings.get("g2", {})
    mode = "tightened" if is_tightened else "normal"
    thresholds = g2_cfg.get(mode, {})

    min_comps = thresholds.get("min_comps", 5 if is_tightened else 3)
    max_range_width = thresholds.get("max_range_width", 0.12 if is_tightened else 0.20)
    max_divergence = thresholds.get("max_divergence", 0.06 if is_tightened else 0.10)

    reasons: List[str] = []

    # 1. Minimum usable comps check
    if usable_comps_count < min_comps:
        reasons.append(
            f"Insufficient usable comps ({usable_comps_count} < minimum required {min_comps})"
        )

    # 2. Range width check
    if point_estimate > 0:
        range_width = (range_high - range_low) / point_estimate
        if range_width > max_range_width:
            reasons.append(
                f"Range width {range_width:.1%} exceeds {mode} threshold ({max_range_width:.1%})"
            )

    # 3. Divergence check between Sales Comp and AVM
    if point_estimate > 0:
        divergence = abs(sales_comp_value - avm_value) / point_estimate
        if divergence > max_divergence:
            reasons.append(
                f"Divergence between Sales Comp (${sales_comp_value:,.0f}) and AVM (${avm_value:,.0f}) is {divergence:.1%} (exceeds {mode} threshold {max_divergence:.1%})"
            )

    # 4. Out of distribution check
    if submarket_distributions:
        gla = subject_features.get("gla_sqft", 0)
        p1 = submarket_distributions.get("gla_p1", 500)
        p99 = submarket_distributions.get("gla_p99", 5000)
        if gla < p1 or gla > p99:
            reasons.append(
                f"Subject GLA ({gla:,.0f} sq ft) is out of distribution for submarket [{p1:,.0f} - {p99:,.0f}]"
            )

    # 5. Held value-moving facts
    if held_value_moving_facts:
        reasons.append(
            f"Subject has {len(held_value_moving_facts)} held G1 facts on value-moving fields: {', '.join(held_value_moving_facts)}"
        )

    gate_result = "routed_to_appraiser" if reasons else "shown"
    return G2Result(gate_result=gate_result, reasons=reasons, is_tightened=is_tightened)
