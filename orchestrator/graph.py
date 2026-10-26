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
from data_sources.crops import normalize_crop, normalize_crop_stage
from data_sources.geocoding import resolve_location
from data_sources.soil import estimate_soil_from_location
from decision.rules import resolve_conflict
from observability import database as obs
from orchestrator.state import AgriMindState, CropContext


def _timed(fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, round((time.perf_counter() - start) * 1000, 2)


def node_weather(state: AgriMindState) -> AgriMindState:
    inputs = state.raw_inputs
    lat = inputs.get("lat")
    lon = inputs.get("lon")

    result, latency = _timed(
        weather_agent.run,
        lat=lat, lon=lon,
        override=inputs.get("weather_override"),
    )
    result.execution_time_ms = latency
    result.input_summary = {"lat": lat, "lon": lon, "has_override": bool(inputs.get("weather_override"))}
    result.findings = f"Rainfall risk: {result.rainfall_risk:.2f} ({result.risk_level})"
    if result.status == "UNAVAILABLE":
        result.warnings = ["Weather telemetry is unavailable. Running under safe default assumptions."]
    elif result.status == "TIMEOUT":
        result.warnings = ["Weather provider timed out. Operating with unverified telemetry."]
    result.evidence = [{"rainfall_risk": result.rainfall_risk, "fertilizer_condition": result.fertilizer_condition}]

    state.weather = result
    state.log(f"weather_agent -> rainfall_risk={result.rainfall_risk}")
    obs.log_agent_call(
        state.run_id, "weather", inputs.get("weather_override") or {"lat": lat, "lon": lon}, result.__dict__,
        "ok" if result.confidence > 0 else "degraded", result.confidence, latency,
        source="open_meteo" if result.is_available else "offline",
        evidence={"rainfall_risk": result.rainfall_risk, "fertilizer_condition": result.fertilizer_condition},
    )
    return state


def node_soil(state: AgriMindState) -> AgriMindState:
    inputs = state.raw_inputs
    soil_type = inputs.get("soil_type", "")
    soil_mode = inputs.get("soil_mode", "")
    n = inputs.get("n")
    p = inputs.get("p")
    k = inputs.get("k")

    # If NPK is unmeasured / not provided
    if n is None or p is None or k is None:
        if not soil_type and (inputs.get("location_name") or inputs.get("lat")):
            est = estimate_soil_from_location(
                location_name=inputs.get("location_name", ""),
                lat=inputs.get("lat"),
                lon=inputs.get("lon"),
            )
            soil_type = est.get("soil_type", "")
            soil_mode = "LOCATION_ESTIMATED"
        elif soil_type:
            soil_mode = soil_mode or "USER_SELECTED"
        else:
            soil_mode = "UNAVAILABLE"

    result, latency = _timed(
        soil_agent.run,
        n=n, p=p, k=k,
        crop=state.crop.crop,
        soil_type=soil_type,
        mode=soil_mode,
    )
    result.execution_time_ms = latency
    result.input_summary = {"n": n, "p": p, "k": k, "crop": state.crop.crop, "soil_type": soil_type, "mode": soil_mode}
    result.findings = result.nutrient_assessment_text
    if not result.npk_available:
        result.warnings = ["NPK measurements were not provided. Soil testing is required before precise fertilizer recommendation."]
    result.evidence = [{"npk_available": result.npk_available, "overall_deficiency": result.overall_deficiency}]

    state.soil = result
    state.log(f"soil_agent -> overall_deficiency={result.overall_deficiency} (npk_available={result.npk_available})")
    obs.log_agent_call(
        state.run_id, "soil", {"n": n, "p": p, "k": k, "soil_type": soil_type, "mode": soil_mode},
        result.__dict__, "ok" if result.npk_available else "unmeasured", result.confidence, latency,
        source=result.calibration_source,
        evidence={"npk_available": result.npk_available, "overall_deficiency": result.overall_deficiency},
    )
    return state


def node_disease(state: AgriMindState) -> AgriMindState:
    inputs = state.raw_inputs
    model_choice = inputs.get("disease_model") or inputs.get("model_name")
    result, latency = _timed(
        disease_agent.run,
        image_path=inputs.get("image_path"),
        override=inputs.get("disease_override"),
        selected_crop=state.crop.crop,
        model_name=model_choice,
    )
    result.execution_time_ms = latency
    result.input_summary = {
        "has_image": bool(inputs.get("image_path")),
        "selected_crop": state.crop.crop,
        "has_override": bool(inputs.get("disease_override")),
        "model_name": model_choice,
    }
    result.findings = (
        f"Detected: {result.predicted_class} (confidence: {result.confidence:.2f})"
        if result.predicted_class else f"Status: {result.status}"
    )
    if result.status == "MODEL_UNAVAILABLE":
        result.warnings = ["Disease model checkpoint is unavailable. Image inference cannot run."]
    elif result.status == "INVALID_IMAGE":
        result.warnings = ["Uploaded image is invalid, corrupted, or unsupported."]
    elif result.crop_mismatch:
        result.warnings = [f"Detected crop '{result.crop_detected}' does not match selected crop '{state.crop.crop}'."]
    result.evidence = [{"predicted_class": result.predicted_class, "crop_mismatch": result.crop_mismatch, "status": result.status}]

    state.disease = result
    if result.predicted_class:
        mismatch_note = " [CROP MISMATCH]" if result.crop_mismatch else ""
        state.log(f"disease_agent -> {result.predicted_class} ({result.confidence}){mismatch_note}")
    else:
        state.log("disease_agent -> no disease image/signal provided")
    obs.log_agent_call(
        state.run_id, "disease",
        inputs.get("disease_override") or {"image_path": inputs.get("image_path")},
        result.__dict__, "ok" if result.predicted_class else "no_input", result.confidence, latency,
        source=result.status,
        evidence={"predicted_class": result.predicted_class, "crop_mismatch": result.crop_mismatch},
    )
    return state


def node_advisory(state: AgriMindState) -> AgriMindState:
    """Standalone Advisory Agent: compute preliminary S(a), no veto logic."""
    result, latency = _timed(advisory_agent.run, state)
    result.execution_time_ms = latency
    result.input_summary = {"crop": state.crop.crop, "growth_stage": state.crop.growth_stage}
    result.findings = f"Preliminary recommendation: {result.preliminary_recommendation}"
    result.evidence = [{"preliminary_recommendation": result.preliminary_recommendation, "scores": result.scores}]

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
    result.execution_time_ms = latency
    result.input_summary = {"current_price": inputs.get("current_price", 0), "crop": state.crop.crop}
    result.findings = f"Market score: {result.market_score:.2f}, signal: {result.signal}"
    if not result.is_available:
        result.warnings = ["Market pricing data is unavailable. Proceeding with agronomic monitoring."]
    result.evidence = [{"market_score": result.market_score, "signal": result.signal}]

    state.market = result
    state.log(f"market_agent -> score={result.market_score} signal={result.signal}")
    obs.log_agent_call(
        state.run_id, "market",
        {"current_price": inputs.get("current_price"), "price_history": inputs.get("price_history"), "crop": state.crop.crop},
        result.__dict__, "ok" if result.is_available else "unavailable", result.confidence, latency,
        source=result.source,
        evidence={"market_score": result.market_score, "signal": result.signal},
    )
    return state


def node_decision(state: AgriMindState) -> AgriMindState:
    """Orchestrator decision layer: Adaptive Evidence Engine + Stage 1 vetoes + Stage 2 scores."""
    decision, _latency = _timed(resolve_conflict, state)
    state.final_recommendation = decision.action

    conflict_rows = decision.to_conflict_rows(state.run_id)
    if not state.conflicts:
        state.conflicts = conflict_rows
    else:
        for c in state.conflicts:
            c["run_id"] = state.run_id

    for row in conflict_rows:
        obs.log_conflict(**row)

    confidence = (decision.scores.get(decision.action, max(decision.scores.values())) if decision.scores else 0.85)
    state.confidence = confidence
    state.log(f"orchestrator -> {decision.action} ({decision.reason}) [DSS: {state.decision_stability_score} - {state.stability_level}]")
    obs.log_decision(
        state.run_id,
        decision.action,
        decision.reason,
        confidence,
        stability_score=state.decision_stability_score,
        stability_level=state.stability_level,
        contributing_evidence=state.supporting_evidence,
        re_evaluation_trigger=state.re_evaluation_trigger,
    )
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
    start_time = time.monotonic()
    run_id = str(uuid.uuid4())

    # 1. Geocode Location if location_name provided
    loc_query = inputs.get("location_name") or inputs.get("location") or ""
    lat = inputs.get("lat")
    lon = inputs.get("lon")
    resolved_loc_str = ""

    if loc_query or (lat is not None and lon is not None):
        geo = resolve_location(loc_query, lat, lon)
        if geo.get("latitude") is not None and geo.get("longitude") is not None:
            inputs["lat"] = geo["latitude"]
            inputs["lon"] = geo["longitude"]
            resolved_loc_str = geo.get("resolved_location") or str(loc_query)
            inputs["location_name"] = resolved_loc_str
            inputs["geocoding_source"] = geo.get("source")
            inputs["geocoding_status"] = geo.get("status")
        else:
            inputs["geocoding_status"] = geo.get("status", "INVALID")
            inputs["geocoding_error"] = geo.get("error")

    # 2. Normalize Crop and Growth Stage
    raw_crop = inputs.get("crop", "")
    norm_crop = normalize_crop(raw_crop)
    canonical_crop = norm_crop["name"] if norm_crop else raw_crop
    canonical_stage = normalize_crop_stage(inputs.get("growth_stage", ""))

    initial_state = AgriMindState(
        run_id=run_id,
        raw_inputs=inputs,
        farm=inputs.get("farm", {}),
        crop=CropContext(
            crop=canonical_crop,
            growth_stage=canonical_stage,
            suitability_hint=float(inputs.get("crop_suitability_hint", 0.6)),
        ),
    )
    obs.init_db()
    obs.log_run_start(
        run_id=run_id,
        payload=inputs,
        crop=canonical_crop,
        growth_stage=canonical_stage,
        soil_type=inputs.get("soil_type", ""),
        lat=inputs.get("lat"),
        lon=inputs.get("lon"),
        location_name=loc_query,
        resolved_location=resolved_loc_str,
    )
    graph = get_graph()
    if graph is None:
        state = initial_state
        for node in (node_weather, node_soil, node_disease, node_advisory, node_market, node_decision):
            state = node(state)
        total_ms = round((time.monotonic() - start_time) * 1000, 2)
        obs.log_run_complete(
            state.run_id,
            state.final_recommendation or "unknown",
            state.confidence or 0.0,
            total_latency_ms=total_ms,
            weather_status=getattr(state.weather, "status", "AVAILABLE"),
            market_status=getattr(state.market, "status", "AVAILABLE"),
            disease_status=getattr(state.disease, "status", "AVAILABLE"),
            decision_stability_score=state.decision_stability_score,
            stability_level=state.stability_level,
            re_evaluation_trigger=state.re_evaluation_trigger,
            resolved_location=resolved_loc_str,
            soil_provenance=str(getattr(state.soil, "provenance", {}).get("mode", "")),
        )
        return state

    final_output = graph.invoke(initial_state)
    state = final_output if isinstance(final_output, AgriMindState) else AgriMindState(**final_output)
    total_ms = round((time.monotonic() - start_time) * 1000, 2)
    obs.log_run_complete(
        state.run_id,
        state.final_recommendation or "unknown",
        state.confidence or 0.0,
        total_latency_ms=total_ms,
        weather_status=getattr(state.weather, "status", "AVAILABLE"),
        market_status=getattr(state.market, "status", "AVAILABLE"),
        disease_status=getattr(state.disease, "status", "AVAILABLE"),
        decision_stability_score=state.decision_stability_score,
        stability_level=state.stability_level,
        re_evaluation_trigger=state.re_evaluation_trigger,
        resolved_location=resolved_loc_str,
        soil_provenance=str(getattr(state.soil, "provenance", {}).get("mode", "")),
    )
    return state
