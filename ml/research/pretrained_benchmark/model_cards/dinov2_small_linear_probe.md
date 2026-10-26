# Model Card: DINOv2-Small (Linear Probe Head) — Champion Foundation Candidate

## Model Details
- **Architecture**: Vision Transformer Small (DINOv2, `facebook/dinov2-small`) with Linear Classification Probe.
- **Backbone Parameters**: 22.1M (frozen 384-dimensional patch14 representation).
- **Head Parameters**: 14,592 (384 -> 38 linear mapping).
- **License**: Apache-2.0 (Meta Open Source).
- **Pretraining Dataset**: LVD-142M (142 million uncurated diverse natural images with self-supervised DINOv2 objective).
- **Adaptation Protocol**: Frozen backbone feature extraction on AgriMind field training manifest (`field_train_manifest.csv`, 419 images) with L2-regularized linear probe training.

## Empirical Evaluation (Field Validation Split, N=108)
- **Top-1 Accuracy**: 63.89% (Wilson 95% CI: [0.5450, 0.7233])
- **Macro-F1 (Evaluated Classes)**: 0.6315
- **Macro-F1 (All 38 Classes)**: 0.4487
- **Expected Calibration Error (ECE)**: 0.0642
- **Composite Score**: 0.7208
- **Cross-Crop Error Rate**: 9.26%
- **Disease-Healthy Error Rate**: 12.96%
- **Confidence Gate Audit (@ 0.60 threshold)**: Actionable Precision = 89.58%, Safety Filtering Efficiency = 87.18%

## Key Strengths & Failure Modes
- **Strengths**: Highest accuracy (63.89%) and lowest ECE (0.0642) of all evaluated candidates. Self-supervised pretraining provides exceptional robustness to outdoor clutter, lighting, and soil backgrounds.
- **Failure Modes**: 10 cross-crop errors observed, predominantly between visual lookalikes (e.g. Potato Early Blight vs Tomato Early Blight caused by identical *Alternaria solani* lesions).
