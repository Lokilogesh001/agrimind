# AgriMind — Specialist Agents Documentation

AgriMind features five domain-specific specialist agents coordinated by a LangGraph orchestrator, accompanied by an explanatory LLM agent.

---

## 1. Weather Agent (`agents/weather_agent.py`)

### Purpose
Retrieves real-time atmospheric conditions and 7-day meteorological forecasts to evaluate precipitation risk, thermal stress, and spray drift hazards.

### Input Parameters
- `lat`: Latitude (float, $-90.0 \le \text{lat} \le 90.0$)
- `lon`: Longitude (float, $-180.0 \le \text{lon} \le 180.0$)
- `weather_override`: Optional dict used in automated test simulations.

### Processing Logic
1. **API Integration:** Queries `https://api.open-meteo.com/v1/forecast` for hourly and daily variables:
   - `precipitation_probability_max`
   - `precipitation_sum`
   - `temperature_2m_max`, `temperature_2m_min`
   - `wind_speed_10m_max`
2. **Rainfall Risk Formulation:**
   $$\text{RainfallRisk} = \min\left(1.0, \frac{\text{PrecipProb}}{100} \times 0.6 + \frac{\min(\text{PrecipSum}, 25.0)}{25.0} \times 0.4\right)$$
3. **Risk Categorization:**
   - $\text{RainfallRisk} \ge 0.70$: `CRITICAL` (Immediate application veto)
   - $0.40 \le \text{RainfallRisk} < 0.70$: `MODERATE`
   - $\text{RainfallRisk} < 0.40$: `LOW`
4. **Thermal Hazard Evaluation:** Checks for extreme heat ($> 38^\circ\text{C}$) or frost risk ($< 5^\circ\text{C}$).

### Output Schema (`WeatherData`)
```python
{
    "rainfall_risk": float,              # [0.0 - 1.0]
    "temperature_risk": float,           # [0.0 - 1.0]
    "irrigation_condition": str,        # "normal" | "delay" | "urgent"
    "fertilizer_condition": str,        # "normal" | "delay"
    "confidence": float,                 # Typically 0.85 when live API is available
    "reason": str,                       # Narrative summary
    "risk_level": str,                   # "LOW" | "MODERATE" | "HIGH" | "CRITICAL"
    "precipitation_probability": float,  # [0.0 - 1.0]
    "rainfall_amount_mm": float,         # Millimeters
    "status": str                        # "AVAILABLE" | "DEGRADED" | "OVERRIDDEN"
}
```

### Degraded & Offline Handling
If Open-Meteo is unreachable (DNS timeout, network failure), the agent gracefully falls back to a regional seasonal heuristic (`confidence = 0.50`, `status = "DEGRADED"`), ensuring the rest of the advisory pipeline never crashes.

---

## 2. Soil Agent (`agents/soil_agent.py`)

### Purpose
Quantifies macro-nutrient deficiencies (Nitrogen $N$, Phosphorus $P$, Potassium $K$), evaluates soil pH suitability, and flags moisture anomalies based on scientific crop standards.

### Input Parameters
- `crop`: Normalized crop identifier (e.g., `"rice"`, `"wheat"`, `"cotton"`)
- `growth_stage`: Phenological stage (e.g., `"vegetative"`, `"flowering"`, `"maturity"`)
- `n`, `p`, `k`: Available soil nutrients (kg/ha or mg/kg)
- `soil_type`: Soil texture classification (e.g., `"clay loam"`, `"sandy loam"`)
- `soil_moisture`: Soil volumetric moisture percentage

### Processing Logic
1. **Target Lookup:** Retrieves target NPK thresholds from `data_sources/crops.py` for the requested crop and growth stage.
2. **Deficiency Calculation:**
   $$\text{Deficiency}_i = \max\left(0.0, \frac{\text{Target}_i - \text{Supplied}_i}{\text{Target}_i}\right) \quad \text{for } i \in \{N, P, K\}$$
3. **Overall Deficiency Metric:**
   $$\text{Deficiency}_{overall} = 0.5 \cdot \text{Deficiency}_N + 0.3 \cdot \text{Deficiency}_P + 0.2 \cdot \text{Deficiency}_K$$
4. **Soil Texture Correction:** Clay soils apply an increased retention coefficient, while sandy soils increase leaching risk adjustments.

### Output Schema (`SoilData`)
```python
{
    "nitrogen_deficiency": float,        # [0.0 - 1.0]
    "phosphorus_deficiency": float,      # [0.0 - 1.0]
    "potassium_deficiency": float,       # [0.0 - 1.0]
    "overall_deficiency": float,         # [0.0 - 1.0]
    "nutrient_status": str,              # "MEASURED" | "DEFICIENT" | "OPTIMAL"
    "priority_nutrient": str,            # "nitrogen" | "phosphorus" | "potassium" | "none"
    "confidence": float,                 # 0.90 if NPK measured, 0.40 if regional fallback
    "targets": dict,                     # {"N": float, "P": float, "K": float}
    "status": str                        # "MEASURED" | "ESTIMATED"
}
```

---

## 3. Disease Agent (`agents/disease_agent.py` & `ml/disease_model.py`)

### Purpose
Classifies phytosanitary diseases and fungal/bacterial infections from smartphone leaf imagery using deep convolutional neural networks.

### Vision Architecture
- **Model Architecture:** Custom PyTorch MobileNetV3-Small transfer-learning classifier.
- **Model Weights:** Loaded from `ml/artifacts/best.pt` (17.2 MB).
- **Classes:** 38 crop disease classes derived from the PlantVillage taxonomy (Apple, Tomato, Corn, Potato, Grape, Pepper, etc.).

### Inference & Validation Pipeline
1. **Preprocessing:** Resizes input image to $224 \times 224$ pixels, normalizes with ImageNet mean `[0.485, 0.456, 0.406]` and std `[0.229, 0.224, 0.225]`.
2. **Softmax Scoring:** Computes class probability distribution.
3. **Hard Confidence Gate (0.60):** If top prediction probability $< 0.60$, the output is deemed uncertain:
   - `confidence_gate_passed = False`
   - `actionable = False`
   - Blocks automated chemical treatment recommendations.
4. **Crop Species Compatibility Check:** Verifies that the detected disease species matches the requested crop context (e.g., preventing a tomato blight diagnosis from being applied to a rice paddy).

### Output Schema (`DiseaseData`)
```python
{
    "predicted_class": str | None,       # Raw model class label
    "normalized_disease": str | None,    # Clean disease name (e.g., "Late Blight")
    "crop_detected": str | None,         # Host plant detected
    "confidence": float,                 # [0.0 - 1.0]
    "severity": str,                     # "none" | "low" | "moderate" | "high"
    "actionable": bool,                  # True only if confidence >= 0.60 and matched
    "confidence_gate_passed": bool,      # Gate indicator
    "crop_mismatch": bool,               # Incompatibility flag
    "status": str                        # "CONFIRMED" | "UNCERTAIN" | "NOT_SUPPLIED"
}
```

---

## 4. Market Agent (`agents/market_agent.py`)

### Purpose
Monitors commodity market spot prices and agricultural mandi trend movements to determine economic harvest timing and price momentum.

### Input Parameters
- `crop`: Target crop identifier.
- `current_price`: Latest spot price per quintal.
- `price_history`: Array of historical closing prices (up to 365 days).

### Processing Logic
1. Computes 7-day Simple Moving Average (SMA) and Exponential Moving Average (EMA).
2. Calculates price momentum ($\Delta P = \frac{P_{today} - P_{7d}}{P_{7d}}$).
3. Evaluates price volatility $\sigma$ across the observation window.
4. Generates market signal:
   - Strong upward trend ($\Delta P > +5\%$): `HOLD` / `DELAY_HARVEST`
   - Strong downward trend ($\Delta P < -5\%$): `SELL` / `EXPEDITE_HARVEST`
   - Sideways / neutral trend: `NEUTRAL`

### Output Schema (`MarketData`)
```python
{
    "price_change_pct": float,
    "moving_average": float,
    "market_score": float,               # [0.0 - 1.0]
    "signal": str,                       # "sell" | "hold" | "neutral"
    "confidence": float,                 # 0.80 if historical data supplied, 0.0 if missing
    "is_available": bool,
    "status": str                        # "AVAILABLE" | "UNAVAILABLE"
}
```

---

## 5. Advisory Agent (`agents/advisory_agent.py`)

### Purpose
Aggregates initial agent outputs and computes preliminary agronomic action scores prior to the centralized conflict resolution stage.

### Scoring Heuristics
Evaluates three base candidate actions:
- `apply_fertilizer`: Driven by soil deficiency and absence of adverse weather.
- `delay`: Driven by rainfall risk and saturated soil moisture.
- `monitor`: Default steady-state agronomic maintenance.

---

## 6. LLM Explainer Agent (`llm/explainer.py`)

### Purpose
Synthesizes the deterministic action, execution trace, and retrieved ICAR citations into an empathetic, clear, farmer-facing explanation.

### Architecture
- **Provider Chain:** Configurable via `LLM_PROVIDER_ORDER=xai,groq,gemini`.
- **System Prompt:** Strict instructions mandating:
  - Explanations must strictly reflect the deterministic recommendation.
  - No new chemical compounds or dosages may be invented.
  - References must cite verified ICAR advisory chunks.
- **Deterministic Fallback:** If all external API calls fail or timeout, an internal rule-based template engine formats the explanation with zero latency and zero failure rate.
