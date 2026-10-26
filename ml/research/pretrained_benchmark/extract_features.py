"""AgriMind Foundation Model Benchmark — Visual Feature Extraction and Caching.

Extracts and caches frozen visual representations for:
1. DINOv2-Small (facebook/dinov2-small, 384-dim)
2. CLIP ViT-B/32 (openai/clip-vit-base-patch32, 512-dim)
3. CLIP Text Prototypes across all 38 AgriMind taxonomy classes

Outputs stored under ml/research/pretrained_benchmark/feature_cache/.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F
from torchvision import transforms
from transformers import (
    AutoImageProcessor,
    AutoModel,
    CLIPModel,
    CLIPProcessor,
    CLIPTokenizer,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.research.unified_optimization.experiment_runner import extract_crop_name


def load_manifest(manifest_path: Path, data_root: Path, class_to_idx: dict[str, int]) -> list[dict[str, Any]]:
    samples = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rel = row.get("image_path") or row.get("relative_path")
            p = data_root / rel
            if not p.is_file():
                raise FileNotFoundError(f"Missing image: {p}")
            cls = row.get("mapped_class") or row.get("class_name")
            samples.append({
                "path": str(p),
                "class_name": cls,
                "class_idx": class_to_idx[cls],
                "group_id": row.get("group_id", ""),
            })
    return samples


def extract_dinov2_features(model_id: str, samples: list[dict[str, Any]], device: torch.device, batch_size: int = 16) -> torch.Tensor:
    print(f"[EXTRACT] Loading {model_id}...")
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id).to(device)
    model.eval()

    all_feats = []
    for i in range(0, len(samples), batch_size):
        batch_samples = samples[i : i + batch_size]
        images = [Image.open(s["path"]).convert("RGB") for s in batch_samples]
        inputs = processor(images=images, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            # Use pooler output or CLS token
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                feats = outputs.pooler_output
            else:
                feats = outputs.last_hidden_state[:, 0, :]
            feats = F.normalize(feats, p=2, dim=-1)
            all_feats.append(feats.cpu())

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return torch.cat(all_feats, dim=0)


def extract_clip_features(model_id: str, samples: list[dict[str, Any]], device: torch.device, batch_size: int = 16) -> torch.Tensor:
    print(f"[EXTRACT] Loading {model_id}...")
    processor = CLIPProcessor.from_pretrained(model_id)
    model = CLIPModel.from_pretrained(model_id).to(device)
    model.eval()

    all_feats = []
    for i in range(0, len(samples), batch_size):
        batch_samples = samples[i : i + batch_size]
        images = [Image.open(s["path"]).convert("RGB") for s in batch_samples]
        inputs = processor(images=images, return_tensors="pt").to(device)
        with torch.no_grad():
            out = model.get_image_features(**inputs)
            image_features = out.pooler_output if hasattr(out, "pooler_output") else out
            image_features = F.normalize(image_features, p=2, dim=-1)
            all_feats.append(image_features.cpu())

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return torch.cat(all_feats, dim=0)


def extract_clip_text_prototypes(model_id: str, classes: list[str], device: torch.device) -> torch.Tensor:
    """Generate normalized zero-shot text prototypes for all 38 classes."""
    print(f"[EXTRACT] Generating CLIP text prototypes for 38 classes...")
    model = CLIPModel.from_pretrained(model_id).to(device)
    tokenizer = CLIPTokenizer.from_pretrained(model_id)
    model.eval()

    prompts = []
    for c in classes:
        # e.g. "Apple___Cedar_apple_rust" -> "a leaf of apple with cedar apple rust disease"
        # e.g. "Tomato___healthy" -> "a healthy tomato plant leaf"
        parts = c.split("___")
        crop = parts[0].replace("_", " ").replace("(maize)", "corn").strip()
        disease = parts[1].replace("_", " ").strip()
        if "healthy" in disease.lower():
            text = f"a photo of a healthy {crop} leaf"
        else:
            text = f"a photo of a {crop} leaf infected with {disease}"
        prompts.append(text)

    inputs = tokenizer(prompts, padding=True, return_tensors="pt").to(device)
    with torch.no_grad():
        out_text = model.get_text_features(**inputs)
        text_features = out_text.pooler_output if hasattr(out_text, "pooler_output") else out_text
        text_features = F.normalize(text_features, p=2, dim=-1)

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return text_features.cpu()


def main():
    cache_dir = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "feature_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    base_ckpt = REPO_ROOT / "ml" / "artifacts" / "best.pt"
    base_payload = torch.load(str(base_ckpt), map_location="cpu", weights_only=False)
    classes = base_payload["classes"]
    class_to_idx = {c: i for i, c in enumerate(classes)}

    train_manifest = REPO_ROOT / "evaluation" / "manifests" / "field_train_manifest.csv"
    val_manifest = REPO_ROOT / "evaluation" / "manifests" / "field_val_manifest.csv"
    data_root = REPO_ROOT / "evaluation" / "datasets" / "field_data" / "images"

    train_samples = load_manifest(train_manifest, data_root, class_to_idx)
    val_samples = load_manifest(val_manifest, data_root, class_to_idx)

    train_labels = torch.tensor([s["class_idx"] for s in train_samples], dtype=torch.long)
    val_labels = torch.tensor([s["class_idx"] for s in val_samples], dtype=torch.long)

    torch.save(train_labels, cache_dir / "labels_train.pt")
    torch.save(val_labels, cache_dir / "labels_val.pt")
    (cache_dir / "classes.json").write_text(json.dumps({"classes": classes, "class_to_idx": class_to_idx}, indent=2), encoding="utf-8")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[CACHE] Extracting features on {device}...")

    # 1. DINOv2-Small
    dino_train = extract_dinov2_features("facebook/dinov2-small", train_samples, device)
    dino_val = extract_dinov2_features("facebook/dinov2-small", val_samples, device)
    torch.save(dino_train, cache_dir / "dinov2_small_train.pt")
    torch.save(dino_val, cache_dir / "dinov2_small_val.pt")
    print(f"[CACHE] DINOv2-Small cached: Train shape {dino_train.shape}, Val shape {dino_val.shape}")

    # 2. CLIP ViT-B/32
    clip_train = extract_clip_features("openai/clip-vit-base-patch32", train_samples, device)
    clip_val = extract_clip_features("openai/clip-vit-base-patch32", val_samples, device)
    clip_text_prototypes = extract_clip_text_prototypes("openai/clip-vit-base-patch32", classes, device)
    torch.save(clip_train, cache_dir / "clip_train.pt")
    torch.save(clip_val, cache_dir / "clip_val.pt")
    torch.save(clip_text_prototypes, cache_dir / "clip_text_prototypes.pt")
    print(f"[CACHE] CLIP cached: Train shape {clip_train.shape}, Val shape {clip_val.shape}, Text prototypes {clip_text_prototypes.shape}")

    # 3. Concatenated Fusion Cache
    fusion_train = torch.cat([dino_train, clip_train], dim=-1)
    fusion_val = torch.cat([dino_val, clip_val], dim=-1)
    torch.save(fusion_train, cache_dir / "fusion_dino_clip_train.pt")
    torch.save(fusion_val, cache_dir / "fusion_dino_clip_val.pt")
    print(f"[CACHE] Fusion cached: Train shape {fusion_train.shape}, Val shape {fusion_val.shape}")

    print("\n[FEATURE CACHE COMPLETE] All frozen representations successfully cached!")


if __name__ == "__main__":
    main()
