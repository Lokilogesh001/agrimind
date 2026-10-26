# Model Card: DINOv2 + CLIP Feature Fusion

## Model Details
- **Backbones**:
  1. DINOv2-Small (`facebook/dinov2-small`, 384-dim, self-supervised visual structure).
  2. CLIP ViT-B/32 (`openai/clip-vit-base-patch32`, 512-dim, multimodal vision-language semantics).
- **Combined Feature Dimension**: 896-dim concatenation.
- **Classifier Heads Tested**:
  1. L2 Linear Probe Head.
  2. Hybrid Head (Cosine Similarity Prototypes + Linear Probe).

## Empirical Evaluation (Field Validation Split, N=108)
- **Linear Probe**: Accuracy: 62.96%, Macro-F1: 0.6311, ECE: 0.0783, Composite Score: 0.7157.
- **Hybrid Head**: Accuracy: 62.96%, Macro-F1: 0.6338, ECE: 0.2160, Composite Score: 0.6961.

## Comparative Insight
Concatenating CLIP features slightly boosts Macro-F1 in the hybrid formulation (0.6338 vs 0.6315) by providing multimodal semantic anchoring, but DINOv2-Small alone provides simpler deployment (384-dim vs 896-dim) with superior ECE (0.0642 vs 0.0783) and higher overall accuracy (63.89%).
