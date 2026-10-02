"""Soil Agent — nutrient deficiency scoring."""
from __future__ import annotations
from data_sources.soil import get_reference_targets, get_provenance
from orchestrator.state import SoilResult


def _deficiency(actual: float, target: float) -> float:
    if target <= 0: return 0.0
    return round(max(0.0, (target - actual) / target), 4)


def run(n: float, p: float, k: float, crop: str = "", soil_type: str = "",
        targets: dict | None = None, weights: dict | None = None) -> SoilResult:
    ref_targets, ref_weights = get_reference_targets(crop, soil_type)
    prov = get_provenance(crop, soil_type)
    targets = targets or ref_targets
    weights = weights or ref_weights
    dn, dp, dk = _deficiency(float(n), targets["N"]), _deficiency(float(p), targets["P"]), _deficiency(float(k), targets["K"])
    deficiencies = {"nitrogen": dn, "phosphorus": dp, "potassium": dk}
    overall = round(weights["N"]*dn + weights["P"]*dp + weights["K"]*dk, 4)
    return SoilResult(
        nitrogen_deficiency=dn, phosphorus_deficiency=dp, potassium_deficiency=dk,
        overall_deficiency=overall, priority_nutrient=max(deficiencies, key=deficiencies.get),
        confidence=0.9,
        supplied={"n": float(n), "p": float(p), "k": float(k)},
        targets=targets,
        crop=crop,
        soil_type=soil_type,
        calibration_source="icar_crop_soil_calibrated" if crop or soil_type else "standard_default",
        provenance=prov,
    )
