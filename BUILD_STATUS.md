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
## Comprehensive System Repair Batch — VERIFIED (v1.0-verified Baseline)

- **Frozen Baseline Tag**: `v1.0-verified` (Commit: `11f1925`)
- **Optional Image Support**: Case A (image provided), Case B (override provided), Case C (text/data-only query) all fully operational without crashing.
- **Weather Failure Safety**: External API failure or missing coordinates sets `is_available=False` and neutral 0.50 suitability in scoring rather than falsely maximizing fertilizer suitability.
- **Soil Agent Calibration**: Crop-specific NPK reference targets (Tomato, Potato, Rice, Maize, Legumes, etc.) and soil-type adjustments (Sandy, Clay, Loam, Alluvial) transparently qualified as project calibration heuristics and engineering baselines with explicit provenance tracking, distinguishing heuristics from authoritative local guidance.
- **Market Agent Integration**: Wired `data_sources.market.fetch_prices` into the agent; handles missing market data gracefully without fabricating prices; real confidence and availability flags exposed.
- **RAG Disease Label Normalization**: PlantVillage raw labels (e.g. `Tomato___Early_blight`) are normalized to clean crop and disease terms, doubling retrieval score and evidence relevance.
- **Observability Enhancement**: Added `runs` table to record run-level metadata (`crop`, `growth_stage`, `soil_type`, `recommendation`, `confidence`, `status`, `timestamp`) and added LLM token usage tracking.
- **Frontend Repair**: Installed Next.js dependencies (`npm install`), verified `npm run build` succeeds, fixed market confidence display, fixed `Pnull` priority rendering, and added a field feedback reporting UI for `/api/feedback`.
- **CORS Hardening**: Changed default wildcard CORS to local web clients (`http://localhost:3000,http://127.0.0.1:3000`).
- **Test Suite Expanded**: **49 automated tests passing**. All 12 end-to-end scenarios fully verified.

---

## v1.1 Demo-Ready Baseline — VERIFIED

Status: **VERIFIED**
Branch: `v1.1-demo-ready`
Baseline Tag Preserved: `v1.0-verified` (`11f1925`)

### Hardening & Additions in v1.1:
1. **Weather Agent Hardening**:
   - Explicit status enumeration: `AVAILABLE`, `UNAVAILABLE`, `INVALID`, `TIMEOUT`.
   - `fetch_forecast` handles timeouts, malformed JSON, and missing precipitation arrays gracefully.
   - Neutral 0.50 weather suitability in deterministic scoring whenever weather is non-AVAILABLE or failed.
   - Weather failure never increases fertilizer recommendation suitability.
2. **Market Adapter & Agent Transparency**:
   - Explicit status enumeration: `REAL_DATA`, `DEMO_DATA`, `UNAVAILABLE`.
   - Real Agmarknet responses tagged `source="agmarknet_api"` and `status="REAL_DATA"`.
   - Missing/unconfigured Agmarknet data emits `signal="hold"` with `confidence=0.0` and `status="DEMO_DATA"` or `UNAVAILABLE`. Zero fabricated live mandi prices.
3. **Soil Calibration & Provenance**:
   - Preserves authoritative qualification: field fertilizer application must be cross-referenced with SAU Package of Practices, KVK guidance, or Soil Health Card.
   - `get_provenance(crop, soil_type)` returns explicit source categorization (`AUTHORITATIVE`, `HEURISTIC`, `FALLBACK`).
4. **Disease Pipeline Multi-Mode Safety**:
   - Mode A (image provided): validates MIME/size (10MB limit), runs inference, normalizes class names, enforces 0.60 confidence gate.
   - Mode B (override provided): direct evaluation without unnecessary model execution.
   - Mode C (no image / override): safe neutral state without crashing.
   - Disease severity explicitly flagged as heuristic.
5. **Observability & Audit Trail**:
   - Additive SQLite/PostgreSQL schema upgrade in `init_db()`: added `completed_at`, `total_latency_ms`, `weather_status`, `market_status`, `disease_status`, `llm_provider`, `llm_status`, `prompt_tokens`, `completion_tokens` to `runs` table without dropping or corrupting existing tables.
   - `GET /api/runs/{run_id}` delivers a comprehensive 9-point execution trace including agent statuses, latencies, conflicts, deterministic decision rule breakdown, LLM usage, and uncertainty notes.
   - Associated farmer feedback records are returned with the run trace.
6. **Security Hardening**:
   - Strict multipart upload validation: rejects files > 10MB (HTTP 413), unsupported MIME types (HTTP 415), and malformed payloads (HTTP 400).
   - Sanitized filenames prevents directory traversal. Temporary files deleted immediately in a `finally` block.
   - Safe CORS whitelist; no credentials, secrets, or API keys in code or logs.
7. **Frontend Alignment**:
   - Displays weather status badges (`[AVAILABLE]`, `[TIMEOUT]`, `[UNAVAILABLE]`, `[INVALID]`).
   - Displays market status badges (`[REAL_DATA]`, `[DEMO_DATA]`, `[UNAVAILABLE]`).
   - Displays soil provenance tags and disease heuristic severity qualifiers.
   - Clean farmer feedback submission dialog.
   - Zero broken properties (`Pnull`, `NaN`, etc.).
8. **Verification & Test Suite**:
   - Python Tests: **68 passed / 0 failed** (49 baseline + 19 v1.1 hardening tests).
   - E2E Scenarios: **18/18 passed** (12 baseline + 6 new v1.1 scenarios: run trace retrieval, feedback submission, market unavailable, malformed weather response, demo mode, no external keys).
   - Frontend Build: `npm run build` succeeds cleanly (`✓ Compiled successfully`).
   - Product Verification Script: `python scripts/verify_product.py` passes all 4 checks.
   - Zero hardcoded secrets detected.
