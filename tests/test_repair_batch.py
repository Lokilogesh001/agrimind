"""Comprehensive test suite verifying the complete AgriMind repair batch."""
import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import disease_agent, market_agent, soil_agent, weather_agent
from api.main import app
from data_sources import soil as soil_ds
from decision.rules import resolve_conflict
from decision.scoring import weighted_score, _weather_suitability
from observability import database as obs
from orchestrator.graph import run_advisory
from orchestrator.state import AgriMindState, WeatherResult, SoilResult, DiseaseResult, MarketResult
from rag.retriever import KnowledgeRetriever


# ==============================================================================
# 1. DISEASE AGENT TESTS
# ==============================================================================

def test_disease_no_image_no_override():
    """Case C: No image and no override must return safe default without crashing."""
    res = disease_agent.run(image_path=None, override=None)
    assert res.predicted_class is None
    assert res.confidence == 0.0
    assert res.severity == "low"
    assert res.actionable is False
    assert res.normalized_disease is None


def test_disease_override_used_normally():
    """Case B: disease_override is respected and normalized."""
    override = {"predicted_class": "Tomato___Early_blight", "confidence": 0.88}
    res = disease_agent.run(override=override)
    assert res.predicted_class == "Tomato___Early_blight"
    assert res.confidence == 0.88
    assert res.severity == "high"
    assert res.actionable is True
    assert res.normalized_disease == "early blight"
    assert res.crop_detected == "tomato"


def test_disease_low_confidence_gate():
    """Confidence below 0.60 must yield actionable=False."""
    override = {"predicted_class": "Tomato___Early_blight", "confidence": 0.45}
    res = disease_agent.run(override=override)
    assert res.actionable is False


def test_disease_normalization_plantvillage_labels():
    """Verify multiple PlantVillage label formats are cleanly normalized."""
    labels = {
        "Tomato___Early_blight": ("tomato", "early blight"),
        "Potato___Late_blight": ("potato", "late blight"),
        "Corn_(maize)___healthy": ("corn", "healthy"),
        "Apple___Apple_scab": ("apple", "apple scab"),
        "Tomato_Early_blight": ("tomato", "early blight"),
        "healthy": ("", "healthy"),
    }
    for raw, (expected_crop, expected_disease) in labels.items():
        norm = disease_agent.normalize_disease_label(raw)
        assert norm["crop"] == expected_crop
        assert norm["disease"] == expected_disease


def test_disease_inference_with_real_image(tmp_path):
    """Case A: Valid image runs MobileNetV3 inference without crashing."""
    img_path = str(tmp_path / "test_leaf.jpg")
    Image.new("RGB", (224, 224), (60, 130, 45)).save(img_path)
    res = disease_agent.run(image_path=img_path)
    assert res.predicted_class is not None
    assert 0.0 <= res.confidence <= 1.0
    assert res.severity in {"low", "moderate", "high"}


# ==============================================================================
# 2. WEATHER AGENT & WEATHER FAILURE SAFETY TESTS
# ==============================================================================

def test_weather_failure_handled_explicitly():
    """Weather lookup failure must set is_available=False and confidence=0.0."""
    res = weather_agent.run(lat=None, lon=None)
    assert res.is_available is False
    assert res.confidence == 0.0
    assert res.reason == "weather_unavailable"


def test_weather_failure_not_interpreted_as_safe_weather():
    """WEATHER FAILURE != GOOD WEATHER. Suitability must not be 1.0 (1 - 0.0)."""
    state = AgriMindState(run_id="weather-test")
    state.weather = WeatherResult(rainfall_risk=0.0, confidence=0.0, is_available=False, reason="weather_unavailable")
    suitability = _weather_suitability(state, "apply_fertilizer")
    # Must be neutral/conservative (0.50), not 1.0
    assert suitability == 0.5


def test_weather_normal_suitability():
    """When weather is available, rainfall risk influences suitability normally."""
    state = AgriMindState(run_id="weather-test")
    state.weather = WeatherResult(rainfall_risk=0.10, confidence=0.85, is_available=True)
    assert _weather_suitability(state, "apply_fertilizer") == 0.90
    assert _weather_suitability(state, "delay") == 0.10


# ==============================================================================
# 3. SOIL AGENT CALIBRATION TESTS
# ==============================================================================

def test_soil_crop_specific_targets():
    """Crop targets must differ between heavy feeders and nitrogen-fixing legumes."""
    tomato_targets, tomato_weights = soil_ds.get_reference_targets(crop="Tomato")
    legume_targets, legume_weights = soil_ds.get_reference_targets(crop="Groundnut")

    # Tomato needs more N (120) than legume groundnut (25)
    assert tomato_targets["N"] > legume_targets["N"]
    # Legumes weight P heavily for root nodulation
    assert legume_weights["P"] > tomato_weights["P"]


def test_soil_type_multipliers():
    """Sandy leaching soil vs clay nutrient-retentive soil adjustments."""
    sandy_targets, _ = soil_ds.get_reference_targets(crop="Tomato", soil_type="sandy")
    clay_targets, _ = soil_ds.get_reference_targets(crop="Tomato", soil_type="clay")

    # Sandy soil has higher leaching multiplier for N & K than clay
    assert sandy_targets["N"] > clay_targets["N"]
    assert sandy_targets["K"] > clay_targets["K"]


def test_soil_result_metadata():
    """SoilResult must expose transparent calculation metadata."""
    res = soil_agent.run(n=30, p=45, k=60, crop="Tomato", soil_type="loam")
    assert res.supplied == {"n": 30.0, "p": 45.0, "k": 60.0}
    assert res.targets["N"] == 120.0
    assert res.crop == "Tomato"
    assert res.soil_type == "loam"
    assert res.calibration_source == "project_calibration_heuristic"
    assert res.overall_deficiency > 0.0


# ==============================================================================
# 4. MARKET AGENT & DATA SOURCE TESTS
# ==============================================================================

def test_market_available_data():
    """Supplied prices calculate trend, volatility, and score with confidence."""
    res = market_agent.run(current_price=2200, price_history=[1900, 1950, 2000, 2050])
    assert res.is_available is True
    assert res.confidence >= 0.70
    assert res.market_score > 0.0
    assert res.signal in {"sell", "hold", "caution"}


def test_market_unavailable_data():
    """Missing prices must not fabricate data; marks unavailable safely."""
    res = market_agent.run(current_price=0, price_history=[])
    assert res.is_available is False
    assert res.confidence == 0.0
    assert res.signal == "hold"


# ==============================================================================
# 5. DECISION ENGINE SAFETY TESTS
# ==============================================================================

def test_decision_missing_disease_does_not_trigger_urgency():
    """Missing disease signal must never trigger DISEASE_MANAGEMENT_FIRST."""
    state = AgriMindState(run_id="dec-test")
    state.weather = WeatherResult(rainfall_risk=0.1, confidence=0.85, is_available=True)
    state.soil = SoilResult(overall_deficiency=0.3, confidence=0.9)
    state.disease = DiseaseResult(predicted_class=None, confidence=0.0, actionable=False, severity="low")
    state.market = MarketResult(is_available=False, confidence=0.0)
    decision = resolve_conflict(state)
    assert decision.action != "DISEASE_MANAGEMENT_FIRST"
    assert state.disease.actionable is False


def test_decision_missing_weather_conservative():
    """When weather is unavailable and soil deficiency is low, system does not blindly apply fertilizer."""
    state = AgriMindState(run_id="dec-test")
    state.weather = WeatherResult(rainfall_risk=0.0, confidence=0.0, is_available=False, reason="weather_unavailable")
    state.soil = SoilResult(overall_deficiency=0.2, confidence=0.9)
    state.disease = DiseaseResult(predicted_class=None, confidence=0.0, actionable=False)
    state.market = MarketResult(is_available=False, confidence=0.0)
    decision = resolve_conflict(state)
    assert decision.action in {"monitor", "delay"}


# ==============================================================================
# 6. RAG RETRIEVAL WITH NORMALIZATION TESTS
# ==============================================================================

def test_rag_with_raw_and_normalized_labels():
    """Knowledge retriever gets strong relevance with both raw and clean disease strings."""
    r = KnowledgeRetriever()
    hits_raw = r.search("Tomato early blight", n_results=4, crop="tomato", disease="Tomato___Early_blight")
    assert hits_raw
    assert any("tomato" in h.get("metadata", {}).get("crops", "") for h in hits_raw)
    assert any("early blight" in h.get("text", "").lower() for h in hits_raw)


def test_rag_empty_query():
    """Empty query returns empty list without error."""
    assert KnowledgeRetriever().search("") == []


# ==============================================================================
# 7. END-TO-END API TESTS
# ==============================================================================

def test_api_advisory_without_image_succeeds():
    """POST /api/advisory without an image returns HTTP 200 with complete advisory."""
    client = TestClient(app)
    payload = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "lat": 13.08,
        "lon": 80.27,
        "n": 25,
        "p": 45,
        "k": 70,
        "current_price": 2000,
        "price_history": [1950, 1980, 2000],
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["recommendation"]
    assert "explanation" in data
    assert data["disease"]["predicted_class"] is None
    assert data["disease"]["actionable"] is False
    assert data["soil"]["overall_deficiency"] > 0
    assert "audit" in data


def test_api_advisory_with_override_succeeds():
    """POST /api/advisory with disease_override succeeds."""
    client = TestClient(app)
    payload = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "lat": 13.08,
        "lon": 80.27,
        "n": 25,
        "p": 45,
        "k": 70,
        "disease_override": {"predicted_class": "Tomato___Early_blight", "confidence": 0.85},
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["recommendation"] == "DISEASE_MANAGEMENT_FIRST"
    assert data["disease"]["normalized_disease"] == "early blight"


def test_api_advisory_upload_with_image():
    """POST /api/advisory/upload with valid JPEG executes end-to-end."""
    client = TestClient(app)
    buf = io.BytesIO()
    Image.new("RGB", (224, 224), (70, 140, 50)).save(buf, format="JPEG")
    res = client.post(
        "/api/advisory/upload",
        data={"crop": "Tomato", "growth_stage": "vegetative", "n": 25, "p": 45, "k": 70},
        files={"image": ("leaf.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["recommendation"]
    assert data["disease"]["predicted_class"] is not None


def test_api_feedback_and_run_retrieval():
    """POST /api/feedback saves feedback and GET /api/runs/{run_id} returns it."""
    client = TestClient(app)
    # Generate a run
    res = client.post("/api/advisory", json={"n": 25, "p": 45, "k": 70})
    assert res.status_code == 200
    run_id = res.json()["run_id"]

    # Submit feedback
    fb_res = client.post(
        "/api/feedback",
        json={
            "run_id": run_id,
            "farmer_action_taken": "Applied recommended urea",
            "outcome_reported": "Crop recovered well",
            "comment": "Good advice",
        },
    )
    assert fb_res.status_code == 200
    assert fb_res.json()["status"] == "saved"

    # Retrieve run trail
    run_trail = client.get(f"/api/runs/{run_id}").json()
    assert run_trail["run_id"] == run_id
    assert len(run_trail["agent_logs"]) >= 5
    assert len(run_trail["decisions"]) >= 1
    assert run_trail.get("run") is not None
