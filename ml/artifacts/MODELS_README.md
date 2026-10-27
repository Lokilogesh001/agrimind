# AgriMind Disease Vision Models — Runtime Requirements & Setup

This directory contains configuration, manifests, and checkpoints for AgriMind's crop disease vision system.

## Active Models

### 1. Default Champion: DINOv2-Small + Rank-4 LoRA (`dinov2_lora`)
- **Role:** Default disease model across all API endpoints and the Next.js UI.
- **Architecture:** Foundation model `facebook/dinov2-small` (Vision Transformer, ViT-S/14, 384-dimensional latent embedding) fine-tuned with Low-Rank Adaptation (LoRA rank $r=4$, scaling $\alpha=8$, dropout $p=0.05$) applied to transformer blocks 8, 9, 10, and 11, paired with a linear classification head for 38 disease/healthy classes.
- **LoRA Adapter Checkpoint:** `ml/artifacts/dinov2_lora_r4_b4_best.pt`
  - Size: 88.48 MB (88,480,982 bytes)
  - SHA-256: `8ae555c2054fd518edb5382519cca4fba9d2bff4bc039636fddc4b14edf1aa68`
- **Backbone Requirement:** `facebook/dinov2-small`
  - Revision commit: `67ab8680145be8a9668d2b8b939922e3eb8c6c58`
  - Automatically fetched from Hugging Face on first run if online.
  - Cached locally in `~/.cache/huggingface/hub/models--facebook--dinov2-small`.
- **Offline / Air-Gapped Setup:**
  1. In an internet-connected environment, download the backbone:
     ```python
     from transformers import AutoModel
     AutoModel.from_pretrained("facebook/dinov2-small")
     ```
  2. Copy the Hugging Face cache folder to the offline machine:
     - Linux/macOS: `~/.cache/huggingface/hub/`
     - Windows: `%USERPROFILE%\.cache\huggingface\hub\`
  3. Set environment variable: `HF_HUB_OFFLINE=1`.

### 2. Rollback Baseline: MobileNetV3-Large (`production`)
- **Role:** Explicit rollback and fallback classifier.
- **Architecture:** `torchvision.models.mobilenet_v3_large(weights=None)` with custom 38-class head.
- **Weights File:** `ml/artifacts/best.pt`
  - Size: 17.20 MB (17,198,293 bytes)
  - SHA-256: `c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e`
- **Usage:**
  - In `.env`: set `DISEASE_MODEL_BACKBONE=production`.
  - In API call: pass `disease_model="production"`.
  - In Next.js UI: select "MobileNetV3 (Rollback)" in the model selector.

---

## Verified Evaluation Benchmark

| Evaluation Dataset | Metric | MobileNetV3 (Baseline) | DINOv2 LoRA (Champion) | Relative Delta |
| :--- | :--- | :---: | :---: | :---: |
| **Field Validation (Held-out)** | Top-1 Accuracy | 39.81% | **64.81%** | +25.00% |
| | Macro-F1 (27 classes) | 0.3760 | **0.6510** | +0.2750 |
| | Expected Calibration Error (ECE) | 0.1420 | **0.0573** | -59.6% (better) |
| **PlantDoc Field Benchmark** | Unconstrained Accuracy | 44.07% | **56.78%** | +12.71% |
| | Macro-F1 | 0.4359 | **0.5532** | +0.1173 |
| | Crop-Constrained Accuracy | 59.32% | **72.46%** | +13.14% |
| **Independent Field Test** | Unconstrained Accuracy | 44.34% | **66.06%** | +21.72% |
| | Macro-F1 | 0.4236 | **0.6301** | +0.2065 |
| | Crop-Constrained Accuracy | 60.18% | **73.30%** | +13.12% |

*Note: Evaluation figures are measured on the project benchmark test sets. Crop-constrained inference filters candidate classes to the verified host crop submitted by the farmer, significantly reducing cross-crop false positives.*
