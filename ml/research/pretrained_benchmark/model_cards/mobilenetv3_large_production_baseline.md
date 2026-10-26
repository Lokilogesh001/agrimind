# Model Card: AgriMind Production Baseline (best.pt)

## Model Details
- **Architecture**: MobileNetV3-Large (Custom linear classifier: 960 -> 38).
- **Path**: `ml/artifacts/best.pt` (SHA-256: `c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e`).
- **Total Parameters**: 4,242,438 (~4.2M).
- **Status**: UNCHANGED PRODUCTION SYSTEM.

## Empirical Evaluation (Field Validation Split, N=108)
- **Top-1 Accuracy**: 20.37%
- **Macro-F1 (Evaluated Classes)**: 0.1815
- **Expected Calibration Error (ECE)**: 0.2924
- **Composite Score**: 0.3037
- **Cross-Crop Error Rate**: 57.41%
- **Disease-Healthy Error Rate**: 22.22%
- **Inference Latency**: 21.35 ms/sample
