# AgriMind Agent Contracts Specification

## 1. Overview

This document specifies the formalized data contracts and execution boundaries for AgriMind specialist agents:
- **Weather Agent**
- **Soil Agent**
- **Crop Disease Agent**
- **Advisory Agent**
- **Market Intelligence Agent**
- **Central Orchestrator & Conflict Resolver**

---

## 2. Standardized Agent Result Schema

All specialist agents return dataclasses inheriting from `AgentResult` (`orchestrator/state.py`):

```python
class AgentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    OVERRIDE = "OVERRIDE"

@dataclass
class AgentResult:
    agent_name: str
    status: str = AgentStatus.SUCCESS.value
    input_summary: dict = field(default_factory=dict)
    findings: str = ""
    evidence: list = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error_code: Optional[str] = None
    execution_time_ms: float = 0.0
    source_metadata: dict = field(default_factory=dict)
```

### Contract Invariants
1. `confidence`: Bounded in `[0.0, 1.0]`. Zero represents absent or completely unverified evidence; 1.0 represents high-confidence ground truth.
2. `execution_time_ms`: Non-negative float measuring agent execution latency in milliseconds.
3. `status`: Machine-readable canonical status enum. Missing dependencies must explicitly return `UNAVAILABLE` rather than pretending to succeed with empty data.
4. `evidence`: List of key-value evidence pairs forwarded to the Adaptive Evidence Engine.

---

## 3. Specialist Agent Specifications

### 3.1 Weather Agent (`agents/weather_agent.py`)
- **Inputs:** `lat: float`, `lon: float`, `override: Optional[dict]`
- **Contract:** Returns `WeatherResult(AgentResult)`
- **Key Fields:**
  - `rainfall_risk: float` (0.0 to 1.0)
  - `risk_level: str` (`LOW`, `MODERATE`, `HIGH`, `SEVERE`)
  - `fertilizer_condition: str` (`normal`, `delay`)
  - `irrigation_condition: str` (`normal`, `avoid`)
  - `status: str` (`AVAILABLE`, `UNAVAILABLE`, `TIMEOUT`, `INVALID`, `OVERRIDE`)
- **Failure Behavior:**
  - If coordinates are missing or API fails, returns `status="UNAVAILABLE"`, `rainfall_risk=0.0`, `confidence=0.0`.
  - When timed out, returns `status="TIMEOUT"`.
  - Never fabricates zero rainfall when telemetry is missing; triggers Rule E confidence penalty.

### 3.2 Soil Agent (`agents/soil_agent.py`)
- **Inputs:** `n: float | None`, `p: float | None`, `k: float | None`, `crop: str`, `soil_type: str`, `mode: str`
- **Contract:** Returns `SoilResult(AgentResult)`
- **Key Fields:**
  - `nitrogen_deficiency: Optional[float]`
  - `phosphorus_deficiency: Optional[float]`
  - `potassium_deficiency: Optional[float]`
  - `overall_deficiency: Optional[float]`
  - `nutrient_status: str` (`MEASURED`, `UNAVAILABLE`)
  - `npk_available: bool`
  - `status: str` (`MEASURED`, `LOCATION_ESTIMATED`, `USER_SELECTED`, `UNAVAILABLE`)
- **Failure Behavior:**
  - If NPK is unmeasured, deficiencies remain `None`, `npk_available=False`.
  - Does NOT invent default nutrient deficiencies. Rule A blocks chemical fertilizer dosage.

### 3.3 Crop Disease Agent (`agents/disease_agent.py`)
- **Inputs:** `image_path: Optional[str]`, `selected_crop: str`, `override: Optional[dict]`
- **Contract:** Returns `DiseaseResult(AgentResult)`
- **Key Fields:**
  - `predicted_class: Optional[str]`
  - `confidence: float`
  - `crop_detected: Optional[str]`
  - `crop_mismatch: bool`
  - `actionable: bool`
  - `status: str` (`AVAILABLE`, `NOT_SUPPLIED`, `OVERRIDE`, `MODEL_UNAVAILABLE`, `INVALID_IMAGE`)
- **Failure Behavior:**
  - Missing checkpoint returns `status="MODEL_UNAVAILABLE"`, `confidence=0.0`.
  - Corrupt or malformed image returns `status="INVALID_IMAGE"`.
  - Treatment state machine marks `DEFERRED_MODEL_UNAVAILABLE` or `DEFERRED_INVALID_IMAGE`; chemical spray is strictly held.

### 3.4 Advisory Agent (`agents/advisory_agent.py`)
- **Inputs:** `state: AgriMindState`, `weights: Optional[dict]`
- **Contract:** Returns `AdvisoryResult(AgentResult)`
- **Key Fields:**
  - `scores: dict[str, float]` (`apply_fertilizer`, `delay`, `monitor`)
  - `preliminary_recommendation: str`
  - `confidence: float`
- **Responsibility:**
  - Pure preliminary scoring agent $S(a)$.
  - Intentionally does not execute safety vetoes; delegates authoritative veto logic to the central orchestrator and safety guard.

### 3.5 Market Agent (`agents/market_agent.py`)
- **Inputs:** `current_price: float`, `price_history: list[float]`, `crop: str`, `growth_stage: str`, `market: Optional[str]`
- **Contract:** Returns `MarketResult(AgentResult)`
- **Key Fields:**
  - `market_score: float` (0.0 to 1.0)
  - `signal: str` (`sell`, `hold`, `caution`)
  - `benchmark_price: Optional[float]` (populated when farmer provides input; source='caller_provided', status='USER_SUPPLIED')
  - `observed_price: Optional[float]` (populated strictly when live/cached APMC telemetry is retrieved; status='REAL_DATA' or 'CACHED')
  - `authoritative: bool` (`True` only for verified live APMC Mandi feeds; `False` for cached observations and user-supplied benchmarks)
  - `retrieval_timestamp: Optional[str]` (ISO-8601 timestamp of verified market observation)
  - `phenology_override_applied: bool` (guards against selling signals during vegetative, flowering, or fruit development)
  - `status: str` (`REAL_DATA`, `CACHED`, `USER_SUPPLIED`, `UNAVAILABLE`)
- **Provenance Invariant:**
  - Caller-provided benchmark prices must **NEVER** be presented as verified live market prices or populate `observed_price`.
  - When no market data is available, `status="UNAVAILABLE"`, `is_available=False`, and sell/hold conclusions are suppressed.
- **Boundary Constraint:**
  - Advisory context only; market signals CANNOT override agronomic safety decisions or force harvest in premature crop growth stages.

---

## 4. Orchestrator Handoff & Validation

1. **State Preservation:** State is managed via `AgriMindState` (`orchestrator/state.py`).
2. **Contract Enforcement:** Each graph node measures execution time, populates `input_summary` and `warnings`, and calls `validate_contract()`.
3. **Execution Trace:** Every node handoff logs its inputs, outputs, latency, and status to the observability audit trail in SQLite.
