"""FastAPI Endpoints, Security Guards & Observability Verification Suite.

Mandatory Requirements (Phase F & H):
1. Public endpoints: GET /health, GET /health/model, GET /api/crops, GET /api/location/search.
2. Advisory execution: POST /api/advisory returns structured response, DSS, market provenance, and audit trail.
3. Request validation: Bounds checking for lat/lon, non-negative prices, and non-empty location strings.
4. Security boundaries:
   - ENVIRONMENT=production blocks overrides and returns 403 on /api/internal/test-advisory.
   - Public advisory blocks synthetic overrides in production.
5. Image upload endpoint (POST /api/advisory/upload):
   - Valid JPEG accepted.
   - Missing, 0-byte, invalid format, and wrong mime-type safely rejected.
6. Observability and persistence:
   - GET /api/runs/{run_id} returns logged agent calls, decisions, and conflicts.
   - POST /api/feedback saves farmer feedback into SQLite observability database.
"""
from __future__ import annotations

import io
import os
from unittest.mock import patch
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from api.main import app
from observability import database as obs

client = TestClient(app)


@pytest.fixture(autouse=True)
def init_test_db():
    obs.init_db()


# ==============================================================================
# 1. Health & Metadata Endpoints
# ==============================================================================
def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "agrimind-api"


def test_model_health_endpoint():
    res = client.get("/health/model")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "ready" in data
    assert "checkpoint_path" in data


def test_crops_registry_endpoint():
    res = client.get("/api/crops")
    assert res.status_code == 200
    data = res.json()
    assert "crops" in data
    assert "categories" in data
    assert "stages" in data
    assert len(data["crops"]) > 0


def test_location_search_endpoint():
    res = client.get("/api/location/search?q=Madurai")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data


# ==============================================================================
# 2. Advisory Execution & Serialization
# ==============================================================================
def test_post_advisory_valid_request():
    payload = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "lat": 9.9252,
        "lon": 78.1198,
        "n": 30.0,
        "p": 45.0,
        "k": 60.0,
        "soil_type": "red_soil",
        "current_price": 2200.0,
        "price_history": [2100.0, 2150.0, 2200.0],
    }
    res = client.post("/api/advisory", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "recommendation" in data
    assert "decision_stability_score" in data
    assert "evidence_quality_score" in data
    assert "market" in data
    assert data["market"]["status"] == "USER_SUPPLIED"
    assert data["market"]["observed_price"] is None
    assert data["market"]["benchmark_price"] == 2200.0
    assert "audit" in data
    assert "run_id" in data


# ==============================================================================
# 3. Request Validation & Bounds Checking
# ==============================================================================
def test_advisory_invalid_coordinates():
    res = client.post("/api/advisory", json={"lat": 150.0, "lon": 78.0, "crop": "Tomato"})
    assert res.status_code == 422


def test_advisory_negative_price():
    res = client.post("/api/advisory", json={"current_price": -50.0, "crop": "Tomato"})
    assert res.status_code == 422


def test_advisory_empty_location_string():
    res = client.post("/api/advisory", json={"location_name": "   ", "crop": "Tomato"})
    assert res.status_code == 422


# ==============================================================================
# 4. Security Boundaries & Production Environment Guards
# ==============================================================================
def test_production_blocks_internal_test_endpoint():
    """In production, /api/internal/test-advisory MUST return 403 Forbidden."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        res = client.post("/api/internal/test-advisory", json={"crop": "Tomato"})
        assert res.status_code == 403
        assert "disabled in production" in res.json()["detail"]


def test_production_blocks_synthetic_overrides():
    """In production, public /api/advisory MUST reject synthetic overrides."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        res = client.post(
            "/api/advisory",
            json={"crop": "Tomato", "weather_override": {"rainfall_risk": 0.9}},
        )
        assert res.status_code == 422
        assert "forbidden in production" in str(res.json())


def test_development_without_flag_blocks_synthetic_overrides():
    """In development without ALLOW_TEST_OVERRIDES=true, overrides are rejected."""
    with patch.dict(os.environ, {"ENVIRONMENT": "development", "ALLOW_TEST_OVERRIDES": "false"}):
        res = client.post(
            "/api/advisory",
            json={"crop": "Tomato", "weather_override": {"rainfall_risk": 0.9}},
        )
        assert res.status_code == 422
        assert "disabled in this environment" in str(res.json())


# ==============================================================================
# 5. Leaf Image Upload Endpoint & Validation
# ==============================================================================
def _create_test_image_bytes(format: str = "JPEG", size=(100, 100)) -> bytes:
    img = Image.new("RGB", size, color=(0, 128, 0))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def test_advisory_upload_valid_image():
    img_bytes = _create_test_image_bytes("JPEG")
    files = {"image": ("leaf.jpg", img_bytes, "image/jpeg")}
    data = {"crop": "Tomato", "growth_stage": "vegetative", "current_price": "2000"}

    res = client.post("/api/advisory/upload", data=data, files=files)
    assert res.status_code == 200
    resp_data = res.json()
    assert "recommendation" in resp_data
    assert "disease" in resp_data


def test_advisory_upload_missing_image():
    res = client.post("/api/advisory/upload", data={"crop": "Tomato"})
    assert res.status_code == 400
    assert "image is required" in res.json()["detail"].lower()


def test_advisory_upload_empty_image():
    files = {"image": ("empty.jpg", b"", "image/jpeg")}
    res = client.post("/api/advisory/upload", data={"crop": "Tomato"}, files=files)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_advisory_upload_invalid_file_content():
    files = {"image": ("leaf.jpg", b"NOT_AN_IMAGE_FILE", "image/jpeg")}
    res = client.post("/api/advisory/upload", data={"crop": "Tomato"}, files=files)
    assert res.status_code == 400
    assert "not a valid image" in res.json()["detail"].lower()


def test_advisory_upload_disallowed_mime_type():
    files = {"image": ("script.sh", b"echo hello", "text/plain")}
    res = client.post("/api/advisory/upload", data={"crop": "Tomato"}, files=files)
    assert res.status_code == 415


# ==============================================================================
# 6. Observability & Run Audit Trails
# ==============================================================================
def test_observability_run_audit_trail_and_feedback():
    # 1. Run advisory
    payload = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "n": 25.0,
        "p": 45.0,
        "k": 70.0,
        "soil_type": "red_soil",
    }
    adv_res = client.post("/api/advisory", json=payload)
    assert adv_res.status_code == 200
    run_id = adv_res.json()["run_id"]

    # 2. Retrieve execution trail
    trail_res = client.get(f"/api/runs/{run_id}")
    assert trail_res.status_code == 200
    trail = trail_res.json()
    assert "run_id" in trail
    assert "agent_logs" in trail
    assert len(trail["agent_logs"]) >= 3  # at least weather, soil, advisory logged

    # 3. Submit farmer feedback
    fb_payload = {
        "run_id": run_id,
        "farmer_action_taken": "Applied recommended organic mulch",
        "outcome_reported": "Crop recovered successfully",
        "comment": "Accurate guidance",
    }
    fb_res = client.post("/api/feedback", json=fb_payload)
    assert fb_res.status_code == 200
    assert fb_res.json()["status"] == "saved"
