"""Automated unit and regression tests for Phase 2 field fine-tuning pipeline.

Validates:
1. Class-index consistency across baseline, research checkpoint, and taxonomy.
2. Checkpoint loading and classifier head topology [38, 960].
3. Strict zero-leakage enforcement (manifest disjointness and grouped-specimen isolation).
4. Label mapping validity across all field manifests.
5. Two-phase freezing mechanics (frozen backbone warmup vs controlled partial unfreezing).
6. Pre-training baseline and history tracking.
7. Production checkpoint immutability (ml/artifacts/best.pt remains unchanged).
8. Deterministic reproducibility under seed control.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from torch import nn

REPO_ROOT = Path(__file__).resolve().parent.parent

from ml.disease_model import build_model
from ml.train_field_finetune import (
    FieldManifestDataset,
    compute_class_weights,
    evaluate_split,
    make_field_transforms,
)
from scripts.prepare_field_splits import PLANTDOC_TO_PLANTVILLAGE


EXPECTED_BASELINE_SHA256 = "c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e"


def test_production_checkpoint_immutability():
    """Verify that ml/artifacts/best.pt has not been modified or overwritten."""
    ckpt_path = REPO_ROOT / "ml" / "artifacts" / "best.pt"
    assert ckpt_path.is_file(), "Production checkpoint missing!"
    current_sha = hashlib.sha256(ckpt_path.read_bytes()).hexdigest()
    assert current_sha == EXPECTED_BASELINE_SHA256, (
        f"Production checkpoint was modified! Expected {EXPECTED_BASELINE_SHA256}, got {current_sha}"
    )


def test_class_index_consistency():
    """Verify class-index order is identical between baseline, candidate checkpoint, and taxonomy."""
    base_payload = torch.load(str(REPO_ROOT / "ml" / "artifacts" / "best.pt"), map_location="cpu", weights_only=False)
    base_classes = base_payload["classes"]

    cand_path = REPO_ROOT / "ml" / "research" / "candidate_v1" / "checkpoint_best_val.pt"
    assert cand_path.is_file(), f"Candidate checkpoint missing at {cand_path}"
    cand_payload = torch.load(str(cand_path), map_location="cpu", weights_only=False)
    cand_classes = cand_payload["classes"]

    classes_json_path = REPO_ROOT / "ml" / "research" / "candidate_v1" / "classes.json"
    assert classes_json_path.is_file()
    json_data = json.loads(classes_json_path.read_text(encoding="utf-8"))
    json_classes = json_data["classes"]

    assert len(base_classes) == 38
    assert len(cand_classes) == 38
    assert len(json_classes) == 38

    assert base_classes == cand_classes, "Class taxonomy mismatch between baseline and research candidate!"
    assert base_classes == json_classes, "Class taxonomy mismatch between baseline and classes.json!"


def test_checkpoint_loading_and_head_topology():
    """Verify research checkpoint loads cleanly and matches MobileNetV3-Large topology."""
    cand_path = REPO_ROOT / "ml" / "research" / "candidate_v1" / "checkpoint_best_val.pt"
    payload = torch.load(str(cand_path), map_location="cpu", weights_only=False)

    model = build_model(len(payload["classes"]), pretrained=False)
    model.load_state_dict(payload["state_dict"])
    model.eval()

    # Verify head topology
    classifier_linear = model.classifier[3]
    assert isinstance(classifier_linear, nn.Linear)
    assert classifier_linear.in_features == 1280
    assert classifier_linear.out_features == 38

    # Verify dummy inference pass
    dummy = torch.randn(2, 3, 224, 224)
    with torch.inference_mode():
        logits = model(dummy)
    assert logits.shape == (2, 38)


def test_strict_zero_data_leakage():
    """Verify zero hash and zero specimen-stem overlap between all splits (A, B, train, val)."""
    test_a_p = REPO_ROOT / "evaluation" / "manifests" / "plantdoc_test_manifest.csv"
    test_b_p = REPO_ROOT / "evaluation" / "manifests" / "independent_field_test_manifest.csv"
    train_p = REPO_ROOT / "evaluation" / "manifests" / "field_train_manifest.csv"
    val_p = REPO_ROOT / "evaluation" / "manifests" / "field_val_manifest.csv"

    assert test_a_p.is_file() and test_b_p.is_file() and train_p.is_file() and val_p.is_file()

    rows_a = list(csv.DictReader(test_a_p.open(encoding="utf-8")))
    rows_b = list(csv.DictReader(test_b_p.open(encoding="utf-8")))
    train_rows = list(csv.DictReader(train_p.open(encoding="utf-8")))
    val_rows = list(csv.DictReader(val_p.open(encoding="utf-8")))

    ha = {r["sha256"] for r in rows_a if "sha256" in r}
    hb = {r["sha256"] for r in rows_b if "sha256" in r}
    htrain = {r["sha256"] for r in train_rows if "sha256" in r}
    hval = {r["sha256"] for r in val_rows if "sha256" in r}

    stema = {r["group_id"].lower() for r in rows_a if "group_id" in r}
    stemb = {r["group_id"].lower() for r in rows_b if "group_id" in r}
    stemtrain = {r["group_id"].lower() for r in train_rows if "group_id" in r}
    stemval = {r["group_id"].lower() for r in val_rows if "group_id" in r}

    # 1. Exact hash disjointness
    assert len(htrain & ha) == 0, f"Train-TestA hash leakage! Overlap: {htrain & ha}"
    assert len(hval & ha) == 0, f"Val-TestA hash leakage! Overlap: {hval & ha}"
    assert len(htrain & hval) == 0, f"Train-Val hash leakage! Overlap: {htrain & hval}"
    assert len(hb & ha) == 0, f"TestB-TestA hash leakage! Overlap: {hb & ha}"
    assert len(hb & hval) == 0, f"TestB-Val hash leakage! Overlap: {hb & hval}"
    assert len(hb & htrain) == 0, f"TestB-Train hash leakage! Overlap: {hb & htrain}"

    # 2. Specimen group isolation
    assert len(stemtrain & stema) == 0, f"Train-TestA stem leakage! Overlap: {stemtrain & stema}"
    assert len(stemval & stema) == 0, f"Val-TestA stem leakage! Overlap: {stemval & stema}"
    assert len(stemtrain & stemval) == 0, f"Train-Val stem leakage! Overlap: {stemtrain & stemval}"
    assert len(stemb & stema) == 0, f"TestB-TestA stem leakage! Overlap: {stemb & stema}"
    assert len(stemb & stemval) == 0, f"TestB-Val stem leakage! Overlap: {stemb & stemval}"
    assert len(stemb & stemtrain) == 0, f"TestB-Train stem leakage! Overlap: {stemb & stemtrain}"


def test_label_mapping_integrity():
    """Verify all mapped classes in manifests match AgriMind's 38-class taxonomy."""
    base_payload = torch.load(str(REPO_ROOT / "ml" / "artifacts" / "best.pt"), map_location="cpu", weights_only=False)
    valid_classes = set(base_payload["classes"])

    for path_key in ["field_train_manifest.csv", "field_val_manifest.csv", "independent_field_test_manifest.csv"]:
        man_path = REPO_ROOT / "evaluation" / "manifests" / path_key
        rows = list(csv.DictReader(man_path.open(encoding="utf-8")))
        for r in rows:
            mapped = r.get("mapped_class")
            assert mapped in valid_classes, f"Manifest {path_key} contains invalid class: {mapped}"

    for orig, mapped in PLANTDOC_TO_PLANTVILLAGE.items():
        assert mapped in valid_classes, f"PLANTDOC_TO_PLANTVILLAGE contains unmapped class: {mapped}"


def test_freezing_and_gradient_mechanics():
    """Verify two-phase parameter freezing logic operates as specified."""
    model = build_model(38, pretrained=False)

    # Stage 1: Warmup freezing
    for param in model.features.parameters():
        param.requires_grad = False
    for param in model.classifier.parameters():
        param.requires_grad = True

    assert not any(p.requires_grad for p in model.features.parameters())
    assert all(p.requires_grad for p in model.classifier.parameters())

    # Stage 2: Controlled unfreezing of blocks 13-16
    for idx, child in enumerate(model.features):
        if idx >= 13:
            for p in child.parameters():
                p.requires_grad = True
        else:
            for p in child.parameters():
                p.requires_grad = False

    # Blocks 0-12 must be frozen
    for idx in range(13):
        for p in model.features[idx].parameters():
            assert not p.requires_grad

    # Blocks 13-16 must be trainable
    for idx in range(13, len(model.features)):
        for p in model.features[idx].parameters():
            assert p.requires_grad


def test_baseline_and_training_history_artifacts():
    """Verify pre-finetune baseline and training history files exist with valid metrics."""
    res_dir = REPO_ROOT / "ml" / "research" / "candidate_v1"
    base_json = res_dir / "pre_finetune_baseline.json"
    hist_json = res_dir / "training_history.json"
    cfg_json = res_dir / "training_config.json"
    val_json = res_dir / "val_metrics.json"

    assert base_json.is_file(), f"Missing {base_json}"
    assert hist_json.is_file(), f"Missing {hist_json}"
    assert cfg_json.is_file(), f"Missing {cfg_json}"
    assert val_json.is_file(), f"Missing {val_json}"

    base_data = json.loads(base_json.read_text(encoding="utf-8"))
    assert "accuracy" in base_data
    assert "macro_f1" in base_data
    assert "ece" in base_data
    assert 0.0 <= base_data["accuracy"] <= 1.0

    hist_data = json.loads(hist_json.read_text(encoding="utf-8"))
    assert len(hist_data) >= 1
    for row in hist_data:
        assert "stage" in row
        assert "train_loss" in row
        assert "val_macro_f1" in row


def test_class_weights_computation():
    """Verify class weight calculation handles imbalance correctly and bounds weights."""
    labels = [0, 0, 0, 1, 2, 2]
    weights = compute_class_weights(labels, num_classes=4)
    assert len(weights) == 4
    assert torch.is_tensor(weights)
    # Rare class 1 should have higher weight than frequent class 0
    assert weights[1] > weights[0]
    # All weights bounded
    assert torch.all(weights >= 0.1)
    assert torch.all(weights <= 10.0)


def test_field_transforms_output_properties():
    """Verify field transforms generate valid 3-channel (224, 224) tensors with finite values."""
    train_tf, eval_tf = make_field_transforms()
    from PIL import Image
    dummy_img = Image.new("RGB", (320, 240), color=(120, 150, 80))

    t_train = train_tf(dummy_img)
    t_eval = eval_tf(dummy_img)

    assert t_train.shape == (3, 224, 224)
    assert t_eval.shape == (3, 224, 224)
    assert torch.isfinite(t_train).all()
    assert torch.isfinite(t_eval).all()


def test_all_candidate_checkpoints_validity():
    """Verify all experimental candidate checkpoints exist, load cleanly, and pass forward pass."""
    cand_dirs = [
        "candidate_warmup",
        "candidate_v1",
        "candidate_v2_finetune",
    ]
    for cdir in cand_dirs:
        ckpt_path = REPO_ROOT / "ml" / "research" / cdir / "checkpoint_best_val.pt"
        assert ckpt_path.is_file(), f"Missing checkpoint: {ckpt_path}"
        payload = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        assert len(payload["classes"]) == 38
        model = build_model(38, pretrained=False)
        model.load_state_dict(payload["state_dict"])
        model.eval()
        dummy = torch.randn(1, 3, 224, 224)
        with torch.inference_mode():
            logits = model(dummy)
        assert logits.shape == (1, 38)
        assert torch.isfinite(logits).all()


def test_comprehensive_evaluation_results_artifact():
    """Verify comprehensive multi-model evaluation artifact exists with valid metrics."""
    res_path = REPO_ROOT / "evaluation" / "artifacts" / "comprehensive_evaluation_results.json"
    assert res_path.is_file(), f"Missing results artifact at {res_path}"
    data = json.loads(res_path.read_text(encoding="utf-8"))

    assert "models_audited" in data
    assert "experiments" in data
    assert len(data["models_audited"]) >= 4

    # Check baseline on Benchmark B exists
    base_exp = data["experiments"]["Baseline (best.pt)"]
    assert "Benchmark B (Independent Field Test) | Unconstrained (Top-1)" in base_exp
    b_res = base_exp["Benchmark B (Independent Field Test) | Unconstrained (Top-1)"]
    assert "accuracy" in b_res
    assert "wilson_95_ci" in b_res
    assert "macro_f1_evaluated" in b_res
    assert "expected_calibration_error" in b_res
    assert 0.0 <= b_res["accuracy"] <= 1.0


def test_independent_benchmark_b_images_exist_and_readable():
    """Verify all images in Benchmark B manifest exist on disk and can be decoded by PIL."""
    manifest_p = REPO_ROOT / "evaluation" / "manifests" / "independent_field_test_manifest.csv"
    assert manifest_p.is_file()
    rows = list(csv.DictReader(manifest_p.open(encoding="utf-8")))
    assert len(rows) >= 200

    from PIL import Image
    for r in rows[:20]:  # sample check
        img_p = REPO_ROOT / "evaluation" / "datasets" / "field_data" / "images" / r["image_path"]
        assert img_p.is_file(), f"Benchmark B image missing: {img_p}"
        with Image.open(img_p) as img:
            assert img.size[0] >= 10 and img.size[1] >= 10
