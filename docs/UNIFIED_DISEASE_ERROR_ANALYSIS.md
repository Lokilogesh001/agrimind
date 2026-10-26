# AGRIMIND UNIFIED 38-CLASS DISEASE MODEL — ERROR ANALYSIS & DIAGNOSTICS
**Audit Timestamp:** 2026-10-26T05:36:02.858588+00:00
**Checkpoint Evaluated:** `D:\project\AGRIMIND\demo\agrimind_batch1\ml\research\unified_optimization\finalist_model\checkpoint_best_val.pt`
**SHA-256 Digest:** `9ef7145b2ae3e314130f2d5af2e85d9bb974d8fb7bfee47eb7c814c55722de24`
**Validation Manifest:** `D:\project\AGRIMIND\demo\agrimind_batch1\evaluation\manifests\field_val_manifest.csv` (108 samples across 27 evaluated classes)

## 1. Executive Summary & Core Performance
| Metric | Evaluated Value | 95% Wilson CI / Note |
|---|---:|---|
| **Top-1 Accuracy** | **39.81%** | [31.09%, 49.24%] |
| **Macro-F1 (27 represented classes)** | **0.3748** | Primary screening metric |
| **Macro-F1 (All 38 taxonomy classes)** | **0.2663** | Includes zero-support penalty (11 classes) |
| **Expected Calibration Error (ECE)** | **0.1418** | 10 probability bins |
| **Maximum Calibration Error (MCE)** | **0.3418** | Worst-case calibration gap |

## 2. Production Confidence Gate Audit (Threshold = 0.60)
AgriMind enforces a 0.60 softmax confidence gate before showing predictions to farmers. Predictions below 0.60 trigger automatic escalation to local Krishi Vigyan Kendra (KVK) extension specialists.

| Gate Category | Count | Percentage | Operational Meaning |
|---|---:|---:|---|
| **Actionable Predictions (Conf >= 0.60)** | **39** | **36.1%** | Direct farmer advisory active |
| - *Actionable Correct* | 22 | 20.4% | Correct treatment advice provided |
| - *False Confident (Dangerous)* | 17 | 15.7% | Incorrect diagnosis shown as confident |
| **Gated / Escalated (Conf < 0.60)** | **69** | **63.9%** | Sent to agricultural extension / KVK |
| - *Safely Filtered Errors* | 48 | 44.4% | Errors prevented from reaching farmer |
| - *Suppressed Correct Calls* | 21 | 19.4% | Timid correct predictions escalated |

> **Actionable Precision:** **56.41%** of predictions that pass the 0.60 gate are strictly accurate.
> **Safety Filtering Efficiency:** The gate successfully intercepted **73.85%** of all model errors before downstream recommendation.

## 3. Two-Level Error Decomposition
| Error Dimension | Error Count | Rate (% of Val Split) | Agronomic Risk Profile |
|---|---:|---:|---|
| **Cross-Crop Pathogen Errors** | **45** | **41.67%** | Severe (Crop hallucination leads to completely irrelevant pesticide advice) |
| **Within-Crop Pathogen Confusion** | **20** | **18.52%** | Moderate (Correct crop, but misdiagnosed fungal vs bacterial foliar symptom) |
| **Disease-vs-Healthy Inversion** | **20** | **18.52%** | High (Treating healthy crop with agrochemicals or missing active infection) |
| **Total Prediction Errors** | **65** | **60.19%** | Across 108 field validation images |

## 4. Priority Diagnostic Pairs Investigation
The 7 specific diagnostic problem areas flagged in prior AgriMind evaluations were systematically inspected:

| Diagnostic Focus Pair | Confusion Instances | Mean Confidence | Agronomic Analysis |
|---|---:|---:|---|
| `Tomato___Septoria_leaf_spot` -> `Tomato___Bacterial_spot` | **2** | 0.6471 | Within-crop foliar bacterial/fungal spot ambiguity |
| `Tomato___Early_blight` -> `Tomato___Late_blight` | **1** | 0.3792 | Target-board concentric rings vs water-soaked lesions |
| `Corn_(maize)___Common_rust_` -> `Corn_(maize)___Northern_Leaf_Blight` | **1** | 0.6034 | Rust pustules vs elongated elliptical lesions |
| `Potato___Early_blight` -> `Potato___Late_blight` | **1** | 0.4116 | Solanaceous blight pathogen confusion |
| `Blueberry___healthy` -> `Apple___Cedar_apple_rust` | **2** | 0.1934 | Cross-crop leaf rust hallucination |
| `Tomato___Septoria_leaf_spot` -> `Tomato___healthy` | **0** | N/A | Underdiagnosis of foliar fungal infection |
| `Tomato___Early_blight` -> `Tomato___healthy` | **0** | N/A | Underdiagnosis of concentric foliar blight |

## 5. Top Confusion Pairs (Worst Error Modes)
| True Label | Predicted Label | Error Count | Error Mode | Mean Confidence |
|---|---|---:|---|---:|
| `Corn_(maize)___Northern_Leaf_Blight` | `Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot` | 2 | Within-Crop Pathogen Confusion | 0.6958 |
| `Cherry_(including_sour)___healthy` | `Peach___healthy` | 2 | Cross-Crop Misclassification | 0.6797 |
| `Tomato___Septoria_leaf_spot` | `Tomato___Bacterial_spot` | 2 | Within-Crop Pathogen Confusion | 0.6471 |
| `Peach___healthy` | `Tomato___Tomato_Yellow_Leaf_Curl_Virus` | 2 | Cross-Crop Misclassification | 0.4965 |
| `Tomato___Leaf_Mold` | `Tomato___Late_blight` | 2 | Within-Crop Pathogen Confusion | 0.4031 |
| `Blueberry___healthy` | `Apple___Cedar_apple_rust` | 2 | Cross-Crop Misclassification | 0.1934 |
| `Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot` | `Corn_(maize)___Common_rust_` | 1 | Within-Crop Pathogen Confusion | 0.9306 |
| `Apple___Cedar_apple_rust` | `Potato___Early_blight` | 1 | Cross-Crop Misclassification | 0.8615 |
| `Tomato___Bacterial_spot` | `Cherry_(including_sour)___healthy` | 1 | Cross-Crop Misclassification | 0.8539 |
| `Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot` | `Corn_(maize)___Northern_Leaf_Blight` | 1 | Within-Crop Pathogen Confusion | 0.7488 |
| `Grape___healthy` | `Strawberry___healthy` | 1 | Cross-Crop Misclassification | 0.7380 |
| `Apple___healthy` | `Peach___healthy` | 1 | Cross-Crop Misclassification | 0.7291 |
| `Pepper,_bell___Bacterial_spot` | `Tomato___Tomato_Yellow_Leaf_Curl_Virus` | 1 | Cross-Crop Misclassification | 0.7291 |
| `Apple___Apple_scab` | `Pepper,_bell___healthy` | 1 | Cross-Crop Misclassification | 0.6871 |
| `Blueberry___healthy` | `Soybean___healthy` | 1 | Cross-Crop Misclassification | 0.6397 |

## 6. Concrete Recommendations for Future Data Collection
1. **Expand Missing 10 Training Classes:** Blueberries, Cherries, Grapes, and Peaches are severely underrepresented in the 419-image field training set. Adding 20–30 real field photos per missing class is the single highest-ROI step.
2. **Add Targeted Solanaceous Spot Pairs:** Capture paired early-stage and late-stage Tomato Early Blight vs Septoria vs Bacterial Spot images under direct sunlight and high relative humidity.
3. **Multi-Scale Foliar Crops:** Collect images with varying working distances (15cm macro to 60cm canopy) to eliminate scale bias between laboratory flat-bed scans and field photography.
