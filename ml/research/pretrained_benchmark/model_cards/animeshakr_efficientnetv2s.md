# Model Card: animeshakr/plant-disease-efficientnetv2s — BLOCKED

## Model Details
- **Architecture**: EfficientNetV2-S (quantized TFLite).
- **Repository**: `https://huggingface.co/animeshakr/plant-disease-efficientnetv2s`
- **License**: Apache-2.0.

## Status: BLOCKED_INCOMPATIBLE_FORMAT
- **Blocker Reason**: The repository contains only `model_float16_quant.tflite` (44.3 MB). No PyTorch weights, state dictionary, or Python inference script are provided.
- **Action Taken**: Documented blocker in compliance with Section 2 protocol. Did not force incompatible runtime dependencies into the PyTorch production stack.
