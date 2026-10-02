"""LangGraph orchestration for AgriMind.

The graph deliberately separates the Advisory Agent from conflict resolution:

START -> weather -> soil -> disease -> advisory -> market -> decision -> END

Advisory computes preliminary S(a). Market contributes economic context. The
final decision node then applies the canonical two-stage conflict policy and
persists the resulting audit trail.
"""
from __future__ import annotations

import time
import uuid

try:
    from langgraph.graph import END, StateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False

from agents import advisory_agent, disease_agent, market_agent, soil_agent, weather_agent
from decision.rules import resolve_conflict
from observability import database as obs
from orchestrator.state import AgriMindState, CropContext


def _timed(fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, round((time.perf_counter() - start) * 1000, 2)


def node_weather(state: AgriMindState) -> AgriMindState:
    inputs = state.raw_inputs
    result, latency = _timed(
        weather_agent.run,
        lat=inputs.get("lat"), lon=inputs.get("lon"),
        override=inputs.get("weather_override"),
    )
    state.weather = result
    state.log(f"weather_agent -> rainfall_risk={result.rainfall_risk}")
    obs.log_agent_call(
        state.run_id, "weather", inputs.get("weather_override") or {}, result.__dict__,
        "ok" if result.confidence > 0 else "degraded", result.confidence, latency,
    )
    return state


def node_soil(state: AgriMindState) -> AgriMindState:
    inputs = state.raw_inputs
    result, latency = _timed(soil_agent.run, n=inputs["n"], p=inputs["p"], k=inputs["k"], crop=state.crop.crop, soil_type=inputs.get("soil_type", ""))
    state.soil = result
    state.log(f"soil_agent -> overall_deficiency={result.overall_deficiency}")
    obs.log_agent_call(
        state.run_id, "soil", {"n": inputs["n"], "p": inputs["p"], "k": inputs["k"]},
        result.__dict__, "ok", result.confidence, latency,
    )
    return state


def node_disease(state: AgriMindState) -> AgriMindState:
    inputs = state.raw_inputs
    result, latency = _timed(
        disease_agent.run,
        image_path=inputs.get("image_path"), override=inputs.get("disease_override"),
    )
    state.disease = result
    if result.predicted_class:
        state.log(f"disease_agent -> {result.predicted_class} ({result.confidence})")
    else:
        state.log("disease_agent -> no disease image/signal provided")
    obs.log_agent_call(
        state.run_id, "disease",
        inputs.get("disease_override") or {"image_path": inputs.get("image_path")},
        result.__dict__, "ok" if result.predicted_class else "no_input", result.confidence, latency,
    )
    return state


def node_advisory(state: AgriMindState) -> AgriMindState:
    """Standalone Advisory Agent: compute preliminary S(a), no veto logic."""
    result, latency = _timed(advisory_agent.run, state)
    state.advisory = result
    state.log(f"advisory_agent -> preliminary={result.preliminary_recommendation}")
    obs.log_agent_call(
        state.run_id, "advisory", {"crop": state.crop.__dict__}, result.__dict__,
        "ok", result.confidence, latency,
    )
    return state


def node_market(state: AgriMindState) -> AgriMindState:
    inputs = state.raw_inputs
    result, latency = _timed(
        market_agent.run,
        current_price=inputs.get("current_price", 0),
        price_history=inputs.get("price_history", []),
        crop=state.crop.crop,
        market=inputs.get("market"),
    )
    state.market = result
    state.log(f"market_agent -> score={result.market_score} signal={result.signal}")
    obs.log_agent_call(
        state.run_id, "market",
        {"current_price": inputs.get("current_price"), "price_history": inputs.get("price_history"), "crop": state.crop.crop},
        result.__dict__, "ok" if result.is_available else "unavailable", result.confidence, latency,
    )
    return state


def node_decision(state: AgriMindState) -> AgriMindState:
    """Orchestrator decision layer: Stage 1 vetoes + Stage 2 scores."""
    decision, _latency = _timed(resolve_conflict, state)
    state.final_recommendation = decision.action
    state.conflicts.extend(decision.to_conflict_rows(state.run_id))

    for row in decision.to_conflict_rows(state.run_id):
        obs.log_conflict(**row)

    confidence = (decision.scores.get(decision.action, max(decision.scores.values())) if decision.scores else 0.85)
    state.confidence = confidence
    state.log(f"orchestrator -> {decision.action} ({decision.reason})")
    obs.log_decision(state.run_id, decision.action, decision.reason, confidence)
    return state


_COMPILED_GRAPH = None


def build_graph():
    if not LANGGRAPH_AVAILABLE:
        return None
    graph = StateGraph(AgriMindState)
    graph.add_node("weather", node_weather)
    graph.add_node("soil", node_soil)
    graph.add_node("disease", node_disease)
    graph.add_node("advisory", node_advisory)
    graph.add_node("market", node_market)
    graph.add_node("decision", node_decision)

    graph.set_entry_point("weather")
    graph.add_edge("weather", "soil")
    graph.add_edge("soil", "disease")
    graph.add_edge("disease", "advisory")
    graph.add_edge("advisory", "market")
    graph.add_edge("market", "decision")
    graph.add_edge("decision", END)
    return graph.compile()


def get_graph():
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_graph()
    return _COMPILED_GRAPH


def run_advisory(inputs: dict) -> AgriMindState:
    run_id = str(uuid.uuid4())
    initial_state = AgriMindState(
        run_id=run_id,
        raw_inputs=inputs,
        farm=inputs.get("farm", {}),
        crop=CropContext(
            crop=inputs.get("crop", ""),
            growth_stage=inputs.get("growth_stage", ""),
            suitability_hint=float(inputs.get("crop_suitability_hint", 0.6)),
        ),
    )
    obs.init_db()
    obs.log_run_start(
        run_id=run_id,
        payload=inputs,
        crop=inputs.get("crop", ""),
        growth_stage=inputs.get("growth_stage", ""),
        soil_type=inputs.get("soil_type", ""),
        lat=inputs.get("lat"),
        lon=inputs.get("lon"),
    )
    graph = get_graph()
    if graph is None:
        state = initial_state
        for node in (node_weather, node_soil, node_disease, node_advisory, node_market, node_decision):
            state = node(state)
        obs.log_run_complete(state.run_id, state.final_recommendation or "unknown", state.confidence or 0.0)
        return state
    final_output = graph.invoke(initial_state)
    state = final_output if isinstance(final_output, AgriMindState) else AgriMindState(**final_output)
    obs.log_run_complete(state.run_id, state.final_recommendation or "unknown", state.confidence or 0.0)
    return state
