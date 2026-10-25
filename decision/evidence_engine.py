"""Adaptive Evidence & Conflict Resolution Engine for AgriMind.

Novelty Module:
1. Collects structured agent evidence from all specialist agents.
2. Normalizes confidence, assesses source reliability, and evaluates temporal relevance.
3. Detects explicit conflicts (Weather vs Soil, Disease vs Crop, Market vs Safety, Missing NPK).
4. Resolves conflicts using authoritative agronomic safety hierarchies.
5. Computes the deterministic Decision Stability Score (DSS) using a transparent weighted formula.
6. Enforces uncertainty awareness (prevents overconfident recommendations when data is missing).
7. Derives deterministic re-evaluation triggers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from decision.models import ConflictSpec, Decision, ActionStr
from decision.scoring import ACTIONS, weighted_score
from decision.evidence_quality import calculate_evidence_quality
from decision.safety_guard import apply_agronomic_safety_guard, derive_decision_change_triggers

# ==============================================================================
# CONFIGURABLE DETERMINISTIC CONSTANTS & WEIGHTS (Section 16)
# ==============================================================================
WEIGHT_AGENT_CONFIDENCE = 0.25
WEIGHT_SOURCE_RELIABILITY = 0.20
WEIGHT_TEMPORAL_RELEVANCE = 0.15
WEIGHT_EVIDENCE_COMPLETENESS = 0.25
WEIGHT_AGENT_AGREEMENT = 0.15

CONFLICT_PENALTY_RATE = 0.12  # Penalty per significant conflict

STABILITY_THRESHOLD_HIGH = 0.80
STABILITY_THRESHOLD_MODERATE = 0.60
STABILITY_THRESHOLD_LOW = 0.40

# Source reliability ratings [0.0 - 1.0]
SOURCE_RELIABILITY_SCORES: dict[str, float] = {
    "open_meteo": 0.90,
    "caller_coordinates": 0.95,
    "open_meteo_geocoding": 0.85,
    "local_agri_registry": 0.90,
    "measured_soil_test": 0.95,
    "project_calibration_heuristic": 0.70,
    "engineering_fallback_default": 0.50,
    "regional_agroclimatic_heuristic": 0.65,
    "agmarknet_api": 0.90,
    "agmarknet_cache": 0.75,
    "caller_provided": 0.70,
    "user_supplied": 0.65,
    "plantvillage_mobilenet": 0.85,
    "disease_override": 0.80,
    "none": 0.10,
    "unspecified": 0.30,
}


def get_stability_level(score: float) -> str:
    """Classify Decision Stability Score into discrete tiers."""
    if score >= STABILITY_THRESHOLD_HIGH:
        return "HIGH"
    if score >= STABILITY_THRESHOLD_MODERATE:
        return "MODERATE"
    if score >= STABILITY_THRESHOLD_LOW:
        return "LOW"
    return "INSUFFICIENT"


# ==============================================================================
# 1. STRUCTURED AGENT EVIDENCE EXTRACTION (Section 13)
# ==============================================================================

def extract_weather_evidence(state: Any) -> dict[str, Any]:
    w = state.weather
    is_avail = getattr(w, "is_available", True) and getattr(w, "status", "AVAILABLE") == "AVAILABLE"
    risk = getattr(w, "rainfall_risk", 0.0)
    conf = getattr(w, "confidence", 0.0) if is_avail else 0.0
    status = getattr(w, "status", "AVAILABLE" if is_avail else "UNAVAILABLE")
    source = "open_meteo" if is_avail else "none"

    from agents.weather_agent import get_weather_risk_level
    risk_level = getattr(w, "risk_level", None) or get_weather_risk_level(risk)
    risk_exp = getattr(w, "risk_explanation", "")
    finding = (
        f"Rainfall risk: {risk:.2f} ({risk_level}) - condition: {getattr(w, 'fertilizer_condition', 'normal')}. {risk_exp}".strip()
        if is_avail else f"Weather data {status} ({getattr(w, 'reason', 'offline')})"
    )
    limitations = []
    if not is_avail:
        limitations.append("External weather forecast unavailable; assuming conservative neutral risk.")
    elif risk_level in ("HIGH", "SEVERE") or risk >= 0.60:
        limitations.append("Imminent precipitation prevents safe agrochemical applications.")

    return {
        "agent": "weather",
        "finding": finding,
        "confidence": round(conf, 4),
        "source": source,
        "source_type": "meteorological_api" if is_avail else "offline_fallback",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "evidence": [
            {
                "rainfall_risk": risk,
                "risk_level": risk_level,
                "risk_explanation": risk_exp,
                "irrigation_condition": getattr(w, "irrigation_condition", "normal"),
            },
        ],
        "limitations": limitations,
    }


def extract_soil_evidence(state: Any) -> dict[str, Any]:
    s = state.soil
    npk_avail = getattr(s, "npk_available", True)
    conf = getattr(s, "confidence", 0.0) if npk_avail else 0.0
    status = getattr(s, "status", "AVAILABLE" if npk_avail else "UNAVAILABLE")
    prov = getattr(s, "provenance", {}) or {}
    mode = prov.get("mode", "MEASURED" if npk_avail else "UNAVAILABLE")

    source = "measured_soil_test" if mode == "MEASURED" and npk_avail else (
        "regional_agroclimatic_heuristic" if mode == "LOCATION_ESTIMATED" else (
            "project_calibration_heuristic" if getattr(s, "soil_type", "") else "none"
        )
    )

    limitations = []
    if not npk_avail:
        finding = (
            "Soil nutrient assessment: Unavailable. NPK measurements were not provided, "
            "so nutrient deficiency was not calculated."
        )
        limitations.append("Missing measured NPK data; cannot diagnose specific nutrient deficiency.")
        evidence_records = [
            {
                "overall_deficiency": None,
                "nutrient_status": "UNAVAILABLE",
                "npk_available": False,
                "soil_type": getattr(s, "soil_type", ""),
            },
        ]
    else:
        defic = getattr(s, "overall_deficiency", 0.0)
        p_nut = getattr(s, "priority_nutrient", "balanced")
        finding = f"Overall nutrient deficiency {defic:.2f} (priority: {p_nut})"
        limitations.append("Field doses must be adjusted with local soil test card and SAU recommendations.")
        evidence_records = [
            {
                "overall_deficiency": defic,
                "nutrient_status": "MEASURED",
                "npk_available": True,
                "soil_type": getattr(s, "soil_type", ""),
            },
        ]

    return {
        "agent": "soil",
        "finding": finding,
        "confidence": round(conf, 4),
        "source": source,
        "source_type": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "evidence": evidence_records,
        "limitations": limitations,
    }


def extract_disease_evidence(state: Any) -> dict[str, Any]:
    d = state.disease
    cls_name = getattr(d, "predicted_class", None)
    conf = getattr(d, "confidence", 0.0)
    actionable = getattr(d, "actionable", False)
    mismatch = getattr(d, "crop_mismatch", False)
    severity = getattr(d, "severity", "low")

    source = "disease_override" if getattr(d, "status", "") == "OVERRIDE" else (
        "plantvillage_mobilenet" if cls_name else "none"
    )

    limitations = []
    if mismatch:
        limitations.append("Crop mismatch detected between selected crop and model prediction; evidence non-actionable.")
    elif not cls_name:
        limitations.append("No leaf image provided; disease evaluation inactive.")
    elif not actionable:
        limitations.append("Model confidence below safety threshold (0.60); treated as non-actionable.")

    finding = f"Detected: {cls_name} ({conf:.2f}, severity: {severity})" if cls_name else "No disease detected / no leaf image"

    return {
        "agent": "disease",
        "finding": finding,
        "confidence": round(conf, 4),
        "source": source,
        "source_type": "vision_classifier" if cls_name else "none",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": getattr(d, "status", "AVAILABLE"),
        "evidence": [
            {
                "predicted_class": cls_name,
                "actionable": actionable,
                "crop_mismatch": mismatch,
                "severity": severity,
            },
        ],
        "limitations": limitations,
    }


def extract_market_evidence(state: Any) -> dict[str, Any]:
    m = state.market
    is_avail = getattr(m, "is_available", True) and getattr(m, "status", "AVAILABLE") != "UNAVAILABLE"
    conf = getattr(m, "confidence", 0.0) if is_avail else 0.0
    status = getattr(m, "status", "AVAILABLE" if is_avail else "UNAVAILABLE")
    source = getattr(m, "source", "agmarknet_api" if is_avail else "none")

    finding = f"Market signal: {getattr(m, 'signal', 'hold')} (score: {getattr(m, 'market_score', 0.0):.2f})" if is_avail else "Market price data unavailable; using safe hold fallback"
    limitations = ["Market conditions advisory only; cannot override agronomic safety."]
    if status in ("DEMO_DATA", "USER_SUPPLIED") or source == "caller_provided":
        limitations.append("Caller-provided benchmark price used; not verified real-time APMC mandi telemetry.")
    elif status == "CACHED" or source == "agmarknet_cache":
        limitations.append("Cached APMC mandi telemetry used; observe market observation latency.")

    return {
        "agent": "market",
        "finding": finding,
        "confidence": round(conf, 4),
        "source": source,
        "source_type": "market_feed" if is_avail else "none",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "evidence": [
            {
                "signal": getattr(m, "signal", "hold"),
                "score": getattr(m, "market_score", 0.0),
                "is_available": is_avail,
            },
        ],
        "limitations": limitations,
    }


def collect_agent_evidence(state: Any) -> list[dict[str, Any]]:
    """Extract structured evidence from all agents."""
    return [
        extract_weather_evidence(state),
        extract_soil_evidence(state),
        extract_disease_evidence(state),
        extract_market_evidence(state),
    ]


# ==============================================================================
# 2. CONFLICT DETECTION & RESOLUTION (Sections 14, 15)
# ==============================================================================

def detect_and_resolve_conflicts(state: Any, evidence_list: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None, str, int | None, str]:
    """Detect agronomic, disease, weather, and market conflicts and resolve them authoritatively.

    Returns:
    (conflicts_list, terminal_action, terminal_reason, priority, re_evaluation_trigger)
    """
    conflicts: list[dict[str, Any]] = []
    terminal_action: str | None = None
    terminal_reason: str = ""
    terminal_priority: int | None = None
    re_evaluation_trigger: str = "Re-evaluate during regular crop growth monitoring."

    w = state.weather
    s = state.soil
    d = state.disease
    m = state.market

    w_avail = getattr(w, "is_available", True) and getattr(w, "status", "AVAILABLE") == "AVAILABLE"
    s_npk = getattr(s, "npk_available", True)
    d_mismatch = getattr(d, "crop_mismatch", False)

    # P2: confidence gate, not a terminal decision
    # Requires both an actual detected disease signal and confidence >= 0.60 without crop mismatch
    is_actionable = bool(getattr(d, "predicted_class", None)) and (getattr(d, "confidence", 0.0) >= 0.60) and not d_mismatch
    d.actionable = is_actionable

    # Check for acute critical disease (e.g. late blight epidemic) requiring immediate field quarantine
    d_class_str = str(getattr(d, "predicted_class", "") or "").lower()
    has_severe_disease = getattr(d, "actionable", False) and ("late_blight" in d_class_str or getattr(d, "severity", "low") == "critical")

    # 1. Weather vs Fertilizer (Rainfall Risk Veto — Priority 1)
    if w.rainfall_risk > 0.70:
        c1 = {
            "agent_a": "weather",
            "agent_b": "soil",
            "conflict_type": "weather_vs_fertilizer",
            "issue": "rainfall_risk",
            "evidence": f"Rainfall risk {w.rainfall_risk:.2f} makes immediate chemical or fertilizer application unsafe.",
            "resolution": "Weather safety veto takes precedence; DELAY all applications.",
            "priority": 1,
            "score_impact": -0.20,
        }
        c2 = {
            "agent_a": "weather",
            "agent_b": "advisory",
            "conflict_type": "weather_vs_advisory",
            "issue": "rainfall_risk",
            "evidence": "Rainfall risk overrides preliminary advisory scores.",
            "resolution": "DELAY takes precedence.",
            "priority": 1,
            "score_impact": -0.20,
        }
        c3 = {
            "agent_a": "weather",
            "agent_b": "market",
            "conflict_type": "weather_vs_market",
            "issue": "rainfall_risk",
            "evidence": "Rainfall risk overrides market activity.",
            "resolution": "DELAY takes precedence.",
            "priority": 1,
            "score_impact": -0.20,
        }
        conflicts.extend([c1, c2, c3])

        if not has_severe_disease:
            terminal_action = ActionStr("DELAY")
            terminal_reason = "rainfall_risk"
            terminal_priority = 1
            re_evaluation_trigger = "Re-evaluate after heavy rainfall passes."
            return conflicts, terminal_action, terminal_reason, terminal_priority, re_evaluation_trigger
        else:
            # When severe disease is active, disease containment protocol takes priority,
            # while chemical spray is deferred via the treatment permission state machine
            conflicts.append({
                "agent_a": "weather",
                "agent_b": "disease",
                "conflict_type": "weather_vs_disease",
                "issue": "rainfall_risk",
                "evidence": f"Rainfall risk {w.rainfall_risk:.2f} requires delaying chemical spray; cultural sanitation prioritized.",
                "resolution": "DISEASE_MANAGEMENT_FIRST focuses on non-chemical containment; chemical spray held for rain-free window.",
                "priority": 1,
                "score_impact": -0.15,
            })

    # 2. Crop Mismatch in Disease Model
    if d_mismatch:
        dis_label = (getattr(d, 'predicted_class', '') or getattr(d, 'crop_detected', '')).replace('___', ' ')
        conflicts.append({
            "agent_a": "disease",
            "agent_b": "crop_selector",
            "conflict_type": "disease_crop_mismatch",
            "issue": "crop_mismatch",
            "evidence": f"Selected crop: {state.crop.crop}, Detected crop/disease: {dis_label}, Confidence: {getattr(d, 'confidence', 0.0):.2f}.",
            "resolution": "Disease action blocked due to crop mismatch; standard crop advisory continues.",
            "priority": 2,
            "score_impact": -0.15,
        })
        d.actionable = False

    # 3. Disease Urgency (Priority 3)
    if getattr(d, "actionable", False) and getattr(d, "severity", "low") == "high":
        conflicts.append({
            "agent_a": "disease",
            "agent_b": "advisory",
            "conflict_type": "disease_urgency",
            "issue": "disease_urgency",
            "evidence": f"Severe actionable infection '{d.predicted_class}' requires immediate phytosanitary treatment.",
            "resolution": "DISEASE_MANAGEMENT_FIRST prioritizes crop protection over standard field tasks.",
            "priority": 3,
            "score_impact": 0.0,
        })
        terminal_action = "DISEASE_MANAGEMENT_FIRST"
        terminal_reason = "disease_urgency"
        terminal_priority = 3
        re_evaluation_trigger = "Re-evaluate 3-5 days after disease treatment spray."
        return conflicts, terminal_action, terminal_reason, terminal_priority, re_evaluation_trigger

    # 4. Severe Soil Deficiency (Priority 4)
    if s_npk and getattr(s, "overall_deficiency", None) is not None and s.overall_deficiency > 0.60:
        conflicts.append({
            "agent_a": "soil",
            "agent_b": "advisory",
            "conflict_type": "soil_deficiency_priority",
            "issue": "soil_deficiency",
            "evidence": f"Measured nutrient deficiency {s.overall_deficiency:.2f} exceeds application threshold.",
            "resolution": "apply_fertilizer prioritized for crop sustenance.",
            "priority": 4,
            "score_impact": 0.0,
        })
        terminal_action = "apply_fertilizer"
        terminal_reason = "soil_deficiency"
        terminal_priority = 4
        re_evaluation_trigger = "Re-evaluate 14 days after fertilizer top-dressing."

    # 5. Missing NPK vs Fertilizer Recommendation Conflict
    if not s_npk:
        conflicts.append({
            "agent_a": "soil",
            "agent_b": "advisory",
            "conflict_type": "missing_npk_uncertainty",
            "issue": "unmeasured_soil_nutrition",
            "evidence": "No measured NPK values provided. Blind fertilizer dosage would risk agronomic error.",
            "resolution": "Recommendation constrained to safe monitoring until Soil Health Card test is provided.",
            "priority": 5,
            "score_impact": -0.25,
        })
        re_evaluation_trigger = "Re-evaluate after reliable NPK values are supplied."

    # 6. Moderate Weather vs Soil Deficiency (conflict without full veto)
    if s_npk and getattr(s, "overall_deficiency", None) is not None and s.overall_deficiency > 0.40 and w.rainfall_risk > 0.50:
        conflicts.append({
            "agent_a": "weather",
            "agent_b": "soil",
            "conflict_type": "fertilizer_weather_conflict",
            "issue": "moderate_rain_vs_deficiency",
            "evidence": f"Soil deficiency {s.overall_deficiency:.2f} indicates fertilizer need, but rain risk {w.rainfall_risk:.2f} threatens leaching.",
            "resolution": "Delay immediate application or monitor local sky conditions.",
            "priority": 5,
            "score_impact": -0.10,
        })
        re_evaluation_trigger = "Re-evaluate after rainfall risk subsides below 0.30."

    # 7. Market vs Agronomic Safety & Crop Care
    if getattr(m, "is_available", False) and getattr(m, "signal", "").lower() == "sell":
        if w.rainfall_risk > 0.50:
            conflicts.append({
                "agent_a": "market",
                "agent_b": "weather",
                "conflict_type": "market_vs_weather_safety",
                "issue": "favorable_price_vs_adverse_weather",
                "evidence": "Favorable selling price detected, but impending rainfall may disrupt harvest/transport.",
                "resolution": "Agronomic weather safety takes precedence over selling signal.",
                "priority": 5,
                "score_impact": -0.05,
                "agronomic_recommendation": "delay",
                "market_recommendation": "sell",
                "final_advisory": "Prioritize weather safety delay over selling signal.",
            })
        else:
            c_stage = getattr(getattr(state, "crop", None), "growth_stage", "").lower()
            if any(st in c_stage for st in ("veg", "flower", "fruit", "seedling", "tillering", "heading", "grain")):
                conflicts.append({
                    "agent_a": "market",
                    "agent_b": "crop_care",
                    "conflict_type": "market_vs_agronomic_management",
                    "issue": "market_sell_vs_field_crop_care",
                    "evidence": f"Market indicates favorable selling window ({getattr(m, 'source', 'caller_provided')}), but crop is currently in {c_stage} growth stage.",
                    "resolution": "Agronomic field management remains authoritative; market signal reserved for harvest phase.",
                    "priority": 5,
                    "score_impact": 0.0,
                    "agronomic_recommendation": "apply_fertilizer" if (s_npk and getattr(s, "overall_deficiency", None) and s.overall_deficiency > 0.30) else "monitor",
                    "market_recommendation": "sell",
                    "final_advisory": f"Maintain agronomic crop care for {c_stage} stage; track favorable market price trend toward harvest.",
                })

    for c in conflicts:
        if "agents" not in c and "agent_a" in c and "agent_b" in c:
            c["agents"] = f"{c['agent_a']} vs {c['agent_b']}"

    return conflicts, terminal_action, terminal_reason, terminal_priority, re_evaluation_trigger


# ==============================================================================
# 3. DECISION STABILITY SCORE FORMULA (Section 16)
# ==============================================================================

def calculate_decision_stability_score(
    evidence_list: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    state: Any,
) -> float:
    """Deterministic, transparent calculation of Decision Stability Score (0.0 to 1.0).

    Components:
    - Agent confidence: average confidence of active domain agents
    - Source reliability: mean reliability rating of evidence sources
    - Temporal relevance: based on real-time vs fallback sources
    - Evidence completeness: proportion of core agricultural domains available
    - Conflict penalty: deductions for active unresolved conflicts
    """
    confs = []
    reliabilities = []
    relevances = []

    for e in evidence_list:
        agent = e["agent"]
        if agent in ("weather", "soil"):
            confs.append(e["confidence"])
            reliabilities.append(SOURCE_RELIABILITY_SCORES.get(e["source"], 0.50))
            relevances.append(1.0 if e["source"] in ("open_meteo", "measured_soil_test", "caller_coordinates") else 0.70)
        elif agent == "disease":
            if getattr(state.disease, "predicted_class", None) or getattr(state.disease, "status", "") in ("AVAILABLE", "OVERRIDE"):
                confs.append(e["confidence"])
                reliabilities.append(SOURCE_RELIABILITY_SCORES.get(e["source"], 0.85))
                relevances.append(0.85)
        elif agent == "market":
            if getattr(state.market, "is_available", False) or getattr(state.market, "status", "") in ("REAL_DATA", "DEMO_DATA"):
                confs.append(e["confidence"])
                reliabilities.append(SOURCE_RELIABILITY_SCORES.get(e["source"], 0.75))
                relevances.append(1.0 if e["source"] == "agmarknet_api" else 0.85)

    if not confs:
        confs = [0.0]
        reliabilities = [0.20]
        relevances = [0.20]

    avg_confidence = sum(confs) / len(confs)
    avg_reliability = sum(reliabilities) / len(reliabilities)
    avg_relevance = sum(relevances) / len(relevances)

    completeness = 0.0
    if getattr(state.crop, "crop", ""):
        completeness += 0.25
    if getattr(state.weather, "is_available", False) and getattr(state.weather, "status", "") == "AVAILABLE":
        completeness += 0.35
    if getattr(state.soil, "npk_available", False):
        completeness += 0.40
    elif getattr(state.soil, "soil_type", ""):
        completeness += 0.15

    agreement = 1.0 if not conflicts else max(0.0, 1.0 - (len(conflicts) * 0.25))

    base_score = (
        WEIGHT_AGENT_CONFIDENCE * avg_confidence
        + WEIGHT_SOURCE_RELIABILITY * avg_reliability
        + WEIGHT_TEMPORAL_RELEVANCE * avg_relevance
        + WEIGHT_EVIDENCE_COMPLETENESS * completeness
        + WEIGHT_AGENT_AGREEMENT * agreement
    )

    conflict_penalty = min(len(conflicts) * CONFLICT_PENALTY_RATE, 0.40)
    dss = max(0.0, min(1.0, round(base_score - conflict_penalty, 4)))

    if hasattr(state, "decision_stability_breakdown"):
        state.decision_stability_breakdown = {
            "formula": "DSS = (0.25 * avg_confidence) + (0.20 * avg_source_reliability) + (0.15 * avg_temporal_relevance) + (0.25 * completeness) + (0.15 * agreement) - conflict_penalty",
            "agent_confidence": round(avg_confidence, 4),
            "source_reliability": round(avg_reliability, 4),
            "temporal_relevance": round(avg_relevance, 4),
            "evidence_completeness": round(completeness, 4),
            "agent_agreement": round(agreement, 4),
            "conflict_penalty": round(conflict_penalty, 4),
            "active_conflicts_count": len(conflicts),
            "base_score": round(base_score, 4),
            "final_dss": dss,
        }

    return dss


# ==============================================================================
# 4. UNCERTAINTY-AWARE DECISION & PROVENANCE (Sections 15, 17, 18, 19)
# ==============================================================================

def evaluate_decision(state: Any) -> Decision:
    """Main entrypoint for the Adaptive Evidence & Conflict Resolution Engine.

    Produces authoritative decision, DSS, conflict audit, and decision provenance.
    """
    # 1. Collect structured evidence from agents
    evidence_list = collect_agent_evidence(state)
    state.evidence_items = evidence_list

    # 2. Detect and resolve conflicts
    conflicts, terminal_action, terminal_reason, terminal_priority, re_eval_trigger = (
        detect_and_resolve_conflicts(state, evidence_list)
    )

    # 3. Calculate Decision Stability Score
    dss = calculate_decision_stability_score(evidence_list, conflicts, state)
    stability_level = get_stability_level(dss)

    state.decision_stability_score = dss
    state.stability_level = stability_level
    state.re_evaluation_trigger = re_eval_trigger
    state.conflicts = list(conflicts)

    # 4. Build Decision object
    if terminal_action is not None:
        # Terminal Stage 1 rule applied
        decision = Decision(
            action=terminal_action,
            reason=terminal_reason,
            priority=terminal_priority,
            stage="stage_1",
            overrides=[
                ConflictSpec(c["agent_a"], c["agent_b"], c["issue"], conflict_type=c.get("conflict_type", c["issue"]))
                for c in conflicts
            ],
            is_override=True,
        )
    else:
        # Stage 2 weighted scoring
        scores = dict(state.advisory.scores) if state.advisory.scores else {
            action: weighted_score(state, action) for action in ACTIONS
        }

        # If NPK is unmeasured, cannot recommend apply_fertilizer
        if not getattr(state.soil, "npk_available", True):
            scores["apply_fertilizer"] = min(scores.get("apply_fertilizer", 0.5), 0.35)

        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        best_action = ranked[0][0]
        reason = "weighted_score"
        priority = None
        stage = "stage_2"

        # Market tiebreaker
        if len(ranked) > 1 and abs(ranked[0][1] - ranked[1][1]) < 0.05:
            tied = {ranked[0][0], ranked[1][0]}
            if state.market.market_score > 0.60 and "delay" in tied:
                best_action = "delay"
                reason = "market_tiebreaker"
                overrides_list = [ConflictSpec("market", "advisory", "market_tiebreaker", conflict_type="market_tiebreaker")]
            else:
                overrides_list = [
                    ConflictSpec(c["agent_a"], c["agent_b"], c["issue"], conflict_type=c.get("conflict_type", c["issue"]))
                    for c in conflicts
                ]
        else:
            overrides_list = [
                ConflictSpec(c["agent_a"], c["agent_b"], c["issue"], conflict_type=c.get("conflict_type", c["issue"]))
                for c in conflicts
            ]

        # Uncertainty gate: When NPK is unmeasured/unavailable, system must NOT recommend apply_fertilizer
        if not getattr(state.soil, "npk_available", True) and best_action == "apply_fertilizer":
            best_action = "monitor"
            reason = "insufficient_evidence_precaution"

        decision = Decision(
            action=best_action,
            reason=reason,
            scores=scores,
            stage=stage,
            priority=priority,
            overrides=overrides_list,
            is_override=False,
        )



    # 5. Apply Deterministic Agronomic Safety Guard
    safe_action, safe_reason, applied_constraints, conf_penalty = apply_agronomic_safety_guard(
        state,
        candidate_action=decision.action,
        candidate_reason=decision.reason,
    )
    decision.action = safe_action
    decision.reason = safe_reason
    state.safety_constraints = applied_constraints
    if conf_penalty > 0:
        dss = max(0.0, round(dss - conf_penalty, 4))
        state.decision_stability_score = dss
        state.stability_level = get_stability_level(dss)

    # 6. Calculate Evidence Quality Score & Breakdown
    rag_ev = None
    try:
        from rag.retriever import KnowledgeRetriever
        c_name = getattr(state.crop, "crop", "") or ""
        s_name = getattr(state.crop, "growth_stage", "") or ""
        if c_name:
            q = f"{c_name} {s_name} {decision.action} agronomy".strip()
            rag_ev = KnowledgeRetriever().search(
                q,
                n_results=4,
                crop=c_name,
                growth_stage=s_name,
                location=getattr(state, "raw_inputs", {}).get("location_name"),
            )
    except Exception:
        rag_ev = None

    eqs, eqs_level, eqs_breakdown = calculate_evidence_quality(state, evidence_list, rag_evidence=rag_ev)
    state.evidence_quality_score = eqs
    state.evidence_quality_level = eqs_level
    state.evidence_quality_breakdown = eqs_breakdown.to_dict()

    # 7. Derive Decision Sensitivity triggers ("What would change this decision?")
    decision_triggers = derive_decision_change_triggers(state, safe_action, applied_constraints)
    state.decision_change_triggers = decision_triggers

    # 8. Populate required additional info if uncertainty exists
    req_info = []
    if not getattr(state.soil, "npk_available", True):
        req_info.append("Soil Health Card / measured NPK values")
    if not (getattr(state.weather, "is_available", True) and getattr(state.weather, "status", "") == "AVAILABLE"):
        req_info.append("Live hyper-local weather forecast")
    if getattr(state.disease, "crop_mismatch", False):
        req_info.append("Clear leaf image matching the selected crop")
    state.required_additional_info = req_info

    # 9. Build Decision Provenance
    supporting = []
    conflicting = []
    for e in evidence_list:
        if e["confidence"] > 0:
            supporting.append({
                "agent": e["agent"],
                "finding": e["finding"],
                "confidence": e["confidence"],
                "source": e["source"],
            })
    for c in conflicts:
        row = {
            "agents": f"{c['agent_a']} vs {c['agent_b']}",
            "issue": c["issue"],
            "resolution": c["resolution"],
        }
        if "agronomic_recommendation" in c:
            row["agronomic_recommendation"] = c["agronomic_recommendation"]
        if "market_recommendation" in c:
            row["market_recommendation"] = c["market_recommendation"]
        if "final_advisory" in c:
            row["final_advisory"] = c["final_advisory"]
        conflicting.append(row)

    state.supporting_evidence = supporting
    state.conflicting_evidence = conflicting
    state.resolved_conflicts = conflicts

    state.agronomic_recommendation = decision.action
    state.market_recommendation = getattr(state.market, "signal", "hold")
    if getattr(state.market, "signal", "").lower() == "sell":
        state.farm_advisory = f"Agronomic: {decision.action.replace('_', ' ').capitalize()} | Market: Monitor favorable spot prices for harvest window."
    else:
        state.farm_advisory = f"Agronomic: {decision.action.replace('_', ' ').capitalize()} | Market: {getattr(state.market, 'signal', 'hold').capitalize()}."

    state.decision_provenance = {
        "final_recommendation": decision.action,
        "agronomic_recommendation": state.agronomic_recommendation,
        "market_recommendation": state.market_recommendation,
        "farm_advisory": state.farm_advisory,
        "final_combined_farm_advisory": state.farm_advisory,
        "reason": decision.reason,
        "decision_stability_score": dss,
        "stability_level": state.stability_level,
        "evidence_quality_score": eqs,
        "evidence_quality_level": eqs_level,
        "evidence_quality_breakdown": eqs_breakdown.to_dict(),
        "confidence": state.confidence or dss,
        "supporting_evidence": supporting,
        "conflicting_evidence": conflicting,
        "resolved_conflicts": conflicts,
        "safety_constraints": applied_constraints,
        "re_evaluation_trigger": re_eval_trigger,
        "required_additional_info": req_info,
        "decision_change_triggers": decision_triggers,
    }

    return decision
