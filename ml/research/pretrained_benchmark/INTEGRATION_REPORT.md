# AgriMind — DINOv2 LoRA Production Default Integration Report

**Date:** 2026-10-26
**Status:** Active Production Default (`dinov2_lora`)
**Active Default Model:** DINOv2-Small Rank-4 LoRA (`dinov2_lora_r4_b4_best.pt`)
**Rollback Baseline Model:** MobileNetV3-Large (`ml/artifacts/best.pt`)

---

## Executive Summary

Based on rigorous empirical validation across held-out field test sets (PlantDoc: 56.78% acc / 0.5532 macro-F1 vs MobileNetV3 44.07% / 0.4359; Independent Field Test: 66.06% acc / 0.6301 macro-F1 vs MobileNetV3 44.34% / 0.4236), **DINOv2-Small with Rank-4 LoRA adaptation on the final 4 transformer blocks is now the active DEFAULT disease classification model throughout AgriMind**.

1. **Active Default Throughout Stack:** Unconfigured advisory requests via API, backend agent graph, model registry, and web interface now automatically execute using DINOv2-Small LoRA without requiring explicit configuration or parameters.
2. **Explicit Rollback Preserved:** MobileNetV3-Large remains fully preserved in `ml/artifacts/best.pt` (SHA-256: `c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e`) as the `production` registry entry. Setting `DISEASE_MODEL_BACKBONE=production` or passing `disease_model="production"` instantly routes traffic to MobileNetV3.
3. **Deterministic Offline Weights & Safety:** DINOv2 backbone weights are loaded strictly from offline local cache (`local_files_only=True`). Incompatible, missing, or corrupted weights report honest `MODEL_UNAVAILABLE` errors rather than silently substituting an unverified model.
4. **Diagnostic Correctness & Crop Constraints:** Default inference is unconstrained across all 38 classes. When an optional diagnostic crop is supplied, probabilities are conditioned with an explicit disclosure note and crop-concordance verification, treating the input as contextual metadata rather than botanical proof.
5. **Full Regression Validation:** All 163 automated Python unit/integration tests and the Next.js frontend TypeScript check (`npm run typecheck`) and production build (`npm run build`) passed with zero errors.

---

## 1. Checkpoint Verification and SHA-256 Hashes

| Model Role | File Path | Expected SHA-256 | Verified SHA-256 | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Active Default** | `ml/research/pretrained_benchmark/lora_experiments/checkpoints/dinov2_lora_r4_b4_best.pt` | `8ae555c2054fd518edb5382519cca4fba9d2bff4bc039636fddc4b14edf1aa68` | `8ae555c2054fd518edb5382519cca4fba9d2bff4bc039636fddc4b14edf1aa68` | **MATCH (ACTIVE DEFAULT)** |
| **Rollback Baseline** | `ml/artifacts/best.pt` | `c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e` | `c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e` | **MATCH (UNTOUCHED ROLLBACK)** |

### Architecture Specification
- **Backbone:** `facebook/dinov2-small` (embedding dimension: 384, 6 heads, 12 blocks).
- **Adaptation:** Rank-4 LoRA with $\alpha=8.0$ applied to `qkv` and `proj` linear layers in blocks 8, 9, 10, and 11.
- **Classification Head:** `LayerNorm(384) -> Linear(384, 38)`.
- **Pretrained Weights:** Loaded strictly from offline local HuggingFace cache (`local_files_only=True`), guaranteeing zero runtime network downloads.

---

## 2. Codebase Modifications and Deliverables

```
ml/
├── dinov2_adapter.py             [UPDATED] Strict local_files_only=True enforcement, offline backbone check in get_dinov2_health
├── model_registry.py             [UPDATED] DEFAULT_MODEL_NAME = "dinov2_lora", aliases (default/rollback), disallow silent fallback
orchestrator/
├── state.py                      [UPDATED] DiseaseResult default architecture = "DINOv2-Small-LoRA", version = "r4_b4"
├── graph.py                      [UPDATED] Passes disease_model to disease_agent, preserves multi-agent advisory synthesis
agents/
├── disease_agent.py              [UPDATED] Routes to registry default (DINOv2), reports active model health dynamically
api/
├── main.py                       [UPDATED] BaseAdvisoryRequest validator, /health/model dynamic routing, /health/models
web/app/
├── components/FarmInputForm.tsx   [UPDATED] Default model = "dinov2_lora", default crop filter = "none" (unconstrained)
├── components/DiseaseActionCard.tsx [UPDATED] Crop constraint disclosure banner, concordance gauge, differential diagnoses
├── page.tsx                      [UPDATED] Passes model & crop options, TypeScript interface updated
tests/
├── test_dinov2_adapter.py        [TESTED] 7 unit tests (checkpoint hash, class order, LoRA wrapper, image validation)
├── test_disease_model_registry.py[UPDATED] 10 integration tests (DINOv2 default, rollback override, health endpoints, observability)
.env / .env.example               [UPDATED] Documented DISEASE_MODEL_BACKBONE=dinov2_lora with rollback guidance
```

---

## 3. Empirical Latency and Memory Benchmark

Empirically measured over 50 iterations on local test environment (Intel Core i5-11400H @ 2.70GHz, NVIDIA GeForce RTX 3050 Laptop GPU, PyTorch 2.11.0+cu128).

| Execution Target | Model Architecture | Mean Latency | Median Latency | p95 Latency | Std Dev | Peak RAM / VRAM |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CPU** | MobileNetV3-Large (Rollback) | **38.86 ms** | 38.47 ms | 43.30 ms | 2.58 ms | 0.30 MB RAM |
| **CPU** | DINOv2-Small LoRA (Default) | **84.77 ms** | 84.55 ms | 89.23 ms | 2.57 ms | 0.34 MB RAM |
| **CUDA (RTX 3050)** | MobileNetV3-Large (Rollback) | **32.75 ms** | 31.90 ms | 38.26 ms | 2.96 ms | 32.98 MB VRAM |
| **CUDA (RTX 3050)** | DINOv2-Small LoRA (Default) | **36.77 ms** | 36.89 ms | 39.32 ms | 1.68 ms | 116.56 MB VRAM |

---

## 4. Side-by-Side Predictions on Field Images

Evaluated on representative field test images from `evaluation/datasets/field_data/images/`:

| Crop & Target Pathogen | Sample Image | Rollback Baseline (MobileNetV3) | DINOv2 LoRA (Unconstrained Default) | DINOv2 LoRA (Crop-Constrained) | Concordance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tomato** — Early Blight | `126689-004-D622CD2F.jpg` | Potato Early Blight (88.4%) ❌ *(Cross-crop error)* | Potato Late Blight (28.0%) ⚠️ *(Low-conf safe reject)* | **Tomato Early Blight (79.9%)** ✅ *(Actionable)* | 0.3154 |
| **Potato** — Early Blight | `0061.jpg` | Grape Black Rot (45.6%) ❌ *(Cross-crop error)* | **Potato Early Blight (53.4%)** ✅ *(Top-1 correct)* | **Potato Early Blight (73.9%)** ✅ *(Actionable)* | 0.7229 |
| **Corn** — Common Rust | `37310253806_04fee91918_b.jpg` | Tomato Early Blight (48.7%) ❌ *(Cross-crop error)* | **Corn Common Rust (65.9%)** ✅ *(Actionable)* | **Corn Common Rust (72.8%)** ✅ *(Actionable)* | 0.9057 |
| **Apple** — Apple Scab | `12-20_apple_scab1.jpg` | Strawberry Leaf Scorch (91.5%) ❌ *(High-conf error)* | **Apple Apple Scab (47.3%)** ✅ *(Top-1 correct)* | **Apple Apple Scab (65.1%)** ✅ *(Actionable)* | 0.7270 |
| **Tomato** — Leaf Mold | `23600077_1572609...jpg` | Grape Black Rot (66.3%) ❌ *(Cross-crop error)* | Tomato healthy (46.7%) ⚠️ *(Non-actionable)* | Tomato healthy (58.6%) ⚠️ *(Non-actionable)* | 0.7960 |

---

## 5. Offline Deployment Setup Instructions

To deploy AgriMind on an air-gapped machine or new server with DINOv2 LoRA enabled:

### Step 1: Copy Candidate and Baseline Checkpoints
Ensure the following files are copied to the target repository:
```bash
# 1. DINOv2 LoRA Checkpoint (12.4 MB)
ml/research/pretrained_benchmark/lora_experiments/checkpoints/dinov2_lora_r4_b4_best.pt
# Verify SHA-256: 8ae555c2054fd518edb5382519cca4fba9d2bff4bc039636fddc4b14edf1aa68

# 2. MobileNetV3 Checkpoint (16.9 MB)
ml/artifacts/best.pt
# Verify SHA-256: c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e
```

### Step 2: Cache DINOv2-Small Backbone Locally
Pre-populate the local HuggingFace cache so that `local_files_only=True` succeeds without network calls:
```python
from transformers import Dinov2Model
Dinov2Model.from_pretrained("facebook/dinov2-small")
```
Or copy the cached directory `models--facebook--dinov2-small` into the destination's HuggingFace cache directory (typically `~/.cache/huggingface/hub/` on Linux/macOS or `%USERPROFILE%\.cache\huggingface\hub\` on Windows).

### Step 3: Verify Environment and Readiness
Run the model readiness inspection:
```bash
python -c "from ml.model_registry import get_registry_status; import json; print(json.dumps(get_registry_status(), indent=2))"
```
Ensure `"is_dinov2_default": true` and `models.dinov2_lora.health.ready == true`.

---

## 6. Test Suite and Build Verification

| Test Suite / Command | Execution Command | Result | Duration |
| :--- | :--- | :--- | :--- |
| **DINOv2 Adapter Unit Tests** | `pytest tests/test_dinov2_adapter.py -v` | **7 / 7 PASSED** | 10.49s |
| **Model Registry & Default Tests** | `pytest tests/test_disease_model_registry.py -v` | **10 / 10 PASSED** | 15.45s |
| **Full Python Regression Suite** | `pytest -v` | **163 / 163 PASSED** | 155.51s |
| **Frontend TypeScript Check** | `npm run typecheck` (in `web/`) | **0 Errors (EXIT 0)** | 3.2s |
| **Frontend Production Build** | `npm run build` (in `web/`) | **SUCCESS (EXIT 0)** | 8.8s |

---

## 7. Rollback Protocol

If operational conditions require reverting to MobileNetV3-Large:
1. **Global Configuration:** Set `DISEASE_MODEL_BACKBONE=production` in `.env` or system environment and restart the backend.
2. **Per-Request Override:** Clients can explicitly supply `"disease_model": "production"` in any API request payload.
3. **Verification:** Inspect `GET /health/model` to confirm `"architecture": "MobileNetV3-Large"`.
