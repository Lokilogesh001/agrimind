"""Canonical two-stage AgriMind conflict resolution.

Stage 1 is a strict priority hierarchy. Stage 2 is weighted scoring only when
Stage 1 has not produced a terminal action. Priority 2 is deliberately a gate.
"""
from __future__ import annotations
from decision.models import ConflictSpec, Decision
from decision.scoring import weighted_score

RAINFALL_RISK_VETO_THRESHOLD = 0.70
DISEASE_CONFIDENCE_GATE = 0.60
SOIL_DEFICIENCY_APPLY_THRESHOLD = 0.60
ACTIONS = ("apply_fertilizer", "delay", "monitor")


def resolve_conflict(state) -> Decision:
    # P1: safety veto.
    if state.weather.rainfall_risk > RAINFALL_RISK_VETO_THRESHOLD:
        return Decision(
            action="DELAY", reason="rainfall_risk", priority=1, stage="stage_1",
            overrides=[
                ConflictSpec("weather", "soil", "rainfall_risk"),
                ConflictSpec("weather", "advisory", "rainfall_risk"),
                ConflictSpec("weather", "market", "rainfall_risk"),
            ], is_override=True,
        )

    # P2: confidence gate, not a terminal decision.
    # Requires both an actual detected disease signal and confidence >= threshold.
    state.disease.actionable = bool(state.disease.predicted_class) and state.disease.confidence >= DISEASE_CONFIDENCE_GATE

    # P3: disease urgency.
    if state.disease.actionable and state.disease.severity == "high":
        return Decision(
            action="DISEASE_MANAGEMENT_FIRST", reason="disease_urgency", priority=3,
            stage="stage_1", overrides=[ConflictSpec("disease", "advisory", "disease_urgency")],
            is_override=True,
        )

    # P4: severe soil deficiency is a Stage-1 terminal rule.
    if state.soil.overall_deficiency > SOIL_DEFICIENCY_APPLY_THRESHOLD:
        return Decision(
            action="apply_fertilizer", reason="soil_deficiency", priority=4,
            stage="stage_1", overrides=[ConflictSpec("soil", "advisory", "soil_deficiency")],
            is_override=True,
        )

    scores = dict(state.advisory.scores) if state.advisory.scores else {
        action: weighted_score(state, action) for action in ACTIONS
    }
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    best_action = ranked[0][0]

    # P5: market is only a narrow Stage-2 tie-breaker.
    if len(ranked) > 1 and abs(ranked[0][1] - ranked[1][1]) < 0.05:
        tied = {ranked[0][0], ranked[1][0]}
        if state.market.market_score > 0.60 and "delay" in tied:
            best_action = "delay"
            return Decision(
                action="delay",
                reason="market_tiebreaker",
                scores=scores,
                stage="stage_2",
                overrides=[ConflictSpec("market", "advisory", "market_tiebreaker")],
                is_override=False,
            )

    return Decision(action=best_action, reason="weighted_score", scores=scores, stage="stage_2")
