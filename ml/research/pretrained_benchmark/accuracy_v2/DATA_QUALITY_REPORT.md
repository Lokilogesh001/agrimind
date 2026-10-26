# AgriMind Accuracy V2 — Training & Evaluation Data Quality Report

**Date:** 2026-10-26 | **Protocol:** Strict Evaluation Integrity Audit

## 1. Executive Summary

- **Manifests Audited:** 4 (Train, Validation, PlantDoc Test, Independent Field Test)
- **Corrupt / Missing Images:** 0 across all 984 total dataset images
- **SHA-256 Hash Verification:** 100% match with manifest checksums
- **Taxonomy Alignment:** 100% of mapped classes adhere to the 38 canonical AgriMind classes
- **Data Leakage (Train vs Locked Tests):** Exactly **0 overlapping image hashes**
- **Data Leakage (Val vs Locked Tests):** Exactly **0 overlapping image hashes**

## 2. Dataset Split Overview

| Manifest | Images | Classes Represented | Missing | Unreadable | Hash Mismatches | Mean Resolution |
|---|---:|---:|---:|---:|---:|---:|
| `field_train_manifest.csv` | 419 | 28 / 38 | 0 | 0 | 0 | 985x833 |
| `field_val_manifest.csv` | 108 | 27 / 38 | 0 | 0 | 0 | 1113x939 |
| `plantdoc_test_manifest.csv` | 236 | 27 / 38 | 0 | 0 | 0 | 1055x950 |
| `independent_field_test_manifest.csv` | 221 | 28 / 38 | 0 | 0 | 0 | 1070x914 |

## 3. Data Leakage & Evaluation Integrity Verification

| Check Description | Metric | Threshold | Verdict |
|---|---|---|---|
| Train vs PlantDoc Test Hash Overlap | 0 | 0 | PASS (Zero Leakage) |
| Train vs Independent Field Test Hash Overlap | 0 | 0 | PASS (Zero Leakage) |
| Validation vs PlantDoc Test Hash Overlap | 0 | 0 | PASS (Zero Leakage) |
| Validation vs Independent Field Test Hash Overlap | 0 | 0 | PASS (Zero Leakage) |
| Train vs Validation Hash Overlap | 0 | 0 | PASS (Strict Split) |
| Train vs Validation Group-ID Overlap | 0 | 0 | PASS (Source Disjoint) |

## 4. Class Balance & Representation Analysis

- **Training Samples:** 419 images across 28 represented classes
- **Validation Samples:** 108 images across 27 represented classes
- **Max samples per class (Train):** 24
- **Min samples per class (Train):** 1
- **Imbalance Ratio:** 24.0:1
- **Unrepresented classes in field training split (10/38):**
  - `Apple___Black_rot`
  - `Cherry_(including_sour)___Powdery_mildew`
  - `Corn_(maize)___healthy`
  - `Grape___Esca_(Black_Measles)`
  - `Grape___Leaf_blight_(Isariopsis_Leaf_Spot)`
  - `Orange___Haunglongbing_(Citrus_greening)`
  - `Peach___Bacterial_spot`
  - `Potato___healthy`
  - `Strawberry___Leaf_scorch`
  - `Tomato___Target_Spot`

## 5. Photometric & Resolution Properties

- **Resolution range (Train):** 143x150 to 4608x3370
- **Mean aspect ratio:** 1.24
- **Mean brightness:** 120.58 (std: 42.00)
- **Field vs Lab note:** Real field conditions show heavy background foliage, specular outdoor highlights, and variable focal distances.
