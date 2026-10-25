"""MobileNetV3-Large disease classifier for AgriMind.

Provides:
1. MobileNetV3-Large architecture definition.
2. Robust inference transform and tensor normalization.
3. DiseasePredictor with strict image validation, bounds checking, and corruption protection.
4. Model readiness and health reporting (get_model_health).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from PIL import Image, UnidentifiedImageError
import torch
from torch import nn
from torchvision import models, transforms

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


def build_model(num_classes: int, pretrained: bool = False):
    """Build MobileNetV3-Large model with custom classifier head."""
    weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v3_large(weights=weights)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, num_classes)
    return model


def inference_transform():
    """Inference preprocessing pipeline matching training pipeline."""
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


class DiseasePredictor:
    """Production predictor for crop leaf foliar diseases."""

    def __init__(self, checkpoint: str, confidence_gate: float = 0.60):
        ckpt_path = Path(checkpoint)
        if not ckpt_path.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")

        try:
            payload = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        except Exception as exc:
            raise ValueError(f"Failed to load checkpoint '{checkpoint}': {exc}") from exc

        if not isinstance(payload, dict) or "classes" not in payload or "state_dict" not in payload:
            raise ValueError(f"Incompatible checkpoint '{checkpoint}': missing 'classes' or 'state_dict'")

        self.classes = payload["classes"]
        if not self.classes or not isinstance(self.classes, list):
            raise ValueError(f"Invalid classes in checkpoint '{checkpoint}': must be non-empty list")

        self.model = build_model(len(self.classes), pretrained=False)
        self.model.load_state_dict(payload["state_dict"])
        self.model.eval()
        self.transform = inference_transform()
        self.confidence_gate = confidence_gate
        self.checkpoint_path = str(ckpt_path)

    @torch.inference_mode()
    def predict(self, image_path: str, top_k: int = 3) -> dict[str, Any]:
        """Classify a leaf image with strict input validation."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found at path: {image_path}")

        file_size = path.stat().st_size
        if file_size == 0:
            raise ValueError("Uploaded image file is empty (0 bytes)")
        if file_size > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(f"Image file exceeds maximum size limit ({file_size} > {MAX_IMAGE_SIZE_BYTES})")

        # Validate image decoding and prevent decompression bombs
        try:
            with Image.open(path) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError) as exc:
            raise ValueError(f"Corrupted or unsupported image file: {exc}") from exc

        # Open and convert to RGB
        try:
            with Image.open(path) as img:
                w, h = img.size
                if w < 10 or h < 10:
                    raise ValueError(f"Image resolution too small ({w}x{h}); minimum is 10x10 pixels.")
                if w > 10000 or h > 10000:
                    raise ValueError(f"Image resolution exceeds maximum allowed dimensions ({w}x{h}).")
                image = img.convert("RGB")
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Failed to process image: {exc}") from exc

        tensor = self.transform(image).unsqueeze(0)
        logits = self.model(tensor)
        probs = torch.softmax(logits, dim=1)[0]
        k = min(max(1, top_k), len(self.classes))
        values, indices = torch.topk(probs, k=k)

        results = [
            {"class": self.classes[int(i)], "confidence": round(float(v), 6)}
            for v, i in zip(values, indices)
        ]
        best = results[0]

        return {
            "predicted_class": best["class"],
            "confidence": best["confidence"],
            "actionable": best["confidence"] >= self.confidence_gate,
            "top_k": results,
            "model_architecture": "MobileNetV3-Large",
            "checkpoint": self.checkpoint_path,
        }


def get_model_health(checkpoint_path: str | None = None) -> dict[str, Any]:
    """Inspect and report disease vision model readiness and health."""
    path = checkpoint_path or os.getenv("DISEASE_MODEL_PATH", "ml/artifacts/best.pt")
    ckpt_path = Path(path)

    if not ckpt_path.is_file():
        return {
            "status": "UNAVAILABLE",
            "ready": False,
            "architecture": "MobileNetV3-Large",
            "checkpoint_path": str(ckpt_path),
            "classes_count": 0,
            "classes": [],
            "error": f"Model artifact not found at '{path}'. Genuine model inference cannot run.",
        }

    try:
        data = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        classes = data.get("classes", [])
        if not isinstance(classes, list) or not classes:
            return {
                "status": "INVALID_CHECKPOINT",
                "ready": False,
                "architecture": "MobileNetV3-Large",
                "checkpoint_path": str(ckpt_path),
                "classes_count": 0,
                "classes": [],
                "error": "Checkpoint payload is missing a valid 'classes' list.",
            }
        return {
            "status": "READY",
            "ready": True,
            "architecture": "MobileNetV3-Large",
            "checkpoint_path": str(ckpt_path),
            "file_size_bytes": ckpt_path.stat().st_size,
            "classes_count": len(classes),
            "classes": classes,
            "best_epoch": data.get("best_epoch"),
            "best_val_macro_f1": data.get("best_val_macro_f1"),
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "INCOMPATIBLE_CHECKPOINT",
            "ready": False,
            "architecture": "MobileNetV3-Large",
            "checkpoint_path": str(ckpt_path),
            "classes_count": 0,
            "classes": [],
            "error": f"Failed to inspect checkpoint: {type(exc).__name__}: {exc}",
        }


def save_checkpoint(model, classes, path: str, extra_meta: dict | None = None):
    """Save trained weights and class index mapping."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state_dict": model.state_dict(),
        "classes": classes,
        **(extra_meta or {}),
    }
    torch.save(payload, str(p))
