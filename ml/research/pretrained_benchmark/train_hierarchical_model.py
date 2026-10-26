"""DINOv2-Small Crop-Conditioned Hierarchical Classification Ablation.

Controlled ablation comparing:
1. Flat 38-class DINOv2 linear classifier.
2. Jointly trained crop-identification head (14 botanical crops).
3. Crop-conditioned disease head.
4. End-to-end hierarchical prediction (predicted crop gates pathology logits).
5. Joint probabilistic marginalization: P(y=j) = P(crop=k) * P(y=j | crop=k).
6. Crop-oracle diagnostic (theoretical upper bound when ground-truth crop is known).

Tracks error propagation, crop identification accuracy, ECE, and cross-crop error elimination.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.evaluate_disease_model import compute_ece, compute_wilson_ci
from ml.research.unified_optimization.experiment_runner import extract_crop_name

FC_DIR = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "feature_cache"
EXPERIMENT_DIR = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "hierarchical_experiments"
EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)


class HierarchicalDINOv2(nn.Module):
    """Joint multi-task model predicting both Crop (14-way) and Disease (38-way)."""

    def __init__(self, in_features: int = 384, num_crops: int = 14, num_diseases: int = 38, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        self.crop_head = nn.Linear(in_features, num_crops)
        self.disease_head = nn.Linear(in_features, num_diseases)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        feat = self.dropout(x)
        crop_logits = self.crop_head(feat)
        disease_logits = self.disease_head(feat)
        return crop_logits, disease_logits


def evaluate_hierarchical_suite(
    model: HierarchicalDINOv2,
    X_val: torch.Tensor,
    y_disease_val: np.ndarray,
    y_crop_val: np.ndarray,
    crop_to_diseases: dict[int, list[int]],
    disease_to_crop: dict[int, int],
    classes: list[str],
    crops: list[str],
) -> dict[str, Any]:
    """Evaluate all 5 inference configurations on the validation split."""
    model.eval()
    with torch.no_grad():
        crop_logits, disease_logits = model(X_val)
        crop_probs = torch.softmax(crop_logits, dim=1).cpu().numpy()
        disease_probs = torch.softmax(disease_logits, dim=1).cpu().numpy()
        c_raw = crop_logits.cpu().numpy()
        d_raw = disease_logits.cpu().numpy()

    n = len(y_disease_val)
    eval_classes = sorted(list(set(y_disease_val)))

    # --- 1. Crop Head Standalone Accuracy ---
    pred_crops = np.argmax(crop_probs, axis=1)
    crop_acc = float(accuracy_score(y_crop_val, pred_crops))
    crop_f1 = float(f1_score(y_crop_val, pred_crops, average="macro", zero_division=0))

    # --- 2. Flat 38-class Classifier ---
    pred_flat = np.argmax(disease_probs, axis=1)
    acc_flat = float(accuracy_score(y_disease_val, pred_flat))
    f1_flat = float(f1_score(y_disease_val, pred_flat, labels=eval_classes, average="macro", zero_division=0))
    ece_flat = float(compute_ece(disease_probs, pred_flat, y_disease_val, n_bins=10)["expected_calibration_error"])
    cross_flat = sum(1 for yt, yp in zip(y_disease_val, pred_flat) if disease_to_crop[yt] != disease_to_crop[yp]) / n

    # --- 3. Predicted-Crop Hierarchical Gating (Hard Gate) ---
    pred_hier = []
    probs_hier = []
    for i in range(n):
        c_pred = pred_crops[i]
        valid_diseases = crop_to_diseases[c_pred]
        masked_logits = np.full(len(classes), -1e9)
        for d_idx in valid_diseases:
            masked_logits[d_idx] = d_raw[i, d_idx]
        p = np.exp(masked_logits - np.max(masked_logits))
        p = p / np.sum(p)
        pred_hier.append(int(np.argmax(p)))
        probs_hier.append(p)
    pred_hier = np.array(pred_hier)
    probs_hier = np.vstack(probs_hier)

    acc_hier = float(accuracy_score(y_disease_val, pred_hier))
    f1_hier = float(f1_score(y_disease_val, pred_hier, labels=eval_classes, average="macro", zero_division=0))
    ece_hier = float(compute_ece(probs_hier, pred_hier, y_disease_val, n_bins=10)["expected_calibration_error"])
    cross_hier = sum(1 for yt, yp in zip(y_disease_val, pred_hier) if disease_to_crop[yt] != disease_to_crop[yp]) / n

    # --- 4. Joint Probabilistic Marginalization ---
    # P(disease j) = P(crop c(j)) * P(disease j | crop c(j))
    probs_marginal = np.zeros_like(disease_probs)
    for i in range(n):
        for c_idx, valid_d in crop_to_diseases.items():
            c_p = crop_probs[i, c_idx]
            sub_logits = d_raw[i, valid_d]
            sub_p = np.exp(sub_logits - np.max(sub_logits))
            sub_p = sub_p / np.sum(sub_p)
            for d_idx, p_val in zip(valid_d, sub_p):
                probs_marginal[i, d_idx] = c_p * p_val

    pred_marginal = np.argmax(probs_marginal, axis=1)
    acc_marginal = float(accuracy_score(y_disease_val, pred_marginal))
    f1_marginal = float(f1_score(y_disease_val, pred_marginal, labels=eval_classes, average="macro", zero_division=0))
    ece_marginal = float(compute_ece(probs_marginal, pred_marginal, y_disease_val, n_bins=10)["expected_calibration_error"])
    cross_marginal = sum(1 for yt, yp in zip(y_disease_val, pred_marginal) if disease_to_crop[yt] != disease_to_crop[yp]) / n

    # --- 5. Crop-Oracle Diagnostic (Ground-Truth Crop Upper Bound) ---
    pred_oracle = []
    probs_oracle = []
    for i in range(n):
        c_true = y_crop_val[i]
        valid_diseases = crop_to_diseases[c_true]
        masked_logits = np.full(len(classes), -1e9)
        for d_idx in valid_diseases:
            masked_logits[d_idx] = d_raw[i, d_idx]
        p = np.exp(masked_logits - np.max(masked_logits))
        p = p / np.sum(p)
        pred_oracle.append(int(np.argmax(p)))
        probs_oracle.append(p)
    pred_oracle = np.array(pred_oracle)
    probs_oracle = np.vstack(probs_oracle)

    acc_oracle = float(accuracy_score(y_disease_val, pred_oracle))
    f1_oracle = float(f1_score(y_disease_val, pred_oracle, labels=eval_classes, average="macro", zero_division=0))
    ece_oracle = float(compute_ece(probs_oracle, pred_oracle, y_disease_val, n_bins=10)["expected_calibration_error"])
    cross_oracle = 0.0  # By definition 0 when oracle crop is known

    # Error propagation analysis
    crop_errors = int(np.sum(pred_crops != y_crop_val))
    propagated_disease_errors = int(np.sum((pred_crops != y_crop_val) & (pred_hier != y_disease_val)))

    return {
        "crop_head": {
            "accuracy": round(crop_acc, 4),
            "macro_f1": round(crop_f1, 4),
            "crop_errors": crop_errors,
            "total_evaluated": n,
        },
        "mode_1_flat_38": {
            "accuracy": round(acc_flat, 4),
            "macro_f1": round(f1_flat, 4),
            "ece": round(ece_flat, 4),
            "cross_crop_error_rate": round(cross_flat, 4),
            "composite_score": round(0.40 * f1_flat + 0.30 * acc_flat + 0.15 * (1 - ece_flat) + 0.15 * (1 - cross_flat), 4),
        },
        "mode_2_hierarchical_hard_gating": {
            "accuracy": round(acc_hier, 4),
            "macro_f1": round(f1_hier, 4),
            "ece": round(ece_hier, 4),
            "cross_crop_error_rate": round(cross_hier, 4),
            "composite_score": round(0.40 * f1_hier + 0.30 * acc_hier + 0.15 * (1 - ece_hier) + 0.15 * (1 - cross_hier), 4),
            "error_propagation_rate": round(propagated_disease_errors / max(crop_errors, 1), 4),
        },
        "mode_3_probabilistic_marginalization": {
            "accuracy": round(acc_marginal, 4),
            "macro_f1": round(f1_marginal, 4),
            "ece": round(ece_marginal, 4),
            "cross_crop_error_rate": round(cross_marginal, 4),
            "composite_score": round(0.40 * f1_marginal + 0.30 * acc_marginal + 0.15 * (1 - ece_marginal) + 0.15 * (1 - cross_marginal), 4),
        },
        "mode_4_crop_oracle_upper_bound": {
            "accuracy": round(acc_oracle, 4),
            "macro_f1": round(f1_oracle, 4),
            "ece": round(ece_oracle, 4),
            "cross_crop_error_rate": 0.0,
            "composite_score": round(0.40 * f1_oracle + 0.30 * acc_oracle + 0.15 * (1 - ece_oracle) + 0.15 * 1.0, 4),
        },
    }


def train_hierarchical_model(
    seed: int = 42,
    epochs: int = 150,
    lr: float = 1e-2,
    weight_decay: float = 1e-4,
    crop_loss_weight: float = 0.5,
) -> dict[str, Any]:
    """Train the joint hierarchical DINOv2 head."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    with open(FC_DIR / "classes.json", "r", encoding="utf-8") as f:
        cls_data = json.load(f)
    classes = cls_data["classes"] if isinstance(cls_data, dict) and "classes" in cls_data else cls_data

    # Map classes to crops
    crop_names = sorted(list(set(extract_crop_name(c) for c in classes)))
    crop_to_idx = {c: i for i, c in enumerate(crop_names)}
    disease_to_crop = {i: crop_to_idx[extract_crop_name(c)] for i, c in enumerate(classes)}

    crop_to_diseases = {i: [] for i in range(len(crop_names))}
    for d_idx, c_idx in disease_to_crop.items():
        crop_to_diseases[c_idx].append(d_idx)

    # Load cached features
    X_tr = torch.load(FC_DIR / "dinov2_small_train.pt", weights_only=True)
    X_va = torch.load(FC_DIR / "dinov2_small_val.pt", weights_only=True)
    y_tr_d = torch.load(FC_DIR / "labels_train.pt", weights_only=True)
    y_va_d = torch.load(FC_DIR / "labels_val.pt", weights_only=True)

    y_tr_c = torch.tensor([disease_to_crop[int(y)] for y in y_tr_d], dtype=torch.int64)
    y_va_c = torch.tensor([disease_to_crop[int(y)] for y in y_va_d], dtype=torch.int64)

    train_ds = TensorDataset(X_tr, y_tr_c, y_tr_d)
    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)

    model = HierarchicalDINOv2(
        in_features=384,
        num_crops=len(crop_names),
        num_diseases=len(classes),
        dropout=0.1,
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    crit_crop = nn.CrossEntropyLoss()
    crit_disease = nn.CrossEntropyLoss()

    best_suite = {}
    best_score = -1.0
    best_epoch = 0

    for ep in range(1, epochs + 1):
        model.train()
        for bx, bc, bd in train_loader:
            optimizer.zero_grad()
            out_c, out_d = model(bx)
            loss_c = crit_crop(out_c, bc)
            loss_d = crit_disease(out_d, bd)
            total_loss = loss_d + crop_loss_weight * loss_c
            total_loss.backward()
            optimizer.step()

        # Evaluate
        suite = evaluate_hierarchical_suite(
            model=model,
            X_val=X_va,
            y_disease_val=y_va_d.numpy(),
            y_crop_val=y_va_c.numpy(),
            crop_to_diseases=crop_to_diseases,
            disease_to_crop=disease_to_crop,
            classes=classes,
            crops=crop_names,
        )

        score = suite["mode_2_hierarchical_hard_gating"]["composite_score"]
        if score > best_score:
            best_score = score
            best_epoch = ep
            best_suite = suite
            torch.save(
                {
                    "epoch": ep,
                    "state_dict": model.state_dict(),
                    "crop_names": crop_names,
                    "classes": classes,
                    "crop_to_diseases": crop_to_diseases,
                    "disease_to_crop": disease_to_crop,
                },
                EXPERIMENT_DIR / f"hierarchical_dinov2_seed{seed}_best.pt",
            )

    return {
        "seed": seed,
        "best_epoch": best_epoch,
        "results": best_suite,
    }


def main():
    print("=" * 70)
    print(" EXPERIMENT 2: CROP-CONDITIONED HIERARCHICAL CLASSIFICATION")
    print("=" * 70)

    # Multi-seed training (seeds 42, 101, 202)
    seeds = [42, 101, 202]
    all_runs = []

    for s in seeds:
        print(f"\n--- Training Seed {s} ---")
        run_res = train_hierarchical_model(seed=s)
        all_runs.append(run_res)
        res = run_res["results"]
        print(f"[Seed {s} Results @ Epoch {run_res['best_epoch']}]:")
        print(f"  Crop Head Acc:                     {res['crop_head']['accuracy']*100:.2f}% | F1: {res['crop_head']['macro_f1']:.4f}")
        print(f"  Flat 38-class:                     Acc: {res['mode_1_flat_38']['accuracy']*100:.2f}% | F1: {res['mode_1_flat_38']['macro_f1']:.4f} | ECE: {res['mode_1_flat_38']['ece']:.4f} | Cross-Crop: {res['mode_1_flat_38']['cross_crop_error_rate']*100:.2f}%")
        print(f"  Hierarchical (Hard Gating):        Acc: {res['mode_2_hierarchical_hard_gating']['accuracy']*100:.2f}% | F1: {res['mode_2_hierarchical_hard_gating']['macro_f1']:.4f} | ECE: {res['mode_2_hierarchical_hard_gating']['ece']:.4f} | Cross-Crop: {res['mode_2_hierarchical_hard_gating']['cross_crop_error_rate']*100:.2f}%")
        print(f"  Hierarchical (Marginalization):    Acc: {res['mode_3_probabilistic_marginalization']['accuracy']*100:.2f}% | F1: {res['mode_3_probabilistic_marginalization']['macro_f1']:.4f} | ECE: {res['mode_3_probabilistic_marginalization']['ece']:.4f} | Cross-Crop: {res['mode_3_probabilistic_marginalization']['cross_crop_error_rate']*100:.2f}%")
        print(f"  Crop-Oracle Diagnostic (Upper Bd): Acc: {res['mode_4_crop_oracle_upper_bound']['accuracy']*100:.2f}% | F1: {res['mode_4_crop_oracle_upper_bound']['macro_f1']:.4f} | ECE: {res['mode_4_crop_oracle_upper_bound']['ece']:.4f} | Cross-Crop: 0.00%")

    # Average metrics across seeds
    avg_crop_acc = np.mean([r["results"]["crop_head"]["accuracy"] for r in all_runs])
    avg_flat_acc = np.mean([r["results"]["mode_1_flat_38"]["accuracy"] for r in all_runs])
    avg_flat_f1 = np.mean([r["results"]["mode_1_flat_38"]["macro_f1"] for r in all_runs])
    avg_hier_acc = np.mean([r["results"]["mode_2_hierarchical_hard_gating"]["accuracy"] for r in all_runs])
    avg_hier_f1 = np.mean([r["results"]["mode_2_hierarchical_hard_gating"]["macro_f1"] for r in all_runs])
    avg_hier_cross = np.mean([r["results"]["mode_2_hierarchical_hard_gating"]["cross_crop_error_rate"] for r in all_runs])
    avg_oracle_acc = np.mean([r["results"]["mode_4_crop_oracle_upper_bound"]["accuracy"] for r in all_runs])
    avg_oracle_f1 = np.mean([r["results"]["mode_4_crop_oracle_upper_bound"]["macro_f1"] for r in all_runs])

    print("\n" + "=" * 70)
    print(" HIERARCHICAL ABLATION SUMMARY (Mean across 3 seeds)")
    print("=" * 70)
    print(f"  Crop Identification Accuracy:      {avg_crop_acc*100:.2f}%")
    print(f"  Flat 38-class Baseline:            Acc: {avg_flat_acc*100:.2f}% | Macro-F1: {avg_flat_f1:.4f}")
    print(f"  Predicted Crop Hierarchical Gate:  Acc: {avg_hier_acc*100:.2f}% | Macro-F1: {avg_hier_f1:.4f} | Cross-Crop Err: {avg_hier_cross*100:.2f}%")
    print(f"  Crop-Oracle Upper Bound:           Acc: {avg_oracle_acc*100:.2f}% | Macro-F1: {avg_oracle_f1:.4f} | Cross-Crop Err: 0.00%")

    # Save summary
    out_file = EXPERIMENT_DIR / "hierarchical_experiment_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "num_crops": 14,
                "num_classes": 38,
                "seeds_evaluated": seeds,
                "averaged_metrics": {
                    "crop_head_accuracy": round(float(avg_crop_acc), 4),
                    "flat_38_accuracy": round(float(avg_flat_acc), 4),
                    "flat_38_macro_f1": round(float(avg_flat_f1), 4),
                    "hierarchical_accuracy": round(float(avg_hier_acc), 4),
                    "hierarchical_macro_f1": round(float(avg_hier_f1), 4),
                    "hierarchical_cross_crop_error": round(float(avg_hier_cross), 4),
                    "crop_oracle_accuracy": round(float(avg_oracle_acc), 4),
                    "crop_oracle_macro_f1": round(float(avg_oracle_f1), 4),
                },
                "runs": all_runs,
            },
            f,
            indent=2,
        )
    print(f"\n--> Saved hierarchical summary to: {out_file}")


if __name__ == "__main__":
    main()
