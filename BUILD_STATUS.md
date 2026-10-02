# AgriMind Build Status

## Batch 1 — Correctness, tests, API hardening
Status: **VERIFIED**

- Deterministic P1–P5 decision hierarchy retained.
- P5 market tie-breaker is observable as a Stage-2 non-override conflict.
- Final confidence follows the selected action score in Stage 2.
- Public advisory input rejects arbitrary fields.
- Leaf-image upload validates MIME type, extension, size, and image contents.
- Temporary uploaded images are removed after processing.
- Local verification: product checks pass.
- Local automated verification: **19 tests passed** in the Batch 1 acceptance run.

## Batch 2 — RAG and ICAR evidence quality
Status: **VERIFIED**

- ICAR PDF ingestion preserves useful page/chunk boundaries.
- Extracted text is cleaned of control characters and whitespace artifacts.
- Each chunk receives conservative crop/topic/disease/region metadata plus source page.
- Disease metadata uses an explicit controlled vocabulary rather than noisy regex phrases.
- Local retrieval uses TF-IDF candidate generation plus metadata-aware reranking.
- When tagged material exists, supplied crop context constrains local retrieval so generic passages do not dominate.
- Disease/topic context receives additional relevance weighting.
- Duplicate evidence text is removed from final results.
- API retrieval uses crop, growth stage, predicted disease, and recommendation context.
- Ingestion replaces the local JSON corpus to prevent stale chunks from older extraction runs.
- RAG evidence remains explanatory context and cannot override the deterministic decision policy.

Verification after Batch 2:

- `python -m pytest -q` → **22 passed, 1 skipped**
- `python scripts/verify_product.py` → **PASS**
- `python -m compileall -q .` → **PASS**
- Live FastAPI advisory smoke test → **HTTP 200** with 4 tomato/early-blight-focused ICAR evidence records.

Known non-blocking warnings:

- FastAPI `on_event` startup API is deprecated and can be migrated to lifespan in a later cleanup batch.

## LLM Explanation Layer — VERIFIED

- xAI/Grok is the primary optional explanation provider.
- Optional Groq and Gemini providers can be used as ordered fallbacks.
- The deterministic policy remains authoritative; LLM output cannot change the selected action.
- `.env` is loaded automatically at API startup.
- LLM calls use bounded retries and configurable timeout.
- A small process-local cache avoids repeated identical explanation calls.
- Each LLM/fallback result is persisted as `llm_explainer` in `agent_logs` with provider, model, status, latency, fallback, cache-hit and error metadata.
- API responses expose the latest LLM metadata under `llm`.
- `/api/runs/{run_id}` returns 404 for an unknown run.
## Comprehensive System Repair Batch — VERIFIED

- **Optional Image Support**: Case A (image provided), Case B (override provided), Case C (text/data-only query) all fully operational without crashing.
- **Weather Failure Safety**: External API failure or missing coordinates sets `is_available=False` and neutral 0.50 suitability in scoring rather than falsely maximizing fertilizer suitability.
- **Soil Agent Calibration**: Crop-specific NPK reference targets (Tomato, Potato, Rice, Maize, Legumes, etc.) and soil-type adjustments (Sandy, Clay, Loam, Alluvial) transparently qualified as project calibration heuristics and engineering baselines with explicit provenance tracking, distinguishing heuristics from authoritative local guidance.
- **Market Agent Integration**: Wired `data_sources.market.fetch_prices` into the agent; handles missing market data gracefully without fabricating prices; real confidence and availability flags exposed.
- **RAG Disease Label Normalization**: PlantVillage raw labels (e.g. `Tomato___Early_blight`) are normalized to clean crop and disease terms, doubling retrieval score and evidence relevance.
- **Observability Enhancement**: Added `runs` table to record run-level metadata (`crop`, `growth_stage`, `soil_type`, `recommendation`, `confidence`, `status`, `timestamp`) and added LLM token usage tracking.
- **Frontend Repair**: Installed Next.js dependencies (`npm install`), verified `npm run build` succeeds, fixed market confidence display, fixed `Pnull` priority rendering, and added a field feedback reporting UI for `/api/feedback`.
- **CORS Hardening**: Changed default wildcard CORS to local web clients (`http://localhost:3000,http://127.0.0.1:3000`).
- **Test Suite Expanded**: **49 automated tests passing** (up from 28). All 12 end-to-end scenarios fully verified.
