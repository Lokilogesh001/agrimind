"""Agmarknet Market provider adapter with provenance tracking and cached observation support.

Distinguishes:
1. Live verified Agmarknet observations (source='agmarknet_api', status='REAL_DATA')
2. Cached market observations with timestamps (source='agmarknet_cache', status='CACHED')
3. Unavailable telemetry (returns None)
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

# In-memory observation cache: (crop, market) -> (timestamp, data_dict)
_MARKET_CACHE: dict[tuple[str, str | None], tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 900.0  # 15 minutes TTL for wholesale APMC prices


def clear_market_cache_for_tests():
    """Testing utility to clear cached market observations."""
    global _MARKET_CACHE
    _MARKET_CACHE.clear()


def fetch_prices(
    crop: str,
    market: str | None = None,
    timeout: float = 8.0,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    """Fetch live market prices from Agmarknet API adapter with provenance and cache fallback."""
    if not crop or not crop.strip():
        return None

    norm_crop = crop.strip().lower()
    norm_market = market.strip().lower() if market else None
    cache_key = (norm_crop, norm_market)
    now = time.time()

    # 1. Check valid cache if not forcing refresh
    if not force_refresh and cache_key in _MARKET_CACHE:
        cached_time, cached_data = _MARKET_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            res = dict(cached_data)
            res["source"] = "agmarknet_cache"
            res["status"] = "CACHED"
            res["is_cached"] = True
            return res

    base = os.getenv("AGMARKNET_BASE_URL")
    if not base:
        # Fall back to expired cache if available rather than arbitrary fabrication
        if cache_key in _MARKET_CACHE:
            _, cached_data = _MARKET_CACHE[cache_key]
            res = dict(cached_data)
            res["source"] = "agmarknet_cache"
            res["status"] = "CACHED"
            res["is_cached"] = True
            res["stale"] = True
            return res
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

        # Validate numeric current price
        cp = data.get("current_price")
        if cp is None:
            return None
        try:
            val = float(cp)
            if val <= 0 or val > 1000000:  # Sensible agricultural price bound
                return None
        except (ValueError, TypeError):
            return None

        now_iso = datetime.now(timezone.utc).isoformat()
        clean_data = {
            "current_price": float(cp),
            "price_history": [float(x) for x in data.get("price_history", []) if isinstance(x, (int, float)) and x >= 0],
            "mandi_name": data.get("mandi_name") or market or "Regional APMC Mandi",
            "commodity_grade": data.get("commodity_grade", "FAQ (Fair Average Quality)"),
            "source": "agmarknet_api",
            "status": "REAL_DATA",
            "retrieval_timestamp": data.get("retrieval_timestamp") or now_iso,
            "is_cached": False,
        }

        # Update cache
        _MARKET_CACHE[cache_key] = (now, clean_data)
        return clean_data

    except Exception:
        # If network/API fails, fallback to cached observation if available
        if cache_key in _MARKET_CACHE:
            _, cached_data = _MARKET_CACHE[cache_key]
            res = dict(cached_data)
            res["source"] = "agmarknet_cache"
            res["status"] = "CACHED"
            res["is_cached"] = True
            res["stale"] = True
            return res
        return None
