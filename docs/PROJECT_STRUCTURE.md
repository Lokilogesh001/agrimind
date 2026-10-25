# AgriMind — Project Structure

This document provides a comprehensive mapping of the AgriMind codebase, detailing the purpose of every directory and primary source file in the minimal production repository.

---

## 1. Directory Tree Overview

```text
D:\project\AGRIMIND\demo\agrimind_batch1\
├── .env                              # Active environment configuration (git-ignored)
├── .env.example                      # Template environment configuration with xAI/OpenAI settings
├── .gitignore                        # Git exclusion rules (preserves ml/artifacts/best.pt)
├── agrimind_local.db                 # SQLite local observability audit database
├── Dockerfile                        # Backend container definition
├── docker-compose.yml                # Multi-service container orchestration
├── main.py                           # Standalone CLI demonstration runner
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
│   └── main.py                       # REST API endpoints (/health, /health/model, /api/advisory)
│
├── data_sources/                     # External Integrations & Registries
│   ├── __init__.py
│   ├── crops.py                      # 32-crop registry, NPK targets, and stages
│   ├── geocoding.py                  # Open-Meteo reverse geocoding resolver
│   ├── market.py                     # Agmarknet price client
│   ├── soil.py                       # Soil texture and nutrient calibration tables
│   ├── stores.py                     # Fertilizer / seed dealer locator
│   ├── treatments.py                 # ICAR-verified chemical/cultural treatments & CIBRC dosages
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
│   ├── AGENTS.md                     # Technical reference for specialist agents
│   ├── AGENT_CONTRACTS.md            # Agent contract schemas & status semantics
│   ├── AI_ORCHESTRATION.md           # LangGraph state machine & decision logic
│   ├── API_DOCUMENTATION.md          # REST API endpoints, schemas & examples
│   ├── ARCHITECTURE.md               # High-level architecture & system design
│   ├── CONFIGURATION.md              # Environment variables reference
│   ├── DATABASE.md                   # ER diagram & relational audit schema
│   ├── DECISION_SAFETY.md            # Decision safety rules & conflict arbitration
│   ├── DEPLOYMENT.md                 # Local production & Docker deployment
│   ├── INSTALLATION.md               # Prerequisites & step-by-step setup
│   ├── OBSERVABILITY.md              # Execution trace & telemetry ledger
│   ├── PHASE_1_2_AUDIT.md            # Detailed remediation and hardening audit log
│   ├── PROJECT_OVERVIEW.md           # Project motivation, scope & problem statement
│   ├── PROJECT_STRUCTURE.md          # Complete repository file tree (this file)
│   ├── SYSTEM_WORKFLOW.md            # End-to-end execution flow & sequence diagrams
│   ├── TESTING.md                    # Verification guide & production test runner
│   ├── TROUBLESHOOTING.md            # Solutions for common errors & configuration
│   └── VERIFICATION_REPORT.md        # End-to-end integration & cleanup report
│
├── evaluation/                       # Scientific Evaluation & Validation Pipeline
│   ├── __init__.py
│   ├── evaluate_disease_model.py     # MobileNetV3 evaluation, leakage audit, Wilson CI & ECE calibration
│   ├── evaluate_advisory_benchmark.py # ICAR/TNAU/CIBRC 16-scenario agronomic benchmark runner
│   ├── evaluate_data_quality.py      # Real weather, market, soil, and geocoding resilience probes
│   ├── benchmarks/                   # Versioned Ground-Truth Agronomic Benchmarks
│   │   └── icar_advisory_ground_truth.json # 16 curated ICAR Kharif 2025 & CIBRC scenarios
│   ├── manifests/                    # Auditable Benchmark Manifests & Field Templates
│   │   ├── plantdoc_test_manifest.csv # Verified PlantDoc test manifest (236 images, 27 classes, CC BY 4.0)
│   │   └── external_test_manifest_template.csv # Field trial manifest template for agronomists
│   └── artifacts/                    # Machine-readable evaluation reports & logs (git-ignored)
│       ├── disease_evaluation_status.json
│       ├── disease_evaluation_results.json
│       ├── confusion_matrix.csv
│       ├── advisory_benchmark_report.json
│       ├── data_quality_report.json
│       └── evaluation_summary.json
│
├── knowledge/                        # Authoritative Institutional Knowledge Base
│   ├── ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf  # Source ICAR 2025 PDF
│   └── icar_chunks.json              # 1,219 cleaned & tagged ICAR chunk corpus
│
├── llm/                              # Explanatory Language Model Layer
│   ├── __init__.py
│   ├── config.py                     # Multi-provider configuration loader (OpenAI/xAI)
│   └── explainer.py                  # Resilient fallback chain with credential redaction
│
├── ml/                               # Machine Learning & Computer Vision
│   ├── README.md
│   ├── __init__.py
│   ├── artifacts/
│   │   └── best.pt                   # Verified MobileNetV3-Large checkpoint (17.2 MB, 38 classes)
│   ├── disease_model.py              # MobileNetV3 architecture, inference & bounds validation
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
│   └── state.py                      # AgriMindState dataclass and AgentResult contracts
│
├── rag/                              # Retrieval-Augmented Generation (RAG)
│   ├── README.md
│   ├── __init__.py
│   ├── icar_ingest.py                # ICAR PDF extraction & chunk parser
│   ├── metadata.py                   # Chunk tagging & metadata extractor
│   └── retriever.py                  # TF-IDF candidate search & metadata reranker
│
├── scripts/                          # Automation & Lifecycle Runners
│   ├── clean.js                      # Cache & temporary file cleaner (`npm run clean`)
│   ├── dev.js                        # ONE-command development runner (`npm run dev`)
│   ├── prepare_plantdoc_dataset.py   # PlantDoc test dataset extractor & manifest generator
│   ├── run_evaluation.py             # Unified master scientific evaluation runner (`npm run evaluate`)
│   ├── start.js                      # Production server runner (`npm start`)
│   └── verify_product.py             # 8-tier production verification suite (`npm test`)
│
├── tests/                            # Essential Combinatorial, Safety & Evaluation Test Suite (126 Tests)
│   ├── conftest.py                   # Pytest fixtures & isolated in-memory DB configuration
│   ├── test_agent_contracts.py       # Contract schemas, boundaries & execution timings
│   ├── test_api_and_observability.py # FastAPI endpoints, CORS, production overrides & DB ledger
│   ├── test_combinatorial_matrix.py  # 5-agent full status space & dual failure combinations
│   ├── test_disease_evaluation.py    # Vision classifier evaluation, manifests, leakage, CI & status machine
│   ├── test_fault_injection_and_properties.py # Property-based invariants, model/RAG/LLM fault injection
│   ├── test_market_provenance.py     # APMC live vs. cache vs. user-supplied price isolation
│   └── test_safety_thresholds.py     # Stage-1 guards, boundary thresholds & conflict rules
│
└── web/                              # Next.js 16 (Turbopack) Web Application
    ├── package.json                  # Frontend dependencies (Next 16, React 19, Lucide)
    ├── package-lock.json
    ├── tsconfig.json                 # TypeScript compiler options
    ├── next.config.ts                # Next.js build configuration
    ├── next-env.d.ts
    └── app/
        ├── globals.css               # Design system & responsive styles
        ├── layout.tsx                # Master page layout & HTML head
        ├── page.tsx                  # Interactive agronomic dashboard UI
        └── components/               # Modular UI widgets
            ├── ActionPlan.tsx
            ├── AuditPanel.tsx
            ├── DecisionChangeTriggers.tsx
            ├── DecisionSignals.tsx
            ├── DiseaseActionCard.tsx
            ├── EvidencePanel.tsx
            ├── FarmInputForm.tsx
            ├── FeedbackCard.tsx
            ├── LeafUpload.tsx
            ├── PriceCard.tsx
            ├── WeatherCard.tsx
            └── WhyDecisionCard.tsx
```

---

## 2. Directory Responsibilities

- **`agents/`:** Encapsulates autonomous specialist agents. Each agent accepts normalized inputs, queries its data source, validates its output against the standardized `AgentResult` contract, and reports explicit status semantics.
- **`api/`:** The presentation gateway. Hosts FastAPI REST endpoints, strictly validates input data types, protects against arbitrary override injection in production, and reports model readiness.
- **`decision/`:** The deterministic brain of AgriMind. Contains zero LLM code. Houses Stage-1 Hard Safety Guards (A–F), the P1–P5 conflict resolution engine, and the Decision Stability Score calculator.
- **`orchestrator/`:** Glues the agents and decision engine into a stateful workflow using LangGraph StateGraph.
- **`rag/`:** Institutional knowledge grounding. Indexes the 2025 ICAR Kharif agro-advisories to retrieve scientific references without relying on LLM memory.
- **`llm/`:** Generates farmer-facing natural language explanations via OpenAI $\rightarrow$ xAI Grok $\rightarrow$ Deterministic Template fallback while strictly preserving the authoritative decision.
- **`observability/`:** Database models and logging logic ensuring every execution, decision trail, and conflict is persisted.
- **`evaluation/`:** Reproducible scientific evaluation pipeline. Houses the MobileNetV3 disease classifier evaluation harness with PlantDoc cross-dataset benchmarking, Expected Calibration Error (ECE), Wilson 95% confidence intervals, and leakage detection; the 16-scenario ICAR/TNAU/CIBRC agronomic benchmark runner; external data resilience probes; and machine-readable artifact generation.
- **`scripts/`:** Cross-platform Node.js and Python lifecycle scripts enabling single-command startup (`npm run dev`), build, and teardown, alongside the 8-tier verification suite (`npm test`), the PlantDoc dataset preparer, and the master evaluation runner (`npm run evaluate`).
- **`tests/`:** The 126-test comprehensive validation suite. Validates agent contracts, the exhaustive 32 binary failure combinations, multi-agent interactions, boundary thresholds, market provenance isolation, fault injection, property-based invariants, disease evaluation pipeline integrity, and API endpoints.
- **`web/`:** Responsive, production-grade Next.js 16 web interface featuring map geocoding, leaf image upload, conflict visualization, and feedback submission.

