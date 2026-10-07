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

from data_sources.crops import CATEGORIES, STAGE_REGISTRY, get_crop_registry, get_crops_by_category, normalize_crop
from data_sources.geocoding import resolve_location, search_locations
from data_sources.stores import DEFAULT_SEARCH_RADIUS_KM, find_nearby_stores
from llm.explainer import explain, explain_with_metadata
from observability import database as obs
from orchestrator.graph import run_advisory

@asynccontextmanager
async def lifespan(_app: FastAPI):
    obs.init_db()
    yield


app = FastAPI(title="AgriMind API", version="1.2.0", lifespan=lifespan)
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
    location_name: str | None = Field(default=None, max_length=200)
    crop: str = Field(default="", max_length=100)
    growth_stage: str = Field(default="", max_length=100)
    n: float | None = Field(default=None, ge=0)
    p: float | None = Field(default=None, ge=0)
    k: float | None = Field(default=None, ge=0)
    soil_mode: str | None = Field(default=None, max_length=50)
    current_price: float = Field(default=0, ge=0)
    price_history: list[float] = Field(default_factory=list, max_length=365)
    weather_override: dict | None = None
    disease_override: dict | None = None
    soil_type: str = Field(default="", max_length=100)
    farm: dict = Field(default_factory=dict)
    farm_area: float | None = Field(default=None, ge=0)
    irrigation_method: str | None = Field(default=None, max_length=100)
    sowing_date: str | None = Field(default=None, max_length=50)
    last_irrigation: str | None = Field(default=None, max_length=50)
    symptoms: str | None = Field(default=None, max_length=500)

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
            location=state.raw_inputs.get("location_name"),
        )
        if evidence:
            from decision.evidence_quality import calculate_evidence_quality
            eqs, eqs_lvl, eqs_brk = calculate_evidence_quality(state, rag_evidence=evidence)
            state.evidence_quality_score = eqs
            state.evidence_quality_level = eqs_lvl
            state.evidence_quality_breakdown = eqs_brk.to_dict()
    except Exception:
        evidence = []

    llm_result = explain_with_metadata(state, evidence)
    explanation = llm_result.text
    llm_structured = llm_result.structured_explanation

    trail = obs.get_run_trail(state.run_id)
    llm_logs = [x for x in trail.get("agent_logs", []) if x.get("agent") == "llm_explainer"]
    llm_metadata = llm_logs[-1].get("output", {}) if llm_logs else {}
    if llm_metadata:
        toks = llm_metadata.get("tokens") or {}
        obs.log_run_complete(
            state.run_id,
            state.final_recommendation or "unknown",
            state.confidence or 0.0,
            weather_status=getattr(state.weather, "status", "AVAILABLE"),
            market_status=getattr(state.market, "status", "AVAILABLE"),
            disease_status=getattr(state.disease, "status", "AVAILABLE"),
            llm_provider=llm_metadata.get("provider", llm_result.provider),
            llm_status=llm_metadata.get("status", llm_result.status),
            prompt_tokens=toks.get("prompt_tokens"),
            completion_tokens=toks.get("completion_tokens"),
        )

    from agents.weather_agent import get_weather_risk_level
    w_score = getattr(state.weather, "rainfall_risk", 0.0)
    weather_risk_data = {
        "score": w_score,
        "level": getattr(state.weather, "risk_level", None) or get_weather_risk_level(w_score),
        "explanation": getattr(state.weather, "risk_explanation", ""),
        "precipitation_probability": getattr(state.weather, "precipitation_probability", None),
        "rainfall_amount_mm": getattr(state.weather, "rainfall_amount_mm", None),
    }

    soil_status_data = {
        "nutrient_status": getattr(state.soil, "nutrient_status", "UNAVAILABLE"),
        "status": getattr(state.soil, "status", "UNAVAILABLE"),
        "assessment_text": getattr(state.soil, "nutrient_assessment_text", ""),
        "npk_available": getattr(state.soil, "npk_available", False),
        "overall_deficiency": getattr(state.soil, "overall_deficiency", None),
        "priority_nutrient": getattr(state.soil, "priority_nutrient", ""),
    }

    c_det = (getattr(state.disease, "crop_detected", "") or "Tomato").capitalize()
    c_sel = (getattr(state.crop, "crop", "") or "Rice").capitalize()
    is_mismatch = getattr(state.disease, "crop_mismatch", False)
    d_conf = getattr(state.disease, "confidence", 0.0)
    has_disease = bool(getattr(state.disease, "predicted_class", None))

    disease_gate_data = {
        "confidence": d_conf,
        "confidence_percentage": round(d_conf * 100),
        "confidence_gate": "PASSED" if d_conf >= 0.60 else ("NOT_APPLICABLE" if not has_disease else "FAILED"),
        "crop_match": "FAILED" if is_mismatch else ("NOT_APPLICABLE" if not has_disease else "PASSED"),
        "action": "BLOCKED" if (not getattr(state.disease, "actionable", False) and has_disease) else ("ALLOWED" if getattr(state.disease, "actionable", False) else "INACTIVE"),
        "reason": (
            f"Predicted crop is {c_det} but selected crop is {c_sel}."
            if is_mismatch
            else (
                f"The disease signal is below the 0.60 confidence gate."
                if (has_disease and d_conf < 0.60)
                else (getattr(state.disease, "block_reason", "") or "Crop match")
            )
        ),
    }

    nearby_stores_data = []
    farm_lat = state.raw_inputs.get("lat")
    farm_lon = state.raw_inputs.get("lon")
    if farm_lat is not None and farm_lon is not None:
        try:
            store_res = find_nearby_stores(farm_lat, farm_lon)
            nearby_stores_data = store_res.get("stores", [])
            obs.log_agent_call(
                run_id=state.run_id,
                agent_name="store_locator",
                input_data={
                    "lat": farm_lat,
                    "lon": farm_lon,
                    "radius_km": store_res.get("radius_km"),
                    "location": state.raw_inputs.get("location_name") or "",
                },
                output_data={"count": store_res.get("count", 0), "provider": store_res.get("provider")},
                status="SUCCESS" if store_res.get("count", 0) > 0 else "NO_STORES_FOUND",
                confidence=1.0,
                latency_ms=store_res.get("latency_ms", 0.0),
                source=store_res.get("provider", "store_locator"),
            )
        except Exception:
            nearby_stores_data = []

    return {
        "run_id": state.run_id,
        "recommendation": state.final_recommendation,
        "agronomic_recommendation": getattr(state, "agronomic_recommendation", state.final_recommendation),
        "market_recommendation": getattr(state, "market_recommendation", getattr(state.market, "signal", "hold")),
        "farm_advisory": getattr(state, "farm_advisory", state.final_recommendation),
        "confidence": state.confidence,
        "explanation": explanation,
        "llm_explanation": llm_structured,
        "decision_stability_score": getattr(state, "decision_stability_score", 0.0),
        "stability_level": getattr(state, "stability_level", "INSUFFICIENT"),
        "evidence_quality_score": getattr(state, "evidence_quality_score", 0.0),
        "evidence_quality_level": getattr(state, "evidence_quality_level", "INSUFFICIENT"),
        "evidence_quality_breakdown": getattr(state, "evidence_quality_breakdown", {}) or {},
        "safety_constraints": getattr(state, "safety_constraints", []),
        "decision_change_triggers": getattr(state, "decision_change_triggers", []),
        "weather_risk": weather_risk_data,
        "soil_nutrient_status": soil_status_data,
        "disease_gate": disease_gate_data,
        "re_evaluation_trigger": getattr(state, "re_evaluation_trigger", ""),
        "supporting_evidence": getattr(state, "supporting_evidence", []),
        "conflicting_evidence": getattr(state, "conflicting_evidence", []),
        "resolved_conflicts": getattr(state, "resolved_conflicts", []),
        "required_additional_info": getattr(state, "required_additional_info", []),
        "decision_provenance": getattr(state, "decision_provenance", {}),
        "evidence_items": getattr(state, "evidence_items", []),
        "nearby_stores": nearby_stores_data,
        "location": {
            "location_name": state.raw_inputs.get("location_name") or "",
            "latitude": state.raw_inputs.get("lat"),
            "longitude": state.raw_inputs.get("lon"),
            "geocoding_source": state.raw_inputs.get("geocoding_source") or "unspecified",
            "geocoding_status": state.raw_inputs.get("geocoding_status") or "AVAILABLE",
        },
        "llm": {
            **llm_metadata,
            "provider": llm_result.provider,
            "model": llm_result.model,
            "role": "Explanation and evidence synthesis only",
            "decision_authority": "Deterministic Agronomic Safety Engine",
            "status": llm_result.status,
            "latency_ms": llm_result.latency_ms,
            "fallback_used": llm_result.fallback_used,
            "evidence_sources_count": len(evidence),
            "tokens": llm_result.tokens,
            "structured": llm_structured,
        },
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


@app.get("/")
def root():
    return {"status": "ok", "service": "agrimind-api", "version": "1.2.0"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "agrimind-api", "version": "1.1.0"}


@app.get("/api/crops")
def list_crops():
    """Standardized Crop Registry for searchable crop selection."""
    return {
        "categories": CATEGORIES,
        "crops": get_crop_registry(),
        "by_category": get_crops_by_category(),
        "stages": STAGE_REGISTRY,
    }


@app.get("/api/location/search")
def search_location(q: str = ""):
    """Search for locations via Open-Meteo Geocoding / regional registry."""
    if not q or not q.strip():
        return {"results": []}
    return {"results": search_locations(q.strip(), count=5)}


@app.get("/api/nearby-stores")
def get_nearby_stores(
    lat: float | None = None,
    lon: float | None = None,
    location: str | None = None,
    radius: float | None = None,
    category: str | None = None,
):
    """Discover verified agricultural input stores near resolved farm coordinates."""
    resolved_lat = lat
    resolved_lon = lon
    location_name = location or ""

    if (resolved_lat is None or resolved_lon is None) and location:
        geo = resolve_location(location)
        if geo.get("status") == "RESOLVED":
            resolved_lat = geo.get("latitude")
            resolved_lon = geo.get("longitude")
            location_name = geo.get("location_name", location)

    if resolved_lat is None or resolved_lon is None:
        raise HTTPException(
            status_code=422,
            detail="Valid coordinates (lat, lon) or resolvable location name must be provided.",
        )

    if not (-90.0 <= resolved_lat <= 90.0) or not (-180.0 <= resolved_lon <= 180.0):
        raise HTTPException(
            status_code=422,
            detail=f"Coordinates out of bounds: lat={resolved_lat}, lon={resolved_lon}. Valid bounds: lat [-90, 90], lon [-180, 180].",
        )

    try:
        result = find_nearby_stores(
            lat=resolved_lat,
            lon=resolved_lon,
            radius_km=radius,
            category=category,
        )
    except Exception as exc:
        try:
            obs.log_agent_call(
                run_id="nearby_stores_query",
                agent_name="store_locator",
                input_data={"lat": resolved_lat, "lon": resolved_lon, "radius_km": radius, "location": location_name},
                output_data={"error": str(exc)},
                status="UNAVAILABLE",
                confidence=0.0,
                latency_ms=0.0,
                source="store_locator",
            )
        except Exception:
            pass
        return {
            "status": "unavailable",
            "source": "none",
            "provider": "none",
            "message": "Store discovery is temporarily unavailable. The advisory remains valid.",
            "radius_km": radius or DEFAULT_SEARCH_RADIUS_KM,
            "count": 0,
            "stores": [],
        }

    try:
        obs.log_agent_call(
            run_id="nearby_stores_query",
            agent_name="store_locator",
            input_data={"lat": resolved_lat, "lon": resolved_lon, "radius_km": result.get("radius_km"), "location": location_name},
            output_data={"count": result.get("count", 0), "provider": result.get("provider")},
            status="SUCCESS" if result.get("count", 0) > 0 else "NO_STORES_FOUND",
            confidence=1.0,
            latency_ms=result.get("latency_ms", 0.0),
            source=result.get("provider", "store_locator"),
        )
    except Exception:
        pass

    return {
        **result,
        "location": {
            "location_name": location_name,
            "latitude": resolved_lat,
            "longitude": resolved_lon,
        },
    }


@app.post("/api/advisory")
def advisory(payload: AdvisoryRequest):
    # Validate location when location_name is submitted
    if payload.location_name is not None and not payload.location_name.strip():
        raise HTTPException(status_code=422, detail="Farm location name cannot be empty.")
    if payload.location_name and payload.lat is None:
        geo = resolve_location(payload.location_name)
        if geo.get("status") in ("INVALID", "NOT_FOUND", "ERROR"):
            raise HTTPException(
                status_code=422,
                detail=geo.get("error") or f"Unable to resolve location '{payload.location_name}'.",
            )

    try:
        return _serialize(run_advisory(payload.model_dump()))
    except HTTPException:
        raise
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
    crop: str = Form("Tomato"),
    growth_stage: str = Form("vegetative"),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    location_name: str | None = Form(None),
    n: float | None = Form(None),
    p: float | None = Form(None),
    k: float | None = Form(None),
    current_price: float = Form(0, ge=0),
    price_history: str = Form(""),
    soil_type: str = Form(""),
    soil_mode: str = Form(""),
    farm_area: float | None = Form(None),
    irrigation_method: str = Form(""),
    image: UploadFile | None = File(None),
):
    if image is None:
        raise HTTPException(status_code=400, detail="A crop leaf image is required.")

    # Validate location
    if location_name is not None and not location_name.strip() and lat is None:
        raise HTTPException(status_code=422, detail="Farm location cannot be empty.")
    if location_name and lat is None:
        geo = resolve_location(location_name)
        if geo.get("status") in ("INVALID", "NOT_FOUND", "ERROR"):
            raise HTTPException(status_code=422, detail=geo.get("error") or f"Unable to resolve location '{location_name}'.")

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
            lat=lat,
            lon=lon,
            location_name=location_name,
            crop=crop[:100],
            growth_stage=growth_stage[:100],
            n=n,
            p=p,
            k=k,
            current_price=current_price,
            price_history=history,
            soil_type=soil_type[:100],
            soil_mode=soil_mode[:50] if soil_mode else None,
            farm_area=farm_area,
            irrigation_method=irrigation_method[:100] if irrigation_method else None,
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

