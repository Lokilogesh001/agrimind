from __future__ import annotations
from decision.models import ConflictSpec, Decision
from decision.scoring import weighted_score
from decision.evidence_engine import evaluate_decision

RAINFALL_RISK_VETO_THRESHOLD = 0.70
DISEASE_CONFIDENCE_GATE = 0.60
SOIL_DEFICIENCY_APPLY_THRESHOLD = 0.60
ACTIONS = ("apply_fertilizer", "delay", "monitor")


def resolve_conflict(state) -> Decision:
    """Canonical two-stage AgriMind conflict resolution via Adaptive Evidence Engine."""
    return evaluate_decision(state)

