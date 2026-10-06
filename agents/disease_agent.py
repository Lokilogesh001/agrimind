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
        # Space-separated labels like 'Tomato Early Blight' or 'Rice Blast'
        parts = clean.split()
        first_token = parts[0].lower() if parts else ""
        from data_sources.crops import CROPS_REGISTRY
        known_crops = {c["name"].lower() for c in CROPS_REGISTRY} | {
            "tomato", "potato", "corn", "rice", "wheat", "cotton", "apple", "grape", "cherry",
            "peach", "pepper", "strawberry", "orange", "soybean", "squash", "maize", "sugarcane"
        }
        if first_token in known_crops and len(parts) > 1:
            crop_part, disease_part = parts[0], " ".join(parts[1:])
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


def _check_crop_mismatch(selected: str, detected: str | None) -> bool:
    if not selected or not detected:
        return False
    s = selected.strip().lower()
    d = detected.strip().lower()
    # Normalize synonyms
    s_norm = "rice" if s in ["rice", "paddy"] else ("maize" if s in ["maize", "corn"] else s)
    d_norm = "rice" if d in ["rice", "paddy"] else ("maize" if d in ["maize", "corn"] else d)
    return s_norm != d_norm and s_norm not in d_norm and d_norm not in s_norm


def run(
    image_path: str | None = None,
    model=None,
    override: dict | None = None,
    selected_crop: str = "",
) -> DiseaseResult:
    # Case B: disease_override supplied
    if override is not None:
        predicted_class = override.get("predicted_class")
        confidence = float(override.get("confidence", 0.0))
        norm = normalize_disease_label(predicted_class)
        mismatch = _check_crop_mismatch(selected_crop, norm["crop"])
        conf_gate_passed = confidence >= LOW_CONFIDENCE_GATE
        crop_match_passed = not mismatch
        actionable = conf_gate_passed and crop_match_passed
        if mismatch:
            action_status = "BLOCKED"
            c_det = (norm.get("crop") or "Tomato").capitalize()
            c_sel = (selected_crop or "Rice").capitalize()
            block_reason = f"Predicted crop is {c_det} but selected crop is {c_sel}."
        elif not conf_gate_passed:
            action_status = "BLOCKED"
            block_reason = f"The disease signal is below the {LOW_CONFIDENCE_GATE:.2f} confidence gate."
        else:
            action_status = "ALLOWED"
            block_reason = ""

        return DiseaseResult(
            predicted_class=predicted_class,
            raw_class=predicted_class,
            normalized_disease=norm["disease"],
            crop_detected=norm["crop"],
            confidence=round(confidence, 4),
            severity=_infer_severity(predicted_class),
            actionable=actionable,
            crop_mismatch=mismatch,
            confidence_gate_passed=conf_gate_passed,
            crop_match_passed=crop_match_passed,
            action_status=action_status,
            block_reason=block_reason,
            status="OVERRIDE",
        )

    # Case A: image supplied and exists
    if image_path:
        result = classify(image_path, model=model)
        predicted_class = result["predicted_class"]
        confidence = float(result["confidence"])
        norm = normalize_disease_label(predicted_class)
        mismatch = _check_crop_mismatch(selected_crop, norm["crop"])
        conf_gate_passed = confidence >= LOW_CONFIDENCE_GATE
        crop_match_passed = not mismatch
        actionable = conf_gate_passed and crop_match_passed
        if mismatch:
            action_status = "BLOCKED"
            c_det = (norm.get("crop") or "Tomato").capitalize()
            c_sel = (selected_crop or "Rice").capitalize()
            block_reason = f"Predicted crop is {c_det} but selected crop is {c_sel}."
        elif not conf_gate_passed:
            action_status = "BLOCKED"
            block_reason = f"The disease signal is below the {LOW_CONFIDENCE_GATE:.2f} confidence gate."
        else:
            action_status = "ALLOWED"
            block_reason = ""

        return DiseaseResult(
            predicted_class=predicted_class,
            raw_class=predicted_class,
            normalized_disease=norm["disease"],
            crop_detected=norm["crop"],
            confidence=round(confidence, 4),
            severity=_infer_severity(predicted_class),
            actionable=actionable,
            crop_mismatch=mismatch,
            confidence_gate_passed=conf_gate_passed,
            crop_match_passed=crop_match_passed,
            action_status=action_status,
            block_reason=block_reason,
            status="AVAILABLE",
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
        crop_mismatch=False,
        confidence_gate_passed=False,
        crop_match_passed=True,
        action_status="INACTIVE",
        block_reason="No leaf image provided",
        status="NOT_SUPPLIED",
    )

