# AgriMind Decision Precedence & Safety Architecture

## 1. Safety Core Philosophy

AgriMind operates on a fundamental principle:
> **Agronomic safety decisions are authoritative, deterministic, and immutable. Large Language Models (LLMs) operate strictly as explanation and evidence synthesizers; they can never alter, override, or invent agronomic decisions.**

---

## 2. Rule Hierarchy and Precedence

The decision engine resolves inputs in a strict, two-stage deterministic pipeline:
1. **Stage 1 — Safety Guard Vetoes & Constraints:** Hard agronomic boundaries evaluated before considering optimization scores.
2. **Stage 2 — Adaptive Scoring & DSS:** Multi-criteria weighted scoring evaluated only within the feasible bounds permitted by Stage 1.

```mermaid
graph TD
    A[Raw Inputs & Agent Telemetry] --> B[Stage 1: Safety Guard & Conflict Vetoes]
    B -->|Rainfall Risk >= 0.70| V1[Rule D: DELAY Action Veto]
    B -->|Confidence < 0.60 or Model Unavailable| V2[Rule B: Block Disease Action]
    B -->|Crop Mismatch| V3[Rule C: Restrict Disease Spray]
    B -->|NPK Missing| V4[Rule A: Block Exact Fertilizer Dosage]
    B -->|Permitted| C[Stage 2: Multi-Agent Scoring S(a)]
    C --> D[Adaptive Evidence Engine & DSS]
    D --> E[Final Immutable Recommendation]
    E --> F[LLM Explainer & Transparency UI]
```

### Deterministic Safety Rules

#### Rule D — Weather Safety Veto (Priority 1)
- **Condition:** Continuous rainfall risk $\ge 0.60$ or discrete risk level in (`HIGH`, `SEVERE`).
- **Enforcement:** Unconditionally blocks fertilizer broadcasting and chemical fungicide applications. Forces action to `DELAY`.
- **Agronomic Grounding:** Prevents chemical run-off into aquatic ecosystems and nutrient leaching beyond root absorption zones.

#### Rule B — Disease Confidence Gate (Priority 2)
- **Condition:** Pathogen classification confidence $< 0.60$, model checkpoint unavailable (`MODEL_UNAVAILABLE`), or invalid image input.
- **Enforcement:** Blocks `DISEASE_MANAGEMENT_FIRST` chemical spraying. Constrains action to `monitor` and triggers cultural phytosanitary sanitation steps.
- **Agronomic Grounding:** Prevents unnecessary or phytotoxic pesticide application based on uncertain image diagnosis.

#### Rule C — Crop Mismatch Guard (Priority 3)
- **Condition:** Disease detected belongs to a different botanical family than the farmer-selected crop (e.g., tomato late blight on rice leaves).
- **Enforcement:** Action status set to `BLOCKED`, treatment permission marks `RESTRICTED_CROP_MISMATCH`.
- **Agronomic Grounding:** Using registered fungicides across incompatible crop species risks canopy scorching, legal residue violations, and crop failure.

#### Rule A — Soil Evidence Guard (Priority 4)
- **Condition:** NPK soil test measurements are not provided (`n is None or p is None or k is None`).
- **Enforcement:** Blocks `apply_fertilizer` recommendations that depend on measured nutrient targets; advises Soil Health Card laboratory testing.
- **Agronomic Grounding:** Blind chemical fertilization leads to soil salinity buildup, nutrient lockup, and wasteful expenditure.

#### Rule E — Data Freshness & Reliability Guard (Priority 5)
- **Condition:** Meteorological telemetry is `UNAVAILABLE`, `TIMEOUT`, or `INVALID`, or disease diagnostic model is offline.
- **Enforcement:** Applies explicit confidence penalties (e.g., $-0.15$ for weather, $-0.10$ for disease) to prevent overconfident claims.

#### Rule F — Conflicting Evidence & Market Precedence (Priority 6)
- **Condition:** Market agent issues `SELL` signal while adverse weather or vegetative growth stage is active.
- **Enforcement:** Agronomic safety and physiological maturity strictly override commercial selling signals.

---

## 3. Treatment Permission State Machine

Chemical intervention is regulated via `TreatmentPermission` (`data_sources/treatments.py`):

| State | Chemical Spray Allowed | Rationale |
|:---|:---:|:---|
| `PERMITTED` | **Yes** | Pathogen confirmed $\ge 0.60$, crop matched, weather rain-free window open, registered in CIBRC catalog. |
| `DEFERRED_WEATHER` | **No** | Rainfall risk exceeds safe threshold; holds spraying until rain-free window. |
| `DEFERRED_MODEL_UNAVAILABLE` | **No** | ML checkpoint offline; chemical application held pending extension agronomist review. |
| `DEFERRED_INVALID_IMAGE` | **No** | Image corrupted or invalid; held pending re-upload. |
| `DEFERRED_UNVERIFIED` | **No** | Confidence below 60% gate; held pending manual field scouting. |
| `RESTRICTED_CROP_MISMATCH` | **No** | Predicted disease species does not match selected crop. |
| `NO_ACTION_REQUIRED` | **No** | Foliage is healthy; prophylactic sprays discouraged. |

---

## 4. Explainer Trust Boundary

1. **Non-Authoritative Role:** The LLM provider (OpenAI / xAI Grok / Template) receives the immutable decision record and state evidence.
2. **Decision Invariance:** Explainer output cannot modify `final_recommendation`, `confidence`, `treatment_permission`, or `decision_stability_score`.
3. **Structured Fallback:** If LLM providers time out, fail authentication, or return malformed JSON, AgriMind seamlessly falls back to the deterministic template generator with zero loss of decision integrity.
