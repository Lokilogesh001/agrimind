"""Market provider adapter.

The production adapter can be pointed at an Agmarknet-backed service through
AGMARKNET_BASE_URL. The agent remains usable with caller-supplied history for
offline/demo operation.
"""
from __future__ import annotations
import os


def fetch_prices(crop: str, market: str | None = None, timeout: float = 8) -> dict | None:
    base = os.getenv("AGMARKNET_BASE_URL")
    if not base:
        return None
    try:
        import requests
        params = {"crop": crop}
        if market:
            params["market"] = market
        response = requests.get(base, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None
        data["source"] = "agmarknet_api"
        data["status"] = "REAL_DATA"
        return data
    except Exception:
        return None
