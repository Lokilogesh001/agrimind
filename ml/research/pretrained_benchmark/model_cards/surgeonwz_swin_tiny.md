# Model Card: surgeonwz/plant-village

## Model Details
- **Architecture**: Swin Transformer Tiny (`microsoft/swin-tiny-patch4-window7-224`).
- **Repository**: `https://huggingface.co/surgeonwz/plant-village`
- **Total Parameters**: 27,548,272 (~27.5M).
- **License**: Apache-2.0.

## Empirical Evaluation (Field Validation Split, N=108)
- **Top-1 Accuracy**: 19.44% (Wilson 95% CI: [0.1322, 0.2769])
- **Macro-F1 (Evaluated Classes)**: 0.1413
- **Expected Calibration Error (ECE)**: 0.2504
- **Composite Score**: 0.2995
- **Cross-Crop Error Rate**: 46.30%
- **Disease-Healthy Error Rate**: 20.37%
- **Inference Latency**: 21.05 ms/sample

## Analysis
Swin-Tiny exhibits moderate calibration (ECE 0.2504) due to window-based self-attention, but suffered severe accuracy degradation (19.44%) due to absence of in-the-wild training examples.
