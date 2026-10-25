"""
Observability layer — implements the canonical schema (doc Section 5):

    agent_logs(id, run_id, agent_name, input, output, status, confidence, latency, timestamp)
    decisions(decision_id, run_id, recommendation, reason, confidence, timestamp)
    conflicts(conflict_id, run_id, agent_a, agent_b, issue, resolution, priority)
    feedback(run_id, farmer_action_taken, outcome_reported, comment, timestamp)

Production DATABASE_URL points at Supabase Postgres. Local dev/tests default
to a SQLite file so the orchestrator is runnable without provisioning a
Supabase project first — SQLAlchemy makes this swap a one-line env change,
it does not change the canonical architecture (Supabase Postgres is still
what production runs against).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, DateTime,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from sqlalchemy.pool import StaticPool

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///agrimind_local.db")

Base = declarative_base()
_engine = None
_SessionLocal = None


def _get_engine():
    _get_session_factory()
    return _engine


def _get_session_factory():
    """Create the engine lazily so tests and deployments can change DATABASE_URL.

    This also avoids binding the DB to the import-time working directory.
    """
    global _engine, _SessionLocal
    url = os.environ.get("DATABASE_URL", DATABASE_URL)
    if _engine is None or str(_engine.url) != url:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        engine_kwargs = {"echo": False, "future": True, "connect_args": connect_args}
        if url in ("sqlite:///:memory:", "sqlite://", "sqlite:///"):
            engine_kwargs["poolclass"] = StaticPool
        _engine = create_engine(url, **engine_kwargs)
        _SessionLocal = sessionmaker(bind=_engine, future=True)
    return _SessionLocal


def reset_engine_for_tests():
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


class AgentLog(Base):
    __tablename__ = "agent_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True, nullable=False)
    agent_name = Column(String, nullable=False)
    input = Column(Text)
    output = Column(Text)
    status = Column(String)
    confidence = Column(Float)
    latency = Column(Float)
    source = Column(String)
    evidence = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Decision(Base):
    __tablename__ = "decisions"
    decision_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True, nullable=False)
    recommendation = Column(String)
    reason = Column(String)
    confidence = Column(Float)
    stability_score = Column(Float)
    stability_level = Column(String)
    contributing_evidence = Column(Text)
    re_evaluation_trigger = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Conflict(Base):
    __tablename__ = "conflicts"
    conflict_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True, nullable=False)
    agent_a = Column(String)
    agent_b = Column(String)
    issue = Column(String)
    resolution = Column(String)
    priority = Column(Integer)
    conflict_type = Column(String)
    evidence = Column(Text)
    score_impact = Column(Float)


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True, nullable=False)
    farmer_action_taken = Column(String)
    outcome_reported = Column(String)
    comment = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RunRecord(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, unique=True, index=True, nullable=False)
    crop = Column(String)
    growth_stage = Column(String)
    soil_type = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    location_name = Column(String)
    resolved_location = Column(String)
    soil_provenance = Column(String)
    recommendation = Column(String)
    confidence = Column(Float)
    decision_stability_score = Column(Float)
    stability_level = Column(String)
    re_evaluation_trigger = Column(String)
    status = Column(String, default="completed")
    raw_payload = Column(Text)
    weather_status = Column(String, default="AVAILABLE")
    market_status = Column(String, default="AVAILABLE")
    disease_status = Column(String, default="AVAILABLE")
    llm_provider = Column(String)
    llm_status = Column(String)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_latency_ms = Column(Float)
    completed_at = Column(DateTime)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    factory = _get_session_factory()
    bind = factory.kw["bind"]
    Base.metadata.create_all(bind=bind)
    try:
        from sqlalchemy import text
        with bind.connect() as conn:
            if bind.dialect.name == "sqlite":
                # Ensure all columns exist across SQLite tables
                run_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(runs)"))}
                new_run_cols = [
                    ("weather_status", "VARCHAR"),
                    ("market_status", "VARCHAR"),
                    ("disease_status", "VARCHAR"),
                    ("llm_provider", "VARCHAR"),
                    ("llm_status", "VARCHAR"),
                    ("prompt_tokens", "INTEGER"),
                    ("completion_tokens", "INTEGER"),
                    ("total_latency_ms", "FLOAT"),
                    ("completed_at", "DATETIME"),
                    ("location_name", "VARCHAR"),
                    ("resolved_location", "VARCHAR"),
                    ("soil_provenance", "VARCHAR"),
                    ("decision_stability_score", "FLOAT"),
                    ("stability_level", "VARCHAR"),
                    ("re_evaluation_trigger", "VARCHAR"),
                ]
                for col_name, col_type in new_run_cols:
                    if col_name not in run_cols:
                        conn.execute(text(f"ALTER TABLE runs ADD COLUMN {col_name} {col_type}"))

                agent_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(agent_logs)"))}
                for col_name, col_type in [("source", "VARCHAR"), ("evidence", "TEXT")]:
                    if col_name not in agent_cols:
                        conn.execute(text(f"ALTER TABLE agent_logs ADD COLUMN {col_name} {col_type}"))

                dec_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(decisions)"))}
                for col_name, col_type in [
                    ("stability_score", "FLOAT"),
                    ("stability_level", "VARCHAR"),
                    ("contributing_evidence", "TEXT"),
                    ("re_evaluation_trigger", "VARCHAR"),
                ]:
                    if col_name not in dec_cols:
                        conn.execute(text(f"ALTER TABLE decisions ADD COLUMN {col_name} {col_type}"))

                conf_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(conflicts)"))}
                for col_name, col_type in [
                    ("conflict_type", "VARCHAR"),
                    ("evidence", "TEXT"),
                    ("score_impact", "FLOAT"),
                ]:
                    if col_name not in conf_cols:
                        conn.execute(text(f"ALTER TABLE conflicts ADD COLUMN {col_name} {col_type}"))

                conn.commit()
    except Exception:
        pass


def log_run_start(
    run_id: str,
    payload: dict,
    crop: str = "",
    growth_stage: str = "",
    soil_type: str = "",
    lat: float | None = None,
    lon: float | None = None,
    location_name: str = "",
    resolved_location: str = "",
    soil_provenance: str = "",
):
    try:
        with _get_session_factory()() as session:
            row = RunRecord(
                run_id=run_id,
                crop=crop,
                growth_stage=growth_stage,
                soil_type=soil_type,
                lat=lat,
                lon=lon,
                location_name=location_name,
                resolved_location=resolved_location,
                soil_provenance=soil_provenance,
                raw_payload=json.dumps(payload, default=str),
                status="started",
            )
            session.add(row)
            session.commit()
    except Exception:
        pass


def log_run_complete(
    run_id: str,
    recommendation: str,
    confidence: float,
    total_latency_ms: float = 0.0,
    weather_status: str = "AVAILABLE",
    market_status: str = "AVAILABLE",
    disease_status: str = "AVAILABLE",
    llm_provider: str = "",
    llm_status: str = "",
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    decision_stability_score: float | None = None,
    stability_level: str = "",
    re_evaluation_trigger: str = "",
    resolved_location: str = "",
    soil_provenance: str = "",
):
    try:
        with _get_session_factory()() as session:
            row = session.query(RunRecord).filter_by(run_id=run_id).first()
            if row:
                row.recommendation = recommendation
                row.confidence = confidence
                row.status = "completed"
                row.completed_at = datetime.now(timezone.utc)
                if total_latency_ms > 0:
                    row.total_latency_ms = total_latency_ms
                if weather_status:
                    row.weather_status = weather_status
                if market_status:
                    row.market_status = market_status
                if disease_status:
                    row.disease_status = disease_status
                if llm_provider:
                    row.llm_provider = llm_provider
                if llm_status:
                    row.llm_status = llm_status
                if prompt_tokens is not None:
                    row.prompt_tokens = prompt_tokens
                if completion_tokens is not None:
                    row.completion_tokens = completion_tokens
                if decision_stability_score is not None:
                    row.decision_stability_score = decision_stability_score
                if stability_level:
                    row.stability_level = stability_level
                if re_evaluation_trigger:
                    row.re_evaluation_trigger = re_evaluation_trigger
                if resolved_location and not row.resolved_location:
                    row.resolved_location = resolved_location
                if soil_provenance and not row.soil_provenance:
                    row.soil_provenance = soil_provenance
                session.commit()
    except Exception:
        pass


def log_agent_call(
    run_id: str,
    agent_name: str,
    input_data: dict,
    output_data: dict,
    status: str,
    confidence: float,
    latency_ms: float,
    source: str = "",
    evidence: Any = None,
):
    with _get_session_factory()() as session:
        row = AgentLog(
            run_id=run_id,
            agent_name=agent_name,
            input=json.dumps(input_data, default=str),
            output=json.dumps(output_data, default=str),
            status=status,
            confidence=confidence,
            latency=latency_ms,
            source=source,
            evidence=json.dumps(evidence, default=str) if evidence else "",
        )
        session.add(row)
        session.commit()


def log_decision(
    run_id: str,
    recommendation: str,
    reason: str,
    confidence: float,
    stability_score: float | None = None,
    stability_level: str = "",
    contributing_evidence: Any = None,
    re_evaluation_trigger: str = "",
):
    with _get_session_factory()() as session:
        row = Decision(
            run_id=run_id,
            recommendation=recommendation,
            reason=reason,
            confidence=confidence,
            stability_score=stability_score,
            stability_level=stability_level,
            contributing_evidence=json.dumps(contributing_evidence, default=str) if contributing_evidence else "",
            re_evaluation_trigger=re_evaluation_trigger,
        )
        session.add(row)
        session.commit()


def log_conflict(
    run_id: str,
    agent_a: str,
    agent_b: str,
    issue: str,
    resolution: str,
    priority: int,
    conflict_type: str = "",
    evidence: str = "",
    score_impact: float = 0.0,
):
    with _get_session_factory()() as session:
        row = Conflict(
            run_id=run_id,
            agent_a=agent_a,
            agent_b=agent_b,
            issue=issue,
            resolution=resolution,
            priority=priority,
            conflict_type=conflict_type,
            evidence=evidence,
            score_impact=score_impact,
        )
        session.add(row)
        session.commit()


def log_feedback(
    run_id: str,
    farmer_action_taken: str,
    outcome_reported: str = "",
    comment: str = "",
    days_post_application: int | None = None,
    reporter_type: str = "farmer_self_reported",
    outcome_category: str = "partially_improved",
    **kwargs: Any,
):
    with _get_session_factory()() as session:
        detail_comment = comment
        if days_post_application is not None:
            detail_comment = f"[{reporter_type.upper()} · {days_post_application}d post-app · {outcome_category.upper()}] {comment}".strip()
        row = Feedback(
            run_id=run_id,
            farmer_action_taken=farmer_action_taken,
            outcome_reported=outcome_reported,
            comment=detail_comment,
        )
        session.add(row)
        session.commit()


def get_run_trail(run_id: str) -> dict:
    """Pulls the full auditable trail for one run — agent logs, decision,
    conflicts, and run metadata."""
    with _get_session_factory()() as session:
        logs = session.query(AgentLog).filter_by(run_id=run_id).all()
        decisions = session.query(Decision).filter_by(run_id=run_id).all()
        conflicts = session.query(Conflict).filter_by(run_id=run_id).all()
        feedbacks = session.query(Feedback).filter_by(run_id=run_id).all()
        run_record = session.query(RunRecord).filter_by(run_id=run_id).first()

        run_info = {
            "run_id": run_record.run_id,
            "crop": run_record.crop,
            "growth_stage": run_record.growth_stage,
            "soil_type": run_record.soil_type,
            "lat": run_record.lat,
            "lon": run_record.lon,
            "location_name": getattr(run_record, "location_name", None),
            "resolved_location": getattr(run_record, "resolved_location", None),
            "soil_provenance": getattr(run_record, "soil_provenance", None),
            "recommendation": run_record.recommendation,
            "confidence": run_record.confidence,
            "decision_stability_score": getattr(run_record, "decision_stability_score", None),
            "stability_level": getattr(run_record, "stability_level", None),
            "re_evaluation_trigger": getattr(run_record, "re_evaluation_trigger", None),
            "status": run_record.status,
            "total_latency_ms": getattr(run_record, "total_latency_ms", None),
            "weather_status": getattr(run_record, "weather_status", "AVAILABLE"),
            "market_status": getattr(run_record, "market_status", "AVAILABLE"),
            "disease_status": getattr(run_record, "disease_status", "AVAILABLE"),
            "llm_provider": getattr(run_record, "llm_provider", None),
            "timestamp": str(run_record.timestamp),
        } if run_record else None

        primary_decision = decisions[0] if decisions else None
        summary = {
            "run_id": run_id,
            "executed_agents": [l.agent_name for l in logs],
            "data_sources_available": {
                "weather": getattr(run_record, "weather_status", "AVAILABLE") in ("AVAILABLE", "REAL_DATA", "FALLBACK"),
                "market": getattr(run_record, "market_status", "") in ("REAL_DATA", "DEMO_DATA", "AVAILABLE"),
                "disease_model": getattr(run_record, "disease_status", "AVAILABLE") not in ("NOT_SUPPLIED", "UNAVAILABLE", ""),
            },
            "market_provenance": {
                "available": getattr(run_record, "market_status", "") in ("REAL_DATA", "DEMO_DATA", "AVAILABLE"),
                "status": getattr(run_record, "market_status", "UNAVAILABLE"),
                "authoritative": False if getattr(run_record, "market_status", "") == "DEMO_DATA" else (getattr(run_record, "market_status", "") == "REAL_DATA"),
                "source": "caller_provided" if getattr(run_record, "market_status", "") == "DEMO_DATA" else ("agmarknet_api" if getattr(run_record, "market_status", "") == "REAL_DATA" else "none"),
            },
            "conflicts_count": len(conflicts),
            "deterministic_rule": primary_decision.reason if primary_decision else "unknown",
            "final_recommendation": run_record.recommendation if run_record else (primary_decision.recommendation if primary_decision else "unknown"),
            "confidence": run_record.confidence if run_record else (primary_decision.confidence if primary_decision else 0.0),
            "decision_stability_score": getattr(run_record, "decision_stability_score", getattr(primary_decision, "stability_score", None)),
            "stability_level": getattr(run_record, "stability_level", getattr(primary_decision, "stability_level", None)),
            "re_evaluation_trigger": getattr(run_record, "re_evaluation_trigger", getattr(primary_decision, "re_evaluation_trigger", None)),
            "llm_used": bool(getattr(run_record, "llm_provider", None) and getattr(run_record, "llm_provider", "") not in ("", "deterministic")),
        }

        return {
            "run_id": run_id,
            "run": run_info,
            "summary": summary,
            "agent_logs": [
                {
                    "agent": l.agent_name,
                    "status": l.status,
                    "confidence": l.confidence,
                    "latency_ms": l.latency,
                    "source": getattr(l, "source", None),
                    "output": json.loads(l.output) if l.output else {},
                }
                for l in logs
            ],
            "decisions": [
                {
                    "recommendation": d.recommendation,
                    "reason": d.reason,
                    "confidence": d.confidence,
                    "stability_score": getattr(d, "stability_score", None),
                    "stability_level": getattr(d, "stability_level", None),
                    "re_evaluation_trigger": getattr(d, "re_evaluation_trigger", None),
                }
                for d in decisions
            ],
            "conflicts": [
                {
                    "agent_a": c.agent_a,
                    "agent_b": c.agent_b,
                    "issue": c.issue,
                    "resolution": c.resolution,
                    "priority": c.priority,
                    "conflict_type": getattr(c, "conflict_type", None),
                    "evidence": getattr(c, "evidence", None),
                    "score_impact": getattr(c, "score_impact", None),
                }
                for c in conflicts
            ],
            "feedback": [
                {
                    "farmer_action_taken": f.farmer_action_taken,
                    "outcome_reported": f.outcome_reported,
                    "comment": f.comment,
                    "timestamp": str(f.timestamp),
                }
                for f in feedbacks
            ],
        }

