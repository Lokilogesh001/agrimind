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
        _engine = create_engine(url, echo=False, future=True, connect_args=connect_args)
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
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Decision(Base):
    __tablename__ = "decisions"
    decision_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True, nullable=False)
    recommendation = Column(String)
    reason = Column(String)
    confidence = Column(Float)
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
    recommendation = Column(String)
    confidence = Column(Float)
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
                cols = {row[1] for row in conn.execute(text("PRAGMA table_info(runs)"))}
                new_cols = [
                    ("weather_status", "VARCHAR"),
                    ("market_status", "VARCHAR"),
                    ("disease_status", "VARCHAR"),
                    ("llm_provider", "VARCHAR"),
                    ("llm_status", "VARCHAR"),
                    ("prompt_tokens", "INTEGER"),
                    ("completion_tokens", "INTEGER"),
                    ("total_latency_ms", "FLOAT"),
                    ("completed_at", "DATETIME"),
                ]
                for col_name, col_type in new_cols:
                    if col_name not in cols:
                        conn.execute(text(f"ALTER TABLE runs ADD COLUMN {col_name} {col_type}"))
                conn.commit()
    except Exception:
        pass


def log_run_start(run_id: str, payload: dict, crop: str = "", growth_stage: str = "", soil_type: str = "", lat: float | None = None, lon: float | None = None):
    try:
        with _get_session_factory()() as session:
            row = RunRecord(
                run_id=run_id,
                crop=crop,
                growth_stage=growth_stage,
                soil_type=soil_type,
                lat=lat,
                lon=lon,
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
                session.commit()
    except Exception:
        pass


def log_agent_call(run_id: str, agent_name: str, input_data: dict, output_data: dict,
                    status: str, confidence: float, latency_ms: float):
    with _get_session_factory()() as session:
        row = AgentLog(
            run_id=run_id, agent_name=agent_name,
            input=json.dumps(input_data, default=str),
            output=json.dumps(output_data, default=str),
            status=status, confidence=confidence, latency=latency_ms,
        )
        session.add(row)
        session.commit()


def log_decision(run_id: str, recommendation: str, reason: str, confidence: float):
    with _get_session_factory()() as session:
        row = Decision(run_id=run_id, recommendation=recommendation, reason=reason, confidence=confidence)
        session.add(row)
        session.commit()


def log_conflict(run_id: str, agent_a: str, agent_b: str, issue: str, resolution: str, priority: int):
    with _get_session_factory()() as session:
        row = Conflict(
            run_id=run_id, agent_a=agent_a, agent_b=agent_b,
            issue=issue, resolution=resolution, priority=priority,
        )
        session.add(row)
        session.commit()


def log_feedback(run_id: str, farmer_action_taken: str, outcome_reported: str = "", comment: str = ""):
    with _get_session_factory()() as session:
        row = Feedback(
            run_id=run_id, farmer_action_taken=farmer_action_taken,
            outcome_reported=outcome_reported, comment=comment,
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
            "recommendation": run_record.recommendation,
            "confidence": run_record.confidence,
            "status": run_record.status,
            "total_latency_ms": getattr(run_record, "total_latency_ms", None),
            "weather_status": getattr(run_record, "weather_status", "AVAILABLE"),
            "market_status": getattr(run_record, "market_status", "AVAILABLE"),
            "disease_status": getattr(run_record, "disease_status", "AVAILABLE"),
            "llm_provider": getattr(run_record, "llm_provider", None),
            "timestamp": str(run_record.timestamp),
        } if run_record else None

        summary = {
            "run_id": run_id,
            "executed_agents": [l.agent_name for l in logs],
            "data_sources_available": {
                "weather": getattr(run_record, "weather_status", "AVAILABLE") == "AVAILABLE",
                "market": getattr(run_record, "market_status", "AVAILABLE") in ("REAL_DATA", "AVAILABLE"),
                "disease_model": getattr(run_record, "disease_status", "AVAILABLE") != "NOT_SUPPLIED",
            },
            "conflicts_count": len(conflicts),
            "deterministic_rule": decisions[0].reason if decisions else "unknown",
            "final_recommendation": run_record.recommendation if run_record else (decisions[0].recommendation if decisions else "unknown"),
            "confidence": run_record.confidence if run_record else (decisions[0].confidence if decisions else 0.0),
            "llm_used": bool(getattr(run_record, "llm_provider", None) and getattr(run_record, "llm_provider", "") not in ("", "deterministic")),
        }

        return {
            "run_id": run_id,
            "run": run_info,
            "summary": summary,
            "agent_logs": [
                {"agent": l.agent_name, "status": l.status, "confidence": l.confidence,
                 "latency_ms": l.latency, "output": json.loads(l.output) if l.output else {}}
                for l in logs
            ],
            "decisions": [
                {"recommendation": d.recommendation, "reason": d.reason, "confidence": d.confidence}
                for d in decisions
            ],
            "conflicts": [
                {"agent_a": c.agent_a, "agent_b": c.agent_b, "issue": c.issue,
                 "resolution": c.resolution, "priority": c.priority}
                for c in conflicts
            ],
            "feedback": [
                {"farmer_action_taken": f.farmer_action_taken, "outcome_reported": f.outcome_reported,
                 "comment": f.comment, "timestamp": str(f.timestamp)}
                for f in feedbacks
            ],
        }
