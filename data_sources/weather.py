"""Open-Meteo provider adapter."""
from __future__ import annotations
import os


def fetch_forecast(lat: float, lon: float, timeout: float = 8) -> dict | None:
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
            return {"status": "INVALID", "error": "malformed_json", "hourly": None}
        if "status" not in data:
            data["status"] = "AVAILABLE"
        return data
    except Exception as exc:
        try:
            import requests
            if isinstance(exc, requests.exceptions.Timeout):
                return {"status": "TIMEOUT", "error": "timeout", "hourly": None}
        except Exception:
            pass
        return {"status": "UNAVAILABLE", "error": str(exc), "hourly": None}
