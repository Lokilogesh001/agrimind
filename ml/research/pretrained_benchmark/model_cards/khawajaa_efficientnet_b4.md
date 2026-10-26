# Model Card: Khawajaa/plant-disease-detector

## Model Details
- **Architecture**: EfficientNet-B4 with custom 2-layer classifier head (1792 -> 512 -> 38).
- **Repository**: `https://huggingface.co/Khawajaa/plant-disease-detector`
- **Total Parameters**: 18,477,370 (~18.5M).
- **License**: Not explicitly declared on repository (assumed research/educational).
- **Claimed Score**: 98.8% accuracy on PlantVillage test split.

## Empirical Evaluation (Field Validation Split, N=108)
- **Top-1 Accuracy**: 16.67% (Wilson 95% CI: [0.1092, 0.2464])
- **Macro-F1 (Evaluated Classes)**: 0.1549
- **Expected Calibration Error (ECE)**: 0.6271
- **Composite Score**: 0.2234
- **Cross-Crop Error Rate**: 51.85%
- **Disease-Healthy Error Rate**: 26.85%
- **Inference Latency**: 18.23 ms/sample

## Analysis & Domain Collapse
This checkpoint exhibits catastrophic domain collapse. Despite claiming 98.8% laboratory accuracy, on field imagery accuracy collapses to 16.67% (worse than random guessing across top crops). It relies almost entirely on background lab artifacts.
