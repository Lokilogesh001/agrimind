"""Real LangGraph integration test.

This test intentionally imports the real LangGraph package. It is skipped only
when the dependency is absent; no fake graph implementation is used.
"""
import os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("langgraph")

from orchestrator.graph import build_graph
from orchestrator.state import AgriMindState
from observability import database as obs


def test_real_langgraph_executes_all_nodes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # database.py binds its engine at import time, so this test focuses on the
    # actual graph execution and uses the existing observability engine.
    obs.init_db()
    inputs = {
        "weather_override": {"precip_prob": .9, "intensity": .8, "duration": .75},
        "n": 20, "p": 45, "k": 70,
        "disease_override": {"predicted_class": "Tomato_Early_blight", "confidence": .78},
        "current_price": 2200, "price_history": [1900, 1950, 2000, 2050],
    }
    state = AgriMindState(run_id="graph-test", raw_inputs=inputs)
    result = build_graph().invoke(state)
    assert result["final_recommendation"] == "DELAY"
    assert result["advisory"].preliminary_recommendation
    assert result["market"].market_score >= 0
    assert result["conflicts"]
    assert result["conflicts"][0]["agent_a"] == "weather"
