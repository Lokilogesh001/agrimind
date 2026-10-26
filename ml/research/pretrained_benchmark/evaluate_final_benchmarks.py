"""Approved Final Evaluation on Untouched Benchmark Splits.

Protocol:
- Evaluates frozen candidate checkpoints ONCE on the locked benchmark test splits:
  1. Benchmark A (PlantDoc Test Split): evaluation/manifests/plantdoc_test_manifest.csv (N=236)
  2. Benchmark B (Independent Field Test): evaluation/manifests/independent_field_test_manifest.csv (N=221)
- Candidates compared:
  1. Production Baseline (MobileNetV3-Large, best.pt)
  2. AgriMind Stage D Champion (MobileNetV3-Large, checkpoint_best_val.pt)
  3. DINOv2-Small (Linear Probe)
  4. DINOv2-Small LoRA Champion (dinov2_lora_r4_b4_best.pt)
  5. Hierarchical DINOv2 (Unconstrained Prediction & Crop-Oracle Diagnostic)
- Reports Top-1 Accuracy, Wilson 95% CI, Macro-F1 (eval classes and 38 classes),
  ECE, Cross-Crop Error Rate, and Confidence Gating (@0.60 threshold).
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
from PIL import Image
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
import torch
import torch.nn as nn
from torchvision import transforms

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.evaluate_disease_model import compute_ece, compute_wilson_ci
from ml.disease_model import IMAGENET_MEAN, IMAGENET_STD, build_model, inference_transform
from ml.research.pretrained_benchmark.train_dinov2_lora import DINOv2LoRAClassifier
from ml.research.pretrained_benchmark.train_hierarchical_model import HierarchicalDINOv2
from ml.research.unified_optimization.experiment_runner import extract_crop_name

MANIFEST_PLANTDOC = REPO_ROOT / "evaluation" / "manifests" / "plantdoc_test_manifest.csv"
ROOT_PLANTDOC = REPO_ROOT / "evaluation" / "datasets" / "plantdoc_test" / "images"

MANIFEST_INDEP = REPO_ROOT / "evaluation" / "manifests" / "independent_field_test_manifest.csv"
ROOT_INDEP = REPO_ROOT / "evaluation" / "datasets" / "field_data" / "images"

OUTPUT_DIR = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "final_benchmark_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_dataset(manifest_path: Path, data_root: Path, class_to_idx: dict[str, int]) -> list[dict[str, Any]]:
    samples = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rel = row.get("image_path") or row.get("relative_path")
            cls = row.get("mapped_class") or row.get("class_name")
            p = data_root / rel
            if not p.is_file():
                raise FileNotFoundError(f"Missing file: {p}")
            samples.append({
                "path": p,
                "class_name": cls,
                "class_idx": class_to_idx[cls],
            })
    return samples


def evaluate_predictions(
    y_true: list[int],
    y_pred: list[int],
    all_probs: np.ndarray,
    classes: list[str],
    latencies: list[float],
) -> dict[str, Any]:
    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    total = len(y_true_arr)
    correct = int(np.sum(y_true_arr == y_pred_arr))
    acc = float(correct / total)
    wilson = compute_wilson_ci(correct, total, confidence=0.95)

    eval_classes = sorted(list(set(y_true)))
    macro_f1 = float(f1_score(y_true_arr, y_pred_arr, labels=eval_classes, average="macro", zero_division=0))
    macro_f1_38 = float(f1_score(y_true_arr, y_pred_arr, labels=list(range(len(classes))), average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true_arr, y_pred_arr, labels=eval_classes, average="weighted", zero_division=0))
    prec, rec, _, _ = precision_recall_fscore_support(y_true_arr, y_pred_arr, labels=eval_classes, average="macro", zero_division=0)

    ece_dict = compute_ece(all_probs, y_pred_arr, y_true_arr, n_bins=10)
    ece_val = float(ece_dict["expected_calibration_error"])

    cross_crop_errors = sum(
        1 for yt, yp in zip(y_true, y_pred) if yt != yp and extract_crop_name(classes[yt]) != extract_crop_name(classes[yp])
    )
    cross_crop_rate = float(cross_crop_errors / total)

    comp_score = round(
        0.40 * macro_f1 + 0.30 * acc + 0.15 * max(0.0, 1.0 - ece_val) + 0.15 * max(0.0, 1.0 - cross_crop_rate), 4
    )

    confs = np.max(all_probs, axis=1)
    passed_gate = confs >= 0.60
    act_count = int(np.sum(passed_gate))
    act_correct = int(np.sum(passed_gate & (y_true_arr == y_pred_arr)))
    act_prec = float(act_correct / max(act_count, 1))
    safely_rejected = int(np.sum((~passed_gate) & (y_true_arr != y_pred_arr)))
    filter_eff = float(safely_rejected / max(total - correct, 1))

    return {
        "accuracy": round(acc, 4),
        "wilson_95_ci": wilson,
        "macro_f1": round(macro_f1, 4),
        "macro_f1_38": round(macro_f1_38, 4),
        "macro_precision": round(float(prec), 4),
        "macro_recall": round(float(rec), 4),
        "weighted_f1": round(weighted_f1, 4),
        "expected_calibration_error": round(ece_val, 4),
        "composite_score": comp_score,
        "cross_crop_error_rate": round(cross_crop_rate, 4),
        "actionable_precision": round(act_prec, 4),
        "safety_filtering_efficiency": round(filter_eff, 4),
        "mean_latency_ms": round(float(np.mean(latencies)), 2),
        "total_samples": total,
        "evaluated_classes_count": len(eval_classes),
    }


def main():
    print("=" * 70)
    print(" AGRIMIND — FROZEN FINAL BENCHMARK EVALUATION ON UNTOUCHED SPLITS")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load classes
    fc_dir = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "feature_cache"
    with open(fc_dir / "classes.json", "r", encoding="utf-8") as f:
        cls_data = json.load(f)
    classes = cls_data["classes"] if isinstance(cls_data, dict) and "classes" in cls_data else cls_data
    class_to_idx = {c: i for i, c in enumerate(classes)}

    crop_names = sorted(list(set(extract_crop_name(c) for c in classes)))
    crop_to_idx = {c: i for i, c in enumerate(crop_names)}
    disease_to_crop = {i: crop_to_idx[extract_crop_name(c)] for i, c in enumerate(classes)}
    crop_to_diseases = {i: [] for i in range(len(crop_names))}
    for d_idx, c_idx in disease_to_crop.items():
        crop_to_diseases[c_idx].append(d_idx)

    # Preload benchmark datasets
    print("\n[DATASETS] Preloading benchmark test sets into memory...")
    pdoc_samples = load_dataset(MANIFEST_PLANTDOC, ROOT_PLANTDOC, class_to_idx)
    indep_samples = load_dataset(MANIFEST_INDEP, ROOT_INDEP, class_to_idx)
    print(f"--> Benchmark A (PlantDoc Test): {len(pdoc_samples)} images")
    print(f"--> Benchmark B (Independent Field Test): {len(indep_samples)} images")

    # Load candidate models
    print("\n[MODELS] Loading frozen candidate models...")

    # 1. Baseline MobileNetV3
    base_model = build_model(len(classes), pretrained=False)
    base_model.load_state_dict(torch.load(REPO_ROOT / "ml" / "artifacts" / "best.pt", map_location="cpu", weights_only=False)["state_dict"])
    base_model.to(device).eval()

    # 2. Stage D Finalist MobileNetV3
    stage_d_model = build_model(len(classes), pretrained=False)
    stage_d_model.load_state_dict(torch.load(REPO_ROOT / "ml" / "research" / "unified_optimization" / "finalist_model" / "checkpoint_best_val.pt", map_location="cpu", weights_only=False)["state_dict"])
    stage_d_model.to(device).eval()

    # 3. DINOv2 LoRA Champion
    lora_ckpt = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "lora_experiments" / "checkpoints" / "dinov2_lora_r4_b4_best.pt"
    lora_data = torch.load(lora_ckpt, map_location="cpu", weights_only=False)
    lora_model = DINOv2LoRAClassifier(num_classes=len(classes), lora_rank=4, num_lora_blocks=4)
    lora_model.load_state_dict(lora_data["state_dict"])
    lora_model.to(device).eval()

    # Transforms
    mob_trans = inference_transform()
    dino_trans = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])

    benchmarks = {
        "Benchmark_A_PlantDoc_Test": pdoc_samples,
        "Benchmark_B_Independent_Field_Test": indep_samples,
    }

    full_results = {}

    for b_name, b_samples in benchmarks.items():
        print(f"\n{'='*70}\n EVALUATING: {b_name} (N={len(b_samples)})\n{'='*70}")
        full_results[b_name] = {}

        # Preload PIL images
        pil_images = [Image.open(s["path"]).convert("RGB") for s in b_samples]
        y_true = [s["class_idx"] for s in b_samples]

        # Candidate 1: Production Baseline MobileNetV3
        print("--> Evaluating 1. Production Baseline (MobileNetV3-Large)...")
        y_pred = []
        probs = []
        lats = []
        for img in pil_images:
            tensor = mob_trans(img).unsqueeze(0).to(device)
            t0 = time.perf_counter()
            with torch.no_grad():
                out = base_model(tensor)
                p = torch.softmax(out, dim=1).squeeze(0).cpu().numpy()
            lats.append((time.perf_counter() - t0) * 1000.0)
            y_pred.append(int(np.argmax(p)))
            probs.append(p)
        full_results[b_name]["Production_Baseline_MobileNetV3"] = evaluate_predictions(y_true, y_pred, np.vstack(probs), classes, lats)

        # Candidate 2: Stage D Finalist MobileNetV3
        print("--> Evaluating 2. Stage D Champion (MobileNetV3-Large)...")
        y_pred = []
        probs = []
        lats = []
        for img in pil_images:
            tensor = mob_trans(img).unsqueeze(0).to(device)
            t0 = time.perf_counter()
            with torch.no_grad():
                out = stage_d_model(tensor)
                p = torch.softmax(out, dim=1).squeeze(0).cpu().numpy()
            lats.append((time.perf_counter() - t0) * 1000.0)
            y_pred.append(int(np.argmax(p)))
            probs.append(p)
        full_results[b_name]["Stage_D_Champion_MobileNetV3"] = evaluate_predictions(y_true, y_pred, np.vstack(probs), classes, lats)

        # Candidate 3: DINOv2 LoRA Champion (Unconstrained)
        print("--> Evaluating 3. DINOv2-Small LoRA Champion (Unconstrained)...")
        y_pred = []
        probs = []
        lats = []
        raw_logits_list = []
        for img in pil_images:
            tensor = dino_trans(img).unsqueeze(0).to(device)
            t0 = time.perf_counter()
            with torch.no_grad():
                out = lora_model(tensor)
                p = torch.softmax(out, dim=1).squeeze(0).cpu().numpy()
                raw = out.squeeze(0).cpu().numpy()
            lats.append((time.perf_counter() - t0) * 1000.0)
            y_pred.append(int(np.argmax(p)))
            probs.append(p)
            raw_logits_list.append(raw)
        full_results[b_name]["DINOv2_Small_LoRA_Unconstrained"] = evaluate_predictions(y_true, y_pred, np.vstack(probs), classes, lats)

        # Candidate 4: DINOv2 LoRA + Crop-Oracle Diagnostic
        print("--> Evaluating 4. DINOv2-Small LoRA (Crop-Oracle Diagnostic)...")
        y_pred_oracle = []
        probs_oracle = []
        for yt, raw in zip(y_true, raw_logits_list):
            c_true = disease_to_crop[yt]
            valid_d = crop_to_diseases[c_true]
            masked = np.full(len(classes), -1e9)
            for d in valid_d:
                masked[d] = raw[d]
            p = np.exp(masked - np.max(masked))
            p = p / np.sum(p)
            y_pred_oracle.append(int(np.argmax(p)))
            probs_oracle.append(p)
        full_results[b_name]["DINOv2_Small_LoRA_Crop_Oracle"] = evaluate_predictions(y_true, y_pred_oracle, np.vstack(probs_oracle), classes, lats)

        # Print summary for this benchmark
        print(f"\n[SUMMARY: {b_name}]")
        for m_name, m_dict in full_results[b_name].items():
            print(f"  {m_name:<38} | Acc: {m_dict['accuracy']*100:6.2f}% | F1: {m_dict['macro_f1']:.4f} | ECE: {m_dict['expected_calibration_error']:.4f} | Score: {m_dict['composite_score']:.4f} | Cross-Crop Err: {m_dict['cross_crop_error_rate']*100:5.2f}%")

    # Save to JSON
    json_path = OUTPUT_DIR / "untouched_benchmarks_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "benchmarks": full_results,
            },
            f,
            indent=2,
        )
    print(f"\n--> Saved untouched benchmark results to: {json_path}")


if __name__ == "__main__":
    main()
