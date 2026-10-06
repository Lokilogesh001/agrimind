"""Deterministic Agronomic Safety Guard and Decision Sensitivity.

Enforces hard agronomic safety rules between conflict resolution and the final decision.
The Safety Guard is NOT an LLM. It enforces hard safety constraints:
- Rule A: Missing critical soil evidence (blocks exact fertilizer dosage)
- Rule B: Low disease confidence (blocks disease-specific treatment)
- Rule C: Crop mismatch (blocks disease-specific action)
- Rule D: Unsafe weather (blocks unsafe operations, enforces DELAY)
- Rule E: Stale critical data (downgrades confidence, prevents high-risk decisions)
- Rule F: Conflicting evidence (lowers stability, surfaces conflicts, enforces safe action)
"""
from __future__ import annotations

from typing import Any


def apply_agronomic_safety_guard(
    state: Any,
    candidate_action: str = "monitor",
    candidate_reason: str = "default",
) -> tuple[str, str, list[str], float]:
    """Execute the deterministic Agronomic Safety Guard.

    Returns:
        final_action: constrained or confirmed action
        final_reason: updated reason if safety constrained
        applied_constraints: list of human-readable constraint descriptions
        confidence_delta: penalty to subtract from raw confidence
    """
    applied_constraints: list[str] = []
    action = candidate_action
    reason = candidate_reason
    confidence_penalty = 0.0

    w = getattr(state, "weather", None)
    s = getattr(state, "soil", None)
    d = getattr(state, "disease", None)
    m = getattr(state, "market", None)

    # -------------------------------------------------------------------------
    # Rule A — Missing critical soil evidence
    # If fertilizer dosage would depend on NPK but measured NPK is unavailable:
    # DO NOT issue exact fertilizer dosage.
    # -------------------------------------------------------------------------
    npk_avail = getattr(s, "npk_available", False) if s else False
    if not npk_avail:
        if action == "apply_fertilizer":
            action = "monitor"
            reason = "rule_a_soil_safety_veto"
            applied_constraints.append(
                "Rule A (Soil Safety): Soil testing is required before precise fertilizer recommendation. "
                "NPK measurements were not provided, so exact nutrient dosage was blocked."
            )
        else:
            applied_constraints.append(
                "Rule A (Soil Advisory): Soil testing is required before precise fertilizer recommendation. "
                "Nutrient deficiency was not calculated due to missing NPK measurements."
            )

    # -------------------------------------------------------------------------
    # Rule B — Low disease confidence
    # If disease confidence is below actionable threshold (0.60):
    # DO NOT issue disease-specific treatment recommendation.
    # -------------------------------------------------------------------------
    d_class = getattr(d, "predicted_class", None) if d else None
    d_conf = getattr(d, "confidence", 0.0) if d else 0.0
    d_actionable = getattr(d, "actionable", False) if d else False
    d_mismatch = getattr(d, "crop_mismatch", False) if d else False
    selected_crop_name = getattr(getattr(state, "crop", None), "crop", "") or "selected crop"

    if d_class and not d_mismatch and d_conf < 0.60:
        if action == "DISEASE_MANAGEMENT_FIRST":
            action = "monitor"
            reason = "rule_b_low_disease_confidence"
        applied_constraints.append(
            f"Rule B (Disease Confidence): Disease evidence is insufficient for treatment advice "
            f"(confidence {d_conf:.2f} < 0.60 threshold). Disease-specific treatment blocked."
        )

    # -------------------------------------------------------------------------
    # Rule C — Crop mismatch
    # If disease model prediction conflicts with selected crop:
    # DO NOT issue disease-specific action.
    # -------------------------------------------------------------------------
    if d_mismatch:
        if action == "DISEASE_MANAGEMENT_FIRST":
            action = "monitor"
            reason = "rule_c_crop_mismatch"
        dis_display = d_class.replace("___", " ").replace("_", " ") if d_class else "disease prediction"
        applied_constraints.append(
            f"Rule C (Crop Match Guard): Disease model prediction conflicts with selected crop "
            f"('{selected_crop_name}'). Selected crop: {selected_crop_name}, "
            f"Detected crop/disease: {dis_display}, Confidence: {d_conf:.2f}. "
            f"Disease-specific action prohibited."
        )

    # -------------------------------------------------------------------------
    # Rule D — Unsafe weather
    # If configured weather safety threshold is exceeded:
    # BLOCK unsafe agronomic operation (e.g. fertilizer application).
    # -------------------------------------------------------------------------
    from agents.weather_agent import get_weather_risk_level
    rainfall_risk = getattr(w, "rainfall_risk", 0.0) if w else 0.0
    w_level = getattr(w, "risk_level", None) or get_weather_risk_level(rainfall_risk)
    if w_level in ("HIGH", "SEVERE") or round(rainfall_risk, 4) >= 0.60:
        desc = "Severe rainfall risk" if w_level == "SEVERE" else "High rainfall risk"
        if action == "apply_fertilizer":
            action = "delay"
            reason = "rule_d_weather_safety_veto"
            applied_constraints.append(
                f"Rule D (Weather Safety): {desc} ({rainfall_risk:.2f} - {w_level}) "
                f"threatens chemical wash-off and leaching. Immediate field application blocked; DELAY enforced."
            )
        elif action != "delay":
            applied_constraints.append(
                f"Rule D (Weather Notice): {desc} ({rainfall_risk:.2f} - {w_level}) "
                f"requires delaying chemical spraying or top-dressing operations."
            )

    # -------------------------------------------------------------------------
    # Rule E — Stale or unavailable critical data
    # If critical weather/market data is stale or unavailable:
    # Downgrade confidence and prevent high-risk decisions.
    # -------------------------------------------------------------------------
    w_status = getattr(w, "status", "AVAILABLE") if w else "UNAVAILABLE"
    if w_status in ("UNAVAILABLE", "TIMEOUT", "INVALID"):
        confidence_penalty += 0.15
        applied_constraints.append(
            f"Rule E (Data Freshness Guard): Meteorological forecast is {w_status}. "
            f"Confidence downgraded due to unverified weather telemetry."
        )

    # -------------------------------------------------------------------------
    # Rule F — Conflicting evidence
    # If critical agents disagree:
    # Lower stability, surface conflict, provide safe constrained action.
    # -------------------------------------------------------------------------
    conflicts = getattr(state, "conflicts", [])
    if conflicts:
        applied_constraints.append(
            f"Rule F (Conflict Resolution Guard): {len(conflicts)} active conflict(s) detected. "
            f"Recommendation constrained to safe agronomic action."
        )

    return action, reason, applied_constraints, confidence_penalty


def derive_decision_change_triggers(
    state: Any,
    action: str,
    applied_constraints: list[str],
) -> list[str]:
    """Deterministically list conditions that would alter the current decision.

    Only lists conditions that actually influence the current decision.
    """
    triggers: list[str] = []

    s = getattr(state, "soil", None)
    w = getattr(state, "weather", None)
    d = getattr(state, "disease", None)
    m = getattr(state, "market", None)

    # Trigger: Soil NPK
    if not (s and getattr(s, "npk_available", False)):
        triggers.append("Reliable NPK values become available (enables precise nutrient deficiency calculation and dosage)")

    # Trigger: Weather
    w_risk = getattr(w, "rainfall_risk", 0.0) if w else 0.0
    if w_risk >= 0.30 or action == "delay":
        triggers.append("Rainfall risk decreases below 0.30 (clears weather safety block for field applications)")
    elif w and getattr(w, "status", "AVAILABLE") != "AVAILABLE":
        triggers.append("Hyper-local live meteorological telemetry becomes available")

    # Trigger: Growth stage
    if getattr(state.crop, "growth_stage", ""):
        triggers.append("Crop enters next growth stage (alters physiological nutrient and irrigation demand)")

    # Trigger: Disease
    if d:
        if getattr(d, "crop_mismatch", False):
            triggers.append("Leaf image from matching crop is provided")
        elif getattr(d, "predicted_class", None) and getattr(d, "confidence", 0.0) < 0.60:
            triggers.append("High-confidence leaf image (>0.60) confirms active pathogen infection")
        elif not getattr(d, "predicted_class", None):
            triggers.append("High-confidence disease evidence becomes available via leaf photo")

    # Trigger: Market
    if m and getattr(m, "is_available", False):
        if getattr(m, "signal", "") == "hold" and getattr(m, "market_score", 0.0) > 0.50:
            triggers.append("Market arrivals and spot prices reach peak harvest threshold")

    return triggers
