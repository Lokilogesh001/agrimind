# AgriMind — Testing & Operational Verification Guide

AgriMind maintains a production-focused verification suite covering deterministic decision safety, API contract integrity, ML inference validation, ICAR RAG retrieval precision, and end-to-end multi-agent orchestration.

---

## 1. Operational Verification Architecture & Commands

For minimal production deployments, AgriMind uses a high-speed, self-contained verification runner (`scripts/verify_product.py`) that tests all critical system layers without requiring bloated test harnesses or fixtures.

| Level | Command | Scope | Target |
| :--- | :--- | :--- | :--- |
| **Essential Validation Suite** | `py -m pytest tests/ -v` | Combinatorial, safety, contract, provenance & disease evaluation tests | `tests/` (126 tests) |
| **Production System Suite** | `npm test` or `py scripts/verify_product.py` | Full 8-tier production operational verification | `scripts/verify_product.py` |
| **Product Smoke Check** | `npm run test:product` | Alias for fast production sanity check | `scripts/verify_product.py` |
| **TypeScript Typecheck** | `npm run lint` or `npm --prefix web run typecheck` | Next.js frontend TypeScript compilation check | `web/` |
| **Python Syntax Check** | `py -m compileall -q .` | Full bytecode compilation check across all modules | Project root |
| **Frontend Production Build** | `npm run build` | Next.js Turbopack production compilation | `web/` |

---

## 2. Production Verification Suite (`scripts/verify_product.py`)

A comprehensive, zero-mock operational runner executing live checks against the backend, model checkpoint, and database:

```bash
python scripts/verify_product.py
```

### 8 Verification Tiers Executed:
1. **Observability Database Engine:**
   - Initializes SQLite/Postgres engine and verifies table schema connectivity.
2. **Disease Vision Classifier & Model Artifact:**
   - Verifies `ml/artifacts/best.pt` file presence, size (17.2 MB), and `MobileNetV3-Large` architecture.
   - Asserts all 38 PlantVillage classes are registered.
   - Runs genuine inference on a synthetic RGB leaf image and validates top-3 prediction distribution.
   - Verifies invalid/corrupted image rejection (zero-byte files raise `ValueError`).
3. **Specialist Agent Contracts & State Machine:**
   - Executes LangGraph multi-agent orchestration pipeline.
   - Asserts all 5 specialist agents (Weather, Soil, Disease, Advisory, Market) return valid structured contracts conforming to `AgentResult` and explicit status semantics.
   - Confirms execution trace logging and positive Decision Stability Score (DSS).
4. **Deterministic Hard Safety Guards (Rules A through F):**
   - **Rule D (Rainfall Veto):** Asserts precipitation probability $\ge 0.60$ enforces `DELAY` even under acute nitrogen deficiency.
   - **Rule A (Soil Guard):** Asserts unmeasured soil tests cannot fabricate NPK fertilizer doses or approve chemical replenishment.
   - **Rule B (Disease Gate):** Asserts disease prediction confidence $< 0.60$ blocks chemical treatment.
   - **Rule C (Crop Match Guard):** Asserts cross-species diagnoses (e.g., tomato blight on rice) are flagged in safety constraints and blocked.
   - **Rule F (Agronomic Priority):** Asserts extreme falling market prices cannot override agronomic safety vetoes.
5. **ICAR Agricultural Knowledge Retrieval:**
   - Searches local ICAR Kharif 2025 corpus and asserts relevant advisory chunk retrieval with document and excerpt metadata.
6. **LLM Provider Chain & Resilient Fallback:**
   - Validates that OpenAI $\rightarrow$ xAI Grok $\rightarrow$ Deterministic Template fallback preserves authoritative decisions without mutation.
7. **Observability Database Persistence:**
   - Verifies that advisory runs, inputs, decisions, and agent latencies are persisted to `agrimind_local.db` and queryable via `get_run_trail()`.
8. **FastAPI HTTP Endpoints (Live In-Process Client):**
   - Asserts HTTP 200 on `GET /health` (`status="ok"`).
   - Asserts HTTP 200 on `GET /health/model` (`ready=true`, `classes_count=38`).
   - Asserts HTTP 200 on `POST /api/internal/test-advisory` with structured response.

---

## 3. Production Verification Execution Results (Verified)

```text
======================================================================
🌾 AGRIMIND PRODUCTION SYSTEM VERIFICATION RUNNER
======================================================================

[VERIFY] 1. Observability Database Initialization...
  ✅ PASS: SQLite observability engine initialized cleanly

[VERIFY] 2. Disease Vision Model & Checkpoint Integrity...
  ✅ PASS: Model status is READY (expected READY)
  ✅ PASS: Loaded all 38 PlantVillage classes
  ✅ PASS: Architecture is MobileNetV3-Large
  ✅ PASS: Predicted class: Corn_(maize)___healthy
  ✅ PASS: Confidence score: 0.679186
  ✅ PASS: Top-3 class distribution returned
  ✅ PASS: Zero-byte / corrupted image rejected cleanly with ValueError

[VERIFY] 3. Specialist Agent Contracts & End-to-End Orchestration...
  ✅ PASS: Weather agent contract: AVAILABLE
  ✅ PASS: Soil agent contract: MEASURED
  ✅ PASS: Disease agent contract: OVERRIDE
  ✅ PASS: Advisory agent contract: SUCCESS
  ✅ PASS: Market agent contract: UNAVAILABLE
  ✅ PASS: Execution trace recorded (6 events)
  ✅ PASS: Decision stability score: 0.9442

[VERIFY] 4. Deterministic Safety Guards (Rules A - F)...
  ✅ PASS: Rule D (Rain Veto): Expected DELAY, got DELAY
  ✅ PASS: Rule A (Soil Guard): npk_available is False when unmeasured
  ✅ PASS: Rule A: No fabricated fertilizer doses
  ✅ PASS: Rule A: Chemical fertilizer application blocked without measured soil test
  ✅ PASS: Rule B (Confidence Gate): Action blocked for confidence < 0.60
  ✅ PASS: Rule C (Crop Mismatch): Flagged cross-species diagnosis in safety constraints
  ✅ PASS: Rule F (Agronomic Priority): Falling market price cannot override rainfall safety veto

[VERIFY] 5. ICAR Agricultural Knowledge Retrieval...
  ✅ PASS: Retrieved 3 relevant ICAR advisory documents
  ✅ PASS: Retrieved documents contain document and text metadata

[VERIFY] 6. LLM Explanation Provider Chain & Resilient Fallback...
  ✅ PASS: Explanation generated via provider: deterministic
  ✅ PASS: Detailed advisory guidance text generated successfully
  ✅ PASS: Structured explanation dictionary present

[VERIFY] 7. Observability Database Persistence...
  ✅ PASS: Retrieved 5 logged advisory runs from database
  ✅ PASS: Latest run recorded: ID=66bdfdc1..., Action=apply_fertilizer
  ✅ PASS: Auditable run trail contains 6 agent logs

[VERIFY] 8. FastAPI HTTP Endpoints (Live In-Process Client)...
  ✅ PASS: /health endpoint returned 200 OK
  ✅ PASS: /health/model endpoint returned 200 READY
  ✅ PASS: /api/internal/test-advisory returned status 200
  ✅ PASS: Advisory returned valid response: apply_fertilizer

======================================================================
🎉 ALL 8 PRODUCTION SYSTEM CHECKS PASSED PERFECTLY!
======================================================================
```

---

## 4. Historical Test Suite Verification Record (Pre-Cleanup Baseline)

Prior to consolidating into a minimal production repository structure, the complete 160+ unit, integration, and security test suite achieved 100% pass rates across all modules:

| Test Module | Tests | Result | Focus |
|:---|:---:|:---:|:---|
| `test_phase1_phase2_comprehensive.py` | 18 | **PASSED** | End-to-end integration and security hardening |
| `test_llm_provider_chain.py` | 18 | **PASSED** | Multi-provider fallback and credential redaction |
| `test_audit_remediation.py` | 11 | **PASSED** | Defect remediation and model safety |
| `test_repair_batch.py` | 21 | **PASSED** | Edge cases and null input handling |
| `test_v11_hardening.py` | 21 | **PASSED** | Safety Guards A–F and P1–P5 priority resolution |
| `test_adaptive_evidence_novelty.py` | 26 | **PASSED** | Decision stability score (DSS) and evidence weighting |
| `test_orchestrator.py` | 7 | **PASSED** | LangGraph orchestration and state propagation |
| `test_nearby_stores.py` | 12 | **PASSED** | Spatial store queries and dealer locator |
| `test_rag_quality.py` | 6 | **PASSED** | ICAR 2025 chunk retrieval precision |
| `test_api_hardening.py` | 4 | **PASSED** | Pydantic payload validation and coordinate boundaries |
| `test_refactor.py` | 7 | **PASSED** | Modular scoring equivalence |
| `test_graph_wiring.py` | 1 | **PASSED** | LangGraph topology and transitions |
| `test_llm_observability.py` | 5 | **PASSED** | Audit logging and non-override immutability |

**Historical Total:** 160+ passing tests, 0 failures, 100% verified baseline.

---

## 5. Re-Established Validation Framework (`tests/`)

Phase 3 re-established a compact, maintainable validation suite in `tests/` specifically addressing combinatorial coverage, threshold boundary transitions, and market provenance:

```bash
# Run the complete essential validation suite
py -m pytest tests/ -v
```

### Module Breakdown (110 Tests Total — 100% Passing)
1. `tests/test_agent_contracts.py` (10 tests):
   - Contract schemas across all 5 agents (Weather, Soil, Disease, Advisory, Market).
   - Invariants: confidence bounded in $[0.0, 1.0]$, execution timings $\ge 0$, explicit status semantics.
2. `tests/test_combinatorial_matrix.py` (41 tests):
   - 5-agent full failure power set ($2^5 = 32$ subsets):
     - $C(5, 0) = 1$: All 5 agents succeed.
     - $C(5, 1) = 5$: Each agent fails individually while 4 succeed.
     - $C(5, 2) = 10$: All pairs of simultaneous agent failures.
     - $C(5, 3) = 10$: All triplets of simultaneous agent failures.
     - $C(5, 4) = 5$: Exactly 1 lone survivor agent available.
     - $C(5, 5) = 1$: Total system blackout (all 5 unavailable/failed).
   - Targeted asymmetric & multi-system failure interactions (9 tests):
     - Disease active + weather/soil missing.
     - Weather unavailable while fertilizer requested.
     - Market sell signal + heavy rainfall veto conflict.
     - Contradictory agent evidence arbitration.
     - Heavy rainfall veto + unmeasured soil + disease model unavailable compound safety.
     - Disease model failure + RAG retriever empty + LLM timeout fallback.
     - Agent HTTP timeouts & malformed status handling.
     - Deterministic reproducibility ($f(x_1) = f(x_2)$).
     - Repeated requests & state immutability.
3. `tests/test_safety_thresholds.py` (30 tests):
   - Exact boundary transitions immediately below, at, and above configured thresholds:
     - Weather rain risk: 0.59 (permitted) vs 0.60 (DELAY veto) vs 0.61 (DELAY veto).
     - Disease confidence gate: 0.59 (blocked) vs 0.60 (actionable) vs 0.61 (actionable).
     - Decision Stability Score (DSS) tiers: 0.39/0.40, 0.59/0.60, 0.79/0.80.
     - Evidence Quality Score (EQS) tiers: 0.34/0.35, 0.54/0.55, 0.74/0.75.
     - Crop mismatch rules: cross-crop disease prediction (e.g. Rice with Tomato Early Blight) blocked & flagged.
     - Missing soil NPK: unmeasured test never fabricates deficiency or chemical fertilizer recommendation.
   - Negative-control & mutation tests (4 tests):
     - Proves that without Guard D, `apply_fertilizer` would be emitted, but Guard D actively mutates it to `DELAY`.
     - Proves that without Guard A, fertilizer would proceed on unmeasured soil, but Guard A actively forces `monitor`.
     - Proves that without Guard B, low-confidence Late Blight would trigger chemical spray, but Guard B blocks it.
     - Proves that without Guard C, cross-species disease prediction would trigger chemical spray, but Guard C blocks it.
   - Weather fallback & provenance preservation regression tests (3 tests):
     - `test_weather_timeout_agent_output_and_advisory_safety`: Verifies that weather timeouts are explicitly flagged (`status="TIMEOUT"`, `is_available=False`, `is_estimated=True`, `risk_level="UNKNOWN"`), trigger conservative Rule D fertilizer delays (`DELAY`), and immediately hold chemical spraying (`weather_hold=True`, `is_permitted=False`).
     - `test_weather_cache_timestamp_and_provenance_preservation`: Verifies that cached weather entries retain original observation/retrieval timestamps, report `freshness_status="CACHED"` and `is_cached=True`, and expire cleanly beyond the 15-minute TTL.
     - `test_all_six_weather_states_end_to_end_safety`: End-to-end trace across `REAL_DATA`, `CACHED`, `STALE_CACHE`, `TIMEOUT`, `UNAVAILABLE`, and `INVALID`, proving that stale or unknown weather never silently becomes a verified low-risk observation and always defers chemical fertilizer and foliar spraying.
4. `tests/test_market_provenance.py` (7 tests):
   - Provenance isolation: caller benchmark price strictly populates `benchmark_price` and NEVER leaks into `observed_price`.
   - Verified Agmarknet live price populates `observed_price` with `status="REAL_DATA"`.
   - Cached observation populates `observed_price` with `status="CACHED"` within 15-minute TTL.
   - Unavailable market data suppresses unsupported sell/hold conclusions.
5. `tests/test_fault_injection_and_properties.py` (8 tests):
   - 100 seeded property-based iterations (fixed seed 42) verifying global safety invariants.
   - Fault injection: missing/corrupted model checkpoints, 0-byte and oversized images.
   - LLM provider failures: rate limits (429), timeouts, and malformed responses safely falling back to deterministic template.
   - Database persistence fault resilience.
6. `tests/test_api_and_observability.py` (17 tests):
   - FastAPI public endpoints: `/health`, `/health/model`, `/api/crops`, `/api/location/search`.
   - Request bounds checking: coordinates, non-negative prices, location validation.
   - Security: `ENVIRONMENT=production` forbids synthetic overrides and blocks `/api/internal/test-advisory` with 403.
   - Image upload endpoint validation: MIME type, empty file, corrupted data.
   - Observability: Run audit trail retrieval via `GET /api/runs/{run_id}` and feedback persistence.
7. `tests/test_disease_evaluation.py` (13 tests):
   - Checkpoint architecture and exact 38-class index mapping validation (`best.pt`).
   - Preprocessing consistency: 224×224 RGB resolution, PyTorch ToTensor, and ImageNet normalization.
   - Missing and corrupted checkpoint detection (`CHECKPOINT_UNAVAILABLE`).
   - Empty dataset and corrupted image rejection (`BLOCKED_INVALID_DATA`).
   - Invalid, unknown, and unmapped labels handling (isolated in `unmapped_samples`).
   - Duplicate detection and grouped-specimen leakage checking (`check_train_test_leakage`).
   - Wilson 95% confidence interval mathematical bounds validation.
   - Partial class coverage handling and transition to `PARTIAL_CROSS_DATASET_EVALUATION`.
   - 38×38 confusion matrix shape and per-class support metric calculation.
   - Expected Calibration Error (ECE) and confidence statistics verification.
   - Deterministic reproducibility across repeated evaluations on identical datasets.
   - Unavailable external dataset graceful handling (`BLOCKED_PENDING_DATA`).

---

## 6. Phase 4 & Phase 5 Scientific Evaluation & Real-World Validation Suite

AgriMind features an automated, reproducible scientific evaluation and benchmarking pipeline designed for empirical dissertation evidence. The suite evaluates vision model accuracy on independent cross-dataset benchmarks, agronomic safety conformance, and external data resilience without fabricating ground truth or claiming unproven live validations.

### 6.1 Unified Master Evaluation Command

```bash
# Run the complete scientific evaluation suite (auto-detects PlantDoc benchmark if present)
python scripts/run_evaluation.py

# Alternatively via npm
npm run evaluate

# Run independent disease evaluation directly
python evaluation/evaluate_disease_model.py \
  --checkpoint ml/artifacts/best.pt \
  --data-dir evaluation/datasets/plantdoc_test/images \
  --manifest evaluation/manifests/plantdoc_test_manifest.csv \
  --output-dir evaluation/artifacts
```

**Parameters Supported:**
- `--checkpoint`: Path to vision model checkpoint (default: `ml/artifacts/best.pt`)
- `--data-dir`: Root directory of labeled test images (default: auto-detected `evaluation/datasets/plantdoc_test/images`)
- `--manifest`: Path to labeled test manifest file (default: auto-detected `evaluation/manifests/plantdoc_test_manifest.csv`)
- `--train-manifest`: Path to training manifest for leakage checking (default: `None`)
- `--benchmark`: Path to ground truth scenario benchmark (default: `evaluation/benchmarks/icar_advisory_ground_truth.json`)
- `--output-dir`: Target directory for artifacts (default: `evaluation/artifacts`)
- `--seed`: Deterministic random seed (default: `42`)
- `--batch-size`: Batch size for classifier evaluation (default: `32`)

---

### 6.2 Evaluation Subsystems & Tooling

#### 1. Disease Classifier Scientific Evaluation (`evaluation/evaluate_disease_model.py`)
- **Architecture:** MobileNetV3-Large image classifier across 38 PlantVillage classes (`ml/artifacts/best.pt`, SHA-256: `c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e`).
- **Independent Benchmark Dataset:** PlantDoc Test Set (Singh et al., ACM CoDS-COMAD 2020), licensed under Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Candidate Sources Evaluated for Independent Validation:**
  1. *ICAR Rice & Maize (AIKosh):* Evaluated live portal (`https://aikosh.indiaai.gov.in/`). Contains 8 rice classes and 6 maize classes. The model has zero rice classes (Rule C would trigger); only 1 maize class overlaps (`Corn Northern Leaf Blight`). In addition, data download requires MeriPehchaan/DigiLocker Indian citizen SSO authentication with OTP and data request approval. Not directly downloadable headless.
  2. *Paddy Doctor:* Evaluated live portal (`https://paddydoc.github.io/dataset/`). Contains exclusively paddy/rice diseases (Blast, Brown Spot, Hispa, Tungro, etc.). Zero class overlap with the model's 38 PlantVillage classes. Incompatible with the model's 38-class head.
  3. *PlantDoc Dataset:* Validated and acquired via GitHub (`https://github.com/pratikkayal/PlantDoc-Dataset`). CC BY 4.0 license confirmed. Features 27 disease and healthy foliage classes directly mapping to the model's 38-class taxonomy, captured in non-laboratory open environments with natural clutter and lighting.
- **Auditable Manifest:** Generated via `scripts/prepare_plantdoc_dataset.py` at `evaluation/manifests/plantdoc_test_manifest.csv` (236 valid images, 0 duplicates, 0 corruptions, SHA-256 hashes recorded).
- **Safe Evaluation Status Model:**
  * `BLOCKED_PENDING_DATA`: No independent external dataset has been evaluated.
  * `PARTIAL_CROSS_DATASET_EVALUATION`: External benchmark completed for a valid subset of classes (< 38 classes). *This is the current verified status for PlantDoc (27/38 classes).*
  * `CROSS_DATASET_EVALUATION_COMPLETE`: External benchmark completed for all 38 classes with recorded limitations.
  * `BLOCKED_INVALID_DATA`: Dataset malformed, empty, or unmapped.
  * `FIELD_VALIDATED`: Strictly reserved for certified real-farm cohort trials (never used for cross-dataset benchmarks).
- **Independent Cross-Dataset Results (PlantDoc Test Set, 236 images, 27 classes):**
  - **Top-1 Accuracy:** 25.42% (60 / 236 correct).
  - **Wilson 95% Confidence Interval:** `[0.2029, 0.3134]` (`[20.29%, 31.34%]`).
  - **Macro-F1 (Evaluated 27 Classes):** 0.2268.
  - **Macro-F1 (All 38 Classes):** 0.1611.
  - **Weighted-F1:** 0.2319.
  - **Expected Calibration Error (ECE):** 0.2890 (Maximum Calibration Error: 0.5284 across 10 confidence bins).
  - **Gate Abstention:** 56.78% of field predictions fall below the 0.60 confidence gate, safely triggering Rule B fallback to KVK extension experts rather than administering erroneous chemicals.

---

### 6.3 Scientific Interpretation: Three-Tier Validation Framework

AgriMind enforces strict academic precision across three fundamentally distinct validation categories:

#### Tier A: Laboratory PlantVillage Validation
- **Setting:** Laboratory benchtop photography (Mohanty et al., 2016).
- **Conditions:** Detached leaves, uniform matte black/grey backgrounds, controlled diffuse artificial illumination, centered leaf orientation, severe lesions.
- **Reported Metric:** 99.39% validation Macro-F1 (`best_val_macro_f1 = 0.993914` at epoch 9).
- **Scientific Limitation:** Validates high-contrast feature separability under laboratory benchtop conditions. Does NOT establish clinical efficacy or generalizability to living field crops.

#### Tier B: Independent Cross-Dataset Evaluation (PlantDoc)
- **Setting:** Internet-collected non-laboratory foliage images under variable natural conditions (Singh et al., 2020).
- **Conditions:** Complex agricultural backgrounds (soil, weeds, neighboring stems), uncontrolled direct sunlight and cloud shadows, natural clutter, phone camera compression.
- **Coverage:** 27 of 38 classes (71.05% coverage; 11 unrepresented classes recorded).
- **Reported Metric:** 25.42% Top-1 Accuracy (Wilson 95% CI: `[20.29%, 31.34%]`), 0.2268 Macro-F1 (evaluated classes), 0.2890 ECE.
- **Scientific Insight:** The stark performance gap between Tier A (99.39%) and Tier B (25.42%) empirically verifies severe out-of-distribution domain shift. This validates the architectural necessity of AgriMind's deterministic safety gates (Rule B 0.60 confidence gate, Rule C crop mismatch guard) to prevent dangerous agrochemical misapplication.

#### Tier C: In-Situ Indian Field Validation
- **Setting:** Independently labeled real-farm cohort photographs collected in active Indian agricultural districts.
- **Status:** **BLOCKED PENDING FIELD DATA.** AgriMind does NOT claim field validation without a certified real-farm trial.

---

### 6.4 Practical Indian Field Validation Protocol

For future field validation trials, AgriMind specifies the following reproducible agronomic protocol:

1. **Target Crops & Supported Classes:**
   - Focus on AgriMind's primary supported crops: Tomato (10 classes), Potato (3 classes), Bell Pepper (2 classes), Maize/Corn (4 classes), and Apple (4 classes).
2. **Multi-Farm Sampling Strategy:**
   - Minimum of 3 agro-ecological zones (e.g., Western Maharashtra black soil, Gangetic alluvial Bihar/UP, and semi-arid Karnataka red soil).
   - Minimum of 5 separate farms per agro-climatic zone across 2 consecutive cropping seasons (Kharif and Rabi).
3. **Environmental & Morphological Diversity:**
   - Multiple collection dates tracking crop phenology: vegetative, flowering, and fruit-bearing stages.
   - Variable ambient lighting: early morning oblique sunlight, noon direct sunlight, overcast diffuse lighting, and late afternoon shadows.
   - Severity stratification: early-stage micro-lesions, moderate foliar symptoms, and advanced necrosis.
4. **Acquisition Standards & Metadata:**
   - Original-resolution smartphone captures (uncompressed JPEG/RAW from typical low-to-mid-tier devices: 12–48 MP).
   - Strict metadata logging: timestamp, GPS coordinates, crop cultivar, days after sowing, and recent spray history.
5. **Double-Blind Agronomic Ground Truth:**
   - Triplicate independent annotation by 3 qualified ICAR-KVK Subject Matter Specialists (SMS) in Plant Pathology.
   - Consensus rule: Majority agreement (2/3) required for positive label; unanimous agreement for healthy status.
   - Ambiguous or disputed lesions subjected to lab confirmation (microscopy or PCR) or tagged `UNCERTAIN` and excluded from primary benchmark.
6. **Farmer Consent, Ethics & Data Privacy:**
   - Explicit informed consent signed in vernacular languages (Hindi, Marathi, Tamil, etc.).
   - No personally identifiable farmer faces, homesteads, or vehicle registration numbers included in imagery.
7. **Leakage Protection & Locked Test Split:**
   - Grouped-specimen isolation: all photographs of the same plant or plot assigned strictly to either train, validation, or test partition.
   - Independent test set locked before any model inspection or threshold calibration.
8. **Predeclared Acceptance Criteria:**
   - Predeclared threshold targets agreed with consulting agronomists prior to unblinding test data:
     * Minimum Top-1 Accuracy: $\ge 75\%$ on target deployment classes.
     * Minimum Class Recall: $\ge 70\%$ for high-consequence pathogens (e.g., Potato Late Blight).
     * Maximum False Positive Rate on Healthy Foliage: $\le 10\%$.
     * Calibration ECE: $\le 0.15$.

---

### 6.5 Machine-Readable Output Artifacts (`evaluation/artifacts/`)

| Artifact File | Schema / Contents | Purpose |
| :--- | :--- | :--- |
| `disease_evaluation_status.json` | Status (`PARTIAL_CROSS_DATASET_EVALUATION`), checkpoint SHA-256, 27/38 classes evaluated, top-1 accuracy (25.42%), Wilson 95% CI, Macro-F1 (0.2268), ECE, fraction below 0.60 gate (56.78%). | Official ML model status artifact |
| `disease_evaluation_results.json` | Granular evaluation metrics: per-class precision/recall/F1/support across all 38 classes, 38×38 confusion matrix, 10-bin ECE calibration table, confidence distribution, misclassifications, and runtime environment. | Quantitative vision evaluation |
| `confusion_matrix.csv` | 38×38 comma-separated confusion matrix table with class headers. | Visual error analysis |
| `advisory_benchmark_report.json` | 16 scenario evaluations, inputs, expected behavior, actual output, safety rule checks, independent safety invariant evaluation, citation grounding, expert disclosure. | Agronomic safety & conformance evidence |
| `data_quality_report.json` | 18 empirical probes across weather, market, soil, and geocoding subsystems with latency, freshness status, probe type, and data category breakdown. | Telemetry resilience verification |
| `evaluation_summary.json` | Master consolidated report unifying disease (PlantDoc), advisory (16 ICAR scenarios), and data quality (18 probes) results. | Master dissertation evaluation report |



