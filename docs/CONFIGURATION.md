# AgriMind — Configuration & Environment Variables

This document defines all configuration settings for AgriMind. Settings are loaded from the root `.env` file via `python-dotenv`. A template is provided in `.env.example`.

> **Security Rule:** Never commit real secrets or production API keys to git. The `.gitignore` file explicitly excludes `.env`.

---

## 1. Core Configuration (Required)

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///agrimind_local.db` | SQLAlchemy connection string. Defaults to local SQLite file. For PostgreSQL (e.g. Supabase), set to `postgresql+psycopg2://user:pass@host:5432/dbname`. |
| `DISEASE_MODEL_PATH` | `ml/artifacts/best.pt` | Relative or absolute path to the PyTorch MobileNetV3 weights file for plant leaf disease inference. |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated list of allowed origins permitted to query the FastAPI backend. |

---

## 2. External Data APIs (Optional / Defaults Provided)

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `OPEN_METEO_BASE_URL` | `https://api.open-meteo.com/v1/forecast` | Open-Meteo REST API endpoint for meteorological forecasts. Does not require an API key for standard usage. |
| `AGMARKNET_BASE_URL` | *(empty)* | Optional endpoint for live Agmarknet mandi commodity feeds. If left empty, the market agent operates in degraded / neutral mode. |

---

## 3. LLM Explanation Layer (Optional)

The core decision engine is 100% deterministic and does **not** require any LLM API keys to run. If LLM keys are omitted, AgriMind automatically uses its built-in rule-based template engine.

If external generative models are desired for richer vernacular explanations, supply any or all of the following:

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `XAI_API_KEY` | *(empty)* | API key for xAI (Grok). |
| `XAI_MODEL` | `grok-4.6` | Model identifier for xAI. |
| `GROQ_API_KEY` | *(empty)* | API key for Groq Cloud. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Model identifier for Groq. |
| `GEMINI_API_KEY` | *(empty)* | API key for Google Gemini. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model identifier for Gemini. |
| `LLM_PROVIDER_ORDER` | `xai,groq,gemini` | Comma-separated prioritized provider sequence for fallback routing. |
| `LLM_TIMEOUT_SECONDS` | `20` | Timeout threshold per provider attempt in seconds. |
| `LLM_RETRIES` | `2` | Number of retry attempts per provider before moving to the next. |

---

## 4. Frontend Configuration (`web/`)

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Target URL used by the Next.js client-side fetch calls to connect to the FastAPI gateway. |

---

## 5. Sample `.env` Configuration File

```ini
# Database & Core
DATABASE_URL=sqlite:///agrimind_local.db
DISEASE_MODEL_PATH=ml/artifacts/best.pt
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Weather & Market APIs
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1/forecast
AGMARKNET_BASE_URL=

# Optional LLM Explanation Layer (leave empty for deterministic mode)
XAI_API_KEY=
XAI_MODEL=grok-4.6
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
LLM_PROVIDER_ORDER=xai,groq,gemini
LLM_TIMEOUT_SECONDS=20
LLM_RETRIES=2
```
