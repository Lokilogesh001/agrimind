"""
End-to-end demo — runs the exact worked example from the canonical doc
(Section 49 / the reconciled documentation's example trail):

    Weather Agent  -> rainfall_risk = 0.82
    Soil Agent     -> deficiency = 0.91
    Disease Agent  -> confidence = 0.78, severity = high
    Advisory Agent -> would suggest APPLY fertilizer
    Orchestrator   -> DELAY (rainfall safety veto, Priority 1)
    Conflict       -> Weather vs Soil, logged to observability

Run: python main.py
"""

from observability import database as obs
from orchestrator.graph import run_advisory


def print_trail(state):
    print(f"\nRun ID: {state.run_id}\n")
    for line in state.execution_trace:
        print(f"  {line}")

    print(f"\nFinal recommendation: {state.final_recommendation}")

    if state.conflicts:
        print("\nConflicts logged:")
        for c in state.conflicts:
            print(f"  {c['agent_a']} vs {c['agent_b']} -> {c['resolution']} (priority {c['priority']})")
    else:
        print("\nNo conflicts — Stage 2 weighted scoring decided this run.")

    trail = obs.get_run_trail(state.run_id)
    print(f"\nPersisted to observability DB: "
          f"{len(trail['agent_logs'])} agent_logs, "
          f"{len(trail['decisions'])} decisions, "
          f"{len(trail['conflicts'])} conflicts.")


def scenario_matches_doc_example():
    """Weather + soil conflict — rainfall safety should veto the fertilizer
    application even though soil deficiency is severe."""
    inputs = {
        "weather_override": {"precip_prob": 0.90, "intensity": 0.80, "duration": 0.75},  # -> rainfall_risk ~0.82
        "n": 20, "p": 45, "k": 70,   # low nitrogen -> high deficiency
        "disease_override": {"predicted_class": "Tomato_Early_blight", "confidence": 0.78},
        "current_price": 2200, "price_history": [1900, 1950, 2000, 2000, 2050],
    }
    print("=" * 70)
    print("SCENARIO: rainfall safety veto overrides soil + disease urgency")
    print("=" * 70)
    state = run_advisory(inputs)
    print_trail(state)
    return state


def scenario_clear_weather_soil_deficiency():
    """No rain, real deficiency, healthy plant -> Stage 2 should favour
    apply_fertilizer with no veto firing."""
    inputs = {
        "weather_override": {"precip_prob": 0.05, "intensity": 0.05, "duration": 0.0},
        "n": 25, "p": 45, "k": 70,
        "disease_override": {"predicted_class": "healthy", "confidence": 0.95},
        "current_price": 2000, "price_history": [1950, 1980, 2000],
    }
    print("\n" + "=" * 70)
    print("SCENARIO: clear weather + soil deficiency, no disease -> Stage 2")
    print("=" * 70)
    state = run_advisory(inputs)
    print_trail(state)
    return state


def scenario_low_confidence_disease_is_a_gate():
    """Uncertain disease read should gate rather than block the whole run."""
    inputs = {
        "weather_override": {"precip_prob": 0.1, "intensity": 0.1, "duration": 0.0},
        "n": 40, "p": 45, "k": 70,
        "disease_override": {"predicted_class": "Tomato_Early_blight", "confidence": 0.42},
        "current_price": 2000, "price_history": [1950, 1980, 2000],
    }
    print("\n" + "=" * 70)
    print("SCENARIO: low-confidence disease read -> gate, not a hard veto")
    print("=" * 70)
    state = run_advisory(inputs)
    print_trail(state)
    return state


if __name__ == "__main__":
    obs.init_db()
    scenario_matches_doc_example()
    scenario_clear_weather_soil_deficiency()
    scenario_low_confidence_disease_is_a_gate()
