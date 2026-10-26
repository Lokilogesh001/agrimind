"""Comprehensive Scientific Evaluation Suite for AgriMind Disease Classifiers.

Executes controlled, reproducible evaluations across multiple models and benchmarks:
- Models: Baseline (best.pt), Candidate Warmup, Candidate V1, Candidate V2 Finetune
- Benchmarks:
  * Benchmark A: Locked Legacy PlantDoc Test Set (236 images, 27 classes)
  * Benchmark B: Pre-declared Independent Field Test Set (221 images, 28 classes)
- Modes:
  * Unconstrained (Standard top-1 38-class inference)
  * Crop-Constrained (Hierarchical logit masking using user/crop-agent crop context)
- Metrics:
  * Top-1 Accuracy with Wilson 95% Confidence Interval
  * Macro-F1 (evaluated classes and all 38 classes)
  * Weighted-F1, Precision, Recall
  * Expected Calibration Error (ECE) and MCE
  * Confidence threshold (0.60) audit: actionability, false-confident error rate
  * Cross-crop vs within-crop error breakdown
  * 38x38 Confusion Matrix
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
from PIL import Image
import torch
from torchvision import transforms

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.disease_model import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    build_model,
)
from evaluation.evaluate_disease_model import (
    compute_wilson_ci,
    compute_ece,
)


def locate_image(rel_path: str) -> Path:
    candidates = [
        REPO_ROOT / "evaluation" / "datasets" / "plantdoc_test" / "images" / rel_path,
        REPO_ROOT / "evaluation" / "datasets" / "field_data" / "images" / rel_path,
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(f"Could not locate image: {rel_path}")


def get_crop_from_class(cname: str) -> str:
    raw_crop = cname.split("___")[0]
    return raw_crop.replace("_(maize)", "").replace(",_bell", "").replace("_", " ").strip().lower()


def evaluate_model_on_manifest(
    model: torch.nn.Module,
    classes: list[str],
    class_to_idx: dict[str, int],
    manifest_path: str | Path,
    transform,
    device: torch.device,
    crop_constrained: bool = False,
) -> dict[str, Any]:
    man_path = Path(manifest_path)
    rows = list(csv.DictReader(man_path.open(encoding="utf-8")))

    num_classes = len(classes)
    y_true = []
    y_pred = []
    y_conf = []
    all_probs = []

    cm = np.zeros((num_classes, num_classes), dtype=int)
    samples_detail = []

    model.eval()
    with torch.inference_mode():
        for idx, row in enumerate(rows):
            img_path = locate_image(row["image_path"])
            true_class = row["mapped_class"]
            true_idx = class_to_idx[true_class]
            true_crop = get_crop_from_class(true_class)

            with Image.open(img_path) as img:
                img_tensor = transform(img.convert("RGB")).unsqueeze(0).to(device)

            logits = model(img_tensor).cpu().numpy().copy()

            if crop_constrained:
                for c_i, c_name in enumerate(classes):
                    c_crop = get_crop_from_class(c_name)
                    if true_crop not in c_crop and c_crop not in true_crop:
                        logits[0, c_i] = -1e9

            exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
            probs = (exp_logits / np.sum(exp_logits, axis=1, keepdims=True))[0]

            pred_idx = int(np.argmax(probs))
            conf = float(probs[pred_idx])
            pred_class = classes[pred_idx]
            pred_crop = get_crop_from_class(pred_class)

            y_true.append(true_idx)
            y_pred.append(pred_idx)
            y_conf.append(conf)
            all_probs.append(probs)

            cm[true_idx, pred_idx] += 1

            is_correct = (true_idx == pred_idx)
            is_crop_match = (true_crop == pred_crop)

            samples_detail.append({
                "sample_id": idx + 1,
                "image_path": row["image_path"],
                "true_class": true_class,
                "true_crop": true_crop,
                "pred_class": pred_class,
                "pred_crop": pred_crop,
                "confidence": round(conf, 4),
                "is_correct": is_correct,
                "crop_match": is_crop_match,
                "actionable_gate_0_60": conf >= 0.60,
            })

    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    y_conf_arr = np.array(y_conf)
    all_probs_arr = np.array(all_probs)

    total_evaluated = len(y_true_arr)
    total_correct = int(np.sum(y_true_arr == y_pred_arr))
    acc = float(total_correct / total_evaluated) if total_evaluated > 0 else 0.0
    wilson_ci = compute_wilson_ci(total_correct, total_evaluated, confidence=0.95)

    eval_classes_idx = sorted(list(set(y_true)))

    # Per-class metrics
    per_class = {}
    f1s_eval = []
    for idx in range(num_classes):
        cname = classes[idx]
        tp = int(cm[idx, idx])
        fn = int(np.sum(cm[idx, :]) - tp)
        fp = int(np.sum(cm[:, idx]) - tp)
        supp = int(np.sum(cm[idx, :]))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        if idx in eval_classes_idx:
            f1s_eval.append(f1)

        per_class[cname] = {
            "support": supp,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
        }

    macro_f1_evaluated = float(np.mean(f1s_eval)) if f1s_eval else 0.0
    all_f1s = [per_class[c]["f1_score"] for c in classes]
    macro_f1_all = float(np.mean(all_f1s))

    # Weighted F1
    supports = [per_class[classes[i]]["support"] for i in eval_classes_idx]
    weighted_f1 = float(np.sum(np.array(f1s_eval) * np.array(supports)) / total_evaluated) if total_evaluated > 0 else 0.0

    # Calibration
    ece_info = compute_ece(all_probs_arr, y_pred_arr, y_true_arr, n_bins=10)

    # 0.60 Gate Audit
    actionable_mask = y_conf_arr >= 0.60
    total_actionable = int(np.sum(actionable_mask))
    actionable_correct = int(np.sum((y_true_arr == y_pred_arr) & actionable_mask))
    false_confident = int(np.sum((y_true_arr != y_pred_arr) & actionable_mask))

    suppressed_mask = ~actionable_mask
    total_suppressed = int(np.sum(suppressed_mask))
    safely_rejected = int(np.sum((y_true_arr != y_pred_arr) & suppressed_mask))
    suppressed_correct = int(np.sum((y_true_arr == y_pred_arr) & suppressed_mask))

    # Error decomposition
    errors = [s for s in samples_detail if not s["is_correct"]]
    cross_crop_errors = [s for s in errors if not s["crop_match"]]
    within_crop_errors = [s for s in errors if s["crop_match"]]

    return {
        "manifest": str(man_path),
        "crop_constrained": crop_constrained,
        "sample_count": total_evaluated,
        "classes_evaluated_count": len(eval_classes_idx),
        "accuracy": round(acc, 4),
        "wilson_95_ci": [wilson_ci["lower"], wilson_ci["upper"]],
        "macro_f1_evaluated": round(macro_f1_evaluated, 4),
        "macro_f1_all_38": round(macro_f1_all, 4),
        "weighted_f1": round(weighted_f1, 4),
        "mean_confidence": round(float(np.mean(y_conf_arr)), 4),
        "expected_calibration_error": ece_info["expected_calibration_error"],
        "maximum_calibration_error": ece_info.get("maximum_calibration_error", 0.0),
        "gate_0_60_audit": {
            "total_actionable": total_actionable,
            "actionable_accuracy": round(float(actionable_correct / total_actionable), 4) if total_actionable > 0 else 0.0,
            "false_confident_errors": false_confident,
            "total_suppressed": total_suppressed,
            "abstention_rate": round(float(total_suppressed / total_evaluated), 4) if total_evaluated > 0 else 0.0,
            "safely_rejected_errors": safely_rejected,
            "suppressed_correct": suppressed_correct,
            "safety_filtering_efficiency": round(float(safely_rejected / len(errors)), 4) if errors else 1.0,
        },
        "error_decomposition": {
            "total_errors": len(errors),
            "cross_crop_errors": len(cross_crop_errors),
            "cross_crop_percentage": round((len(cross_crop_errors) / len(errors)) * 100, 2) if errors else 0.0,
            "within_crop_errors": len(within_crop_errors),
            "within_crop_percentage": round((len(within_crop_errors) / len(errors)) * 100, 2) if errors else 0.0,
        },
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
    }


def run_comprehensive_matrix():
    device = torch.device("cpu")
    eval_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])

    models_to_test = [
        ("Baseline (best.pt)", REPO_ROOT / "ml" / "artifacts" / "best.pt"),
        ("Candidate Warmup", REPO_ROOT / "ml" / "research" / "candidate_warmup" / "checkpoint_best_val.pt"),
        ("Candidate V1 (Partial Finetune)", REPO_ROOT / "ml" / "research" / "candidate_v1" / "checkpoint_best_val.pt"),
        ("Candidate V2 (Cosine Finetune)", REPO_ROOT / "ml" / "research" / "candidate_v2_finetune" / "checkpoint_best_val.pt"),
        ("RTX3050 V1 (Field Finetune)", REPO_ROOT / "ml" / "research" / "rtx3050_v1" / "checkpoint_best_val.pt"),
    ]

    benchmarks = [
        ("Benchmark A (Locked PlantDoc Test)", REPO_ROOT / "evaluation" / "manifests" / "plantdoc_test_manifest.csv"),
        ("Benchmark B (Independent Field Test)", REPO_ROOT / "evaluation" / "manifests" / "independent_field_test_manifest.csv"),
    ]

    all_results: dict[str, Any] = {
        "metadata": {
            "title": "AgriMind Comprehensive Disease Classifier Multi-Model Benchmark",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "target_metric": ">= 85.0% Top-1 Accuracy on Independent Field Benchmark",
        },
        "models_audited": {},
        "experiments": {},
    }

    # Record model hashes
    for mname, mpath in models_to_test:
        raw_b = mpath.read_bytes()
        all_results["models_audited"][mname] = {
            "path": str(mpath),
            "sha256": hashlib.sha256(raw_b).hexdigest(),
            "size_bytes": len(raw_b),
        }

    print("=" * 80)
    print("AGRIMIND COMPREHENSIVE MULTI-MODEL EXPERIMENT EVALUATION")
    print("=" * 80)

    for mname, mpath in models_to_test:
        print(f"\n---> Evaluating Model: {mname}")
        payload = torch.load(str(mpath), map_location="cpu", weights_only=False)
        classes = payload["classes"]
        class_to_idx = payload.get("class_to_idx") or {c: i for i, c in enumerate(classes)}

        model = build_model(len(classes), pretrained=False).to(device)
        model.load_state_dict(payload["state_dict"])

        all_results["experiments"][mname] = {}

        for bname, bmanifest in benchmarks:
            for constrained in [False, True]:
                mode_label = "Crop-Constrained (Rule C)" if constrained else "Unconstrained (Top-1)"
                exp_key = f"{bname} | {mode_label}"

                print(f"  Running: {exp_key}...")
                metrics = evaluate_model_on_manifest(
                    model=model,
                    classes=classes,
                    class_to_idx=class_to_idx,
                    manifest_path=bmanifest,
                    transform=eval_transform,
                    device=device,
                    crop_constrained=constrained,
                )
                all_results["experiments"][mname][exp_key] = metrics

                print(f"    Acc: {metrics['accuracy']*100:.2f}% (95% CI: [{metrics['wilson_95_ci'][0]*100:.1f}%, {metrics['wilson_95_ci'][1]*100:.1f}%]) | "
                      f"Macro-F1: {metrics['macro_f1_evaluated']:.4f} | ECE: {metrics['expected_calibration_error']:.4f} | "
                      f"Cross-Crop Err: {metrics['error_decomposition']['cross_crop_percentage']:.1f}%")

    # Export main results JSON
    out_dir = REPO_ROOT / "evaluation" / "artifacts" / "rtx3050_comparison"
    out_dir.mkdir(parents=True, exist_ok=True)
    res_path = out_dir / "comprehensive_evaluation_results.json"
    res_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\n[DONE] Saved comprehensive evaluation results: {res_path}")

    # Export Confusion Matrices for key runs
    base_classes = all_results["experiments"]["Baseline (best.pt)"]["Benchmark A (Locked PlantDoc Test) | Unconstrained (Top-1)"]["per_class"]
    classes_list = list(base_classes.keys())

    # 1. Benchmark A Baseline
    cm_a_base = all_results["experiments"]["Baseline (best.pt)"]["Benchmark A (Locked PlantDoc Test) | Unconstrained (Top-1)"]["confusion_matrix"]
    with open(out_dir / "benchmark_a_baseline_confusion_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["True\\Pred"] + classes_list)
        for i, row in enumerate(cm_a_base):
            w.writerow([classes_list[i]] + row)

    # 2. Benchmark B Baseline
    cm_b_base = all_results["experiments"]["Baseline (best.pt)"]["Benchmark B (Independent Field Test) | Unconstrained (Top-1)"]["confusion_matrix"]
    with open(out_dir / "benchmark_b_baseline_confusion_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["True\\Pred"] + classes_list)
        for i, row in enumerate(cm_b_base):
            w.writerow([classes_list[i]] + row)

    # 3. Benchmark B Candidate V2 Finetune
    cm_b_v2 = all_results["experiments"]["Candidate V2 (Cosine Finetune)"]["Benchmark B (Independent Field Test) | Unconstrained (Top-1)"]["confusion_matrix"]
    with open(out_dir / "benchmark_b_candidate_v2_confusion_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["True\\Pred"] + classes_list)
        for i, row in enumerate(cm_b_v2):
            w.writerow([classes_list[i]] + row)

    print(f"[DONE] Exported confusion matrices to CSV under {out_dir}")
    return all_results


if __name__ == "__main__":
    run_comprehensive_matrix()
