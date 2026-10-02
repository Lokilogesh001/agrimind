"""Tests for the three architectural fixes applied to the proven codebase."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import advisory_agent, weather_agent
from decision.rules import ConflictSpec, resolve_conflict
from orchestrator.state import AgriMindState, WeatherResult, SoilResult, DiseaseResult, MarketResult


def state(rain=0.1, deficiency=0.8, disease_conf=0.42, severity="high"):
    s = AgriMindState(run_id="r")
    s.weather = WeatherResult(rainfall_risk=rain, confidence=.9)
    s.soil = SoilResult(overall_deficiency=deficiency, confidence=.9)
    s.disease = DiseaseResult(predicted_class="Tomato_Early_blight", confidence=disease_conf, severity=severity)
    s.market = MarketResult(market_score=.5)
    return s


def test_advisory_agent_is_separate_and_only_scores():
    s = state(deficiency=.8, disease_conf=.95, severity="low")
    result = advisory_agent.run(s)
    assert set(result.scores) == {"apply_fertilizer", "delay", "monitor"}
    assert result.preliminary_recommendation == max(result.scores, key=result.scores.get)
    assert s.disease.actionable is False  # advisory does not apply the gate


def test_weather_agent_uses_data_source_adapter(monkeypatch):
    seen = {}
    def fake(lat, lon, timeout=5):
        seen.update(lat=lat, lon=lon, timeout=timeout)
        return {"hourly": {"precipitation_probability": [0], "precipitation": [0]}}
    monkeypatch.setattr("agents.weather_agent.fetch_forecast", fake)
    result = weather_agent.run(lat=13.08, lon=80.27)
    assert seen["lat"] == 13.08 and seen["lon"] == 80.27
    assert result.confidence > 0


def test_conflict_metadata_lives_on_decision():
    s = state(rain=.9)
    d = resolve_conflict(s)
    assert d.overrides
    assert all(isinstance(x, ConflictSpec) for x in d.overrides)
    rows = d.to_conflict_rows("r")
    assert {r["agent_a"] for r in rows} == {"weather"}
    assert {r["agent_b"] for r in rows} == {"soil", "advisory", "market"}


def test_priority_two_still_falls_through():
    s = state(rain=.1, deficiency=.2, disease_conf=.42, severity="high")
    d = resolve_conflict(s)
    assert s.disease.actionable is False
    assert d.priority != 3
    assert d.scores is not None


def test_priority_four_soil_threshold_is_terminal_after_higher_rules():
    s = state(rain=.10, deficiency=.75, disease_conf=.95, severity="low")
    d = resolve_conflict(s)
    assert d.action == "apply_fertilizer"
    assert d.priority == 4
    assert d.is_override is True
    assert d.overrides[0].agent_a == "soil"
    assert d.overrides[0].agent_b == "advisory"


def test_priority_one_beats_priority_four_and_three():
    s = state(rain=.71, deficiency=.99, disease_conf=.99, severity="high")
    d = resolve_conflict(s)
    assert d.action == "DELAY"
    assert d.priority == 1
    assert {c.agent_a for c in d.overrides} == {"weather"}


def test_boundary_values_are_not_strictly_over_threshold():
    s = state(rain=.70, deficiency=.60, disease_conf=.60, severity="low")
    d = resolve_conflict(s)
    assert d.priority is None
    assert s.disease.actionable is True
