"""AgriMind Unified 38-Class Disease Model Optimization Experiment Runner.

Provides:
- Declarative experiment configuration space generation and validation.
- Strict read-only baseline preservation (never touches ml/artifacts/best.pt).
- Safe GPU execution on NVIDIA RTX 3050 Laptop GPU (4 GB VRAM) with OOM handling and cache recovery.
- Checkpoint saving with SHA-256 verification, metadata, and full reproducibility.
- Automated run ledger, metrics tracking, per-class evaluations, and ranked leaderboard.
- Predeclared composite selection rule:
    Score = 0.40 * Macro_F1_eval + 0.30 * Accuracy + 0.15 * (1 - ECE) + 0.15 * (1 - Cross_Crop_Error)
"""
from __future__ import annotations

import argparse
import copy
import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import gc
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Callable

import numpy as np
from PIL import Image
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import transforms

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.disease_model import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    build_model,
)
from evaluation.evaluate_disease_model import compute_ece, compute_wilson_ci

EXPECTED_BASELINE_SHA256 = "c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e"


def sha256_of_file(file_path: str | Path) -> str:
    """Compute hex SHA-256 digest of a local file."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found for hashing: {p}")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_system_environment() -> dict[str, Any]:
    """Capture hardware, OS, and framework versions."""
    cuda_avail = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_avail else "CPU"
    vram_gb = (
        torch.cuda.get_device_properties(0).total_memory / (1024**3)
        if cuda_avail
        else 0.0
    )
    return {
        "python_version": sys.version,
        "platform": sys.platform,
        "torch_version": torch.__version__,
        "torch_cuda_available": cuda_avail,
        "cuda_device_name": device_name,
        "cuda_vram_gb": round(vram_gb, 4),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def extract_crop_name(class_name: str) -> str:
    """Extract normalized crop name from 38-class taxonomy label."""
    # e.g. "Corn_(maize)___Common_rust_" -> "corn"
    # e.g. "Pepper,_bell___Bacterial_spot" -> "pepper"
    prefix = class_name.split("___")[0]
    cleaned = prefix.replace("_(maize)", "").replace(",_bell", "").replace("_(including_sour)", "").strip().lower()
    return cleaned


@dataclass
class ExperimentConfig:
    """Declarative configuration for a single research experiment."""
    run_id: str
    stage: str  # "stage_a", "stage_b", "stage_c", "stage_d", "finalist"
    description: str = ""
    base_checkpoint: str = "ml/artifacts/best.pt"
    train_manifest: str = "evaluation/manifests/field_train_manifest.csv"
    val_manifest: str = "evaluation/manifests/field_val_manifest.csv"
    data_root: str = "evaluation/datasets/field_data/images"
    output_dir: str = ""
    warmup_epochs: int = 3
    finetune_epochs: int = 6
    batch_size: int = 8
    warmup_lr: float = 1e-4
    finetune_lr: float = 5e-5
    weight_decay: float = 1e-4
    seed: int = 42
    unfreeze_from_block: int = 13  # MobileNetV3 features blocks (13-16 standard, 10-16 deeper, 0 all)
    loss_type: str = "label_smooth_ce"  # "label_smooth_ce", "unweighted_ce", "focal"
    label_smoothing: float = 0.05
    use_class_weights: bool = True
    sampler_type: str = "shuffle"  # "shuffle", "balanced"
    scheduler_type: str = "cosine"  # "cosine", "step", "none"
    augmentation_type: str = "standard"  # "standard", "mild", "strong"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compute_config_hash(self) -> str:
        """Deterministic fingerprint of this configuration."""
        raw = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class FieldDataset(Dataset):
    """Manifest dataset with image integrity checking and sample mapping."""

    def __init__(
        self,
        root_dir: str | Path,
        manifest_path: str | Path,
        class_to_idx: dict[str, int],
        transform: Callable | None = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.manifest_path = Path(manifest_path)
        self.class_to_idx = class_to_idx
        self.transform = transform

        if not self.manifest_path.is_file():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")

        rows = list(csv.DictReader(self.manifest_path.open(encoding="utf-8")))
        self.samples = []
        for r in rows:
            img_p = self.root_dir / r["image_path"]
            if not img_p.is_file():
                continue
            cname = r["mapped_class"]
            if cname not in self.class_to_idx:
                continue
            self.samples.append({
                "path": img_p,
                "class_name": cname,
                "class_idx": self.class_to_idx[cname],
                "group_id": r.get("group_id", ""),
                "sha256": r.get("sha256", ""),
            })

        # In-memory PIL cache to avoid repeated disk reads on each epoch
        self.cached_images: list[Image.Image] = [
            Image.open(s["path"]).convert("RGB") for s in self.samples
        ]

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int, str]:
        item = self.samples[idx]
        img = self.cached_images[idx].copy()
        if self.transform:
            img = self.transform(img)
        return img, item["class_idx"], item["group_id"]


def build_transforms(aug_type: str = "standard") -> tuple[transforms.Compose, transforms.Compose]:
    """Build train and validation transform pipelines."""
    eval_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])

    if aug_type == "mild":
        train_tf = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.RandomResizedCrop(224, scale=(0.85, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])
    elif aug_type == "strong":
        train_tf = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.RandomResizedCrop(224, scale=(0.65, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.15),
            transforms.RandomRotation(degrees=20),
            transforms.ColorJitter(brightness=0.30, contrast=0.30, saturation=0.30, hue=0.10),
            transforms.RandomPerspective(distortion_scale=0.15, p=0.30),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])
    else:  # standard
        train_tf = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.RandomResizedCrop(224, scale=(0.70, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.10),
            transforms.RandomAffine(degrees=15, shear=5),
            transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25, hue=0.08),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])

    return train_tf, eval_tf


class FocalLoss(nn.Module):
    """Focal Loss with optional class weights and gamma focusing parameter."""

    def __init__(self, weight: torch.Tensor | None = None, gamma: float = 2.0, label_smoothing: float = 0.0) -> None:
        super().__init__()
        self.weight = weight
        self.gamma = gamma
        self.label_smoothing = label_smoothing

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = nn.functional.cross_entropy(
            inputs, targets, weight=self.weight, reduction="none", label_smoothing=self.label_smoothing
        )
        pt = torch.exp(-ce_loss)
        focal_loss = ((1.0 - pt) ** self.gamma) * ce_loss
        return focal_loss.mean()


def build_loss_fn(
    loss_type: str,
    weights: torch.Tensor | None,
    label_smoothing: float = 0.05,
) -> nn.Module:
    """Build loss function based on experiment specification."""
    if loss_type == "unweighted_ce":
        return nn.CrossEntropyLoss(label_smoothing=label_smoothing)
    elif loss_type == "focal":
        return FocalLoss(weight=weights, gamma=2.0, label_smoothing=label_smoothing)
    else:  # default "label_smooth_ce"
        return nn.CrossEntropyLoss(weight=weights, label_smoothing=label_smoothing)


def compute_class_weights(labels: list[int], num_classes: int) -> torch.Tensor:
    """Compute balanced class weights with clipping."""
    counts = np.bincount(labels, minlength=num_classes).astype(np.float64)
    counts = np.maximum(counts, 1.0)
    weights = len(labels) / (num_classes * counts)
    weights = np.clip(weights, 0.1, 10.0)
    return torch.tensor(weights, dtype=torch.float32)


def evaluate_model_on_split(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    classes: list[str],
) -> dict[str, Any]:
    """Thorough scientific evaluation of model on a dataset split."""
    model.eval()
    truth_list: list[int] = []
    pred_list: list[int] = []
    conf_list: list[float] = []
    probs_list: list[np.ndarray] = []

    with torch.inference_mode():
        for images, labels, _ in loader:
            images = images.to(device)
            logits = model(images)
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            preds = np.argmax(probs, axis=1)
            confs = np.max(probs, axis=1)

            truth_list.extend(labels.numpy().tolist())
            pred_list.extend(preds.tolist())
            conf_list.extend(confs.tolist())
            probs_list.append(probs)

    if not truth_list:
        return {"accuracy": 0.0, "macro_f1": 0.0, "total_evaluated": 0}

    y_true = np.array(truth_list)
    y_pred = np.array(pred_list)
    y_conf = np.array(conf_list)
    all_probs = np.vstack(probs_list)

    total_evaluated = len(y_true)
    correct_mask = (y_true == y_pred)
    total_correct = int(np.sum(correct_mask))
    acc = float(accuracy_score(y_true, y_pred))
    wilson_ci = compute_wilson_ci(total_correct, total_evaluated, confidence=0.95)

    eval_classes_idx = sorted(list(set(y_true)))
    macro_f1_eval = float(f1_score(y_true, y_pred, labels=eval_classes_idx, average="macro", zero_division=0))
    macro_f1_38 = float(f1_score(y_true, y_pred, labels=list(range(len(classes))), average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    # Error decomposition: cross-crop vs within-crop vs disease-vs-healthy
    cross_crop_errors = 0
    within_crop_errors = 0
    disease_healthy_errors = 0
    total_errors = int(np.sum(~correct_mask))

    for yt, yp in zip(y_true, y_pred):
        if yt != yp:
            c_true = classes[yt]
            c_pred = classes[yp]
            crop_true = extract_crop_name(c_true)
            crop_pred = extract_crop_name(c_pred)

            if crop_true != crop_pred:
                cross_crop_errors += 1
            else:
                within_crop_errors += 1

            is_true_healthy = "healthy" in c_true.lower()
            is_pred_healthy = "healthy" in c_pred.lower()
            if is_true_healthy != is_pred_healthy:
                disease_healthy_errors += 1

    cross_crop_error_rate = round(cross_crop_errors / max(total_evaluated, 1), 4)
    disease_healthy_error_rate = round(disease_healthy_errors / max(total_evaluated, 1), 4)

    prec, rec, f1s, supp = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(classes))), zero_division=0
    )

    per_class = {}
    for idx, cname in enumerate(classes):
        per_class[cname] = {
            "precision": round(float(prec[idx]), 4),
            "recall": round(float(rec[idx]), 4),
            "f1_score": round(float(f1s[idx]), 4),
            "support": int(supp[idx]),
            "evaluated": idx in eval_classes_idx,
        }

    ece_dict = compute_ece(all_probs, y_pred, y_true, n_bins=10)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(classes))))

    # Composite predeclared score:
    # Score = 0.40 * Macro_F1_eval + 0.30 * Acc + 0.15 * (1 - ECE) + 0.15 * (1 - Cross_Crop_Rate)
    ece_val = ece_dict["expected_calibration_error"]
    composite_score = round(
        0.40 * macro_f1_eval
        + 0.30 * acc
        + 0.15 * max(0.0, 1.0 - ece_val)
        + 0.15 * max(0.0, 1.0 - cross_crop_error_rate),
        4,
    )

    return {
        "accuracy": round(acc, 4),
        "wilson_95_ci": wilson_ci,
        "macro_f1": round(macro_f1_eval, 4),
        "macro_f1_all_38": round(macro_f1_38, 4),
        "weighted_f1": round(weighted_f1, 4),
        "mean_confidence": round(float(np.mean(y_conf)), 4),
        "ece": ece_val,
        "mce": ece_dict["maximum_calibration_error"],
        "composite_score": composite_score,
        "cross_crop_errors": cross_crop_errors,
        "cross_crop_error_rate": cross_crop_error_rate,
        "within_crop_errors": within_crop_errors,
        "disease_healthy_errors": disease_healthy_errors,
        "disease_healthy_error_rate": disease_healthy_error_rate,
        "total_errors": total_errors,
        "total_evaluated": total_evaluated,
        "evaluated_classes_count": len(eval_classes_idx),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
    }


def execute_single_run(config: ExperimentConfig, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Execute a single training run according to its ExperimentConfig."""
    start_time = time.time()

    # Safety checks
    base_ckpt = repo_root / config.base_checkpoint
    if not base_ckpt.is_file():
        raise FileNotFoundError(f"Baseline checkpoint not found at: {base_ckpt}")
    base_sha256 = sha256_of_file(base_ckpt)
    if base_sha256 != EXPECTED_BASELINE_SHA256:
        raise ValueError(
            f"SAFETY VIOLATION: Baseline checkpoint sha256 mismatch! Expected {EXPECTED_BASELINE_SHA256}, got {base_sha256}"
        )

    # Disallow using test manifests for training
    locked_manifests = [
        "plantdoc_test_manifest.csv",
        "independent_field_test_manifest.csv",
    ]
    for lm in locked_manifests:
        if lm in config.train_manifest or lm in config.val_manifest:
            raise ValueError(f"LEAKAGE SAFETY VIOLATION: Locked test manifest '{lm}' cannot be used in training/val!")

    # Set seeds
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    out_path = Path(config.output_dir) if config.output_dir else (repo_root / "ml" / "research" / "unified_optimization" / "runs" / config.run_id)
    out_path.mkdir(parents=True, exist_ok=True)

    # Setup logger for run
    log_file = out_path / "run.log"
    logger = logging.getLogger(config.run_id)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    logger.info(f"Starting run {config.run_id} (Stage: {config.stage}) on device {device}")
    logger.info(f"Config: {json.dumps(config.to_dict(), indent=2)}")

    # Load base model payload
    payload = torch.load(str(base_ckpt), map_location="cpu", weights_only=False)
    classes = payload["classes"]
    class_to_idx = payload.get("class_to_idx") or {c: i for i, c in enumerate(classes)}
    num_classes = len(classes)

    # Save classes map
    (out_path / "classes.json").write_text(
        json.dumps({"classes": classes, "class_to_idx": class_to_idx}, indent=2), encoding="utf-8"
    )

    # Prepare datasets
    train_tf, eval_tf = build_transforms(config.augmentation_type)
    train_ds = FieldDataset(repo_root / config.data_root, repo_root / config.train_manifest, class_to_idx, transform=train_tf)
    val_ds = FieldDataset(repo_root / config.data_root, repo_root / config.val_manifest, class_to_idx, transform=eval_tf)

    logger.info(f"Train samples: {len(train_ds)} | Val samples: {len(val_ds)}")

    # Sampler
    train_labels = [item["class_idx"] for item in train_ds.samples]
    if config.sampler_type == "balanced":
        class_counts = np.bincount(train_labels, minlength=num_classes).astype(np.float64)
        class_counts = np.maximum(class_counts, 1.0)
        sample_weights = [1.0 / class_counts[c] for c in train_labels]
        sampler = WeightedRandomSampler(sample_weights, num_samples=len(train_labels), replacement=True)
        train_loader = DataLoader(train_ds, batch_size=config.batch_size, sampler=sampler, num_workers=0)
    else:
        train_loader = DataLoader(train_ds, batch_size=config.batch_size, shuffle=True, num_workers=0)

    val_loader = DataLoader(val_ds, batch_size=config.batch_size, shuffle=False, num_workers=0)

    # Loss weights & criterion
    if config.use_class_weights:
        weights = compute_class_weights(train_labels, num_classes).to(device)
    else:
        weights = None
    criterion = build_loss_fn(config.loss_type, weights, label_smoothing=config.label_smoothing)

    # Instantiate model
    model = build_model(num_classes, pretrained=False).to(device)
    model.load_state_dict(payload["state_dict"])

    # Baseline evaluation before training
    baseline_metrics = evaluate_model_on_split(model, val_loader, device, classes)
    (out_path / "pre_finetune_baseline.json").write_text(
        json.dumps(baseline_metrics, indent=2), encoding="utf-8"
    )
    logger.info(f"Pre-training baseline: Acc={baseline_metrics['accuracy']:.4f}, Macro-F1={baseline_metrics['macro_f1']:.4f}, ECE={baseline_metrics['ece']:.4f}")

    best_ckpt_path = out_path / "checkpoint_best_val.pt"
    best_val_f1 = baseline_metrics["macro_f1"]
    best_val_acc = baseline_metrics["accuracy"]
    best_composite = baseline_metrics["composite_score"]
    best_epoch = 0

    # Initial fallback checkpoint
    torch.save({
        "epoch": 0,
        "state_dict": model.state_dict(),
        "classes": classes,
        "class_to_idx": class_to_idx,
        "val_macro_f1": best_val_f1,
        "val_accuracy": best_val_acc,
        "composite_score": best_composite,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "parent_baseline_sha256": base_sha256,
        "run_id": config.run_id,
        "config": config.to_dict(),
    }, str(best_ckpt_path))

    training_history: list[dict[str, Any]] = []
    current_epoch = 0

    try:
        # =====================================================================
        # STAGE 1: WARMUP CLASSIFIER HEAD
        # =====================================================================
        if config.warmup_epochs > 0:
            logger.info(f"--- Stage 1: Warmup Classifier Head ({config.warmup_epochs} epochs) ---")
            for p in model.features.parameters():
                p.requires_grad = False
            for p in model.classifier.parameters():
                p.requires_grad = True

            opt_warmup = torch.optim.AdamW(
                model.classifier.parameters(), lr=config.warmup_lr, weight_decay=config.weight_decay
            )

            for epoch in range(config.warmup_epochs):
                current_epoch += 1
                model.train()
                running_loss = 0.0
                seen = 0

                for x, y, _ in train_loader:
                    x, y = x.to(device), y.to(device)
                    opt_warmup.zero_grad(set_to_none=True)
                    logits = model(x)
                    loss = criterion(logits, y)
                    loss.backward()
                    opt_warmup.step()
                    running_loss += loss.item() * len(y)
                    seen += len(y)

                train_loss = running_loss / max(seen, 1)
                val_eval = evaluate_model_on_split(model, val_loader, device, classes)

                record = {
                    "stage": "warmup",
                    "epoch": current_epoch,
                    "train_loss": round(train_loss, 4),
                    "val_accuracy": val_eval["accuracy"],
                    "val_macro_f1": val_eval["macro_f1"],
                    "val_macro_f1_38": val_eval["macro_f1_all_38"],
                    "val_ece": val_eval["ece"],
                    "composite_score": val_eval["composite_score"],
                    "cross_crop_rate": val_eval["cross_crop_error_rate"],
                    "mean_confidence": val_eval["mean_confidence"],
                }
                training_history.append(record)
                logger.info(
                    f"Epoch {current_epoch} (Warmup) | Loss: {train_loss:.4f} | Val Acc: {val_eval['accuracy']:.4f} | "
                    f"Val F1: {val_eval['macro_f1']:.4f} | Score: {val_eval['composite_score']:.4f}"
                )

                if val_eval["macro_f1"] > best_val_f1:
                    best_val_f1 = val_eval["macro_f1"]
                    best_val_acc = val_eval["accuracy"]
                    best_composite = val_eval["composite_score"]
                    best_epoch = current_epoch
                    torch.save({
                        "epoch": current_epoch,
                        "state_dict": model.state_dict(),
                        "classes": classes,
                        "class_to_idx": class_to_idx,
                        "val_macro_f1": best_val_f1,
                        "val_accuracy": best_val_acc,
                        "composite_score": best_composite,
                        "stage": "warmup",
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "parent_baseline_sha256": base_sha256,
                        "run_id": config.run_id,
                        "config": config.to_dict(),
                    }, str(best_ckpt_path))

        # =====================================================================
        # STAGE 2: PARTIAL FINE-TUNING
        # =====================================================================
        if config.finetune_epochs > 0:
            logger.info(f"--- Stage 2: Fine-Tuning ({config.finetune_epochs} epochs, unfreeze from block {config.unfreeze_from_block}) ---")
            for idx, child in enumerate(model.features):
                if idx >= config.unfreeze_from_block:
                    for p in child.parameters():
                        p.requires_grad = True
                else:
                    for p in child.parameters():
                        p.requires_grad = False
            for p in model.classifier.parameters():
                p.requires_grad = True

            trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
            frozen_params = sum(p.numel() for p in model.parameters() if not p.requires_grad)
            logger.info(f"Trainable params: {trainable_params:,} | Frozen params: {frozen_params:,}")

            opt_ft = torch.optim.AdamW(
                [p for p in model.parameters() if p.requires_grad],
                lr=config.finetune_lr,
                weight_decay=config.weight_decay,
            )

            if config.scheduler_type == "cosine":
                scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                    opt_ft, T_max=max(config.finetune_epochs, 1), eta_min=1e-6
                )
            elif config.scheduler_type == "step":
                scheduler = torch.optim.lr_scheduler.StepLR(opt_ft, step_size=3, gamma=0.5)
            else:
                scheduler = None

            for epoch in range(config.finetune_epochs):
                current_epoch += 1
                model.train()
                running_loss = 0.0
                seen = 0

                for x, y, _ in train_loader:
                    x, y = x.to(device), y.to(device)
                    opt_ft.zero_grad(set_to_none=True)
                    logits = model(x)
                    loss = criterion(logits, y)
                    loss.backward()
                    opt_ft.step()
                    running_loss += loss.item() * len(y)
                    seen += len(y)

                if scheduler is not None:
                    scheduler.step()

                train_loss = running_loss / max(seen, 1)
                val_eval = evaluate_model_on_split(model, val_loader, device, classes)

                record = {
                    "stage": "finetune",
                    "epoch": current_epoch,
                    "train_loss": round(train_loss, 4),
                    "val_accuracy": val_eval["accuracy"],
                    "val_macro_f1": val_eval["macro_f1"],
                    "val_macro_f1_38": val_eval["macro_f1_all_38"],
                    "val_ece": val_eval["ece"],
                    "composite_score": val_eval["composite_score"],
                    "cross_crop_rate": val_eval["cross_crop_error_rate"],
                    "mean_confidence": val_eval["mean_confidence"],
                }
                training_history.append(record)
                logger.info(
                    f"Epoch {current_epoch} (FT) | Loss: {train_loss:.4f} | Val Acc: {val_eval['accuracy']:.4f} | "
                    f"Val F1: {val_eval['macro_f1']:.4f} | Score: {val_eval['composite_score']:.4f}"
                )

                if val_eval["macro_f1"] > best_val_f1:
                    best_val_f1 = val_eval["macro_f1"]
                    best_val_acc = val_eval["accuracy"]
                    best_composite = val_eval["composite_score"]
                    best_epoch = current_epoch
                    torch.save({
                        "epoch": current_epoch,
                        "state_dict": model.state_dict(),
                        "classes": classes,
                        "class_to_idx": class_to_idx,
                        "val_macro_f1": best_val_f1,
                        "val_accuracy": best_val_acc,
                        "composite_score": best_composite,
                        "stage": "finetune",
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "parent_baseline_sha256": base_sha256,
                        "run_id": config.run_id,
                        "config": config.to_dict(),
                    }, str(best_ckpt_path))

        # Re-evaluate best saved checkpoint
        best_payload = torch.load(str(best_ckpt_path), map_location="cpu", weights_only=False)
        model.load_state_dict(best_payload["state_dict"])
        final_val_results = evaluate_model_on_split(model, val_loader, device, classes)

        # Artifacts
        (out_path / "training_history.json").write_text(json.dumps(training_history, indent=2), encoding="utf-8")
        (out_path / "val_metrics.json").write_text(json.dumps(final_val_results, indent=2), encoding="utf-8")
        (out_path / "config.json").write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")

        if training_history:
            with open(out_path / "training_history.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(training_history[0].keys()))
                w.writeheader()
                w.writerows(training_history)

        with open(out_path / "val_confusion_matrix.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["True\\Pred"] + classes)
            for i, row in enumerate(final_val_results["confusion_matrix"]):
                w.writerow([classes[i]] + row)

        best_ckpt_sha256 = sha256_of_file(best_ckpt_path)
        runtime_sec = round(time.time() - start_time, 2)

        summary = {
            "status": "COMPLETED",
            "run_id": config.run_id,
            "stage": config.stage,
            "config": config.to_dict(),
            "best_epoch": best_epoch,
            "best_val_macro_f1": final_val_results["macro_f1"],
            "best_val_accuracy": final_val_results["accuracy"],
            "best_val_macro_f1_38": final_val_results["macro_f1_all_38"],
            "best_val_weighted_f1": final_val_results["weighted_f1"],
            "best_val_ece": final_val_results["ece"],
            "best_val_mce": final_val_results["mce"],
            "best_composite_score": final_val_results["composite_score"],
            "cross_crop_error_rate": final_val_results["cross_crop_error_rate"],
            "disease_healthy_error_rate": final_val_results["disease_healthy_error_rate"],
            "checkpoint_path": str(best_ckpt_path),
            "checkpoint_sha256": best_ckpt_sha256,
            "runtime_seconds": runtime_sec,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        (out_path / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info(f"Run completed successfully in {runtime_sec}s. Best F1: {final_val_results['macro_f1']:.4f}")

        # Final safety check: baseline checkpoint must remain untouched!
        current_base_sha = sha256_of_file(base_ckpt)
        assert current_base_sha == EXPECTED_BASELINE_SHA256, "CRITICAL: Baseline ml/artifacts/best.pt was modified!"

        return summary

    except torch.cuda.OutOfMemoryError as oom_exc:
        logger.error(f"CUDA OutOfMemoryError in run {config.run_id}: {oom_exc}")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        err_summary = {
            "status": "FAILED_OOM",
            "run_id": config.run_id,
            "stage": config.stage,
            "config": config.to_dict(),
            "error": str(oom_exc),
            "runtime_seconds": round(time.time() - start_time, 2),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        (out_path / "run_summary.json").write_text(json.dumps(err_summary, indent=2), encoding="utf-8")
        return err_summary

    except Exception as exc:
        logger.error(f"Unhandled error in run {config.run_id}: {exc}", exc_info=True)
        err_summary = {
            "status": "FAILED_ERROR",
            "run_id": config.run_id,
            "stage": config.stage,
            "config": config.to_dict(),
            "error": f"{type(exc).__name__}: {exc}",
            "runtime_seconds": round(time.time() - start_time, 2),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        (out_path / "run_summary.json").write_text(json.dumps(err_summary, indent=2), encoding="utf-8")
        return err_summary

    finally:
        # Clean memory
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()


def enumerate_stage_a_grid() -> list[ExperimentConfig]:
    """Generate the full 36-combination Stage A grid.

    Warmup LRs: [0.00005, 0.0001, 0.0002]
    Fine-tuning LRs: [0.00001, 0.00002, 0.00005, 0.0001]
    Weight Decay: [0.00001, 0.0001, 0.001]
    """
    warmup_lrs = [0.00005, 0.0001, 0.0002]
    finetune_lrs = [0.00001, 0.00002, 0.00005, 0.0001]
    weight_decays = [0.00001, 0.0001, 0.001]

    grid: list[ExperimentConfig] = []
    idx = 1
    for w_lr in warmup_lrs:
        for f_lr in finetune_lrs:
            for wd in weight_decays:
                run_id = f"stage_a_{idx:02d}_wlr{w_lr:.5f}_flr{f_lr:.5f}_wd{wd:.5f}"
                cfg = ExperimentConfig(
                    run_id=run_id,
                    stage="stage_a",
                    description=f"Stage A grid search {idx:02d}/36",
                    warmup_epochs=3,
                    finetune_epochs=6,
                    batch_size=8,
                    warmup_lr=w_lr,
                    finetune_lr=f_lr,
                    weight_decay=wd,
                    seed=42,
                    unfreeze_from_block=13,
                    loss_type="label_smooth_ce",
                    label_smoothing=0.05,
                    use_class_weights=True,
                    sampler_type="shuffle",
                    scheduler_type="cosine",
                    augmentation_type="standard",
                )
                grid.append(cfg)
                idx += 1

    return grid


def update_leaderboard_and_ledger(
    workspace_dir: Path,
    all_configs: list[ExperimentConfig],
    results: list[dict[str, Any]],
) -> tuple[Path, Path]:
    """Compile and export run_ledger and leaderboard CSV and JSON."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    ledger_path_json = workspace_dir / "run_ledger.json"
    ledger_path_csv = workspace_dir / "run_ledger.csv"
    leaderboard_path_json = workspace_dir / "leaderboard.json"
    leaderboard_path_csv = workspace_dir / "leaderboard.csv"

    # Save ledger
    ledger_path_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    if results:
        fieldnames = [
            "run_id", "stage", "status", "best_val_macro_f1", "best_val_accuracy",
            "best_val_macro_f1_38", "best_val_ece", "best_composite_score",
            "cross_crop_error_rate", "runtime_seconds", "checkpoint_sha256"
        ]
        with open(ledger_path_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)

    # Compile leaderboard from completed runs
    completed = [r for r in results if r.get("status") == "COMPLETED"]
    # Sort by composite_score descending, then by macro_f1 descending
    completed.sort(key=lambda x: (x.get("best_composite_score", 0), x.get("best_val_macro_f1", 0)), reverse=True)

    leaderboard_path_json.write_text(json.dumps(completed, indent=2), encoding="utf-8")
    if completed:
        lb_fields = [
            "rank", "run_id", "stage", "best_composite_score", "best_val_macro_f1",
            "best_val_accuracy", "best_val_macro_f1_38", "best_val_ece", "best_val_mce",
            "cross_crop_error_rate", "disease_healthy_error_rate", "best_epoch",
            "warmup_lr", "finetune_lr", "weight_decay", "runtime_seconds", "checkpoint_path"
        ]
        lb_rows = []
        for rank, r in enumerate(completed, start=1):
            cfg = r.get("config", {})
            lb_rows.append({
                "rank": rank,
                "run_id": r.get("run_id"),
                "stage": r.get("stage"),
                "best_composite_score": r.get("best_composite_score"),
                "best_val_macro_f1": r.get("best_val_macro_f1"),
                "best_val_accuracy": r.get("best_val_accuracy"),
                "best_val_macro_f1_38": r.get("best_val_macro_f1_38"),
                "best_val_ece": r.get("best_val_ece"),
                "best_val_mce": r.get("best_val_mce"),
                "cross_crop_error_rate": r.get("cross_crop_error_rate"),
                "disease_healthy_error_rate": r.get("disease_healthy_error_rate"),
                "best_epoch": r.get("best_epoch"),
                "warmup_lr": cfg.get("warmup_lr"),
                "finetune_lr": cfg.get("finetune_lr"),
                "weight_decay": cfg.get("weight_decay"),
                "runtime_seconds": r.get("runtime_seconds"),
                "checkpoint_path": r.get("checkpoint_path"),
            })
        with open(leaderboard_path_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=lb_fields)
            w.writeheader()
            w.writerows(lb_rows)

    return leaderboard_path_csv, ledger_path_csv


def run_experiment_suite(
    configs: list[ExperimentConfig],
    workspace_dir: Path | None = None,
    max_runs: int | None = None,
    resume: bool = True,
) -> list[dict[str, Any]]:
    """Execute a list of experiment configurations sequentially with resumption."""
    ws = workspace_dir or (REPO_ROOT / "ml" / "research" / "unified_optimization")
    ws.mkdir(parents=True, exist_ok=True)

    # Save environment info
    (ws / "env_info.json").write_text(json.dumps(get_system_environment(), indent=2), encoding="utf-8")

    # Load existing ledger if present
    ledger_json = ws / "run_ledger.json"
    results_map: dict[str, dict[str, Any]] = {}
    if ledger_json.is_file():
        try:
            for item in json.loads(ledger_json.read_text(encoding="utf-8")):
                results_map[item["run_id"]] = item
        except Exception:
            pass

    executed_count = 0
    all_results: list[dict[str, Any]] = []

    print(f"\n==================================================================")
    print(f" AgriMind Experiment Suite: {len(configs)} total configurations")
    print(f" Workspace: {ws}")
    print(f" Resume mode: {resume} | Max runs limit: {max_runs}")
    print(f"==================================================================\n")

    for i, cfg in enumerate(configs, start=1):
        if max_runs is not None and executed_count >= max_runs:
            print(f"[RUNNER] Max runs limit ({max_runs}) reached. Stopping cleanly.")
            break

        run_dir = ws / "runs" / cfg.run_id
        summary_file = run_dir / "run_summary.json"

        # Check if already completed and resumeable
        if resume and cfg.run_id in results_map and results_map[cfg.run_id].get("status") == "COMPLETED" and summary_file.is_file():
            print(f"[{i}/{len(configs)}] SKIPPING {cfg.run_id} (already completed with Val F1={results_map[cfg.run_id].get('best_val_macro_f1'):.4f})")
            all_results.append(results_map[cfg.run_id])
            continue

        cfg.output_dir = str(run_dir)
        print(f"\n[{i}/{len(configs)}] >>> LAUNCHING: {cfg.run_id}")
        print(f"    Stage: {cfg.stage} | WLR: {cfg.warmup_lr} | FLR: {cfg.finetune_lr} | WD: {cfg.weight_decay}")

        summary = execute_single_run(cfg, repo_root=REPO_ROOT)
        results_map[cfg.run_id] = summary
        all_results.append(summary)
        executed_count += 1

        # Incremental ledger and leaderboard update
        update_leaderboard_and_ledger(ws, configs, list(results_map.values()))

    # Final compilation
    update_leaderboard_and_ledger(ws, configs, list(results_map.values()))
    print(f"\n[RUNNER] Completed {executed_count} new runs. Total evaluated: {len(all_results)}.")
    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AgriMind Unified Disease Optimization Experiment Runner")
    parser.add_argument("--stage", type=str, default="stage_a", choices=["stage_a", "custom"])
    parser.add_argument("--max-runs", type=int, default=None)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    if args.stage == "stage_a":
        grid = enumerate_stage_a_grid()
        run_experiment_suite(grid, max_runs=args.max_runs, resume=not args.no_resume)
