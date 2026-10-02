from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from dotenv import load_dotenv

load_dotenv()

from llm.explainer import explain
from observability import database as obs
from orchestrator.graph import run_advisory

@asynccontextmanager
async def lifespan(_app: FastAPI):
    obs.init_db()
    yield


app = FastAPI(title="AgriMind API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class AdvisoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    crop: str = Field(default="", max_length=100)
    growth_stage: str = Field(default="", max_length=100)
    n: float = Field(ge=0)
    p: float = Field(ge=0)
    k: float = Field(ge=0)
    current_price: float = Field(default=0, ge=0)
    price_history: list[float] = Field(default_factory=list, max_length=365)
    weather_override: dict | None = None
    disease_override: dict | None = None
    soil_type: str = Field(default="", max_length=100)
    farm: dict = Field(default_factory=dict)

    @field_validator("price_history")
    @classmethod
    def validate_price_history(cls, values: list[float]) -> list[float]:
        if any(v < 0 for v in values):
            raise ValueError("price_history values must be non-negative")
        return values


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    farmer_action_taken: str = Field(max_length=200)
    outcome_reported: str = Field(default="", max_length=1000)
    comment: str = Field(default="", max_length=2000)


def _serialize(state):
    evidence = []
    try:
        from rag.retriever import KnowledgeRetriever
        disease_name = state.disease.normalized_disease or state.disease.predicted_class or ""
        if disease_name.lower() in {"healthy", "none", "unknown"}:
            disease_name = ""
        query_parts = [state.crop.crop, state.crop.growth_stage, disease_name, state.final_recommendation, "agronomy"]
        query = " ".join(p for p in query_parts if p).strip()
        evidence = KnowledgeRetriever().search(
            query,
            n_results=4,
            crop=state.crop.crop,
            growth_stage=state.crop.growth_stage,
            disease=disease_name,
        )
    except Exception:
        evidence = []
    explanation = explain(state, evidence)
    trail = obs.get_run_trail(state.run_id)
    llm_logs = [x for x in trail.get("agent_logs", []) if x.get("agent") == "llm_explainer"]
    llm_metadata = llm_logs[-1].get("output", {}) if llm_logs else {}
    return {
        "run_id": state.run_id,
        "recommendation": state.final_recommendation,
        "confidence": state.confidence,
        "explanation": explanation,
        "llm": llm_metadata,
        "weather": state.weather.__dict__,
        "soil": state.soil.__dict__,
        "disease": state.disease.__dict__,
        "advisory": state.advisory.__dict__,
        "market": state.market.__dict__,
        "conflicts": state.conflicts,
        "execution_trace": state.execution_trace,
        "evidence": evidence,
        "audit": trail,
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "agrimind-api", "version": "1.0.0"}


@app.post("/api/advisory")
def advisory(payload: AdvisoryRequest):
    try:
        return _serialize(run_advisory(payload.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _read_valid_image(image: UploadFile) -> bytes:
    content_type = (image.content_type or "").lower()
    suffix = Path(image.filename or "").suffix.lower()
    if content_type not in ALLOWED_IMAGE_TYPES or suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image.")

    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 5 MB upload limit.")
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.") from exc
    return data


@app.post("/api/advisory/upload")
async def advisory_upload(
    crop: str = Form("Tomato"), growth_stage: str = Form("vegetative"),
    lat: float | None = Form(None), lon: float | None = Form(None),
    n: float = Form(50, ge=0), p: float = Form(50, ge=0), k: float = Form(50, ge=0),
    current_price: float = Form(0, ge=0), price_history: str = Form(""),
    soil_type: str = Form(""), image: UploadFile | None = File(None),
):
    if image is None:
        raise HTTPException(status_code=400, detail="A crop leaf image is required.")

    path = None
    try:
        data = await _read_valid_image(image)
        try:
            history = [float(x.strip()) for x in price_history.split(",") if x.strip()]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="price_history must be comma-separated numbers.") from exc
        if len(history) > 365 or any(x < 0 for x in history):
            raise HTTPException(status_code=422, detail="price_history must contain at most 365 non-negative values.")

        suffix = Path(image.filename or "leaf.jpg").suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            path = tmp.name

        payload = AdvisoryRequest(
            lat=lat, lon=lon, crop=crop[:100], growth_stage=growth_stage[:100],
            n=n, p=p, k=k, current_price=current_price, price_history=history,
            soil_type=soil_type[:100],
        ).model_dump()
        payload["image_path"] = path  # internal, validated temporary path only
        return _serialize(run_advisory(payload))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    trail = obs.get_run_trail(run_id)
    if not trail.get("agent_logs") and not trail.get("decisions") and not trail.get("conflicts"):
        raise HTTPException(status_code=404, detail="Run not found")
    return trail


@app.post("/api/feedback")
def feedback(payload: FeedbackRequest):
    obs.log_feedback(**payload.model_dump())
    return {"status": "saved", "run_id": payload.run_id}
