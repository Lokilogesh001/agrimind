"""DINOv2-Small LoRA Fine-Tuning Pipeline for AgriMind Field Adaptation.

Implements parameter-efficient fine-tuning (PEFT) on facebook/dinov2-small:
- Exact LoRALinear wrapper targeting Dinov2Attention actual query and value projections (q_proj, v_proj).
- Supports rank variation (r in {4, 8, 16}) and block depth selection (last 2 vs last 4 blocks).
- Realistic field augmentation: Perspective transform (Jenpoer-style camera tilt simulation),
  color jitter (outdoor sunlight variation), and random resized crop.
- Differential learning rates: Lower for LoRA adapters, higher for linear classifier head.
- Full validation suite reporting: Top-1 Accuracy, Wilson 95% CI, Macro-F1 (eval classes and 38 classes),
  ECE, Cross-crop error rate, and Composite Score.
- Multi-seed confirmation for winning configurations.
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

import numpy as np
from PIL import Image
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from transformers import Dinov2Model

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from evaluation.evaluate_disease_model import compute_ece, compute_wilson_ci
from ml.disease_model import IMAGENET_MEAN, IMAGENET_STD
from ml.research.unified_optimization.experiment_runner import extract_crop_name

MANIFEST_TRAIN = REPO_ROOT / "evaluation" / "manifests" / "field_train_manifest.csv"
MANIFEST_VAL = REPO_ROOT / "evaluation" / "manifests" / "field_val_manifest.csv"
DATA_ROOT = REPO_ROOT / "evaluation" / "datasets" / "field_data" / "images"
EXPERIMENT_DIR = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "lora_experiments"
EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR = EXPERIMENT_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


class LoRALinear(nn.Module):
    """Low-Rank Adaptation wrapper for PyTorch Linear layers."""

    def __init__(self, base_linear: nn.Linear, r: int = 8, lora_alpha: float = 16.0, lora_dropout: float = 0.05):
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


class FieldLeafDataset(Dataset):
    """Dataset for field leaf images with realistic field transforms and RAM caching."""

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
                    img = Image.open(img_path).convert("RGB")
                    self.samples.append((img, class_to_idx[cls_name], cls_name))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int, str]:
        img, cls_idx, cls_name = self.samples[idx]
        if self.transform is not None:
            tensor = self.transform(img)
        else:
            tensor = transforms.ToTensor()(img)
        return tensor, cls_idx, cls_name


def get_field_transforms(is_train: bool = True) -> transforms.Compose:
    """Build preprocessing and augmentation pipelines."""
    if is_train:
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomPerspective(distortion_scale=0.2, p=0.5),  # Jenpoer camera tilt
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15, hue=0.05),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


class DINOv2LoRAClassifier(nn.Module):
    """DINOv2-Small backbone with configurable LoRA adapters and regularized linear head."""

    def __init__(
        self,
        num_classes: int = 38,
        lora_rank: int = 8,
        num_lora_blocks: int = 4,  # Last 4 (8, 9, 10, 11) or last 2 (10, 11) or 0 (frozen)
        lora_alpha: float = 16.0,
        lora_dropout: float = 0.05,
    ):
        super().__init__()
        self.backbone = Dinov2Model.from_pretrained("facebook/dinov2-small")
        self.num_classes = num_classes
        self.lora_rank = lora_rank
        self.num_lora_blocks = num_lora_blocks

        # Freeze all backbone parameters by default
        for p in self.backbone.parameters():
            p.requires_grad = False

        # Apply LoRA to targeted blocks
        if num_lora_blocks > 0 and lora_rank > 0:
            total_layers = len(self.backbone.encoder.layer)  # 12
            start_layer = total_layers - num_lora_blocks
            for idx in range(start_layer, total_layers):
                att = self.backbone.encoder.layer[idx].attention
                att.q_proj = LoRALinear(att.q_proj, r=lora_rank, lora_alpha=lora_alpha, lora_dropout=lora_dropout)
                att.v_proj = LoRALinear(att.v_proj, r=lora_rank, lora_alpha=lora_alpha, lora_dropout=lora_dropout)

        self.classifier = nn.Sequential(
            nn.Dropout(p=0.1),
            nn.Linear(384, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.backbone(x)
        cls_token = out.last_hidden_state[:, 0]
        logits = self.classifier(cls_token)
        return logits


def evaluate_model(
    model: nn.Module,
    val_loader: DataLoader,
    classes: list[str],
    device: torch.device,
) -> dict[str, Any]:
    """Run full evaluation suite on validation set."""
    model.eval()
    y_true = []
    y_pred = []
    probs_list = []
    latencies = []

    with torch.no_grad():
        for x, y, _ in val_loader:
            x = x.to(device)
            t0 = time.perf_counter()
            logits = model(x)
            latencies.append((time.perf_counter() - t0) * 1000.0 / len(y))
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            preds = np.argmax(probs, axis=1)

            y_true.extend(y.numpy().tolist())
            y_pred.extend(preds.tolist())
            probs_list.append(probs)

    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    all_probs = np.vstack(probs_list)

    total_evaluated = len(y_true_arr)
    total_correct = int(np.sum(y_true_arr == y_pred_arr))
    acc = float(total_correct / total_evaluated)
    wilson_ci = compute_wilson_ci(total_correct, total_evaluated, confidence=0.95)

    eval_classes_idx = sorted(list(set(y_true)))
    macro_f1 = float(f1_score(y_true_arr, y_pred_arr, labels=eval_classes_idx, average="macro", zero_division=0))
    macro_f1_38 = float(f1_score(y_true_arr, y_pred_arr, labels=list(range(len(classes))), average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true_arr, y_pred_arr, labels=eval_classes_idx, average="weighted", zero_division=0))
    precision, recall, _, _ = precision_recall_fscore_support(
        y_true_arr, y_pred_arr, labels=eval_classes_idx, average="macro", zero_division=0
    )

    ece_dict = compute_ece(all_probs, y_pred_arr, y_true_arr, n_bins=10)
    ece_val = float(ece_dict["expected_calibration_error"])

    # Cross-crop errors
    cross_crop_errors = sum(
        1 for yt, yp in zip(y_true, y_pred) if yt != yp and extract_crop_name(classes[yt]) != extract_crop_name(classes[yp])
    )
    cross_crop_rate = float(cross_crop_errors / total_evaluated)

    comp_score = round(
        0.40 * macro_f1 + 0.30 * acc + 0.15 * max(0.0, 1.0 - ece_val) + 0.15 * max(0.0, 1.0 - cross_crop_rate), 4
    )

    # 0.60 Confidence gate audit
    confs = np.max(all_probs, axis=1)
    passed_gate = confs >= 0.60
    act_count = int(np.sum(passed_gate))
    act_correct = int(np.sum(passed_gate & (y_true_arr == y_pred_arr)))
    act_prec = float(act_correct / max(act_count, 1))
    safely_rejected = int(np.sum((~passed_gate) & (y_true_arr != y_pred_arr)))
    filter_eff = float(safely_rejected / max(total_evaluated - total_correct, 1))

    return {
        "accuracy": round(acc, 4),
        "wilson_95_ci": wilson_ci,
        "macro_f1": round(macro_f1, 4),
        "macro_f1_38": round(macro_f1_38, 4),
        "macro_precision": round(float(precision), 4),
        "macro_recall": round(float(recall), 4),
        "weighted_f1": round(weighted_f1, 4),
        "expected_calibration_error": round(ece_val, 4),
        "maximum_calibration_error": round(float(ece_dict["maximum_calibration_error"]), 4),
        "composite_score": comp_score,
        "cross_crop_error_rate": round(cross_crop_rate, 4),
        "actionable_precision": round(act_prec, 4),
        "safety_filtering_efficiency": round(filter_eff, 4),
        "mean_latency_ms": round(float(np.mean(latencies)), 2),
    }


def train_run(
    run_id: str,
    lora_rank: int,
    num_lora_blocks: int,
    epochs: int = 15,
    batch_size: int = 16,
    lr_lora: float = 1e-4,
    lr_head: float = 1e-3,
    weight_decay: float = 1e-4,
    label_smoothing: float = 0.05,
    seed: int = 42,
    device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu"),
) -> dict[str, Any]:
    """Train a single DINOv2 LoRA configuration."""
    print(f"\n{'='*70}\n[RUN: {run_id}] Rank={lora_rank} | Blocks={num_lora_blocks} | Seed={seed}\n{'='*70}")

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    classes_file = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "feature_cache" / "classes.json"
    with open(classes_file, "r", encoding="utf-8") as f:
        cls_data = json.load(f)
    classes = cls_data["classes"] if isinstance(cls_data, dict) and "classes" in cls_data else cls_data
    class_to_idx = {c: i for i, c in enumerate(classes)}

    train_ds = FieldLeafDataset(MANIFEST_TRAIN, DATA_ROOT, class_to_idx, transform=get_field_transforms(is_train=True))
    val_ds = FieldLeafDataset(MANIFEST_VAL, DATA_ROOT, class_to_idx, transform=get_field_transforms(is_train=False))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=True)

    model = DINOv2LoRAClassifier(
        num_classes=len(classes),
        lora_rank=lora_rank,
        num_lora_blocks=num_lora_blocks,
    ).to(device)

    # Param groups for differential learning rates
    lora_params = []
    head_params = []
    for name, p in model.named_parameters():
        if p.requires_grad:
            if "classifier" in name:
                head_params.append(p)
            else:
                lora_params.append(p)

    trainable_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_count = sum(p.numel() for p in model.parameters())
    print(f"Trainable params: {trainable_count:,} / {total_count:,} ({trainable_count/total_count*100:.2f}%)")

    param_groups = []
    if lora_params:
        param_groups.append({"params": lora_params, "lr": lr_lora, "weight_decay": weight_decay})
    if head_params:
        param_groups.append({"params": head_params, "lr": lr_head, "weight_decay": weight_decay})

    optimizer = torch.optim.AdamW(param_groups)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    criterion = nn.CrossEntropyLoss(label_smoothing=label_smoothing)

    best_val_score = -1.0
    best_metrics = {}
    best_epoch = 0
    t_start = time.perf_counter()

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
            optimizer.step()

            train_loss += loss.item() * len(y)
            preds = torch.argmax(logits, dim=1)
            train_correct += int(torch.sum(preds == y))
            total_train += len(y)

        scheduler.step()

        # Validation
        val_metrics = evaluate_model(model, val_loader, classes, device)
        comp = val_metrics["composite_score"]
        acc = val_metrics["accuracy"]
        f1 = val_metrics["macro_f1"]
        ece = val_metrics["expected_calibration_error"]

        print(f"Epoch {epoch:02d}/{epochs:02d} | Train Loss: {train_loss/total_train:.4f} Acc: {train_correct/total_train*100:.1f}% | Val Acc: {acc*100:.2f}% F1: {f1:.4f} ECE: {ece:.4f} Score: {comp:.4f}")

        if comp > best_val_score:
            best_val_score = comp
            best_epoch = epoch
            best_metrics = val_metrics
            # Save checkpoint
            ckpt_path = CHECKPOINT_DIR / f"{run_id}_best.pt"
            torch.save(
                {
                    "run_id": run_id,
                    "lora_rank": lora_rank,
                    "num_lora_blocks": num_lora_blocks,
                    "best_epoch": best_epoch,
                    "metrics": best_metrics,
                    "state_dict": model.state_dict(),
                    "seed": seed,
                },
                ckpt_path,
            )

    train_time = round(time.perf_counter() - t_start, 2)
    print(f"[FINISHED {run_id}] Best Epoch {best_epoch} | Score: {best_val_score:.4f} | Time: {train_time}s")

    # Hash checkpoint
    ckpt_path = CHECKPOINT_DIR / f"{run_id}_best.pt"
    with open(ckpt_path, "rb") as f:
        ckpt_sha = hashlib.sha256(f.read()).hexdigest()

    return {
        "run_id": run_id,
        "lora_rank": lora_rank,
        "num_lora_blocks": num_lora_blocks,
        "trainable_parameters": trainable_count,
        "total_parameters": total_count,
        "seed": seed,
        "epochs": epochs,
        "best_epoch": best_epoch,
        "train_time_seconds": train_time,
        "checkpoint_path": str(ckpt_path),
        "checkpoint_sha256": ckpt_sha,
        **best_metrics,
    }


def main():
    print("=" * 70)
    print(" EXPERIMENT 1: DINOv2-SMALL LoRA PARAMETER-EFFICIENT FINE-TUNING")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)} (VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB)")

    # Systematic ablation matrix as requested:
    # 1. Frozen DINOv2 (Rank 0, 0 blocks)
    # 2. LoRA Rank 4 (last 4 blocks)
    # 3. LoRA Rank 8 (last 4 blocks)
    # 4. LoRA Rank 16 (last 4 blocks)
    # 5. LoRA Rank 8 (last 2 blocks)
    experiments = [
        {"run_id": "dinov2_frozen_baseline", "lora_rank": 0, "num_lora_blocks": 0, "seed": 42},
        {"run_id": "dinov2_lora_r4_b4", "lora_rank": 4, "num_lora_blocks": 4, "seed": 42},
        {"run_id": "dinov2_lora_r8_b4", "lora_rank": 8, "num_lora_blocks": 4, "seed": 42},
        {"run_id": "dinov2_lora_r16_b4", "lora_rank": 16, "num_lora_blocks": 4, "seed": 42},
        {"run_id": "dinov2_lora_r8_b2", "lora_rank": 8, "num_lora_blocks": 2, "seed": 42},
    ]

    results = []
    for exp in experiments:
        res = train_run(
            run_id=exp["run_id"],
            lora_rank=exp["lora_rank"],
            num_lora_blocks=exp["num_lora_blocks"],
            seed=exp["seed"],
            epochs=15,
            batch_size=16,
            device=device,
        )
        results.append(res)

    # Identify best configuration
    best_config = max(results, key=lambda r: (r["composite_score"], r["macro_f1"], r["accuracy"]))
    print(f"\n[LEADERBOARD] Leading configuration: {best_config['run_id']} (Score: {best_config['composite_score']})")

    # Multi-seed evaluation for best configuration (seed 101 and seed 202)
    multi_seed_results = [best_config]
    for s in [101, 202]:
        m_run_id = f"{best_config['run_id']}_seed{s}"
        res_m = train_run(
            run_id=m_run_id,
            lora_rank=best_config["lora_rank"],
            num_lora_blocks=best_config["num_lora_blocks"],
            seed=s,
            epochs=15,
            batch_size=16,
            device=device,
        )
        multi_seed_results.append(res_m)

    # Save ledger
    ledger_path = EXPERIMENT_DIR / "lora_experiment_ledger.json"
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "experiments": results,
                "multi_seed_verification": multi_seed_results,
                "winning_configuration": best_config["run_id"],
            },
            f,
            indent=2,
        )
    print(f"--> Saved LoRA ledger to: {ledger_path}")


if __name__ == "__main__":
    main()
