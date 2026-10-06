# AgriMind — Testing & Verification Guide

AgriMind maintains a rigorous, multi-tiered testing suite covering deterministic decision safety, API contract integrity, ML inference validation, ICAR RAG retrieval precision, and end-to-end multi-agent orchestration.

---

## 1. Test Architecture & Commands

| Level | Command | Scope | Target |
| :--- | :--- | :--- | :--- |
| **Pytest Full Suite** | `npm test` | All 130 automated unit, integration, and safety tests | `tests/` |
| **Agronomic Product Checks** | `npm run test:product` | Offline verification of core agricultural safety gates | `scripts/verify_product.py` |
| **TypeScript Typecheck** | `npm run lint` | Next.js frontend TypeScript compilation check | `web/` |
| **Python Syntax Check** | `python -m compileall -q .` | Full bytecode compilation check across all modules | Project root |

---

## 2. Automated Test Modules Breakdown

The test suite contains **130 automated tests across 10 modules**, executed with `pytest`:

### 2.1. `tests/test_adaptive_evidence_novelty.py` (26 tests)
- Validates the Evidence Engine and novelty scoring heuristics.
- Verifies dynamic weighting adjustments when multi-agent signals shift.
- Tests confidence bounds and edge-case inputs across unusual environmental combinations.

### 2.2. `tests/test_api_hardening.py` (4 tests)
- Enforces strict Pydantic `extra="forbid"` payload validation.
- Verifies rejection of invalid coordinates (e.g., latitude $> 90^\circ$).
- Tests error handling and sanitized responses for malformed client requests.

### 2.3. `tests/test_graph_wiring.py` (1 test)
- Validates LangGraph StateGraph topology, node connectivity, and edge definitions.
- Confirms state dictionary mutability and transition invariants.

### 2.4. `tests/test_llm_observability.py` (5 tests)
- Tests multi-provider router failover logic (xAI -> Groq -> Gemini -> Rule Template).
- Verifies database logging of token usage, latency metrics, and provider statuses.
- Asserts that external LLM responses cannot mutate the deterministic action field.

### 2.5. `tests/test_orchestrator.py` (7 tests)
- Validates end-to-end `run_advisory()` invocations.
- Tests state propagation across weather, soil, disease, market, and advisory nodes.

### 2.6. `tests/test_phase2_research_core.py` (32 tests)
- Exhaustive verification of the Decision Stability Score (DSS) formula:
  $$\text{DSS} = 1.0 - (0.4 \cdot R_{rain} + 0.3 \cdot (1 - C) + 0.3 \cdot K_{conflicts})$$
- Confirms DSS tier thresholds (`HIGH`, `MODERATE`, `LOW`) and corresponding farmer advice.
- Validates re-evaluation trigger selection algorithms.

### 2.7. `tests/test_rag_quality.py` (6 tests)
- Validates ICAR 2025 Kharif chunk ingestion and integrity.
- Tests TF-IDF keyword candidate generation.
- Verifies metadata reranking (crop boosting, growth stage alignment, disease filtering).

### 2.8. `tests/test_refactor.py` (7 tests)
- Regression tests preserving baseline behavior across modular refactoring.
- Confirms mathematical equivalence of modernized scoring modules.

### 2.9. `tests/test_repair_batch.py` (21 tests)
- Validates edge case corrections: zero-division protection in NPK targets, missing weather data, null leaf image handling.

### 2.10. `tests/test_v11_hardening.py` (21 tests)
- Verifies Hard Safety Guards A through F (Rainfall Veto, Severe Disease Outbreak, Waterlogging, Crop-Disease Compatibility, Thermal Stress, Pre-Harvest Interval).
- Verifies P1–P5 priority conflict resolution hierarchy.

---

## 3. Product Verification Script (`scripts/verify_product.py`)

A standalone script designed for zero-dependency sanity checks without running the complete test harness:

```bash
python scripts/verify_product.py
```

### Verification Criteria Checked:
1. **Rainfall Safety Veto:** Asserts that precipitation probability $> 70\%$ enforces `DELAY` even under acute nitrogen deficiency.
2. **Soil Deficiency:** Asserts that under safe weather, low NPK triggers `apply_fertilizer`.
3. **Disease Confidence Gate:** Asserts that disease predictions $< 0.60$ are marked unverified.
4. **ICAR Knowledge Retrieval:** Asserts that queries against the local corpus yield valid advisory citations.

---

## 4. Test Execution Results (Verified)

```text
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\project\AGRIMIND\demo\agrimind_batch1
collected 130 items

tests\test_adaptive_evidence_novelty.py ..........................       [ 20%]
tests\test_api_hardening.py ....                                         [ 23%]
tests\test_graph_wiring.py .                                             [ 23%]
tests\test_llm_observability.py .....                                    [ 27%]
tests\test_orchestrator.py .......                                       [ 33%]
tests\test_phase2_research_core.py ................................      [ 57%]
tests\test_rag_quality.py ......                                         [ 62%]
tests\test_refactor.py .......                                           [ 67%]
tests\test_repair_batch.py .....................                         [ 83%]
tests\test_v11_hardening.py .....................                        [100%]

======================= 130 passed, 1 warning in 59.01s =======================
```
