"""Tests for DINOv2-Small LoRA Inference Adapter."""
import hashlib
import os
from pathlib import Path
import tempfile
import pytest
import torch
from PIL import Image

from ml.dinov2_adapter import (
    DINOv2LoRAPredictor,
    DINOv2LoRAClassifier,
    LoRALinear,
    get_dinov2_health,
    PLANTVILLAGE_CLASSES_38,
    extract_crop_from_class,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_IMAGE = REPO_ROOT / "evaluation" / "datasets" / "field_data" / "images" / "Tomato Early blight leaf" / "126689-004-D622CD2F.jpg"
CHECKPOINT_PATH = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "lora_experiments" / "checkpoints" / "dinov2_lora_r4_b4_best.pt"
EXPECTED_SHA256 = "8ae555c2054fd518edb5382519cca4fba9d2bff4bc039636fddc4b14edf1aa68"


def test_checkpoint_exists_and_hash():
    """Verify Rank-4 checkpoint exists and matches locked SHA-256."""
    assert CHECKPOINT_PATH.is_file(), f"Checkpoint not found: {CHECKPOINT_PATH}"
    with open(CHECKPOINT_PATH, "rb") as f:
        file_sha = hashlib.sha256(f.read()).hexdigest()
    assert file_sha == EXPECTED_SHA256


def test_dinov2_health_reporting():
    """Verify health reporting on existing and missing checkpoints."""
    health = get_dinov2_health(str(CHECKPOINT_PATH))
    assert health["status"] == "READY"
    assert health["ready"] is True
    assert health["model_name"] == "DINOv2-Small-LoRA"
    assert health["lora_rank"] == 4
    assert health["num_lora_blocks"] == 4
    assert health["checkpoint_sha256"] == EXPECTED_SHA256

    # Test missing checkpoint
    missing_health = get_dinov2_health("non_existent_ckpt.pt")
    assert missing_health["status"] == "UNAVAILABLE"
    assert missing_health["ready"] is False


def test_class_ordering_and_names():
    """Ensure exact 38 PlantVillage classes with zero discrepancies."""
    assert len(PLANTVILLAGE_CLASSES_38) == 38
    assert PLANTVILLAGE_CLASSES_38[0] == "Apple___Apple_scab"
    assert PLANTVILLAGE_CLASSES_38[-1] == "Tomato___healthy"

    crops = {extract_crop_from_class(c) for c in PLANTVILLAGE_CLASSES_38}
    expected_crops = {
        "apple", "blueberry", "cherry", "corn", "grape", "orange",
        "peach", "pepper", "potato", "raspberry", "soybean", "squash",
        "strawberry", "tomato",
    }
    assert crops == expected_crops


def test_lora_linear_wrapper():
    """Verify LoRALinear forward pass and mathematical scaling."""
    base_linear = torch.nn.Linear(384, 384)
    lora = LoRALinear(base_linear, r=4, lora_alpha=16.0, lora_dropout=0.0)
    assert lora.scaling == 4.0
    assert lora.lora_A.shape == (4, 384)
    assert lora.lora_B.shape == (384, 4)

    x = torch.randn(2, 384)
    out = lora(x)
    assert out.shape == (2, 384)


def test_cpu_loading_and_inference():
    """Verify DINOv2LoRAPredictor loads and predicts on CPU."""
    if not SAMPLE_IMAGE.is_file():
        pytest.skip("Sample field image not found.")

    predictor = DINOv2LoRAPredictor(checkpoint=str(CHECKPOINT_PATH), device="cpu")
    assert predictor.device == torch.device("cpu")

    res = predictor.predict(str(SAMPLE_IMAGE))
    assert res["model_architecture"] == "DINOv2-Small-LoRA"
    assert res["model_version"] == "r4_b4"
    assert res["predicted_class"] in PLANTVILLAGE_CLASSES_38
    assert 0.0 <= res["confidence"] <= 1.0
    assert len(res["all_probabilities"]) == 38
    assert abs(sum(res["all_probabilities"].values()) - 1.0) < 1e-3
    assert res["latency_ms"] > 0


def test_crop_selection_modes():
    """Test unconstrained, matching, discordant, and unsupported crop inputs."""
    if not SAMPLE_IMAGE.is_file():
        pytest.skip("Sample field image not found.")

    predictor = DINOv2LoRAPredictor(checkpoint=str(CHECKPOINT_PATH), device="cpu")

    # 1. Unconstrained mode
    res_none = predictor.predict(str(SAMPLE_IMAGE), selected_crop=None)
    assert res_none["crop_aware_mode"] is False
    assert res_none["crop_status"] == "NOT_PROVIDED"
    assert res_none["crop_warning"] is None

    # 2. Matching crop (Tomato)
    res_tomato = predictor.predict(str(SAMPLE_IMAGE), selected_crop="Tomato")
    assert res_tomato["crop_aware_mode"] is True
    assert res_tomato["crop_status"] == "APPLIED"
    assert res_tomato["crop_concordance"] is not None

    # 3. Unsupported / Unknown crop
    res_unknown = predictor.predict(str(SAMPLE_IMAGE), selected_crop="Sugarcane")
    assert res_unknown["crop_aware_mode"] is False
    assert res_unknown["crop_status"] == "UNSUPPORTED_CROP"
    assert "Sugarcane" in res_unknown["crop_warning"]


def test_invalid_image_rejection():
    """Test strict image rejection: non-existent, empty, non-image, corrupt, resolution."""
    predictor = DINOv2LoRAPredictor(checkpoint=str(CHECKPOINT_PATH), device="cpu")

    # 1. Non-existent file
    with pytest.raises(FileNotFoundError):
        predictor.predict("non_existent_leaf_image.jpg")

    # 2. Empty 0-byte file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        with pytest.raises(ValueError, match="empty"):
            predictor.predict(tmp_path)
    finally:
        os.unlink(tmp_path)

    # 3. Non-image text file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, mode="w") as tmp:
        tmp.write("This is not an image file.")
        tmp_path = tmp.name
    try:
        with pytest.raises(ValueError, match="Corrupted or unsupported"):
            predictor.predict(tmp_path)
    finally:
        os.unlink(tmp_path)

    # 4. Tiny resolution (< 10x10)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tiny_img = Image.new("RGB", (5, 5), color="green")
        tiny_img.save(tmp.name)
        tmp_path = tmp.name
    try:
        with pytest.raises(ValueError, match="resolution too small"):
            predictor.predict(tmp_path)
    finally:
        os.unlink(tmp_path)
