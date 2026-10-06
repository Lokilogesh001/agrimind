# AgriMind — REST API Documentation

The AgriMind API is built with FastAPI (version 1.2.0) and serves both JSON and multipart form endpoints on port 8000. All request schemas use Pydantic models with `extra="forbid"`, which rejects undeclared or malicious fields.

Interactive Swagger documentation is available at `http://127.0.0.1:8000/docs` and ReDoc at `http://127.0.0.1:8000/redoc`.

---

## 1. Endpoints Overview

| Method | Endpoint | Purpose | Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Root service identification and version info. | None |
| `GET` | `/health` | Liveness and readiness health probe. | None |
| `GET` | `/api/crops` | Retrieves registry of 32 supported crops, aliases, and growth stages. | None |
| `GET` | `/api/location/search` | Geocoding search resolving village/mandi names to coordinates. | None |
| `POST` | `/api/advisory` | Core end-to-end multi-agent advisory generation (JSON payload). | None |
| `POST` | `/api/advisory/upload` | Multipart advisory generation with mobile leaf image classification. | None |
| `GET` | `/api/runs/{run_id}` | Complete relational observability audit trace retrieval. | None |
| `POST` | `/api/feedback` | Records field adoption, observed outcomes, and farmer reviews. | None |

---

## 2. Endpoint Details

### 2.1. `GET /`
Returns service identification.
- **Response `200 OK`:**
```json
{
  "message": "AgriMind API is running",
  "version": "1.2.0"
}
```

---

### 2.2. `GET /health`
Liveness probe checking database connectivity and service readiness.
- **Response `200 OK`:**
```json
{
  "status": "ok",
  "service": "agrimind-api",
  "version": "1.1.0"
}
```

---

### 2.3. `GET /api/crops`
Lists supported agricultural crops, regional aliases, categories, and valid growth stages.
- **Response `200 OK`:**
```json
{
  "crops": [
    {
      "id": "rice",
      "name": "Rice",
      "category": "Cereals",
      "aliases": ["paddy", "dhan", "rice (paddy)"],
      "common_regions": ["Punjab", "West Bengal", "Tamil Nadu", "Odisha"]
    },
    {
      "id": "wheat",
      "name": "Wheat",
      "category": "Cereals",
      "aliases": ["gehun", "sharbati"],
      "common_regions": ["Uttar Pradesh", "Punjab", "Haryana"]
    }
  ],
  "categories": ["Cereals", "Pulses", "Oilseeds", "Commercial", "Vegetables", "Fruits"],
  "stages": {
    "rice": ["seedling", "vegetative", "tillering", "panicle_initiation", "flowering", "maturity"]
  }
}
```

---

### 2.4. `GET /api/location/search?q={query}`
Performs reverse geocoding via Open-Meteo Geocoding API with offline fallback.
- **Query Parameter:** `q` (string, required, min length 2)
- **Response `200 OK`:**
```json
{
  "results": [
    {
      "name": "Coimbatore",
      "display_name": "Coimbatore, Tamil Nadu, India",
      "latitude": 11.0055,
      "longitude": 76.9661,
      "admin1": "Tamil Nadu",
      "country": "India",
      "source": "open_meteo_geocoding",
      "status": "RESOLVED"
    }
  ]
}
```

---

### 2.5. `POST /api/advisory`
Executes the full multi-agent advisory pipeline via JSON payload.

- **Request Headers:** `Content-Type: application/json`
- **Request Body Schema (`AdvisoryRequest`):**
```json
{
  "crop": "rice",
  "growth_stage": "vegetative",
  "lat": 11.0055,
  "lon": 76.9661,
  "location_name": "Coimbatore, Tamil Nadu, India",
  "n": 140.0,
  "p": 15.0,
  "k": 120.0,
  "soil_type": "clay loam",
  "sowing_date": "2026-06-15",
  "farm_area": 2.5,
  "irrigation_method": "flood"
}
```

- **Validation Rules:**
  - Extra fields are forbidden (`422 Unprocessable Content`).
  - `lat` must be within `[-90, 90]`.
  - `lon` must be within `[-180, 180]`.
  - `n`, `p`, `k` must be non-negative numbers.

- **Response `200 OK`:**
```json
{
  "run_id": "c5f7b1f3-6d88-49b5-8668-12a453dc098b",
  "recommendation": "delay",
  "explanation": "Recommendation: delay. Rainfall risk: 0.45 (MODERATE). Moderate rainfall risk increases uncertainty around immediate fertilizer application. Target phosphorus is deficient (15 kg/ha supplied vs 40 kg/ha benchmark). Delay chemical top-dressing until weather stabilizes.",
  "confidence": 0.6065,
  "decision_stability_score": 0.9538,
  "stability_level": "HIGH",
  "re_evaluation_trigger": "Re-evaluate during regular crop growth monitoring.",
  "execution_trace": [
    "Location resolved: Coimbatore, Tamil Nadu, India",
    "Weather Agent: Moderate rainfall probability detected (0.73)",
    "Soil Agent: Nitrogen optimal, Phosphorus deficient (0.62 deficiency)",
    "Decision: Weighted score computed -> DELAY fertilizer application",
    "Observability trace recorded to database"
  ],
  "conflicts": [],
  "icar_evidence": [],
  "audit": {
    "total_latency_ms": 1968.92,
    "weather_status": "AVAILABLE",
    "market_status": "UNAVAILABLE",
    "disease_status": "NOT_SUPPLIED"
  }
}
```

---

### 2.6. `POST /api/advisory/upload`
Multipart form upload enabling on-device PyTorch leaf disease diagnosis alongside agronomic parameters.

- **Request Headers:** `Content-Type: multipart/form-data`
- **Form Fields:**
  - `image`: Binary leaf image file (JPEG/PNG, max 10MB).
  - `crop`: Form string (e.g. `"tomato"`).
  - `growth_stage`: Form string (e.g. `"flowering"`).
  - `lat`: Form float (e.g. `11.0055`).
  - `lon`: Form float (e.g. `76.9661`).
  - `n`, `p`, `k`: Optional nutrient values.
- **Response `200 OK`:**
Returns the same structured payload as `/api/advisory`, with disease classification, predicted class, and phytosanitary treatment ICAR citations.

---

### 2.7. `GET /api/runs/{run_id}`
Retrieves the complete immutable audit trail for a historic run from the database.
- **Path Parameter:** `run_id` (UUID string)
- **Response `200 OK`:**
```json
{
  "run": {
    "run_id": "c5f7b1f3-6d88-49b5-8668-12a453dc098b",
    "crop": "Rice",
    "recommendation": "delay",
    "confidence": 0.6065,
    "decision_stability_score": 0.9538,
    "stability_level": "HIGH",
    "status": "completed",
    "total_latency_ms": 1968.92
  },
  "agent_logs": [
    {
      "agent_name": "weather",
      "status": "ok",
      "confidence": 0.85,
      "latency": 1060.07,
      "source": "open_meteo"
    }
  ],
  "decisions": [
    {
      "recommendation": "delay",
      "reason": "weighted_score",
      "confidence": 0.6065,
      "stability_score": 0.9538
    }
  ],
  "conflicts": [],
  "feedback": []
}
```

---

### 2.8. `POST /api/feedback`
Records farmer field outcome data.
- **Request Body Schema (`FeedbackRequest`):**
```json
{
  "run_id": "c5f7b1f3-6d88-49b5-8668-12a453dc098b",
  "farmer_action_taken": "Delayed fertilizer application as recommended",
  "outcome_reported": "Rainfall occurred next day; runoff and nutrient loss prevented.",
  "comment": "Accurate rainfall safety veto."
}
```
- **Response `200 OK`:**
```json
{
  "status": "saved",
  "run_id": "c5f7b1f3-6d88-49b5-8668-12a453dc098b"
}
```
