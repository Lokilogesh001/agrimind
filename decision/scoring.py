"""
Weighted advisory scoring: S(a) = w_s*S_soil + w_w*S_weather + w_d*S_disease + w_c*S_crop

Only invoked by decision.rules.resolve_conflict for actions that survive
Stage 1 (the veto layer). Weights are prototype parameters — see canonical
doc Section 10 for the "pending empirical validation" note.
"""

from __future__ import annotations

DEFAULT_WEIGHTS = {
    "soil": 0.35,
    "weather": 0.30,
    "disease": 0.15,
    "crop": 0.20,
}


def _soil_support(state, action: str) -> float:
    d = state.soil.overall_deficiency
    if action == "apply_fertilizer":
        return d
    if action == "delay":
        return 1 - d
    return 0.5  # monitor: neutral


def _weather_suitability(state, action: str) -> float:
    # If weather data is unavailable, invalid, timed out, or has 0 confidence,
    # do NOT assume safe weather (r=0.0). Weather failure must not artificially maximize fertilizer suitability.
    weather = getattr(state, "weather", None)
    status = getattr(weather, "status", "AVAILABLE") if weather else "UNAVAILABLE"
    if (
        weather is None
        or not getattr(weather, "is_available", True)
        or weather.confidence == 0.0
        or status in ("UNAVAILABLE", "INVALID", "TIMEOUT")
        or getattr(weather, "reason", "") in (
            "weather_unavailable", "weather_timeout", "weather_malformed", "missing_precipitation_data"
        )
    ):
        return 0.5  # Neutral conservative suitability

    r = state.weather.rainfall_risk
    if action == "apply_fertilizer":
        return 1 - r
    if action == "delay":
        return r
    return 0.5


def _disease_relevance(state, action: str) -> float:
    if not state.disease.actionable or not state.disease.predicted_class:
        return 0.3
    if action == "apply_fertilizer":
        # An active disease slightly reduces enthusiasm for routine fertilizing
        return 1 - (state.disease.confidence * 0.3)
    return 0.5


def _crop_suitability(state, action: str) -> float:
    # Placeholder for crop/growth-stage context; defaults to neutral until
    # the crop-context input schema is finalized.
    return state.crop.suitability_hint if hasattr(state.crop, "suitability_hint") else 0.6


def weighted_score(state, action: str, weights: dict | None = None) -> float:
    w = weights or DEFAULT_WEIGHTS
    s_soil = _soil_support(state, action)
    s_weather = _weather_suitability(state, action)
    s_disease = _disease_relevance(state, action)
    s_crop = _crop_suitability(state, action)

    score = (
        w["soil"] * s_soil
        + w["weather"] * s_weather
        + w["disease"] * s_disease
        + w["crop"] * s_crop
    )
    return round(score, 4)
