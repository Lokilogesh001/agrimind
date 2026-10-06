"""Weather Agent — rainfall risk scoring (blueprint Sections 5-6)."""
from __future__ import annotations

from data_sources.weather import fetch_forecast
from orchestrator.state import WeatherResult

DEFAULT_WEIGHTS = {"precip_prob": 0.4, "intensity": 0.4, "duration": 0.2}

# Configurable deterministic weather risk level thresholds
WEATHER_RISK_THRESHOLDS = {
    "LOW": 0.29,
    "MODERATE": 0.59,
    "HIGH": 0.79,
    "SEVERE": 1.00,
}


def get_weather_risk_level(risk: float, thresholds: dict | None = None) -> str:
    """Map continuous risk score to explicit deterministic tiers:
    0.00–0.29 = LOW
    0.30–0.59 = MODERATE
    0.60–0.79 = HIGH
    0.80–1.00 = SEVERE
    """
    th = thresholds or WEATHER_RISK_THRESHOLDS
    r = round(float(risk), 4)
    if r <= th.get("LOW", 0.29):
        return "LOW"
    elif r <= th.get("MODERATE", 0.59):
        return "MODERATE"
    elif r <= th.get("HIGH", 0.79):
        return "HIGH"
    else:
        return "SEVERE"


def get_weather_risk_explanation(risk: float, level: str | None = None) -> str:
    """Agronomic explanation describing how the risk score affects field decisions."""
    lvl = level or get_weather_risk_level(risk)
    if lvl == "LOW":
        return "Low rainfall risk supports planned field operations and normal fertilizer scheduling."
    elif lvl == "MODERATE":
        return "Moderate rainfall risk increases uncertainty around immediate fertilizer application."
    elif lvl == "HIGH":
        return "High rainfall risk indicates strong runoff and leaching hazard; delay chemical and fertilizer application."
    else:
        return "Severe rainfall risk presents acute waterlogging and nutrient washout hazard; suspend all field operations."


def _rainfall_risk(precip_prob: float, intensity: float, duration: float,
                   weights: dict = DEFAULT_WEIGHTS) -> float:
    r = (
        weights["precip_prob"] * precip_prob
        + weights["intensity"] * intensity
        + weights["duration"] * duration
    )
    return round(min(max(r, 0.0), 1.0), 4)


def run(lat: float | None = None, lon: float | None = None,
        override: dict | None = None) -> WeatherResult:
    direct_risk = None
    if override is not None:
        precip_prob = float(override.get("precip_prob", override.get("precipitation_probability", 0.0)))
        intensity = float(override.get("intensity", 0.0))
        duration = float(override.get("duration", 0.0))
        confidence = float(override.get("confidence", 0.85))
        status = "AVAILABLE"
        if "rainfall_risk" in override:
            direct_risk = float(override["rainfall_risk"])
        elif "risk" in override:
            direct_risk = float(override["risk"])
    else:
        if lat is None or lon is None:
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status="UNAVAILABLE",
                fertilizer_condition="unknown",
                irrigation_condition="unknown",
                reason="weather_unavailable",
                risk_level="LOW",
                risk_explanation=get_weather_risk_explanation(0.0, "LOW"),
            )
        forecast = fetch_forecast(lat, lon)
        if forecast is None:
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status="UNAVAILABLE",
                fertilizer_condition="unknown",
                irrigation_condition="unknown",
                reason="weather_unavailable",
                risk_level="LOW",
                risk_explanation=get_weather_risk_explanation(0.0, "LOW"),
            )

        status = forecast.get("status", "AVAILABLE")
        if status == "TIMEOUT":
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status="TIMEOUT",
                fertilizer_condition="unknown",
                irrigation_condition="unknown",
                reason="weather_timeout",
                risk_level="LOW",
                risk_explanation=get_weather_risk_explanation(0.0, "LOW"),
            )
        if status in ("UNAVAILABLE", "INVALID"):
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status=status,
                fertilizer_condition="unknown",
                irrigation_condition="unknown",
                reason="weather_malformed" if status == "INVALID" else "weather_unavailable",
                risk_level="LOW",
                risk_explanation=get_weather_risk_explanation(0.0, "LOW"),
            )

        hourly = forecast.get("hourly")
        if not isinstance(hourly, dict):
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status="INVALID",
                fertilizer_condition="unknown",
                irrigation_condition="unknown",
                reason="weather_malformed",
                risk_level="LOW",
                risk_explanation=get_weather_risk_explanation(0.0, "LOW"),
            )

        probs = hourly.get("precipitation_probability")
        precs = hourly.get("precipitation")
        if probs is None or precs is None or not isinstance(probs, list) or not isinstance(precs, list):
            # Missing precipitation fields: do NOT assume zero rainfall!
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status="INVALID",
                fertilizer_condition="unknown",
                irrigation_condition="unknown",
                reason="missing_precipitation_data",
                risk_level="LOW",
                risk_explanation=get_weather_risk_explanation(0.0, "LOW"),
            )

        precip_prob = (max(probs) if probs else 0) / 100.0
        intensity = min((max(precs) if precs else 0) / 10.0, 1.0)
        duration = min(sum(1 for p in probs if p > 50) / max(len(probs), 1), 1.0)
        confidence = 0.85
        status = "AVAILABLE"

    risk = direct_risk if direct_risk is not None else _rainfall_risk(precip_prob, intensity, duration)
    risk_level = get_weather_risk_level(risk)
    fertilizer_condition = "delay" if risk_level in ("HIGH", "SEVERE") or risk >= 0.60 else "normal"
    irrigation_condition = "avoid" if risk_level in ("HIGH", "SEVERE") or risk >= 0.60 else "normal"
    risk_explanation = get_weather_risk_explanation(risk, risk_level)
    reason = "High rainfall expected" if risk_level in ("HIGH", "SEVERE") or risk >= 0.60 else "Rainfall risk manageable"
    return WeatherResult(
        rainfall_risk=risk,
        temperature_risk=0.0,
        irrigation_condition=irrigation_condition,
        fertilizer_condition=fertilizer_condition,
        confidence=confidence,
        reason=reason,
        is_available=True,
        status=status,
        risk_level=risk_level,
        risk_explanation=risk_explanation,
        precipitation_probability=round(precip_prob, 2),
        rainfall_amount_mm=round(intensity * 10.0, 2),
    )
