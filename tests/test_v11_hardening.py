"""Comprehensive v1.1 hardening and acceptance test suite for AgriMind.

Verifies:
1. Weather robustness (TIMEOUT, UNAVAILABLE, INVALID, missing precipitation).
2. Market data differentiation (REAL_DATA, DEMO_DATA, UNAVAILABLE).
3. Soil calibration provenance exposure.
4. API hardening (health, upload bounds, mime types, coord validation).
5. New E2E Scenarios 13-18.
"""
import io
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from agents import weather_agent, market_agent, soil_agent, disease_agent
from api.main import app
from data_sources import weather as weather_ds
from data_sources import market as market_ds
from decision.scoring import _weather_suitability
from llm import explainer
from observability import database as obs
from orchestrator.graph import run_advisory
from orchestrator.state import AgriMindState, WeatherResult, SoilResult, DiseaseResult, MarketResult


client = TestClient(app)


# ==============================================================================
# 1. WEATHER ROBUSTNESS & TIMEOUT / MALFORMED TESTS
# ==============================================================================

def test_weather_timeout_handled_explicitly(monkeypatch):
    """Weather provider timeout must set status=TIMEOUT and is_available=False."""
    def fake_timeout(*args, **kwargs):
        return {"status": "TIMEOUT", "error": "timeout", "hourly": None}

    monkeypatch.setattr(weather_agent, "fetch_forecast", fake_timeout)
    res = weather_agent.run(lat=13.08, lon=80.27)
    assert res.is_available is False
    assert res.status == "TIMEOUT"
    assert res.confidence == 0.0
    assert res.reason == "weather_timeout"


def test_weather_malformed_response_handled(monkeypatch):
    """Malformed or non-dict weather response must set status=INVALID and is_available=False."""
    def fake_malformed(*args, **kwargs):
        return {"status": "INVALID", "error": "malformed_json", "hourly": None}

    monkeypatch.setattr(weather_agent, "fetch_forecast", fake_malformed)
    res = weather_agent.run(lat=13.08, lon=80.27)
    assert res.is_available is False
    assert res.status == "INVALID"
    assert res.confidence == 0.0
    assert res.reason == "weather_malformed"


def test_weather_missing_precipitation_fields(monkeypatch):
    """Missing precipitation_probability or precipitation must NOT assume zero rain."""
    def fake_incomplete(*args, **kwargs):
        # Hourly present, but missing rainfall arrays
        return {"hourly": {"temperature_2m": [28.5, 29.0]}, "status": "AVAILABLE"}

    monkeypatch.setattr(weather_agent, "fetch_forecast", fake_incomplete)
    res = weather_agent.run(lat=13.08, lon=80.27)
    assert res.is_available is False
    assert res.status == "INVALID"
    assert res.confidence == 0.0
    assert res.reason == "missing_precipitation_data"


def test_weather_failure_does_not_inflate_fertilizer_suitability():
    """All weather failure conditions (TIMEOUT, UNAVAILABLE, INVALID) must evaluate to 0.50 neutral."""
    for st, reason in [("TIMEOUT", "weather_timeout"), ("UNAVAILABLE", "weather_unavailable"), ("INVALID", "weather_malformed")]:
        state = AgriMindState(run_id="suitability-test")
        state.weather = WeatherResult(rainfall_risk=0.0, confidence=0.0, is_available=False, status=st, reason=reason)
        score = _weather_suitability(state, "apply_fertilizer")
        assert score == 0.50, f"Expected 0.50 for {st}, got {score}"


# ==============================================================================
# 2. MARKET DATA DIFFERENTIATION TESTS
# ==============================================================================

def test_market_live_success_real_data(monkeypatch):
    """Live Agmarknet response must set status=REAL_DATA and source=agmarknet_api."""
    def fake_live(crop, market=None, timeout=8):
        return {
            "current_price": 2400.0,
            "price_history": [2200.0, 2300.0, 2400.0],
            "status": "REAL_DATA",
            "source": "agmarknet_api",
        }

    monkeypatch.setattr(market_agent, "fetch_prices", fake_live)
    res = market_agent.run(crop="tomato")
    assert res.is_available is True
    assert res.status == "REAL_DATA"
    assert res.source == "agmarknet_api"
    assert res.confidence >= 0.70
    assert res.market_score > 0.0


def test_market_unavailable_when_unconfigured(monkeypatch):
    """When AGMARKNET_BASE_URL is unconfigured and caller provides no price, status=UNAVAILABLE."""
    monkeypatch.delenv("AGMARKNET_BASE_URL", raising=False)
    res = market_agent.run(crop="tomato", current_price=0.0, price_history=[])
    assert res.is_available is False
    assert res.status == "UNAVAILABLE"
    assert res.source == "none"
    assert res.signal == "hold"
    assert res.confidence == 0.0


def test_market_caller_provided_demo_data():
    """Caller-provided prices must be labeled status=DEMO_DATA, source=caller_provided."""
    res = market_agent.run(current_price=2100.0, price_history=[1900.0, 2000.0, 2100.0], crop="tomato")
    assert res.is_available is True
    assert res.status == "DEMO_DATA"
    assert res.source == "caller_provided"
    assert res.confidence >= 0.70


# ==============================================================================
# 3. SOIL CALIBRATION & PROVENANCE TESTS
# ==============================================================================

def test_soil_provenance_exposure():
    """SoilResult must include explicit provenance classification metadata."""
    res = soil_agent.run(n=25, p=45, k=70, crop="tomato", soil_type="sandy")
    assert res.provenance is not None
    assert res.provenance["crop"] == "tomato"
    assert res.provenance["crop_target_provenance"] == "project_calibration_heuristic"
    assert res.provenance["soil_multiplier_provenance"] == "project_calibration_heuristic"
    assert res.provenance["is_authoritative_icar"] is False
    assert "SAU" in res.provenance["guidance_note"]


# ==============================================================================
# 4. API HARDENING & VALIDATION TESTS
# ==============================================================================

def test_api_health_endpoint():
    """GET /health must return HTTP 200 and version 1.1.0."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.1.0"


def test_api_invalid_coordinates_boundary():
    """Coordinates out of range (-90..90, -180..180) must be rejected with 422."""
    res1 = client.post("/api/advisory", json={"lat": 95.0, "lon": 77.0, "n": 20, "p": 20, "k": 20})
    assert res1.status_code == 422

    res2 = client.post("/api/advisory", json={"lat": 12.0, "lon": 190.0, "n": 20, "p": 20, "k": 20})
    assert res2.status_code == 422


def test_api_oversized_upload_rejected():
    """Upload exceeding 5 MB must return HTTP 413."""
    oversized = b"x" * (5 * 1024 * 1024 + 10)
    res = client.post(
        "/api/advisory/upload",
        data={"crop": "Tomato", "n": 20, "p": 20, "k": 20},
        files={"image": ("big.jpg", oversized, "image/jpeg")},
    )
    assert res.status_code == 413


def test_api_invalid_mime_type_rejected():
    """Uploading non-image mime type (e.g. text/plain) must return HTTP 415."""
    res = client.post(
        "/api/advisory/upload",
        data={"crop": "Tomato", "n": 20, "p": 20, "k": 20},
        files={"image": ("script.sh", b"#!/bin/sh\necho hello", "text/plain")},
    )
    assert res.status_code == 415


def test_api_corrupted_image_rejected():
    """Uploading a file claiming to be JPEG but with invalid contents must return HTTP 400."""
    res = client.post(
        "/api/advisory/upload",
        data={"crop": "Tomato", "n": 20, "p": 20, "k": 20},
        files={"image": ("leaf.jpg", b"NOT_A_REAL_JPEG_IMAGE_HEADER", "image/jpeg")},
    )
    assert res.status_code == 400


# ==============================================================================
# 5. NEW E2E SCENARIOS 13 TO 18
# ==============================================================================

def test_e2e_scenario_13_run_trace_retrieval():
    """Scenario 13: Full run trace retrieval via GET /api/runs/{run_id}."""
    post_res = client.post("/api/advisory", json={"crop": "tomato", "n": 20, "p": 40, "k": 60})
    assert post_res.status_code == 200
    run_id = post_res.json()["run_id"]

    get_res = client.get(f"/api/runs/{run_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["run_id"] == run_id
    assert "summary" in data
    assert data["summary"]["run_id"] == run_id
    assert "executed_agents" in data["summary"]
    assert len(data["summary"]["executed_agents"]) >= 5
    assert "data_sources_available" in data["summary"]
    assert "deterministic_rule" in data["summary"]
    assert data["run"]["status"] == "completed"


def test_e2e_scenario_14_feedback_submission():
    """Scenario 14: Submit user feedback on an advisory run and confirm persistence."""
    post_res = client.post("/api/advisory", json={"crop": "potato", "n": 25, "p": 45, "k": 70})
    run_id = post_res.json()["run_id"]

    fb_res = client.post(
        "/api/feedback",
        json={
            "run_id": run_id,
            "farmer_action_taken": "Applied recommended potash top-dressing",
            "outcome_reported": "Tubers matured with good uniformity",
            "comment": "Accurate advisory",
        },
    )
    assert fb_res.status_code == 200
    assert fb_res.json()["status"] == "saved"

    # Verify trace retrieval contains feedback
    trail = client.get(f"/api/runs/{run_id}").json()
    assert len(trail["feedback"]) >= 1
    assert trail["feedback"][0]["farmer_action_taken"] == "Applied recommended potash top-dressing"


def test_e2e_scenario_15_market_unavailable_safe_fallback():
    """Scenario 15: When market is unavailable, system issues safe hold fallback."""
    inputs = {"crop": "rice", "n": 50, "p": 50, "k": 50, "current_price": 0.0, "price_history": []}
    res = client.post("/api/advisory", json=inputs)
    assert res.status_code == 200
    data = res.json()
    assert data["market"]["is_available"] is False
    assert data["market"]["signal"] == "hold"
    assert data["market"]["status"] == "UNAVAILABLE"
    assert data["recommendation"]  # Final recommendation generated safely


def test_e2e_scenario_16_malformed_weather_response(monkeypatch):
    """Scenario 16: Malformed weather provider data safely defaults to neutral score."""
    def fake_malformed_api(lat, lon, timeout=8):
        return {"status": "INVALID", "error": "malformed_json", "hourly": None}

    monkeypatch.setattr(weather_agent, "fetch_forecast", fake_malformed_api)
    inputs = {"crop": "maize", "lat": 15.0, "lon": 75.0, "n": 20, "p": 30, "k": 40}
    res = client.post("/api/advisory", json=inputs)
    assert res.status_code == 200
    data = res.json()
    assert data["weather"]["is_available"] is False
    assert data["weather"]["status"] == "INVALID"
    assert data["recommendation"] == "apply_fertilizer"  # Not blocked or crashed by weather


def test_e2e_scenario_17_demo_mode_full_offline():
    """Scenario 17: Full demo mode offline with caller-supplied context succeeds with 200."""
    inputs = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "soil_type": "alluvial",
        "n": 20,
        "p": 35,
        "k": 50,
        "current_price": 2200.0,
        "price_history": [2000.0, 2100.0, 2200.0],
        "weather_override": {"precip_prob": 0.10, "intensity": 0.05, "duration": 0.0},
        "disease_override": {"predicted_class": "Tomato___healthy", "confidence": 0.95},
    }
    res = client.post("/api/advisory", json=inputs)
    assert res.status_code == 200
    data = res.json()
    assert data["recommendation"] == "apply_fertilizer"
    assert data["market"]["status"] == "DEMO_DATA"
    assert data["weather"]["status"] == "AVAILABLE"


def test_e2e_scenario_18_no_external_api_keys(monkeypatch):
    """Scenario 18: System produces deterministic explanation when no LLM keys exist."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    explainer._CACHE.clear()

    inputs = {"crop": "wheat", "n": 15, "p": 25, "k": 35}
    res = client.post("/api/advisory", json=inputs)
    assert res.status_code == 200
    data = res.json()
    assert "Recommendation:" in data["explanation"]
    assert data["llm"]["provider"] == "deterministic"
    assert data["llm"]["status"] == "deterministic"
    assert data["llm"]["fallback_used"] is False


def test_market_demo_data_provenance_and_summary_availability():
    """Verify market DEMO_DATA provenance, non-authoritative flag, and summary available=True."""
    inputs = {
        "crop": "tomato",
        "current_price": 2200,
        "price_history": [2000, 2100, 2200],
    }
    res = client.post("/api/advisory", json=inputs)
    assert res.status_code == 200
    data = res.json()
    run_id = data["run_id"]

    # Market agent response checks
    assert data["market"]["status"] == "DEMO_DATA"
    assert data["market"]["is_available"] is True
    assert data["market"]["source"] == "caller_provided"
    assert data["market"]["authoritative"] is False

    # Observability run summary checks
    sum_res = client.get(f"/api/runs/{run_id}")
    assert sum_res.status_code == 200
    sum_data = sum_res.json()["summary"]
    assert sum_data["data_sources_available"]["market"] is True
    assert sum_data["market_provenance"]["status"] == "DEMO_DATA"
    assert sum_data["market_provenance"]["authoritative"] is False


def test_market_sell_signal_does_not_override_agronomic_action():
    """Verify that a market SELL signal does not override agronomic crop management in vegetative stage."""
    inputs = {
        "crop": "tomato",
        "growth_stage": "vegetative",
        "n": 10,
        "p": 15,
        "k": 20,
        "current_price": 3000,
        "price_history": [2000, 2500, 3000],  # Strong upward trend -> SELL signal
        "weather_override": {"precip_prob": 0.05, "intensity": 0.0, "duration": 0.0},
    }
    res = client.post("/api/advisory", json=inputs)
    assert res.status_code == 200
    data = res.json()

    # Agronomic recommendation must remain authoritative (not 'sell')
    assert data["recommendation"] in ("apply_fertilizer", "monitor")
    assert data["market"]["signal"] == "sell"
    assert data["agronomic_recommendation"] in ("apply_fertilizer", "monitor")
    assert data["market_recommendation"] == "sell"
    assert "Agronomic:" in data["farm_advisory"]

    # Conflict list must contain market_vs_agronomic_management conflict with 3-part advisory
    conflicts = data.get("resolved_conflicts", [])
    market_conf = [c for c in conflicts if "market" in str(c.get("conflict_type", "")).lower() or "market" in str(c.get("agent_a", "")).lower()]
    assert len(market_conf) > 0
    c = market_conf[0]
    assert "agronomic_recommendation" in c
    assert c["market_recommendation"] == "sell"
    assert "final_advisory" in c
