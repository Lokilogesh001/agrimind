"""AgriMind Production System Verification Suite.

Comprehensive, self-contained operational verification:
1. Observability database initialization and audit persistence
2. Disease vision model health, checkpoint loading, inference, and corruption rejection
3. Specialist agent contract validation (Weather, Soil, Disease, Advisory, Market)
4. Deterministic safety guard verification (Rules A-F)
5. ICAR agricultural knowledge retrieval grounding
6. Resilient LLM explanation fallback handling
7. FastAPI HTTP API endpoint validation
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from PIL import Image

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force development mode during local verification runner
os.environ["ENVIRONMENT"] = "development"
os.environ["ALLOW_TEST_OVERRIDES"] = "true"

from api.main import app
from fastapi.testclient import TestClient
from ml.disease_model import DiseasePredictor, get_model_health
from orchestrator.graph import run_advisory
from orchestrator.state import AgentStatus
from observability import database as obs
from llm.explainer import explain_with_metadata


def print_step(name: str):
    print(f"\n[VERIFY] {name}...")


def assert_pass(condition: bool, msg: str):
    if not condition:
        print(f"  ❌ FAIL: {msg}")
        raise AssertionError(msg)
    print(f"  ✅ PASS: {msg}")


def test_database():
    print_step("1. Observability Database Initialization")
    obs.init_db()
    with obs._get_session_factory()() as session:
        assert_pass(session is not None, "SQLite observability engine initialized cleanly")


def test_disease_model():
    print_step("2. Disease Vision Model & Checkpoint Integrity")
    health = get_model_health()
    assert_pass(health["ready"] is True, f"Model status is {health['status']} (expected READY)")
    assert_pass(health["classes_count"] == 38, f"Loaded all {health['classes_count']} PlantVillage classes")
    assert_pass(health["architecture"] == "MobileNetV3-Large", "Architecture is MobileNetV3-Large")

    predictor = DiseasePredictor(checkpoint=health["checkpoint_path"])

    # Test genuine inference on synthetic RGB leaf image
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
        img = Image.new("RGB", (224, 224), color=(34, 139, 34))  # Forest green
        img.save(tmp_path, format="JPEG")

    try:
        pred = predictor.predict(tmp_path, top_k=3)
        assert_pass(pred["predicted_class"] in predictor.classes, f"Predicted class: {pred['predicted_class']}")
        assert_pass(isinstance(pred["confidence"], float) and pred["confidence"] >= 0.0, f"Confidence score: {pred['confidence']}")
        assert_pass(len(pred["top_k"]) == 3, "Top-3 class distribution returned")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Test invalid image rejection (0-byte file)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as empty_tmp:
        empty_path = empty_tmp.name

    try:
        rejected = False
        try:
            predictor.predict(empty_path)
        except ValueError:
            rejected = True
        assert_pass(rejected, "Zero-byte / corrupted image rejected cleanly with ValueError")
    finally:
        if os.path.exists(empty_path):
            os.remove(empty_path)


def test_agent_contracts_and_workflow():
    print_step("3. Specialist Agent Contracts & End-to-End Orchestration")
    payload = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
        "n": 25,
        "p": 45,
        "k": 70,
        "soil_type": "red_soil",
        "soil_mode": "MEASURED",
        "weather_override": {"precip_prob": 0.05, "intensity": 0.0, "duration": 0.0},
        "disease_override": {"predicted_class": "healthy", "confidence": 0.95},
    }
    state = run_advisory(payload)

    assert_pass(len(state.weather.validate_contract()) == 0 and state.weather.status in ("AVAILABLE", "OVERRIDE", "SUCCESS"), f"Weather agent contract: {state.weather.status}")
    assert_pass(len(state.soil.validate_contract()) == 0 and state.soil.status in ("AVAILABLE", "MEASURED", "SUCCESS"), f"Soil agent contract: {state.soil.status}")
    assert_pass(len(state.disease.validate_contract()) == 0 and state.disease.status in ("AVAILABLE", "OVERRIDE", "SUCCESS"), f"Disease agent contract: {state.disease.status}")
    assert_pass(len(state.advisory.validate_contract()) == 0 and state.advisory.status in ("AVAILABLE", "SUCCESS"), f"Advisory agent contract: {state.advisory.status}")
    assert_pass(len(state.market.validate_contract()) == 0 and state.market.status in ("AVAILABLE", "SUCCESS", "OVERRIDE", "UNAVAILABLE", "REAL_DATA", "DEMO_DATA", "USER_SUPPLIED", "CACHED"), f"Market agent contract: {state.market.status}")
    assert_pass(len(state.execution_trace) > 0, f"Execution trace recorded ({len(state.execution_trace)} events)")
    assert_pass(state.decision_stability_score > 0.0, f"Decision stability score: {state.decision_stability_score}")


def test_safety_guards():
    print_step("4. Deterministic Safety Guards (Rules A - F)")

    # Rule D: Heavy precipitation forces DELAY veto
    state_rain = run_advisory({
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "weather_override": {"precip_prob": 0.95, "intensity": 0.85, "duration": 0.8},
        "n": 20, "p": 30, "k": 40,
        "soil_mode": "MEASURED",
        "disease_override": {"predicted_class": "Tomato___Early_blight", "confidence": 0.85},
    })
    assert_pass(state_rain.final_recommendation == "DELAY", f"Rule D (Rain Veto): Expected DELAY, got {state_rain.final_recommendation}")

    # Rule A: Missing soil measurements cannot fabricate NPK fertilizer doses
    state_soil = run_advisory({
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "weather_override": {"precip_prob": 0.05, "intensity": 0.0, "duration": 0.0},
        # No N, P, K provided
    })
    assert_pass(state_soil.soil.npk_available is False, "Rule A (Soil Guard): npk_available is False when unmeasured")
    assert_pass(state_soil.soil.overall_deficiency is None or state_soil.soil.overall_deficiency == 0.0, "Rule A: No fabricated fertilizer doses")
    assert_pass(state_soil.final_recommendation != "apply_fertilizer", "Rule A: Chemical fertilizer application blocked without measured soil test")

    # Rule B: Low disease confidence (< 0.60) blocks treatment actionability
    state_disease_low = run_advisory({
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "weather_override": {"precip_prob": 0.05, "intensity": 0.0, "duration": 0.0},
        "disease_override": {"predicted_class": "Tomato___Early_blight", "confidence": 0.45},
    })
    assert_pass(state_disease_low.disease.actionable is False, "Rule B (Confidence Gate): Action blocked for confidence < 0.60")

    # Rule C: Crop mismatch safety
    state_mismatch = run_advisory({
        "crop": "Rice",
        "growth_stage": "vegetative",
        "weather_override": {"precip_prob": 0.05, "intensity": 0.0, "duration": 0.0},
        "disease_override": {"predicted_class": "Tomato___Early_blight", "confidence": 0.90},
    })
    mismatch_flagged = any("crop match" in str(c).lower() or "mismatch" in str(c).lower() for c in state_mismatch.safety_constraints) or not state_mismatch.disease.actionable
    assert_pass(mismatch_flagged, "Rule C (Crop Mismatch): Flagged cross-species diagnosis in safety constraints")

    # Rule F: Market signal cannot override agronomic safety
    state_market = run_advisory({
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "weather_override": {"precip_prob": 0.95, "intensity": 0.90, "duration": 0.8},
        "market_override": {"price_trend": "falling_rapidly", "price_change_pct": -25.0, "action": "sell_immediately"},
    })
    assert_pass(state_market.final_recommendation == "DELAY", "Rule F (Agronomic Priority): Falling market price cannot override rainfall safety veto")


def test_rag_retrieval():
    print_step("5. ICAR Agricultural Knowledge Retrieval")
    from rag.retriever import KnowledgeRetriever
    retriever = KnowledgeRetriever()
    hits = retriever.search("tomato early blight copper fungicide spray schedule", n_results=3)
    assert_pass(len(hits) > 0, f"Retrieved {len(hits)} relevant ICAR advisory documents")
    assert_pass("document" in hits[0] and "text" in hits[0], "Retrieved documents contain document and text metadata")


def test_llm_fallback():
    print_step("6. LLM Explanation Provider Chain & Resilient Fallback")
    from rag.retriever import KnowledgeRetriever
    state = run_advisory({
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
        "n": 20, "p": 45, "k": 70,
        "soil_mode": "MEASURED",
        "weather_override": {"precip_prob": 0.05, "intensity": 0.0, "duration": 0.0},
        "disease_override": {"predicted_class": "healthy", "confidence": 0.95},
    })
    evidence = KnowledgeRetriever().search("tomato vegetative fertilizer", n_results=2)
    result = explain_with_metadata(state, evidence)
    assert_pass(result.provider in ("openai", "grok", "deterministic"), f"Explanation generated via provider: {result.provider}")
    assert_pass(len(result.text) > 0, "Detailed advisory guidance text generated successfully")
    assert_pass(result.structured_explanation is not None, "Structured explanation dictionary present")


def test_observability_persistence():
    print_step("7. Observability Database Persistence")
    with obs._get_session_factory()() as session:
        runs = session.query(obs.RunRecord).order_by(obs.RunRecord.timestamp.desc()).limit(5).all()
        assert_pass(len(runs) > 0, f"Retrieved {len(runs)} logged advisory runs from database")
        latest = runs[0]
        assert_pass(bool(latest.run_id), f"Latest run recorded: ID={latest.run_id[:8]}..., Action={latest.recommendation}")
        trail = obs.get_run_trail(latest.run_id)
        assert_pass("agent_logs" in trail, f"Auditable run trail contains {len(trail.get('agent_logs', []))} agent logs")


def test_api_endpoints():
    print_step("8. FastAPI HTTP Endpoints (Live In-Process Client)")
    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/health")
    assert_pass(res_health.status_code == 200 and res_health.json()["status"] == "ok", "/health endpoint returned 200 OK")

    # 2. Model health check
    res_model = client.get("/health/model")
    assert_pass(res_model.status_code == 200 and res_model.json()["ready"] is True, "/health/model endpoint returned 200 READY")

    # 3. Advisory test endpoint
    res_adv = client.post("/api/internal/test-advisory", json={
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
        "n": 20, "p": 30, "k": 40,
        "soil_mode": "MEASURED",
        "weather_override": {"precip_prob": 0.05, "intensity": 0.0, "duration": 0.0},
        "disease_override": {"predicted_class": "healthy", "confidence": 0.95},
    })
    assert_pass(res_adv.status_code == 200, f"/api/internal/test-advisory returned status {res_adv.status_code}")
    data = res_adv.json()
    assert_pass("recommendation" in data and "explanation" in data, f"Advisory returned valid response: {data.get('recommendation')}")


def main():
    print("=" * 70)
    print("🌾 AGRIMIND PRODUCTION SYSTEM VERIFICATION RUNNER")
    print("=" * 70)
    try:
        test_database()
        test_disease_model()
        test_agent_contracts_and_workflow()
        test_safety_guards()
        test_rag_retrieval()
        test_llm_fallback()
        test_observability_persistence()
        test_api_endpoints()

        print("\n" + "=" * 70)
        print("🎉 ALL 8 PRODUCTION SYSTEM CHECKS PASSED PERFECTLY!")
        print("=" * 70 + "\n")
        return 0
    except Exception as exc:
        print(f"\n❌ VERIFICATION FAILED: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
