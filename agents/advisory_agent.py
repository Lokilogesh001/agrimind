"""Advisory Agent — preliminary agronomic scoring.

The Advisory Agent is intentionally separate from the orchestrator's conflict
resolver. It computes the preliminary action scores S(a); the orchestrator
then applies the canonical two-stage policy on top of those scores.
"""
from __future__ import annotations

from dataclasses import dataclass

from decision.scoring import weighted_score, DEFAULT_WEIGHTS
from orchestrator.state import AdvisoryResult

ACTIONS = ("apply_fertilizer", "delay", "monitor")


def run(state, weights: dict | None = None) -> AdvisoryResult:
    """Compute preliminary S(a) scores without applying veto rules."""
    weights = weights or DEFAULT_WEIGHTS
    scores = {action: weighted_score(state, action=action, weights=weights) for action in ACTIONS}
    recommendation = max(scores, key=scores.get)
    return AdvisoryResult(
        scores=scores,
        preliminary_recommendation=recommendation,
        confidence=max(scores.values()) if scores else 0.0,
        reason="preliminary_weighted_score",
    )
