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
        precip_prob = float(override.get("precip_prob", 0.0))
        intensity = float(override.get("intensity", 0.0))
        duration = float(override.get("duration", 0.0))
        confidence = float(override.get("confidence", 0.85))
        status = "AVAILABLE"
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
            )

        precip_prob = (max(probs) if probs else 0) / 100.0
        intensity = min((max(precs) if precs else 0) / 10.0, 1.0)
        duration = min(sum(1 for p in probs if p > 50) / max(len(probs), 1), 1.0)
        confidence = 0.85
        status = "AVAILABLE"

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
        status=status,
    )
