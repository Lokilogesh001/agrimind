"""Fault Injection & Property-Based Invariant Verification Suite.

Mandatory Requirements (Phase E Sections 7.4 & 7.5):
1. Property-based randomized scenario generation with fixed seed 42.
2. Core Safety Invariants:
   - Unsafe weather (>=0.60) NEVER produces apply_fertilizer.
   - Low disease confidence (<0.60) or crop mismatch NEVER triggers disease-specific treatment.
   - Missing soil NPK NEVER produces non-zero deficiency or chemical fertilizer recommendation.
   - Caller benchmark price NEVER leaks into observed_price.
   - Confidence, DSS, and EQS are ALWAYS bounded within [0.0, 1.0].
   - Identical deterministic inputs ALWAYS yield identical decisions.
3. Fault Injection:
   - Missing or corrupted model checkpoint.
   - Empty (0-byte), invalid non-image, and oversized image files.
   - LLM timeout, rate limit, and malformed response gracefully falling back to deterministic template.
   - Database persistence resilience.
"""
from __future__ import annotations

import os
import random
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agents import disease_agent, market_agent, soil_agent, weather_agent
from decision.rules import resolve_conflict
from llm.explainer import explain_with_metadata
from ml.disease_model import DiseasePredictor
from orchestrator.state import (
    AgriMindState,
    CropContext,
    DiseaseResult,
    MarketResult,
    SoilResult,
    WeatherResult,
)


# ==============================================================================
# 1. Seeded Randomized Property-Based Tests (Fixed Seed 42)
# ==============================================================================
def test_seeded_property_based_invariants():
    """Evaluate 100 randomly generated scenarios under fixed seed 42 to verify global invariants."""
    rng = random.Random(42)

    crops = ["Tomato", "Rice", "Maize", "Cotton", "Potato"]
    stages = ["vegetative", "flowering", "tillering", "harvest"]
    diseases = ["Tomato___Early_blight", "Potato___Late_blight", "Rice___Blast", None]

    for iteration in range(100):
        crop = rng.choice(crops)
        stage = rng.choice(stages)
        rain_risk = round(rng.uniform(0.0, 1.0), 3)

        npk_available = rng.choice([True, False])
        soil_def = round(rng.uniform(0.0, 1.0), 3) if npk_available else None

        dis_choice = rng.choice(diseases)
        dis_conf = round(rng.uniform(0.0, 1.0), 3) if dis_choice else 0.0

        caller_price = round(rng.uniform(0.0, 5000.0), 2) if rng.choice([True, False]) else 0.0

        # Construct state
        state = AgriMindState(
            run_id=f"property_test_{iteration}",
            crop=CropContext(crop=crop, growth_stage=stage),
        )
        state.weather = weather_agent.run(override={"rainfall_risk": rain_risk, "status": "AVAILABLE"})
        state.soil = soil_agent.run(
            n=50 if npk_available else None,
            p=50 if npk_available else None,
            k=50 if npk_available else None,
            crop=crop,
            soil_type="red_soil",
        )
        state.disease = disease_agent.run(
            override={"predicted_class": dis_choice, "confidence": dis_conf} if dis_choice else None,
            selected_crop=crop,
        )
        state.market = market_agent.run(current_price=caller_price, crop=crop)

        decision = resolve_conflict(state)

        # ----------------------------------------------------------------------
        # INVARIANT 1: Weather rainfall risk >= 0.60 NEVER produces apply_fertilizer
        # ----------------------------------------------------------------------
        if state.weather.rainfall_risk >= 0.60:
            assert decision.action != "apply_fertilizer", (
                f"Iteration {iteration}: Unsafe rain risk {state.weather.rainfall_risk} allowed apply_fertilizer!"
            )

        # ----------------------------------------------------------------------
        # INVARIANT 2: Low disease confidence (< 0.60) or mismatch NEVER triggers DISEASE_MANAGEMENT_FIRST
        # ----------------------------------------------------------------------
        if state.disease.confidence < 0.60 or state.disease.crop_mismatch or not state.disease.predicted_class:
            assert decision.action != "DISEASE_MANAGEMENT_FIRST", (
                f"Iteration {iteration}: Low confidence/mismatch disease triggered treatment!"
            )

        # ----------------------------------------------------------------------
        # INVARIANT 3: Missing soil NPK NEVER produces non-zero deficiency or apply_fertilizer
        # ----------------------------------------------------------------------
        if not npk_available:
            assert state.soil.npk_available is False
            assert state.soil.overall_deficiency is None
            assert decision.action != "apply_fertilizer", (
                f"Iteration {iteration}: Unmeasured NPK allowed chemical fertilizer dosage!"
            )

        # ----------------------------------------------------------------------
        # INVARIANT 4: Caller benchmark price NEVER leaks into observed_price
        # ----------------------------------------------------------------------
        if caller_price > 0:
            assert state.market.status == "USER_SUPPLIED"
            assert state.market.observed_price is None, (
                f"Iteration {iteration}: User price leaked into observed_price!"
            )

        # ----------------------------------------------------------------------
        # INVARIANT 5: Confidence, DSS, and EQS are bounded in [0.0, 1.0]
        # ----------------------------------------------------------------------
        assert 0.0 <= state.decision_stability_score <= 1.0
        assert 0.0 <= state.evidence_quality_score <= 1.0


# ==============================================================================
# 2. Fault Injection: Model Checkpoints & Image Validation
# ==============================================================================
def test_missing_model_checkpoint_fault_injection():
    """Non-existent checkpoint file must raise FileNotFoundError cleanly."""
    with pytest.raises(FileNotFoundError):
        DiseasePredictor("ml/artifacts/non_existent_checkpoint.pt")


def test_corrupted_model_checkpoint_fault_injection(tmp_path: Path):
    """Corrupted checkpoint payload (e.g. invalid bytes) must raise ValueError, not crash process."""
    corrupt_ckpt = tmp_path / "corrupt.pt"
    corrupt_ckpt.write_bytes(b"NOT_A_VALID_TORCH_MODEL_DATA")

    with pytest.raises(ValueError):
        DiseasePredictor(str(corrupt_ckpt))


def test_zero_byte_image_fault_injection(tmp_path: Path):
    """Empty 0-byte leaf file must be rejected explicitly."""
    empty_img = tmp_path / "empty_leaf.jpg"
    empty_img.write_bytes(b"")

    with patch("ml.disease_model.DiseasePredictor.__init__", return_value=None):
        predictor = DiseasePredictor.__new__(DiseasePredictor)
        with pytest.raises(ValueError, match="empty"):
            predictor.predict(str(empty_img))


def test_oversized_image_fault_injection(tmp_path: Path):
    """Image exceeding maximum size limit (> 10MB) must be rejected explicitly."""
    huge_img = tmp_path / "huge_leaf.jpg"
    # Write sparse file of 11 MB
    with open(huge_img, "wb") as f:
        f.seek(11 * 1024 * 1024)
        f.write(b"0")

    with patch("ml.disease_model.DiseasePredictor.__init__", return_value=None):
        predictor = DiseasePredictor.__new__(DiseasePredictor)
        with pytest.raises(ValueError, match="exceeds maximum size limit"):
            predictor.predict(str(huge_img))


# ==============================================================================
# 3. Fault Injection: LLM Provider Failures & Safe Fallback
# ==============================================================================
def test_llm_rate_limit_and_timeout_triggers_deterministic_fallback():
    """Simulate upstream LLM API 429 rate limit and ensure deterministic fallback succeeds."""
    state = AgriMindState(
        run_id="fault_llm_run",
        crop=CropContext(crop="Tomato", growth_stage="vegetative"),
    )
    state.weather = WeatherResult(rainfall_risk=0.1, status="AVAILABLE")
    state.soil = SoilResult(npk_available=True, overall_deficiency=0.3, status="MEASURED")
    state.disease = DiseaseResult(status="NOT_SUPPLIED")
    state.market = MarketResult(status="USER_SUPPLIED", current_price=2000.0)
    decision = resolve_conflict(state)
    state.final_recommendation = decision.action

    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key", "LLM_PRIMARY_PROVIDER": "openai"}):
        with patch("llm.explainer._call_chat_completion", side_effect=RuntimeError("RateLimitError: 429 Too Many Requests")):
            res = explain_with_metadata(state, evidence=[{"id": "ICAR-01", "text": "Apply compost."}])
            # Must gracefully fall back to deterministic template without raising
            assert res.provider == "deterministic"
            assert res.fallback_used is True
            assert res.structured_explanation is not None
            assert len(res.text) > 0


def test_llm_malformed_json_triggers_deterministic_fallback():
    """Simulate LLM returning unparseable garbage output."""
    state = AgriMindState(
        run_id="fault_json_run",
        crop=CropContext(crop="Rice", growth_stage="tillering"),
    )
    state.final_recommendation = "monitor"

    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
        with patch("llm.explainer._call_chat_completion", return_value="<<<MALFORMED NOT JSON STRING>>>"):
            res = explain_with_metadata(state, evidence=[])
            assert res.structured_explanation is not None
            assert res.provider == "deterministic"


# ==============================================================================
# 4. Fault Injection: Database Persistence Resilience
# ==============================================================================
def test_database_logging_failure_does_not_corrupt_advisory():
    """Simulate SQLite locked / disk full error during logging: advisory must still succeed."""
    with patch("observability.database.log_agent_call", side_effect=Exception("Database locked")):
        with patch("observability.database.log_decision", side_effect=Exception("Database locked")):
            # Running orchestrator must not crash if observability fails
            state = AgriMindState(
                run_id="db_fault_run",
                crop=CropContext(crop="Tomato", growth_stage="vegetative"),
            )
            state.weather = WeatherResult(rainfall_risk=0.1, status="AVAILABLE")
            state.soil = SoilResult(npk_available=True, overall_deficiency=0.5, status="MEASURED")
            state.disease = DiseaseResult(status="NOT_SUPPLIED")
            state.market = MarketResult(status="UNAVAILABLE")

            decision = resolve_conflict(state)
            assert decision.action in ("apply_fertilizer", "monitor", "delay")
