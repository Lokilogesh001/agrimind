"""MobileNetV3-Large field fine-tuning pipeline for AgriMind Phase 2 research.

Implements two-phase transfer learning on real agricultural field imagery:
- Phase 1: Warmup classifier head with frozen feature backbone.
- Phase 2: Controlled partial fine-tuning of top inverted residual blocks (blocks 13-16).
- Strict non-overwrite rule: Saves candidate checkpoints exclusively under ml/research/.
- Pre-training baseline evaluation on validation split before fine-tuning.
- Real field augmentations, class balancing, label smoothing, and calibration tracking.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

import numpy as np
from PIL import Image
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.disease_model import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    build_model,
)
from evaluation.evaluate_disease_model import compute_ece


class FieldManifestDataset(Dataset):
    """Manifest-backed dataset for field training and validation splits."""

    def __init__(
        self,
        root_dir: str | Path,
        manifest_path: str | Path,
        class_to_idx: dict[str, int],
        transform=None,
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
            })

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int, str]:
        item = self.samples[idx]
        img = Image.open(item["path"]).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, item["class_idx"], item["group_id"]


def make_field_transforms():
    """Field-specific realistic augmentations preserving foliar pathology signatures."""
    train_tf = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomResizedCrop(224, scale=(0.70, 1.0)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.1),
        transforms.RandomAffine(degrees=15, shear=5),
        transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25, hue=0.08),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    return train_tf, eval_tf


def compute_class_weights(labels: list[int], num_classes: int) -> torch.Tensor:
    """Compute balanced class weights based on inverse frequency."""
    counts = np.bincount(labels, minlength=num_classes).astype(np.float64)
    # Avoid zero division
    counts = np.maximum(counts, 1.0)
    weights = len(labels) / (num_classes * counts)
    # Clip extreme ratios
    weights = np.clip(weights, 0.1, 10.0)
    return torch.tensor(weights, dtype=torch.float32)


def evaluate_split(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    classes: list[str],
) -> dict[str, Any]:
    model.eval()
    truth_list = []
    pred_list = []
    conf_list = []
    probs_list = []

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
        return {"accuracy": 0.0, "macro_f1": 0.0}

    y_true = np.array(truth_list)
    y_pred = np.array(pred_list)
    y_conf = np.array(conf_list)
    all_probs = np.vstack(probs_list)

    acc = float(accuracy_score(y_true, y_pred))
    eval_classes_idx = sorted(list(set(y_true)))
    macro_f1 = float(f1_score(y_true, y_pred, labels=eval_classes_idx, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

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
        }

    ece = compute_ece(all_probs, y_pred, y_true, n_bins=10)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(classes))))

    return {
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "mean_confidence": round(float(np.mean(y_conf)), 4),
        "ece": ece["expected_calibration_error"],
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "total_evaluated": len(y_true),
    }


def run_field_finetuning(
    base_checkpoint: str = "ml/artifacts/best.pt",
    train_manifest: str = "evaluation/manifests/field_train_manifest.csv",
    val_manifest: str = "evaluation/manifests/field_val_manifest.csv",
    data_root: str = "evaluation/datasets/field_data/images",
    output_dir: str = "ml/research/candidate_v1",
    warmup_epochs: int = 3,
    finetune_epochs: int = 5,
    batch_size: int = 16,
    warmup_lr: float = 1e-3,
    finetune_lr: float = 1e-4,
    weight_decay: float = 1e-4,
    seed: int = 42,
) -> dict[str, Any]:
    # Reproducibility
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[FIELD-TRAIN] Runtime Device: {device}")

    # 1. Audit and Read Baseline Checkpoint (Strictly Read-Only)
    ckpt_path = Path(base_checkpoint)
    if not ckpt_path.is_file():
        raise FileNotFoundError(f"Baseline checkpoint not found at: {ckpt_path}")

    base_bytes = ckpt_path.read_bytes()
    base_sha256 = hashlib.sha256(base_bytes).hexdigest()
    print(f"[FIELD-TRAIN] Loaded baseline checkpoint: {ckpt_path} (SHA-256: {base_sha256[:16]}...)")

    payload = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    classes = payload["classes"]
    class_to_idx = payload.get("class_to_idx") or {c: i for i, c in enumerate(classes)}
    num_classes = len(classes)

    # Output directory
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 2. Datasets and Loaders
    train_tf, eval_tf = make_field_transforms()
    train_ds = FieldManifestDataset(data_root, train_manifest, class_to_idx, transform=train_tf)
    val_ds = FieldManifestDataset(data_root, val_manifest, class_to_idx, transform=eval_tf)

    print(f"[FIELD-TRAIN] Train set: {len(train_ds)} samples | Val set: {len(val_ds)} samples")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    # Class weights from train distribution
    train_labels = [item["class_idx"] for item in train_ds.samples]
    weights = compute_class_weights(train_labels, num_classes).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights, label_smoothing=0.05)

    # 3. Model Instantiation & Pre-Training Baseline
    model = build_model(num_classes, pretrained=False).to(device)
    model.load_state_dict(payload["state_dict"])

    print("[FIELD-TRAIN] Evaluating pre-finetuning baseline on field validation split...")
    baseline_metrics = evaluate_split(model, val_loader, device, classes)
    print(f"  Baseline Val Accuracy: {baseline_metrics['accuracy']:.4f}")
    print(f"  Baseline Val Macro-F1: {baseline_metrics['macro_f1']:.4f}")
    print(f"  Baseline ECE:          {baseline_metrics['ece']:.4f}")

    (out_path / "pre_finetune_baseline.json").write_text(
        json.dumps(baseline_metrics, indent=2), encoding="utf-8"
    )

    # Save classes map
    (out_path / "classes.json").write_text(
        json.dumps({"classes": classes, "class_to_idx": class_to_idx}, indent=2), encoding="utf-8"
    )

    training_history = []
    best_val_f1 = baseline_metrics["macro_f1"]
    best_ckpt_path = out_path / "checkpoint_best_val.pt"

    # Save initial baseline as best checkpoint fallback
    torch.save({
        "epoch": 0,
        "state_dict": model.state_dict(),
        "classes": classes,
        "class_to_idx": class_to_idx,
        "val_macro_f1": baseline_metrics["macro_f1"],
        "val_accuracy": baseline_metrics["accuracy"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "parent_baseline_sha256": base_sha256,
    }, str(best_ckpt_path))

    # =========================================================================
    # STAGE 1: WARMUP CLASSIFIER HEAD (FROZEN BACKBONE)
    # =========================================================================
    print(f"\n[FIELD-TRAIN] === STAGE 1: Warmup Classifier Head ({warmup_epochs} epochs) ===")
    for param in model.features.parameters():
        param.requires_grad = False
    for param in model.classifier.parameters():
        param.requires_grad = True

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    frozen_params = sum(p.numel() for p in model.parameters() if not p.requires_grad)
    print(f"  Trainable params: {trainable_params:,} | Frozen params: {frozen_params:,}")

    optimizer_warmup = torch.optim.AdamW(
        model.classifier.parameters(), lr=warmup_lr, weight_decay=weight_decay
    )

    current_epoch = 0
    for epoch in range(warmup_epochs):
        current_epoch += 1
        model.train()
        running_loss = 0.0
        seen = 0

        for x, y, _ in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer_warmup.zero_grad(set_to_none=True)
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer_warmup.step()
            running_loss += loss.item() * len(y)
            seen += len(y)

        train_loss = running_loss / max(seen, 1)
        val_eval = evaluate_split(model, val_loader, device, classes)

        record = {
            "stage": "warmup",
            "epoch": current_epoch,
            "train_loss": round(train_loss, 4),
            "val_accuracy": val_eval["accuracy"],
            "val_macro_f1": val_eval["macro_f1"],
            "val_weighted_f1": val_eval["weighted_f1"],
            "val_ece": val_eval["ece"],
            "mean_confidence": val_eval["mean_confidence"],
        }
        training_history.append(record)
        print(f"  Warmup Epoch {current_epoch}/{warmup_epochs} | Loss: {train_loss:.4f} | Val Acc: {val_eval['accuracy']:.4f} | Val F1: {val_eval['macro_f1']:.4f}")

        if val_eval["macro_f1"] > best_val_f1:
            best_val_f1 = val_eval["macro_f1"]
            torch.save({
                "epoch": current_epoch,
                "state_dict": model.state_dict(),
                "classes": classes,
                "class_to_idx": class_to_idx,
                "val_macro_f1": best_val_f1,
                "val_accuracy": val_eval["accuracy"],
                "stage": "warmup",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "parent_baseline_sha256": base_sha256,
            }, str(best_ckpt_path))
            print(f"    --> Saved new best checkpoint (Val F1: {best_val_f1:.4f})")

    # =========================================================================
    # STAGE 2: CONTROLLED PARTIAL FINE-TUNING (UNFREEZE TOP BLOCKS 13-16)
    # =========================================================================
    print(f"\n[FIELD-TRAIN] === STAGE 2: Controlled Partial Fine-Tuning ({finetune_epochs} epochs) ===")
    # Unfreeze blocks 13 through 16 of MobileNetV3 features
    # features contains: 0..16
    for idx, child in enumerate(model.features):
        if idx >= 13:
            for p in child.parameters():
                p.requires_grad = True
        else:
            for p in child.parameters():
                p.requires_grad = False

    trainable_params_s2 = sum(p.numel() for p in model.parameters() if p.requires_grad)
    frozen_params_s2 = sum(p.numel() for p in model.parameters() if not p.requires_grad)
    print(f"  Stage 2 Trainable params: {trainable_params_s2:,} | Frozen params: {frozen_params_s2:,}")

    optimizer_finetune = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=finetune_lr,
        weight_decay=weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer_finetune, T_max=max(finetune_epochs, 1), eta_min=1e-6
    )

    for epoch in range(finetune_epochs):
        current_epoch += 1
        model.train()
        running_loss = 0.0
        seen = 0

        for x, y, _ in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer_finetune.zero_grad(set_to_none=True)
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer_finetune.step()
            running_loss += loss.item() * len(y)
            seen += len(y)

        scheduler.step()
        train_loss = running_loss / max(seen, 1)
        val_eval = evaluate_split(model, val_loader, device, classes)

        record = {
            "stage": "partial_finetune",
            "epoch": current_epoch,
            "train_loss": round(train_loss, 4),
            "val_accuracy": val_eval["accuracy"],
            "val_macro_f1": val_eval["macro_f1"],
            "val_weighted_f1": val_eval["weighted_f1"],
            "val_ece": val_eval["ece"],
            "mean_confidence": val_eval["mean_confidence"],
        }
        training_history.append(record)
        print(f"  Fine-Tune Epoch {current_epoch} | Loss: {train_loss:.4f} | Val Acc: {val_eval['accuracy']:.4f} | Val F1: {val_eval['macro_f1']:.4f}")

        if val_eval["macro_f1"] > best_val_f1:
            best_val_f1 = val_eval["macro_f1"]
            torch.save({
                "epoch": current_epoch,
                "state_dict": model.state_dict(),
                "classes": classes,
                "class_to_idx": class_to_idx,
                "val_macro_f1": best_val_f1,
                "val_accuracy": val_eval["accuracy"],
                "stage": "partial_finetune",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "parent_baseline_sha256": base_sha256,
            }, str(best_ckpt_path))
            print(f"    --> Saved new best checkpoint (Val F1: {best_val_f1:.4f})")

    # Final validation on best saved checkpoint
    best_payload = torch.load(str(best_ckpt_path), map_location="cpu", weights_only=False)
    model.load_state_dict(best_payload["state_dict"])
    final_val_results = evaluate_split(model, val_loader, device, classes)

    # Save artifacts
    (out_path / "training_history.json").write_text(json.dumps(training_history, indent=2), encoding="utf-8")
    (out_path / "val_metrics.json").write_text(json.dumps(final_val_results, indent=2), encoding="utf-8")

    # CSV History
    with open(out_path / "training_history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(training_history[0].keys()))
        w.writeheader()
        w.writerows(training_history)

    # Confusion matrix
    with open(out_path / "val_confusion_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["True\\Pred"] + classes)
        for i, row in enumerate(final_val_results["confusion_matrix"]):
            w.writerow([classes[i]] + row)

    config_info = {
        "base_checkpoint": base_checkpoint,
        "base_checkpoint_sha256": base_sha256,
        "train_manifest": train_manifest,
        "val_manifest": val_manifest,
        "train_samples_count": len(train_ds),
        "val_samples_count": len(val_ds),
        "warmup_epochs": warmup_epochs,
        "finetune_epochs": finetune_epochs,
        "batch_size": batch_size,
        "warmup_lr": warmup_lr,
        "finetune_lr": finetune_lr,
        "weight_decay": weight_decay,
        "seed": seed,
        "output_directory": output_dir,
        "best_checkpoint": str(best_ckpt_path),
        "best_val_macro_f1": round(best_val_f1, 4),
        "pre_finetune_macro_f1": baseline_metrics["macro_f1"],
    }
    (out_path / "training_config.json").write_text(json.dumps(config_info, indent=2), encoding="utf-8")

    # Verify baseline checkpoint integrity was never compromised
    current_base_sha256 = hashlib.sha256(Path(base_checkpoint).read_bytes()).hexdigest()
    assert current_base_sha256 == base_sha256, "FATAL: Baseline checkpoint ml/artifacts/best.pt was modified!"
    print(f"\n[FIELD-TRAIN] Training complete! Baseline ml/artifacts/best.pt preserved untouched.")
    print(f"[FIELD-TRAIN] Best research checkpoint saved to: {best_ckpt_path}")

    return {
        "status": "SUCCESS",
        "pre_finetune_baseline": baseline_metrics,
        "final_validation": final_val_results,
        "config": config_info,
        "history": training_history,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, default="ml/research/candidate_v1")
    parser.add_argument("--warmup-epochs", type=int, default=3)
    parser.add_argument("--finetune-epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--warmup-lr", type=float, default=1e-3)
    parser.add_argument("--finetune-lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    run_field_finetuning(
        output_dir=args.output_dir,
        warmup_epochs=args.warmup_epochs,
        finetune_epochs=args.finetune_epochs,
        batch_size=args.batch_size,
        warmup_lr=args.warmup_lr,
        finetune_lr=args.finetune_lr,
        weight_decay=args.weight_decay,
        seed=args.seed,
    )
