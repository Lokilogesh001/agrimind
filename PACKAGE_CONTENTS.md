# AgriMind Core Package — Manifest & Runtime Contents

This archive (`AgriMind_Core_Modules.zip`) contains the complete runnable core source code, dependency manifests, configuration templates, frontend source, required runtime assets, and startup scripts for **AgriMind: Autonomous Multi-Agent Agricultural Intelligence Platform**.

---

## 1. Package Contents Overview

### Application Source Code
- `agents/` — Autonomous specialist agents (`weather_agent.py`, `soil_agent.py`, `disease_agent.py`, `advisory_agent.py`, `market_agent.py`).
- `api/` — FastAPI REST API service with CORS, request validation, image security checks, store discovery, and telemetry (`main.py`).
- `data_sources/` — Live data integrations and fallbacks:
  - `crops.py`: 12-crop agronomic taxonomy, phenological growth stages, and stage registry.
  - `geocoding.py`: Open-Meteo forward geocoding with local centroid fallback.
  - `weather.py`: Open-Meteo precipitation/temperature client with disk/memory caching.
  - `soil.py`: NPK balance assessment and stoichiometric nutrient requirement models.
  - `market.py`: Agmarknet market spot price and modal arrival trend analyzer.
  - `stores.py`: OpenStreetMap Overpass API nearby verified agricultural store locator.
  - `treatments.py`: Safe chemical, biological, and cultural treatment database.
- `decision/` — Two-stage deterministic agronomic decision engine:
  - `evidence_engine.py`: Evidence collector, Decision Stability Score (DSS) calculator, and conflict detector.
  - `evidence_quality.py`: Multi-factor Evidence Quality Score (EQS) breakdown.
  - `safety_guard.py`: Six deterministic agronomic safety rules (Rules A–F) and decision change triggers.
  - `scoring.py`: Stage 2 weighted multi-criteria scoring algorithm.
  - `rules.py` & `models.py`: Agronomic thresholds, conflict specifications, and schemas.
- `llm/` — Source-grounded explanation layer:
  - `explainer.py`: Multi-provider failover chain (OpenAI `gpt-4o-mini` $\to$ xAI `grok-2-latest` $\to$ Deterministic Template).
  - `config.py`: Sanitized configuration loader and key safety masking.
- `ml/` — Crop disease computer vision modules:
  - `dinov2_adapter.py`: Production champion DINOv2-Small + Rank-4 LoRA model adapter with crop constraints, confidence gating, and ambiguity detection.
  - `disease_model.py`: MobileNetV3-Large rollback predictor with test-time augmentations.
  - `model_registry.py`: Central registry and fallback resolver for registered vision models.
  - `plantvillage_dataset.py`: 38-class PlantVillage + Field taxonomy mapping.
  - `train_disease.py` & `train_field_finetune.py`: Training and fine-tuning pipelines.
  - `artifacts/dinov2_lora_r4_b4_best.pt`: Champion LoRA checkpoint (88.48 MB, 88,480,982 bytes, SHA-256: `8ae555c2...`).
  - `artifacts/MODEL_MANIFEST.json` & `artifacts/MODELS_README.md`: Checkpoint specifications, SHA-256 hashes, and setup guide.
- `observability/` — Telemetry and audit trails:
  - `database.py`: SQLAlchemy session manager, SQLite local file storage, and Supabase PostgreSQL support.
  - `schema.sql`: Canonical DDL for `agent_logs`, `decisions`, `conflicts`, `feedback`, and `runs`.
- `orchestrator/` — Multi-agent workflow orchestrator:
  - `graph.py`: Directed acyclic execution graph, parallel agent invocation, and conflict arbitration.
  - `state.py`: Typed immutable blackboard state container.
- `rag/` — Retrieval-Augmented Generation agronomic knowledge engine:
  - `retriever.py`: Hybrid BM25 keyword matching with regional agroclimatic zone reranking and source citation formatting.
  - `metadata.py`: ICAR chunk metadata schema and region tagging.
  - `icar_ingest.py`: PDF document processing and chunk generator.
- `knowledge/` — Runtime knowledge corpus:
  - `icar_chunks.json`: Pre-chunked, indexed ICAR Kharif Agro-Advisories corpus (2.36 MB) required for runtime RAG evidence retrieval.
- `web/` — Next.js 16 modern responsive farmer-facing dashboard:
  - `app/page.tsx`: Reactive single-page dashboard with real-time advisory streaming.
  - `app/layout.tsx` & `app/globals.css`: Modern visual styling with glassmorphism, fluid typography, dark mode, and accessibility tokens.
  - `app/components/`: 19 modular React 19 components including `FarmInputForm.tsx`, `AdvisoryHero.tsx`, `DiseaseActionCard.tsx`, `NearbyStoresCard.tsx`, `AuditPanel.tsx`, `ActionPlan.tsx`, etc.
  - `package.json`, `package-lock.json`, `tsconfig.json`, `next.config.ts`: Frontend build and type-checking configuration.
- Runtime Scripts & Root Configuration:
  - `main.py`: Command-line end-to-end verification script demonstrating 3 multi-agent agronomic scenarios.
  - `start.ps1`: Automated cross-platform Windows PowerShell startup script.
  - `start.sh`: Automated Linux/macOS Bash startup script.
  - `requirements.txt`: Python package manifest with pinned runtime dependencies.
  - `.env.example`: Environment variable template with safe defaults.
  - `.gitignore`: Clean ignore rules for virtual environments, caches, build output, and databases.
  - `Dockerfile` & `docker-compose.yml`: Containerized production deployment configuration.
  - `AgriMind_Complete_Documentation.md`: Complete 21-section single-file documentation.

---

## 2. Deliberately Excluded Items

To guarantee a clean, leak-free, and lightweight package, the following files and directories are explicitly excluded:
- Virtual environments: `.venv/`, `venv/`, `env/`.
- Package managers and build output: `node_modules/`, `web/.next/`, `web/tsconfig.tsbuildinfo`.
- Python caches: `__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/`, `.ruff_cache/`.
- Local test suites: `tests/` (unit and integration tests intended for development).
- Local runtime databases: `agrimind_local.db` (created automatically on first boot via `init_db()`).
- Secrets and environment overrides: Local `.env` files containing user API keys or local settings.
- Raw training and evaluation image datasets: `evaluation/datasets/` (several gigabytes of raw training photos).
- Research experiment runs and intermediate checkpoints: `ml/research/` (hundreds of megabytes of feature caches, optuna trials, and temporary weights).
- Ingestion-time raw PDF: `knowledge/ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf` (17.8 MB raw document; the extracted runtime JSON `knowledge/icar_chunks.json` is included).
- Git repository metadata: `.git/`, `.github/`.
- Rollback MobileNetV3 checkpoint: `ml/artifacts/best.pt` (17.2 MB baseline; instructions provided in `ml/artifacts/MODELS_README.md` if rollback is needed).

---

## 3. External Model & Data Asset Requirements

AgriMind is architected with graceful fallback behavior, but full multimodal functionality requires the following external assets:

1. **DINOv2-Small Backbone Weights (`facebook/dinov2-small`):**
   - The LoRA adapter checkpoint (`ml/artifacts/dinov2_lora_r4_b4_best.pt`, 88.48 MB, 88,480,982 bytes) **is included** in this archive.
   - On the first leaf image diagnostic query, Hugging Face `transformers` downloads the base ViT backbone (~85 MB) and caches it in `~/.cache/huggingface/hub`.
   - In air-gapped environments, copy this cache from a connected machine and set `HF_HUB_OFFLINE=1`.
2. **MobileNetV3 Rollback Checkpoint (`ml/artifacts/best.pt` - Optional):**
   - Only required if you explicitly switch `DISEASE_MODEL_BACKBONE=production`. If missing, the model registry gracefully flags MobileNetV3 as `UNAVAILABLE` while the default DINOv2 LoRA operates normally.
3. **Open-Meteo Weather & Geocoding APIs:**
   - Free, public endpoints requiring no API keys (`https://api.open-meteo.com` and `https://geocoding-api.open-meteo.com`). If offline or rate-limited, local agroclimatic centroid fallbacks automatically activate.
4. **LLM Provider API Key (Optional):**
   - `OPENAI_API_KEY` (or `XAI_API_KEY`). If omitted, AgriMind's built-in **Deterministic Template Explainer** generates complete, agronomic explanations with zero network dependency.
5. **Agmarknet Mandi API (Optional):**
   - If `AGMARKNET_BASE_URL` is omitted, realistic historical modal price curves and MSP price floors are applied automatically.

---

## 4. Quick Start & Execution

### Windows (PowerShell)
```powershell
# Automated single-command startup (creates .venv, installs dependencies, launches backend & frontend)
.\start.ps1
```

### Linux / macOS (Bash)
```bash
# Make script executable and run
chmod +x start.sh
./start.sh
```

### Manual Installation

#### Backend
```bash
python -m venv .venv
# Activate venv:
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend
```bash
cd web
npm install
npm run dev
```

Visit the dashboard at `http://localhost:3000` and API documentation at `http://localhost:8000/docs`.

---

## 5. Verification Checklist

- [x] Backend runs headless verification scenario: `python main.py`
- [x] REST API readiness endpoint: `GET http://localhost:8000/health`
- [x] Disease model health check: `GET http://localhost:8000/health/model`
- [x] Next.js frontend builds without type errors: `cd web && npm run typecheck`
