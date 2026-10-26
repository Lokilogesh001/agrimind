# Model Card: AgriMind Stage D Champion (stage_d_02)

## Model Details
- **Architecture**: MobileNetV3-Large with stage-wise field adaptation.
- **Checkpoint**: `ml/research/unified_optimization/finalist_model/checkpoint_best_val.pt` (SHA-256: `9ef7145b2ae3e314130f2d5af2e85d9bb974d8fb7bfee47eb7c814c55722de24`).
- **Training Protocol**: 5-epoch head warmup (lr=2e-4) followed by 10-epoch partial backbone finetuning (unfreeze from block 13, lr=1e-4) with unweighted cross-entropy.
- **Total Parameters**: 4,242,438 (~4.2M).

## Empirical Evaluation (Field Validation Split, N=108)
- **Top-1 Accuracy**: 39.81%
- **Macro-F1 (Evaluated Classes)**: 0.3760
- **Expected Calibration Error (ECE)**: 0.1381
- **Composite Score**: 0.4853
- **Cross-Crop Error Rate**: 42.59%
- **Disease-Healthy Error Rate**: 18.52%
- **Inference Latency**: 17.80 ms/sample
