# AgriMind Phase 1 & Phase 2 Technical Audit

## 1. Executive Summary

This audit documents the baseline assessment, root cause analysis, architecture hardening, and verification results for AgriMind Phase 1 (Correctness & Safety) and Phase 2 (Agent Contracts & Decision Reliability).

AgriMind is an observable, multi-agent agricultural advisory platform. Its authoritative agronomic decision core is deterministic, while LLMs operate strictly as non-authoritative explanation synthesizers.

---

## 2. Baseline Findings & Root Causes

### 2.1 Public API Override Vulnerability
- **Finding:** The public `POST /api/advisory` endpoint accepted `weather_override` and `disease_override` dictionaries directly in `AdvisoryRequest` with no environment checks.
- **Root Cause:** Overrides were originally introduced for rapid testing without distinguishing public versus internal testing request contracts. In production, this would allow client-side requests to fabricate weather observations or inject false disease diagnoses.
- **Fix:**
  - Restructured schemas into `BaseAdvisoryRequest`, public `AdvisoryRequest`, and `InternalAdvisoryRequest`.
  - Added strict override validation in `AdvisoryRequest`: unconditionally forbidden when `ENVIRONMENT=production`, and rejected by default in development unless `ALLOW_TEST_OVERRIDES=true`.
  - Added a dedicated internal testing endpoint `POST /api/internal/test-advisory`, which is blocked in production (`403 Forbidden`).

### 2.2 Disease Model Artifact Verification & Failure Handling
- **Finding:** Prior reports questioned the presence of `ml/artifacts/best.pt`.
- **Inspection & Verification:**
  - Checkpoint `ml/artifacts/best.pt` was inspected and verified using PyTorch. It is an authentic 17.2 MB MobileNetV3-Large checkpoint trained on 38 PlantVillage classes with 312 weight tensors.
  - However, previously, if the checkpoint was deleted, corrupted, or an invalid image uploaded, the error paths could cause unhandled exceptions or permit disease treatments without diagnosis.
- **Fix:**
  - Hardened `ml/disease_model.py`: added pre-inference validation for file size (10 MB cap), dimension checks (minimum 32x32), aspect ratio bounds, and PIL corruption checks.
  - Added `get_model_health()` returning structured health metadata (`READY`, `MISSING_CHECKPOINT`, `INVALID_CHECKPOINT`).
  - Added `GET /health/model` endpoint.
  - Updated `agents/disease_agent.py` to return structured `MODEL_UNAVAILABLE` or `INVALID_IMAGE` statuses.
  - Updated `data_sources/treatments.py` to block chemical spray recommendations (`DEFERRED_MODEL_UNAVAILABLE`, `DEFERRED_INVALID_IMAGE`) so unverified diagnosis cannot be treated as healthy foliage.

### 2.3 Resilient Multi-Provider LLM Fallback Chain
- **Finding:** Single-provider LLM integrations were prone to unhandled timeouts, rate-limit cascades, and credential leakage in logs.
- **Fix:**
  - Implemented resilient fallback chain: `OpenAI (gpt-4o-mini)` → `xAI Grok (grok-2-latest via https://api.x.ai/v1)` → `Deterministic Template Fallback`.
  - Created centralized configuration loader `llm/config.py` respecting `OPENAI_TIMEOUT_SECONDS=30`, `LLM_TIMEOUT_SECONDS=30`, `LLM_MAX_RETRIES=1`, and bounded exponential backoff.
  - Sanitized log outputs with `_sanitize_log_text()` to prevent API keys from appearing in logs or database records.
  - Guaranteed absolute decision immutability: the deterministic decision engine output can never be overridden by LLM explanatory text.

### 2.4 Agent Contract Standardization
- **Finding:** Specialist agents returned disparate dataclasses with inconsistent status semantics (`is_available`, strings, or booleans).
- **Fix:**
  - Created `AgentStatus` enum (`SUCCESS`, `PARTIAL`, `UNAVAILABLE`, `FAILED`, `SKIPPED`, `OVERRIDE`) in `orchestrator/state.py`.
  - Standardized `AgentResult` base dataclass containing `agent_name`, `status`, `input_summary`, `findings`, `evidence`, `confidence`, `warnings`, `error_code`, `execution_time_ms`, and `source_metadata`.
  - Retained 100% backward compatibility for all specialist result classes (`WeatherResult`, `SoilResult`, `DiseaseResult`, `AdvisoryResult`, `MarketResult`).
  - Orchestrator graph nodes populate execution timings and input summaries and validate outputs.

---

## 3. Safety Guard Precedence (Rules A through F)

Authoritative agronomic decisions follow a strict, deterministic hierarchy:

| Priority | Rule | Name | Precedence & Action |
|:---:|:---:|:---|:---|
| **P1** | **Rule D** | Weather Safety Veto | Rainfall risk > 0.70 unconditionally vetoes chemical sprays and fertilizer broadcasting; enforces `DELAY`. |
| **P2** | **Rule B** | Disease Confidence Gate | Disease confidence < 0.60, missing checkpoint (`MODEL_UNAVAILABLE`), or invalid image blocks disease treatment; enforces non-chemical monitoring. |
| **P3** | **Rule C** | Crop Mismatch Guard | Selected crop vs. predicted foliar class mismatch blocks disease action; enforces `RESTRICTED_CROP_MISMATCH`. |
| **P4** | **Rule A** | Soil Evidence Guard | Unmeasured NPK blocks exact fertilizer dosage; enforces soil testing advisory. |
| **P5** | **Rule E** | Data Freshness Guard | Stale, offline, or timed-out weather/disease telemetry applies confidence penalties. |
| **P6** | **Rule F** | Market vs. Agronomy | Market sell signals cannot override agronomic safety or harvest maturity constraints. |

---

## 4. Verification Summary

- **Backend Pytest Suites:**
  - `tests/test_phase1_phase2_comprehensive.py`: 18/18 passed (100%).
  - `tests/test_llm_provider_chain.py`: 18/18 passed (100%).
  - `tests/test_repair_batch.py`: 21/21 passed (100%).
  - `tests/test_audit_remediation.py`: 11/11 passed (100%).
  - `tests/test_v11_hardening.py`: 21/21 passed (100%).
  - `tests/test_adaptive_evidence_novelty.py`: 26/26 passed (100%).
  - Core unit test batch (API hardening, wiring, observability, stores, orchestrator, refactor): 45/45 passed (100%).
- **Frontend Turbopack Build:** Next.js 16.3.4 compiled cleanly with 0 TypeScript errors.
