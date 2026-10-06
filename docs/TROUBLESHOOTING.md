# AgriMind — Troubleshooting Guide

This guide provides targeted solutions for issues that may arise during installation, development, or live execution.

---

## 1. Startup & Runtime Issues

### 1.1. `npm run dev` Fails: Python Not Found
- **Symptom:** Terminal reports `[agrimind] ERROR: Python not found. Please install Python 3.10+.`
- **Cause:** Python is either not installed or not added to your system `PATH`.
- **Solution:**
  1. Verify Python installation by running `python --version` or `py -3 --version`.
  2. If using a virtual environment, activate it (`.venv\Scripts\activate` on Windows or `source .venv/bin/activate` on Linux/macOS) or ensure the `.venv` directory exists in the project root.

---

### 1.2. `npm run dev` Fails: Missing Python Dependencies
- **Symptom:** `[agrimind] ERROR: Missing Python dependencies (fastapi, uvicorn).`
- **Cause:** Dependencies from `requirements.txt` have not been installed in the active environment.
- **Solution:**
  ```bash
  pip install -r requirements.txt
  ```

---

### 1.3. Port 8000 or Port 3000 Already in Use
- **Symptom:** Server reports `EADDRINUSE` or port conflict warning.
- **Cause:** A previous instance of Uvicorn or Next.js did not terminate cleanly.
- **Solution:**
  The `scripts/dev.js` launcher automatically detects and frees occupied ports. To manually terminate lingering processes:
  - **Windows PowerShell:**
    ```powershell
    Get-NetTCPConnection -LocalPort 8000, 3000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
    ```
  - **Linux / macOS:**
    ```bash
    fuser -k 8000/tcp 3000/tcp
    ```

---

### 1.4. `npm run lint` Fails in `web/`
- **Symptom:** Next.js reports `Invalid project directory provided, no such directory: web/lint`.
- **Cause:** In Next.js 16+, `next lint` was removed from the core CLI.
- **Solution:**
  Use TypeScript type-checking directly:
  ```bash
  npm run lint
  ```
  *(Configured to execute `tsc --noEmit` in `web/`).*

---

## 2. API & Data Issues

### 2.1. HTTP `422 Unprocessable Content` on `/api/advisory`
- **Symptom:** Client receives `422 Unprocessable Entity` when submitting advisory requests.
- **Cause:** AgriMind uses strict Pydantic validation (`extra="forbid"`). Supplying undeclared field names (e.g., `soil_nitrogen` instead of `n`) causes schema rejection.
- **Solution:**
  Ensure the request body conforms exactly to `AdvisoryRequest`:
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
    "soil_type": "clay loam"
  }
  ```

---

### 2.2. Missing Disease Model Weights (`best.pt`)
- **Symptom:** Disease Agent reports model file missing or falls back to degraded mode.
- **Cause:** The PyTorch weights file `ml/artifacts/best.pt` is missing or the path in `DISEASE_MODEL_PATH` is incorrect.
- **Solution:**
  1. Confirm `ml/artifacts/best.pt` exists (17.2 MB).
  2. Verify `.env` contains:
     ```ini
     DISEASE_MODEL_PATH=ml/artifacts/best.pt
     ```

---

### 2.3. Open-Meteo Weather API Timeouts
- **Symptom:** Weather Agent reports `status = "DEGRADED"` with confidence `0.50`.
- **Cause:** Internet connection down or Open-Meteo API is unreachable.
- **Solution:**
  This is expected fallback behavior. The system automatically engages its internal seasonal meteorological heuristics to allow uninterrupted advisory generation.

---

### 2.4. LLM API Rate Limits or Quota Exhaustion
- **Symptom:** Log shows `[llm_explainer] status: degraded`.
- **Cause:** External API keys (xAI / Groq / Gemini) are missing, invalid, or out of quota.
- **Solution:**
  No action required. AgriMind's deterministic rule template automatically generates the complete explanation. If you wish to enable external LLM synthesis, ensure valid API keys are placed in `.env`.
