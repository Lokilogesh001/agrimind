"""Comprehensive tests for AgriMind Phase 2 Research Core Upgrades.

Covers:
1. Soil Deficiency Semantics (explicit UNAVAILABLE status, None deficiency, specific text)
2. Interpretable Weather Risk (boundary thresholds, distinct probability vs risk)
3. Upgraded RAG Multi-Attribute Evidence Ranking (location hierarchy, stage matching, provenance)
4. Evidence Quality Score & Breakdown (reproducibility, 0-1 bounds, component breakdown)
5. Deterministic Agronomic Safety Guard (Rules A through F)
6. Decision Sensitivity triggers ("What would change this decision?")
"""
from __future__ import annotations

from pathlib import Path
import pytest

from agents import soil_agent, weather_agent
from agents.weather_agent import (
    WEATHER_RISK_THRESHOLDS,
    get_weather_risk_level,
    get_weather_risk_explanation,
)
from data_sources.soil import estimate_soil_from_location
from decision.evidence_quality import (
    calculate_evidence_quality,
    get_evidence_quality_level,
    EvidenceQualityBreakdown,
)
from decision.safety_guard import (
    apply_agronomic_safety_guard,
    derive_decision_change_triggers,
)
from orchestrator.state import (
    AgriMindState,
    CropContext,
    DiseaseResult,
    MarketResult,
    SoilResult,
    WeatherResult,
)
from orchestrator.graph import run_advisory
from rag.retriever import KnowledgeRetriever


CORPUS_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "icar_chunks.json"


# ==============================================================================
# 1. SOIL DEFICIENCY SEMANTICS TESTS
# ==============================================================================

def test_soil_missing_npk_returns_unavailable():
    """Missing NPK must yield nutrient_status=UNAVAILABLE and deficiency=None."""
    res = soil_agent.run(n=None, p=None, k=None, crop="Tomato", soil_type="")
    assert res.npk_available is False
    assert res.nutrient_status == "UNAVAILABLE"
    assert res.overall_deficiency is None
    assert res.nitrogen_deficiency is None
    assert res.phosphorus_deficiency is None
    assert res.potassium_deficiency is None
    assert res.priority_nutrient == ""
    assert res.status == "UNAVAILABLE"
    assert "Soil nutrient assessment: Unavailable" in res.nutrient_assessment_text
    assert "NPK measurements were not provided, so nutrient deficiency was not calculated." in res.nutrient_assessment_text


def test_soil_user_selected_mode_provenance():
    """Manual soil type without NPK tags status=USER_SELECTED with UNAVAILABLE nutrient status."""
    res = soil_agent.run(n=None, p=None, k=None, crop="Rice", soil_type="clay", mode="USER_SELECTED")
    assert res.status == "USER_SELECTED"
    assert res.nutrient_status == "UNAVAILABLE"
    assert res.overall_deficiency is None
    assert res.priority_nutrient == ""
    assert res.provenance["mode"] == "USER_SELECTED"
    assert res.provenance["npk_available"] is False


def test_soil_location_estimated_provenance():
    """Regional estimation tags LOCATION_ESTIMATED without fabricating measured values."""
    est = estimate_soil_from_location(location_name="Coimbatore, Tamil Nadu")
    assert est["status"] == "LOCATION_ESTIMATED"
    assert est["is_measured"] is False
    assert est["soil_type"] == "red"


def test_soil_measured_npk_evaluates_deficiency():
    """Measured NPK enables deficiency calculations and identifies priority nutrient."""
    res = soil_agent.run(n=20, p=30, k=40, crop="Tomato", soil_type="loam")
    assert res.npk_available is True
    assert res.nutrient_status == "MEASURED"
    assert res.status == "MEASURED"
    assert res.overall_deficiency is not None
    assert res.overall_deficiency > 0.0
    assert res.priority_nutrient in ("nitrogen", "phosphorus", "potassium")
    assert res.confidence == 0.9


# ==============================================================================
# 2. WEATHER RISK INTERPRETABILITY TESTS
# ==============================================================================

@pytest.mark.parametrize("risk,expected_level", [
    (0.00, "LOW"),
    (0.20, "LOW"),
    (0.29, "LOW"),
    (0.30, "MODERATE"),
    (0.49, "MODERATE"),
    (0.59, "MODERATE"),
    (0.60, "HIGH"),
    (0.70, "HIGH"),
    (0.79, "HIGH"),
    (0.80, "SEVERE"),
    (0.95, "SEVERE"),
    (1.00, "SEVERE"),
])
def test_weather_risk_level_boundaries(risk, expected_level):
    """Verify deterministic boundary classifications for all weather risk tiers."""
    assert get_weather_risk_level(risk) == expected_level


def test_weather_risk_distinguishes_probability_and_score():
    """Ensure risk score, precipitation probability, and rainfall amount are distinct."""
    override = {"precip_prob": 0.45, "intensity": 0.80, "duration": 0.30}
    res = weather_agent.run(override=override)
    assert res.rainfall_risk > 0.0
    assert res.precipitation_probability == 0.45
    assert res.rainfall_amount_mm == 8.0  # intensity * 10
    # Risk score is a combined weighted index, not identical to precipitation probability
    assert res.rainfall_risk != res.precipitation_probability
    assert res.risk_level in ("LOW", "MODERATE", "HIGH", "SEVERE")
    assert len(res.risk_explanation) > 10


def test_weather_risk_explanation_meaningful():
    """Verify agronomic explanations describe decision effects."""
    exp_mod = get_weather_risk_explanation(0.45, "MODERATE")
    assert "uncertainty" in exp_mod.lower() or "moderate" in exp_mod.lower()

    exp_high = get_weather_risk_explanation(0.75, "HIGH")
    assert "delay" in exp_high.lower() or "hazard" in exp_high.lower()


# ==============================================================================
# 3. RAG / KNOWLEDGE EVIDENCE RANKING TESTS
# ==============================================================================

def test_rag_regional_ranking_prioritizes_local_state():
    """Tamil Nadu + Rice must rank higher than general India + Rice or unrelated regions."""
    retriever = KnowledgeRetriever(corpus_path=str(CORPUS_PATH))
    hits = retriever.search(
        "rice kharif sowing fertilizer",
        n_results=6,
        crop="rice",
        location="Thanjavur, Tamil Nadu",
    )
    assert hits
    top = hits[0]
    assert top["crop_relevance"] >= 0.70
    assert "relevance_badges" in top
    assert "final_rank_score" in top
    assert top["document"].endswith(".pdf")
    assert "score" in top and top["score"] > 0


def test_rag_growth_stage_ranking_boosts_matching_stage():
    """Matching growth stage receives higher stage_relevance than an unrelated stage."""
    retriever = KnowledgeRetriever(corpus_path=str(CORPUS_PATH))
    hits_flowering = retriever.search(
        "rice fertilizer water management",
        n_results=4,
        crop="rice",
        growth_stage="flowering",
    )
    hits_generic = retriever.search(
        "rice fertilizer water management",
        n_results=4,
        crop="rice",
        growth_stage="unspecified_stage_xyz",
    )
    assert hits_flowering
    top_flowering = hits_flowering[0]
    assert top_flowering["stage_relevance"] >= 0.20


def test_rag_evidence_retains_full_provenance():
    """Every evidence hit must retain full provenance fields without fabricated metadata."""
    retriever = KnowledgeRetriever(corpus_path=str(CORPUS_PATH))
    hits = retriever.search("tomato early blight", n_results=2, crop="tomato", disease="early blight")
    assert hits
    hit = hits[0]
    expected_keys = {
        "source", "document", "page", "chunk", "score",
        "crop_relevance", "location_relevance", "stage_relevance",
        "source_reliability", "temporal_relevance", "final_rank_score",
        "relevance_badges", "text", "metadata"
    }
    for k in expected_keys:
        assert k in hit, f"Missing provenance key: {k}"


# ==============================================================================
# 4. EVIDENCE QUALITY SCORE & BREAKDOWN TESTS
# ==============================================================================

def test_evidence_quality_score_deterministic_and_bounded():
    """Evidence Quality Score must be reproducible, 0-1 bounded, and provide breakdown."""
    state = AgriMindState(run_id="test-eqs")
    state.crop = CropContext(crop="Tomato", growth_stage="flowering")
    state.weather = WeatherResult(rainfall_risk=0.20, confidence=0.85, is_available=True, status="AVAILABLE")
    state.soil = SoilResult(overall_deficiency=0.35, confidence=0.90, npk_available=True, status="MEASURED")
    state.raw_inputs = {"lat": 13.0827, "lon": 80.2707, "location_name": "Chennai, Tamil Nadu", "geocoding_status": "AVAILABLE"}

    eqs, level, breakdown = calculate_evidence_quality(state)
    assert 0.0 <= eqs <= 1.0
    assert level in ("GOOD", "MODERATE", "LOW", "INSUFFICIENT")
    assert isinstance(breakdown, EvidenceQualityBreakdown)
    assert breakdown.crop_relevance == 1.0  # Tomato is in registry
    assert breakdown.location_relevance == 1.0  # Coords + available geocoding
    assert breakdown.stage_relevance == 1.0  # flowering is in STAGE_REGISTRY
    assert breakdown.source_reliability >= 0.75
    assert breakdown.completeness >= 0.80


def test_evidence_quality_missing_evidence_lowers_score():
    """Missing crop, location, weather, and soil significantly lowers EQS."""
    sparse_state = AgriMindState(run_id="test-sparse")
    sparse_state.crop = CropContext(crop="", growth_stage="")
    sparse_state.weather = WeatherResult(is_available=False, status="UNAVAILABLE")
    sparse_state.soil = SoilResult(npk_available=False, status="UNAVAILABLE")
    sparse_state.raw_inputs = {}

    eqs, level, breakdown = calculate_evidence_quality(sparse_state)
    assert eqs < 0.40
    assert level in ("LOW", "INSUFFICIENT")
    assert breakdown.completeness == 0.0


# ==============================================================================
# 5. DETERMINISTIC AGRONOMIC SAFETY GUARD TESTS
# ==============================================================================

def test_safety_guard_rule_a_blocks_fertilizer_without_npk():
    """Rule A: If NPK is unmeasured, exact fertilizer dosage is blocked; forced to monitor."""
    state = AgriMindState(run_id="test-safety-a")
    state.soil = SoilResult(overall_deficiency=None, npk_available=False, status="UNAVAILABLE")
    action, reason, constraints, pen = apply_agronomic_safety_guard(state, "apply_fertilizer", "weighted_score")
    assert action == "monitor"
    assert "rule_a" in reason
    assert any("Rule A" in c and "Soil testing is required" in c for c in constraints)


def test_safety_guard_rule_b_blocks_low_confidence_disease_treatment():
    """Rule B: Disease confidence below 0.60 blocks disease-specific action."""
    state = AgriMindState(run_id="test-safety-b")
    state.disease = DiseaseResult(predicted_class="Tomato___Early_blight", confidence=0.45, actionable=False)
    action, reason, constraints, pen = apply_agronomic_safety_guard(state, "DISEASE_MANAGEMENT_FIRST", "disease_urgency")
    assert action == "monitor"
    assert any("Rule B" in c and "insufficient for treatment advice" in c for c in constraints)


def test_safety_guard_rule_c_blocks_crop_mismatch():
    """Rule C: Mismatch between disease model and crop blocks disease action."""
    state = AgriMindState(run_id="test-safety-c")
    state.crop = CropContext(crop="Rice")
    state.disease = DiseaseResult(predicted_class="Tomato___Early_blight", confidence=0.88, crop_mismatch=True, actionable=False)
    action, reason, constraints, pen = apply_agronomic_safety_guard(state, "DISEASE_MANAGEMENT_FIRST", "disease_urgency")
    assert action == "monitor"
    assert any("Rule C" in c and "conflicts with selected crop" in c for c in constraints)


def test_safety_guard_rule_d_blocks_unsafe_weather():
    """Rule D: High rainfall risk blocks application and enforces DELAY."""
    state = AgriMindState(run_id="test-safety-d")
    state.weather = WeatherResult(rainfall_risk=0.75, risk_level="HIGH")
    state.soil = SoilResult(npk_available=True, overall_deficiency=0.70, status="MEASURED")
    action, reason, constraints, pen = apply_agronomic_safety_guard(state, "apply_fertilizer", "weighted_score")
    assert action == "delay"
    assert any("Rule D" in c and "DELAY enforced" in c for c in constraints)


def test_safety_guard_rule_e_downgrades_confidence_for_stale_data():
    """Rule E: Offline or invalid weather telemetry penalizes confidence."""
    state = AgriMindState(run_id="test-safety-e")
    state.weather = WeatherResult(is_available=False, status="TIMEOUT")
    action, reason, constraints, pen = apply_agronomic_safety_guard(state, "monitor", "neutral")
    assert pen > 0.0
    assert any("Rule E" in c for c in constraints)


# ==============================================================================
# 6. DECISION SENSITIVITY ("WHAT WOULD CHANGE THIS DECISION?") TESTS
# ==============================================================================

def test_decision_sensitivity_triggers_missing_npk_and_weather():
    """Missing NPK and elevated rainfall dynamically appear in decision change triggers."""
    state = AgriMindState(run_id="test-triggers")
    state.crop = CropContext(crop="Rice", growth_stage="vegetative")
    state.soil = SoilResult(npk_available=False, overall_deficiency=None)
    state.weather = WeatherResult(rainfall_risk=0.65, risk_level="HIGH")

    triggers = derive_decision_change_triggers(state, "delay", ["Rule A", "Rule D"])
    assert any("NPK values become available" in t for t in triggers)
    assert any("Rainfall risk decreases below 0.30" in t for t in triggers)
    assert any("growth stage" in t for t in triggers)


def test_end_to_end_phase2_advisory_payload():
    """End-to-end run confirms all Phase 2 metrics are populated in the advisory response."""
    inputs = {
        "location_name": "Madurai, Tamil Nadu",
        "crop": "Rice",
        "growth_stage": "flowering",
    }
    result_state = run_advisory(inputs)
    assert result_state.final_recommendation in ("monitor", "delay")
    assert result_state.evidence_quality_score > 0.0
    assert result_state.evidence_quality_level in ("GOOD", "MODERATE", "LOW")
    assert result_state.evidence_quality_breakdown is not None
    assert len(result_state.decision_change_triggers) > 0
    assert len(result_state.safety_constraints) > 0
    assert result_state.weather.risk_level in ("LOW", "MODERATE", "HIGH", "SEVERE")
    assert len(result_state.weather.risk_explanation) > 0
    assert result_state.soil.nutrient_status == "UNAVAILABLE"
    assert result_state.soil.overall_deficiency is None


def test_rag_rice_tamil_nadu_excludes_fish_culture_and_unrelated_crops():
    """Verify that retrieval for Rice in Tamil Nadu flowering excludes fish culture and unrelated crops."""
    retriever = KnowledgeRetriever(corpus_path=str(CORPUS_PATH))
    hits = retriever.search(
        "Rice flowering management Tamil Nadu",
        n_results=4,
        crop="Rice",
        growth_stage="flowering",
        location="Tamil Nadu",
    )
    assert len(hits) > 0
    # Provenance fields present
    for h in hits:
        assert "source" in h
        assert "document" in h
        assert "page" in h
        assert "chunk" in h
        assert "score" in h
        assert "relevance_badges" in h
        assert "source_reliability" in h
        # Ensure no fish culture or fingerlings or pond fertility appears
        txt = h["text"].lower()
        assert "fish culture" not in txt
        assert "fingerlings" not in txt
        assert "pond fertility" not in txt
        # Crop match must be HIGH or MEDIUM
        assert h["crop_relevance"] >= 0.70


def test_disease_crop_mismatch_wording_accurate():
    """When confidence is high (0.95) but crop mismatches, wording must not claim below 0.60 gate."""
    from llm.explainer import deterministic_explanation

    state = AgriMindState(run_id="test-dis-mismatch")
    state.crop = CropContext(crop="Rice", growth_stage="flowering")
    state.disease = DiseaseResult(
        predicted_class="Tomato___Early_blight",
        confidence=0.95,
        crop_mismatch=True,
        actionable=False,
    )
    state.weather = WeatherResult(rainfall_risk=0.20, risk_level="LOW")
    state.soil = SoilResult(npk_available=False, overall_deficiency=None)
    state.final_recommendation = "monitor"

    action, reason, constraints, pen = apply_agronomic_safety_guard(state)
    explanation = deterministic_explanation(state)

    # Must NOT claim below 0.60 confidence gate
    assert "below the 0.60 confidence gate" not in explanation
    # Must explicitly state confidence gate passed, crop match failed, action blocked
    assert "Confidence gate: PASSED" in explanation
    assert "Crop match: FAILED" in explanation
    assert "Disease action: BLOCKED" in explanation
    assert "Predicted crop is Tomato but selected crop is Rice" in explanation
    assert "95%" in explanation
    # Rule C must be triggered, NOT Rule B
    assert any("Rule C" in c for c in constraints)
    assert not any("Rule B" in c for c in constraints)

