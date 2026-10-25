"""Open-Meteo Geocoding Adapter for AgriMind.

Resolves human-readable farm locations (village, town, district, pincode)
into internal coordinates without requiring the farmer to enter raw lat/lon.
Includes offline knowledge for key agricultural regions and an LRU cache.
"""
from __future__ import annotations

import os
import re
from typing import Any
import requests

GEOCODING_BASE_URL = os.getenv("GEOCODING_BASE_URL", "https://geocoding-api.open-meteo.com/v1/search")

# Local fallback cache for deterministic unit tests and offline reliability
LOCAL_FARM_LOCATIONS: dict[str, dict[str, Any]] = {
    "chennai": {
        "location_name": "Chennai, Tamil Nadu, India",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "admin1": "Tamil Nadu",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "madurai": {
        "location_name": "Madurai, Tamil Nadu, India",
        "latitude": 9.9252,
        "longitude": 78.1198,
        "admin1": "Tamil Nadu",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "pune": {
        "location_name": "Pune, Maharashtra, India",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "admin1": "Maharashtra",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "nashik": {
        "location_name": "Nashik, Maharashtra, India",
        "latitude": 19.9975,
        "longitude": 73.7898,
        "admin1": "Maharashtra",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "karnal": {
        "location_name": "Karnal, Haryana, India",
        "latitude": 29.6857,
        "longitude": 76.9905,
        "admin1": "Haryana",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "ludhiana": {
        "location_name": "Ludhiana, Punjab, India",
        "latitude": 30.9010,
        "longitude": 75.8573,
        "admin1": "Punjab",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "varanasi": {
        "location_name": "Varanasi, Uttar Pradesh, India",
        "latitude": 25.3176,
        "longitude": 82.9739,
        "admin1": "Uttar Pradesh",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "guntur": {
        "location_name": "Guntur, Andhra Pradesh, India",
        "latitude": 16.3067,
        "longitude": 80.4365,
        "admin1": "Andhra Pradesh",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "indore": {
        "location_name": "Indore, Madhya Pradesh, India",
        "latitude": 22.7196,
        "longitude": 75.8577,
        "admin1": "Madhya Pradesh",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "coimbatore": {
        "location_name": "Coimbatore, Tamil Nadu, India",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "admin1": "Tamil Nadu",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
    "anand": {
        "location_name": "Anand, Gujarat, India",
        "latitude": 22.5645,
        "longitude": 72.9289,
        "admin1": "Gujarat",
        "country": "India",
        "source": "local_agri_registry",
        "status": "RESOLVED",
    },
}

_MEMORY_CACHE: dict[str, dict[str, Any]] = {}


def _clean_query(query: str | None) -> str:
    if not query:
        return ""
    clean = re.sub(r"[^\w\s,\-]", "", str(query).strip().lower())
    return " ".join(clean.split())


def search_locations(query: str, count: int = 5, timeout: float = 6) -> list[dict[str, Any]]:
    """Search for locations matching the query.

    Returns a list of resolved candidates.
    """
    clean = _clean_query(query)
    if not clean:
        return []

    # Check local dictionary first
    local_matches = []
    for k, v in LOCAL_FARM_LOCATIONS.items():
        if clean in k or k in clean or clean in v["location_name"].lower():
            local_matches.append({
                "name": v["location_name"].split(",")[0],
                "display_name": v["location_name"],
                "latitude": v["latitude"],
                "longitude": v["longitude"],
                "admin1": v.get("admin1", ""),
                "country": v.get("country", "India"),
                "source": "local_agri_registry",
                "status": "RESOLVED",
            })

    try:
        url = GEOCODING_BASE_URL
        params = {"name": clean, "count": count, "language": "en", "format": "json"}
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
                api_results = []
                for item in data["results"]:
                    name = item.get("name", "")
                    admin1 = item.get("admin1", "")
                    country = item.get("country", "")
                    display = ", ".join(x for x in [name, admin1, country] if x)
                    lat = float(item["latitude"])
                    lon = float(item["longitude"])
                    api_results.append({
                        "name": name,
                        "display_name": display,
                        "latitude": round(lat, 4),
                        "longitude": round(lon, 4),
                        "admin1": admin1,
                        "country": country,
                        "source": "open_meteo_geocoding",
                        "status": "RESOLVED",
                    })
                if api_results:
                    return api_results
    except Exception:
        pass

    return local_matches


def resolve_location(
    location_name: str | None,
    lat: float | None = None,
    lon: float | None = None,
    timeout: float = 6,
) -> dict[str, Any]:
    """Resolve location to internal coordinates with full provenance and validation.

    Never silently invents coordinates.
    """
    # 1. If explicit coordinates already provided (e.g. from internal selector)
    if lat is not None and lon is not None:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return {
                "submitted_location": location_name or "",
                "resolved_location": "",
                "latitude": None,
                "longitude": None,
                "source": "validation_error",
                "status": "INVALID",
                "error": f"Coordinates out of bounds: lat={lat}, lon={lon}",
            }
        return {
            "submitted_location": location_name or f"Coordinates ({lat}, {lon})",
            "resolved_location": location_name or f"Coordinates ({lat}, {lon})",
            "latitude": round(float(lat), 4),
            "longitude": round(float(lon), 4),
            "source": "caller_coordinates",
            "status": "RESOLVED",
            "error": None,
        }

    clean = _clean_query(location_name)
    if not clean:
        return {
            "submitted_location": location_name or "",
            "resolved_location": "",
            "latitude": None,
            "longitude": None,
            "source": "none",
            "status": "INVALID",
            "error": "Farm location name cannot be empty.",
        }

    # 2. Check memory cache
    if clean in _MEMORY_CACHE:
        return _MEMORY_CACHE[clean]

    # 3. Check local farm locations
    for k, v in LOCAL_FARM_LOCATIONS.items():
        if clean == k or clean in k or k in clean or clean in v["location_name"].lower():
            res = {
                "submitted_location": location_name,
                "resolved_location": v["location_name"],
                "latitude": v["latitude"],
                "longitude": v["longitude"],
                "source": v["source"],
                "status": "RESOLVED",
                "precision": "city_centroid",
                "precision_note": "Coordinates represent regional municipal centroid. For farm-level precision, enter exact GPS coordinates.",
                "error": None,
            }
            _MEMORY_CACHE[clean] = res
            return res

    # 4. Query Open-Meteo Geocoding API
    try:
        url = GEOCODING_BASE_URL
        params = {"name": clean, "count": 5, "language": "en", "format": "json"}
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code != 200:
            return {
                "submitted_location": location_name,
                "resolved_location": "",
                "latitude": None,
                "longitude": None,
                "source": "open_meteo_geocoding",
                "status": "ERROR",
                "precision": "unknown",
                "precision_note": "",
                "error": f"Geocoding service returned status {resp.status_code}",
            }

        data = resp.json()
        if not isinstance(data, dict):
            return {
                "submitted_location": location_name,
                "resolved_location": "",
                "latitude": None,
                "longitude": None,
                "source": "open_meteo_geocoding",
                "status": "INVALID",
                "precision": "unknown",
                "precision_note": "",
                "error": "Malformed geocoding response",
            }

        results = data.get("results")
        if not results or not isinstance(results, list):
            return {
                "submitted_location": location_name,
                "resolved_location": "",
                "latitude": None,
                "longitude": None,
                "source": "open_meteo_geocoding",
                "status": "NOT_FOUND",
                "precision": "unknown",
                "precision_note": "",
                "error": f"No geocoding match found for location '{location_name}'",
            }

        top = results[0]
        name = top.get("name", "")
        admin1 = top.get("admin1", "")
        country = top.get("country", "")
        display = ", ".join(x for x in [name, admin1, country] if x)
        lat_val = float(top["latitude"])
        lon_val = float(top["longitude"])

        status = "RESOLVED"
        if len(results) > 1 and clean in ["india", "north", "south"]:
            status = "AMBIGUOUS"

        res = {
            "submitted_location": location_name,
            "resolved_location": display,
            "latitude": round(lat_val, 4),
            "longitude": round(lon_val, 4),
            "source": "open_meteo_geocoding",
            "status": status,
            "precision": "city_centroid" if not top.get("feature_code", "").startswith("PPLX") else "suburb",
            "precision_note": "Coordinates represent regional municipal centroid. For farm-level precision, enter exact GPS coordinates.",
            "error": None,
        }
        _MEMORY_CACHE[clean] = res
        return res

    except requests.exceptions.Timeout:
        return {
            "submitted_location": location_name,
            "resolved_location": "",
            "latitude": None,
            "longitude": None,
            "source": "open_meteo_geocoding",
            "status": "TIMEOUT",
            "error": "Geocoding request timed out.",
        }
    except Exception as exc:
        return {
            "submitted_location": location_name,
            "resolved_location": "",
            "latitude": None,
            "longitude": None,
            "source": "open_meteo_geocoding",
            "status": "ERROR",
            "error": str(exc),
        }
