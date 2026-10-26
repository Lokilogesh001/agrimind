"""Empirical runtime latency, peak memory, and side-by-side inference benchmark.

Compares:
1. Production: MobileNetV3-Large (ml/artifacts/best.pt)
2. Candidate: DINOv2-Small Rank-4 LoRA (dinov2_lora_r4_b4_best.pt)

Environments:
- CPU (Torch CPU threads)
- GPU (CUDA if available)
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import sys
import time
import tracemalloc
from typing import Any

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.disease_model import DiseasePredictor
from ml.dinov2_adapter import DINOv2LoRAPredictor
PROD_CHECKPOINT = REPO_ROOT / "ml" / "artifacts" / "best.pt"
DINO_CHECKPOINT = (
    REPO_ROOT
    / "ml"
    / "research"
    / "pretrained_benchmark"
    / "lora_experiments"
    / "checkpoints"
    / "dinov2_lora_r4_b4_best.pt"
)
OUTPUT_FILE = REPO_ROOT / "ml" / "research" / "pretrained_benchmark" / "runtime_benchmark_results.json"


def find_sample_images() -> list[tuple[str, str, str]]:
    """Locate representative field images across diverse crops."""
    base = REPO_ROOT / "evaluation" / "datasets" / "field_data" / "images"
    candidates = [
        ("Tomato", "Early blight", base / "Tomato Early blight leaf" / "*.jpg"),
        ("Tomato", "Leaf Mold", base / "Tomato mold leaf" / "*.jpg"),
        ("Potato", "Early blight", base / "Potato leaf early blight" / "*.jpg"),
        ("Corn", "Common rust", base / "Corn rust leaf" / "*.jpg"),
        ("Apple", "Apple scab", base / "Apple Scab Leaf" / "*.jpg"),
    ]
    results = []
    for crop, disease, pattern in candidates:
        matches = glob.glob(str(pattern))
        if matches:
            results.append((crop, disease, matches[0]))
    return results


def benchmark_model(
    model_fn,
    image_path: str,
    device_name: str,
    n_warmup: int = 20,
    n_iters: int = 50,
) -> dict[str, Any]:
    """Measure inference latency percentiles and peak memory usage."""
    # Warmup
    for _ in range(n_warmup):
        _ = model_fn(image_path)

    if device_name == "cuda" and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

    tracemalloc.start()
    latencies = []

    for _ in range(n_iters):
        if device_name == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        _ = model_fn(image_path)
        if device_name == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize()
        latencies.append((time.perf_counter() - t0) * 1000.0)

    _, peak_cpu_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_gpu_mb = 0.0
    if device_name == "cuda" and torch.cuda.is_available():
        peak_gpu_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)

    return {
        "device": device_name,
        "n_iterations": n_iters,
        "mean_latency_ms": round(float(np.mean(latencies)), 2),
        "median_latency_ms": round(float(np.median(latencies)), 2),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
        "std_latency_ms": round(float(np.std(latencies)), 2),
        "peak_cpu_ram_mb": round(peak_cpu_bytes / (1024 * 1024), 2),
        "peak_gpu_vram_mb": peak_gpu_mb,
    }


def run_benchmark():
    samples = find_sample_images()
    if not samples:
        print("No sample field images found!")
        return

    test_image = samples[0][2]
    print(f"Benchmarking test image: {test_image}")

    cuda_available = torch.cuda.is_available()
    devices = ["cpu"]
    if cuda_available:
        devices.append("cuda")

    benchmark_data = {"devices": {}, "side_by_side": []}

    for dev in devices:
        print(f"\n--- Benchmarking on {dev.upper()} ---")
        # 1. Production MobileNetV3
        prod_predictor = DiseasePredictor(str(PROD_CHECKPOINT))
        if dev == "cuda":
            prod_predictor.model.to("cuda")
            from PIL import Image
            def prod_fn(p):
                img = Image.open(p).convert("RGB")
                tensor = prod_predictor.transform(img).unsqueeze(0).to("cuda")
                with torch.no_grad():
                    logits = prod_predictor.model(tensor)
                    probs = torch.softmax(logits, dim=1)
                return probs
        else:
            def prod_fn(p):
                return prod_predictor.predict(p)

        prod_stats = benchmark_model(prod_fn, test_image, dev)
        print(f"Production MobileNetV3 ({dev}): {prod_stats['mean_latency_ms']} ms (p95: {prod_stats['p95_latency_ms']} ms)")

        # 2. Candidate DINOv2 LoRA
        dinov2_predictor = DINOv2LoRAPredictor(str(DINO_CHECKPOINT), device=dev)
        dinov2_stats = benchmark_model(
            lambda p: dinov2_predictor.predict(p),
            test_image,
            dev,
        )
        print(f"Candidate DINOv2 LoRA ({dev}): {dinov2_stats['mean_latency_ms']} ms (p95: {dinov2_stats['p95_latency_ms']} ms)")

        benchmark_data["devices"][dev] = {
            "mobilenet_v3": prod_stats,
            "dinov2_lora": dinov2_stats,
        }

    # Side-by-side predictions across representative crops
    print("\n--- Running Side-by-Side Predictions ---")
    prod_pred = DiseasePredictor(str(PROD_CHECKPOINT))
    dino_pred = DINOv2LoRAPredictor(str(DINO_CHECKPOINT), device="cpu")

    for crop, disease, img_path in samples:
        p_res = prod_pred.predict(img_path)
        d_flat = dino_pred.predict(img_path, selected_crop=None)
        d_crop = dino_pred.predict(img_path, selected_crop=crop)

        comparison_entry = {
            "crop": crop,
            "ground_truth_disease": disease,
            "image_file": Path(img_path).name,
            "mobilenet_v3": {
                "predicted_class": p_res["predicted_class"],
                "confidence": p_res["confidence"],
                "actionable": p_res["actionable"],
            },
            "dinov2_lora_unconstrained": {
                "predicted_class": d_flat["predicted_class"],
                "confidence": d_flat["confidence"],
                "actionable": d_flat["actionable"],
            },
            "dinov2_lora_crop_aware": {
                "predicted_class": d_crop["predicted_class"],
                "confidence": d_crop["confidence"],
                "crop_concordance": d_crop["crop_concordance"],
                "crop_status": d_crop["crop_status"],
                "actionable": d_crop["actionable"],
                "crop_warning": d_crop["crop_warning"],
            },
        }
        benchmark_data["side_by_side"].append(comparison_entry)
        print(f"[{crop} - {disease}]")
        print(f"  MobileNetV3:       {p_res['predicted_class']} ({p_res['confidence']*100:.1f}%)")
        print(f"  DINOv2 (Flat):     {d_flat['predicted_class']} ({d_flat['confidence']*100:.1f}%)")
        print(f"  DINOv2 (Crop-Opt): {d_crop['predicted_class']} ({d_crop['confidence']*100:.1f}%) [Concordance: {d_crop['crop_concordance']}]")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)
    print(f"\nBenchmark results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_benchmark()
