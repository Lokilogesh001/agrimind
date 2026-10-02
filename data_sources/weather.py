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
        return response.json()
    except Exception:
        return None
