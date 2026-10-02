"""Weather Agent — rainfall risk scoring (blueprint Sections 5-6)."""
from __future__ import annotations

from data_sources.weather import fetch_forecast
from orchestrator.state import WeatherResult

DEFAULT_WEIGHTS = {"precip_prob": 0.4, "intensity": 0.4, "duration": 0.2}


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
    if override is not None:
        precip_prob, intensity, duration = (
            override["precip_prob"], override["intensity"], override["duration"]
        )
        confidence = override.get("confidence", 0.85)
    else:
        forecast = fetch_forecast(lat, lon) if lat is not None and lon is not None else None
        if forecast is None:
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                fertilizer_condition="unknown",
                irrigation_condition="unknown",
                reason="weather_unavailable",
            )
        hourly = forecast.get("hourly", {})
        probs = hourly.get("precipitation_probability", [0])
        precs = hourly.get("precipitation", [0])
        precip_prob = (max(probs) if probs else 0) / 100.0
        intensity = min((max(precs) if precs else 0) / 10.0, 1.0)
        duration = min(sum(1 for p in probs if p > 50) / max(len(probs), 1), 1.0)
        confidence = 0.85

    risk = _rainfall_risk(precip_prob, intensity, duration)
    fertilizer_condition = "delay" if risk > 0.60 else "normal"
    irrigation_condition = "avoid" if risk > 0.60 else "normal"
    return WeatherResult(
        rainfall_risk=risk,
        temperature_risk=0.0,
        irrigation_condition=irrigation_condition,
        fertilizer_condition=fertilizer_condition,
        confidence=confidence,
        reason="High rainfall expected" if risk > 0.60 else "Rainfall risk manageable",
        is_available=True,
    )
