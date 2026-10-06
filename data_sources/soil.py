"""Soil reference provider and calibration provenance.

This module provides agronomic reference targets (N, P, K in kg/ha equivalent)
and priority weights calibrated by crop family and soil texture type.

PROVENANCE & ATTRIBUTION NOTICE:
--------------------------------
The numeric reference values and multipliers in this module are PROJECT
CALIBRATION ASSUMPTIONS, HEURISTIC REFERENCE TARGETS, and ENGINEERING DEFAULTS.
They are NOT official or page-traceable ICAR recommendations.

While informed by general Indian agricultural principles (such as higher N demand
in cereals and elevated P requirements for legume root nodulation as broadly
discussed in Indian agronomic literature), exact fertilizer doses depend on local
soil tests, regional agro-climatic zones, and cultivar characteristics.

Actual field applications must always be validated against authoritative local
agronomic guidance (e.g., State Agricultural Universities [SAUs] Package of
Practices, or district-level ICAR Krishi Vigyan Kendra [KVK] soil health card
recommendations).
"""
from __future__ import annotations

# ==============================================================================
# PROVENANCE CLASSIFICATION CATEGORIES (Step 4 compliance)
# ==============================================================================
PROVENANCE_AUTHORITATIVE = "authoritative_source_backed"  # Directly cited from published bulletin table
PROVENANCE_HEURISTIC = "project_calibration_heuristic"    # Engineering heuristic baseline
PROVENANCE_FALLBACK = "engineering_fallback_default"      # Generic standard default

# ==============================================================================
# 1. FALLBACK / DEFAULT VALUES (Category: engineering_fallback_default)
# ==============================================================================
# Standard baseline defaults (kg/ha equivalent) applied when crop is unspecified
DEFAULT_TARGETS = {"N": 100.0, "P": 50.0, "K": 100.0}
DEFAULT_WEIGHTS = {"N": 0.5, "P": 0.2, "K": 0.3}

# ==============================================================================
# 2. CROP-SPECIFIC REFERENCE TARGETS (Category: project_calibration_heuristic)
# ==============================================================================
# Heuristic crop reference baselines (kg/ha equivalent) for deficiency calculations.
# Note: Not directly cited to specific ICAR bulletin pages; used as project baselines.
CROP_TARGETS: dict[str, dict[str, float]] = {
    "tomato": {"N": 120.0, "P": 60.0, "K": 80.0},
    "potato": {"N": 150.0, "P": 60.0, "K": 120.0},
    "rice": {"N": 100.0, "P": 40.0, "K": 40.0},
    "paddy": {"N": 100.0, "P": 40.0, "K": 40.0},
    "wheat": {"N": 120.0, "P": 60.0, "K": 40.0},
    "maize": {"N": 120.0, "P": 60.0, "K": 50.0},
    "corn": {"N": 120.0, "P": 60.0, "K": 50.0},
    "cotton": {"N": 120.0, "P": 60.0, "K": 60.0},
    "groundnut": {"N": 25.0, "P": 50.0, "K": 40.0},
    "peanut": {"N": 25.0, "P": 50.0, "K": 40.0},
    "soybean": {"N": 30.0, "P": 60.0, "K": 40.0},
    "pigeonpea": {"N": 25.0, "P": 50.0, "K": 30.0},
    "chilli": {"N": 100.0, "P": 50.0, "K": 50.0},
    "bell_pepper": {"N": 100.0, "P": 50.0, "K": 50.0},
    "apple": {"N": 100.0, "P": 50.0, "K": 100.0},
}

# Legume crops fix nitrogen and rely heavily on phosphorus for root nodulation
LEGUME_CROPS = {"groundnut", "peanut", "soybean", "pigeonpea", "blackgram", "greengram", "chickpea"}
LEGUME_WEIGHTS = {"N": 0.25, "P": 0.50, "K": 0.25}

# ==============================================================================
# 3. SOIL TYPE TEXTURE MULTIPLIERS (Category: project_calibration_heuristic)
# ==============================================================================
# Heuristic adjustments modeling soil nutrient retention vs leaching behavior:
# - Sandy: lower CEC, higher nitrate/potash leaching -> positive adjustment multiplier
# - Clay/Black: high CEC, potassium-rich vertisols -> lower N/K adjustment multiplier
# - Loam/Alluvial: balanced reference baseline (1.00)
SOIL_TYPE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "sandy": {"N": 1.10, "P": 1.00, "K": 1.10},       # High leaching, lower nutrient retention
    "red": {"N": 1.05, "P": 1.00, "K": 1.05},
    "clay": {"N": 0.95, "P": 1.05, "K": 0.90},       # High retention, potassium naturally higher in vertisols
    "black": {"N": 0.95, "P": 1.05, "K": 0.90},
    "loam": {"N": 1.00, "P": 1.00, "K": 1.00},       # Balanced loam reference
    "alluvial": {"N": 1.00, "P": 1.00, "K": 1.00},
}


def get_reference_targets(crop: str = "", soil_type: str = "") -> tuple[dict, dict]:
    """Retrieve calibrated NPK reference targets and weights."""
    crop_key = (crop or "").strip().lower().replace(" ", "_")
    base_targets = CROP_TARGETS.get(crop_key, DEFAULT_TARGETS).copy()

    # Determine nutrient weights based on crop family
    weights = LEGUME_WEIGHTS.copy() if crop_key in LEGUME_CROPS else DEFAULT_WEIGHTS.copy()

    # Apply soil type adjustments if recognized
    soil_key = (soil_type or "").strip().lower()
    multipliers = SOIL_TYPE_MULTIPLIERS.get(soil_key, {"N": 1.0, "P": 1.0, "K": 1.0})

    targets = {
        k: round(base_targets[k] * multipliers[k], 2)
        for k in ("N", "P", "K")
    }

    return targets, weights


# Standard Manual Soil Type Options
STANDARD_SOIL_TYPES = [
    {"id": "sandy", "name": "Sandy"},
    {"id": "sandy_loam", "name": "Sandy Loam"},
    {"id": "loam", "name": "Loam"},
    {"id": "clay", "name": "Clay"},
    {"id": "clay_loam", "name": "Clay Loam"},
    {"id": "red", "name": "Red Soil"},
    {"id": "black", "name": "Black Soil"},
    {"id": "alluvial", "name": "Alluvial"},
    {"id": "laterite", "name": "Laterite"},
    {"id": "unknown", "name": "Unknown"},
]


def estimate_soil_from_location(
    location_name: str = "",
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    """Provide conservative location-derived soil estimation.

    Never claims location-derived soil is measured field data.
    """
    loc_clean = (location_name or "").lower()

    soil_type = "loam"
    region_source = "regional_agroclimatic_heuristic"

    if any(k in loc_clean for k in ["punjab", "haryana", "uttar pradesh", "bihar", "bengal", "ganga", "karnal", "ludhiana", "varanasi"]):
        soil_type = "alluvial"
    elif any(k in loc_clean for k in ["maharashtra", "deccan", "pune", "nashik", "indore", "madhya pradesh"]):
        soil_type = "black"
    elif any(k in loc_clean for k in ["tamil nadu", "chennai", "madurai", "coimbatore", "karnataka", "andhra", "guntur", "telangana", "odisha"]):
        soil_type = "red"
    elif any(k in loc_clean for k in ["rajasthan", "thar", "gujarat", "anand"]):
        soil_type = "sandy_loam"
    elif lat is not None and lon is not None:
        if lat > 26.0 and 74.0 <= lon <= 88.0:
            soil_type = "alluvial"
        elif 16.0 <= lat <= 24.0 and 73.0 <= lon <= 80.0:
            soil_type = "black"
        elif lat < 16.0:
            soil_type = "red"
        else:
            soil_type = "loam"
    else:
        return {
            "soil_type": "unknown",
            "source": "none",
            "confidence": 0.0,
            "status": "UNAVAILABLE",
            "is_measured": False,
        }

    return {
        "soil_type": soil_type,
        "source": region_source,
        "confidence": 0.60,
        "status": "LOCATION_ESTIMATED",
        "is_measured": False,
        "note": "Estimated from regional agro-ecological zone; not a field measurement.",
    }


def get_provenance(crop: str = "", soil_type: str = "", mode: str = "MEASURED", npk_available: bool = True) -> dict:
    """Return explicit provenance audit metadata for the given crop and soil configuration."""
    crop_key = (crop or "").strip().lower().replace(" ", "_")
    soil_key = (soil_type or "").strip().lower()

    crop_prov = PROVENANCE_HEURISTIC if crop_key in CROP_TARGETS else PROVENANCE_FALLBACK
    soil_prov = PROVENANCE_HEURISTIC if soil_key in SOIL_TYPE_MULTIPLIERS else PROVENANCE_FALLBACK

    valid_modes = {"MEASURED", "LOCATION_ESTIMATED", "USER_SELECTED", "UNAVAILABLE"}
    provenance_mode = mode if mode in valid_modes else ("MEASURED" if npk_available else "UNAVAILABLE")

    return {
        "crop": crop or "unspecified",
        "soil_type": soil_type or "unspecified",
        "crop_target_provenance": crop_prov,
        "soil_multiplier_provenance": soil_prov,
        "mode": provenance_mode,
        "npk_available": npk_available,
        "is_authoritative_icar": False,
        "guidance_note": (
            "Values are project calibration heuristics. Real field application should be "
            "cross-referenced with local SAU Package of Practices or district KVK recommendations."
            if npk_available
            else "NPK values not measured. Soil deficiency evaluation skipped to avoid fabricating nutrition data."
        ),
    }

