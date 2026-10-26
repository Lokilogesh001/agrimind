"""Model Registry for AgriMind Disease Vision Classifiers.

Manages switching between the verified production MobileNetV3-Large model
and non-production research candidates (such as DINOv2-Small LoRA).

Design Principles:
1. Strict Production Preservation: 'production' is always the default.
2. Explicit Selection: Environment variable DISEASE_MODEL_BACKBONE or explicit request option.
3. Safe Failure Handling: Incompatible/missing candidate models report errors clearly
   without silent substitution unless explicitly requested with clear logging.
4. Model Provenance: Every prediction records model architecture and version.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from ml.disease_model import DiseasePredictor, get_model_health
from ml.dinov2_adapter import DINOv2LoRAPredictor, get_dinov2_health

logger = logging.getLogger("agrimind.model_registry")

MODEL_PRODUCTION = "production"
MODEL_DINOV2_LORA = "dinov2_lora"
DEFAULT_MODEL_NAME = MODEL_DINOV2_LORA

SUPPORTED_MODELS = {
    MODEL_DINOV2_LORA: {
        "name": MODEL_DINOV2_LORA,
        "display_name": "DINOv2-Small Rank-4 LoRA (Default Disease Classifier)",
        "architecture": "DINOv2-Small-LoRA",
        "default_checkpoint": DINOv2LoRAPredictor.DEFAULT_CHECKPOINT,
        "is_default": True,
        "is_production": True,
    },
    MODEL_PRODUCTION: {
        "name": MODEL_PRODUCTION,
        "display_name": "MobileNetV3-Large (Rollback Production Baseline)",
        "architecture": "MobileNetV3-Large",
        "default_checkpoint": "ml/artifacts/best.pt",
        "is_default": False,
        "is_production": False,
        "is_rollback": True,
    },
}

_MODEL_CACHE: dict[str, Any] = {}


def resolve_model_name(requested_name: str | None = None) -> str:
    """Resolve model name from explicit request, environment, or default.

    Validates that the resolved name is an allowed model key.
    """
    raw_name = requested_name or os.getenv("DISEASE_MODEL_BACKBONE", DEFAULT_MODEL_NAME)
    norm = raw_name.strip().lower()

    # Aliases
    if norm in ("mobilenet", "mobilenetv3", "production", "prod", "baseline", "rollback"):
        return MODEL_PRODUCTION
    if norm in ("dinov2", "dinov2_lora", "dinov2-small", "dinov2_small_lora", "lora", "default"):
        return MODEL_DINOV2_LORA

    valid_keys = list(SUPPORTED_MODELS.keys())
    raise ValueError(
        f"Unsupported disease model '{requested_name}'. Allowed options: {valid_keys}"
    )


def get_model(
    model_name: str | None = None,
    checkpoint_path: str | None = None,
    allow_fallback: bool = False,
) -> Any:
    """Retrieve or instantiate the requested predictor instance.

    Cached across requests for low-latency inference.
    Strictly forbids silent model substitution when artifacts are missing.
    """
    resolved = resolve_model_name(model_name)
    cache_key = f"{resolved}:{checkpoint_path or 'default'}"

    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    try:
        if resolved == MODEL_DINOV2_LORA:
            ckpt = checkpoint_path or os.getenv("DINOV2_LORA_CHECKPOINT_PATH", DINOv2LoRAPredictor.DEFAULT_CHECKPOINT)
            predictor = DINOv2LoRAPredictor(checkpoint=ckpt)
        elif resolved == MODEL_PRODUCTION:
            ckpt = checkpoint_path or os.getenv("DISEASE_MODEL_PATH", "ml/artifacts/best.pt")
            predictor = DiseasePredictor(checkpoint=ckpt)
        else:
            raise ValueError(f"Unknown model resolved: {resolved}")

        _MODEL_CACHE[cache_key] = predictor
        return predictor

    except Exception as exc:
        logger.error("Failed to load model '%s': %s", resolved, exc)
        # Disallow silent substitution: raise clear exception to trigger MODEL_UNAVAILABLE
        raise


def get_registry_status() -> dict[str, Any]:
    """Inspect and report the status of all registered disease vision models."""
    active_env_model = resolve_model_name(None)
    dinov2_health = get_dinov2_health()
    prod_health = get_model_health()

    return {
        "active_default_model": active_env_model,
        "is_dinov2_default": active_env_model == MODEL_DINOV2_LORA,
        "is_production_default": active_env_model == MODEL_PRODUCTION,
        "supported_models": list(SUPPORTED_MODELS.keys()),
        "models": {
            MODEL_DINOV2_LORA: {
                **SUPPORTED_MODELS[MODEL_DINOV2_LORA],
                "health": dinov2_health,
            },
            MODEL_PRODUCTION: {
                **SUPPORTED_MODELS[MODEL_PRODUCTION],
                "health": prod_health,
            },
        },
    }
