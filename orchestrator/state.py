"""Shared state object passed through the LangGraph orchestrator.

Mirrors the conceptual state dict from the blueprint (Section 34), typed
with dataclasses so decision.rules can rely on attribute access rather than
dict key lookups.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WeatherResult:
    rainfall_risk: float = 0.0
    temperature_risk: float = 0.0
    irrigation_condition: str = "normal"
    fertilizer_condition: str = "normal"
    confidence: float = 0.0
    reason: str = ""
    is_available: bool = True


@dataclass
class SoilResult:
    nitrogen_deficiency: float = 0.0
    phosphorus_deficiency: float = 0.0
    potassium_deficiency: float = 0.0
    overall_deficiency: float = 0.0
    priority_nutrient: str = ""
    confidence: float = 0.0
    supplied: dict = field(default_factory=dict)
    targets: dict = field(default_factory=dict)
    crop: str = ""
    soil_type: str = ""
    calibration_source: str = "icar_standard"


@dataclass
class DiseaseResult:
    predicted_class: Optional[str] = None
    confidence: float = 0.0
    severity: str = "low"          # low | moderate | high
    actionable: bool = False        # set by decision.rules during Stage 1
    raw_class: Optional[str] = None
    normalized_disease: Optional[str] = None
    crop_detected: Optional[str] = None


@dataclass
class AdvisoryResult:
    scores: dict = field(default_factory=dict)
    preliminary_recommendation: str = "monitor"
    confidence: float = 0.0
    reason: str = ""


@dataclass
class MarketResult:
    price_change_pct: float = 0.0
    moving_average: float = 0.0
    market_score: float = 0.0
    signal: str = "hold"
    confidence: float = 0.0
    is_available: bool = True


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

    def log(self, event: str):
        self.execution_trace.append(event)
