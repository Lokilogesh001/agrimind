"""Comprehensive test suite for Adaptive Evidence & Conflict Resolution Engine.

Verifies:
1. Scenario 1: Location + crop + no soil NPK + no image -> works safely without fabricating NPK.
2. Scenario 2: Location + crop + manual soil type + no NPK -> works with USER_SELECTED provenance.
3. Scenario 3: Location + crop + measured NPK -> works with MEASURED provenance.
4. Scenario 4: Location + crop + leaf image -> works end-to-end with vision inference.
5. Scenario 5: Invalid location -> returns clear validation error (HTTP 422).
6. Scenario 6: Weather API unavailable -> does not recommend fertilizer simply because weather data failed.
7. Scenario 7: Disease confidence below threshold -> does not trigger disease-management action.
8. Scenario 8: Heavy rain + soil deficiency -> detects conflict and resolves according to safety veto.
9. Scenario 9: Crop mismatch between selected crop and disease model -> detects and records conflict.
10. Scenario 10: Low evidence availability -> produces low/insufficient Decision Stability Score.
11. Scenario 11: Caller-provided market demo data -> status=DEMO_DATA, is_available=true.
12. Scenario 12: No market data -> remains safely unavailable without fabricating prices.
13. Unit tests for location resolution, crop normalization, soil provenance, DSS, conflict resolution, re-evaluation triggers.
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from agents import advisory_agent, disease_agent, market_agent, soil_agent, weather_agent
from api.main import app
from data_sources.crops import (
    CROPS_REGISTRY,
    get_crop_registry,
    get_crops_by_category,
    normalize_crop,
    normalize_crop_stage,
)
from data_sources.geocoding import resolve_location, search_locations
from data_sources.soil import estimate_soil_from_location, get_provenance
from decision.evidence_engine import (
    calculate_decision_stability_score,
    collect_agent_evidence,
    detect_and_resolve_conflicts,
    evaluate_decision,
    get_stability_level,
)
from decision.rules import resolve_conflict
from orchestrator.graph import run_advisory
from orchestrator.state import (
    AgriMindState,
    CropContext,
    DiseaseResult,
    MarketResult,
    SoilResult,
    WeatherResult,
)

client = TestClient(app)


# ==============================================================================
# UNIT TESTS: GEOCODING & LOCATION RESOLUTION
# ==============================================================================

def test_unit_geocoding_known_location():
    """Resolving a known agricultural district returns coordinates and RESOLVED status."""
    res = resolve_location("Madurai, Tamil Nadu")
    assert res["status"] == "RESOLVED"
    assert res["latitude"] is not None
    assert res["longitude"] is not None
    assert "Tamil Nadu" in res["resolved_location"]


def test_unit_geocoding_invalid_empty():
    """Empty location string yields INVALID status without crashing or inventing coords."""
    res = resolve_location("")
    assert res["status"] == "INVALID"
    assert res["latitude"] is None
    assert res["longitude"] is None
    assert res["error"] is not None


def test_unit_geocoding_invalid_gibberish():
    """Non-existent gibberish location must not silently fabricate coordinates."""
    res = resolve_location("xyznonexistentplace9876543210")
    assert res["status"] in ("NOT_FOUND", "INVALID", "ERROR")
    assert res["latitude"] is None
    assert res["longitude"] is None


def test_unit_location_search_candidates():
    """search_locations returns multiple matching candidates."""
    hits = search_locations("Tamil Nadu")
    assert isinstance(hits, list)
    assert len(hits) >= 1
    assert any("latitude" in h for h in hits)


# ==============================================================================
# UNIT TESTS: CROP REGISTRY & NORMALIZATION
# ==============================================================================

def test_unit_crop_registry_structure():
    """Every crop in registry must have id, name, category, and aliases."""
    registry = get_crop_registry()
    assert len(registry) >= 20
    for crop in registry:
        assert "id" in crop
        assert "name" in crop
        assert "category" in crop
        assert isinstance(crop["aliases"], list)


def test_unit_crop_category_grouping():
    """Categories correctly group crops into cereals, pulses, oilseeds, vegetables, fruits, commercial."""
    grouped = get_crops_by_category()
    assert "Cereals" in grouped
    assert "Vegetables" in grouped
    assert "Pulses" in grouped
    assert any(c["id"] == "rice" for c in grouped["Cereals"])
    assert any(c["id"] == "tomato" for c in grouped["Vegetables"])


def test_unit_crop_alias_normalization():
    """Alternate user spellings and aliases normalize to canonical crop."""
    paddy = normalize_crop("paddy")
    assert paddy is not None
    assert paddy["id"] == "rice"

    corn = normalize_crop("corn")
    assert corn is not None
    assert corn["id"] == "maize"

    tamatar = normalize_crop("tamatar")
    assert tamatar is not None
    assert tamatar["id"] == "tomato"


def test_unit_crop_stage_normalization():
    """Stage aliases normalize to standard ID."""
    assert normalize_crop_stage("vegetative") == "vegetative"
    assert normalize_crop_stage("Flowering / Bloom") == "flowering"
    assert normalize_crop_stage("pod formation") == "fruiting_grain_filling"
    assert normalize_crop_stage("sprout") == "seedling"
    assert normalize_crop_stage(None) == "unknown"


# ==============================================================================
# UNIT TESTS: SOIL PROVENANCE & FLEXIBLE NPK
# ==============================================================================

def test_unit_soil_missing_npk_does_not_fabricate_deficiency():
    """Missing NPK must yield confidence=0, npk_available=False, and deficiency=None (UNAVAILABLE)."""
    res = soil_agent.run(n=None, p=None, k=None, crop="Tomato", soil_type="loam")
    assert res.npk_available is False
    assert res.confidence == 0.0
    assert res.overall_deficiency is None
    assert res.nutrient_status == "UNAVAILABLE"
    assert "Unavailable" in res.nutrient_assessment_text
    assert res.priority_nutrient == ""
    assert res.provenance["npk_available"] is False
    assert res.provenance["mode"] == "USER_SELECTED"


def test_unit_soil_location_estimation():
    """Regional soil estimation tags LOCATION_ESTIMATED without claiming field measurement."""
    est = estimate_soil_from_location(location_name="Ludhiana, Punjab")
    assert est["status"] == "LOCATION_ESTIMATED"
    assert est["soil_type"] == "alluvial"
    assert est["is_measured"] is False
    assert "not a field measurement" in est["note"]


def test_unit_soil_measured_mode_provenance():
    """When NPK is measured, provenance records MEASURED with calibrated targets."""
    res = soil_agent.run(n=40, p=50, k=60, crop="Tomato", soil_type="loam", mode="MEASURED")
    assert res.npk_available is True
    assert res.confidence == 0.9
    assert res.overall_deficiency > 0.0
    assert res.provenance["mode"] == "MEASURED"


# ==============================================================================
# UNIT TESTS: CONFLICT DETECTION & RESOLUTION NOVELTY
# ==============================================================================

def test_unit_conflict_weather_vs_fertilizer_veto():
    """High rainfall risk must veto soil deficiency and trigger DELAY with P1."""
    state = AgriMindState(run_id="conf-veto")
    state.weather = WeatherResult(rainfall_risk=0.85, confidence=0.90, is_available=True)
    state.soil = SoilResult(overall_deficiency=0.75, confidence=0.90, npk_available=True)
    decision = resolve_conflict(state)

    assert decision.action == "DELAY"
    assert decision.priority == 1
    assert decision.reason == "rainfall_risk"
    assert any(c["conflict_type"] == "weather_vs_fertilizer" for c in state.conflicts)
    assert "rainfall" in state.re_evaluation_trigger.lower()


def test_unit_conflict_crop_mismatch_suppression():
    """Crop mismatch between selected crop and model detected crop must be flagged as conflict."""
    state = AgriMindState(run_id="conf-mismatch")
    state.crop = CropContext(crop="Tomato")
    state.weather = WeatherResult(rainfall_risk=0.10, confidence=0.85, is_available=True)
    state.soil = SoilResult(overall_deficiency=0.10, confidence=0.90, npk_available=True)
    # Model detected potato late blight on tomato query
    res = disease_agent.run(
        override={"predicted_class": "Potato___Late_blight", "confidence": 0.88},
        selected_crop="Tomato",
    )
    state.disease = res
    assert res.crop_mismatch is True
    assert res.actionable is False

    decision = resolve_conflict(state)
    assert any(c["conflict_type"] == "disease_crop_mismatch" for c in state.conflicts)
    # Because of mismatch, disease management is NOT triggered
    assert decision.action != "DISEASE_MANAGEMENT_FIRST"


def test_unit_decision_stability_score_calculation():
    """DSS considers confidence, source reliability, temporal relevance, completeness, and penalties."""
    evidence = [
        {"agent": "weather", "confidence": 0.85, "source": "open_meteo"},
        {"agent": "soil", "confidence": 0.90, "source": "measured_soil_test"},
        {"agent": "disease", "confidence": 0.0, "source": "none"},
        {"agent": "market", "confidence": 0.80, "source": "agmarknet_api"},
    ]
    conflicts = []
    state = AgriMindState(run_id="dss-test")
    state.crop = CropContext(crop="Tomato")
    state.weather = WeatherResult(is_available=True, status="AVAILABLE")
    state.soil = SoilResult(npk_available=True)
    state.market = MarketResult(is_available=True)

    score = calculate_decision_stability_score(evidence, conflicts, state)
    assert 0.70 <= score <= 1.00
    level = get_stability_level(score)
    assert level in ("HIGH", "MODERATE")


# ==============================================================================
# MANDATORY SCENARIOS 1 TO 12 (Section 24)
# ==============================================================================

def test_scenario_1_location_crop_no_soil_npk_no_image():
    """Scenario 1: Location + crop + no soil NPK + no image must work safely."""
    payload = {
        "location_name": "Madurai, Tamil Nadu",
        "crop": "Tomato",
        "growth_stage": "vegetative",
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["recommendation"] in ("monitor", "delay")
    assert data["soil"]["npk_available"] is False
    assert data["soil"]["overall_deficiency"] is None
    assert data["soil"]["nutrient_status"] == "UNAVAILABLE"
    assert data["disease"]["predicted_class"] is None
    assert data["location"]["latitude"] is not None
    assert "re_evaluation_trigger" in data


def test_scenario_2_location_crop_manual_soil_no_npk():
    """Scenario 2: Location + crop + manual soil type + no NPK must work."""
    payload = {
        "location_name": "Pune, Maharashtra",
        "crop": "Wheat",
        "soil_type": "black",
        "soil_mode": "USER_SELECTED",
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["soil"]["soil_type"] == "black"
    assert data["soil"]["npk_available"] is False
    assert data["soil"]["provenance"]["mode"] == "USER_SELECTED"
    assert data["decision_stability_score"] >= 0.0


def test_scenario_3_location_crop_measured_npk():
    """Scenario 3: Location + crop + measured NPK must evaluate nutrient deficiency."""
    payload = {
        "location_name": "Karnal, Haryana",
        "crop": "Rice",
        "growth_stage": "vegetative",
        "n": 30,
        "p": 15,
        "k": 20,
        "soil_type": "alluvial",
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["soil"]["npk_available"] is True
    assert data["soil"]["overall_deficiency"] > 0.0
    assert data["soil"]["priority_nutrient"]
    assert data["decision_stability_score"] > 0.40


def test_scenario_4_location_crop_leaf_image(tmp_path):
    """Scenario 4: Location + crop + leaf image must run vision classification end-to-end."""
    img_path = tmp_path / "leaf.jpg"
    Image.new("RGB", (224, 224), (50, 150, 60)).save(img_path, format="JPEG")

    with open(img_path, "rb") as f:
        res = client.post(
            "/api/advisory/upload",
            data={
                "location_name": "Nashik, Maharashtra",
                "crop": "Tomato",
                "growth_stage": "vegetative",
            },
            files={"image": ("leaf.jpg", f.read(), "image/jpeg")},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["disease"]["predicted_class"] is not None
    assert data["recommendation"]
    assert data["decision_stability_score"] > 0


def test_scenario_5_invalid_location_returns_validation_error():
    """Scenario 5: Invalid location must return a clear validation error (HTTP 422)."""
    payload = {
        "location_name": "xyzinvalidnonexistentregion123456",
        "crop": "Tomato",
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 422
    assert "location" in res.json()["detail"].lower()


def test_scenario_6_weather_api_unavailable_does_not_blindly_recommend_fertilizer(monkeypatch):
    """Scenario 6: Weather API unavailable must not recommend fertilizer simply because weather data failed."""
    def fake_failed_weather(*args, **kwargs):
        return {"status": "UNAVAILABLE", "error": "connection_refused", "hourly": None}

    monkeypatch.setattr(weather_agent, "fetch_forecast", fake_failed_weather)
    payload = {
        "location_name": "Varanasi, Uttar Pradesh",
        "crop": "Tomato",
        "n": 100,  # Low deficiency
        "p": 50,
        "k": 70,
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["weather"]["is_available"] is False
    assert data["recommendation"] != "apply_fertilizer"
    assert data["recommendation"] in ("monitor", "delay")


def test_scenario_7_disease_confidence_below_threshold_not_actionable():
    """Scenario 7: Disease confidence below threshold (0.60) must not trigger disease-management action."""
    payload = {
        "location_name": "Coimbatore, Tamil Nadu",
        "crop": "Tomato",
        "disease_override": {"predicted_class": "Tomato___Early_blight", "confidence": 0.40},
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["disease"]["actionable"] is False
    assert data["recommendation"] != "DISEASE_MANAGEMENT_FIRST"


def test_scenario_8_heavy_rain_soil_deficiency_conflict_resolution():
    """Scenario 8: Heavy rain + soil deficiency must detect conflict and resolve according to weather safety veto."""
    payload = {
        "location_name": "Guntur, Andhra Pradesh",
        "crop": "Tomato",
        "n": 20,
        "p": 20,
        "k": 20,
        "weather_override": {"precip_prob": 0.95, "intensity": 0.90, "duration": 0.80},
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["recommendation"] == "DELAY"
    assert any(c["agent_a"] == "weather" and c["agent_b"] == "soil" for c in data["conflicts"])
    assert "heavy rainfall passes" in data["re_evaluation_trigger"].lower()


def test_scenario_9_crop_mismatch_detected_and_recorded():
    """Scenario 9: Crop mismatch between selected crop and disease model must detect and record conflict."""
    payload = {
        "location_name": "Indore, Madhya Pradesh",
        "crop": "Tomato",
        # Disease override predicts potato disease on a tomato farm query
        "disease_override": {"predicted_class": "Potato___Late_blight", "confidence": 0.90},
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["disease"]["crop_mismatch"] is True
    assert data["disease"]["actionable"] is False
    assert data["recommendation"] != "DISEASE_MANAGEMENT_FIRST"
    assert any(c["conflict_type"] == "disease_crop_mismatch" for c in data["conflicts"])


def test_scenario_10_low_evidence_produces_low_stability_score():
    """Scenario 10: Low evidence availability must produce LOW or INSUFFICIENT Decision Stability Score."""
    # Run with no NPK, no weather, no image, no market
    state = AgriMindState(run_id="scen-10")
    state.weather = WeatherResult(is_available=False, confidence=0.0, status="UNAVAILABLE")
    state.soil = SoilResult(npk_available=False, confidence=0.0, status="UNAVAILABLE")
    state.disease = DiseaseResult(predicted_class=None, confidence=0.0, actionable=False)
    state.market = MarketResult(is_available=False, confidence=0.0, status="UNAVAILABLE")

    evidence = collect_agent_evidence(state)
    dss = calculate_decision_stability_score(evidence, [], state)
    level = get_stability_level(dss)

    assert dss < 0.40
    assert level == "INSUFFICIENT"


def test_scenario_11_market_demo_data_semantics():
    """Scenario 11: Caller-provided market demo data must have status=DEMO_DATA, is_available=true."""
    res = market_agent.run(current_price=2300.0, price_history=[2100.0, 2200.0, 2300.0], crop="Tomato")
    assert res.status == "DEMO_DATA"
    assert res.is_available is True
    assert res.source == "caller_provided"
    assert res.confidence >= 0.70


def test_scenario_12_no_market_data_safely_unavailable():
    """Scenario 12: No market data must remain safely unavailable without fabricating prices."""
    res = market_agent.run(current_price=0.0, price_history=[], crop="")
    assert res.status == "UNAVAILABLE"
    assert res.is_available is False
    assert res.source == "none"
    assert res.confidence == 0.0
    assert res.signal == "hold"
