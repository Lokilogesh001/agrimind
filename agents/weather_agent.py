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
    source = "open_meteo"
    freshness_status = "REAL_DATA"
    is_cached = False
    is_estimated = False
    observation_time = None
    retrieval_time = None

    if override is not None:
        precip_prob = float(override.get("precip_prob", override.get("precipitation_probability", 0.0)))
        intensity = float(override.get("intensity", 0.0))
        duration = float(override.get("duration", 0.0))
        confidence = float(override.get("confidence", 0.85))
        status = override.get("status", "AVAILABLE")
        source = override.get("source", "mock_telemetry")
        freshness_status = override.get("freshness_status", "REAL_DATA")
        is_cached = bool(override.get("is_cached", False))
        is_estimated = bool(override.get("is_estimated", False))
        observation_time = override.get("observation_time")
        retrieval_time = override.get("retrieval_time")
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
                fertilizer_condition="delay",
                irrigation_condition="delay",
                reason="weather_unavailable",
                risk_level="UNKNOWN",
                risk_explanation="Meteorological telemetry unavailable. Immature assumption of zero rainfall is prohibited; conservative safety delay applied.",
                source="none",
                freshness_status="UNAVAILABLE",
                is_estimated=True,
            )
        forecast = fetch_forecast(lat, lon)
        if forecast is None:
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status="UNAVAILABLE",
                fertilizer_condition="delay",
                irrigation_condition="delay",
                reason="weather_unavailable",
                risk_level="UNKNOWN",
                risk_explanation="Meteorological telemetry unavailable. Immature assumption of zero rainfall is prohibited; conservative safety delay applied.",
                source="open_meteo",
                freshness_status="UNAVAILABLE",
                is_estimated=True,
            )

        status = forecast.get("status", "AVAILABLE")
        source = forecast.get("source", "open_meteo")
        freshness_status = forecast.get("freshness_status", "REAL_DATA")
        is_cached = forecast.get("is_cached", False)
        is_estimated = forecast.get("is_estimated", False)
        observation_time = forecast.get("observation_time")
        retrieval_time = forecast.get("retrieval_time")

        if status == "TIMEOUT":
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status="TIMEOUT",
                fertilizer_condition="delay",
                irrigation_condition="delay",
                reason="weather_timeout",
                risk_level="UNKNOWN",
                risk_explanation="Meteorological request timed out. Immature assumption of zero rainfall is prohibited; conservative safety delay applied.",
                source=source,
                freshness_status=freshness_status,
                is_cached=is_cached,
                is_estimated=True,
                observation_time=observation_time,
                retrieval_time=retrieval_time,
            )
        if status in ("UNAVAILABLE", "INVALID"):
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status=status,
                fertilizer_condition="delay",
                irrigation_condition="delay",
                reason="weather_malformed" if status == "INVALID" else "weather_unavailable",
                risk_level="UNKNOWN",
                risk_explanation=f"Meteorological forecast is {status}. Rain risk is unverified; conservative delay enforced.",
                source=source,
                freshness_status=freshness_status,
                is_cached=is_cached,
                is_estimated=True,
                observation_time=observation_time,
                retrieval_time=retrieval_time,
            )

        hourly = forecast.get("hourly")
        if not isinstance(hourly, dict):
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status="INVALID",
                fertilizer_condition="delay",
                irrigation_condition="delay",
                reason="weather_malformed",
                risk_level="UNKNOWN",
                risk_explanation="Meteorological hourly payload missing. Rain risk unverified; conservative delay enforced.",
                source=source,
                freshness_status=freshness_status,
                is_cached=is_cached,
                is_estimated=True,
                observation_time=observation_time,
                retrieval_time=retrieval_time,
            )

        probs = hourly.get("precipitation_probability")
        precs = hourly.get("precipitation")
        if probs is None or precs is None or not isinstance(probs, list) or not isinstance(precs, list):
            return WeatherResult(
                rainfall_risk=0.0,
                confidence=0.0,
                is_available=False,
                status="INVALID",
                fertilizer_condition="delay",
                irrigation_condition="delay",
                reason="missing_precipitation_data",
                risk_level="UNKNOWN",
                risk_explanation="Precipitation arrays missing from forecast. Rain risk unverified; conservative delay enforced.",
                source=source,
                freshness_status=freshness_status,
                is_cached=is_cached,
                is_estimated=True,
                observation_time=observation_time,
                retrieval_time=retrieval_time,
            )

        precip_prob = (max(probs) if probs else 0) / 100.0
        intensity = min((max(precs) if precs else 0) / 10.0, 1.0)
        duration = min(sum(1 for p in probs if p > 50) / max(len(probs), 1), 1.0)
        confidence = 0.85 if status in ("AVAILABLE", "CACHED") else 0.70

    risk = direct_risk if direct_risk is not None else _rainfall_risk(precip_prob, intensity, duration)
    risk_level = get_weather_risk_level(risk)
    fertilizer_condition = "delay" if risk_level in ("HIGH", "SEVERE") or risk >= 0.60 or status == "STALE_CACHE" else "normal"
    irrigation_condition = "avoid" if risk_level in ("HIGH", "SEVERE") or risk >= 0.60 else ("delay" if status == "STALE_CACHE" else "normal")
    risk_explanation = get_weather_risk_explanation(risk, risk_level)
    reason = "High rainfall expected" if risk_level in ("HIGH", "SEVERE") or risk >= 0.60 else "Rainfall risk manageable"

    if status == "STALE_CACHE":
        confidence = 0.50
        reason = "Meteorological telemetry is stale; conservative delay applied"
        risk_explanation = (
            f"Meteorological telemetry is STALE (cache expired >15 min, live refresh failed). "
            f"Stale observation ({risk:.2f}) cannot verify dry conditions; conservative delay enforced."
        )
    peak_intensity = round(intensity * 10.0, 2)
    washoff = "HIGH" if risk >= 0.60 else ("MODERATE" if risk >= 0.30 else "LOW")
    leaching = "HIGH" if (risk >= 0.60 or peak_intensity >= 5.0) else ("MODERATE" if risk >= 0.30 else "LOW")

    formula_str = (
        f"Rainfall Risk {risk:.4f} = (0.40 * Prob:{precip_prob:.2f}) + "
        f"(0.40 * Intensity:{intensity:.2f}) + (0.20 * Duration:{duration:.2f})"
    )

    return WeatherResult(
        rainfall_risk=risk,
        temperature_risk=0.0,
        irrigation_condition=irrigation_condition,
        fertilizer_condition=fertilizer_condition,
        confidence=confidence,
        reason=reason,
        is_available=(status in ("AVAILABLE", "CACHED", "STALE_CACHE")),
        status=status,
        risk_level=risk_level,
        risk_explanation=risk_explanation,
        precipitation_probability=round(precip_prob, 2),
        rainfall_amount_mm=peak_intensity,
        forecast_horizon_hours=48,
        peak_intensity_mm_hr=peak_intensity,
        duration_hours_fraction=round(duration, 2),
        risk_formula=formula_str,
        washoff_risk_level=washoff,
        leaching_risk_level=leaching,
        source=source,
        freshness_status=freshness_status,
        observation_time=observation_time,
        retrieval_time=retrieval_time,
        is_cached=is_cached,
        is_estimated=is_estimated,
    )

