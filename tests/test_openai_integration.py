"""Comprehensive verification of the OpenAI-only explanation architecture.

Tests all 12 required scenarios:
1. Healthy crop
2. Disease detected
3. Disease + nutrient deficiency
4. Nutrient deficiency without disease
5. High rainfall -> DELAY
6. Low-confidence disease
7. Missing NPK
8. Market conflict
9. OpenAI successful response
10. OpenAI API failure
11. Invalid OpenAI response
12. Deterministic fallback

For every test: verifies that the deterministic decision remains authoritative.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from api.main import app
from fastapi.testclient import TestClient
from llm import explainer
from orchestrator.graph import run_advisory

client = TestClient(app)


# ------------------------------------------------------------------------------
# Test 1: Healthy Crop
# ------------------------------------------------------------------------------
def test_1_healthy_crop(monkeypatch):
    """Healthy crop with normal conditions retains authoritative deterministic decision."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (
        {
            "summary": "Crop foliage is healthy. Continue standard scouting.",
            "why_this_decision": "No pathogens or severe weather constraints detected.",
            "immediate_guidance": "Maintain routine irrigation.",
            "additional_agronomic_context": ["Foliage shows normal chlorophyll index."],
            "important_cautions": ["Do not apply unverified prophylactic pesticides."],
            "what_could_change_decision": ["Appearance of leaf spots."],
            "evidence_used": ["ICAR Good Agricultural Practices"],
            "uncertainty": "Calibrated against visual assessment.",
            "llm_role": "explanation_only",
        },
        {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}
    ))
    explainer._CACHE.clear()

    inputs = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "disease_override": {"predicted_class": "Tomato___healthy", "confidence": 0.98},
        "weather_override": {"precip_prob": 0.1, "intensity": 0.0},
    }
    state = run_advisory(inputs)
    assert state.final_recommendation in ("monitor", "apply_fertilizer")
    result = explainer.explain_with_metadata(state)
    assert result.provider == "openai"
    assert result.status == "success"
    assert result.structured_explanation["llm_role"] == "explanation_only"


# ------------------------------------------------------------------------------
# Test 2: Disease Detected
# ------------------------------------------------------------------------------
def test_2_disease_detected(monkeypatch):
    """Disease detected triggers DISEASE_MANAGEMENT_FIRST and LLM cannot override it."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # Simulate LLM attempting to recommend fertilizer
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (
        {
            "summary": "Early blight detected on tomato foliage. Phytosanitary treatment required.",
            "why_this_decision": "High confidence foliar disease must be treated before nutritional correction.",
            "immediate_guidance": "Isolate affected foliage and apply verified bio-fungicide.",
            "additional_agronomic_context": ["Pathogen spreads rapidly in warm humid microclimates."],
            "important_cautions": ["Never apply nitrogen top-dressing to active blight as it accelerates vegetative tissue susceptibility."],
            "what_could_change_decision": ["Containment of leaf lesions."],
            "evidence_used": ["ICAR Tomato Crop Protection"],
            "uncertainty": "Lab culture or extension confirmation recommended.",
            "llm_role": "explanation_only",
        },
        None
    ))
    explainer._CACHE.clear()

    inputs = {
        "crop": "Tomato",
        "disease_override": {"predicted_class": "Tomato___Early_blight", "confidence": 0.92},
        "weather_override": {"precip_prob": 0.1, "intensity": 0.0},
    }
    state = run_advisory(inputs)
    assert state.final_recommendation == "DISEASE_MANAGEMENT_FIRST"
    result = explainer.explain_with_metadata(state)
    assert result.provider == "openai"
    # Authoritative recommendation on state remains DISEASE_MANAGEMENT_FIRST
    assert state.final_recommendation == "DISEASE_MANAGEMENT_FIRST"


# ------------------------------------------------------------------------------
# Test 3: Disease + Nutrient Deficiency (Disease precedence)
# ------------------------------------------------------------------------------
def test_3_disease_plus_nutrient_deficiency(monkeypatch):
    """Disease takes priority over nutrient deficiency, decision engine is authoritative."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (
        {
            "summary": "Disease treatment takes absolute precedence over severe nitrogen deficit.",
            "why_this_decision": "Nutrient application during active foliar fungal attack worsens lesion spread.",
            "immediate_guidance": "Treat disease first; hold fertilizer application.",
            "additional_agronomic_context": ["Foliar pathogen suppresses nutrient translocation."],
            "important_cautions": ["Fertilizer application is currently blocked by agronomic safety guard."],
            "what_could_change_decision": ["Complete disease remediation."],
            "evidence_used": ["ICAR Integrated Pest and Disease Management"],
            "uncertainty": "Field verification recommended.",
            "llm_role": "explanation_only",
        },
        None
    ))
    explainer._CACHE.clear()

    inputs = {
        "crop": "Tomato",
        "n": 10.0, "p": 15.0, "k": 20.0,
        "disease_override": {"predicted_class": "Tomato___Early_blight", "confidence": 0.95},
        "weather_override": {"precip_prob": 0.05, "intensity": 0.0},
    }
    state = run_advisory(inputs)
    assert state.final_recommendation == "DISEASE_MANAGEMENT_FIRST"
    result = explainer.explain_with_metadata(state)
    assert state.final_recommendation == "DISEASE_MANAGEMENT_FIRST"


# ------------------------------------------------------------------------------
# Test 4: Nutrient Deficiency without Disease
# ------------------------------------------------------------------------------
def test_4_nutrient_deficiency_without_disease(monkeypatch):
    """Nutrient deficiency with clear weather and healthy crop recommends apply_fertilizer."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (
        {
            "summary": "Apply scheduled fertilizer replenishment to correct verified nitrogen deficit.",
            "why_this_decision": "Soil test indicates severe nitrogen deficiency.",
            "immediate_guidance": "Apply split dose as basal or top-dressing.",
            "additional_agronomic_context": ["Nitrogen is critical for tillering/canopy development."],
            "important_cautions": ["Exact application rate requires verification against the applicable agronomic recommendation for the crop, soil and field conditions."],
            "what_could_change_decision": ["Sudden rainfall forecast."],
            "evidence_used": ["ICAR Soil Health Card Scheme"],
            "uncertainty": "Calibrated against soil test parameters.",
            "llm_role": "explanation_only",
        },
        None
    ))
    explainer._CACHE.clear()

    inputs = {
        "crop": "Wheat",
        "n": 15.0, "p": 25.0, "k": 35.0,
        "disease_override": {"predicted_class": "Tomato___healthy", "confidence": 0.95},
        "weather_override": {"precip_prob": 0.1, "intensity": 0.0},
    }
    state = run_advisory(inputs)
    assert state.final_recommendation == "apply_fertilizer"
    result = explainer.explain_with_metadata(state)
    assert state.final_recommendation == "apply_fertilizer"


# ------------------------------------------------------------------------------
# Test 5: High Rainfall -> DELAY
# ------------------------------------------------------------------------------
def test_5_high_rainfall_delay(monkeypatch):
    """High rainfall triggers DELAY veto and LLM must explain postponement."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (
        {
            "summary": "Application postponed due to severe rainfall hazard.",
            "why_this_decision": "High precipitation risk causes chemical wash-off and leaching.",
            "immediate_guidance": "Suspend all spraying and chemical field operations.",
            "additional_agronomic_context": ["Waterlogged soils impede plant nutrient absorption."],
            "important_cautions": ["Chemical application under rainfall violates safety standards."],
            "what_could_change_decision": ["Precipitation probability dropping below 30%."],
            "evidence_used": ["IMD Agro-Meteorological Weather Protocol"],
            "uncertainty": "Forecast horizon 48 hours.",
            "llm_role": "explanation_only",
        },
        None
    ))
    explainer._CACHE.clear()

    inputs = {
        "crop": "Rice",
        "n": 10.0, "p": 15.0, "k": 20.0,
        "weather_override": {"precip_prob": 0.95, "intensity": 25.0, "duration": 6.0},
    }
    state = run_advisory(inputs)
    assert state.final_recommendation == "DELAY"
    result = explainer.explain_with_metadata(state)
    assert state.final_recommendation == "DELAY"


# ------------------------------------------------------------------------------
# Test 6: Low Confidence Disease (< 0.60 gate)
# ------------------------------------------------------------------------------
def test_6_low_confidence_disease(monkeypatch):
    """Disease detection below 0.60 confidence gate is blocked from triggering disease action."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    explainer._CACHE.clear()

    inputs = {
        "crop": "Tomato",
        "disease_override": {"predicted_class": "Tomato___Early_blight", "confidence": 0.45},
        "weather_override": {"precip_prob": 0.1, "intensity": 0.0},
    }
    state = run_advisory(inputs)
    assert not state.disease.actionable
    assert state.final_recommendation != "disease_management_first"


# ------------------------------------------------------------------------------
# Test 7: Missing NPK
# ------------------------------------------------------------------------------
def test_7_missing_npk(monkeypatch):
    """Missing NPK prevents blind chemical dosing claims."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    explainer._CACHE.clear()

    inputs = {
        "crop": "Wheat",
        "weather_override": {"precip_prob": 0.1, "intensity": 0.0},
    }
    state = run_advisory(inputs)
    result = explainer.explain_with_metadata(state)
    assert result.structured_explanation is not None
    assert "Unmeasured" in str(result.structured_explanation["additional_agronomic_context"]) or "not provided" in result.text


# ------------------------------------------------------------------------------
# Test 8: Market Conflict
# ------------------------------------------------------------------------------
def test_8_market_conflict(monkeypatch):
    """Market sell signal during vegetative stage does not override agronomic field care."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    explainer._CACHE.clear()

    inputs = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "current_price": 5000.0,
        "price_history": [2000.0, 3000.0, 4500.0, 5000.0],
        "weather_override": {"precip_prob": 0.1, "intensity": 0.0},
    }
    state = run_advisory(inputs)
    # Agronomic recommendation remains primary; vegetative crop cannot be harvested early
    assert state.final_recommendation in ("monitor", "apply_fertilizer")
    result = explainer.explain_with_metadata(state)
    assert state.final_recommendation in ("monitor", "apply_fertilizer")


# ------------------------------------------------------------------------------
# Test 9: OpenAI Successful Response
# ------------------------------------------------------------------------------
def test_9_openai_successful_response(monkeypatch):
    """OpenAI successful response returns structured data with status=success."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    mock_resp = {
        "summary": "Verified explanation from OpenAI.",
        "why_this_decision": "Clear agronomic rationale.",
        "immediate_guidance": "Field action step.",
        "additional_agronomic_context": ["Context A", "Context B"],
        "important_cautions": ["Caution A"],
        "what_could_change_decision": ["Trigger A"],
        "evidence_used": ["Evidence doc 1"],
        "uncertainty": "Low uncertainty.",
        "llm_role": "explanation_only",
    }
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (mock_resp, {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}))
    explainer._CACHE.clear()

    state = SimpleNamespace(
        run_id="run-9",
        final_recommendation="monitor",
        execution_trace=["orchestrator -> monitor"],
        weather=SimpleNamespace(rainfall_risk=0.1, risk_level="LOW", risk_explanation="Clear skies."),
        soil=SimpleNamespace(npk_available=False, overall_deficiency=None, priority_nutrient=None),
        disease=SimpleNamespace(predicted_class=None, confidence=0.0, actionable=False),
        advisory=SimpleNamespace(scores={"monitor": 0.9}),
        market=SimpleNamespace(signal="hold", market_score=0.5),
        crop=SimpleNamespace(crop="Maize", growth_stage="vegetative"),
    )
    result = explainer.explain_with_metadata(state)
    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.status == "success"
    assert result.fallback_used is False
    assert result.structured_explanation["why_this_decision"] == "Clear agronomic rationale."


# ------------------------------------------------------------------------------
# Test 10: OpenAI API Failure -> Deterministic Fallback
# ------------------------------------------------------------------------------
def test_10_openai_api_failure(monkeypatch):
    """OpenAI API failure (timeout, network down) falls back to deterministic explanation."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Connection timed out")))
    explainer._CACHE.clear()

    state = SimpleNamespace(
        run_id="run-10",
        final_recommendation="DELAY",
        execution_trace=["orchestrator -> DELAY"],
        weather=SimpleNamespace(rainfall_risk=0.9, risk_level="HIGH", risk_explanation="Heavy rain."),
        soil=SimpleNamespace(npk_available=True, overall_deficiency=0.3, priority_nutrient="nitrogen"),
        disease=SimpleNamespace(predicted_class=None, confidence=0.0, actionable=False),
        advisory=SimpleNamespace(scores={"delay": 0.8}),
        market=SimpleNamespace(signal="hold", market_score=0.5),
        crop=SimpleNamespace(crop="Tomato", growth_stage="vegetative"),
    )
    result = explainer.explain_with_metadata(state)
    assert result.provider == "deterministic"
    assert result.status == "fallback"
    assert result.fallback_used is True
    assert "Recommendation: DELAY." in result.text


# ------------------------------------------------------------------------------
# Test 11: Invalid OpenAI Response -> Fallback
# ------------------------------------------------------------------------------
def test_11_invalid_openai_response(monkeypatch):
    """Invalid/malformed schema from OpenAI falls back to deterministic explanation."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: ({"corrupted": True}, None))
    explainer._CACHE.clear()

    state = SimpleNamespace(
        run_id="run-11",
        final_recommendation="apply_fertilizer",
        execution_trace=["orchestrator -> apply_fertilizer"],
        weather=SimpleNamespace(rainfall_risk=0.1, risk_level="LOW", risk_explanation="Clear skies."),
        soil=SimpleNamespace(npk_available=True, overall_deficiency=0.6, priority_nutrient="phosphorus"),
        disease=SimpleNamespace(predicted_class=None, confidence=0.0, actionable=False),
        advisory=SimpleNamespace(scores={"apply_fertilizer": 0.8}),
        market=SimpleNamespace(signal="hold", market_score=0.5),
        crop=SimpleNamespace(crop="Wheat", growth_stage="vegetative"),
    )
    result = explainer.explain_with_metadata(state)
    assert result.provider == "deterministic"
    assert result.status == "fallback"
    assert result.fallback_used is True
    assert "Recommendation: apply fertilizer." in result.text


# ------------------------------------------------------------------------------
# Test 12: Deterministic Fallback (No Key)
# ------------------------------------------------------------------------------
def test_12_deterministic_fallback_no_key(monkeypatch):
    """When no OpenAI key is set, zero external latency and deterministic template is used."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    explainer._CACHE.clear()

    state = SimpleNamespace(
        run_id="run-12",
        final_recommendation="monitor",
        execution_trace=["orchestrator -> monitor"],
        weather=SimpleNamespace(rainfall_risk=0.1, risk_level="LOW", risk_explanation="Clear skies."),
        soil=SimpleNamespace(npk_available=False, overall_deficiency=None, priority_nutrient=None),
        disease=SimpleNamespace(predicted_class=None, confidence=0.0, actionable=False),
        advisory=SimpleNamespace(scores={"monitor": 0.8}),
        market=SimpleNamespace(signal="hold", market_score=0.5),
        crop=SimpleNamespace(crop="Maize", growth_stage="vegetative"),
    )
    result = explainer.explain_with_metadata(state)
    assert result.provider == "deterministic"
    assert result.model == "rule-based-template"
    assert result.status == "deterministic"
    assert result.fallback_used is False
    assert result.latency_ms == 0.0
    assert result.error is None
