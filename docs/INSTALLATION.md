# AgriMind — Installation & Setup Guide

This guide provides copy-paste instructions for setting up, configuring, and launching the complete AgriMind platform on Windows, macOS, or Linux.

---

## 1. Prerequisites

Before starting, ensure your system has the following runtimes installed:

| Requirement | Minimum Version | Verified Version | Notes |
| :--- | :--- | :--- | :--- |
| **Node.js** | `v18.0.0` or higher | `v24.12.0` | Required for Next.js frontend and root orchestration |
| **npm** | `v9.0.0` or higher | `v11.19.1` | Node package manager |
| **Python** | `3.10` or higher | `3.14.2` | Required for FastAPI backend and PyTorch inference |
| **Git** | `2.30+` | Latest | Version control |

---

## 2. Step-by-Step Installation

### Step 1: Open Terminal in Project Root
Navigate to the root directory:
```bash
cd D:\project\AGRIMIND\demo\agrimind_batch1
```

### Step 2: Configure Environment Variables
Copy the template configuration file:
```bash
# Windows PowerShell
Copy-Item .env.example .env

# Linux / macOS / Git Bash
cp .env.example .env
```
*(The default `.env` is already configured for offline and local development with SQLite and public Open-Meteo weather APIs).*

### Step 3: Install Python Dependencies
Install required Python packages into your environment or virtual environment:
```bash
pip install -r requirements.txt
```
*(Key packages installed include `fastapi`, `uvicorn`, `langgraph`, `torch`, `torchvision`, `scikit-learn`, `pydantic`, `sqlalchemy`, and `pytest`).*

### Step 4: Install Node.js Dependencies
Run `npm install` in the project root:
```bash
npm install
```
*(The root `package.json` includes an automatic `postinstall` hook that installs dependencies for the Next.js frontend in `web/` automatically).*

---

## 3. The ONE-Command Startup

To launch the complete application (FastAPI backend + Next.js frontend):

```bash
npm run dev
```

### What Happens Automatically:
1. Detects your active Python environment.
2. Checks that `fastapi` and `uvicorn` are available.
3. Inspects ports 8000 and 3000 to prevent port conflict deadlocks.
4. Spawns the **FastAPI Backend** on `http://127.0.0.1:8000` (API Docs at `/docs`).
5. Spawns the **Next.js Web Frontend** on `http://localhost:3000`.
6. Streams color-coded output to your terminal (`[backend]` in cyan, `[frontend]` in magenta).
7. Waits for both services to become healthy before printing the ready banner.

**To stop all services cleanly**, simply press `Ctrl+C`. All child processes and ports will be released immediately without leaving orphaned background tasks.

---

## 4. Production Build & Execution

To test or deploy in production mode:

### 1. Build the Application
```bash
npm run build
```
*(Compiles the Next.js application using Turbopack into an optimized standalone static/SSR bundle).*

### 2. Start Production Servers
```bash
npm start
```
*(Launches production Uvicorn server and Next.js production server concurrently).*

---

## 5. Verification Commands

Verify system integrity at any time with the built-in test commands:

```bash
# Run the complete automated test suite (130 tests)
npm test

# Run the agronomic product verification suite
npm run test:product

# Run TypeScript type-checking
npm run lint

# Clean all temporary caches, __pycache__, and build artifacts
npm run clean
```
