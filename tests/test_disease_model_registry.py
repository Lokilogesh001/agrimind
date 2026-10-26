"""Tests for Disease Model Registry, DINOv2 default status, and rollback behavior."""
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from api.main import app
from ml.model_registry import (
    get_model,
    resolve_model_name,
    get_registry_status,
    MODEL_PRODUCTION,
    MODEL_DINOV2_LORA,
    DEFAULT_MODEL_NAME,
)
from agents.disease_agent import run as run_disease_agent, get_disease_model_health
from orchestrator.graph import run_advisory
from observability import database as obs

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_IMAGE = REPO_ROOT / "evaluation" / "datasets" / "field_data" / "images" / "Tomato Early blight leaf" / "126689-004-D622CD2F.jpg"


@pytest.fixture(autouse=True)
def init_test_db():
    obs.init_db()


def test_dinov2_default_is_active(monkeypatch):
    """Verify that unconfigured model registry strictly defaults to DINOv2 LoRA."""
    monkeypatch.delenv("DISEASE_MODEL_BACKBONE", raising=False)
    assert DEFAULT_MODEL_NAME == MODEL_DINOV2_LORA
    resolved = resolve_model_name(None)
    assert resolved == MODEL_DINOV2_LORA

    default_model = get_model()
    assert hasattr(default_model, "predict")
    assert default_model.model_architecture == "DINOv2-Small-LoRA"


def test_explicit_production_and_rollback_override(monkeypatch):
    """Verify that explicit production or rollback selection chooses MobileNetV3."""
    # 1. Via environment variable
    monkeypatch.setenv("DISEASE_MODEL_BACKBONE", "production")
    assert resolve_model_name(None) == MODEL_PRODUCTION

    prod_model = get_model()
    assert hasattr(prod_model, "predict")
    assert prod_model.model.__class__.__name__ == "MobileNetV3"

    # 2. Via explicit parameter and aliases
    assert resolve_model_name("production") == MODEL_PRODUCTION
    assert resolve_model_name("mobilenet") == MODEL_PRODUCTION
    assert resolve_model_name("mobilenetv3") == MODEL_PRODUCTION
    assert resolve_model_name("rollback") == MODEL_PRODUCTION
    assert resolve_model_name("baseline") == MODEL_PRODUCTION


def test_explicit_dinov2_override():
    """Test alias normalization for DINOv2 selection and rejection of unknown models."""
    assert resolve_model_name("dinov2") == MODEL_DINOV2_LORA
    assert resolve_model_name("dinov2_lora") == MODEL_DINOV2_LORA
    assert resolve_model_name("dinov2-small") == MODEL_DINOV2_LORA
    assert resolve_model_name("lora") == MODEL_DINOV2_LORA
    assert resolve_model_name("default") == MODEL_DINOV2_LORA

    # Disallow invalid model names
    with pytest.raises(ValueError, match="Unsupported disease model"):
        resolve_model_name("resnet50_unknown")


def test_registry_health_and_api_endpoints(monkeypatch):
    """Verify /health/model and /health/models endpoints reflect DINOv2 default and rollback."""
    monkeypatch.delenv("DISEASE_MODEL_BACKBONE", raising=False)

    with TestClient(app) as client:
        # Default endpoint reports active model (DINOv2-Small-LoRA)
        res_default = client.get("/health/model")
        assert res_default.status_code == 200
        data_default = res_default.json()
        assert data_default["status"] == "READY"
        assert data_default["model_name"] == "DINOv2-Small-LoRA"
        assert data_default["model_version"] == "r4_b4"

        # Explicit query for production rollback baseline
        res_prod = client.get("/health/model?model=production")
        assert res_prod.status_code == 200
        data_prod = res_prod.json()
        assert data_prod["status"] == "READY"
        assert data_prod["architecture"] == "MobileNetV3-Large"

        # Multi-model registry health status
        res_multi = client.get("/health/models")
        assert res_multi.status_code == 200
        data_multi = res_multi.json()
        assert data_multi["active_default_model"] == MODEL_DINOV2_LORA
        assert data_multi["is_dinov2_default"] is True
        assert data_multi["is_production_default"] is False
        assert MODEL_DINOV2_LORA in data_multi["models"]
        assert MODEL_PRODUCTION in data_multi["models"]


def test_api_default_dispatches_to_dinov2(monkeypatch):
    """Verify that unconfigured /api/advisory/upload dispatches to DINOv2 LoRA by default."""
    if not SAMPLE_IMAGE.is_file():
        pytest.skip("Sample field image not found.")

    monkeypatch.delenv("DISEASE_MODEL_BACKBONE", raising=False)

    with TestClient(app) as client:
        with open(SAMPLE_IMAGE, "rb") as f:
            # Unconfigured request (no disease_model specified)
            res = client.post(
                "/api/advisory/upload",
                data={
                    "crop": "Tomato",
                    "growth_stage": "vegetative",
                    "current_price": "2000",
                },
                files={"image": ("leaf.jpg", f, "image/jpeg")},
            )
        assert res.status_code == 200, f"Error: {res.text}"
        data = res.json()
        assert data["disease_gate"]["status"] == "AVAILABLE"
        assert data["disease_gate"]["model_architecture"] == "DINOv2-Small-LoRA"
        assert data["disease_gate"]["model_version"] == "r4_b4"


def test_api_explicit_rollback_dispatches_to_mobilenet():
    """Verify that requesting disease_model='production' dispatches to MobileNetV3."""
    if not SAMPLE_IMAGE.is_file():
        pytest.skip("Sample field image not found.")

    with TestClient(app) as client:
        with open(SAMPLE_IMAGE, "rb") as f:
            res = client.post(
                "/api/advisory/upload",
                data={
                    "crop": "Tomato",
                    "growth_stage": "vegetative",
                    "current_price": "2000",
                    "disease_model": "production",
                },
                files={"image": ("leaf.jpg", f, "image/jpeg")},
            )
        assert res.status_code == 200, f"Error: {res.text}"
        data = res.json()
        assert data["disease_gate"]["status"] == "AVAILABLE"
        assert data["disease_gate"]["model_architecture"] == "MobileNetV3-Large"


def test_api_invalid_model_name_raises_error():
    """Verify that invalid model names reject without silent fallback."""
    if not SAMPLE_IMAGE.is_file():
        pytest.skip("Sample field image not found.")

    with TestClient(app) as client:
        with open(SAMPLE_IMAGE, "rb") as f:
            res = client.post(
                "/api/advisory/upload",
                data={
                    "crop": "Tomato",
                    "growth_stage": "vegetative",
                    "disease_model": "invalid_model_xyz",
                },
                files={"image": ("leaf.jpg", f, "image/jpeg")},
            )
        assert res.status_code == 422
        assert "Unsupported disease model" in res.text


def test_missing_backbone_never_substitutes_mobilenet():
    """Verify that missing/failed DINOv2 model returns MODEL_UNAVAILABLE without silent substitution."""
    if not SAMPLE_IMAGE.is_file():
        pytest.skip("Sample field image not found.")

    # Simulate missing checkpoint or backbone error
    with patch("agents.disease_agent.get_model", side_effect=RuntimeError("Simulated missing backbone weights")):
        res = run_disease_agent(
            image_path=str(SAMPLE_IMAGE),
            model_name=MODEL_DINOV2_LORA,
        )
        assert res.status == "MODEL_UNAVAILABLE"
        assert res.predicted_class is None
        assert res.actionable is False
        assert "Simulated missing backbone weights" in res.findings


def test_crop_constrained_and_unconstrained_predictions():
    """Verify that crop-constrained and unconstrained modes remain distinct."""
    if not SAMPLE_IMAGE.is_file():
        pytest.skip("Sample field image not found.")

    # 1. Unconstrained
    res_flat = run_disease_agent(
        image_path=str(SAMPLE_IMAGE),
        model_name=MODEL_DINOV2_LORA,
        selected_crop="",
    )
    assert res_flat.status == "AVAILABLE"
    assert res_flat.crop_aware_mode is False
    assert res_flat.crop_concordance is None

    # 2. Crop-constrained
    res_crop = run_disease_agent(
        image_path=str(SAMPLE_IMAGE),
        model_name=MODEL_DINOV2_LORA,
        selected_crop="Tomato",
    )
    assert res_crop.status == "AVAILABLE"
    assert res_crop.crop_aware_mode is True
    assert res_crop.crop_concordance is not None
    assert 0.0 <= res_crop.crop_concordance <= 1.0


def test_observability_records_actual_model_version(monkeypatch):
    """Verify that decision provenance and agent logs record the exact model that executed."""
    if not SAMPLE_IMAGE.is_file():
        pytest.skip("Sample field image not found.")

    monkeypatch.delenv("DISEASE_MODEL_BACKBONE", raising=False)

    payload = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "image_path": str(SAMPLE_IMAGE),
    }
    state = run_advisory(payload)
    assert state.disease.model_architecture == "DINOv2-Small-LoRA"
    assert state.disease.model_version == "r4_b4"

    # Trail validation
    trail = obs.get_run_trail(state.run_id)
    assert trail is not None
    disease_logs = [log for log in trail.get("agent_logs", []) if log["agent"] == "disease"]
    assert len(disease_logs) > 0
    assert disease_logs[0]["output"]["model_architecture"] == "DINOv2-Small-LoRA"
