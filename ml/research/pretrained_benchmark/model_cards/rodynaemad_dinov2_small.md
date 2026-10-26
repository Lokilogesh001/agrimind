# Model Card: rodynaemad/plant-disease-dinov2-small

## Model Details
- **Architecture**: `dinov2-small` fine-tuned for 38-class classification.
- **Repository**: `https://huggingface.co/rodynaemad/plant-disease-dinov2-small`
- **Total Parameters**: 22,085,798 (~22.1M).
- **License**: Apache-2.0.
- **Training Data**: Exclusively laboratory PlantVillage images (plain gray/black backgrounds).

## Empirical Evaluation (Field Validation Split, N=108)
- **Top-1 Accuracy**: 30.56% (Wilson 95% CI: [0.2266, 0.3979])
- **Macro-F1 (Evaluated Classes)**: 0.3034
- **Expected Calibration Error (ECE)**: 0.4871
- **Composite Score**: 0.3913
- **Cross-Crop Error Rate**: 32.41%
- **Disease-Healthy Error Rate**: 25.93%
- **Inference Latency**: 25.45 ms/sample

## Analysis & Domain Collapse
While the DINOv2 backbone retains superior visual features compared to standard CNNs (achieving 30.56% vs 16.67% for EfficientNet-B4), this checkpoint was fine-tuned exclusively on laboratory PlantVillage images. Its classification head suffers from severe overconfidence on out-of-distribution field backgrounds (ECE 0.4871).
