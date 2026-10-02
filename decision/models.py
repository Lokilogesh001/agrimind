"""Domain models for deterministic, auditable AgriMind decisions."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class ConflictSpec:
    agent_a: str
    agent_b: str
    issue: str

@dataclass
class Decision:
    action: str
    reason: str
    priority: Optional[int] = None
    overrides: list[ConflictSpec] = field(default_factory=list)
    scores: Optional[dict[str, float]] = None
    is_override: bool = False
    stage: str = "stage_2"

    def to_conflict_row(self, run_id: str, agent_a: str | None = None, agent_b: str | None = None, issue: str | None = None) -> dict:
        if all(x is not None for x in (agent_a, agent_b, issue)):
            return {"run_id": run_id, "agent_a": agent_a, "agent_b": agent_b, "issue": issue, "resolution": f"{self.action} ({self.reason})", "priority": self.priority}
        rows = self.to_conflict_rows(run_id)
        if not rows:
            raise ValueError("Decision contains no conflict specification")
        return rows[0]

    def to_conflict_rows(self, run_id: str) -> list[dict]:
        return [
            {
                "run_id": run_id,
                "agent_a": c.agent_a,
                "agent_b": c.agent_b,
                "issue": c.issue,
                "resolution": f"{self.action} ({self.reason})",
                "priority": self.priority,
            }
            for c in self.overrides
        ]
