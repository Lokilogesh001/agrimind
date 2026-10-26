"""Automated Tests for Disease Classifier Evaluation Pipeline & Status Model.

Validates:
1. Exact 38-class index mapping in checkpoint.
2. Preprocessing consistency (resolution, color space, ImageNet normalization).
3. Missing or corrupted checkpoint handling.
4. Empty dataset and corrupted image rejection.
5. Invalid, unknown, and unmapped labels handling.
6. Duplicate detection and grouped-specimen leakage checks.
7. Partial class coverage and Wilson 95% confidence interval calculations.
8. Confusion matrix dimensions (38x38) and per-class support metrics.
9. Calibration (ECE) and confidence statistics correctness.
10. Safe status transitions (BLOCKED_PENDING_DATA, BLOCKED_INVALID_DATA,
    PARTIAL_CROSS_DATASET_EVALUATION, CROSS_DATASET_EVALUATION_COMPLETE).
11. Prevention of fabricated or stale metrics.
12. Deterministic reproducibility across repeated evaluations.
13. Clean handling of unavailable external datasets.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
from PIL import Image
import pytest
import torch

from evaluation.evaluate_disease_model import (
    IndependentDataset,
    check_train_test_leakage,
    compute_confidence_statistics,
    compute_ece,
    compute_wilson_ci,
    run_evaluation,
)
from ml.disease_model import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    build_model,
    inference_transform,
)


EXPECTED_38_CLASSES = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Blueberry___healthy",
    "Cherry_(including_sour)___Powdery_mildew",
    "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy",
    "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Peach___Bacterial_spot",
    "Peach___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]


def test_exact_class_index_mapping():
    """Verify best.pt contains exactly 38 classes in exact alphabetical order."""
    ckpt_path = Path("ml/artifacts/best.pt")
    assert ckpt_path.is_file(), "Production checkpoint best.pt must exist"

    payload = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    classes = payload.get("classes")
    assert isinstance(classes, list)
    assert len(classes) == 38, f"Expected 38 classes, found {len(classes)}"
    assert classes == EXPECTED_38_CLASSES, "Class list in checkpoint must match expected 38-class order"

    class_to_idx = payload.get("class_to_idx")
    if class_to_idx:
        for idx, cname in enumerate(classes):
            assert class_to_idx[cname] == idx


def test_preprocessing_consistency():
    """Verify inference preprocessing conforms to ImageNet normalization and 224x224 RGB resolution."""
    transform = inference_transform()
    assert transform is not None

    # Create synthetic test PIL image
    img = Image.new("RGB", (640, 480), color=(120, 200, 80))
    tensor = transform(img)

    assert isinstance(tensor, torch.Tensor)
    assert tensor.shape == (3, 224, 224), f"Expected shape (3, 224, 224), got {tensor.shape}"
    assert tensor.dtype == torch.float32

    # Check normalization: ImageNet mean ~ 0.48, std ~ 0.22, normalized values should span positive and negative
    assert tensor.min() < 0.0
    assert tensor.max() > 0.0


def test_missing_or_corrupted_checkpoint(tmp_path: Path):
    """Verify evaluator reports CHECKPOINT_UNAVAILABLE on missing or corrupted checkpoint."""
    out_dir = tmp_path / "artifacts"

    # Missing checkpoint
    res_missing = run_evaluation(
        checkpoint=str(tmp_path / "non_existent.pt"),
        output_dir=str(out_dir),
    )
    assert res_missing["status"] == "CHECKPOINT_UNAVAILABLE"
    assert "not found" in res_missing["error"].lower()

    # Corrupt checkpoint
    corrupt_pt = tmp_path / "corrupt.pt"
    corrupt_pt.write_bytes(b"NOT_A_VALID_PYTORCH_FILE_HEADER")
    res_corrupt = run_evaluation(
        checkpoint=str(corrupt_pt),
        output_dir=str(out_dir),
    )
    assert res_corrupt["status"] == "CHECKPOINT_UNAVAILABLE"
    assert "failed" in res_corrupt["error"].lower()


def test_empty_dataset_and_corrupt_images(tmp_path: Path):
    """Verify evaluator rejects empty manifests or all-corrupt image datasets with BLOCKED_INVALID_DATA."""
    out_dir = tmp_path / "artifacts"
    data_dir = tmp_path / "images"
    data_dir.mkdir(parents=True)

    # 1. Empty manifest
    empty_manifest = tmp_path / "empty_manifest.csv"
    empty_manifest.write_text("image_path,mapped_class\n", encoding="utf-8")

    res_empty = run_evaluation(
        checkpoint="ml/artifacts/best.pt",
        data_dir=str(data_dir),
        manifest=str(empty_manifest),
        output_dir=str(out_dir),
    )
    assert res_empty["status"] == "BLOCKED_INVALID_DATA"
    assert "zero valid" in res_empty["error"].lower()

    # 2. Corrupt images in manifest
    corrupt_file = data_dir / "bad_image.jpg"
    corrupt_file.write_bytes(b"GARBAGE_BYTES_NOT_AN_IMAGE")
    corrupt_manifest = tmp_path / "corrupt_manifest.csv"
    corrupt_manifest.write_text(
        "image_path,mapped_class\nbad_image.jpg,Tomato___Early_blight\n",
        encoding="utf-8",
    )

    res_corrupt = run_evaluation(
        checkpoint="ml/artifacts/best.pt",
        data_dir=str(data_dir),
        manifest=str(corrupt_manifest),
        output_dir=str(out_dir),
    )
    assert res_corrupt["status"] == "BLOCKED_INVALID_DATA"
    assert res_corrupt["invalid_samples_count"] == 1


def test_invalid_unknown_and_unmapped_labels(tmp_path: Path):
    """Verify unmapped and unknown labels are safely excluded and audited."""
    data_dir = tmp_path / "images"
    data_dir.mkdir(parents=True)

    img = Image.new("RGB", (224, 224), color=(50, 150, 50))
    img_path = data_dir / "sample.jpg"
    img.save(img_path)

    # Manifest with UNMAPPED and out-of-taxonomy class
    manifest_csv = tmp_path / "unmapped_manifest.csv"
    manifest_csv.write_text(
        "image_path,mapped_class,original_label\n"
        "sample.jpg,UNMAPPED,Paddy_Blast\n"
        "sample.jpg,Rice___Bacterial_blight,Bacterial_Blight\n",
        encoding="utf-8",
    )

    class_to_idx = {name: i for i, name in enumerate(EXPECTED_38_CLASSES)}
    ds = IndependentDataset(
        root=data_dir,
        manifest=manifest_csv,
        class_to_idx=class_to_idx,
    )

    assert len(ds) == 0, "No samples should be eligible when all labels are unmapped or unknown"
    assert len(ds.unmapped_samples) == 2
    assert "not in model 38-class taxonomy" in ds.unmapped_samples[0]["reason"]


def test_duplicate_detection_and_grouped_specimen_leakage(tmp_path: Path):
    """Verify train/test leakage audit catches exact path duplicates and grouped-leaf stems."""
    train_manifest = tmp_path / "train.csv"
    test_manifest = tmp_path / "test.csv"

    # Train has tomato leaf 01 and 02
    train_manifest.write_text(
        "image_path\n"
        "Tomato___Early_blight/plant_01_viewA.jpg\n"
        "Tomato___Early_blight/plant_02_viewA.jpg\n",
        encoding="utf-8",
    )

    # Test has exact duplicate (plant_01_viewA.jpg) and grouped-specimen leakage (plant_02_viewB.jpg)
    test_manifest.write_text(
        "image_path\n"
        "Tomato___Early_blight/plant_01_viewA.jpg\n"
        "Tomato___Early_blight/plant_02_viewB.jpg\n",
        encoding="utf-8",
    )

    leakage = check_train_test_leakage(train_manifest, test_manifest)
    assert leakage["leakage_check_performed"] is True
    assert leakage["has_leakage"] is True
    assert leakage["exact_file_overlap_count"] == 1
    assert leakage["grouped_leaf_overlap_count"] == 2


def test_wilson_confidence_interval_correctness():
    """Verify Wilson score confidence interval returns valid mathematical bounds."""
    # 0 out of 100
    ci_zero = compute_wilson_ci(0, 100)
    assert ci_zero["lower"] == 0.0
    assert 0.0 < ci_zero["upper"] < 0.05

    # 50 out of 100
    ci_half = compute_wilson_ci(50, 100)
    assert 0.40 < ci_half["lower"] < 0.50
    assert 0.50 < ci_half["upper"] < 0.60

    # 100 out of 100
    ci_full = compute_wilson_ci(100, 100)
    assert 0.95 < ci_zero["lower"] <= 1.0 or ci_full["lower"] > 0.95
    assert ci_full["upper"] == 1.0


def test_partial_class_coverage_and_status(tmp_path: Path):
    """Verify evaluator transitions to PARTIAL_CROSS_DATASET_EVALUATION when < 38 classes are evaluated."""
    out_dir = tmp_path / "artifacts"
    data_dir = tmp_path / "images"
    data_dir.mkdir(parents=True)

    # Create 3 synthetic test images for 2 classes
    img1 = Image.new("RGB", (224, 224), color=(100, 150, 50))
    img2 = Image.new("RGB", (224, 224), color=(150, 100, 50))
    img3 = Image.new("RGB", (224, 224), color=(50, 100, 150))
    img1.save(data_dir / "t1.jpg")
    img2.save(data_dir / "t2.jpg")
    img3.save(data_dir / "c1.jpg")

    manifest = tmp_path / "partial_manifest.csv"
    manifest.write_text(
        "image_path,mapped_class,group_id\n"
        "t1.jpg,Tomato___Early_blight,group_1\n"
        "t2.jpg,Tomato___Early_blight,group_1\n"
        "c1.jpg,Corn_(maize)___Common_rust_,group_2\n",
        encoding="utf-8",
    )

    results = run_evaluation(
        checkpoint="ml/artifacts/best.pt",
        data_dir=str(data_dir),
        manifest=str(manifest),
        output_dir=str(out_dir),
    )

    assert results["status"] == "PARTIAL_CROSS_DATASET_EVALUATION"
    assert results["class_coverage"]["classes_evaluated_count"] == 2
    assert results["class_coverage"]["classes_total_count"] == 38
    assert results["class_coverage"]["coverage_percentage"] == round((2 / 38) * 100, 2)
    assert len(results["class_coverage"]["unrepresented_classes"]) == 36
    assert results["sample_counts"]["unique_specimen_groups"] == 2
    assert "Tomato___Early_blight" in results["class_coverage"]["evaluated_classes"]
    assert "Corn_(maize)___Common_rust_" in results["class_coverage"]["evaluated_classes"]


def test_confusion_matrix_and_per_class_metrics(tmp_path: Path):
    """Verify 38x38 confusion matrix shape and per-class support metrics."""
    out_dir = tmp_path / "artifacts"
    data_dir = tmp_path / "images"
    data_dir.mkdir(parents=True)

    img = Image.new("RGB", (224, 224), color=(100, 100, 100))
    img.save(data_dir / "sample.jpg")

    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "image_path,mapped_class\nsample.jpg,Apple___Apple_scab\n",
        encoding="utf-8",
    )

    results = run_evaluation(
        checkpoint="ml/artifacts/best.pt",
        data_dir=str(data_dir),
        manifest=str(manifest),
        output_dir=str(out_dir),
    )

    assert results["confusion_matrix_shape"] == [38, 38]
    cm_csv = Path(results["confusion_matrix_csv"])
    assert cm_csv.is_file()

    # Per-class metrics dictionary must contain all 38 classes
    per_class = results["per_class_metrics"]
    assert len(per_class) == 38
    assert per_class["Apple___Apple_scab"]["support"] == 1
    assert per_class["Apple___Apple_scab"]["evaluated"] is True
    assert per_class["Apple___Black_rot"]["support"] == 0
    assert per_class["Apple___Black_rot"]["evaluated"] is False


def test_calibration_ece_computation():
    """Verify ECE and reliability bins computation."""
    probs = np.array([
        [0.9, 0.1],
        [0.8, 0.2],
        [0.7, 0.3],
        [0.6, 0.4],
    ])
    preds = np.array([0, 0, 0, 1])
    truths = np.array([0, 0, 1, 1])

    ece_dict = compute_ece(probs, preds, truths, n_bins=5)
    assert "expected_calibration_error" in ece_dict
    assert 0.0 <= ece_dict["expected_calibration_error"] <= 1.0
    assert len(ece_dict["bins"]) == 5


def test_confidence_statistics():
    """Verify confidence statistics calculations."""
    confs = np.array([0.95, 0.85, 0.55, 0.40, 0.90])
    stats = compute_confidence_statistics(confs)

    assert stats["min"] == 0.40
    assert stats["max"] == 0.95
    assert stats["mean"] == round(float(np.mean(confs)), 4)
    # 2 out of 5 values (0.55, 0.40) are < 0.60 -> fraction = 0.40
    assert stats["fraction_below_gate_0_60"] == 0.40


def test_reproducibility_of_repeated_evaluation(tmp_path: Path):
    """Verify repeated evaluation on fixed dataset produces deterministic bit-for-bit metrics."""
    data_dir = tmp_path / "images"
    data_dir.mkdir(parents=True)

    img = Image.new("RGB", (224, 224), color=(80, 180, 80))
    img.save(data_dir / "deterministic.jpg")

    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "image_path,mapped_class\ndeterministic.jpg,Tomato___healthy\n",
        encoding="utf-8",
    )

    out_1 = tmp_path / "run1"
    out_2 = tmp_path / "run2"

    res1 = run_evaluation(
        checkpoint="ml/artifacts/best.pt",
        data_dir=str(data_dir),
        manifest=str(manifest),
        output_dir=str(out_1),
        seed=42,
    )
    res2 = run_evaluation(
        checkpoint="ml/artifacts/best.pt",
        data_dir=str(data_dir),
        manifest=str(manifest),
        output_dir=str(out_2),
        seed=42,
    )

    assert res1["metrics"] == res2["metrics"]
    assert res1["calibration"] == res2["calibration"]
    assert res1["confidence_statistics"] == res2["confidence_statistics"]


def test_proper_handling_of_unavailable_external_dataset(tmp_path: Path):
    """Verify evaluator reports BLOCKED_PENDING_DATA when external dataset is absent."""
    out_dir = tmp_path / "out"
    res = run_evaluation(
        checkpoint="ml/artifacts/best.pt",
        data_dir=None,
        manifest=None,
        output_dir=str(out_dir),
    )
    assert res["status"] == "BLOCKED_PENDING_DATA"
    assert res["model_ready"] is True
    assert (out_dir / "disease_evaluation_status.json").is_file()


def test_disease_error_analysis_artifacts_and_consistency():
    """Verify Phase 1 disease error analysis JSON and Markdown artifacts for mathematical integrity."""
    import json
    repo_root = Path(__file__).resolve().parent.parent
    json_path = repo_root / "evaluation" / "artifacts" / "disease_error_analysis.json"
    md_path = repo_root / "docs" / "DISEASE_ERROR_ANALYSIS.md"

    assert json_path.is_file(), f"Missing artifact: {json_path}"
    assert md_path.is_file(), f"Missing artifact: {md_path}"

    data = json.loads(json_path.read_text(encoding="utf-8"))
    meta = data["audit_metadata"]
    metrics = data["headline_metrics"]
    gate = data["confidence_gate_audit"]
    decomp = data["error_decomposition"]

    # Checkpoint integrity
    assert meta["checkpoint_sha256"] == "c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e"
    assert meta["total_evaluated_samples"] == 236
    assert meta["evaluated_classes_count"] == 27
    assert meta["unrepresented_classes_count"] == 11

    # Exact arithmetic closure
    assert metrics["total_correct"] + metrics["total_incorrect"] == 236
    assert metrics["total_correct"] == 60
    assert metrics["total_incorrect"] == 176
    assert round(metrics["top1_accuracy"], 4) == 0.2542

    # Error decomposition closure
    assert decomp["cross_crop_errors_count"] + decomp["within_crop_errors_count"] == decomp["total_errors"]
    assert decomp["total_errors"] == 176
    assert decomp["cross_crop_errors_count"] == 114
    assert decomp["within_crop_errors_count"] == 62

    # Confidence gate closure
    assert gate["total_actionable"] + gate["total_abstentions"] == 236
    assert gate["actionable_correct"] + gate["false_confident_predictions"] == gate["total_actionable"]
    assert gate["safely_rejected_errors"] + gate["suppressed_correct_predictions"] == gate["total_abstentions"]
    assert gate["safely_rejected_errors"] + gate["false_confident_predictions"] == 176
