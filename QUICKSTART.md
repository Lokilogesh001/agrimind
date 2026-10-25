# 🌾 AgriMind — Quickstart Guide

Welcome to **AgriMind**, an intelligent, observable multi-agent agricultural advisory platform. This guide provides instructions to run AgriMind locally on your machine in 3 simple steps.

---

## 1. Prerequisites

Ensure you have the following installed:
- **Python 3.10+** (tested up to 3.14): [python.org](https://www.python.org/)
- **Node.js 18+** & **npm**: [nodejs.org](https://nodejs.org/)

---

## 2. Setup (One-Time)

Open a terminal in the extracted `agrimind/` directory:

```bash
# 1. Copy the safe environment template
cp .env.example .env
# (On Windows Command Prompt: copy .env.example .env)

# 2. Install backend Python dependencies
pip install -r requirements.txt

# 3. Install frontend Node dependencies
npm install
```

> **Note:** The vision model checkpoint (`ml/artifacts/best.pt`) is already pre-packaged. External LLM API keys in `.env` are completely optional; if omitted, the system seamlessly engages its built-in deterministic rule explainer with zero downtime.

---

## 3. Start the Application

### Option A: Windows Automated Launcher (Recommended)
In PowerShell:
```powershell
.\start.ps1
```
*This starts the FastAPI backend on port 8000 and the Next.js frontend on port 3000 concurrently, checking process health and handling clean termination on `Ctrl+C`.*

### Option B: Cross-Platform Node Launcher (Mac / Linux / Windows)
```bash
npm run dev
```

---

## 4. Access the Platform

Open your web browser:
- **Web Dashboard:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Interactive Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **System Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 5. Verification & Tests

To verify that all components are functioning properly:

```bash
# Run the 8-tier production operational check
npm test

# Run the full automated test suite (126 tests)
pytest tests/ -v

# Run the scientific evaluation runner (16 ICAR scenarios + 18 data quality probes)
npm run evaluate
```
