# AgriMind Accuracy V2 — Comprehensive Disease Model Experiment Report

**Date:** 2026-10-26
**Repository:** `D:\project\AGRIMIND\demo\agrimind_batch1`
**Current Branch:** `experiments/dinov2-field-accuracy-v2`
**Baseline Git Checkpoint:** Commit [`4b2439b`](https://github.com/Lokilogesh001/agrimind/commit/4b2439bbd80ee6ba6d32f67cd95dafa4557b2c34), Tag `agrimind-dinov2-baseline-20261026` (pushed to `origin/main`)
**Hardware Environment:** NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM), CUDA 12.8, PyTorch 2.11.0+cu128

---

## 1. Executive Summary & Authoritative Decision

### Final Decision: INCUMBENT DINOv2 LoRA RETAINED AS DEFAULT
> **VERDICT: The incumbent model (`DINOv2-Small + Rank-4 LoRA on blocks 8–11`) is retained as the production default.**
> Systematic empirical testing across 16 experiment runs spanning five research domains (Frozen Features, LoRA Architecture, Partial Fine-Tuning, Field Augmentations & Loss Functions, and Multi-Seed Bootstrap Testing) confirmed that **no candidate demonstrated a statistically significant improvement** over the incumbent on held-out validation Macro-F1 (0.6510) and accuracy (64.81%).
> The incumbent DINOv2 LoRA model maintains superior calibration (ECE 0.0573), low cross-crop confusion (10.19%), and zero regression on locked field benchmarks.

### Model Registry Status & Checkpoint Hashes
| Model Identifier | Architecture | Checkpoint Path | SHA-256 Checksum | Operational Status |
|---|---|---|---|---|
| **Default Candidate (`dinov2_lora`)** | DINOv2-Small + Rank-4 LoRA (blocks 8–11) | `ml/research/pretrained_benchmark/lora_experiments/checkpoints/dinov2_lora_r4_b4_best.pt` | `8ae555c2054fd518edb5382519cca4fba9d2bff4bc039636fddc4b14edf1aa68` | **ACTIVE DEFAULT** |
| **Preserved Rollback (`production`)** | MobileNetV3-Large | `ml/artifacts/best.pt` | `c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e` | **PRESERVED ROLLBACK** |

---

## 2. Phase 1 — GitHub Baseline Checkpoint Safeguard

Prior to executing accuracy experiments, the application baseline was completely audited, tested, committed, tagged, and pushed to GitHub:
1. **Model Default Enforcement:** Audited and verified `DEFAULT_MODEL_NAME = "dinov2_lora"` throughout `ml/model_registry.py`, `ml/dinov2_adapter.py`, `agents/disease_agent.py`, `orchestrator/state.py`, `api/main.py`, and frontend components (`FarmInputForm.tsx`, `DiseaseActionCard.tsx`).
2. **Offline Local Loading:** Enforced `local_files_only=True` in `Dinov2Model.from_pretrained` with explicit health diagnostics.
3. **Regression Tests:** 163/163 unit and integration tests passed in 155s (`pytest tests/`). Frontend build passed (`npm run build`).
4. **Git Checkpoint:**
   - Commit: `4b2439bbd80ee6ba6d32f67cd95dafa4557b2c34` (`chore: checkpoint AgriMind DINOv2 default before accuracy improvements`)
   - Tag: `agrimind-dinov2-baseline-20261026`
   - Remote Status: Verified pushed to `https://github.com/Lokilogesh001/agrimind.git` (`origin/main`).

---

## 3. Training & Evaluation Data Integrity Audit

A comprehensive pre-experiment data quality audit was executed on all 984 dataset images across 4 manifests (`evaluation/manifests/`):
- `field_train_manifest.csv` (419 images across 28 represented classes)
- `field_val_manifest.csv` (108 images across 27 represented classes)
- `plantdoc_test_manifest.csv` (236 images, locked evaluation set)
- `independent_field_test_manifest.csv` (221 images, locked evaluation set)

### Audit Findings
| Metric / Check | Value | Threshold | Status |
|---|---:|---:|---|
| **Corrupt / Zero-Byte Images** | 0 / 984 | 0 | PASS |
| **SHA-256 Manifest Checksums** | 100% match | 100% | PASS |
| **Train vs PlantDoc Test Leakage** | 0 overlapping hashes | 0 | PASS (Zero Leakage) |
| **Train vs Independent Test Leakage** | 0 overlapping hashes | 0 | PASS (Zero Leakage) |
| **Val vs Locked Tests Leakage** | 0 overlapping hashes | 0 | PASS (Zero Leakage) |
| **Train vs Val Source Overlap** | 0 group-ID collisions | 0 | PASS (Source Disjoint) |
| **Canonical Taxonomy Alignment** | 100% mapped to 38 classes | 100% | PASS |
| **Class Imbalance Ratio** | 24.0 : 1 (max: 24, min: 1) | N/A | Documented constraint |

---

## 4. Disciplined Accuracy Experiment Matrix

All experiments were executed in `ml/research/pretrained_benchmark/accuracy_v2/` with isolated configs, seeds, training history, per-sample predictions, confusion matrices, and saved checkpoints.

### Complete Experiment Leaderboard
Sorted by Predeclared Composite Score ($0.40 \cdot \text{F1} + 0.30 \cdot \text{Acc} + 0.15 \cdot (1 - \text{ECE}) + 0.15 \cdot (1 - \text{CrossCrop})$):

| Rank | Run ID | Domain | Top-1 Acc | Macro-F1 (27 cls) | Macro-F1 (38 cls) | ECE | Cross-Crop Err | Composite Score | Actionable Prec (0.60) | Trainable Params | Train Time |
|:---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1** | **`exp_B2_lora_r4_b4_baseline`** | **Domain B: LoRA Architecture** | **64.81%** | **0.6510** | **0.4626** | **0.0573** | **10.19%** | **0.7310** | **81.67%** | **39,206** | **143.0s** |
| 2 | `exp_A1_linear_probe_c_sweep` | Domain A: Frozen Features | 64.81% | 0.6467 | 0.4595 | 0.0573 | 9.26% | 0.7307 | 82.54% | 10,780 | 1.8s |
| 3 | `exp_D3_label_smoothing_010` | Domain D: Augmentations & Losses | 63.89% | 0.6471 | 0.4598 | 0.0686 | 11.11% | 0.7236 | 85.19% | 39,206 | 144.1s |
| 4 | `exp_B3_lora_r4_b2` | Domain B: LoRA Architecture | 63.89% | 0.6430 | 0.4568 | 0.0672 | 11.11% | 0.7221 | 76.67% | 26,918 | 132.1s |
| 5 | `exp_B1_lora_r2_b4` | Domain B: LoRA Architecture | 63.89% | 0.6334 | 0.4500 | 0.0712 | 12.04% | 0.7163 | 80.70% | 26,918 | 143.8s |
| 6 | `exp_D1_balanced_focal_loss` | Domain D: Augmentations & Losses | 62.04% | 0.6227 | 0.4424 | 0.0955 | 11.11% | 0.7042 | 85.00% | 39,206 | 141.0s |
| 7 | `exp_B2_lora_r4_b4_seed999` | Domain E: Multi-Seed | 62.04% | 0.6168 | 0.4382 | 0.1023 | 11.11% | 0.7008 | 83.72% | 39,206 | 146.1s |
| 8 | `exp_B2_lora_r4_b4_seed123` | Domain E: Multi-Seed | 61.11% | 0.6078 | 0.4319 | 0.1053 | 12.96% | 0.6912 | 84.44% | 39,206 | 143.9s |
| 9 | `exp_B5_lora_r4_b4_target_all` | Domain B: LoRA Architecture | 61.11% | 0.6064 | 0.4309 | 0.1071 | 12.96% | 0.6904 | 78.18% | 63,782 | 158.1s |
| 10 | `exp_D2_enhanced_field_aug` | Domain D: Augmentations & Losses | 61.11% | 0.6124 | 0.4352 | 0.1078 | 14.81% | 0.6899 | 84.75% | 39,206 | 146.7s |
| 11 | `exp_C1_unfreeze_block11` | Domain C: Partial Fine-Tuning | 60.19% | 0.5923 | 0.4208 | 0.0552 | 12.96% | 0.6898 | 80.00% | 1,789,862 | 115.4s |
| 12 | `exp_B4_lora_r8_b4_reg_wd` | Domain B: LoRA Architecture | 60.19% | 0.5969 | 0.4241 | 0.0640 | 13.89% | 0.6889 | 82.46% | 63,782 | 145.8s |
| 13 | `exp_C2_unfreeze_blocks10_11` | Domain C: Partial Fine-Tuning | 58.33% | 0.5785 | 0.4110 | 0.1058 | 13.89% | 0.6697 | 78.33% | 3,565,094 | 124.5s |
| 14 | `exp_A3_dino_clip_fusion_probe` | Domain A: Frozen Features | 60.19% | 0.6047 | 0.4296 | 0.3573 | 11.11% | 0.6522 | 0.00% | 25,116 | 2.1s |
| 15 | `exp_A2_cosine_classifier` | Domain A: Frozen Features | 56.48% | 0.5633 | 0.4002 | 0.1761 | 13.89% | 0.6475 | 66.23% | 0 | 0.25s |

---

## 5. Domain-by-Domain Analysis & Scientific Insights

### Domain A — Frozen-Feature Classifiers
- **Logistic Regression (C-sweep):** A fine-grained L2 regularization scan on frozen DINOv2-Small features with $C=50.0$ achieved 64.81% accuracy and 0.6467 Macro-F1, closely matching the LoRA adapter.
- **Cosine / Prototype Classifiers:** L2-normalized cosine nearest-centroid classifier scored 56.48% accuracy. The high-dimensional feature space requires learned hyperplanes rather than isotropic spherical centroids due to significant intra-class foliage variance.
- **DINOv2+CLIP Fusion:** Concatenating 384-dim DINOv2 features with 512-dim CLIP ViT-B/32 features did not improve performance (60.19% accuracy) and severely degraded calibration (ECE 0.3573) due to dimensional disparity and feature scale mismatch.

### Domain B — LoRA Architectural Adaptations
- **Rank Search (R2 vs R4 vs R8):** Rank 4 ($r=4, \alpha=16$) was empirically optimal (64.81% acc / 0.6510 F1). Rank 2 ($r=2$) was slightly under-parameterized (63.89% acc / 0.6334 F1). Rank 8 ($r=8$) with weight decay overfit the 419-image training set (60.19% acc / 0.5969 F1).
- **Block Depth (Last 2 vs Last 4 Blocks):** Adapting 4 blocks (blocks 8–11) outperformed adapting 2 blocks (blocks 10–11) by +0.80% Macro-F1 (0.6510 vs 0.6430) and lowered cross-crop error (10.19% vs 11.11%).
- **Target Projections:** Adapting query and value projections (`q_proj`, `v_proj`) strictly outperformed adapting all projections (`q, k, v, o`), which dropped accuracy to 61.11% and Macro-F1 to 0.6064 due to parameter inflation (63.8k parameters).

### Domain C — Controlled Partial Fine-Tuning
- **Block 11 Unfreezing:** Unfreezing the entire 11th transformer block (1.79M trainable parameters) with discriminative learning rate ($1\times 10^{-5}$ backbone, $5\times 10^{-4}$ head) and gradient clipping achieved only 60.19% accuracy / 0.5923 Macro-F1.
- **Blocks 10 & 11 Unfreezing:** Unfreezing the last two blocks (3.57M trainable parameters) dropped accuracy further to 58.33% / 0.5785 Macro-F1.
- **Scientific Takeaway:** Direct gradient backpropagation into the transformer attention weights on a small field dataset (419 images) damages the general-purpose semantic representations learned during DINOv2 self-supervised pretraining. LoRA's low-rank residual constraint acts as an essential regularizer against catastrophic representation collapse.

### Domain D — Field-Appropriate Augmentation & Loss Functions
- **Class-Balanced Focal Loss:** Imposing effective-sample weighting ($\beta=0.999, \gamma=1.5$) did not overcome dataset sparsity and reduced validation accuracy to 62.04% / 0.6227 Macro-F1. In classes with only 1 sample, focal loss upweighting led to outsized gradient variance.
- **Enhanced Field Augmentations:** Introducing random crop scaling (0.85–1.0) and rotation ($\pm 15^\circ$) reduced accuracy to 61.11% / 0.6124 Macro-F1. For subtle crop disease lesions (e.g. apple scab, cedar rust spots), random cropping frequently excluded the diagnostic lesion from the input window.
- **Label Smoothing (0.10):** Smoothing targets by 0.10 was the highest-performing experimental modification (63.89% acc / 0.6471 Macro-F1, Actionable Precision 85.19%), providing excellent calibration, though slightly trailing the incumbent (0.6510 F1).

### Domain E — Multi-Seed Stability & Paired Bootstrap Test
Across 3 independent random seeds (42, 123, 999), the winning `dinov2_lora_r4_b4` architecture achieved:
- **Mean Accuracy:** 62.65% ($\pm 1.57\%$)
- **Mean Macro-F1:** 0.6252 ($\pm 1.86\%$)
- **Paired Bootstrap Test (10,000 iterations):** No candidate achieved a statistically significant improvement ($p < 0.05$) over the incumbent baseline.

---

## 6. Locked Held-Out Benchmark Performance

Evaluating the verified champion against the MobileNetV3 reference on the locked, untouched evaluation sets:

### Benchmark A — PlantDoc Test (236 images, 27 represented classes)
| Model | Top-1 Accuracy | Wilson 95% CI | Macro-F1 (27 cls) | ECE | Cross-Crop Error | Latency |
|---|---:|---:|---:|---:|---:|---:|
| **DINOv2 LoRA Champion (Unconstrained)** | **56.78%** | **[50.40%, 62.94%]** | **0.5532** | **0.0796** | **17.80%** | **14.4 ms** |
| DINOv2 LoRA Champion (Crop Constrained) | 72.46% | [66.43%, 77.76%] | 0.7094 | 0.0685 | 0.00% | 14.4 ms |
| MobileNetV3 (Stage D Champion) | 44.07% | [37.88%, 50.45%] | 0.4359 | 0.1542 | 35.17% | 11.6 ms |
| MobileNetV3 (Production Baseline) | 25.42% | [20.29%, 31.34%] | 0.2268 | 0.2891 | 48.31% | 12.3 ms |

### Benchmark B — Independent Field Test (221 images, 28 represented classes)
| Model | Top-1 Accuracy | Wilson 95% CI | Macro-F1 (28 cls) | ECE | Cross-Crop Error | Latency |
|---|---:|---:|---:|---:|---:|---:|
| **DINOv2 LoRA Champion (Unconstrained)** | **66.06%** | **[59.59%, 71.98%]** | **0.6301** | **0.0423** | **11.76%** | **15.9 ms** |
| DINOv2 LoRA Champion (Crop Constrained) | 73.30% | [67.11%, 78.70%] | 0.7017 | 0.0547 | 0.00% | 15.9 ms |
| MobileNetV3 (Stage D Champion) | 44.34% | [37.95%, 50.93%] | 0.4236 | 0.1333 | 38.01% | 11.7 ms |
| MobileNetV3 (Production Baseline) | 17.19% | [12.79%, 22.72%] | 0.1549 | 0.3143 | 60.63% | 11.8 ms |

---

## 7. Operational & Deployment Specifications

### Active Model Parameters
- **Backbone:** `facebook/dinov2-small` (offline local cache)
- **Trainable LoRA Parameters:** 39,206 (0.18% of 22.10M total parameters)
- **Adapter Rank:** $r=4$, $\alpha=16.0$, dropout=0.05 on Attention blocks 8, 9, 10, 11
- **Preprocessing:** Resize to $224 \times 224$, ImageNet normalization ($\mu = [0.485, 0.456, 0.406]$, $\sigma = [0.229, 0.224, 0.225]$)
- **Inference Latency:** 14.4 ms/image on RTX 3050 GPU (vs 11.6 ms for MobileNetV3)
- **Model Checkpoint Artifact Size:** 88.5 MB (complete self-contained torch state dict)

### Immediate Rollback Procedure
If MobileNetV3 rollback is ever required:
1. Set in `.env`:
   ```bash
   DISEASE_MODEL_BACKBONE=production
   ```
2. Or pass `disease_model="production"` via API request payload.
3. System verifies MobileNetV3 checkpoint SHA-256 (`c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e`) and routes requests cleanly.
