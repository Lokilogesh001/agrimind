"""Evidence Quality Score & Breakdown calculation.

Separates Evidence Quality (trustworthiness, relevance, and completeness of underlying data)
from Decision Stability (internal agent consistency and conflict resolution).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data_sources.crops import get_crop_registry, STAGE_REGISTRY

# Configurable weights for Evidence Quality Score
EQS_WEIGHTS = {
    "crop_relevance": 0.20,
    "location_relevance": 0.20,
    "stage_relevance": 0.15,
    "source_reliability": 0.15,
    "temporal_relevance": 0.10,
    "completeness": 0.20,
}


@dataclass
class EvidenceQualityBreakdown:
    crop_relevance: float
    location_relevance: float
    stage_relevance: float
    source_reliability: float
    temporal_relevance: float
    completeness: float
    overall: float

    def to_dict(self) -> dict[str, float]:
        return {
            "crop_relevance": round(self.crop_relevance, 4),
            "location_relevance": round(self.location_relevance, 4),
            "stage_relevance": round(self.stage_relevance, 4),
            "source_reliability": round(self.source_reliability, 4),
            "temporal_relevance": round(self.temporal_relevance, 4),
            "completeness": round(self.completeness, 4),
            "overall": round(self.overall, 4),
        }


def get_evidence_quality_level(score: float) -> str:
    """Classify Evidence Quality Score into discrete tiers."""
    if score >= 0.75:
        return "GOOD"
    elif score >= 0.55:
        return "MODERATE"
    elif score >= 0.35:
        return "LOW"
    return "INSUFFICIENT"


def calculate_evidence_quality(
    state: Any,
    evidence_items: list[dict[str, Any]] | None = None,
    rag_evidence: list[dict[str, Any]] | None = None,
    weights: dict | None = None,
) -> tuple[float, str, EvidenceQualityBreakdown]:
    """Deterministically compute the Evidence Quality Score and breakdown (0.0 to 1.0).

    Does NOT use an LLM. Fully reproducible from structured evidence.
    """
    w = dict(EQS_WEIGHTS)
    if weights:
        w.update(weights)

    # 1. Crop relevance
    crop_name = getattr(state.crop, "crop", "") or ""
    all_registered_crops = {
        c.get("name", "").lower()
        for c in get_crop_registry()
        if isinstance(c, dict)
    }
    if crop_name and crop_name.lower() in all_registered_crops:
        crop_rel = 1.00
    elif crop_name:
        crop_rel = 0.70
    else:
        crop_rel = 0.00

    # 2. Location relevance
    raw = getattr(state, "raw_inputs", {}) or {}
    has_coords = raw.get("lat") is not None and raw.get("lon") is not None
    geo_status = raw.get("geocoding_status", "")
    if has_coords and geo_status in ("RESOLVED", "AVAILABLE"):
        loc_rel = 1.00
    elif has_coords:
        loc_rel = 0.85
    elif raw.get("location_name"):
        loc_rel = 0.50
    else:
        loc_rel = 0.00

    # 3. Growth stage match
    stage = getattr(state.crop, "growth_stage", "") or ""
    valid_stages = {
        s["id"].lower() for s in STAGE_REGISTRY if isinstance(s, dict)
    } | {
        s["name"].lower() for s in STAGE_REGISTRY if isinstance(s, dict)
    }
    if stage and stage.lower() in valid_stages:
        stage_rel = 1.00
    elif stage:
        stage_rel = 0.60
    else:
        stage_rel = 0.20

    # 4. Source reliability (mean across domain agents)
    sources = []
    if getattr(state.weather, "is_available", False) and getattr(state.weather, "status", "") == "AVAILABLE":
        sources.append(0.90)  # Open-Meteo live API
    else:
        sources.append(0.20)

    soil_mode = getattr(state.soil, "status", "")
    if getattr(state.soil, "npk_available", False) and soil_mode == "MEASURED":
        sources.append(0.95)  # Direct laboratory measurement
    elif soil_mode == "LOCATION_ESTIMATED":
        sources.append(0.65)  # Regional agroclimatic heuristic
    elif getattr(state.soil, "soil_type", ""):
        sources.append(0.70)  # User selected soil type
    else:
        sources.append(0.20)

    if getattr(state.disease, "predicted_class", None):
        sources.append(0.85)  # PlantVillage MobileNet
    else:
        sources.append(0.50)  # Neutral if image not needed

    src_rel = sum(sources) / len(sources)

    # 5. Temporal relevance (live / recent / static)
    temp_scores = []
    if getattr(state.weather, "is_available", False) and getattr(state.weather, "status", "") == "AVAILABLE":
        temp_scores.append(1.00)  # Real-time forecast
    else:
        temp_scores.append(0.30)

    if getattr(state.market, "is_available", False):
        if getattr(state.market, "status", "") == "REAL_DATA":
            temp_scores.append(1.00)
        else:
            temp_scores.append(0.80)  # Demo/caller provided
    else:
        temp_scores.append(0.50)

    if rag_evidence:
        rag_crops = [float(h.get("crop_relevance", 0.0)) for h in rag_evidence]
        rag_locs = [float(h.get("location_relevance", 0.0)) for h in rag_evidence]
        rag_stages = [float(h.get("stage_relevance", 0.0)) for h in rag_evidence]
        rag_srcs = [float(h.get("source_reliability", 0.70)) for h in rag_evidence]
        rag_temps = [float(h.get("temporal_relevance", 0.85)) for h in rag_evidence]

        avg_rag_crop = sum(rag_crops) / len(rag_crops) if rag_crops else 0.50
        avg_rag_loc = sum(rag_locs) / len(rag_locs) if rag_locs else 0.50
        avg_rag_stage = sum(rag_stages) / len(rag_stages) if rag_stages else 0.50
        avg_rag_src = sum(rag_srcs) / len(rag_srcs) if rag_srcs else 0.70

        # Adjust evidence quality to reflect actual retrieved chunk relevance
        crop_rel = round(0.35 * crop_rel + 0.65 * avg_rag_crop, 4)
        loc_rel = round(0.35 * loc_rel + 0.65 * avg_rag_loc, 4)
        stage_rel = round(0.30 * stage_rel + 0.70 * avg_rag_stage, 4)
        sources.append(avg_rag_src)
        src_rel = sum(sources) / len(sources)
        temp_scores.append(sum(rag_temps) / len(rag_temps))

    temp_rel = sum(temp_scores) / len(temp_scores)

    # 6. Evidence completeness
    comp_points = 0.0
    total_points = 5.0
    if crop_name:
        comp_points += 1.0
    if has_coords or raw.get("location_name"):
        comp_points += 1.0
    if getattr(state.weather, "is_available", False) and getattr(state.weather, "status", "") == "AVAILABLE":
        comp_points += 1.0
    if getattr(state.soil, "npk_available", False):
        comp_points += 1.0  # Full soil card
    elif getattr(state.soil, "soil_type", ""):
        comp_points += 0.5  # Partial soil context
    if stage:
        comp_points += 1.0

    completeness = min(1.0, comp_points / total_points)

    # Overall weighted score
    overall = (
        w["crop_relevance"] * crop_rel
        + w["location_relevance"] * loc_rel
        + w["stage_relevance"] * stage_rel
        + w["source_reliability"] * src_rel
        + w["temporal_relevance"] * temp_rel
        + w["completeness"] * completeness
    )
    overall = max(0.0, min(1.0, round(overall, 4)))
    level = get_evidence_quality_level(overall)

    breakdown = EvidenceQualityBreakdown(
        crop_relevance=crop_rel,
        location_relevance=loc_rel,
        stage_relevance=stage_rel,
        source_reliability=src_rel,
        temporal_relevance=temp_rel,
        completeness=completeness,
        overall=overall,
    )

    return overall, level, breakdown
