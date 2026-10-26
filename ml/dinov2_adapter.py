"""DINOv2-Small LoRA Inference Adapter for AgriMind Disease Classification.

Provides:
1. Reconstructed DINOv2-Small backbone with Rank-4 LoRA layers and classification head.
2. Safe offline weight loading without inference-time internet downloads.
3. Strict image validation (non-existent, empty, oversized, corrupted, invalid resolution).
4. Full 38-class probability distribution with finite and sum-to-1 validation.
5. Optional crop-aware probability reweighting, handling unsupported crops and discordant predictions.
6. Ambiguity detection and actionable confidence gating.
7. Diagnostic health inspection (get_dinov2_health).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError
import torch
import torch.nn as nn
from torchvision import transforms
from transformers import Dinov2Model

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
MIN_IMAGE_DIM = 10
MAX_IMAGE_DIM = 10000

# Canonical 38 PlantVillage classes in exact index ordering
PLANTVILLAGE_CLASSES_38 = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Blueberry___healthy",
    "Cherry_(including_sour)___Powdery_mildew",
    "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy",
    "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Peach___Bacterial_spot",
    "Peach___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]

# Supported crop canonical keys and aliases mapping to PlantVillage classes
CROP_ALIASES: dict[str, str] = {
    "apple": "apple",
    "blueberry": "blueberry",
    "cherry": "cherry",
    "sour cherry": "cherry",
    "corn": "corn",
    "maize": "corn",
    "grape": "grape",
    "grapes": "grape",
    "orange": "orange",
    "citrus": "orange",
    "peach": "peach",
    "pepper": "pepper",
    "pepper bell": "pepper",
    "bell pepper": "pepper",
    "capsicum": "pepper",
    "potato": "potato",
    "potatoes": "potato",
    "raspberry": "raspberry",
    "soybean": "soybean",
    "soya": "soybean",
    "squash": "squash",
    "strawberry": "strawberry",
    "strawberries": "strawberry",
    "tomato": "tomato",
    "tomatoes": "tomato",
}


def extract_crop_from_class(class_name: str) -> str:
    """Extract canonical crop name from a PlantVillage class string."""
    raw_crop = class_name.split("___")[0].strip()
    clean = raw_crop.replace("Cherry_(including_sour)", "cherry")
    clean = clean.replace("Corn_(maize)", "corn")
    clean = clean.replace("Pepper,_bell", "pepper")
    return clean.lower()


class LoRALinear(nn.Module):
    """Low-Rank Adaptation wrapper for PyTorch Linear layers."""

    def __init__(
        self,
        base_linear: nn.Linear,
        r: int = 4,
        lora_alpha: float = 16.0,
        lora_dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.base_linear = base_linear
        self.base_linear.weight.requires_grad = False
        if self.base_linear.bias is not None:
            self.base_linear.bias.requires_grad = False
        self.r = r
        self.lora_alpha = lora_alpha
        self.scaling = lora_alpha / r if r > 0 else 1.0
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


class DINOv2LoRAClassifier(nn.Module):
    """DINOv2-Small architecture with injected LoRA adapters and linear classifier."""

    def __init__(
        self,
        num_classes: int = 38,
        lora_rank: int = 4,
        num_lora_blocks: int = 4,
        lora_alpha: float = 16.0,
        local_files_only: bool = True,
    ) -> None:
        super().__init__()
        try:
            self.backbone = Dinov2Model.from_pretrained(
                "facebook/dinov2-small",
                local_files_only=local_files_only,
            )
        except Exception as exc:
            if local_files_only:
                raise RuntimeError(
                    f"DINOv2-Small offline backbone weights not found in local HuggingFace cache: {exc}. "
                    "Inference requires local weights to avoid unverified runtime downloads."
                ) from exc
            self.backbone = Dinov2Model.from_pretrained("facebook/dinov2-small")

        self.num_classes = num_classes
        self.lora_rank = lora_rank
        self.num_lora_blocks = num_lora_blocks

        # Freeze backbone parameters
        for p in self.backbone.parameters():
            p.requires_grad = False

        # Inject LoRA into the final transformer blocks
        if num_lora_blocks > 0 and lora_rank > 0:
            total_layers = len(self.backbone.encoder.layer)
            start_layer = total_layers - num_lora_blocks
            for idx in range(start_layer, total_layers):
                att = self.backbone.encoder.layer[idx].attention
                att.q_proj = LoRALinear(att.q_proj, r=lora_rank, lora_alpha=lora_alpha, lora_dropout=0.0)
                att.v_proj = LoRALinear(att.v_proj, r=lora_rank, lora_alpha=lora_alpha, lora_dropout=0.0)

        self.classifier = nn.Sequential(
            nn.Dropout(p=0.1),
            nn.Linear(384, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.backbone(x)
        cls_token = out.last_hidden_state[:, 0]
        logits = self.classifier(cls_token)
        return logits


def dinov2_inference_transform() -> transforms.Compose:
    """Exact inference preprocessing pipeline for DINOv2."""
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


class DINOv2LoRAPredictor:
    """Inference predictor for DINOv2-Small LoRA candidate."""

    DEFAULT_CHECKPOINT = "ml/research/pretrained_benchmark/lora_experiments/checkpoints/dinov2_lora_r4_b4_best.pt"
    EXPECTED_SHA256 = "8ae555c2054fd518edb5382519cca4fba9d2bff4bc039636fddc4b14edf1aa68"

    def __init__(
        self,
        checkpoint: str | None = None,
        confidence_gate: float = 0.60,
        device: str | None = None,
    ) -> None:
        ckpt_str = checkpoint or self.DEFAULT_CHECKPOINT
        ckpt_path = Path(ckpt_str)
        if not ckpt_path.is_file():
            raise FileNotFoundError(f"DINOv2 LoRA checkpoint not found: {ckpt_str}")

        self.checkpoint_path = str(ckpt_path)
        self.confidence_gate = confidence_gate

        # Device selection
        if device:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Load checkpoint payload
        try:
            payload = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        except Exception as exc:
            raise ValueError(f"Failed to load DINOv2 LoRA checkpoint '{ckpt_str}': {exc}") from exc

        if not isinstance(payload, dict) or "state_dict" not in payload:
            raise ValueError(f"Incompatible checkpoint payload in '{ckpt_str}': missing 'state_dict'")

        self.lora_rank = int(payload.get("lora_rank", 4))
        self.num_lora_blocks = int(payload.get("num_lora_blocks", 4))
        self.model_architecture = "DINOv2-Small-LoRA"
        self.model_version = f"r{self.lora_rank}_b{self.num_lora_blocks}"
        self.best_epoch = payload.get("best_epoch")
        self.metrics = payload.get("metrics", {})
        self.seed = payload.get("seed")

        # Class ordering verification
        classes_file = Path("ml/research/pretrained_benchmark/feature_cache/classes.json")
        if classes_file.is_file():
            try:
                with open(classes_file, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                self.classes = cdata["classes"] if isinstance(cdata, dict) and "classes" in cdata else cdata
            except Exception:
                self.classes = list(PLANTVILLAGE_CLASSES_38)
        else:
            self.classes = list(PLANTVILLAGE_CLASSES_38)

        if len(self.classes) != 38:
            raise ValueError(f"Invalid class count in DINOv2 adapter: expected 38, found {len(self.classes)}")

        # Build architecture and load weights
        self.model = DINOv2LoRAClassifier(
            num_classes=len(self.classes),
            lora_rank=self.lora_rank,
            num_lora_blocks=self.num_lora_blocks,
            local_files_only=True,
        )
        self.model.load_state_dict(payload["state_dict"], strict=True)
        self.model.to(self.device)
        self.model.eval()

        self.transform = dinov2_inference_transform()

        # Build crop-to-indices lookup for fast crop conditioning
        self.crop_to_class_indices: dict[str, list[int]] = {}
        for idx, cls_name in enumerate(self.classes):
            crop_name = extract_crop_from_class(cls_name)
            self.crop_to_class_indices.setdefault(crop_name, []).append(idx)

    def _validate_image_file(self, image_path: str) -> Path:
        """Validate image existence, size, and integrity before processing."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found at path: {image_path}")

        file_size = path.stat().st_size
        if file_size == 0:
            raise ValueError("Uploaded image file is empty (0 bytes)")
        if file_size > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(f"Image file exceeds maximum size limit ({file_size} > {MAX_IMAGE_SIZE_BYTES})")

        # Verify integrity and header
        try:
            with Image.open(path) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError) as exc:
            raise ValueError(f"Corrupted or unsupported image file: {exc}") from exc

        return path

    def _load_and_preprocess(self, path: Path) -> torch.Tensor:
        """Decode image, perform dimension checks, and convert to standardized tensor."""
        try:
            with Image.open(path) as img:
                w, h = img.size
                if w < MIN_IMAGE_DIM or h < MIN_IMAGE_DIM:
                    raise ValueError(f"Image resolution too small ({w}x{h}); minimum is {MIN_IMAGE_DIM}x{MIN_IMAGE_DIM} pixels.")
                if w > MAX_IMAGE_DIM or h > MAX_IMAGE_DIM:
                    raise ValueError(f"Image resolution exceeds maximum allowed dimensions ({w}x{h}).")
                image = img.convert("RGB")
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Failed to process image: {exc}") from exc

        tensor = self.transform(image).unsqueeze(0).to(self.device)
        return tensor

    @torch.inference_mode()
    def predict(
        self,
        image_path: str,
        top_k: int = 5,
        selected_crop: str | None = None,
    ) -> dict[str, Any]:
        """Classify leaf image, returning validated probabilities and optional crop aggregation."""
        t_start = time.perf_counter()

        path = self._validate_image_file(image_path)
        tensor = self._load_and_preprocess(path)

        logits = self.model(tensor)
        raw_probs = torch.softmax(logits, dim=1)[0].cpu().numpy()

        # Validate probabilities are finite and sum to 1.0
        if not np.all(np.isfinite(raw_probs)):
            raise ValueError("Model produced non-finite probability values (NaN or Inf)")

        prob_sum = float(np.sum(raw_probs))
        if not math.isclose(prob_sum, 1.0, rel_tol=1e-3, abs_tol=1e-3):
            raise ValueError(f"Model probabilities do not sum to 1.0 (sum={prob_sum:.6f})")

        # Map all 38 classes
        all_probabilities = {
            self.classes[i]: round(float(raw_probs[i]), 6)
            for i in range(len(self.classes))
        }

        # Unconstrained top-k
        sorted_indices = np.argsort(raw_probs)[::-1]
        k = min(max(1, top_k), len(self.classes))
        unconstrained_top_k = [
            {
                "class": self.classes[int(i)],
                "confidence": round(float(raw_probs[i]), 6),
                "crop": extract_crop_from_class(self.classes[int(i)]),
            }
            for i in sorted_indices[:k]
        ]
        unconstrained_best = unconstrained_top_k[0]

        # Crop Conditioning Logic
        crop_aware_mode = False
        crop_status = "NOT_PROVIDED"
        crop_warning = None
        crop_concordance = None
        conditioned_top_k: list[dict[str, Any]] = []
        final_predicted_class = unconstrained_best["class"]
        final_confidence = unconstrained_best["confidence"]

        if selected_crop and selected_crop.strip():
            crop_clean = selected_crop.strip().lower()
            canonical_crop = CROP_ALIASES.get(crop_clean)

            if canonical_crop and canonical_crop in self.crop_to_class_indices:
                crop_aware_mode = True
                crop_status = "APPLIED"
                crop_indices = self.crop_to_class_indices[canonical_crop]
                crop_prob_mass = float(np.sum(raw_probs[crop_indices]))
                crop_concordance = round(crop_prob_mass, 4)

                # Conditioned probability distribution within the selected crop
                if crop_prob_mass > 1e-8:
                    conditioned_probs = {
                        idx: float(raw_probs[idx]) / crop_prob_mass for idx in crop_indices
                    }
                    sorted_crop_indices = sorted(crop_indices, key=lambda idx: conditioned_probs[idx], reverse=True)
                    conditioned_top_k = [
                        {
                            "class": self.classes[idx],
                            "conditioned_confidence": round(conditioned_probs[idx], 6),
                            "flat_confidence": round(float(raw_probs[idx]), 6),
                            "crop": canonical_crop,
                        }
                        for idx in sorted_crop_indices
                    ]

                    # If crop concordance is reasonable (>= 0.15), use conditioned diagnosis as primary
                    if crop_prob_mass >= 0.15:
                        best_conditioned = conditioned_top_k[0]
                        final_predicted_class = best_conditioned["class"]
                        final_confidence = best_conditioned["conditioned_confidence"]
                    else:
                        # Discordant prediction: visual symptoms indicate another crop
                        unconstrained_crop = unconstrained_best["crop"].capitalize()
                        crop_warning = (
                            f"Visual features strongly indicate {unconstrained_crop} "
                            f"({unconstrained_best['class']}, {unconstrained_best['confidence']*100:.1f}%) "
                            f"rather than entered crop '{selected_crop}' (concordance: {crop_concordance*100:.1f}%). "
                            "Unconstrained diagnosis is retained to avoid erroneous treatment."
                        )
                else:
                    crop_warning = (
                        f"Zero probability mass for entered crop '{selected_crop}' under current visual features. "
                        "Using unconstrained 38-class diagnosis."
                    )
            else:
                crop_status = "UNSUPPORTED_CROP"
                crop_warning = (
                    f"Selected crop '{selected_crop}' is not among the 14 vision-supported crops. "
                    "Unconstrained 38-class classification applied."
                )

        # Ambiguity and Actionability Checks
        detected_crop = extract_crop_from_class(final_predicted_class)
        is_actionable = final_confidence >= self.confidence_gate
        margin = (
            float(unconstrained_top_k[0]["confidence"] - unconstrained_top_k[1]["confidence"])
            if len(unconstrained_top_k) > 1
            else 1.0
        )
        is_ambiguous = (final_confidence < self.confidence_gate) or (margin < 0.15)

        recommendation_note = None
        if is_ambiguous:
            recommendation_note = (
                "Diagnostic confidence is low or visual symptoms are ambiguous. "
                "Review the alternative diagnoses below, retake the photo under diffuse daylight, "
                "or consult a local agronomic extension officer before applying chemical sprays."
            )

        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

        return {
            "predicted_class": final_predicted_class,
            "confidence": round(final_confidence, 4),
            "actionable": is_actionable,
            "crop_detected": detected_crop,
            "selected_crop": selected_crop,
            "crop_aware_mode": crop_aware_mode,
            "crop_status": crop_status,
            "crop_concordance": crop_concordance,
            "crop_warning": crop_warning,
            "ambiguous": is_ambiguous,
            "recommendation_note": recommendation_note,
            "top_k": unconstrained_top_k,
            "conditioned_top_k": conditioned_top_k if crop_aware_mode else [],
            "all_probabilities": all_probabilities,
            "model_architecture": "DINOv2-Small-LoRA",
            "model_version": f"r{self.lora_rank}_b{self.num_lora_blocks}",
            "checkpoint": self.checkpoint_path,
            "latency_ms": latency_ms,
            "device": str(self.device),
        }


def get_dinov2_health(checkpoint_path: str | None = None) -> dict[str, Any]:
    """Inspect and report DINOv2 LoRA model readiness and checkpoint integrity."""
    ckpt_str = checkpoint_path or DINOv2LoRAPredictor.DEFAULT_CHECKPOINT
    ckpt_path = Path(ckpt_str)

    if not ckpt_path.is_file():
        return {
            "status": "UNAVAILABLE",
            "ready": False,
            "model_name": "DINOv2-Small-LoRA",
            "model_version": "r4_b4",
            "checkpoint_path": str(ckpt_path),
            "error": f"Checkpoint not found at '{ckpt_str}'.",
        }

    # Verify offline backbone availability without network downloads
    try:
        _ = Dinov2Model.from_pretrained("facebook/dinov2-small", local_files_only=True)
    except Exception as exc:
        return {
            "status": "BACKBONE_UNAVAILABLE",
            "ready": False,
            "model_name": "DINOv2-Small-LoRA",
            "model_version": "r4_b4",
            "checkpoint_path": str(ckpt_path),
            "error": f"DINOv2-Small backbone weights unavailable offline: {type(exc).__name__}: {exc}",
        }

    try:
        file_size = ckpt_path.stat().st_size
        with open(ckpt_path, "rb") as f:
            file_sha = hashlib.sha256(f.read()).hexdigest()

        payload = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        lora_rank = payload.get("lora_rank")
        num_blocks = payload.get("num_lora_blocks")
        metrics = payload.get("metrics", {})

        return {
            "status": "READY",
            "ready": True,
            "model_name": "DINOv2-Small-LoRA",
            "model_version": f"r{lora_rank}_b{num_blocks}",
            "checkpoint_path": str(ckpt_path),
            "file_size_bytes": file_size,
            "checkpoint_sha256": file_sha,
            "lora_rank": lora_rank,
            "num_lora_blocks": num_blocks,
            "best_epoch": payload.get("best_epoch"),
            "val_accuracy": metrics.get("accuracy"),
            "val_macro_f1": metrics.get("macro_f1"),
            "val_ece": metrics.get("expected_calibration_error"),
            "composite_score": metrics.get("composite_score"),
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "INCOMPATIBLE_CHECKPOINT",
            "ready": False,
            "model_name": "DINOv2-Small-LoRA",
            "model_version": "unknown",
            "checkpoint_path": str(ckpt_path),
            "error": f"Failed to inspect checkpoint: {type(exc).__name__}: {exc}",
        }
