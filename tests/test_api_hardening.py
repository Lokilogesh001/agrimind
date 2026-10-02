"""API boundary tests for the public advisory and image-upload endpoints."""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from PIL import Image

from api.main import app


def _valid_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (120, 160, 90)).save(buf, format="JPEG")
    return buf.getvalue()


def test_public_request_does_not_accept_server_image_path():
    payload = {
        "n": 20, "p": 20, "k": 20,
        "image_path": "C:/Windows/System32/config/SAM",
    }
    response = TestClient(app).post("/api/advisory", json=payload)
    # Pydantic v2 ignores unknown fields by default, so this must not become
    # part of the internal request model. The endpoint may still fail later
    # because no disease override/image is supplied; it must never use the path.
    assert response.status_code == 422


def test_upload_requires_an_image():
    response = TestClient(app).post("/api/advisory/upload", data={"n": 20, "p": 20, "k": 20})
    assert response.status_code == 400
    assert "required" in response.json()["detail"].lower()


def test_upload_rejects_non_image_content():
    response = TestClient(app).post(
        "/api/advisory/upload",
        data={"n": 20, "p": 20, "k": 20},
        files={"image": ("leaf.jpg", b"not-an-image", "image/jpeg")},
    )
    assert response.status_code == 400
    assert "valid image" in response.json()["detail"].lower()


def test_upload_accepts_valid_jpeg(monkeypatch):
    # Replace the expensive graph execution with a tiny deterministic response;
    # this test is about the upload boundary, not model accuracy.
    from orchestrator.state import AgriMindState

    state = AgriMindState(run_id="api-test")
    state.final_recommendation = "monitor"
    state.confidence = 0.5

    monkeypatch.setattr("api.main.run_advisory", lambda inputs: state)
    monkeypatch.setattr("api.main.explain", lambda state, evidence: "ok")
    monkeypatch.setattr("api.main.obs.get_run_trail", lambda run_id: {})

    response = TestClient(app).post(
        "/api/advisory/upload",
        data={"n": 20, "p": 20, "k": 20},
        files={"image": ("leaf.jpg", _valid_jpeg(), "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["recommendation"] == "monitor"
