"""Open-Meteo provider adapter with provenance tracking and observation caching."""
from __future__ import annotations
import os
import time
from datetime import datetime, timezone

# In-memory observation cache: (round(lat, 3), round(lon, 3)) -> (timestamp, data_dict)
_WEATHER_CACHE: dict[tuple[float, float], tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 900  # 15 minutes


def clear_weather_cache_for_tests():
    """Testing utility to clear cached meteorological observations."""
    _WEATHER_CACHE.clear()


def fetch_forecast(lat: float, lon: float, timeout: float = 8, force_refresh: bool = False) -> dict | None:
    now = time.time()
    now_iso = datetime.now(timezone.utc).isoformat()
    cache_key = (round(float(lat), 3), round(float(lon), 3))

    # 1. Check valid cache if not forcing refresh
    if not force_refresh and cache_key in _WEATHER_CACHE:
        cached_time, cached_data = _WEATHER_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            res = dict(cached_data)
            res["source"] = "open_meteo_cache"
            res["status"] = "CACHED"
            res["freshness_status"] = "CACHED"
            res["is_cached"] = True
            res["is_estimated"] = False
            return res

    try:
        import requests
        response = requests.get(
            os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast"),
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation_probability,precipitation,temperature_2m",
                "forecast_days": 1,
                "timezone": "auto",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            # Check if stale cache is available
            if cache_key in _WEATHER_CACHE:
                _, cached_data = _WEATHER_CACHE[cache_key]
                res = dict(cached_data)
                res["source"] = "open_meteo_cache"
                res["status"] = "STALE_CACHE"
                res["freshness_status"] = "STALE_CACHE"
                res["is_cached"] = True
                res["is_estimated"] = True
                return res
            return {
                "status": "INVALID",
                "source": "open_meteo",
                "freshness_status": "INVALID",
                "error": "malformed_json",
                "hourly": None,
                "is_cached": False,
                "is_estimated": True,
                "retrieval_time": now_iso,
                "observation_time": None,
            }

        data["source"] = "open_meteo"
        data["status"] = "AVAILABLE"
        data["freshness_status"] = "REAL_DATA"
        data["is_cached"] = False
        data["is_estimated"] = False
        data["retrieval_time"] = now_iso

        # Extract observation time from hourly array or current time
        hourly = data.get("hourly")
        if isinstance(hourly, dict) and hourly.get("time") and len(hourly["time"]) > 0:
            data["observation_time"] = hourly["time"][0]
        else:
            data["observation_time"] = now_iso

        # Update cache
        _WEATHER_CACHE[cache_key] = (now, dict(data))
        return data

    except Exception as exc:
        is_timeout = False
        try:
            import requests
            if isinstance(exc, requests.exceptions.Timeout):
                is_timeout = True
        except Exception:
            pass

        # If live API fails, fall back to cached observation if available
        if cache_key in _WEATHER_CACHE:
            cached_time, cached_data = _WEATHER_CACHE[cache_key]
            res = dict(cached_data)
            res["source"] = "open_meteo_cache"
            res["status"] = "STALE_CACHE"
            res["freshness_status"] = "STALE_CACHE"
            res["is_cached"] = True
            res["is_estimated"] = True
            return res

        status = "TIMEOUT" if is_timeout else "UNAVAILABLE"
        return {
            "status": status,
            "source": "open_meteo",
            "freshness_status": status,
            "error": "timeout" if is_timeout else str(exc),
            "hourly": None,
            "is_cached": False,
            "is_estimated": True,
            "retrieval_time": now_iso,
            "observation_time": None,
        }

