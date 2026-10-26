"""AgriMind Foundation Model Benchmark — Head Architectures & Feature Fusion.

Evaluates on cached representations:
1. Linear Classifier (Linear Probe with weight decay & cosine scheduling).
2. Cosine-Similarity Multi-Prototype Classifier (MVPDR paradigm, K=1 and K=2 prototypes per class).
3. Hybrid Linear / Prototype Classifier.
4. DINOv2 + CLIP Feature Fusion (896-dim) across Linear and Prototype heads.

Metrics:
- Top-1 Accuracy with Wilson 95% CI
- Macro-F1 (27 represented classes) and Macro-F1 (all 38 classes)
- Expected Calibration Error (ECE) and MCE
- Cross-crop error rate, disease-healthy error rate
- Production 0.60 confidence gate audit
- Predeclared composite score
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
import torch
import torch.nn as nn
import torch.nn.functional as F

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.evaluate_disease_model import compute_ece, compute_wilson_ci
from ml.research.unified_optimization.experiment_runner import extract_crop_name


def evaluate_predictions(
    model_name: str,
    y_true: np.ndarray,
    all_probs: np.ndarray,
    classes: list[str],
    param_count: int,
    mean_latency_ms: float = 0.0,
    confidence_gate: float = 0.60,
) -> dict[str, Any]:
    """Compute standard AgriMind evaluation metrics and gate audit."""
    num_classes = len(classes)
    y_pred = np.argmax(all_probs, axis=-1)
    y_conf = np.max(all_probs, axis=-1)

    total_evaluated = len(y_true)
    total_correct = int(np.sum(y_true == y_pred))
    acc = float(total_correct / max(total_evaluated, 1))
    wilson_ci = compute_wilson_ci(total_correct, total_evaluated, confidence=0.95)

    eval_classes_idx = sorted(list(set(y_true)))
    macro_f1 = float(f1_score(y_true, y_pred, labels=eval_classes_idx, average="macro", zero_division=0))
    macro_f1_38 = float(f1_score(y_true, y_pred, labels=list(range(num_classes)), average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, labels=eval_classes_idx, average="weighted", zero_division=0))

    precision, recall, _, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=eval_classes_idx, average="macro", zero_division=0
    )

    ece_dict = compute_ece(all_probs, y_pred, y_true, n_bins=10)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(num_classes)))

    # Error breakdown
    sample_records = []
    cross_crop_errors = 0
    within_crop_errors = 0
    dh_errors = 0

    for i in range(total_evaluated):
        t_cls = classes[y_true[i]]
        p_cls = classes[y_pred[i]]
        is_corr = (y_true[i] == y_pred[i])
        crop_match = (extract_crop_name(t_cls) == extract_crop_name(p_cls))
        dh_mismatch = (("healthy" not in t_cls.lower()) != ("healthy" not in p_cls.lower()))

        if not is_corr:
            if crop_match:
                within_crop_errors += 1
            else:
                cross_crop_errors += 1
            if dh_mismatch:
                dh_errors += 1

        sample_records.append({
            "true_class": t_cls,
            "pred_class": p_cls,
            "confidence": round(float(y_conf[i]), 4),
            "is_correct": is_corr,
            "crop_match": crop_match,
            "passed_gate": bool(y_conf[i] >= confidence_gate),
        })

    cross_crop_rate = round(cross_crop_errors / max(total_evaluated, 1), 4)
    dh_rate = round(dh_errors / max(total_evaluated, 1), 4)

    # 0.60 Gate audit
    actionable = [s for s in sample_records if s["passed_gate"]]
    abstentions = [s for s in sample_records if not s["passed_gate"]]
    act_corr = sum(1 for s in actionable if s["is_correct"])
    false_conf = sum(1 for s in actionable if not s["is_correct"])
    safely_rej = sum(1 for s in abstentions if not s["is_correct"])

    act_prec = round(act_corr / max(len(actionable), 1), 4)
    filter_eff = round(safely_rej / max(total_evaluated - total_correct, 1), 4)

    # Predeclared composite score
    ece_val = ece_dict["expected_calibration_error"]
    comp_score = round(
        0.40 * macro_f1 + 0.30 * acc + 0.15 * max(0.0, 1.0 - ece_val) + 0.15 * max(0.0, 1.0 - cross_crop_rate), 4
    )

    return {
        "model_name": model_name,
        "parameter_count": param_count,
        "mean_latency_ms": mean_latency_ms,
        "total_evaluated": total_evaluated,
        "accuracy": round(acc, 4),
        "wilson_95_ci": wilson_ci,
        "macro_f1": round(macro_f1, 4),
        "macro_f1_38": round(macro_f1_38, 4),
        "macro_precision": round(float(precision), 4),
        "macro_recall": round(float(recall), 4),
        "weighted_f1": round(weighted_f1, 4),
        "expected_calibration_error": ece_val,
        "maximum_calibration_error": ece_dict["maximum_calibration_error"],
        "composite_score": comp_score,
        "cross_crop_error_rate": cross_crop_rate,
        "disease_healthy_error_rate": dh_rate,
        "cross_crop_errors": cross_crop_errors,
        "within_crop_errors": within_crop_errors,
        "disease_healthy_errors": dh_errors,
        "confidence_gate_audit": {
            "actionable_count": len(actionable),
            "actionable_precision": act_prec,
            "false_confident_count": false_conf,
            "abstention_count": len(abstentions),
            "safely_rejected_errors": safely_rej,
            "safety_filtering_efficiency": filter_eff,
        },
        "confusion_matrix": cm.tolist(),
    }


def train_linear_probe(
    x_train: torch.Tensor,
    y_train: torch.Tensor,
    x_val: torch.Tensor,
    num_classes: int = 38,
    epochs: int = 60,
    lr: float = 0.01,
    weight_decay: float = 0.001,
) -> np.ndarray:
    """Train a linear probe with AdamW and cosine decay."""
    dim = x_train.shape[1]
    linear = nn.Linear(dim, num_classes)
    optimizer = torch.optim.AdamW(linear.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()

    batch_size = 32
    n_samples = len(x_train)

    linear.train()
    for ep in range(epochs):
        perm = torch.randperm(n_samples)
        for i in range(0, n_samples, batch_size):
            idx = perm[i : i + batch_size]
            bx = x_train[idx]
            by = y_train[idx]
            optimizer.zero_grad()
            logits = linear(bx)
            loss = criterion(logits, by)
            loss.backward()
            optimizer.step()
        scheduler.step()

    linear.eval()
    with torch.no_grad():
        val_logits = linear(x_val)
        probs = torch.softmax(val_logits, dim=-1).numpy()
    return probs


def build_prototype_classifier(
    x_train: torch.Tensor,
    y_train: torch.Tensor,
    x_val: torch.Tensor,
    num_classes: int = 38,
    num_prototypes_per_class: int = 2,
    temperature: float = 12.0,
    zero_shot_text_prototypes: torch.Tensor | None = None,
) -> np.ndarray:
    """Cosine-similarity multi-prototype classifier (MVPDR paradigm)."""
    dim = x_train.shape[1]
    prototypes_by_class: dict[int, list[torch.Tensor]] = {}

    for c in range(num_classes):
        mask = (y_train == c)
        c_feats = x_train[mask]
        n_c = len(c_feats)

        if n_c == 0:
            # Unrepresented class
            if zero_shot_text_prototypes is not None and c < len(zero_shot_text_prototypes):
                # Use zero-shot text prototype
                t_proto = zero_shot_text_prototypes[c].unsqueeze(0)
                prototypes_by_class[c] = [F.normalize(t_proto, p=2, dim=-1)]
            else:
                prototypes_by_class[c] = []
        elif n_c <= num_prototypes_per_class:
            # Use all available samples as distinct prototypes
            protos = [F.normalize(c_feats[i : i + 1], p=2, dim=-1) for i in range(n_c)]
            prototypes_by_class[c] = protos
        else:
            # Cluster into K prototypes using KMeans
            km = KMeans(n_clusters=num_prototypes_per_class, random_state=42, n_init=5)
            km.fit(c_feats.numpy())
            protos = [F.normalize(torch.tensor(center, dtype=torch.float32).unsqueeze(0), p=2, dim=-1) for center in km.cluster_centers_]
            prototypes_by_class[c] = protos

    # Compute similarity for validation samples
    val_norm = F.normalize(x_val, p=2, dim=-1)
    val_logits = torch.full((len(x_val), num_classes), -999.0, dtype=torch.float32)

    for c in range(num_classes):
        c_protos = prototypes_by_class[c]
        if not c_protos:
            # Unrepresented class without text fallback
            val_logits[:, c] = -50.0
            continue
        c_proto_matrix = torch.cat(c_protos, dim=0)  # [K, D]
        sims = torch.matmul(val_norm, c_proto_matrix.T)  # [N_val, K]
        max_sim, _ = torch.max(sims, dim=-1)  # Max prototype similarity
        val_logits[:, c] = max_sim * temperature

    probs = torch.softmax(val_logits, dim=-1).numpy()
    return probs


def main():
    cache_dir = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "feature_cache"
    out_dir = REPO_ROOT / "ml" / "research" / "pretrained_benchmark"
    results_dir = out_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    classes_info = json.loads((cache_dir / "classes.json").read_text(encoding="utf-8"))
    classes = classes_info["classes"]
    num_classes = len(classes)

    y_train = torch.load(cache_dir / "labels_train.pt")
    y_val = torch.load(cache_dir / "labels_val.pt")
    y_val_np = y_val.numpy()

    dino_train = torch.load(cache_dir / "dinov2_small_train.pt")
    dino_val = torch.load(cache_dir / "dinov2_small_val.pt")

    clip_train = torch.load(cache_dir / "clip_train.pt")
    clip_val = torch.load(cache_dir / "clip_val.pt")
    clip_text = torch.load(cache_dir / "clip_text_prototypes.pt")

    fusion_train = torch.load(cache_dir / "fusion_dino_clip_train.pt")
    fusion_val = torch.load(cache_dir / "fusion_dino_clip_val.pt")

    all_head_results = []

    print("==================================================================")
    print(" BENCHMARKING FOUNDATION MODEL HEADS & FEATURE FUSIONS")
    print("==================================================================")

    # -------------------------------------------------------------------------
    # 1. DINOv2-Small Linear Probe
    # -------------------------------------------------------------------------
    print("\n>>> 1. DINOv2-Small Linear Probe")
    dino_linear_probs = train_linear_probe(dino_train, y_train, dino_val, num_classes=num_classes)
    res_dino_linear = evaluate_predictions("DINOv2-Small (Linear Probe)", y_val_np, dino_linear_probs, classes, param_count=384 * 38)
    all_head_results.append(res_dino_linear)
    print(f"--> Acc: {res_dino_linear['accuracy']*100:.2f}% | F1: {res_dino_linear['macro_f1']:.4f} | ECE: {res_dino_linear['expected_calibration_error']:.4f} | Score: {res_dino_linear['composite_score']:.4f}")

    # -------------------------------------------------------------------------
    # 2. DINOv2-Small Multi-Prototype Classifier (K=2)
    # -------------------------------------------------------------------------
    print("\n>>> 2. DINOv2-Small Multi-Prototype Classifier (K=2, MVPDR)")
    dino_proto_probs = build_prototype_classifier(dino_train, y_train, dino_val, num_classes=num_classes, num_prototypes_per_class=2)
    res_dino_proto = evaluate_predictions("DINOv2-Small (Multi-Prototype K=2)", y_val_np, dino_proto_probs, classes, param_count=0)
    all_head_results.append(res_dino_proto)
    print(f"--> Acc: {res_dino_proto['accuracy']*100:.2f}% | F1: {res_dino_proto['macro_f1']:.4f} | ECE: {res_dino_proto['expected_calibration_error']:.4f} | Score: {res_dino_proto['composite_score']:.4f}")

    # -------------------------------------------------------------------------
    # 3. DINOv2-Small Hybrid (Linear + Prototype)
    # -------------------------------------------------------------------------
    print("\n>>> 3. DINOv2-Small Hybrid Classifier (Linear + Prototype 50/50)")
    dino_hybrid_probs = 0.5 * dino_linear_probs + 0.5 * dino_proto_probs
    dino_hybrid_probs = dino_hybrid_probs / dino_hybrid_probs.sum(axis=-1, keepdims=True)
    res_dino_hybrid = evaluate_predictions("DINOv2-Small (Hybrid Linear+Prototype)", y_val_np, dino_hybrid_probs, classes, param_count=384 * 38)
    all_head_results.append(res_dino_hybrid)
    print(f"--> Acc: {res_dino_hybrid['accuracy']*100:.2f}% | F1: {res_dino_hybrid['macro_f1']:.4f} | ECE: {res_dino_hybrid['expected_calibration_error']:.4f} | Score: {res_dino_hybrid['composite_score']:.4f}")

    # -------------------------------------------------------------------------
    # 4. CLIP ViT-B/32 Linear Probe
    # -------------------------------------------------------------------------
    print("\n>>> 4. CLIP ViT-B/32 Linear Probe")
    clip_linear_probs = train_linear_probe(clip_train, y_train, clip_val, num_classes=num_classes)
    res_clip_linear = evaluate_predictions("CLIP ViT-B/32 (Linear Probe)", y_val_np, clip_linear_probs, classes, param_count=512 * 38)
    all_head_results.append(res_clip_linear)
    print(f"--> Acc: {res_clip_linear['accuracy']*100:.2f}% | F1: {res_clip_linear['macro_f1']:.4f} | ECE: {res_clip_linear['expected_calibration_error']:.4f} | Score: {res_clip_linear['composite_score']:.4f}")

    # -------------------------------------------------------------------------
    # 5. CLIP ViT-B/32 Multimodal Prototype (Vision + Zero-Shot Text Fallback)
    # -------------------------------------------------------------------------
    print("\n>>> 5. CLIP Multimodal Prototype (Vision + Zero-Shot Text Fallback)")
    clip_proto_probs = build_prototype_classifier(clip_train, y_train, clip_val, num_classes=num_classes, num_prototypes_per_class=2, zero_shot_text_prototypes=clip_text)
    res_clip_proto = evaluate_predictions("CLIP ViT-B/32 (Multimodal Prototype)", y_val_np, clip_proto_probs, classes, param_count=0)
    all_head_results.append(res_clip_proto)
    print(f"--> Acc: {res_clip_proto['accuracy']*100:.2f}% | F1: {res_clip_proto['macro_f1']:.4f} | ECE: {res_clip_proto['expected_calibration_error']:.4f} | Score: {res_clip_proto['composite_score']:.4f}")

    # -------------------------------------------------------------------------
    # 6. DINOv2 + CLIP Feature Fusion Linear Probe (896-dim)
    # -------------------------------------------------------------------------
    print("\n>>> 6. DINOv2 + CLIP Feature Fusion Linear Probe (896-dim)")
    fusion_linear_probs = train_linear_probe(fusion_train, y_train, fusion_val, num_classes=num_classes)
    res_fusion_linear = evaluate_predictions("DINOv2+CLIP Fusion (Linear Probe)", y_val_np, fusion_linear_probs, classes, param_count=896 * 38)
    all_head_results.append(res_fusion_linear)
    print(f"--> Acc: {res_fusion_linear['accuracy']*100:.2f}% | F1: {res_fusion_linear['macro_f1']:.4f} | ECE: {res_fusion_linear['expected_calibration_error']:.4f} | Score: {res_fusion_linear['composite_score']:.4f}")

    # -------------------------------------------------------------------------
    # 7. DINOv2 + CLIP Feature Fusion Hybrid (Linear + Prototype)
    # -------------------------------------------------------------------------
    print("\n>>> 7. DINOv2 + CLIP Feature Fusion Hybrid Classifier")
    fusion_proto_probs = build_prototype_classifier(fusion_train, y_train, fusion_val, num_classes=num_classes, num_prototypes_per_class=2)
    fusion_hybrid_probs = 0.5 * fusion_linear_probs + 0.5 * fusion_proto_probs
    fusion_hybrid_probs = fusion_hybrid_probs / fusion_hybrid_probs.sum(axis=-1, keepdims=True)
    res_fusion_hybrid = evaluate_predictions("DINOv2+CLIP Fusion (Hybrid Head)", y_val_np, fusion_hybrid_probs, classes, param_count=896 * 38)
    all_head_results.append(res_fusion_hybrid)
    print(f"--> Acc: {res_fusion_hybrid['accuracy']*100:.2f}% | F1: {res_fusion_hybrid['macro_f1']:.4f} | ECE: {res_fusion_hybrid['expected_calibration_error']:.4f} | Score: {res_fusion_hybrid['composite_score']:.4f}")

    # Save summary
    (out_dir / "foundation_heads_summary.json").write_text(json.dumps(all_head_results, indent=2), encoding="utf-8")
    print(f"\n[BENCHMARK COMPLETE] Evaluated {len(all_head_results)} foundation head architectures.")


if __name__ == "__main__":
    main()
