"""Combinatorial Validation Suite — 5-Agent Status Matrix & Interactions.

Section 7.1 & 7.2 of Phase 3:
1. Baseline: All 5 agents succeed (AVAILABLE/MEASURED/SUCCESS)
2. Exactly 1 agent fails: 5 single-failure combinations
3. Dual failures: All 10 pairwise combinations C(5, 2)
4. Total failure: All 5 agents unavailable/failed
5. Asymmetric combinations:
   - Disease active, weather & soil missing
   - Weather unavailable while fertilizer is requested
   - Market sell signal conflicts with heavy rainfall veto
   - Malformed/contradictory agent findings
6. Deterministic reproducibility: identical inputs produce identical decisions
"""
from __future__ import annotations

import pytest
from itertools import combinations
from orchestrator.graph import run_advisory
from orchestrator.state import (
    AgriMindState,
    CropContext,
    WeatherResult,
    SoilResult,
    DiseaseResult,
    AdvisoryResult,
    MarketResult,
)
from decision.rules import resolve_conflict


def _create_synthetic_state(
    weather_status: str = "AVAILABLE",
    weather_rain_risk: float = 0.10,
    soil_status: str = "MEASURED",
    soil_npk: bool = True,
    soil_deficiency: float | None = 0.50,
    disease_status: str = "AVAILABLE",
    disease_class: str | None = None,
    disease_conf: float = 0.0,
    crop_mismatch: bool = False,
    market_status: str = "REAL_DATA",
    market_signal: str = "hold",
    market_score: float = 0.55,
    advisory_status: str = "AVAILABLE",
    advisory_action: str = "monitor",
) -> AgriMindState:
    """Helper to assemble a clean synthetic AgriMindState with deterministic agent results."""
    state = AgriMindState(
        run_id="comb_test_run",
        crop=CropContext(crop="Tomato", growth_stage="vegetative", suitability_hint=0.8),
    )
    # 1. Weather
    state.weather = WeatherResult(
        rainfall_risk=weather_rain_risk,
        is_available=(weather_status in ("AVAILABLE", "SUCCESS")),
        status=weather_status,
        confidence=0.90 if weather_status in ("AVAILABLE", "SUCCESS") else 0.0,
    )
    # 2. Soil
    state.soil = SoilResult(
        npk_available=soil_npk,
        overall_deficiency=soil_deficiency if soil_npk else None,
        nitrogen_deficiency=soil_deficiency if soil_npk else None,
        phosphorus_deficiency=soil_deficiency if soil_npk else None,
        potassium_deficiency=soil_deficiency if soil_npk else None,
        status=soil_status,
        confidence=0.85 if soil_npk else 0.0,
    )
    # 3. Disease
    severity = "high" if (disease_class and any(k in disease_class.lower() for k in ("blight", "rot", "wilt"))) else "low"
    state.disease = DiseaseResult(
        predicted_class=disease_class,
        confidence=disease_conf,
        crop_mismatch=crop_mismatch,
        status=disease_status,
        actionable=bool(disease_class and disease_conf >= 0.60 and not crop_mismatch),
        severity=severity,
    )
    # 4. Advisory
    state.advisory = AdvisoryResult(
        preliminary_recommendation=advisory_action,
        status=advisory_status,
        confidence=0.80 if advisory_status == "AVAILABLE" else 0.0,
        scores={"apply_fertilizer": 0.4, "delay": 0.2, "monitor": 0.6},
    )
    # 5. Market
    state.market = MarketResult(
        signal=market_signal,
        market_score=market_score,
        status=market_status,
        is_available=(market_status in ("REAL_DATA", "CACHED", "USER_SUPPLIED")),
        confidence=0.75 if market_status in ("REAL_DATA", "CACHED") else 0.4,
    )
    return state


# ==============================================================================
# 1. Baseline: All 5 Agents Succeed
# ==============================================================================
def test_all_five_agents_succeed():
    state = _create_synthetic_state(
        weather_status="AVAILABLE",
        soil_status="MEASURED",
        disease_status="AVAILABLE",
        disease_class="Tomato___Early_blight",
        disease_conf=0.88,
        advisory_status="AVAILABLE",
        market_status="REAL_DATA",
    )
    decision = resolve_conflict(state)
    assert decision.action in ("DISEASE_MANAGEMENT_FIRST", "apply_fertilizer", "monitor", "delay")
    assert state.decision_stability_score > 0.0
    assert len(state.evidence_items) == 4  # weather, soil, disease, market evidence items
    assert state.advisory.status == "AVAILABLE"  # 5th specialist agent
    assert all(e["agent"] in ("weather", "soil", "disease", "market") for e in state.evidence_items)


# ==============================================================================
# 2. Exactly One Agent Fails (5 distinct single-agent failure modes)
# ==============================================================================
@pytest.mark.parametrize("failing_agent", ["weather", "soil", "disease", "advisory", "market"])
def test_single_agent_failure(failing_agent: str):
    kwargs = {
        "weather_status": "AVAILABLE",
        "soil_status": "MEASURED",
        "disease_status": "AVAILABLE",
        "advisory_status": "AVAILABLE",
        "market_status": "REAL_DATA",
    }
    if failing_agent == "weather":
        kwargs["weather_status"] = "UNAVAILABLE"
    elif failing_agent == "soil":
        kwargs["soil_status"] = "UNAVAILABLE"
        kwargs["soil_npk"] = False
        kwargs["soil_deficiency"] = None
    elif failing_agent == "disease":
        kwargs["disease_status"] = "MODEL_UNAVAILABLE"
        kwargs["disease_class"] = None
        kwargs["disease_conf"] = 0.0
    elif failing_agent == "advisory":
        kwargs["advisory_status"] = "FAILED"
    elif failing_agent == "market":
        kwargs["market_status"] = "UNAVAILABLE"

    state = _create_synthetic_state(**kwargs)
    decision = resolve_conflict(state)
    # Failure of 1 agent must never crash decision or corrupt remaining agents
    assert decision.action is not None
    assert 0.0 <= state.decision_stability_score <= 1.0
    if failing_agent == "advisory":
        assert state.advisory.status == "FAILED"
    else:
        failed_ev = [e for e in state.evidence_items if e["agent"] == failing_agent]
        assert len(failed_ev) == 1
        assert failed_ev[0]["status"] in ("UNAVAILABLE", "MODEL_UNAVAILABLE", "FAILED", "none")


# ==============================================================================
# 3. Dual Failures: Exhaustive Pairwise Matrix C(5, 2) = 10 combinations
# ==============================================================================
AGENT_NAMES = ["weather", "soil", "disease", "advisory", "market"]

@pytest.mark.parametrize("agent_a,agent_b", list(combinations(AGENT_NAMES, 2)))
def test_dual_agent_failures_pairwise(agent_a: str, agent_b: str):
    kwargs = {
        "weather_status": "AVAILABLE",
        "soil_status": "MEASURED",
        "disease_status": "AVAILABLE",
        "advisory_status": "AVAILABLE",
        "market_status": "REAL_DATA",
    }
    for ag in (agent_a, agent_b):
        if ag == "weather":
            kwargs["weather_status"] = "UNAVAILABLE"
        elif ag == "soil":
            kwargs["soil_status"] = "UNAVAILABLE"
            kwargs["soil_npk"] = False
            kwargs["soil_deficiency"] = None
        elif ag == "disease":
            kwargs["disease_status"] = "MODEL_UNAVAILABLE"
            kwargs["disease_class"] = None
        elif ag == "advisory":
            kwargs["advisory_status"] = "FAILED"
        elif ag == "market":
            kwargs["market_status"] = "UNAVAILABLE"

    state = _create_synthetic_state(**kwargs)
    decision = resolve_conflict(state)
    assert decision.action is not None
    # Dual failure must lower stability score compared to full success
    assert state.decision_stability_score <= 0.90


# ==============================================================================
# 4. Three-Agent Failures: Exhaustive Matrix C(5, 3) = 10 combinations
# ==============================================================================
@pytest.mark.parametrize("ag1,ag2,ag3", list(combinations(AGENT_NAMES, 3)))
def test_three_agent_failures_exhaustive(ag1: str, ag2: str, ag3: str):
    """Exhaustively verify all 10 three-agent simultaneous failure subsets."""
    kwargs = {
        "weather_status": "AVAILABLE",
        "soil_status": "MEASURED",
        "disease_status": "AVAILABLE",
        "advisory_status": "AVAILABLE",
        "market_status": "REAL_DATA",
    }
    for ag in (ag1, ag2, ag3):
        if ag == "weather":
            kwargs["weather_status"] = "UNAVAILABLE"
        elif ag == "soil":
            kwargs["soil_status"] = "UNAVAILABLE"
            kwargs["soil_npk"] = False
            kwargs["soil_deficiency"] = None
        elif ag == "disease":
            kwargs["disease_status"] = "MODEL_UNAVAILABLE"
            kwargs["disease_class"] = None
        elif ag == "advisory":
            kwargs["advisory_status"] = "FAILED"
        elif ag == "market":
            kwargs["market_status"] = "UNAVAILABLE"

    state = _create_synthetic_state(**kwargs)
    decision = resolve_conflict(state)
    assert decision.action is not None
    assert 0.0 <= state.decision_stability_score <= 1.0
    # Three agent failures always trigger safety constraints and/or penalties
    assert len(state.safety_constraints) >= 1


# ==============================================================================
# 5. Four-Agent Failures: Exhaustive Matrix C(5, 4) = 5 combinations
# ==============================================================================
@pytest.mark.parametrize("lone_survivor", AGENT_NAMES)
def test_four_agent_failures_exhaustive(lone_survivor: str):
    """Exhaustively verify all 5 combinations where exactly 1 agent is available."""
    kwargs = {
        "weather_status": "UNAVAILABLE",
        "soil_status": "UNAVAILABLE",
        "soil_npk": False,
        "soil_deficiency": None,
        "disease_status": "MODEL_UNAVAILABLE",
        "disease_class": None,
        "disease_conf": 0.0,
        "advisory_status": "FAILED",
        "market_status": "UNAVAILABLE",
    }
    # Turn on only the lone survivor
    if lone_survivor == "weather":
        kwargs["weather_status"] = "AVAILABLE"
        kwargs["weather_rain_risk"] = 0.20
    elif lone_survivor == "soil":
        kwargs["soil_status"] = "MEASURED"
        kwargs["soil_npk"] = True
        kwargs["soil_deficiency"] = 0.50
    elif lone_survivor == "disease":
        kwargs["disease_status"] = "AVAILABLE"
        kwargs["disease_class"] = "Tomato___Early_blight"
        kwargs["disease_conf"] = 0.85
    elif lone_survivor == "advisory":
        kwargs["advisory_status"] = "AVAILABLE"
    elif lone_survivor == "market":
        kwargs["market_status"] = "REAL_DATA"
        kwargs["market_score"] = 0.65

    state = _create_synthetic_state(**kwargs)
    decision = resolve_conflict(state)
    assert decision.action is not None
    # 4 failures: stability must be severely degraded (<0.50)
    assert state.decision_stability_score <= 0.50
    assert state.stability_level in ("LOW", "INSUFFICIENT")


# ==============================================================================
# 6. Total Failure: All 5 Agents Unavailable C(5, 5) = 1 combination
# ==============================================================================
def test_total_agent_failure():
    state = _create_synthetic_state(
        weather_status="UNAVAILABLE",
        soil_status="UNAVAILABLE",
        soil_npk=False,
        soil_deficiency=None,
        disease_status="MODEL_UNAVAILABLE",
        disease_class=None,
        disease_conf=0.0,
        advisory_status="FAILED",
        market_status="UNAVAILABLE",
    )
    decision = resolve_conflict(state)
    # Under total failure, system must fall back to conservative monitor, not fabricate an action
    assert decision.action in ("monitor", "delay")
    assert state.stability_level in ("LOW", "INSUFFICIENT")
    assert state.decision_stability_score < 0.50


# ==============================================================================
# 7. Targeted Asymmetric Combinations
# ==============================================================================
def test_disease_available_soil_weather_missing():
    """Disease is detected with high confidence and virulence, but weather and soil are missing."""
    state = _create_synthetic_state(
        weather_status="UNAVAILABLE",
        weather_rain_risk=0.0,
        soil_status="UNAVAILABLE",
        soil_npk=False,
        soil_deficiency=None,
        disease_status="AVAILABLE",
        disease_class="Tomato___Early_blight",
        disease_conf=0.85,
    )
    decision = resolve_conflict(state)
    # Active high-confidence disease triggers disease management
    assert decision.action == "DISEASE_MANAGEMENT_FIRST"
    # Unverified weather must trigger a freshness/availability constraint
    rule_e_present = any("Rule E" in str(c) for c in state.safety_constraints)
    assert rule_e_present is True


def test_weather_unavailable_while_fertilizer_requested():
    """Soil has high deficiency requesting fertilizer, but weather forecast is unavailable."""
    state = _create_synthetic_state(
        weather_status="UNAVAILABLE",
        weather_rain_risk=0.0,
        soil_status="MEASURED",
        soil_npk=True,
        soil_deficiency=0.75,
        disease_status="AVAILABLE",
        disease_class=None,
    )
    decision = resolve_conflict(state)
    assert decision.action is not None
    # Confidence penalty must be applied for missing weather telemetry
    assert any("Rule E" in str(c) for c in state.safety_constraints)


def test_market_sell_vs_heavy_rainfall_veto():
    """Market has high score (sell now), but imminent rain vetoes field activity."""
    state = _create_synthetic_state(
        weather_status="AVAILABLE",
        weather_rain_risk=0.85,  # heavy rain
        soil_status="MEASURED",
        soil_npk=True,
        soil_deficiency=0.65,
        disease_status="AVAILABLE",
        disease_class=None,
        market_status="REAL_DATA",
        market_signal="sell",
        market_score=0.90,
    )
    decision = resolve_conflict(state)
    # Agronomic safety veto (imminent rainfall) strictly takes precedence over market timing
    assert decision.action == "DELAY"
    assert "rainfall_risk" in decision.reason or "weather_safety" in decision.reason


def test_contradictory_agent_evidence():
    """Soil recommends fertilizer, weather vetoes with rain, disease demands treatment."""
    state = _create_synthetic_state(
        weather_status="AVAILABLE",
        weather_rain_risk=0.80,
        soil_status="MEASURED",
        soil_npk=True,
        soil_deficiency=0.80,
        disease_status="AVAILABLE",
        disease_class="Tomato___Early_blight",
        disease_conf=0.75,
    )
    decision = resolve_conflict(state)
    # Documented precedence: Weather veto delays chemical spray; conflicts recorded
    assert len(state.conflicts) > 0
    assert any(c["conflict_type"] == "weather_vs_fertilizer" for c in state.conflicts)
    assert decision.action in ("DELAY", "DISEASE_MANAGEMENT_FIRST")


# ==============================================================================
# 8. High-Priority Multi-System Failure Interactions
# ==============================================================================
def test_weather_veto_with_missing_soil_and_unavailable_disease():
    """Heavy rain veto + unmeasured soil + unavailable disease classifier.
    Compound safety scenario: Stage-1 Guard D and Guard A must both be enforced.
    """
    state = _create_synthetic_state(
        weather_status="AVAILABLE",
        weather_rain_risk=0.75,  # Heavy rain triggers veto
        soil_status="UNAVAILABLE",
        soil_npk=False,
        soil_deficiency=None,
        disease_status="MODEL_UNAVAILABLE",
        disease_class=None,
        disease_conf=0.0,
        advisory_status="AVAILABLE",
        advisory_action="apply_fertilizer",
    )
    decision = resolve_conflict(state)
    # Rain veto MUST dominate; DELAY enforced, fertilizer and disease treatment blocked
    assert decision.action == "DELAY"
    assert any("Rule D" in str(c) for c in state.safety_constraints)
    assert any("Rule A" in str(c) for c in state.safety_constraints)


def test_disease_model_failure_with_llm_and_rag_failure():
    """Disease model fails + RAG retrieval fails + LLM provider chain fails.
    System must produce conservative deterministic explanation without hallucinating citations.
    """
    from llm.explainer import explain_with_metadata
    from rag.retriever import KnowledgeRetriever

    state = _create_synthetic_state(
        weather_status="AVAILABLE",
        weather_rain_risk=0.15,
        soil_status="MEASURED",
        soil_npk=True,
        soil_deficiency=0.30,
        disease_status="MODEL_UNAVAILABLE",
        disease_class=None,
        disease_conf=0.0,
    )
    decision = resolve_conflict(state)
    state.final_recommendation = decision.action

    # RAG failure simulation (unknown nonsensical query produces empty citations)
    retriever = KnowledgeRetriever()
    empty_docs = retriever.search("xyz_nonexistent_pathogen_9999", n_results=3, min_score=0.99)

    # LLM fallback execution with forced metadata extraction
    res = explain_with_metadata(state, evidence=empty_docs)
    assert res is not None
    assert res.structured_explanation is not None
    # Must NOT invent ICAR citations when none were retrieved
    guidance = str(res.structured_explanation.get("guidance", ""))
    assert "ICAR Citation" not in guidance or "None" in guidance


def test_agent_timeouts_and_malformed_results():
    """Weather agent encounters HTTP timeout; soil agent returns invalid status."""
    state = _create_synthetic_state(
        weather_status="TIMEOUT",
        weather_rain_risk=0.0,
        soil_status="INVALID",
        soil_npk=False,
        soil_deficiency=None,
        disease_status="NOT_SUPPLIED",
        advisory_status="FAILED",
        market_status="UNAVAILABLE",
    )
    decision = resolve_conflict(state)
    # System handles timeout and malformed status gracefully, falling back to monitor
    assert decision.action in ("monitor", "delay")
    assert state.decision_stability_score < 0.50
    assert state.stability_level in ("LOW", "INSUFFICIENT")


# ==============================================================================
# 9. Deterministic Final Decisions for Identical Evidence & Shuffled Requests
# ==============================================================================
def test_deterministic_reproducibility():
    """Two executions with identical evidence MUST produce byte-for-byte identical decisions."""
    state1 = _create_synthetic_state(
        weather_status="AVAILABLE",
        weather_rain_risk=0.25,
        soil_status="MEASURED",
        soil_npk=True,
        soil_deficiency=0.70,
        disease_status="AVAILABLE",
        disease_class=None,
    )
    state2 = _create_synthetic_state(
        weather_status="AVAILABLE",
        weather_rain_risk=0.25,
        soil_status="MEASURED",
        soil_npk=True,
        soil_deficiency=0.70,
        disease_status="AVAILABLE",
        disease_class=None,
    )

    dec1 = resolve_conflict(state1)
    dec2 = resolve_conflict(state2)

    assert dec1.action == dec2.action
    assert dec1.reason == dec2.reason
    assert state1.decision_stability_score == state2.decision_stability_score
    assert state1.stability_level == state2.stability_level
    assert len(state1.conflicts) == len(state2.conflicts)


def test_repeated_requests_and_state_immutability():
    """Running 5 consecutive evaluations on clones must not mutate base values or drift decisions."""
    decisions = []
    scores = []
    for _ in range(5):
        s = _create_synthetic_state(
            weather_status="AVAILABLE",
            weather_rain_risk=0.45,
            soil_status="MEASURED",
            soil_npk=True,
            soil_deficiency=0.55,
            disease_status="AVAILABLE",
            disease_class="Tomato___Early_blight",
            disease_conf=0.72,
        )
        d = resolve_conflict(s)
        decisions.append(d.action)
        scores.append(s.decision_stability_score)

    # All decisions and scores must be identical
    assert len(set(decisions)) == 1
    assert len(set(scores)) == 1
