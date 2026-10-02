"""Fast offline verification for the AgriMind prototype."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orchestrator.graph import run_advisory
from observability import database as obs
from rag.retriever import KnowledgeRetriever


def run(name, payload, expected):
    state=run_advisory(payload)
    ok=state.final_recommendation==expected
    print(f"{name}: {'PASS' if ok else 'FAIL'} -> {state.final_recommendation}")
    if not ok: raise SystemExit(1)

obs.init_db()
run("Rainfall safety veto", {"weather_override":{"precip_prob":.9,"intensity":.8,"duration":.75},"n":20,"p":45,"k":70,"disease_override":{"predicted_class":"Tomato_Early_blight","confidence":.78}}, "DELAY")
run("Soil deficiency", {"weather_override":{"precip_prob":.05,"intensity":.05,"duration":0},"n":25,"p":45,"k":70,"disease_override":{"predicted_class":"healthy","confidence":.95}}, "apply_fertilizer")
state=run_advisory({"weather_override":{"precip_prob":.1,"intensity":.1,"duration":0},"n":40,"p":45,"k":70,"disease_override":{"predicted_class":"Tomato_Early_blight","confidence":.42}})
assert state.disease.actionable is False
print("Disease confidence gate: PASS")

hits=KnowledgeRetriever().search("rice fertilizer soil test weather",3)
print(f"ICAR local retrieval: {'PASS' if hits else 'WARN'} ({len(hits)} hits)")
print("AgriMind offline verification complete.")
