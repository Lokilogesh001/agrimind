# AgriMind — Observability & Traceability

## 1. Observability Architecture
Agricultural recommendations require transparent, accountable auditing. If an advisor recommends withholding fertilizer or spraying a fungicide, the farmer, agronomist, or extension officer must be able to inspect **why** that decision was made.

AgriMind provides end-to-end traceability across four observable tiers:
1. **The 9-Step Linear Execution Trace:** Human-readable ordered event log.
2. **Granular Agent Telemetry:** Per-agent latency (ms), confidence, and input/output payloads.
3. **The Conflict & Safety Ledger:** Dedicated tracking of safety vetoes and priority resolutions.
4. **The Field Feedback Ledger:** Quantitative adoption tracking and outcome validation.

---

## 2. 9-Point Linear Execution Trace
Every run accumulates a structured array of timestamped milestones stored in `state.execution_trace`:

```text
[Step 1] Ingestion: Location resolved to 'Coimbatore, Tamil Nadu, India' (11.0055, 76.9661)
[Step 2] Weather Agent: Open-Meteo live feed -> Rainfall risk: 0.45, Precip Prob: 73%, Rain: 2.1mm
[Step 3] Soil Agent: Crop 'Rice' targets evaluated -> N: optimal, P: deficient (0.62), K: optimal
[Step 4] Disease Agent: No leaf image provided -> Vision module bypassed
[Step 5] Market Agent: Historical mandi trend unavailable -> Marked as neutral
[Step 6] Advisory Heuristic: Preliminary score computed (delay: 0.61, apply: 0.37, monitor: 0.49)
[Step 7] Safety Guard Core: Evaluated Stage-1 Guards A-F -> No hard safety veto active
[Step 8] Decision Engine: Stage-2 scoring finalized -> Action: 'delay' (DSS: 0.9538, Level: HIGH)
[Step 9] Observability: Record persisted to relational database (Run ID: c5f7b1f3-6d88-49b5-8668-12a453dc098b)
```

---

## 3. Agent Latency & Performance Accounting
During pipeline execution, every agent's execution time is measured using monotonic high-resolution timers (`time.perf_counter()`).

Example telemetry recorded in `agent_logs`:
```json
[
  {
    "agent_name": "weather",
    "status": "ok",
    "confidence": 0.85,
    "latency": 1060.07,
    "source": "open_meteo"
  },
  {
    "agent_name": "soil",
    "status": "ok",
    "confidence": 0.90,
    "latency": 0.04,
    "source": "project_calibration_heuristic"
  },
  {
    "agent_name": "disease",
    "status": "no_input",
    "confidence": 0.0,
    "latency": 0.01,
    "source": "NOT_SUPPLIED"
  },
  {
    "agent_name": "advisory",
    "status": "ok",
    "confidence": 0.6065,
    "latency": 0.03,
    "source": "preliminary_weighted_score"
  },
  {
    "agent_name": "market",
    "status": "unavailable",
    "confidence": 0.0,
    "latency": 0.02,
    "source": "none"
  }
]
```
The total pipeline latency is computed and persisted in the master `runs` table (`total_latency_ms`).

---

## 4. Conflict & Safety Event Ledger
When two agents produce contradictory directives, the decision engine constructs a structured audit entry in the `conflicts` table:

```json
{
  "run_id": "7a8b9c-...",
  "agent_a": "weather",
  "agent_b": "soil",
  "issue": "Soil Agent recommends immediate nitrogen application; Weather Agent predicts 82% rainfall probability.",
  "resolution": "Enforced DELAY under Priority 1 (Rainfall Safety Veto Guard A).",
  "priority": 1,
  "conflict_type": "OVERRIDE_HARD_SAFETY",
  "score_impact": 0.25
}
```

---

## 5. Token Usage & LLM Telemetry
When an external LLM provider synthesizes the explanation, AgriMind tracks token usage in `runs`:
- `llm_provider`: e.g. `"xai"`, `"groq"`, `"gemini"`, or `"deterministic"`
- `prompt_tokens`: Count of input prompt tokens consumed
- `completion_tokens`: Count of generated explanation tokens
- `llm_status`: `"success"`, `"fallback_used"`, or `"deterministic"`

---

## 6. Farmer Feedback & Adoption Ledger
Farmer feedback submitted via `POST /api/feedback` is linked directly to the parent `run_id`:
- `farmer_action_taken`: Did the farmer comply with the advice or deviate?
- `outcome_reported`: Crop yield result, runoff observed, disease recovery.
- `comment`: Farmer qualitative feedback.

This data allows agricultural extension teams to continuously monitor the real-world adoption and accuracy of AgriMind advisories.
