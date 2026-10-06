"""Soil Agent — nutrient deficiency scoring."""
from __future__ import annotations
from data_sources.soil import get_reference_targets, get_provenance
from orchestrator.state import SoilResult


def _deficiency(actual: float, target: float) -> float:
    if target <= 0: return 0.0
    return round(max(0.0, (target - actual) / target), 4)


def run(
    n: float | None = None,
    p: float | None = None,
    k: float | None = None,
    crop: str = "",
    soil_type: str = "",
    mode: str = "",
    targets: dict | None = None,
    weights: dict | None = None,
) -> SoilResult:
    has_npk = (n is not None and p is not None and k is not None)
    ref_targets, ref_weights = get_reference_targets(crop, soil_type)

    if not has_npk:
        # CRITICAL: Missing NPK must NOT fabricate nutrient deficiency or use standard default
        determined_mode = mode or ("USER_SELECTED" if soil_type else "UNAVAILABLE")
        prov = get_provenance(crop, soil_type, mode=determined_mode, npk_available=False)
        supplied_dict = {
            "n": float(n) if n is not None else None,
            "p": float(p) if p is not None else None,
            "k": float(k) if k is not None else None,
        }
        return SoilResult(
            nitrogen_deficiency=None,
            phosphorus_deficiency=None,
            potassium_deficiency=None,
            overall_deficiency=None,
            nutrient_status="UNAVAILABLE",
            nutrient_assessment_text="Soil nutrient assessment: Unavailable. NPK measurements were not provided, so nutrient deficiency was not calculated.",
            priority_nutrient="",
            confidence=0.0,
            supplied=supplied_dict,
            targets=targets or ref_targets,
            crop=crop,
            soil_type=soil_type,
            calibration_source="project_calibration_heuristic" if crop or soil_type else "standard_default",
            provenance=prov,
            npk_available=False,
            status=determined_mode,
        )

    # Measured NPK supplied
    determined_mode = mode or "MEASURED"
    prov = get_provenance(crop, soil_type, mode=determined_mode, npk_available=True)
    targets = targets or ref_targets
    weights = weights or ref_weights

    dn = _deficiency(float(n), targets["N"])
    dp = _deficiency(float(p), targets["P"])
    dk = _deficiency(float(k), targets["K"])
    deficiencies = {"nitrogen": dn, "phosphorus": dp, "potassium": dk}
    overall = round(weights["N"] * dn + weights["P"] * dp + weights["K"] * dk, 4)

    return SoilResult(
        nitrogen_deficiency=dn,
        phosphorus_deficiency=dp,
        potassium_deficiency=dk,
        overall_deficiency=overall,
        nutrient_status="MEASURED",
        nutrient_assessment_text=f"Soil nutrient deficiency evaluated: {overall:.2f} (priority: {max(deficiencies, key=deficiencies.get)}).",
        priority_nutrient=max(deficiencies, key=deficiencies.get),
        confidence=0.9,
        supplied={"n": float(n), "p": float(p), "k": float(k)},
        targets=targets,
        crop=crop,
        soil_type=soil_type,
        calibration_source="project_calibration_heuristic" if crop or soil_type else "standard_default",
        provenance=prov,
        npk_available=True,
        status="MEASURED",
    )

