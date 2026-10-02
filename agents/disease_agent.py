"""Disease Agent — image classification wrapper."""
from __future__ import annotations
import os
from functools import lru_cache
from orchestrator.state import DiseaseResult

LOW_CONFIDENCE_GATE = 0.60
_HIGH_SEVERITY_KEYWORDS = ("blight", "rot", "wilt", "rust", "canker", "scab")


def normalize_disease_label(label: str | None) -> dict[str, str]:
    """
    Normalizes PlantVillage or raw disease labels.
    Examples:
      'Tomato___Early_blight' -> crop: 'tomato', disease: 'early blight', display: 'Tomato Early Blight'
      'Potato___Late_blight' -> crop: 'potato', disease: 'late blight', display: 'Potato Late Blight'
      'Corn_(maize)___healthy' -> crop: 'corn', disease: 'healthy', display: 'Corn Healthy'
      'Apple___Apple_scab' -> crop: 'apple', disease: 'apple scab', display: 'Apple Scab'
    """
    if not label:
        return {"raw": "", "crop": "", "disease": "", "display": "None"}

    clean = label.strip()
    if "___" in clean:
        crop_part, disease_part = clean.split("___", 1)
    elif "_" in clean:
        parts = clean.split("_", 1)
        crop_part, disease_part = parts[0], parts[1]
    else:
        crop_part, disease_part = "", clean

    crop_clean = crop_part.replace("_", " ").split("(")[0].strip().lower()
    dis_clean = disease_part.replace("_", " ").replace("  ", " ").strip().lower()
    display_words = [w.capitalize() for w in f"{crop_clean} {dis_clean}".split() if w]
    display = " ".join(display_words)

    return {
        "raw": clean,
        "crop": crop_clean,
        "disease": dis_clean,
        "display": display,
    }


def _infer_severity(predicted_class: str | None) -> str:
    if not predicted_class:
        return "low"
    label = predicted_class.strip().lower()
    disease_component = label.split("___", 1)[-1] if "___" in label else label
    if "healthy" in disease_component:
        return "low"
    return "high" if any(k in disease_component for k in _HIGH_SEVERITY_KEYWORDS) else "moderate"


@lru_cache(maxsize=1)
def _load_default_model():
    path = os.getenv("DISEASE_MODEL_PATH", "ml/artifacts/best.pt")
    if not os.path.exists(path):
        raise RuntimeError(f"Disease model checkpoint not found: {path}")
    from ml.disease_model import DiseasePredictor
    return DiseasePredictor(path, confidence_gate=LOW_CONFIDENCE_GATE)


def classify(image_path: str, model=None) -> dict:
    if not image_path:
        raise ValueError("image_path is required when disease_override is not provided")
    predictor = model or _load_default_model()
    return predictor.predict(image_path)


def run(image_path: str | None = None, model=None, override: dict | None = None) -> DiseaseResult:
    # Case B: disease_override supplied
    if override is not None:
        predicted_class = override.get("predicted_class")
        confidence = float(override.get("confidence", 0.0))
        norm = normalize_disease_label(predicted_class)
        return DiseaseResult(
            predicted_class=predicted_class,
            raw_class=predicted_class,
            normalized_disease=norm["disease"],
            crop_detected=norm["crop"],
            confidence=round(confidence, 4),
            severity=_infer_severity(predicted_class),
            actionable=confidence >= LOW_CONFIDENCE_GATE,
        )

    # Case A: image supplied and exists
    if image_path:
        result = classify(image_path, model=model)
        predicted_class = result["predicted_class"]
        confidence = float(result["confidence"])
        norm = normalize_disease_label(predicted_class)
        return DiseaseResult(
            predicted_class=predicted_class,
            raw_class=predicted_class,
            normalized_disease=norm["disease"],
            crop_detected=norm["crop"],
            confidence=round(confidence, 4),
            severity=_infer_severity(predicted_class),
            actionable=confidence >= LOW_CONFIDENCE_GATE,
        )

    # Case C: No image + no disease_override
    # Do NOT crash. Return benign default with zero confidence and actionable=False
    return DiseaseResult(
        predicted_class=None,
        raw_class=None,
        normalized_disease=None,
        crop_detected=None,
        confidence=0.0,
        severity="low",
        actionable=False,
    )
