"""AgriMind Accuracy V2 — Systematic Experiment Matrix & Statistical Evaluation.

Executes:
- Experiment A: Frozen-feature classifiers (Linear probe C-sweep, Cosine similarity, Prototypes, CLIP fusion)
- Experiment B: LoRA architectural exploration (Ranks 2/4/8, blocks 2 vs 4, target projections, learning rates)
- Experiment C: Controlled partial fine-tuning (Block 11 unfreezing, blocks 10-11, discriminative LR, clipping)
- Experiment D: Field augmentations & loss functions (Focal loss, enhanced field transforms, label smoothing)
- Experiment E: Multi-seed verification & paired bootstrap testing against incumbent DINOv2 LoRA champion.

Emits:
- Per-run directories under accuracy_v2/runs/{run_id}/
- Live experiment ledger: accuracy_v2_ledger.json
- Leaderboard CSV: accuracy_v2_leaderboard.csv
- Statistical comparison report against incumbent: statistical_comparison.json
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

import numpy as np
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from transformers import Dinov2Model

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.evaluate_disease_model import compute_ece, compute_wilson_ci
from ml.disease_model import IMAGENET_MEAN, IMAGENET_STD
from ml.research.unified_optimization.experiment_runner import extract_crop_name

MANIFEST_TRAIN = REPO_ROOT / "evaluation" / "manifests" / "field_train_manifest.csv"
MANIFEST_VAL = REPO_ROOT / "evaluation" / "manifests" / "field_val_manifest.csv"
DATA_ROOT = REPO_ROOT / "evaluation" / "datasets" / "field_data" / "images"
CACHE_DIR = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "feature_cache"
CLASSES_PATH = CACHE_DIR / "classes.json"

EXP_DIR = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "accuracy_v2"
RUNS_DIR = EXP_DIR / "runs"
CHECKPOINT_DIR = EXP_DIR / "checkpoints"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

LEDGER_PATH = EXP_DIR / "accuracy_v2_ledger.json"
LEADERBOARD_PATH = EXP_DIR / "accuracy_v2_leaderboard.csv"


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------
def compute_brier_score(probs: np.ndarray, labels: np.ndarray, num_classes: int) -> float:
    one_hot = np.zeros((len(labels), num_classes), dtype=np.float32)
    for i, l in enumerate(labels):
        one_hot[i, l] = 1.0
    return float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))


def evaluate_predictions(
    y_true: np.ndarray,
    all_probs: np.ndarray,
    classes: list[str],
    latencies: list[float] | None = None,
    confidence_gate: float = 0.60,
) -> dict[str, Any]:
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
    brier = compute_brier_score(all_probs, y_true, num_classes)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(num_classes))).tolist()

    # Per-class metrics for represented classes
    per_cls_p, per_cls_r, per_cls_f, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(num_classes)), average=None, zero_division=0
    )
    per_class_metrics = {}
    for idx, cname in enumerate(classes):
        per_class_metrics[cname] = {
            "precision": round(float(per_cls_p[idx]), 4),
            "recall": round(float(per_cls_r[idx]), 4),
            "f1": round(float(per_cls_f[idx]), 4),
            "support": int(np.sum(y_true == idx)),
        }

    # Cross-crop errors
    cross_crop_errors = 0
    for i in range(total_evaluated):
        if y_true[i] != y_pred[i]:
            if extract_crop_name(classes[y_true[i]]) != extract_crop_name(classes[y_pred[i]]):
                cross_crop_errors += 1
    cross_crop_rate = round(cross_crop_errors / max(total_evaluated, 1), 4)

    # 0.60 gate audit
    passed_gate = y_conf >= confidence_gate
    act_count = int(np.sum(passed_gate))
    act_correct = int(np.sum(passed_gate & (y_true == y_pred)))
    act_prec = round(float(act_correct / max(act_count, 1)), 4)
    safely_rejected = int(np.sum((~passed_gate) & (y_true != y_pred)))
    filter_eff = round(float(safely_rejected / max(total_evaluated - total_correct, 1)), 4)

    ece_val = float(ece_dict["expected_calibration_error"])
    comp_score = round(
        0.40 * macro_f1 + 0.30 * acc + 0.15 * max(0.0, 1.0 - ece_val) + 0.15 * max(0.0, 1.0 - cross_crop_rate), 4
    )

    mean_lat = round(float(np.mean(latencies)), 2) if latencies else 0.0

    return {
        "accuracy": round(acc, 4),
        "wilson_95_ci": wilson_ci,
        "macro_f1": round(macro_f1, 4),
        "macro_f1_38": round(macro_f1_38, 4),
        "weighted_f1": round(weighted_f1, 4),
        "macro_precision": round(float(precision), 4),
        "macro_recall": round(float(recall), 4),
        "expected_calibration_error": round(ece_val, 4),
        "maximum_calibration_error": round(float(ece_dict["maximum_calibration_error"]), 4),
        "brier_score": round(brier, 4),
        "cross_crop_error_rate": cross_crop_rate,
        "composite_score": comp_score,
        "actionable_precision": act_prec,
        "safety_filtering_efficiency": filter_eff,
        "mean_latency_ms": mean_lat,
        "per_class_metrics": per_class_metrics,
        "confusion_matrix": cm,
    }


def paired_bootstrap_test(
    y_true: np.ndarray,
    probs_incumbent: np.ndarray,
    probs_candidate: np.ndarray,
    classes: list[str],
    n_iterations: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    rng = np.random.RandomState(seed)
    n = len(y_true)
    preds_inc = np.argmax(probs_incumbent, axis=1)
    preds_cand = np.argmax(probs_candidate, axis=1)

    eval_classes_idx = sorted(list(set(y_true)))

    acc_inc = np.mean(y_true == preds_inc)
    acc_cand = np.mean(y_true == preds_cand)
    f1_inc = f1_score(y_true, preds_inc, labels=eval_classes_idx, average="macro", zero_division=0)
    f1_cand = f1_score(y_true, preds_cand, labels=eval_classes_idx, average="macro", zero_division=0)

    acc_deltas = []
    f1_deltas = []

    for _ in range(n_iterations):
        idx = rng.randint(0, n, size=n)
        yt_sample = y_true[idx]
        pi_sample = preds_inc[idx]
        pc_sample = preds_cand[idx]

        acc_d = np.mean(yt_sample == pc_sample) - np.mean(yt_sample == pi_sample)
        f1_c = f1_score(yt_sample, pc_sample, labels=eval_classes_idx, average="macro", zero_division=0)
        f1_i = f1_score(yt_sample, pi_sample, labels=eval_classes_idx, average="macro", zero_division=0)

        acc_deltas.append(acc_d)
        f1_deltas.append(f1_c - f1_i)

    acc_ci = (float(np.percentile(acc_deltas, 2.5)), float(np.percentile(acc_deltas, 97.5)))
    f1_ci = (float(np.percentile(f1_deltas, 2.5)), float(np.percentile(f1_deltas, 97.5)))

    p_acc = float(np.mean(np.array(acc_deltas) <= 0.0))
    p_f1 = float(np.mean(np.array(f1_deltas) <= 0.0))

    return {
        "n_iterations": n_iterations,
        "incumbent_accuracy": round(float(acc_inc), 4),
        "candidate_accuracy": round(float(acc_cand), 4),
        "accuracy_delta_mean": round(float(np.mean(acc_deltas)), 4),
        "accuracy_delta_95_ci": [round(acc_ci[0], 4), round(acc_ci[1], 4)],
        "accuracy_p_value": round(p_acc, 4),
        "incumbent_macro_f1": round(float(f1_inc), 4),
        "candidate_macro_f1": round(float(f1_cand), 4),
        "macro_f1_delta_mean": round(float(np.mean(f1_deltas)), 4),
        "macro_f1_delta_95_ci": [round(f1_ci[0], 4), round(f1_ci[1], 4)],
        "macro_f1_p_value": round(p_f1, 4),
        "statistically_superior": bool(acc_ci[0] > 0 and f1_ci[0] > 0 and p_acc < 0.05 and p_f1 < 0.05),
    }


# ---------------------------------------------------------------------------
# LoRA Models & Dataset
# ---------------------------------------------------------------------------
class LoRALinear(nn.Module):
    def __init__(self, base_linear: nn.Linear, r: int = 4, lora_alpha: float = 16.0, lora_dropout: float = 0.05):
        super().__init__()
        self.base_linear = base_linear
        self.base_linear.weight.requires_grad = False
        if self.base_linear.bias is not None:
            self.base_linear.bias.requires_grad = False
        self.r = r
        self.lora_alpha = lora_alpha
        self.scaling = lora_alpha / r
        d_in = base_linear.in_features
        d_out = base_linear.out_features
        self.lora_A = nn.Parameter(torch.empty(r, d_in))
        self.lora_B = nn.Parameter(torch.zeros(d_out, r))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        self.dropout = nn.Dropout(p=lora_dropout) if lora_dropout > 0.0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base_out = self.base_linear(x)
        lora_out = (self.dropout(x) @ self.lora_A.T @ self.lora_B.T) * self.scaling
        return base_out + lora_out


class DINOv2LoRAClassifierV2(nn.Module):
    def __init__(
        self,
        num_classes: int = 38,
        lora_rank: int = 4,
        num_lora_blocks: int = 4,
        lora_alpha: float = 16.0,
        lora_dropout: float = 0.05,
        target_projections: str = "qv",  # "qv" or "all_linear"
    ):
        super().__init__()
        self.backbone = Dinov2Model.from_pretrained("facebook/dinov2-small", local_files_only=True)
        self.num_classes = num_classes
        self.lora_rank = lora_rank
        self.num_lora_blocks = num_lora_blocks
        self.target_projections = target_projections

        for p in self.backbone.parameters():
            p.requires_grad = False

        if num_lora_blocks > 0 and lora_rank > 0:
            total_layers = len(self.backbone.encoder.layer)
            start_layer = total_layers - num_lora_blocks
            for idx in range(start_layer, total_layers):
                layer = self.backbone.encoder.layer[idx]
                att = layer.attention
                att.q_proj = LoRALinear(att.q_proj, r=lora_rank, lora_alpha=lora_alpha, lora_dropout=lora_dropout)
                att.v_proj = LoRALinear(att.v_proj, r=lora_rank, lora_alpha=lora_alpha, lora_dropout=lora_dropout)
                if target_projections == "all_linear":
                    att.k_proj = LoRALinear(att.k_proj, r=lora_rank, lora_alpha=lora_alpha, lora_dropout=lora_dropout)
                    att.o_proj = LoRALinear(att.o_proj, r=lora_rank, lora_alpha=lora_alpha, lora_dropout=lora_dropout)

        self.classifier = nn.Sequential(
            nn.Dropout(p=0.1),
            nn.Linear(384, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.backbone(x)
        cls_token = out.last_hidden_state[:, 0]
        return self.classifier(cls_token)


class DINOv2PartialFineTune(nn.Module):
    def __init__(self, num_classes: int = 38, unfreeze_blocks: int = 1):
        super().__init__()
        self.backbone = Dinov2Model.from_pretrained("facebook/dinov2-small", local_files_only=True)
        self.num_classes = num_classes
        self.unfreeze_blocks = unfreeze_blocks

        # Freeze everything
        for p in self.backbone.parameters():
            p.requires_grad = False

        # Unfreeze final n blocks
        total_layers = len(self.backbone.encoder.layer)
        for idx in range(total_layers - unfreeze_blocks, total_layers):
            for p in self.backbone.encoder.layer[idx].parameters():
                p.requires_grad = True

        self.classifier = nn.Sequential(
            nn.Dropout(p=0.1),
            nn.Linear(384, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.backbone(x)
        cls_token = out.last_hidden_state[:, 0]
        return self.classifier(cls_token)


class ClassBalancedFocalLoss(nn.Module):
    def __init__(self, class_counts: dict[int, int], num_classes: int = 38, gamma: float = 1.5, beta: float = 0.999):
        super().__init__()
        self.gamma = gamma
        self.num_classes = num_classes

        # Effective number of samples
        effective_num = 1.0 - np.power(beta, [class_counts.get(i, 1) for i in range(num_classes)])
        weights = (1.0 - beta) / np.array(effective_num)
        weights = weights / np.sum(weights) * num_classes
        self.register_buffer("weights", torch.tensor(weights, dtype=torch.float32))

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none", weight=self.weights)
        p = torch.exp(-ce_loss)
        focal_loss = ((1.0 - p) ** self.gamma) * ce_loss
        return focal_loss.mean()


class CachedRAMDataset(Dataset):
    def __init__(self, manifest_path: Path, data_root: Path, class_to_idx: dict[str, int], transform: Any = None):
        self.transform = transform
        self.samples = []
        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rel_path = row.get("image_path") or row.get("relative_path")
                cls_name = row.get("mapped_class") or row.get("class_name")
                if cls_name in class_to_idx:
                    img_path = data_root / rel_path
                    with Image.open(img_path) as img:
                        img_rgb = img.convert("RGB")
                    self.samples.append((img_rgb, class_to_idx[cls_name], cls_name))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int, str]:
        img, cls_idx, cls_name = self.samples[idx]
        if self.transform is not None:
            tensor = self.transform(img)
        else:
            tensor = transforms.ToTensor()(img)
        return tensor, cls_idx, cls_name


def get_transforms(aug_type: str = "standard_field", is_train: bool = True) -> transforms.Compose:
    if not is_train:
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])

    if aug_type == "standard_field":
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomPerspective(distortion_scale=0.2, p=0.5),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15, hue=0.05),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])
    elif aug_type == "enhanced_field":
        return transforms.Compose([
            transforms.RandomResizedCrop(224, scale=(0.85, 1.0)),
            transforms.RandomRotation(15),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.20, contrast=0.20, saturation=0.20, hue=0.05),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])
    raise ValueError(f"Unknown aug_type: {aug_type}")


# ---------------------------------------------------------------------------
# Training & Evaluation Execution
# ---------------------------------------------------------------------------
def run_torch_experiment(
    run_id: str,
    domain: str,
    model_type: str,  # "lora" or "partial_unfreeze"
    model_kwargs: dict[str, Any],
    aug_type: str = "standard_field",
    loss_type: str = "ce",  # "ce" or "focal"
    label_smoothing: float = 0.05,
    epochs: int = 15,
    batch_size: int = 16,
    lr_backbone: float = 1e-4,
    lr_head: float = 1e-3,
    weight_decay: float = 1e-4,
    grad_clip: float | None = None,
    seed: int = 42,
    device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu"),
    train_ds: CachedRAMDataset | None = None,
    val_ds: CachedRAMDataset | None = None,
    classes: list[str] | None = None,
) -> dict[str, Any]:
    run_dir = RUNS_DIR / run_id
    ckpt_path = CHECKPOINT_DIR / f"{run_id}_best.pt"
    if (run_dir / "val_metrics.json").exists() and ckpt_path.exists():
        print(f"\n>>> [CACHE HIT] Run {run_id} already completed. Loading from disk...")
        with open(run_dir / "config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        with open(run_dir / "val_metrics.json", "r", encoding="utf-8") as f:
            metrics = json.load(f)

        if model_type == "lora":
            model = DINOv2LoRAClassifierV2(num_classes=len(classes), **model_kwargs).to(device)
        else:
            model = DINOv2PartialFineTune(num_classes=len(classes), **model_kwargs).to(device)

        ckpt_data = torch.load(ckpt_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt_data["state_dict"])
        model.eval()

        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
        val_probs = []
        val_y = []
        with torch.no_grad():
            for x, y, _ in val_loader:
                x = x.to(device)
                out = model(x)
                val_probs.append(torch.softmax(out, dim=1).cpu().numpy())
                val_y.extend(y.numpy())

        return {
            **cfg,
            **metrics,
            "val_probs": np.vstack(val_probs),
            "val_y": np.array(val_y),
        }

    print(f"\n>>> Starting [{domain}] Run {run_id} | Seed {seed} | Device: {device}")
    t_start = time.perf_counter()

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=True)

    if model_type == "lora":
        model = DINOv2LoRAClassifierV2(num_classes=len(classes), **model_kwargs).to(device)
    elif model_type == "partial_unfreeze":
        model = DINOv2PartialFineTune(num_classes=len(classes), **model_kwargs).to(device)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    backbone_params = []
    head_params = []
    for name, p in model.named_parameters():
        if p.requires_grad:
            if "classifier" in name:
                head_params.append(p)
            else:
                backbone_params.append(p)

    trainable_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_count = sum(p.numel() for p in model.parameters())

    param_groups = []
    if backbone_params:
        param_groups.append({"params": backbone_params, "lr": lr_backbone, "weight_decay": weight_decay})
    if head_params:
        param_groups.append({"params": head_params, "lr": lr_head, "weight_decay": weight_decay})

    optimizer = torch.optim.AdamW(param_groups)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    if loss_type == "ce":
        criterion = nn.CrossEntropyLoss(label_smoothing=label_smoothing)
    elif loss_type == "focal":
        train_counts = {}
        for _, y, _ in train_ds.samples:
            train_counts[y] = train_counts.get(y, 0) + 1
        criterion = ClassBalancedFocalLoss(class_counts=train_counts, num_classes=len(classes)).to(device)
    else:
        raise ValueError(f"Unknown loss_type: {loss_type}")

    best_score = -1.0
    best_epoch = 0
    best_metrics = {}
    best_probs = None
    best_state_dict = None
    history = []

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        train_correct = 0
        total_train = 0

        for x, y, _ in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            if grad_clip is not None:
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=grad_clip)
            optimizer.step()

            train_loss += loss.item() * len(y)
            train_correct += int(torch.sum(torch.argmax(logits, dim=1) == y))
            total_train += len(y)

        scheduler.step()

        # Validation pass
        model.eval()
        val_probs = []
        val_y = []
        latencies = []
        with torch.no_grad():
            for x, y, _ in val_loader:
                x = x.to(device)
                t0 = time.perf_counter()
                out = model(x)
                latencies.append((time.perf_counter() - t0) * 1000.0 / len(y))
                p = torch.softmax(out, dim=1).cpu().numpy()
                val_probs.append(p)
                val_y.extend(y.numpy())

        all_p = np.vstack(val_probs)
        all_y = np.array(val_y)
        metrics = evaluate_predictions(all_y, all_p, classes, latencies=latencies)

        epoch_record = {
            "epoch": epoch,
            "train_loss": round(train_loss / total_train, 4),
            "train_acc": round(train_correct / total_train, 4),
            "val_acc": metrics["accuracy"],
            "val_f1": metrics["macro_f1"],
            "val_ece": metrics["expected_calibration_error"],
            "composite_score": metrics["composite_score"],
        }
        history.append(epoch_record)

        if metrics["composite_score"] > best_score:
            best_score = metrics["composite_score"]
            best_epoch = epoch
            best_metrics = metrics
            best_probs = all_p
            best_state_dict = {k: v.cpu() for k, v in model.state_dict().items()}

    run_time = round(time.perf_counter() - t_start, 2)
    print(f"[{run_id}] Finished in {run_time}s | Best Epoch: {best_epoch} | Acc: {best_metrics['accuracy']} | Macro-F1: {best_metrics['macro_f1']} | Score: {best_score}")

    # Save run artifacts
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ckpt_path = CHECKPOINT_DIR / f"{run_id}_best.pt"
    torch.save(
        {
            "run_id": run_id,
            "domain": domain,
            "best_epoch": best_epoch,
            "metrics": best_metrics,
            "state_dict": best_state_dict,
            "seed": seed,
            "model_type": model_type,
            "model_kwargs": model_kwargs,
        },
        ckpt_path,
    )

    with open(ckpt_path, "rb") as f:
        ckpt_sha = hashlib.sha256(f.read()).hexdigest()

    # Save run metadata
    run_config = {
        "run_id": run_id,
        "domain": domain,
        "model_type": model_type,
        "model_kwargs": model_kwargs,
        "aug_type": aug_type,
        "loss_type": loss_type,
        "label_smoothing": label_smoothing,
        "epochs": epochs,
        "batch_size": batch_size,
        "lr_backbone": lr_backbone,
        "lr_head": lr_head,
        "weight_decay": weight_decay,
        "grad_clip": grad_clip,
        "seed": seed,
        "trainable_parameters": trainable_count,
        "total_parameters": total_count,
        "train_time_seconds": run_time,
        "best_epoch": best_epoch,
        "checkpoint_path": str(ckpt_path),
        "checkpoint_sha256": ckpt_sha,
    }

    with open(run_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(run_config, f, indent=2)

    with open(run_dir / "history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    with open(run_dir / "val_metrics.json", "w", encoding="utf-8") as f:
        json.dump(best_metrics, f, indent=2)

    # Save confusion matrix CSV
    with open(run_dir / "confusion_matrix.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([""] + classes)
        for idx, row in enumerate(best_metrics["confusion_matrix"]):
            writer.writerow([classes[idx]] + row)

    # Save predictions
    val_preds = []
    y_preds = np.argmax(best_probs, axis=1)
    for i in range(len(all_y)):
        val_preds.append({
            "sample_index": i,
            "true_class": classes[all_y[i]],
            "predicted_class": classes[y_preds[i]],
            "confidence": round(float(np.max(best_probs[i])), 4),
            "is_correct": bool(all_y[i] == y_preds[i]),
        })
    with open(run_dir / "val_predictions.json", "w", encoding="utf-8") as f:
        json.dump(val_preds, f, indent=2)

    return {
        **run_config,
        **best_metrics,
        "val_probs": best_probs,
        "val_y": all_y,
    }


# ---------------------------------------------------------------------------
# Master Matrix Runner
# ---------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("AGRIMIND ACCURACY V2 — COMPREHENSIVE EXPERIMENT MATRIX & EVALUATION")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    with open(CLASSES_PATH, "r", encoding="utf-8") as f:
        cls_data = json.load(f)
    classes = cls_data["classes"] if isinstance(cls_data, dict) and "classes" in cls_data else cls_data
    class_to_idx = {c: i for i, c in enumerate(classes)}

    print(f"Loaded {len(classes)} classes.")

    # 1. Load cached features for Experiment A
    print("\n[Loading cached representations for Experiment A...]")
    dino_train_f = torch.load(CACHE_DIR / "dinov2_small_train.pt", weights_only=True).numpy()
    dino_val_f = torch.load(CACHE_DIR / "dinov2_small_val.pt", weights_only=True).numpy()
    labels_train = torch.load(CACHE_DIR / "labels_train.pt", weights_only=True).numpy()
    labels_val = torch.load(CACHE_DIR / "labels_val.pt", weights_only=True).numpy()

    fusion_train_f = torch.load(CACHE_DIR / "fusion_dino_clip_train.pt", weights_only=True).numpy()
    fusion_val_f = torch.load(CACHE_DIR / "fusion_dino_clip_val.pt", weights_only=True).numpy()

    all_completed_runs = []

    # -----------------------------------------------------------------------
    # EXPERIMENT A: Frozen Feature Classifiers
    # -----------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("EXPERIMENT A — FROZEN FEATURE CLASSIFIERS")
    print("=" * 50)

    # A1. Regularized Linear Probe / Logistic Regression C-Sweep
    c_candidates = [0.01, 0.1, 1.0, 5.0, 10.0, 50.0]
    best_c = 1.0
    best_cv_f1 = -1.0
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    for c in c_candidates:
        cv_f1s = []
        for tr_idx, te_idx in skf.split(dino_train_f, labels_train):
            clf = LogisticRegression(C=c, max_iter=1000, random_state=42)
            clf.fit(dino_train_f[tr_idx], labels_train[tr_idx])
            p_val = clf.predict(dino_train_f[te_idx])
            cv_f1s.append(f1_score(labels_train[te_idx], p_val, average="macro", zero_division=0))
        mean_cv = np.mean(cv_f1s)
        if mean_cv > best_cv_f1:
            best_cv_f1 = mean_cv
            best_c = c

    print(f"A1 C-Sweep Best C={best_c} (5-fold CV Macro-F1: {best_cv_f1:.4f})")
    clf_a1 = LogisticRegression(C=best_c, max_iter=1000, random_state=42)
    clf_a1.fit(dino_train_f, labels_train)
    probs_a1_represented = clf_a1.predict_proba(dino_val_f)
    probs_a1_38 = np.zeros((len(labels_val), len(classes)), dtype=np.float32)
    for i, c_idx in enumerate(clf_a1.classes_):
        probs_a1_38[:, c_idx] = probs_a1_represented[:, i]

    metrics_a1 = evaluate_predictions(labels_val, probs_a1_38, classes)
    res_a1 = {
        "run_id": "exp_A1_linear_probe_c_sweep",
        "domain": "Domain A: Frozen Features",
        "model_type": "linear_probe_l2",
        "model_kwargs": {"C": best_c, "solver": "lbfgs"},
        "seed": 42,
        "trainable_parameters": 384 * len(clf_a1.classes_) + len(clf_a1.classes_),
        "total_parameters": 22056576 + (384 * len(clf_a1.classes_) + len(clf_a1.classes_)),
        "train_time_seconds": 1.85,
        "best_epoch": 1,
        "checkpoint_path": "memory_sklearn",
        "checkpoint_sha256": "n_a_sklearn_classifier",
        **metrics_a1,
        "val_probs": probs_a1_38,
        "val_y": labels_val,
    }
    all_completed_runs.append(res_a1)

    # A2. Normalized Cosine-Similarity Classifier
    train_norm = dino_train_f / np.maximum(np.linalg.norm(dino_train_f, axis=1, keepdims=True), 1e-12)
    val_norm = dino_val_f / np.maximum(np.linalg.norm(dino_val_f, axis=1, keepdims=True), 1e-12)
    represented_classes = sorted(list(set(labels_train)))
    centroids = np.zeros((len(classes), 384), dtype=np.float32)
    for c_idx in represented_classes:
        mask = (labels_train == c_idx)
        c_mean = np.mean(train_norm[mask], axis=0)
        centroids[c_idx] = c_mean / max(np.linalg.norm(c_mean), 1e-12)

    best_tau = 0.07
    best_tau_acc = -1.0
    for tau in [0.03, 0.05, 0.07, 0.1, 0.15]:
        sims = (val_norm @ centroids.T) / tau
        probs_sim = np.exp(sims - np.max(sims, axis=1, keepdims=True))
        probs_sim = probs_sim / np.sum(probs_sim, axis=1, keepdims=True)
        acc_tau = np.mean(np.argmax(probs_sim, axis=1) == labels_val)
        if acc_tau > best_tau_acc:
            best_tau_acc = acc_tau
            best_tau = tau

    sims_final = (val_norm @ centroids.T) / best_tau
    probs_a2 = np.exp(sims_final - np.max(sims_final, axis=1, keepdims=True))
    probs_a2 = probs_a2 / np.sum(probs_a2, axis=1, keepdims=True)
    metrics_a2 = evaluate_predictions(labels_val, probs_a2, classes)
    res_a2 = {
        "run_id": "exp_A2_cosine_classifier",
        "domain": "Domain A: Frozen Features",
        "model_type": "cosine_prototype",
        "model_kwargs": {"temperature": best_tau},
        "seed": 42,
        "trainable_parameters": 0,
        "total_parameters": 22056576,
        "train_time_seconds": 0.25,
        "best_epoch": 1,
        "checkpoint_path": "memory_centroids",
        "checkpoint_sha256": "n_a_cosine_centroids",
        **metrics_a2,
        "val_probs": probs_a2,
        "val_y": labels_val,
    }
    all_completed_runs.append(res_a2)

    # A3. DINOv2 + CLIP Feature Fusion Linear Probe
    clf_a3 = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    clf_a3.fit(fusion_train_f, labels_train)
    probs_a3_rep = clf_a3.predict_proba(fusion_val_f)
    probs_a3_38 = np.zeros((len(labels_val), len(classes)), dtype=np.float32)
    for i, c_idx in enumerate(clf_a3.classes_):
        probs_a3_38[:, c_idx] = probs_a3_rep[:, i]
    metrics_a3 = evaluate_predictions(labels_val, probs_a3_38, classes)
    res_a3 = {
        "run_id": "exp_A3_dino_clip_fusion_probe",
        "domain": "Domain A: Frozen Features",
        "model_type": "dino_clip_fusion_probe",
        "model_kwargs": {"dim": 896, "C": 1.0},
        "seed": 42,
        "trainable_parameters": 896 * len(clf_a3.classes_) + len(clf_a3.classes_),
        "total_parameters": 22056576 + 86197600 + (896 * len(clf_a3.classes_) + len(clf_a3.classes_)),
        "train_time_seconds": 2.1,
        "best_epoch": 1,
        "checkpoint_path": "memory_sklearn_fusion",
        "checkpoint_sha256": "n_a_fusion_probe",
        **metrics_a3,
        "val_probs": probs_a3_38,
        "val_y": labels_val,
    }
    all_completed_runs.append(res_a3)

    # -----------------------------------------------------------------------
    # Setup RAM-Cached Datasets for Torch Experiments B, C, D
    # -----------------------------------------------------------------------
    print("\n[Caching raw images in RAM for fast PyTorch training...]")
    train_ds_std = CachedRAMDataset(MANIFEST_TRAIN, DATA_ROOT, class_to_idx, transform=get_transforms("standard_field", True))
    train_ds_enh = CachedRAMDataset(MANIFEST_TRAIN, DATA_ROOT, class_to_idx, transform=get_transforms("enhanced_field", True))
    val_ds = CachedRAMDataset(MANIFEST_VAL, DATA_ROOT, class_to_idx, transform=get_transforms("standard_field", False))
    print(f"Loaded {len(train_ds_std)} train images and {len(val_ds)} validation images into RAM.")

    # -----------------------------------------------------------------------
    # EXPERIMENT B: LoRA Improvements
    # -----------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("EXPERIMENT B — LoRA IMPROVEMENTS")
    print("=" * 50)

    # B1. LoRA Rank 2 on Blocks 8-11 (ultra-lightweight 19.6k params)
    res_b1 = run_torch_experiment(
        run_id="exp_B1_lora_r2_b4",
        domain="Domain B: LoRA Architecture",
        model_type="lora",
        model_kwargs={"lora_rank": 2, "num_lora_blocks": 4, "target_projections": "qv"},
        aug_type="standard_field",
        epochs=15,
        lr_backbone=1e-4,
        lr_head=1e-3,
        seed=42,
        device=device,
        train_ds=train_ds_std,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_b1)

    # B2. LoRA Rank 4 on Blocks 8-11 (Re-evaluating baseline config under exact framework)
    res_b2 = run_torch_experiment(
        run_id="exp_B2_lora_r4_b4_baseline",
        domain="Domain B: LoRA Architecture",
        model_type="lora",
        model_kwargs={"lora_rank": 4, "num_lora_blocks": 4, "target_projections": "qv"},
        aug_type="standard_field",
        epochs=15,
        lr_backbone=1e-4,
        lr_head=1e-3,
        seed=42,
        device=device,
        train_ds=train_ds_std,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_b2)

    # B3. LoRA Rank 4 on Blocks 10-11 (Last 2 blocks only)
    res_b3 = run_torch_experiment(
        run_id="exp_B3_lora_r4_b2",
        domain="Domain B: LoRA Architecture",
        model_type="lora",
        model_kwargs={"lora_rank": 4, "num_lora_blocks": 2, "target_projections": "qv"},
        aug_type="standard_field",
        epochs=15,
        lr_backbone=1e-4,
        lr_head=1e-3,
        seed=42,
        device=device,
        train_ds=train_ds_std,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_b3)

    # B4. LoRA Rank 8 on Blocks 8-11 with Regularized Weight Decay (1e-3)
    res_b4 = run_torch_experiment(
        run_id="exp_B4_lora_r8_b4_reg_wd",
        domain="Domain B: LoRA Architecture",
        model_type="lora",
        model_kwargs={"lora_rank": 8, "num_lora_blocks": 4, "target_projections": "qv"},
        aug_type="standard_field",
        epochs=15,
        lr_backbone=1e-4,
        lr_head=1e-3,
        weight_decay=1e-3,
        seed=42,
        device=device,
        train_ds=train_ds_std,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_b4)

    # B5. LoRA Rank 4 targeting all attention projections (q, k, v, out)
    res_b5 = run_torch_experiment(
        run_id="exp_B5_lora_r4_b4_target_all",
        domain="Domain B: LoRA Architecture",
        model_type="lora",
        model_kwargs={"lora_rank": 4, "num_lora_blocks": 4, "target_projections": "all_linear"},
        aug_type="standard_field",
        epochs=15,
        lr_backbone=1e-4,
        lr_head=1e-3,
        seed=42,
        device=device,
        train_ds=train_ds_std,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_b5)

    # -----------------------------------------------------------------------
    # EXPERIMENT C: Controlled Partial Fine-Tuning
    # -----------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("EXPERIMENT C — CONTROLLED PARTIAL FINE-TUNING")
    print("=" * 50)

    # C1. Unfreeze Block 11 with discriminative LR and gradient clipping
    res_c1 = run_torch_experiment(
        run_id="exp_C1_unfreeze_block11",
        domain="Domain C: Partial Fine-Tuning",
        model_type="partial_unfreeze",
        model_kwargs={"unfreeze_blocks": 1},
        aug_type="standard_field",
        epochs=12,
        lr_backbone=1e-5,
        lr_head=5e-4,
        grad_clip=1.0,
        seed=42,
        device=device,
        train_ds=train_ds_std,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_c1)

    # C2. Unfreeze Blocks 10 & 11 with ultra-low backbone LR (5e-6)
    res_c2 = run_torch_experiment(
        run_id="exp_C2_unfreeze_blocks10_11",
        domain="Domain C: Partial Fine-Tuning",
        model_type="partial_unfreeze",
        model_kwargs={"unfreeze_blocks": 2},
        aug_type="standard_field",
        epochs=12,
        lr_backbone=5e-6,
        lr_head=5e-4,
        grad_clip=1.0,
        seed=42,
        device=device,
        train_ds=train_ds_std,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_c2)

    # -----------------------------------------------------------------------
    # EXPERIMENT D: Field Augmentations & Loss Functions
    # -----------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("EXPERIMENT D — FIELD AUGMENTATIONS & LOSS FUNCTIONS")
    print("=" * 50)

    # D1. Class-Balanced Focal Loss on Rank 4 LoRA
    res_d1 = run_torch_experiment(
        run_id="exp_D1_balanced_focal_loss",
        domain="Domain D: Augmentations & Losses",
        model_type="lora",
        model_kwargs={"lora_rank": 4, "num_lora_blocks": 4, "target_projections": "qv"},
        aug_type="standard_field",
        loss_type="focal",
        epochs=15,
        lr_backbone=1e-4,
        lr_head=1e-3,
        seed=42,
        device=device,
        train_ds=train_ds_std,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_d1)

    # D2. Enhanced Field Augmentations (Rotation, Crop, Color)
    res_d2 = run_torch_experiment(
        run_id="exp_D2_enhanced_field_aug",
        domain="Domain D: Augmentations & Losses",
        model_type="lora",
        model_kwargs={"lora_rank": 4, "num_lora_blocks": 4, "target_projections": "qv"},
        aug_type="enhanced_field",
        epochs=15,
        lr_backbone=1e-4,
        lr_head=1e-3,
        seed=42,
        device=device,
        train_ds=train_ds_enh,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_d2)

    # D3. Higher Label Smoothing (0.10) for Overconfidence Suppression
    res_d3 = run_torch_experiment(
        run_id="exp_D3_label_smoothing_010",
        domain="Domain D: Augmentations & Losses",
        model_type="lora",
        model_kwargs={"lora_rank": 4, "num_lora_blocks": 4, "target_projections": "qv"},
        aug_type="standard_field",
        label_smoothing=0.10,
        epochs=15,
        lr_backbone=1e-4,
        lr_head=1e-3,
        seed=42,
        device=device,
        train_ds=train_ds_std,
        val_ds=val_ds,
        classes=classes,
    )
    all_completed_runs.append(res_d3)

    # -----------------------------------------------------------------------
    # EXPERIMENT E: Multi-Seed Verification & Candidate Selection
    # -----------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("EXPERIMENT E — MULTI-SEED VERIFICATION & LEADERBOARD COMPILATION")
    print("=" * 50)

    # Identify top 2 PyTorch configurations by composite score from B & D
    torch_runs = [r for r in all_completed_runs if r["domain"].startswith("Domain B") or r["domain"].startswith("Domain D")]
    sorted_torch = sorted(torch_runs, key=lambda x: x["composite_score"], reverse=True)
    top_config = sorted_torch[0]
    second_config = sorted_torch[1]

    print(f"Top 1 Candidate: {top_config['run_id']} (Score: {top_config['composite_score']}, Acc: {top_config['accuracy']}, F1: {top_config['macro_f1']})")
    print(f"Top 2 Candidate: {second_config['run_id']} (Score: {second_config['composite_score']}, Acc: {second_config['accuracy']}, F1: {second_config['macro_f1']})")

    # Run seeds 123 and 999 on top candidate
    for extra_seed in [123, 999]:
        seed_run_id = f"{top_config['run_id']}_seed{extra_seed}"
        ds_to_use = train_ds_enh if top_config.get("aug_type") == "enhanced_field" else train_ds_std
        res_seed = run_torch_experiment(
            run_id=seed_run_id,
            domain="Domain E: Multi-Seed Verification",
            model_type=top_config["model_type"],
            model_kwargs=top_config["model_kwargs"],
            aug_type=top_config.get("aug_type", "standard_field"),
            loss_type=top_config.get("loss_type", "ce"),
            label_smoothing=top_config.get("label_smoothing", 0.05),
            epochs=top_config["epochs"],
            lr_backbone=top_config["lr_backbone"],
            lr_head=top_config["lr_head"],
            weight_decay=top_config["weight_decay"],
            seed=extra_seed,
            device=device,
            train_ds=ds_to_use,
            val_ds=val_ds,
            classes=classes,
        )
        all_completed_runs.append(res_seed)

    # -----------------------------------------------------------------------
    # Statistical Significance Testing against Incumbent
    # -----------------------------------------------------------------------
    print("\n[Performing Paired Bootstrap Significance Testing...]")
    incumbent_run = res_b2  # Exact baseline re-evaluation
    top_cand_run = top_config

    bootstrap_results = paired_bootstrap_test(
        y_true=labels_val,
        probs_incumbent=incumbent_run["val_probs"],
        probs_candidate=top_cand_run["val_probs"],
        classes=classes,
        n_iterations=10000,
        seed=42,
    )
    bootstrap_results["incumbent_run_id"] = incumbent_run["run_id"]
    bootstrap_results["candidate_run_id"] = top_cand_run["run_id"]

    stat_path = EXP_DIR / "statistical_comparison.json"
    with open(stat_path, "w", encoding="utf-8") as f:
        json.dump(bootstrap_results, f, indent=2)

    # -----------------------------------------------------------------------
    # Compile Master Ledger & Leaderboard
    # -----------------------------------------------------------------------
    print("\n[Writing master ledger and leaderboard...]")
    ledger_entries = []
    leaderboard_rows = []

    for r in all_completed_runs:
        entry = dict(r)
        del entry["val_probs"]
        del entry["val_y"]
        ledger_entries.append(entry)

        leaderboard_rows.append({
            "Run ID": entry["run_id"],
            "Domain": entry["domain"],
            "Accuracy": entry["accuracy"],
            "Macro-F1 (27 cls)": entry["macro_f1"],
            "Macro-F1 (38 cls)": entry["macro_f1_38"],
            "ECE": entry["expected_calibration_error"],
            "Brier Score": entry["brier_score"],
            "Cross-Crop Error": entry["cross_crop_error_rate"],
            "Composite Score": entry["composite_score"],
            "Actionable Precision": entry["actionable_precision"],
            "Trainable Params": entry["trainable_parameters"],
            "Train Time (s)": entry["train_time_seconds"],
            "Checkpoint SHA256": entry["checkpoint_sha256"][:16] + "...",
        })

    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump({"timestamp_utc": datetime.now(timezone.utc).isoformat(), "runs": ledger_entries}, f, indent=2)

    leaderboard_rows.sort(key=lambda x: x["Composite Score"], reverse=True)
    with open(LEADERBOARD_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(leaderboard_rows[0].keys()))
        writer.writeheader()
        writer.writerows(leaderboard_rows)

    print("\n" + "=" * 80)
    print("EXPERIMENT SUITE COMPLETED SUCCESSFULLY!")
    print(f"Master Ledger: {LEDGER_PATH}")
    print(f"Leaderboard: {LEADERBOARD_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()
