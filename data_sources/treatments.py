"""Authoritative Verified Treatment Catalog & Permission State Machine for AgriMind.

Provides:
1. Verified crop/disease treatment catalog based on official recommendations
   (CIBRC pesticide registrations, TNAU Crop Production Guide, ICAR Kharif Agro-Advisory).
2. Deterministic Treatment-Permission State Machine:
   - PERMITTED: All agronomic, meteorological, and label safety conditions satisfied.
   - DEFERRED_WEATHER: High rainfall risk or imminent precipitation threatens washoff/leaching.
   - DEFERRED_UNVERIFIED: Low classifier confidence (<0.60) or unverified field symptoms.
   - RESTRICTED_CROP_MISMATCH: Detected pathogen conflicts with selected crop.
   - NO_ACTION_REQUIRED: Foliage is healthy or no disease detected.
   - UNREGISTERED_EXTENSION_REFERRAL: Crop/disease combination has no certified chemical label;
     safe cultural guidance and KVK / extension referral emitted instead of blind dosage guessing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class VerifiedTreatment:
    crop: str
    disease_key: str
    disease_name: str
    active_ingredient: str
    formulation: str
    dosage: str
    dosage_rate_per_liter: str
    water_volume_per_acre: str
    pre_harvest_interval_days: int
    re_entry_interval_hours: int
    ppe_requirements: list[str]
    rainfastness_window_hours: int
    registration_status: str
    authoritative_source: str
    cultural_measures: str
    application_notes: str


# ==============================================================================
# AUTHORITATIVE TREATMENT CATALOG
# Cross-referenced with CIBRC India, TNAU CPG (Horticulture/Agriculture), ICAR 2025
# ==============================================================================
VERIFIED_TREATMENTS: dict[tuple[str, str], VerifiedTreatment] = {
    # --------------------------------------------------------------------------
    # TOMATO
    # --------------------------------------------------------------------------
    ("tomato", "early_blight"): VerifiedTreatment(
        crop="Tomato",
        disease_key="early_blight",
        disease_name="Early Blight (Alternaria solani)",
        active_ingredient="Mancozeb 75% WP or Chlorothalonil 75% WP",
        formulation="Mancozeb 75 WP or Chlorothalonil 75 WP",
        dosage="2.0 g/L of water",
        dosage_rate_per_liter="2.0 g/L",
        water_volume_per_acre="200–250 L",
        pre_harvest_interval_days=5,
        re_entry_interval_hours=24,
        ppe_requirements=["N95/chemical mist mask", "Nitrile chemical gloves", "Eye protection goggles", "Full-sleeve protective clothing"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved for Tomato Early Blight",
        authoritative_source="TNAU Crop Production Guide 2024 & ICAR Kharif Advisory 2025 (p. 86)",
        cultural_measures="Prune lower senescent leaves showing early target-spot lesions. Ensure wide plant spacing (60×45 cm) for canopy aeration. Avoid overhead sprinkler irrigation.",
        application_notes="Apply at earliest appearance of concentric target lesions on lower foliage. Ensure thorough spray coverage on both adaxial and abaxial leaf surfaces.",
    ),
    ("tomato", "late_blight"): VerifiedTreatment(
        crop="Tomato",
        disease_key="late_blight",
        disease_name="Late Blight (Phytophthora infestans)",
        active_ingredient="Cymoxanil 8% + Mancozeb 64% WP or Metalaxyl-M 4% + Mancozeb 64% WP",
        formulation="Cymoxanil + Mancozeb 72 WP",
        dosage="1.5–2.0 g/L of water",
        dosage_rate_per_liter="1.75 g/L",
        water_volume_per_acre="200–250 L",
        pre_harvest_interval_days=7,
        re_entry_interval_hours=24,
        ppe_requirements=["Respirator mask with organic vapor cartridge", "Nitrile gloves", "Chemical apron", "Protective eyewear"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved for Tomato Late Blight",
        authoritative_source="ICAR Kharif Advisory 2025 (p. 86, 134) & TNAU Plant Pathology",
        cultural_measures="Rogue and destroy infected shoots immediately; bag debris to prevent spore dispersal. Maintain furrow drainage to prevent root moisture stagnation.",
        application_notes="Apply prophylactically when cool, humid, foggy weather persists. Repeat at 7–10 day intervals if blight-conducive weather continues.",
    ),
    ("tomato", "bacterial_spot"): VerifiedTreatment(
        crop="Tomato",
        disease_key="bacterial_spot",
        disease_name="Bacterial Spot (Xanthomonas campestris)",
        active_ingredient="Copper Oxychloride 50% WP + Streptocycline",
        formulation="Copper Oxychloride 50 WP (2.5 g/L) + Streptocycline (100 ppm / 0.1 g/L)",
        dosage="2.5 g/L COC + 0.1 g/L Streptocycline",
        dosage_rate_per_liter="2.5 g/L + 0.1 g/L",
        water_volume_per_acre="200 L",
        pre_harvest_interval_days=3,
        re_entry_interval_hours=24,
        ppe_requirements=["Chemical resistant gloves", "Face shield", "Rubber boots", "Protective coverall"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved Combination",
        authoritative_source="TNAU Crop Protection Compendium & ICAR Horticulture Advisory",
        cultural_measures="Do not handle or prune plants when foliage is wet. Sterilize pruning shears with 10% sodium hypochlorite or alcohol between rows.",
        application_notes="Copper acts as a surface protectant. Ensure complete coverage before rainfall events, but do not spray during imminent downpours.",
    ),
    ("tomato", "leaf_mold"): VerifiedTreatment(
        crop="Tomato",
        disease_key="leaf_mold",
        disease_name="Leaf Mold (Passalora fulva)",
        active_ingredient="Mancozeb 75% WP",
        formulation="Mancozeb 75 WP",
        dosage="2.0 g/L of water",
        dosage_rate_per_liter="2.0 g/L",
        water_volume_per_acre="200 L",
        pre_harvest_interval_days=5,
        re_entry_interval_hours=24,
        ppe_requirements=["Chemical gloves", "Protective glasses", "Cotton dust mask"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved",
        authoritative_source="ICAR Agro-Advisory 2025",
        cultural_measures="Improve ventilation around lower branches. Reduce greenhouse relative humidity below 85% where applicable.",
        application_notes="Target the undersides of leaves where velvety olive-green mold sporulation occurs.",
    ),

    # --------------------------------------------------------------------------
    # POTATO
    # --------------------------------------------------------------------------
    ("potato", "early_blight"): VerifiedTreatment(
        crop="Potato",
        disease_key="early_blight",
        disease_name="Early Blight (Alternaria solani)",
        active_ingredient="Chlorothalonil 75% WP or Mancozeb 75% WP",
        formulation="Chlorothalonil 75 WP",
        dosage="2.0–2.5 g/L of water",
        dosage_rate_per_liter="2.0 g/L",
        water_volume_per_acre="200–250 L",
        pre_harvest_interval_days=7,
        re_entry_interval_hours=24,
        ppe_requirements=["Chemical gloves", "Safety goggles", "Protective clothing"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved for Potato",
        authoritative_source="ICAR-CPRI (Central Potato Research Institute) & ICAR 2025 (p. 268)",
        cultural_measures="Adopt balanced potash fertilization to enhance physiological leaf tolerance. Destroy volunteer potato plants and solanaceous weeds.",
        application_notes="Initiate spray at first appearance of symptoms (usually 45–50 days after planting).",
    ),
    ("potato", "late_blight"): VerifiedTreatment(
        crop="Potato",
        disease_key="late_blight",
        disease_name="Late Blight (Phytophthora infestans)",
        active_ingredient="Dimethomorph 50% WP or Cymoxanil 8% + Mancozeb 64% WP",
        formulation="Cymoxanil 8% + Mancozeb 64% WP",
        dosage="2.0 g/L of water",
        dosage_rate_per_liter="2.0 g/L",
        water_volume_per_acre="250 L",
        pre_harvest_interval_days=10,
        re_entry_interval_hours=24,
        ppe_requirements=["Full chemical mist respirator", "Chemical apron", "Nitrile gloves", "Eye protection"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved for Potato Late Blight",
        authoritative_source="ICAR-CPRI Technical Bulletins & ICAR 2025 (p. 268)",
        cultural_measures="Earthing up to minimum 15 cm ridge height prevents zoospores from washing down into developing tubers. Destroy haulms 10 days before harvest if late blight is active.",
        application_notes="Critical: Late blight can destroy a field in 4–7 days. Prophylactic protection is mandatory during cloudy, mist-laden weather with RH > 85%.",
    ),

    # --------------------------------------------------------------------------
    # RICE (PADDY)
    # --------------------------------------------------------------------------
    ("rice", "blast"): VerifiedTreatment(
        crop="Rice",
        disease_key="blast",
        disease_name="Rice Blast (Magnaporthe oryzae)",
        active_ingredient="Tricyclazole 75% WP",
        formulation="Tricyclazole 75 WP",
        dosage="0.6 g/L of water",
        dosage_rate_per_liter="0.6 g/L",
        water_volume_per_acre="200 L",
        pre_harvest_interval_days=14,
        re_entry_interval_hours=24,
        ppe_requirements=["Protective mask", "Rubber gloves", "Protective boots"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved for Rice Blast",
        authoritative_source="TNAU Agritech Portal & ICAR Kharif Advisory 2025 (p. 14)",
        cultural_measures="Avoid split urea over-application during active tillering and panicle initiation. Maintain shallow water depth (2–5 cm) in field.",
        application_notes="Apply at first spindle-shaped lesion detection on leaves, or at boot leaf stage to prevent neck blast.",
    ),
    ("rice", "brown_spot"): VerifiedTreatment(
        crop="Rice",
        disease_key="brown_spot",
        disease_name="Brown Spot (Bipolaris oryzae)",
        active_ingredient="Mancozeb 75% WP or Propiconazole 25% EC",
        formulation="Mancozeb 75 WP (2.0 g/L) or Propiconazole 25 EC (1.0 ml/L)",
        dosage="2.0 g/L (Mancozeb) or 1.0 ml/L (Propiconazole)",
        dosage_rate_per_liter="2.0 g/L",
        water_volume_per_acre="200 L",
        pre_harvest_interval_days=15,
        re_entry_interval_hours=24,
        ppe_requirements=["Chemical gloves", "Protective glasses", "Dust mask"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved for Rice",
        authoritative_source="TNAU Crop Protection Guide 2024",
        cultural_measures="Correct soil potassium and silicon deficiencies which predispose plants to brown spot infection. Ensure balanced nutrition.",
        application_notes="Foliar spray at early tillering and boot leaf emergence.",
    ),
    ("rice", "bacterial_leaf_blight"): VerifiedTreatment(
        crop="Rice",
        disease_key="bacterial_leaf_blight",
        disease_name="Bacterial Leaf Blight (Xanthomonas oryzae pv. oryzae)",
        active_ingredient="Copper Oxychloride 50% WP + Streptocycline",
        formulation="Copper Oxychloride 50 WP (2.5 g/L) + Streptocycline (0.1 g/L)",
        dosage="2.5 g/L + 0.1 g/L",
        dosage_rate_per_liter="2.5 g/L + 0.1 g/L",
        water_volume_per_acre="200 L",
        pre_harvest_interval_days=10,
        re_entry_interval_hours=24,
        ppe_requirements=["Protective eye goggles", "Chemical resistant gloves", "Protective coverall"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved",
        authoritative_source="TNAU Paddy Protection & ICAR 2025",
        cultural_measures="Drain stagnant field water. Avoid clipping seedling leaf tips during transplantation. Withhold nitrogen top-dressing during active leaf clipping.",
        application_notes="Spray upon detecting wavy translucent leaf margins; strictly avoid spraying during heavy rains.",
    ),

    # --------------------------------------------------------------------------
    # CHILLI (PEPPER)
    # --------------------------------------------------------------------------
    ("chilli", "leaf_spot"): VerifiedTreatment(
        crop="Chilli",
        disease_key="leaf_spot",
        disease_name="Cercospora Leaf Spot / Anthracnose",
        active_ingredient="Chlorothalonil 75% WP or Azoxystrobin 23% SC",
        formulation="Chlorothalonil 75 WP (2.0 g/L) or Azoxystrobin 23 SC (1.0 ml/L)",
        dosage="2.0 g/L (Chlorothalonil) or 1.0 ml/L (Azoxystrobin)",
        dosage_rate_per_liter="2.0 g/L",
        water_volume_per_acre="200 L",
        pre_harvest_interval_days=5,
        re_entry_interval_hours=24,
        ppe_requirements=["Chemical gloves", "Protective goggles", "Protective mask"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved for Chilli",
        authoritative_source="ICAR Kharif Advisory 2025 (p. 86) & TNAU Vegetable Guide",
        cultural_measures="Collect and burn crop residues after harvest. Spray neem seed kernel extract (NSKE 5%) prophylactically.",
        application_notes="Foliar spray every 15 days upon first symptom appearance.",
    ),
    ("chilli", "bacterial_spot"): VerifiedTreatment(
        crop="Chilli",
        disease_key="bacterial_spot",
        disease_name="Bacterial Spot (Xanthomonas vesicatoria)",
        active_ingredient="Copper Oxychloride 50% WP + Streptocycline",
        formulation="Copper Oxychloride 50 WP (2.5 g/L) + Streptocycline (0.1 g/L)",
        dosage="2.5 g/L + 0.1 g/L",
        dosage_rate_per_liter="2.5 g/L + 0.1 g/L",
        water_volume_per_acre="200 L",
        pre_harvest_interval_days=3,
        re_entry_interval_hours=24,
        ppe_requirements=["Chemical gloves", "Protective goggles", "Mask"],
        rainfastness_window_hours=24,
        registration_status="CIBRC Approved",
        authoritative_source="TNAU Crop Protection Guide",
        cultural_measures="Sanitize equipment. Avoid movement through field while plants are damp.",
        application_notes="Apply upon initial symptom detection on foliage or green pods.",
    ),
}


@dataclass
class TreatmentPermission:
    status: str  # PERMITTED | DEFERRED_WEATHER | DEFERRED_UNVERIFIED | RESTRICTED_CROP_MISMATCH | NO_ACTION_REQUIRED | UNREGISTERED_EXTENSION_REFERRAL
    candidate_treatment: Optional[VerifiedTreatment] = None
    is_permitted: bool = False
    action_instruction: str = ""
    weather_hold: bool = False
    rain_free_window_hours: int = 0
    reassessment_trigger: str = ""
    cultural_measures: str = ""
    safety_disclaimer: str = ""
    authority_reference: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "is_permitted": self.is_permitted,
            "action_instruction": self.action_instruction,
            "weather_hold": self.weather_hold,
            "rain_free_window_hours": self.rain_free_window_hours,
            "reassessment_trigger": self.reassessment_trigger,
            "cultural_measures": self.cultural_measures,
            "safety_disclaimer": self.safety_disclaimer,
            "authority_reference": self.authority_reference,
            "treatment_details": (
                {
                    "crop": self.candidate_treatment.crop,
                    "disease_name": self.candidate_treatment.disease_name,
                    "active_ingredient": self.candidate_treatment.active_ingredient,
                    "formulation": self.candidate_treatment.formulation,
                    "dosage": self.candidate_treatment.dosage,
                    "water_volume_per_acre": self.candidate_treatment.water_volume_per_acre,
                    "pre_harvest_interval_days": self.candidate_treatment.pre_harvest_interval_days,
                    "re_entry_interval_hours": self.candidate_treatment.re_entry_interval_hours,
                    "ppe_requirements": self.candidate_treatment.ppe_requirements,
                    "rainfastness_window_hours": self.candidate_treatment.rainfastness_window_hours,
                    "registration_status": self.candidate_treatment.registration_status,
                    "authoritative_source": self.candidate_treatment.authoritative_source,
                    "application_notes": self.candidate_treatment.application_notes,
                }
                if self.candidate_treatment
                else None
            ),
        }


def lookup_verified_treatment(crop: str, disease_label: str | None) -> VerifiedTreatment | None:
    """Find registered treatment candidate in authoritative catalog."""
    if not crop or not disease_label:
        return None
    c_clean = crop.strip().lower()
    if c_clean in ("paddy", "rice"):
        c_clean = "rice"
    elif c_clean in ("pepper", "chilli", "chili"):
        c_clean = "chilli"

    d_clean = disease_label.strip().lower()
    if "___" in d_clean:
        d_clean = d_clean.split("___", 1)[1]
    d_clean = d_clean.replace(" ", "_").replace("-", "_")

    # Match normalized disease keys
    for (cat_crop, cat_dis), treatment in VERIFIED_TREATMENTS.items():
        if cat_crop == c_clean and (cat_dis in d_clean or d_clean in cat_dis):
            return treatment

    # Substring search
    for (cat_crop, cat_dis), treatment in VERIFIED_TREATMENTS.items():
        if cat_crop == c_clean:
            tokens = [t for t in cat_dis.split("_") if len(t) > 3]
            if any(t in d_clean for t in tokens):
                return treatment

    return None


get_verified_treatment = lookup_verified_treatment


def evaluate_treatment_permission_state(
    crop: str,
    disease_result: Any,
    weather_result: Any,
    final_action: str = "monitor",
    safety_constraints: list[str] | None = None,
) -> TreatmentPermission:
    """Deterministic Treatment-Permission State Machine.

    Enforces that chemical treatment instructions strictly agree with:
    1. Pathogen detection & crop-matching validation.
    2. Classifier confidence gate (>= 0.60).
    3. Stage-1 Hard Weather Safety Veto (Rainfall Risk >= 0.60 or DELAY action).
    4. CIBRC/TNAU/ICAR chemical registration catalog.
    """
    safety_constraints = safety_constraints or []
    norm_action = str(final_action or "").lower()

    # Step 0: Disease Diagnostic Model Status Check
    d_status = getattr(disease_result, "status", "AVAILABLE")
    if d_status == "MODEL_UNAVAILABLE":
        return TreatmentPermission(
            status="DEFERRED_MODEL_UNAVAILABLE",
            is_permitted=False,
            action_instruction="Disease diagnostic model is currently unavailable. Agrochemical treatment cannot proceed without verified diagnosis.",
            weather_hold=False,
            rain_free_window_hours=0,
            reassessment_trigger="Contact local Krishi Vigyan Kendra (KVK) extension officer or re-upload leaf image when diagnostic service is restored.",
            cultural_measures="Inspect crop manually for foliar lesions, isolate symptomatic leaves, and avoid unverified chemical sprays.",
            safety_disclaimer="Never apply agrochemicals based on unverified or failed automated diagnostic checks.",
            authority_reference="ICAR Standard Advisory Protocols",
        )
    if d_status == "INVALID_IMAGE":
        return TreatmentPermission(
            status="DEFERRED_INVALID_IMAGE",
            is_permitted=False,
            action_instruction="Submitted image could not be processed or is invalid. Agrochemical treatment held pending clear photographic evidence.",
            weather_hold=False,
            rain_free_window_hours=0,
            reassessment_trigger="Upload a clear, in-focus JPEG/PNG photo of a single symptomatic leaf under natural lighting.",
            cultural_measures="Maintain field sanitation and monitor for spreading lesions.",
            safety_disclaimer="Accurate diagnosis is required before applying chemical treatments.",
            authority_reference="ICAR Plant Pathology Guidelines",
        )

    # Step 1: No Disease or Healthy Foliage
    raw_class = getattr(disease_result, "predicted_class", None) or ""
    if not raw_class or "healthy" in raw_class.lower():
        return TreatmentPermission(
            status="NO_ACTION_REQUIRED",
            is_permitted=False,
            action_instruction="No active foliar pathogen detected. Chemical fungicidal sprays are not recommended.",
            weather_hold=False,
            rain_free_window_hours=0,
            reassessment_trigger="Continue weekly field scouting and maintain standard crop management.",
            cultural_measures="Maintain optimal plant spacing, sanitation, and balanced nutrition.",
            safety_disclaimer="Preventive agrochemical sprays are economically and ecologically unadvised without verified pest/pathogen presence.",
            authority_reference="ICAR Integrated Pest Management (IPM) Core Directives",
        )

    # Step 2: Crop Mismatch Check
    is_mismatch = bool(getattr(disease_result, "crop_mismatch", False))
    if is_mismatch:
        det_crop = getattr(disease_result, "crop_detected", "another crop") or "another crop"
        return TreatmentPermission(
            status="RESTRICTED_CROP_MISMATCH",
            is_permitted=False,
            action_instruction=f"Action blocked: Selected crop is '{crop}', but leaf characteristics match '{det_crop}'. Chemical application strictly prohibited.",
            weather_hold=False,
            rain_free_window_hours=0,
            reassessment_trigger="Upload a clear, in-focus photograph of the true crop foliage.",
            cultural_measures="Verify field planting rows and inspect for weed host species.",
            safety_disclaimer="Applying chemicals formulated or timed for other crop species can cause phytotoxic canopy scorching or illegal residue violations.",
            authority_reference="Central Insecticides Board & Registration Committee (CIBRC) Guidelines",
        )

    # Step 3: Low Classifier Confidence Gate
    d_conf = float(getattr(disease_result, "confidence", 0.0) or 0.0)
    if d_conf < 0.60:
        return TreatmentPermission(
            status="DEFERRED_UNVERIFIED",
            is_permitted=False,
            action_instruction=f"Diagnosis unverified ({round(d_conf * 100)}% confidence < 60% threshold). Chemical fungicides held pending in-person agronomist inspection.",
            weather_hold=False,
            rain_free_window_hours=0,
            reassessment_trigger="Submit additional leaf images under indirect sunlight or consult local Krishi Vigyan Kendra (KVK).",
            cultural_measures="Isolate suspect plants, remove fallen symptomatic leaves, and avoid working in wet canopies.",
            safety_disclaimer="Never apply broad-spectrum chemicals on unverified visual symptoms.",
            authority_reference="ICAR Diagnostics Protocol & Plant Protection Standards",
        )

    # Step 4: Identify Verified Treatment Candidate
    candidate = lookup_verified_treatment(crop, raw_class)
    if not candidate:
        # Non-prescriptive extension referral
        return TreatmentPermission(
            status="UNREGISTERED_EXTENSION_REFERRAL",
            is_permitted=False,
            action_instruction=f"No certified, locally registered chemical formulation found for '{crop}' with pathogen '{raw_class}'. Direct consultation with local KVK / State Agricultural Extension Officer required.",
            weather_hold=False,
            rain_free_window_hours=0,
            reassessment_trigger="Obtain certified local package of practices recommendation from district agricultural office.",
            cultural_measures="Rogue and destroy infected plant debris, prune lower canopy for aeration, and sanitize cutting tools.",
            safety_disclaimer="AgriMind will not guess unverified chemical dosages for non-cataloged crop-pathogen combinations.",
            authority_reference="State Agricultural University (SAU) Package of Practices & Extension Directorate",
        )

    # Step 5: Check Weather & Overarching Safety Veto
    w_status = getattr(weather_result, "status", "AVAILABLE") if weather_result else "UNAVAILABLE"
    w_freshness = getattr(weather_result, "freshness_status", "REAL_DATA") if weather_result else "UNAVAILABLE"
    w_is_stale = (w_status == "STALE_CACHE" or w_freshness == "STALE_CACHE" or getattr(weather_result, "is_stale", False))
    w_avail = (
        getattr(weather_result, "is_available", True)
        and w_status not in ("TIMEOUT", "UNAVAILABLE", "INVALID")
        and not w_is_stale
    )
    w_risk = float(getattr(weather_result, "rainfall_risk", 0.0) or 0.0)
    w_level = str(getattr(weather_result, "risk_level", "LOW")).upper()
    is_rain_delay = norm_action.startswith("delay") or (w_avail and (w_risk >= 0.60 or w_level in ("HIGH", "SEVERE")))

    if not w_avail:
        window_h = candidate.rainfastness_window_hours or 24
        desc_status = "stale observation (>15 min cache)" if w_is_stale else f"unverified ({w_status})"
        return TreatmentPermission(
            status="DEFERRED_WEATHER",
            candidate_treatment=candidate,
            is_permitted=False,
            weather_hold=True,
            rain_free_window_hours=window_h,
            action_instruction=(
                f"Foliar chemical spraying DEFERRED: Meteorological forecast is {desc_status}. "
                f"Chemical application requires a verified rain-free window of at least {window_h} hours "
                f"for {candidate.formulation} adhesion. Spraying without current weather confirmation is prohibited."
            ),
            reassessment_trigger=(
                "Re-evaluate spraying window once meteorological telemetry is restored or fresh observation is retrieved."
            ),
            cultural_measures=(
                f"IMMEDIATE ACTION (Non-Chemical): {candidate.cultural_measures} "
                "Ensure drainage furrows are open to prevent root-zone waterlogging."
            ),
            safety_disclaimer=(
                "Applying agrochemicals under unknown weather conditions risks immediate chemical wash-off "
                "and environmental contamination. Verify dry weather window before spraying."
            ),
            authority_reference="ICAR Rain Safety & CIBRC Chemical Guidelines",
        )


    if is_rain_delay:
        window_h = candidate.rainfastness_window_hours or 24
        return TreatmentPermission(
            status="DEFERRED_WEATHER",
            candidate_treatment=candidate,
            is_permitted=False,
            weather_hold=True,
            rain_free_window_hours=window_h,
            action_instruction=(
                f"Foliar chemical spraying DEFERRED: Rainfall risk ({w_risk:.2f} · {w_level}) "
                f"threatens chemical wash-off and leaching. Minimum {window_h}-hour rain-free interval required for "
                f"{candidate.formulation} adhesion. Spraying immediately is prohibited."
            ),
            reassessment_trigger=(
                f"Re-evaluate spraying window after heavy precipitation clears and forecast shows at least "
                f"{window_h} hours of rain-free weather."
            ),
            cultural_measures=(
                f"IMMEDIATE ACTION (Non-Chemical): {candidate.cultural_measures} "
                f"Ensure drainage furrows are open to prevent root-zone waterlogging during rain."
            ),
            safety_disclaimer=(
                f"Applying fungicides prior to rainfall leads to wash-off, zero biological efficacy, "
                f"and toxic runoff into irrigation streams. Wait for soil trafficability and canopy drying."
            ),
            authority_reference=candidate.authoritative_source,
        )

    # Step 6: All Conditions Satisfied -> Spraying Permitted
    return TreatmentPermission(
        status="PERMITTED",
        candidate_treatment=candidate,
        is_permitted=True,
        weather_hold=False,
        rain_free_window_hours=candidate.rainfastness_window_hours,
        action_instruction=(
            f"Foliar spray of {candidate.formulation} @ {candidate.dosage} "
            f"({candidate.water_volume_per_acre} per acre). Apply with fine mist nozzle at first symptom appearance."
        ),
        reassessment_trigger="Inspect treated foliage in 5–7 days to verify containment and halt of secondary spread.",
        cultural_measures=candidate.cultural_measures,
        safety_disclaimer=(
            f"Statutory Notice: Pre-Harvest Interval (PHI) is {candidate.pre_harvest_interval_days} days. "
            f"Re-entry Interval (REI) is {candidate.re_entry_interval_hours} hours. Mandatory PPE: "
            f"{', '.join(candidate.ppe_requirements)}. Strictly adhere to CIBRC registered label instructions."
        ),
        authority_reference=candidate.authoritative_source,
    )
