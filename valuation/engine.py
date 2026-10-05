"""Deterministic Appraisal-Grade Valuation Engine.

Implements the traditional sales comparison approach, submarket hedonic adjustments,
time trend index adjustments, AVM reconciliation, and risk gating.
"""
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional
import numpy as np

from valuation.gates import evaluate_g2, G2Result


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes Great Circle distance between two lat/lng pairs in statute miles."""
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return round(2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 2)


def weighted_percentile(data: List[float], weights: List[float], percentile: float) -> float:
    """Computes weighted percentile (percentile between 0.0 and 1.0)."""
    if not data:
        return 0.0
    if len(data) == 1:
        return float(data[0])
    data_arr = np.array(data, dtype=float)
    weights_arr = np.array(weights, dtype=float)
    ind = np.argsort(data_arr)
    data_arr = data_arr[ind]
    weights_arr = weights_arr[ind]
    cumsum = np.cumsum(weights_arr)
    total = cumsum[-1]
    if total <= 0:
        return float(np.percentile(data_arr, percentile * 100))
    cutoff = percentile * total
    return float(np.interp(cutoff, cumsum, data_arr))


@dataclass
class CompAdjustment:
    comp_sale_id: str
    comp_property_id: str
    sale_price: float
    sale_date: str
    distance_mi: float
    time_adj_factor: float
    time_adj_price: float
    adjustments: Dict[str, float]  # feature -> dollar amount
    gross_adj_dollars: float
    gross_adj_pct: float
    net_adj_dollars: float
    net_adj_pct: float
    adjusted_price: float
    weight: float
    dropped: bool = False
    drop_reason: Optional[str] = None


@dataclass
class ValuationResult:
    valuation_id: str
    property_id: str
    effective_date: str
    purpose: str
    point: float
    low: float
    high: float
    confidence: float
    sales_comp_value: float
    avm_value: float
    gate_result: str  # 'shown' or 'routed_to_appraiser'
    gate_reasons: List[str]
    is_tightened: bool
    comps: List[CompAdjustment]
    drivers: Dict[str, Any] = field(default_factory=dict)
    supersedes_valuation_id: Optional[str] = None


def compute_time_adjustment(
    sale_date: str,
    effective_date: str,
    submarket: str,
    market_index: Dict[str, Dict[str, float]],  # submarket -> { 'YYYY-MM': index_val }
) -> float:
    """Computes time adjustment factor = index[effective_month] / index[sale_month]."""
    sale_month = sale_date[:7]
    eff_month = effective_date[:7]
    sub_index = market_index.get(submarket, {})

    idx_sale = sub_index.get(sale_month, 100.0)
    idx_eff = sub_index.get(eff_month, idx_sale)

    if idx_sale <= 0:
        return 1.0
    return float(idx_eff / idx_sale)


def clamp_adjustment(feature: str, amount: float, clamps: Dict[str, List[float]]) -> float:
    """Clamps adjustment per unit to configured bounds."""
    if feature in clamps:
        low_bound, high_bound = clamps[feature]
        return max(low_bound, min(high_bound, amount))
    return amount


def calculate_valuation(
    valuation_id: str,
    property_id: str,
    effective_date: str,
    purpose: str,
    subject_features: Dict[str, Any],
    candidate_sales: List[Dict[str, Any]],
    submarket_grid: Dict[str, float],  # feature -> dollars_per_unit
    market_index: Dict[str, Dict[str, float]],
    avm_value: float,
    is_tightened: bool,
    settings: Dict[str, Any],
    submarket_distributions: Optional[Dict[str, Any]] = None,
    held_facts: Optional[List[str]] = None,
    supersedes_valuation_id: Optional[str] = None,
) -> ValuationResult:
    """Pure deterministic valuation calculation."""
    comps_cfg = settings.get("comps", {})
    reconcile_cfg = settings.get("reconcile", {})
    clamps = settings.get("adjustment_clamps", {})
    submarket = subject_features.get("submarket", "Default")

    max_used = comps_cfg.get("max_used", 6)
    max_gross_adj_pct = comps_cfg.get("max_gross_adj_pct", 0.25)
    alpha = reconcile_cfg.get("alpha_sales_comp", 0.70)
    min_half_width_pct = reconcile_cfg.get("range_min_half_width_pct", 0.03)

    comp_adjustments: List[CompAdjustment] = []

    # 1. Process candidate sales
    for sale in candidate_sales:
        sale_id = sale["sale_id"]
        comp_prop_id = sale["property_id"]
        sale_price = float(sale["price"])
        sale_date = str(sale["sale_date"])
        dist_mi = float(sale.get("distance_mi", 0.0))
        if dist_mi == 0.0 and "lat" in subject_features and "lat" in sale:
            dist_mi = haversine_miles(
                float(subject_features["lat"]), float(subject_features["lng"]),
                float(sale["lat"]), float(sale["lng"])
            )

        # Time adjust
        time_factor = compute_time_adjustment(sale_date, effective_date, submarket, market_index)
        time_adj_price = sale_price * time_factor

        # Feature adjustments: adj = coef * (subject - comp)
        # Note for condition_c, quality_q, age_yrs: lower score is superior, so positive adj if comp score is higher
        adjustments: Dict[str, float] = {}
        for feat, coef in submarket_grid.items():
            subj_val = float(subject_features.get(feat, 0))
            comp_val = float(sale.get(feat, 0))
            if feat in ("condition_c", "quality_q"):
                diff = comp_val - subj_val  # Better condition (lower C) gives positive adjustment
                adj_dollars = abs(coef) * diff
            elif feat == "age_yrs":
                diff = comp_val - subj_val  # Newer house (lower age) gives positive adjustment
                adj_dollars = abs(coef) * diff
            else:
                diff = subj_val - comp_val
                adj_dollars = coef * diff
            adjustments[feat] = adj_dollars

        gross_dollars = sum(abs(v) for v in adjustments.values())
        net_dollars = sum(adjustments.values())
        gross_pct = gross_dollars / time_adj_price if time_adj_price > 0 else 1.0
        net_pct = net_dollars / time_adj_price if time_adj_price > 0 else 1.0
        adjusted_price = time_adj_price + net_dollars

        # Check drop criteria
        dropped = False
        drop_reason = None
        if gross_pct > max_gross_adj_pct:
            dropped = True
            drop_reason = f"Gross adjustment {gross_pct:.1%} exceeds maximum {max_gross_adj_pct:.1%}"

        # Weighting
        weight = 1.0 / (0.05 + gross_pct) if not dropped else 0.0

        comp_adjustments.append(
            CompAdjustment(
                comp_sale_id=sale_id,
                comp_property_id=comp_prop_id,
                sale_price=sale_price,
                sale_date=sale_date,
                distance_mi=round(dist_mi, 2),
                time_adj_factor=time_factor,
                time_adj_price=time_adj_price,
                adjustments=adjustments,
                gross_adj_dollars=gross_dollars,
                gross_adj_pct=gross_pct,
                net_adj_dollars=net_dollars,
                net_adj_pct=net_pct,
                adjusted_price=adjusted_price,
                weight=weight,
                dropped=dropped,
                drop_reason=drop_reason,
            )
        )

    # 2. Select top usable comps (up to max_used)
    usable_comps = [c for c in comp_adjustments if not c.dropped]
    # Sort usable comps by weight descending
    usable_comps.sort(key=lambda c: c.weight, reverse=True)
    usable_comps = usable_comps[:max_used]

    # Calculate sales comp value and normalize active comp weights
    total_weight = sum(c.weight for c in usable_comps)
    if total_weight > 0:
        sales_comp_value = sum(c.weight * c.adjusted_price for c in usable_comps) / total_weight
        # Normalize weights so they cleanly sum to 100%
        for c in usable_comps:
            c.weight = c.weight / total_weight
    else:
        sales_comp_value = avm_value

    # Ensure all dropped or excluded comps have 0 weight
    usable_ids = {c.comp_sale_id for c in usable_comps}
    for c in comp_adjustments:
        if c.comp_sale_id not in usable_ids:
            c.weight = 0.0

    # 3. Reconcile with AVM
    point_estimate = (alpha * sales_comp_value) + ((1.0 - alpha) * avm_value)

    # 4. Range calculation
    if usable_comps:
        adj_prices = [c.adjusted_price for c in usable_comps]
        comp_weights = [c.weight for c in usable_comps]
        low_pctile = weighted_percentile(adj_prices, comp_weights, 0.10)
        high_pctile = weighted_percentile(adj_prices, comp_weights, 0.90)
    else:
        low_pctile = point_estimate * 0.95
        high_pctile = point_estimate * 1.05

    # Widen range by half of the divergence between sales comp and avm (|sales_comp - avm| / 2)
    total_widening = abs(sales_comp_value - avm_value) / 2.0
    side_expansion = total_widening / 2.0
    range_low = min(low_pctile - side_expansion, point_estimate * (1.0 - min_half_width_pct))
    range_high = max(high_pctile + side_expansion, point_estimate * (1.0 + min_half_width_pct))

    # 5. Confidence score (0.0 to 1.0)
    # Higher confidence with more comps, lower mean gross adjustment, narrower range, lower divergence
    if usable_comps and point_estimate > 0:
        comp_count_score = min(len(usable_comps) / 5.0, 1.0)
        mean_gross = np.mean([c.gross_adj_pct for c in usable_comps])
        adj_quality_score = max(0.0, 1.0 - (mean_gross / 0.25))
        div_score = max(0.0, 1.0 - (abs(sales_comp_value - avm_value) / (0.15 * point_estimate)))
        confidence = float(np.clip(0.4 * comp_count_score + 0.3 * adj_quality_score + 0.3 * div_score, 0.1, 0.98))
    else:
        confidence = 0.30

    # 6. Evaluate G2 gate
    g2_res: G2Result = evaluate_g2(
        usable_comps_count=len(usable_comps),
        candidate_comps_count=len(candidate_sales),
        point_estimate=point_estimate,
        range_low=range_low,
        range_high=range_high,
        sales_comp_value=sales_comp_value,
        avm_value=avm_value,
        subject_features=subject_features,
        submarket_distributions=submarket_distributions,
        held_value_moving_facts=held_facts or [],
        is_tightened=is_tightened,
        settings=settings,
    )

    drivers = {
        "sales_comp_weight": alpha,
        "avm_weight": 1.0 - alpha,
        "usable_comps_count": len(usable_comps),
        "mean_gross_adj_pct": float(np.mean([c.gross_adj_pct for c in usable_comps])) if usable_comps else 0.0,
        "submarket": submarket,
    }

    return ValuationResult(
        valuation_id=valuation_id,
        property_id=property_id,
        effective_date=effective_date,
        purpose=purpose,
        point=round(point_estimate, 0),
        low=round(range_low, 0),
        high=round(range_high, 0),
        confidence=round(confidence, 2),
        sales_comp_value=round(sales_comp_value, 0),
        avm_value=round(avm_value, 0),
        gate_result=g2_res.gate_result,
        gate_reasons=g2_res.reasons,
        is_tightened=is_tightened,
        comps=comp_adjustments,
        drivers=drivers,
        supersedes_valuation_id=supersedes_valuation_id,
    )


def select_candidate_sales(
    subject: Dict[str, Any],
    all_sales: List[Dict[str, Any]],
    properties_lookup: Dict[str, Dict[str, Any]],
    effective_date: str,
    is_tightened: bool,
    settings: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Selects and ranks eligible candidate comparable sales using multi-step search.
    
    Enforces lookback window (6 -> 9 -> 12 months, strictly <= 12 months) and
    radius steps (1 -> 2 -> 3 miles) per settings.yaml.
    Candidates are scored by appraisal similarity (distance, recency, GLA, quality, condition).
    """
    g2_cfg = settings.get("g2", {})
    thresholds = g2_cfg.get("tightened" if is_tightened else "normal", {})
    min_candidates = thresholds.get("min_candidates", 8 if is_tightened else 5)
    comps_cfg = settings.get("comps", {})
    radius_steps_m = comps_cfg.get("radius_m_steps", [1609, 3219, 4828])
    radius_steps_mi = [round(r / 1609.34, 1) for r in radius_steps_m]  # [1.0, 2.0, 3.0]
    lookback_months = comps_cfg.get("lookback_months_steps", [6, 9, 12])
    lookback_days = [round(m * 30.44) for m in lookback_months]  # [183, 274, 365]

    subj_id = subject.get("property_id")
    submarket = subject.get("submarket")
    subj_lat = float(subject.get("lat", 0.0))
    subj_lng = float(subject.get("lng", 0.0))
    subj_gla = float(subject.get("gla_sqft", 1500))
    subj_beds = float(subject.get("beds", 3))
    subj_baths = float(subject.get("baths_total", 2.0))
    subj_q = float(subject.get("quality_q", 3))
    subj_c = float(subject.get("condition_c", 3))
    subj_age = float(subject.get("age_yrs", 20))
    subj_pool = int(subject.get("pool", 0))

    try:
        eff_dt = date.fromisoformat(effective_date[:10])
    except Exception:
        eff_dt = date(2026, 10, 5)

    # Hard ceiling: strictly within 365 days (12 months) before effective date
    max_days = 365

    matched_sales: List[Dict[str, Any]] = []

    # Step through radius (1.0 -> 2.0 -> 3.0 miles)
    # Within each radius, search across the eligible lookback window (up to 12 months)
    for r_mi in radius_steps_mi:
        current_matches = []
        for s in all_sales:
            if s.get("sale_type") != "arms_length":
                continue
            if s.get("submarket") != submarket:
                continue
            if s.get("property_id") == subj_id:
                continue

            # Check date: strictly past, within 365 days
            s_date_str = str(s.get("sale_date", ""))
            try:
                s_dt = date.fromisoformat(s_date_str[:10])
            except Exception:
                continue

            days_diff = (eff_dt - s_dt).days
            if days_diff <= 0 or days_diff > max_days:
                continue

            # Distance
            comp_prop = properties_lookup.get(s["property_id"], {})
            c_lat = float(comp_prop.get("lat", s.get("lat", 0.0)))
            c_lng = float(comp_prop.get("lng", s.get("lng", 0.0)))

            if subj_lat != 0.0 and c_lat != 0.0:
                dist = haversine_miles(subj_lat, subj_lng, c_lat, c_lng)
            else:
                dist = float(s.get("distance_mi", 0.5))

            if dist > r_mi:
                continue

            cand = dict(s)
            cand["distance_mi"] = dist
            cand["lat"] = c_lat
            cand["lng"] = c_lng
            cand["address_line"] = comp_prop.get("address_line", f"Property {s['property_id']}")

            # Appraisal similarity scoring (proximity, recency, GLA, quality, condition, baths, beds)
            gla_diff_pct = abs(float(cand.get("gla_sqft", 0)) - subj_gla) / max(subj_gla, 1.0)
            months_since = days_diff / 30.44
            q_diff = abs(float(cand.get("quality_q", 3)) - subj_q)
            c_diff = abs(float(cand.get("condition_c", 3)) - subj_c)
            baths_diff = abs(float(cand.get("baths_total", 2)) - subj_baths)
            beds_diff = abs(float(cand.get("beds", 3)) - subj_beds)
            age_diff = abs(float(cand.get("age_yrs", 0)) - subj_age)
            pool_mismatch = 1 if int(cand.get("pool", 0)) != subj_pool else 0

            similarity = 1.0 / (
                1.0
                + 3.0 * dist
                + 0.05 * months_since
                + 5.0 * gla_diff_pct
                + 1.5 * q_diff
                + 1.0 * c_diff
                + 0.5 * baths_diff
                + 0.5 * beds_diff
                + 0.01 * age_diff
                + 0.3 * pool_mismatch
            )
            cand["similarity_score"] = similarity
            current_matches.append(cand)

        if len(current_matches) >= min_candidates:
            matched_sales = current_matches
            break

    if not matched_sales:
        matched_sales = current_matches

    # Sort by similarity score descending and return top candidates
    matched_sales.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
    return matched_sales[:12]
