"""Agent Contracts & Specialist Agent Invariants Suite."""
from __future__ import annotations

import pytest
from agents import weather_agent, soil_agent, disease_agent, advisory_agent, market_agent
from orchestrator.state import (
    AgentResult,
    WeatherResult,
    SoilResult,
    DiseaseResult,
    AdvisoryResult,
    MarketResult,
    CropContext,
    AgriMindState,
)


def test_weather_agent_contract_success():
    res = weather_agent.run(lat=9.9252, lon=78.1198)
    assert isinstance(res, WeatherResult)
    assert isinstance(res, AgentResult)
    assert len(res.validate_contract()) == 0
    assert 0.0 <= res.confidence <= 1.0
    assert res.execution_time_ms >= 0.0
    assert res.status in ("AVAILABLE", "SUCCESS", "FALLBACK", "UNAVAILABLE")
    assert 0.0 <= res.rainfall_risk <= 1.0


def test_weather_agent_contract_fallback():
    # Invalid coordinates trigger safe fallback or explicit status without crashing
    res = weather_agent.run(lat=999.0, lon=999.0)
    assert isinstance(res, WeatherResult)
    assert len(res.validate_contract()) == 0
    assert res.status in ("UNAVAILABLE", "FALLBACK", "INVALID")
    assert 0.0 <= res.rainfall_risk <= 1.0


def test_soil_agent_contract_measured():
    res = soil_agent.run(n=25, p=45, k=70, soil_type="red_soil", crop="Tomato")
    assert isinstance(res, SoilResult)
    assert len(res.validate_contract()) == 0
    assert res.status in ("MEASURED", "AVAILABLE", "SUCCESS")
    assert res.npk_available is True
    assert res.overall_deficiency is not None
    assert 0.0 <= res.overall_deficiency <= 1.0
    assert 0.0 <= res.confidence <= 1.0


def test_soil_agent_contract_unmeasured():
    res = soil_agent.run(n=None, p=None, k=None, soil_type="red_soil", crop="Tomato")
    assert isinstance(res, SoilResult)
    assert len(res.validate_contract()) == 0
    assert res.npk_available is False
    assert res.overall_deficiency is None
    assert res.status in ("UNAVAILABLE", "LOCATION_ESTIMATED", "USER_SELECTED")


def test_disease_agent_contract_not_supplied():
    res = disease_agent.run(image_path=None)
    assert isinstance(res, DiseaseResult)
    assert len(res.validate_contract()) == 0
    assert res.status in ("NOT_SUPPLIED", "UNAVAILABLE")
    assert res.actionable is False
    assert res.predicted_class is None


def test_disease_agent_contract_override():
    res = disease_agent.run(
        override={"predicted_class": "Tomato___Early_blight", "confidence": 0.88},
        selected_crop="Tomato",
    )
    assert isinstance(res, DiseaseResult)
    assert len(res.validate_contract()) == 0
    assert res.status in ("OVERRIDE", "AVAILABLE")
    assert res.confidence == 0.88
    assert res.predicted_class == "Tomato___Early_blight"
    assert res.crop_mismatch is False


def test_disease_agent_contract_crop_mismatch():
    res = disease_agent.run(
        override={"predicted_class": "Tomato___Early_blight", "confidence": 0.88},
        selected_crop="Rice",
    )
    assert isinstance(res, DiseaseResult)
    assert len(res.validate_contract()) == 0
    assert res.crop_mismatch is True


def test_advisory_agent_contract():
    crop = CropContext(crop="Tomato", growth_stage="vegetative")
    weather = WeatherResult(rainfall_risk=0.1, status="AVAILABLE")
    soil = SoilResult(overall_deficiency=0.5, npk_available=True, status="MEASURED")
    disease = DiseaseResult(status="NOT_SUPPLIED")
    market = MarketResult(signal="hold", status="UNAVAILABLE")
    state = AgriMindState(
        run_id="test_contract_run",
        crop=crop,
        weather=weather,
        soil=soil,
        disease=disease,
        market=market,
    )

    res = advisory_agent.run(state)
    assert isinstance(res, AdvisoryResult)
    assert len(res.validate_contract()) == 0
    assert res.status in ("AVAILABLE", "SUCCESS")
    assert res.preliminary_recommendation in ("apply_fertilizer", "monitor", "delay")
    assert 0.0 <= res.confidence <= 1.0


def test_market_agent_contract_user_supplied():
    res = market_agent.run(current_price=2400.0, price_history=[2300.0, 2350.0, 2400.0], crop="Tomato")
    assert isinstance(res, MarketResult)
    assert len(res.validate_contract()) == 0
    assert res.status == "USER_SUPPLIED"
    assert res.source == "caller_provided"
    assert res.benchmark_price == 2400.0
    assert res.observed_price is None  # Strict provenance: caller input is NEVER observed APMC rate
    assert res.authoritative is False
    assert 0.0 <= res.confidence <= 1.0


def test_market_agent_contract_unavailable():
    res = market_agent.run(current_price=0.0, price_history=[], crop="")
    assert isinstance(res, MarketResult)
    assert len(res.validate_contract()) == 0
    assert res.status == "UNAVAILABLE"
    assert res.source == "none"
    assert res.is_available is False
    assert res.observed_price is None
    assert res.benchmark_price is None
