# AgriMind — Project Structure

This document provides a comprehensive mapping of the AgriMind codebase, detailing the purpose of every directory and primary source file.

---

## 1. Directory Tree Overview

```text
D:\project\AGRIMIND\demo\agrimind_batch1\
├── .env                              # Active environment configuration
├── .env.example                      # Template environment configuration
├── .gitignore                        # Git exclusion rules
├── agrimind_local.db                 # SQLite local observability audit database
├── Dockerfile                        # Backend container definition
├── docker-compose.yml                # Multi-service container orchestration
├── main.py                           # Standalone CLI demonstration script
├── package.json                      # Root orchestration scripts & metadata
├── requirements.txt                  # Python backend dependencies
├── start.ps1                         # PowerShell runner script
├── BUILD_STATUS.md                   # Development batch historical audit notes
├── PROJECT_AUDIT.md                  # Comprehensive project health & audit report
├── README.md                         # Primary project introduction & quickstart
│
├── agents/                           # Specialist Domain Agents
│   ├── __init__.py
│   ├── advisory_agent.py             # Preliminary agronomic heuristic scoring
│   ├── disease_agent.py              # Phytosanitary vision inference & gate
│   ├── market_agent.py               # Agmarknet mandi price trend analyzer
│   ├── soil_agent.py                 # Macro-nutrient NPK deficiency evaluator
│   └── weather_agent.py              # Open-Meteo meteorological risk calculator
│
├── api/                              # FastAPI Gateway Layer
│   ├── __init__.py
│   └── main.py                       # REST API endpoints, CORS, and Pydantic schemas
│
├── data_sources/                     # External Integrations & Registries
│   ├── __init__.py
│   ├── crops.py                      # 32-crop registry, NPK targets, and stages
│   ├── geocoding.py                  # Open-Meteo reverse geocoding resolver
│   ├── market.py                     # Agmarknet price client
│   ├── soil.py                       # Soil texture and nutrient calibration tables
│   └── weather.py                    # Open-Meteo API forecast client
│
├── decision/                         # Deterministic Decision Core
│   ├── __init__.py
│   ├── evidence_engine.py            # Evidence synthesis & dynamic weighting
│   ├── evidence_quality.py           # Signal completeness & provenance scoring
│   ├── models.py                     # Dataclasses for decision outputs
│   ├── rules.py                      # P1-P5 conflict hierarchy & arbitration
│   ├── safety_guard.py               # Stage-1 Hard Safety Guards A-F
│   └── scoring.py                    # Decision Stability Score (DSS) formula
│
├── docs/                             # System Documentation Suite
│   ├── ARCHITECTURE.md               # High-level architecture & system design
│   ├── AGENTS.md                     # Technical reference for specialist agents
│   ├── AI_ORCHESTRATION.md           # LangGraph state machine & decision logic
│   ├── API_DOCUMENTATION.md          # REST API endpoints, schemas & examples
│   ├── CONFIGURATION.md              # Environment variables reference
│   ├── DATABASE.md                   # ER diagram & relational audit schema
│   ├── DEPLOYMENT.md                 # Local production & Docker deployment
│   ├── INSTALLATION.md               # Prerequisites & step-by-step setup
│   ├── OBSERVABILITY.md              # Execution trace & telemetry ledger
│   ├── PROJECT_OVERVIEW.md           # Project motivation, scope & problem statement
│   ├── PROJECT_STRUCTURE.md          # Complete repository file tree (this file)
│   ├── SYSTEM_WORKFLOW.md            # End-to-end execution flow & sequence diagrams
│   ├── TESTING.md                    # Pytest suite & verification criteria
│   └── TROUBLESHOOTING.md            # Solutions for common errors & configuration
│
├── knowledge/                        # Authoritative Institutional Knowledge Base
│   ├── ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf  # Source ICAR 2025 PDF
│   └── icar_chunks.json              # 1,219 cleaned & tagged ICAR chunk corpus
│
├── llm/                              # Explanatory Language Model Layer
│   ├── __init__.py
│   └── explainer.py                  # Multi-provider fallback router (xAI/Groq/Gemini)
│
├── ml/                               # Machine Learning & Computer Vision
│   ├── README.md
│   ├── __init__.py
│   ├── artifacts/
│   │   └── best.pt                   # Trained MobileNetV3 PyTorch weights (17.2 MB)
│   ├── disease_model.py              # MobileNetV3 model architecture definition
│   ├── plantvillage_dataset.py       # PlantVillage PyTorch Dataset loader
│   └── train_disease.py              # Transfer learning training pipeline
│
├── observability/                    # Persistence & Audit Ledger
│   ├── __init__.py
│   ├── database.py                   # SQLAlchemy 2.0 ORM models & helpers
│   └── schema.sql                    # PostgreSQL Supabase schema & RLS policies
│
├── orchestrator/                     # Multi-Agent Workflow Engine
│   ├── __init__.py
│   ├── graph.py                      # LangGraph StateGraph pipeline builder
│   └── state.py                      # AdvisoryState dataclass definition
│
├── rag/                              # Retrieval-Augmented Generation (RAG)
│   ├── README.md
│   ├── __init__.py
│   ├── icar_ingest.py                # ICAR PDF extraction & chunk parser
│   ├── metadata.py                   # Chunk tagging & metadata extractor
│   └── retriever.py                  # TF-IDF candidate search & metadata reranker
│
├── scripts/                          # Automation & Lifecycle Runners
│   ├── clean.js                      # Cache & temporary file cleaner
│   ├── dev.js                        # ONE-command development runner (`npm run dev`)
│   ├── start.js                      # Production server runner (`npm start`)
│   └── verify_product.py             # Offline product sanity test script
│
├── tests/                            # Automated Verification Test Suite (130 Tests)
│   ├── __init__.py
│   ├── test_adaptive_evidence_novelty.py   # Evidence weighting tests (26)
│   ├── test_api_hardening.py               # Pydantic schema validation tests (4)
│   ├── test_graph_wiring.py                # LangGraph node connection tests (1)
│   ├── test_llm_observability.py           # LLM failover & token logging tests (5)
│   ├── test_orchestrator.py                # End-to-end orchestration tests (7)
│   ├── test_phase2_research_core.py        # DSS & stability tests (32)
│   ├── test_rag_quality.py                 # ICAR retrieval quality tests (6)
│   ├── test_refactor.py                    # Regression tests (7)
│   ├── test_repair_batch.py                # Edge-case repair tests (21)
│   └── test_v11_hardening.py               # Safety guard & P1-P5 tests (21)
│
└── web/                              # Next.js 16 (Turbopack) Web Application
    ├── package.json                  # Frontend dependencies (Next 16, React 19)
    ├── package-lock.json
    ├── tsconfig.json                 # TypeScript compiler options
    ├── next.config.ts                # Next.js build configuration
    ├── next-env.d.ts
    └── app/
        ├── globals.css               # Design system & responsive styles
        ├── layout.tsx                # Master page layout & HTML head
        └── page.tsx                  # Interactive agronomic dashboard UI
```

---

## 2. Directory Responsibilities

- **`agents/`:** Encapsulates autonomous specialist agents. Each agent functions independently, accepts normalized inputs, queries its data source, and returns an evidence dataclass with a self-reported confidence metric.
- **`api/`:** The presentation gateway. Hosts FastAPI REST endpoints, strictly validates input data types, handles multipart binary uploads, and serializes responses.
- **`decision/`:** The deterministic brain of AgriMind. Contains zero LLM code. Houses Stage-1 Hard Safety Guards (A–F), the P1–P5 conflict resolution engine, and the Decision Stability Score calculator.
- **`orchestrator/`:** Glues the agents and decision engine into a stateful workflow using LangGraph.
- **`rag/`:** Institutional knowledge grounding. Indexes the 2025 ICAR Kharif agro-advisories to retrieve scientific references without relying on LLM memory.
- **`llm/`:** Generates farmer-facing natural language explanations while preserving the decision computed by the decision engine.
- **`observability/`:** Database models and logging logic ensuring every execution, decision trail, and conflict is persisted.
- **`scripts/`:** Cross-platform Node.js lifecycle scripts enabling single-command startup (`npm run dev`), build, and teardown.
- **`web/`:** Responsive, production-grade Next.js 16 web interface featuring map geocoding, leaf image upload, conflict visualization, and feedback submission.
