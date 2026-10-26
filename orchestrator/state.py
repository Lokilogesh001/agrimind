"""Shared state object passed through the LangGraph orchestrator.

Mirrors the conceptual state dict from the blueprint (Section 34), typed
with standardized dataclasses so decision.rules can rely on attribute access
rather than dict key lookups. Standardizes agent result contracts across all specialist agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AgentStatus(str, Enum):
    """Explicit canonical status values for all AgriMind specialist agents."""
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    OVERRIDE = "OVERRIDE"


@dataclass
class AgentResult:
    """Standardized base contract for all specialist agents."""
    agent_name: str = "specialist_agent"
    status: str = AgentStatus.SUCCESS.value
    input_summary: dict = field(default_factory=dict)
    findings: str = ""
    evidence: list = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error_code: Optional[str] = None
    execution_time_ms: float = 0.0
    source_metadata: dict = field(default_factory=dict)

    def validate_contract(self) -> list[str]:
        """Validate agent output against contract invariants."""
        issues: list[str] = []
        if not (0.0 <= self.confidence <= 1.0):
            issues.append(f"Confidence score {self.confidence} must be within [0.0, 1.0]")
        if self.execution_time_ms < 0:
            issues.append(f"Execution time {self.execution_time_ms} cannot be negative")
        return issues


@dataclass
class WeatherResult(AgentResult):
    agent_name: str = "weather"
    rainfall_risk: float = 0.0
    temperature_risk: float = 0.0
    irrigation_condition: str = "normal"
    fertilizer_condition: str = "normal"
    confidence: float = 0.0
    reason: str = ""
    is_available: bool = True
    status: str = "AVAILABLE"  # AVAILABLE | UNAVAILABLE | INVALID | TIMEOUT | OVERRIDE
    risk_level: str = "LOW"    # LOW | MODERATE | HIGH | SEVERE
    risk_explanation: str = ""
    precipitation_probability: Optional[float] = None
    rainfall_amount_mm: Optional[float] = None
    forecast_horizon_hours: int = 48
    peak_intensity_mm_hr: Optional[float] = None
    duration_hours_fraction: Optional[float] = None
    risk_formula: str = "(0.40 * precip_prob) + (0.40 * intensity) + (0.20 * duration)"
    washoff_risk_level: str = "LOW"
    leaching_risk_level: str = "LOW"
    source: str = "open_meteo"
    freshness_status: str = "REAL_DATA"  # REAL_DATA | CACHED | STALE_CACHE | UNAVAILABLE | ESTIMATED
    observation_time: Optional[str] = None
    retrieval_time: Optional[str] = None
    is_cached: bool = False
    is_estimated: bool = False


@dataclass
class SoilResult(AgentResult):
    agent_name: str = "soil"
    nitrogen_deficiency: Optional[float] = None
    phosphorus_deficiency: Optional[float] = None
    potassium_deficiency: Optional[float] = None
    overall_deficiency: Optional[float] = None
    nutrient_status: str = "UNAVAILABLE"  # MEASURED | UNAVAILABLE
    nutrient_assessment_text: str = ""
    priority_nutrient: str = ""
    confidence: float = 0.0
    supplied: dict = field(default_factory=dict)
    targets: dict = field(default_factory=dict)
    crop: str = ""
    soil_type: str = ""
    calibration_source: str = "project_calibration_heuristic"
    provenance: dict = field(default_factory=dict)
    npk_available: bool = True
    status: str = "AVAILABLE"  # MEASURED | LOCATION_ESTIMATED | USER_SELECTED | UNAVAILABLE

    def __post_init__(self):
        if self.overall_deficiency is None and not self.supplied:
            self.npk_available = False
            self.nutrient_status = "UNAVAILABLE"
        elif self.overall_deficiency is not None:
            self.npk_available = True
            self.nutrient_status = "MEASURED"


@dataclass
class DiseaseResult(AgentResult):
    agent_name: str = "disease"
    predicted_class: Optional[str] = None
    confidence: float = 0.0
    severity: str = "low"          # low | moderate | high
    actionable: bool = False        # set by decision.rules during Stage 1
    raw_class: Optional[str] = None
    normalized_disease: Optional[str] = None
    crop_detected: Optional[str] = None
    severity_source: str = "heuristic_keyword"
    status: str = "AVAILABLE"  # AVAILABLE | NOT_SUPPLIED | OVERRIDE | MODEL_UNAVAILABLE | INVALID_IMAGE
    crop_mismatch: bool = False
    confidence_gate_passed: bool = False
    crop_match_passed: bool = True
    action_status: str = "INACTIVE"  # ALLOWED | BLOCKED | INACTIVE
    block_reason: str = ""
    classifier_score: float = 0.0
    severity_qualification: str = ""
    treatment_details: Optional[dict] = None
    model_architecture: str = "DINOv2-Small-LoRA"
    model_version: str = "r4_b4"
    crop_concordance: Optional[float] = None
    crop_aware_mode: bool = False
    ambiguous: bool = False
    recommendation_note: Optional[str] = None
    top_alternatives: list[dict] = field(default_factory=list)


@dataclass
class AdvisoryResult(AgentResult):
    agent_name: str = "advisory"
    scores: dict = field(default_factory=dict)
    preliminary_recommendation: str = "monitor"
    confidence: float = 0.0
    reason: str = ""


@dataclass
class MarketResult(AgentResult):
    agent_name: str = "market"
    price_change_pct: float = 0.0
    moving_average: float = 0.0
    market_score: float = 0.0
    signal: str = "hold"
    confidence: float = 0.0
    is_available: bool = True
    status: str = "AVAILABLE"  # REAL_DATA | UNAVAILABLE | DEMO_DATA | OVERRIDE
    source: str = "unspecified"  # agmarknet_api | caller_provided | none
    authoritative: bool = False
    benchmark_price: Optional[float] = None
    current_price: Optional[float] = None
    observed_price: Optional[float] = None
    mandi_name: Optional[str] = None
    commodity_grade: Optional[str] = None
    retrieval_timestamp: Optional[str] = None
    market_formula: str = "(0.50 * Trend) + (0.30 * (1 - Volatility)) + (0.20 * Arrival)"
    phenology_override_applied: bool = False
    phenology_note: str = ""


@dataclass
class CropContext:
    crop: str = ""
    growth_stage: str = ""
    suitability_hint: float = 0.6


@dataclass
class AgriMindState:
    run_id: str
    raw_inputs: dict = field(default_factory=dict)   # farmer query payload for this run
    farm: dict = field(default_factory=dict)
    crop: CropContext = field(default_factory=CropContext)

    weather: WeatherResult = field(default_factory=WeatherResult)
    soil: SoilResult = field(default_factory=SoilResult)
    disease: DiseaseResult = field(default_factory=DiseaseResult)
    advisory: AdvisoryResult = field(default_factory=AdvisoryResult)
    market: MarketResult = field(default_factory=MarketResult)

    conflicts: list = field(default_factory=list)
    final_recommendation: Optional[str] = None
    confidence: Optional[float] = None
    execution_trace: list = field(default_factory=list)

    # Core Novelty — Adaptive Evidence & Conflict Resolution
    evidence_items: list = field(default_factory=list)
    decision_stability_score: float = 0.0
    stability_level: str = "INSUFFICIENT"  # HIGH | MODERATE | LOW | INSUFFICIENT
    supporting_evidence: list = field(default_factory=list)
    conflicting_evidence: list = field(default_factory=list)
    resolved_conflicts: list = field(default_factory=list)
    re_evaluation_trigger: str = ""
    required_additional_info: list = field(default_factory=list)
    decision_provenance: dict = field(default_factory=dict)
    evidence_quality_score: float = 0.0
    evidence_quality_level: str = "INSUFFICIENT"  # EXCELLENT | GOOD | MODERATE | LOW | INSUFFICIENT
    evidence_quality_breakdown: Optional[dict] = None
    decision_stability_breakdown: Optional[dict] = None
    safety_constraints: list = field(default_factory=list)
    decision_change_triggers: list = field(default_factory=list)
    agronomic_recommendation: Optional[str] = None
    market_recommendation: Optional[str] = None
    farm_advisory: Optional[str] = None
    operational_plan: Optional[dict] = None
    treatment_permission: Optional[dict] = None

    @property
    def recommendation(self) -> Optional[str]:
        return self.final_recommendation

    @recommendation.setter
    def recommendation(self, value: Optional[str]):
        self.final_recommendation = value

    def log(self, event: str):
        self.execution_trace.append(event)
