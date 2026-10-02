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
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    factory = _get_session_factory()
    factory.kw["bind"].dispose if False else None
    Base.metadata.create_all(bind=factory.kw["bind"])


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


def log_run_complete(run_id: str, recommendation: str, confidence: float):
    try:
        with _get_session_factory()() as session:
            row = session.query(RunRecord).filter_by(run_id=run_id).first()
            if row:
                row.recommendation = recommendation
                row.confidence = confidence
                row.status = "completed"
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
            "timestamp": str(run_record.timestamp),
        } if run_record else None

        return {
            "run_id": run_id,
            "run": run_info,
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
        }
