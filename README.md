# AgriMind

**Observable multi-agent orchestration system for intelligent crop advisory.**

## 1. Project Purpose

AgriMind is a multi-agent agronomic advisory platform designed to deliver safe, transparent, auditable, and scientifically calibrated crop guidance to farmers and agricultural extension officers. It resolves the core flaw of purely generative agricultural AI—hallucinations and ungrounded advice—by decoupling decision computation from explanation:

- **Deterministic Core**: Agronomic actions, fertilizer adjustments, disease treatments, and weather safety policies are calculated via deterministic rules and validated scoring functions. LLMs never select or override agronomic decisions.
- **Explainability**: LLMs (or deterministic fallback templates) translate structured agent findings and ICAR (Indian Council of Agricultural Research) evidence into clear, localized explanations.
- **Traceability & Provenance**: Every output is linked to an auditable run ID capturing agent states, confidence levels, data source availability, heuristic/authoritative tags, and conflict resolutions.

---

## 2. System Architecture

The pipeline processes user context through five specialized agents, resolves conflicts via a multi-stage deterministic engine, retrieves ICAR grounding, generates an auditable advisory, and logs the execution to an observability store:

```text
Farmer Context + Optional Image / Soil Nutrients
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    Weather Agent           Soil Agent
 (Open-Meteo API / Safe)  (NPK & Soil Texture)
         │                       │
         └───────────┬───────────┘
                     ▼
               Disease Agent
        (MobileNetV3 / Override / Text)
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
   Market Agent            Advisory Agent
(Agmarknet / Fallback) (Nutrient Requirements)
         │                       │
         └───────────┬───────────┘
                     ▼
       Deterministic Decision Engine
     (Safety Policies P1–P5 + Scoring)
                     │
                     ▼
          ICAR Knowledge RAG
     (Official 2025 Kharif Advisories)
                     │
                     ▼
           LLM Explanation Layer
      (Grok / Groq / Gemini / Template)
                     │
                     ▼
       Auditable Response + Web UI
    (Run-level trace in SQLite/Postgres)
```

---

## 3. Installation

Prerequisites:
- Python 3.10+ (tested on Python 3.11/3.12)
- Node.js 18+ and npm
- SQLite3 (default local database)

```bash
# Clone and enter directory
cd agrimind_batch1

# Python virtual environment
python -m venv .venv
# Activate virtual environment (Windows PowerShell: .venv\Scripts\Activate.ps1)
# Activate virtual environment (Linux/macOS: source .venv/bin/activate)

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd web
npm ci
cd ..
```

---

## 4. Environment Variables

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Key environment configuration:
- `DATABASE_URL`: SQLAlchemy connection string (default: `sqlite:///agrimind_local.db`).
- `OPEN_METEO_BASE_URL`: Forecast endpoint (default: `https://api.open-meteo.com/v1/forecast`).
- `AGMARKNET_BASE_URL`: Agmarknet API endpoint. If empty, market agent safely runs in `DEMO_DATA` / `UNAVAILABLE` fallback mode.
- `DISEASE_MODEL_PATH`: PyTorch model weights path (default: `ml/artifacts/best.pt`).
- `CORS_ORIGINS`: Allowed origins list (default: `http://localhost:3000,http://127.0.0.1:3000`).
- `XAI_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`: Optional provider keys for natural language explanations.
- `LLM_PROVIDER_ORDER`: Fallback sequence (default: `xai,groq,gemini`).

---

## 5. Running the Backend

Start the FastAPI application:

```bash
uvicorn api.main:app --reload --port 8000
```

FastAPI OpenAPI documentation will be available at `http://localhost:8000/docs`.

---

## 6. Running the Frontend

The interactive user interface is built with Next.js:

```bash
cd web
npm run dev
```

Visit `http://localhost:3000` to interact with the advisory portal.

For production builds:
```bash
npm run build
```

---

## 7. Running Tests

Run the complete test suite without requiring paid API keys or live external connections:

```bash
# Complete pytest suite (68 tests across unit, integration, and E2E scenarios)
python -m pytest -v

# Verification script
python scripts/verify_product.py

# Syntax and compilation check
python -m compileall -q .
```

---

## 8. Free & Offline Demo Mode

AgriMind runs completely offline without requiring any paid subscriptions:
- **No LLM API keys needed**: When LLM keys are absent, the system produces structured deterministic explanations without failing or compromising safety.
- **Weather API failures / offline**: If Open-Meteo is unreachable or coordinates are invalid, the weather agent transitions to an explicit safe state (`UNAVAILABLE`, `TIMEOUT`, `INVALID`) and sets a neutral 0.50 score, preventing false fertilizer recommendations.
- **Market API offline**: If Agmarknet is unreachable or unconfigured, the system explicitly labels the state as `DEMO_DATA` or `UNAVAILABLE` and emits a neutral hold signal, preventing fake data from being presented as live mandi prices.

---

## 9. Advisory Workflow & Safety Policies

Advisory decisions follow a strict, non-negotiable 2-stage hierarchy:

### Stage 1: Deterministic Safety Gates (Rules)
1. **P1 Weather Safety**: Rainfall probability > 70% triggers `DELAY` to prevent fertilizer runoff and chemical leaching.
2. **P2 Disease Confidence Gate**: Disease predictions with confidence < 0.60 are marked non-actionable; advisory continues with general crop health.
3. **P3 Disease Urgency**: Actionable disease with high severity forces `DISEASE_MANAGEMENT_FIRST`.
4. **P4 Nutrient Requirement**: Severe soil nutrient deficiency (> 60%) triggers `apply_fertilizer`.
5. **P5 Market Condition**: Market economic signal acts strictly as a Stage-2 tie-breaker and cannot override agronomic safety.

### Stage 2: Multi-Criteria Decision Scoring
When multiple actions are plausible, actions are scored on agronomic suitability, weather compatibility, and economic indicators. The highest scoring valid action is selected.

---

## 10. Observability & Run-Level Traceability

Every advisory execution is assigned a unique `run_id` (UUIDv4) and recorded across five relational tables:
- `runs`: Top-level execution trace (run ID, crop, growth stage, soil type, recommendation, confidence, latencies, LLM token counts, weather/market/disease statuses).
- `agent_logs`: Input, output, status, and latency of every individual agent.
- `decisions`: Deterministic rule evaluations, candidates, and scoring breakdowns.
- `conflicts`: Detected multi-agent conflicts, resolution policies, and chosen winners.
- `feedback`: End-user field accuracy ratings and notes.

### Run Trace Endpoint
Inspect the complete 9-point execution trail for any advisory run:
```bash
curl http://localhost:8000/api/runs/{run_id}
```
Returns:
1. `run_id` and timestamp
2. `agents_executed` (statuses, latencies)
3. `agent_outputs` summary
4. `data_source_availability` (weather, market statuses)
5. `conflicts` and resolutions
6. `decision_rule` and score breakdown
7. `llm_used` (provider, status, token usage)
8. `final_recommendation` and confidence
9. `uncertainty` notes and warnings

---

## 11. Disease Pipeline

The disease model utilizes a MobileNetV3-Large neural network trained on the PlantVillage dataset:
- **Mode A (Image Provided)**: Validates image (JPEG/PNG, <= 10MB), runs inference, normalizes class labels (e.g., `Tomato___Early_blight` → Tomato Early Blight), applies confidence thresholding (0.60 gate).
- **Mode B (Disease Override)**: Respects user-specified diagnosis without running redundant model inference.
- **Mode C (Data Only)**: Fully operational when no image is provided; marks disease state as unknown/non-actionable without crashing.
- **Severity Qualification**: PlantVillage labels lack severity annotations; all disease severity metrics are explicitly identified as heuristics.

---

## 12. RAG & ICAR Evidence Grounding

AgriMind ingests official ICAR Kharif Agro-Advisories (2025):
- Preserves exact source document and page number boundaries.
- Contextual query generation blends crop, growth stage, soil, and diagnosed condition.
- TF-IDF candidate generation with metadata-aware reranking ensures that only relevant recommendations are retrieved.
- RAG evidence provides scientific grounding for explanations and cannot override safety gates.

---

## 13. Soil Calibration & Provenance

Crop nutrient reference targets (Tomato, Potato, Rice, Maize, etc.) and soil texture adjustments (Sandy, Clay, Loam, Alluvial) are explicitly categorized:
- `AUTHORITATIVE`: Direct, verified recommendations.
- `HEURISTIC`: Calibrated engineering baseline heuristics.
- `FALLBACK`: Generic crop nutritional benchmarks.

`get_provenance(crop, soil_type)` returns full metadata.

> **Field Application Note**: Actual field fertilizer application should always be cross-referenced with State Agricultural University (SAU) Package of Practices, district Krishi Vigyan Kendra (KVK) guidance, or the farmer's Soil Health Card.

---

## 14. Market & Weather Data Limitations

- **Weather**: Integrated with Open-Meteo. Does not fabricate forecast data when offline or unavailable. Missing precipitation data is explicitly flagged rather than treated as zero rainfall.
- **Market (Agmarknet)**: If the Agmarknet API is unconfigured or returns an empty result, market status is marked as `DEMO_DATA` or `UNAVAILABLE`. Prices are never fabricated.

---

## 15. Deployment & Production Notes

- **Docker Support**: Preconfigured `Dockerfile` and `docker-compose.yml` for containerized backend and database deployment.
- **Database Migrations**: Additive SQLite/PostgreSQL schema initialization via `init_db()` preserves all existing rows and tables across updates.
- **Security**: CORS is restricted to local/whitelisted origins, uploads are validated for file size (10MB limit), magic byte signatures, and path traversal vulnerabilities.
- **Clean API Contract**:
  - `GET /health`: System health and version status.
  - `POST /api/advisory`: JSON advisory calculation.
  - `POST /api/advisory/upload`: Multipart form advisory with leaf image.
  - `GET /api/runs/{run_id}`: Comprehensive execution audit trail.
  - `POST /api/feedback`: Farmer feedback and rating submission.
