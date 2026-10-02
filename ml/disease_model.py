"""MobileNetV3-Large disease classifier for AgriMind."""
from __future__ import annotations
from pathlib import Path
import torch
from torch import nn
from torchvision import models, transforms
from PIL import Image

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_model(num_classes: int, pretrained: bool = True):
    weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v3_large(weights=weights)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, num_classes)
    return model


def inference_transform():
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


class DiseasePredictor:
    def __init__(self, checkpoint: str, confidence_gate: float = 0.60):
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        self.classes = payload["classes"]
        self.model = build_model(len(self.classes), pretrained=False)
        self.model.load_state_dict(payload["state_dict"])
        self.model.eval()
        self.transform = inference_transform()
        self.confidence_gate = confidence_gate

    @torch.inference_mode()
    def predict(self, image_path: str, top_k: int = 3) -> dict:
        image = Image.open(image_path).convert("RGB")
        logits = self.model(self.transform(image).unsqueeze(0))
        probs = torch.softmax(logits, dim=1)[0]
        values, indices = torch.topk(probs, k=min(top_k, len(self.classes)))
        results = [
            {"class": self.classes[int(i)], "confidence": round(float(v), 6)}
            for v, i in zip(values, indices)
        ]
        best = results[0]
        return {
            "predicted_class": best["class"],
            "confidence": best["confidence"],
            "actionable": best["confidence"] >= self.confidence_gate,
            "top_k": results,
        }


def save_checkpoint(model, classes, path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "classes": classes}, path)
