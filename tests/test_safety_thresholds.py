"""Safety Thresholds & Boundary Condition Verification Suite.

Validates exact threshold boundary transitions:
1. Weather rainfall risk veto: 0.59 (permitted), 0.60 (veto enforced), 0.61 (veto enforced)
2. Disease confidence gate: 0.59 (blocked), 0.60 (actionable), 0.61 (actionable)
3. Decision Stability Score (DSS) tiers:
   - 0.39 (INSUFFICIENT) vs 0.40 (LOW)
   - 0.59 (LOW) vs 0.60 (MODERATE)
   - 0.79 (MODERATE) vs 0.80 (HIGH)
4. Evidence Quality Score (EQS) tiers:
   - 0.34 (INSUFFICIENT) vs 0.35 (LOW)
   - 0.54 (LOW) vs 0.55 (MODERATE)
   - 0.74 (MODERATE) vs 0.75 (GOOD)
5. Crop mismatch safety: cross-crop disease predictions blocked unconditionally
6. Missing soil NPK: unmeasured test never fabricates deficiency or allows chemical dosage
"""
from __future__ import annotations

import pytest
from agents import disease_agent, soil_agent, weather_agent
from decision.rules import resolve_conflict
from decision.evidence_engine import get_stability_level
from decision.evidence_quality import get_evidence_quality_level
from decision.safety_guard import apply_agronomic_safety_guard
from orchestrator.state import (
    AgriMindState,
    CropContext,
    WeatherResult,
    SoilResult,
    DiseaseResult,
    AdvisoryResult,
    MarketResult,
)


# ==============================================================================
# 1. Weather Rain Risk Veto Boundaries (0.59 vs 0.60 vs 0.61)
# ==============================================================================
@pytest.mark.parametrize(
    "rain_risk,expected_action,expected_reason",
    [
        (0.59, "apply_fertilizer", "soil_deficiency"),
        (0.60, "DELAY", "rule_d_weather_safety_veto"),
        (0.61, "DELAY", "rule_d_weather_safety_veto"),
    ],
)
def test_weather_rain_risk_threshold_boundaries(rain_risk: float, expected_action: str, expected_reason: str):
    """At 0.59 rainfall risk does not trigger veto; at >=0.60 Rule D enforces DELAY."""
    state = AgriMindState(
        run_id="thresh_weather_run",
        crop=CropContext(crop="Tomato", growth_stage="vegetative"),
    )
    state.weather = WeatherResult(
        rainfall_risk=rain_risk,
        status="AVAILABLE",
        is_available=True,
        confidence=0.9,
    )
    state.soil = SoilResult(
        npk_available=True,
        overall_deficiency=0.75,
        status="MEASURED",
        confidence=0.85,
    )
    state.disease = DiseaseResult(status="NOT_SUPPLIED", confidence=0.0)
    state.market = MarketResult(status="REAL_DATA", is_available=True, confidence=0.8)
    state.advisory = AdvisoryResult(
        preliminary_recommendation="apply_fertilizer",
        status="AVAILABLE",
        confidence=0.8,
    )

    decision = resolve_conflict(state)
    assert decision.action == expected_action
    if rain_risk >= 0.60:
        assert any("Rule D" in str(c) for c in state.safety_constraints)
        assert decision.reason in (expected_reason, "rainfall_risk")


# ==============================================================================
# 2. Disease Confidence Gate Boundaries (0.59 vs 0.60 vs 0.61)
# ==============================================================================
@pytest.mark.parametrize(
    "conf,expected_actionable",
    [
        (0.59, False),
        (0.60, True),
        (0.61, True),
    ],
)
def test_disease_confidence_gate_boundaries(conf: float, expected_actionable: bool):
    """Disease prediction <0.60 is gated as non-actionable; >=0.60 is actionable."""
    res = disease_agent.run(
        override={"predicted_class": "Tomato___Early_blight", "confidence": conf},
        selected_crop="Tomato",
    )
    assert res.actionable is expected_actionable
    assert res.confidence == conf


def test_disease_confidence_gate_prevents_treatment_below_threshold():
    """Confidence 0.59 must be blocked by Rule B from triggering disease treatment."""
    state = AgriMindState(
        run_id="thresh_disease_run",
        crop=CropContext(crop="Tomato", growth_stage="vegetative"),
    )
    state.weather = WeatherResult(rainfall_risk=0.1, status="AVAILABLE", confidence=0.9)
    state.soil = SoilResult(npk_available=True, overall_deficiency=0.2, status="MEASURED", confidence=0.8)
    state.disease = DiseaseResult(
        predicted_class="Tomato___Early_blight",
        confidence=0.59,
        crop_mismatch=False,
        status="AVAILABLE",
        actionable=False,
        severity="high",
    )
    state.advisory = AdvisoryResult(preliminary_recommendation="monitor", status="AVAILABLE")
    state.market = MarketResult(status="REAL_DATA", is_available=True)

    decision = resolve_conflict(state)
    # Low confidence (< 0.60) MUST NOT trigger DISEASE_MANAGEMENT_FIRST
    assert decision.action != "DISEASE_MANAGEMENT_FIRST"
    assert any("Rule B" in str(c) for c in state.safety_constraints)


# ==============================================================================
# 3. Decision Stability Score (DSS) Tier Boundaries
# ==============================================================================
@pytest.mark.parametrize(
    "score,expected_tier",
    [
        (0.39, "INSUFFICIENT"),
        (0.40, "LOW"),
        (0.59, "LOW"),
        (0.60, "MODERATE"),
        (0.79, "MODERATE"),
        (0.80, "HIGH"),
        (1.00, "HIGH"),
    ],
)
def test_dss_tier_boundaries(score: float, expected_tier: str):
    assert get_stability_level(score) == expected_tier


# ==============================================================================
# 4. Evidence Quality Score (EQS) Tier Boundaries
# ==============================================================================
@pytest.mark.parametrize(
    "score,expected_tier",
    [
        (0.34, "INSUFFICIENT"),
        (0.35, "LOW"),
        (0.54, "LOW"),
        (0.55, "MODERATE"),
        (0.74, "MODERATE"),
        (0.75, "GOOD"),
        (0.95, "GOOD"),
    ],
)
def test_eqs_tier_boundaries(score: float, expected_tier: str):
    assert get_evidence_quality_level(score) == expected_tier


# ==============================================================================
# 5. Crop Mismatch Safety Rules
# ==============================================================================
def test_crop_mismatch_blocks_action_unconditionally():
    """Predicting Tomato Early Blight when farmer selected Rice must be blocked."""
    res = disease_agent.run(
        override={"predicted_class": "Tomato___Early_blight", "confidence": 0.95},
        selected_crop="Rice",
    )
    assert res.crop_mismatch is True
    assert res.actionable is False

    # In full decision engine, crop mismatch must enforce Rule C
    state = AgriMindState(
        run_id="mismatch_run",
        crop=CropContext(crop="Rice", growth_stage="tillering"),
    )
    state.weather = WeatherResult(rainfall_risk=0.1, status="AVAILABLE", confidence=0.9)
    state.soil = SoilResult(npk_available=True, overall_deficiency=0.3, status="MEASURED", confidence=0.8)
    state.disease = res
    state.advisory = AdvisoryResult(preliminary_recommendation="monitor", status="AVAILABLE")
    state.market = MarketResult(status="REAL_DATA", is_available=True)

    decision = resolve_conflict(state)
    assert decision.action != "DISEASE_MANAGEMENT_FIRST"
    assert any("Rule C" in str(c) for c in state.safety_constraints)


# ==============================================================================
# 6. Missing Soil NPK Invariants
# ==============================================================================
def test_missing_soil_npk_blocks_fertilizer():
    """Unmeasured soil MUST NOT fabricate deficiency or allow apply_fertilizer."""
    res = soil_agent.run(n=None, p=None, k=None, crop="Tomato", soil_type="red_soil")
    assert res.npk_available is False
    assert res.overall_deficiency is None
    assert res.nitrogen_deficiency is None
    assert res.phosphorus_deficiency is None
    assert res.potassium_deficiency is None

    # Even if advisory preliminarily proposes apply_fertilizer, Rule A MUST veto it
    state = AgriMindState(
        run_id="missing_npk_run",
        crop=CropContext(crop="Tomato", growth_stage="vegetative"),
    )
    state.weather = WeatherResult(rainfall_risk=0.1, status="AVAILABLE", confidence=0.9)
    state.soil = res
    state.disease = DiseaseResult(status="NOT_SUPPLIED")
    state.advisory = AdvisoryResult(preliminary_recommendation="apply_fertilizer", status="AVAILABLE")
    state.market = MarketResult(status="REAL_DATA", is_available=True)

    action, reason, constraints, penalty = apply_agronomic_safety_guard(
        state, candidate_action="apply_fertilizer", candidate_reason="advisory"
    )
    assert action == "monitor"
    assert reason == "rule_a_soil_safety_veto"
    assert any("Rule A" in c for c in constraints)


# ==============================================================================
# 7. Negative-Control & Mutation Tests (Proving Guard Efficacy)
# ==============================================================================
def test_negative_control_weather_rain_veto_mutates_action():
    """Negative control: If Rule D was absent, candidate action would be apply_fertilizer.
    Production Guard D MUST mutate apply_fertilizer into DELAY when rain_risk >= 0.60.
    """
    state = AgriMindState(
        run_id="mut_weather_run",
        crop=CropContext(crop="Tomato", growth_stage="vegetative"),
    )
    state.weather = WeatherResult(rainfall_risk=0.85, status="AVAILABLE", confidence=0.9)
    state.soil = SoilResult(npk_available=True, overall_deficiency=0.80, status="MEASURED", confidence=0.9)
    state.disease = DiseaseResult(status="NOT_SUPPLIED")
    state.advisory = AdvisoryResult(preliminary_recommendation="apply_fertilizer", status="AVAILABLE")
    state.market = MarketResult(status="REAL_DATA", is_available=True)

    # 1. Unchecked candidate action:
    candidate_action = "apply_fertilizer"
    assert candidate_action == "apply_fertilizer"

    # 2. Production Stage-1 Guard applied:
    guarded_action, reason, constraints, penalty = apply_agronomic_safety_guard(
        state, candidate_action=candidate_action, candidate_reason="soil_deficiency"
    )
    # The guard MUST actively mutate the action away from apply_fertilizer to DELAY
    assert guarded_action == "DELAY"
    assert guarded_action != candidate_action
    assert any("Rule D" in c for c in constraints)


def test_negative_control_soil_guard_mutates_unmeasured_fertilizer():
    """Negative control: If Rule A was absent, candidate action would be apply_fertilizer.
    Production Guard A MUST mutate apply_fertilizer into monitor when NPK is unmeasured.
    """
    state = AgriMindState(
        run_id="mut_soil_run",
        crop=CropContext(crop="Tomato", growth_stage="vegetative"),
    )
    state.weather = WeatherResult(rainfall_risk=0.10, status="AVAILABLE", confidence=0.9)
    state.soil = SoilResult(npk_available=False, overall_deficiency=None, status="UNAVAILABLE", confidence=0.0)
    state.disease = DiseaseResult(status="NOT_SUPPLIED")
    state.advisory = AdvisoryResult(preliminary_recommendation="apply_fertilizer", status="AVAILABLE")
    state.market = MarketResult(status="REAL_DATA", is_available=True)

    candidate_action = "apply_fertilizer"
    guarded_action, reason, constraints, penalty = apply_agronomic_safety_guard(
        state, candidate_action=candidate_action, candidate_reason="advisory"
    )
    assert guarded_action == "monitor"
    assert guarded_action != candidate_action
    assert any("Rule A" in c for c in constraints)


def test_negative_control_disease_gate_blocks_low_confidence():
    """Negative control: If Rule B was absent, Late Blight diagnosis would trigger immediate chemical spray.
    Production Guard B MUST block actionable treatment when confidence is below 0.60.
    """
    res = disease_agent.run(
        override={"predicted_class": "Tomato___Late_blight", "confidence": 0.58},
        selected_crop="Tomato",
    )
    assert res.actionable is False
    assert res.action_status == "BLOCKED"
    assert "confidence gate" in res.block_reason


def test_negative_control_crop_mismatch_blocks_treatment():
    """Negative control: If Rule C was absent, high confidence Early Blight would trigger treatment on Rice.
    Production Guard C MUST block actionable treatment when predicted crop differs from selected crop.
    """
    res = disease_agent.run(
        override={"predicted_class": "Tomato___Early_blight", "confidence": 0.98},
        selected_crop="Rice",
    )
    assert res.actionable is False
    assert res.action_status == "BLOCKED"
    assert res.crop_mismatch is True


# ==============================================================================
# 7. Weather Fallback Safety & Caching Provenance Regression Tests
# ==============================================================================
def test_weather_timeout_agent_output_and_advisory_safety():
    """Verify that a timeout cannot become a false zero-rain-risk observation.
    Agent must mark output as unavailable/estimated with conservative delay,
    and final advisory must defer chemical treatments.
    """
    from unittest.mock import patch
    import requests
    from data_sources import weather
    from data_sources.treatments import evaluate_treatment_permission_state

    weather.clear_weather_cache_for_tests()
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
        w_res = weather_agent.run(lat=28.6139, lon=77.2090)

    # 1. Verify agent contract
    assert w_res.status == "TIMEOUT"
    assert w_res.is_available is False
    assert w_res.is_estimated is True
    assert w_res.freshness_status in ("TIMEOUT", "UNAVAILABLE")
    assert w_res.fertilizer_condition == "delay"
    assert w_res.risk_level == "UNKNOWN"

    # 2. Verify final advisory and safety guard
    state = AgriMindState(
        run_id="weather_timeout_test_run",
        crop=CropContext(crop="Tomato", growth_stage="vegetative"),
    )
    state.weather = w_res
    state.soil = SoilResult(npk_available=True, overall_deficiency=0.75, status="MEASURED")
    state.disease = DiseaseResult(status="NOT_SUPPLIED")
    state.advisory = AdvisoryResult(preliminary_recommendation="apply_fertilizer", status="AVAILABLE")
    state.market = MarketResult(status="REAL_DATA", is_available=True)

    decision = resolve_conflict(state)
    # Fertilizer must NOT be blindly applied when weather is unknown
    assert decision.action == "DELAY"
    assert any("Rule D" in c for c in state.safety_constraints)

    # 3. Verify spray treatment permission is held
    d_res = DiseaseResult(
        predicted_class="Tomato___Early_blight",
        confidence=0.90,
        status="AVAILABLE",
        actionable=True,
    )
    perm = evaluate_treatment_permission_state(
        crop="Tomato",
        disease_result=d_res,
        weather_result=w_res,
        final_action="DISEASE_MANAGEMENT_FIRST",
    )
    assert perm.is_permitted is False
    assert perm.weather_hold is True
    assert perm.status == "DEFERRED_WEATHER"


def test_weather_cache_timestamp_and_provenance_preservation():
    """Verify that cached meteorological data carries original observation/retrieval timestamp and freshness status."""
    from unittest.mock import MagicMock, patch
    from data_sources import weather

    weather.clear_weather_cache_for_tests()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "hourly": {
            "time": ["2026-10-26T00:00:00Z", "2026-10-26T01:00:00Z"],
            "precipitation_probability": [10, 15],
            "precipitation": [0.0, 0.0],
            "temperature_2m": [26.0, 25.5],
        }
    }
    mock_resp.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_resp):
        res1 = weather.fetch_forecast(lat=28.6139, lon=77.2090, force_refresh=True)
        assert res1["status"] == "AVAILABLE"
        assert res1["freshness_status"] == "REAL_DATA"
        assert res1["is_cached"] is False
        orig_retrieval = res1["retrieval_time"]
        orig_obs = res1["observation_time"]
        assert orig_retrieval is not None
        assert orig_obs == "2026-10-26T00:00:00Z"

    # Second call without network should serve from cache with preserved timestamps
    res2 = weather.fetch_forecast(lat=28.6139, lon=77.2090, force_refresh=False)
    assert res2["status"] == "CACHED"
    assert res2["freshness_status"] == "CACHED"
    assert res2["is_cached"] is True
    assert res2["retrieval_time"] == orig_retrieval
    assert res2["observation_time"] == orig_obs


def test_all_six_weather_states_end_to_end_safety():
    """Trace all 6 weather states: REAL_DATA, CACHED, STALE_CACHE, TIMEOUT, UNAVAILABLE, and INVALID.
    Verify that unknown or stale weather NEVER silently becomes a verified low-risk observation.
    """
    from decision.rules import resolve_conflict
    from data_sources.treatments import evaluate_treatment_permission_state
    from agents.weather_agent import run as run_weather_agent

    disease_res = DiseaseResult(
        predicted_class="Tomato___Early_blight",
        confidence=0.90,
        status="AVAILABLE",
        actionable=True,
    )
    soil_res = SoilResult(npk_available=True, overall_deficiency=0.75, status="MEASURED")

    def build_state(w_res):
        st = AgriMindState(
            run_id=f"test_{w_res.status}",
            crop=CropContext(crop="Tomato", growth_stage="vegetative"),
        )
        st.weather = w_res
        st.soil = soil_res
        st.disease = disease_res
        st.advisory = AdvisoryResult(preliminary_recommendation="apply_fertilizer", status="AVAILABLE")
        st.market = MarketResult(status="REAL_DATA", is_available=True)
        return st

    # 1. REAL_DATA with Low Rain: Fertilizer & Spray Permitted
    w_real = run_weather_agent(override={
        "rainfall_risk": 0.15,
        "status": "AVAILABLE",
        "freshness_status": "REAL_DATA",
        "is_cached": False,
        "is_estimated": False,
    })
    assert w_real.fertilizer_condition == "normal"
    assert w_real.irrigation_condition == "normal"
    st_real = build_state(w_real)
    dec_real = resolve_conflict(st_real)
    assert dec_real.action == "apply_fertilizer"
    perm_real = evaluate_treatment_permission_state(
        crop="Tomato", disease_result=disease_res, weather_result=w_real, final_action="DISEASE_MANAGEMENT_FIRST"
    )
    assert perm_real.is_permitted is True
    assert perm_real.weather_hold is False

    # 2. CACHED (<15 min TTL) with Low Rain: Fertilizer & Spray Permitted
    w_cached = run_weather_agent(override={
        "rainfall_risk": 0.15,
        "status": "CACHED",
        "freshness_status": "CACHED",
        "is_cached": True,
        "is_estimated": False,
    })
    assert w_cached.fertilizer_condition == "normal"
    assert w_cached.irrigation_condition == "normal"
    st_cached = build_state(w_cached)
    dec_cached = resolve_conflict(st_cached)
    assert dec_cached.action == "apply_fertilizer"
    perm_cached = evaluate_treatment_permission_state(
        crop="Tomato", disease_result=disease_res, weather_result=w_cached, final_action="DISEASE_MANAGEMENT_FIRST"
    )
    assert perm_cached.is_permitted is True
    assert perm_cached.weather_hold is False

    # 3. STALE_CACHE (>15 min TTL) Even With Low Rain (0.15):
    # Stale weather MUST NOT silently permit chemical operations!
    w_stale = run_weather_agent(override={
        "rainfall_risk": 0.15,
        "status": "STALE_CACHE",
        "freshness_status": "STALE_CACHE",
        "is_cached": True,
        "is_estimated": True,
    })
    assert w_stale.fertilizer_condition == "delay"
    assert w_stale.irrigation_condition == "delay"
    assert "STALE" in w_stale.risk_explanation
    st_stale = build_state(w_stale)
    dec_stale = resolve_conflict(st_stale)
    assert dec_stale.action == "DELAY"
    assert any("Rule D" in c for c in st_stale.safety_constraints)
    perm_stale = evaluate_treatment_permission_state(
        crop="Tomato", disease_result=disease_res, weather_result=w_stale, final_action="DISEASE_MANAGEMENT_FIRST"
    )
    assert perm_stale.is_permitted is False
    assert perm_stale.weather_hold is True
    assert perm_stale.status == "DEFERRED_WEATHER"

    # 4. TIMEOUT: Conservative Delay on Fertilizer & Spray Held
    w_timeout = WeatherResult(
        rainfall_risk=0.0,
        status="TIMEOUT",
        freshness_status="TIMEOUT",
        is_available=False,
        risk_level="UNKNOWN",
        is_estimated=True,
    )
    st_timeout = build_state(w_timeout)
    dec_timeout = resolve_conflict(st_timeout)
    assert dec_timeout.action == "DELAY"
    perm_timeout = evaluate_treatment_permission_state(
        crop="Tomato", disease_result=disease_res, weather_result=w_timeout, final_action="DISEASE_MANAGEMENT_FIRST"
    )
    assert perm_timeout.is_permitted is False
    assert perm_timeout.weather_hold is True
    assert perm_timeout.status == "DEFERRED_WEATHER"

    # 5. UNAVAILABLE: Conservative Delay on Fertilizer & Spray Held
    w_unavail = WeatherResult(
        rainfall_risk=0.0,
        status="UNAVAILABLE",
        freshness_status="UNAVAILABLE",
        is_available=False,
        risk_level="UNKNOWN",
        is_estimated=True,
    )
    st_unavail = build_state(w_unavail)
    dec_unavail = resolve_conflict(st_unavail)
    assert dec_unavail.action == "DELAY"
    perm_unavail = evaluate_treatment_permission_state(
        crop="Tomato", disease_result=disease_res, weather_result=w_unavail, final_action="DISEASE_MANAGEMENT_FIRST"
    )
    assert perm_unavail.is_permitted is False
    assert perm_unavail.weather_hold is True
    assert perm_unavail.status == "DEFERRED_WEATHER"

    # 6. INVALID: Conservative Delay on Fertilizer & Spray Held
    w_invalid = WeatherResult(
        rainfall_risk=0.0,
        status="INVALID",
        freshness_status="INVALID",
        is_available=False,
        risk_level="UNKNOWN",
        is_estimated=True,
    )
    st_invalid = build_state(w_invalid)
    dec_invalid = resolve_conflict(st_invalid)
    assert dec_invalid.action == "DELAY"
    perm_invalid = evaluate_treatment_permission_state(
        crop="Tomato", disease_result=disease_res, weather_result=w_invalid, final_action="DISEASE_MANAGEMENT_FIRST"
    )
    assert perm_invalid.is_permitted is False
    assert perm_invalid.weather_hold is True
    assert perm_invalid.status == "DEFERRED_WEATHER"


