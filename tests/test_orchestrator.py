"""
Tests the two-stage conflict resolver directly against the canonical
scenarios from doc Section 76, plus the priority-2 gate-vs-terminal-decision
fix. Uses the AgriMindState dataclass directly (not the full LangGraph
pipeline) so these stay fast and network-free.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision.rules import resolve_conflict
from orchestrator.state import AgriMindState, WeatherResult, SoilResult, DiseaseResult, MarketResult


def make_state(rainfall_risk=0.2, deficiency=0.2, disease_conf=0.9, severity="low",
                predicted_class="healthy", market_score=0.5):
    s = AgriMindState(run_id="test-run")
    s.weather = WeatherResult(rainfall_risk=rainfall_risk, confidence=0.85)
    s.soil = SoilResult(overall_deficiency=deficiency, confidence=0.9)
    s.disease = DiseaseResult(predicted_class=predicted_class, confidence=disease_conf, severity=severity)
    s.market = MarketResult(market_score=market_score)
    return s


def test_scenario_1_soil_deficiency_no_rain():
    """Soil deficiency + no rain -> fertilizer should be appropriate (Stage 2, no veto)."""
    state = make_state(rainfall_risk=0.1, deficiency=0.8)
    decision = resolve_conflict(state)
    assert decision.is_override is True
    assert decision.priority == 4
    assert decision.action == "apply_fertilizer", decision.action


def test_scenario_2_soil_deficiency_heavy_rain():
    """Soil deficiency + heavy rain -> Priority 1 veto forces DELAY."""
    state = make_state(rainfall_risk=0.85, deficiency=0.9)
    decision = resolve_conflict(state)
    assert decision.is_override is True
    assert decision.priority == 1
    assert decision.action == "DELAY"


def test_scenario_3_disease_low_confidence_is_a_gate_not_a_veto():
    """Low disease confidence must NOT short-circuit into a terminal decision —
    it's a gate (state.disease.actionable=False) that Stage 2 still runs after."""
    state = make_state(rainfall_risk=0.1, deficiency=0.3, disease_conf=0.42,
                        severity="high", predicted_class="Tomato_Early_blight")
    decision = resolve_conflict(state)
    assert state.disease.actionable is False
    # Priority 3 (disease urgency) must NOT fire because actionable is False,
    # even though severity is "high" — confidence gate blocks it.
    assert decision.priority != 3
    # Falls through to Stage 2 weighted scoring instead of a hard veto.
    assert decision.is_override is False
    assert decision.scores is not None


def test_scenario_4_market_high_volatility_cautious():
    """Market signal should never override agronomic safety — verified by
    confirming the rainfall veto still wins even with a strong market score."""
    state = make_state(rainfall_risk=0.9, deficiency=0.9, market_score=0.95)
    decision = resolve_conflict(state)
    assert decision.action == "DELAY"
    assert decision.priority == 1


def test_disease_urgency_overrides_fertilizer_timing():
    """High-confidence, high-severity disease should defer fertilizer timing
    (Priority 3) when no higher-priority veto has fired."""
    state = make_state(rainfall_risk=0.2, deficiency=0.7, disease_conf=0.91,
                        severity="high", predicted_class="Tomato_Early_blight")
    decision = resolve_conflict(state)
    assert decision.action == "DISEASE_MANAGEMENT_FIRST"
    assert decision.priority == 3
    assert decision.is_override is True


def test_conflict_row_shape_matches_schema():
    """Every override must serialize into the exact conflicts-table shape."""
    state = make_state(rainfall_risk=0.85, deficiency=0.9)
    decision = resolve_conflict(state)
    row = decision.to_conflict_row(run_id="r1", agent_a="soil", agent_b="weather", issue="rainfall_risk")
    for key in ("run_id", "agent_a", "agent_b", "issue", "resolution", "priority"):
        assert key in row


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


def test_market_tiebreaker_is_observable_and_non_override():
    """P5 may break a near-tie, but must remain Stage 2 and non-override."""
    state = make_state(rainfall_risk=0.2, deficiency=0.2, disease_conf=0.4,
                       severity="high", predicted_class="Tomato_Early_blight", market_score=0.9)
    decision = resolve_conflict(state)
    assert decision.action == "delay"
    assert decision.reason == "market_tiebreaker"
    assert decision.stage == "stage_2"
    assert decision.is_override is False
    assert decision.priority is None
    rows = decision.to_conflict_rows("p5")
    assert rows == [{
        "run_id": "p5", "agent_a": "market", "agent_b": "advisory",
        "issue": "market_tiebreaker", "resolution": "delay (market_tiebreaker)",
        "priority": None,
    }]
