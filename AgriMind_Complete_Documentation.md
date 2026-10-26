# AGRIMIND: Complete System Architecture, Modules, Operations & Technical Reference

> **Document Version:** 2.0.0  
> **Release Date:** October 2026  
> **Repository:** `d:\project\AGRIMIND\demo\agrimind_batch1`  
> **Target Audience:** Systems Architects, Agronomy Researchers, ML Engineers, Full-Stack Developers, and DevOps Specialists  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Complete Project Structure](#3-complete-project-structure)
4. [End-to-End Workflow](#4-end-to-end-workflow)
5. [AI and Specialist Agent Design](#5-ai-and-specialist-agent-design)
6. [Disease Detection Model & Vision System](#6-disease-detection-model--vision-system)
7. [Data Sources & External Integrations](#7-data-sources--external-integrations)
8. [RAG and Agricultural Knowledge Engine](#8-rag-and-agricultural-knowledge-engine)
9. [Decision Safety, Guardrails & Explainability](#9-decision-safety-guardrails--explainability)
10. [Observability, Telemetry & Persistence](#10-observability-telemetry--persistence)
11. [API Reference & Route Specifications](#11-api-reference--route-specifications)
12. [Frontend Architecture & Components](#12-frontend-architecture--components)
13. [Environment Configuration](#13-environment-configuration)
14. [Installation & Setup Guide](#14-installation--setup-guide)
15. [Practical Usage Examples](#15-practical-usage-examples)
16. [Model Evaluation, Benchmarking & Training](#16-model-evaluation-benchmarking--training)
17. [Performance, Hardware & Deployment](#17-performance-hardware--deployment)
18. [Troubleshooting & Diagnostics](#18-troubleshooting--diagnostics)
19. [Security, Privacy & Open-Source Licensing](#19-security-privacy--open-source-licensing)
20. [Known Limitations & Roadmap](#20-known-limitations--roadmap)
21. [Glossary & References](#21-glossary--references)

---

## 1. Project Overview

### 1.1 Project Title and Purpose
**AgriMind** is an autonomous multi-agent agricultural decision intelligence and diagnostic platform designed to provide smallholder and commercial farmers with hyper-local, multimodal, and agronomically safe crop management advisories.

Modern farming requires synthesizing disparate and rapidly fluctuating environmental, biological, and economic signals:
- Changing weather conditions that dictate agrochemical wash-off risk.
- Chemical soil nutrient balances ($N, P, K$) that govern fertilizer absorption.
- Foliar pathogen infections that require timely and precise diagnostic interventions.
- Regional agricultural market (mandi) spot prices and arrival volumes that govern harvest timing.

AgriMind reconciles these disparate factors into a cohesive, deterministic operational plan, grounded by verified agronomic literature and explained through safe, hallucination-resistant language models.

### 1.2 Problem Statement
Conventional agricultural advisory systems typically suffer from three fundamental architectural flaws:
1. **Siloed Single-Task Models:** A vision model might detect *Tomato Early Blight* with high confidence and instruct the farmer to apply copper fungicide immediately. However, if that model is unaware that a 35 mm heavy rainfall event will occur within three hours, the chemical wash-off will waste farmer capital and cause chemical runoff into local waterways.
2. **Uncalibrated Hallucination in Generative AI:** Pure LLM-based agricultural chatbots hallucinate chemical dosages, prescribe restricted synthetic chemicals, or offer vague suggestions lacking local agroclimatic context.
3. **Black-Box Opacity:** Farmers and agricultural extension officers distrust systems that cannot explain *why* a particular recommendation was reached, *which* agent voted for it, and *what* specific weather or soil condition would cause the recommendation to reverse.

### 1.3 Objectives
- **Multimodal Synthesis:** Concurrently ingest tabular farm data, GPS/geocoded locations, live atmospheric telemetry, stoichiometric soil test reports, and leaf photos.
- **Deterministic Agronomic Safety:** Enforce hard agronomic veto rules (such as rainfall safety overrides, low-confidence diagnostic gates, and crop mismatch guards) before any advice reaches a farmer.
- **Transparent Explainability:** Produce quantitative metrics for **Decision Stability (DSS)** and **Evidence Quality (EQS)** alongside an immutable audit trail of agent interactions and conflict resolutions.
- **Edge & Offline Resilience:** Provide high-speed local inference, cached regional datasets, and deterministic template fallback generation when internet connectivity is degraded or absent.

### 1.4 Target Users
- **Smallholder & Commercial Farmers:** Needing clear, actionable daily field instructions (e.g., whether to irrigate, spray fungicide, apply urea, or hold harvest).
- **Agricultural Extension Workers & Agronomists:** Requiring auditable decision traces, NPK balance calculations, and ICAR-backed treatment citations.
- **Agri-Tech Enterprises & Co-operatives:** Integrating standardized RESTful agricultural intelligence endpoints into farmer-facing mobile applications and supply chain portals.

### 1.5 Scope and Limitations
AgriMind currently focuses on 12 major crop categories across 38 foliar disease conditions. It operates across India's regional agroclimatic zones with dynamic geocoding support. 

*Limitation:* AgriMind provides decision support. It does not replace on-site physical soil laboratory testing or statutory agricultural advisory bodies. Agrochemical prescriptions must always be verified against local statutory label permits.

### 1.6 Architectural Contrast: AgriMind vs. Single-Model Pipelines

| Dimension | Conventional Single-Model Pipeline | Pure LLM Chatbot | AgriMind Multi-Agent Platform |
| :--- | :--- | :--- | :--- |
| **Decision Authority** | Monolithic neural network classification | Unconstrained generative text completion | **Deterministic Agronomic Safety Guard & Rule Engine** |
| **Conflict Handling** | Silent averaging or single-domain blindness | Semantic smoothing over contradictory prompts | **Explicit Multi-Agent Conflict Detection & Priority Arbitration** |
| **Weather Awareness** | None (pure computer vision) | Weak (unverified web search or outdated training data) | **Live Open-Meteo API with Precipitation Risk & Runoff Veto** |
| **Soil Integration** | Disconnected tabular script | Qualitative general advice | **Stoichiometric NPK Balance with Deficit Modeling** |
| **Explainability** | Heatmaps (Grad-CAM) showing pixels | Conversational text without source grounding | **Dual-Metric (DSS/EQS), Agent Contribution Graph & Audit Logs** |
| **Offline Safety** | Requires model weights; crashes if weights missing | Completely inoperable without API connectivity | **Graceful Degraded States & Deterministic Template Explainer** |

---

## 2. System Architecture

### 2.1 High-Level Architecture Overview
AgriMind follows a decoupled, blackboard-style multi-agent orchestration architecture. The system separates **evidence collection**, **agronomic decision-making**, **evidence retrieval**, and **natural language synthesis** into distinct operational stages.

```mermaid
flowchart TD
    subgraph ClientLayer["Client & Ingestion Layer"]
        UI["Next.js 16 Web Dashboard\n(App Router + React 19)"]
        API["FastAPI Gateway (Port 8000)\n(Request Validation & Image Security)"]
    end

    subgraph SpecialistAgents["Autonomous Specialist Agents (Parallel Execution)"]
        WA["Weather Agent\n(Open-Meteo Forecast & Rain Risk)"]
        SA["Soil Agent\n(NPK Stoichiometry & Deficit)"]
        DA["Disease Vision Agent\n(DINOv2 LoRA / MobileNetV3)"]
        MA["Market Agent\n(Agmarknet Modal Price Trends)"]
        AA["Advisory Agent\n(Agronomic Baseline Rules)"]
    end

    subgraph CoreEngine["Deterministic Decision & Safety Core"]
        ORCH["Orchestrator Graph\n(Blackboard State Accumulator)"]
        RULE["Adaptive Evidence Engine\n(Conflict Detection & Arbitration)"]
        GUARD["Agronomic Safety Guard\n(Hard Veto Rules A through F)"]
        METRICS["Metrics Calculator\n(DSS & EQS Scores + Triggers)"]
    end

    subgraph KnowledgeLayer["Grounded Knowledge & Explanation"]
        RAG["Hybrid ICAR RAG Engine\n(BM25 + Regional Agroclimatic Reranking)"]
        LLM["Multi-Provider LLM Explainer\n(OpenAI -> xAI Grok -> Template)"]
    end

    subgraph PersistenceLayer["Observability & Storage"]
        DB[("Observability Store\n(SQLite agrimind_local.db / Supabase Postgres)")]
        STORES["Nearby Agricultural Stores\n(OpenStreetMap Overpass Engine)"]
    end

    UI -->|JSON / Multipart Form| API
    API --> ORCH
    ORCH -->|Parallel Dispatch| WA & SA & DA & MA & AA
    WA & SA & DA & MA & AA -->|Agent Evidence & Confidence| ORCH
    ORCH --> RULE
    RULE --> GUARD
    GUARD --> METRICS
    METRICS --> RAG
    RAG --> LLM
    LLM --> API
    API --> UI

    RULE -.->|Log Conflicts & Decisions| DB
    ORCH -.->|Log Agent Telemetry & Latency| DB
    API -.->|Query Geocoded Stores| STORES
```

### 2.2 Core Module Responsibilities
- **`agents/`**: Houses independent domain agents that ingest raw contextual data and emit typed evidence dictionaries with bounded confidence scores ($0.0 \le c \le 1.0$).
- **`api/`**: Exposes FastAPI endpoints, handles CORS, validates image uploads via PIL verification, and shapes JSON responses.
- **`data_sources/`**: Contains connectors and clients for external REST APIs, local geocoding caches, soil balance algorithms, crop phenology registries, and chemical treatment mappings.
- **`decision/`**: Implements the deterministic core: weighted multi-criteria scoring, conflict detection, the 6 hard agronomic safety rules, Decision Stability Score (DSS), and Evidence Quality Score (EQS).
- **`llm/`**: Manages the explanation pipeline. Formulates strictly constrained system prompts and executes failover across OpenAI, xAI Grok, and deterministic templates.
- **`ml/`**: Manages computer vision models for crop foliar diagnosis, including model registry, pre-processing, inference adapters, and test-time augmentation.
- **`observability/`**: Manages database sessions, table creation, agent latency logging, decision trails, and feedback persistence.
- **`orchestrator/`**: Coordinates agent execution, manages shared state (`AdvisoryState`), and routes state through the decision pipeline.
- **`rag/`**: Implements metadata-aware semantic retrieval over the 2025 ICAR Agro-Advisories corpus.
- **`web/`**: Next.js 16 frontend containing 19 reactive components for farm parameter input, leaf image uploads, live decision visualization, and store locators.

---

## 3. Complete Project Structure

Below is the verified structural tree of the clean core package:

```
AgriMind_Core_Modules/
│
├── agents/                     # Specialist Domain Agents
│   ├── __init__.py
│   ├── advisory_agent.py       # Agronomic baseline treatment generator
│   ├── disease_agent.py        # Vision inference agent with crop mismatch check
│   ├── market_agent.py         # Mandi price trend and arrival analyzer
│   ├── soil_agent.py           # Stoichiometric NPK deficit evaluator
│   └── weather_agent.py        # Atmospheric precipitation risk evaluator
│
├── api/                        # REST API Application Layer
│   ├── __init__.py
│   └── main.py                 # FastAPI application, route handlers, serialization
│
├── data_sources/               # Telemetry Connectors & Agricultural Registries
│   ├── __init__.py
│   ├── crops.py                # 12-crop taxonomy and phenological stage registry
│   ├── geocoding.py            # Open-Meteo forward geocoding & regional centroids
│   ├── market.py               # Agmarknet mandi market data client & heuristics
│   ├── soil.py                 # Soil nutrient models and stoichiometric balances
│   ├── stores.py               # OpenStreetMap Overpass agro-input store locator
│   ├── treatments.py           # Chemical, biological & cultural treatment database
│   └── weather.py              # Open-Meteo precipitation & temperature client
│
├── decision/                   # Deterministic Agronomic Safety Core
│   ├── __init__.py
│   ├── evidence_engine.py      # Adaptive evidence collector & DSS scoring engine
│   ├── evidence_quality.py     # Multi-factor Evidence Quality Score (EQS)
│   ├── models.py               # Dataclasses (ConflictSpec, Decision, ActionStr)
│   ├── rules.py                # Conflict resolution entrypoint & threshold constants
│   ├── safety_guard.py         # Agronomic Safety Guard (Rules A through F)
│   └── scoring.py              # Stage 2 weighted multi-criteria scoring
│
├── knowledge/                  # Runtime Agricultural Knowledge Assets
│   └── icar_chunks.json        # Pre-chunked ICAR 2025 Advisory corpus (2.36 MB)
│
├── llm/                        # Source-Grounded Explanation Engine
│   ├── __init__.py
│   ├── config.py               # LLM provider configuration & credential sanitizer
│   └── explainer.py            # Failover chain: OpenAI -> Grok -> Deterministic Template
│
├── ml/                         # Computer Vision Disease Diagnosis System
│   ├── __init__.py
│   ├── artifacts/              # Model Checkpoints & Manifests
│   │   ├── MODEL_MANIFEST.json # Checkpoint specifications, SHA-256 hashes, metrics
│   │   ├── MODELS_README.md    # Offline setup guide & hardware requirements
│   │   └── dinov2_lora_r4_b4_best.pt # Champion LoRA checkpoint (88.48 MB, SHA-256: 8ae555c2...)
│   ├── dinov2_adapter.py       # DINOv2 LoRA predictor, crop gating & ambiguity logic
│   ├── disease_model.py        # MobileNetV3-Large rollback predictor
│   ├── model_registry.py       # Vision model registry and resolver
│   ├── plantvillage_dataset.py # 38-class taxonomic mapping & normalization constants
│   ├── train_disease.py        # MobileNetV3 training pipeline
│   └── train_field_finetune.py # DINOv2 LoRA training and adaptation script
│
├── observability/              # Observability, Telemetry & Persistence
│   ├── __init__.py
│   ├── database.py             # SQLAlchemy ORM, SQLite local default, Supabase Postgres
│   └── schema.sql              # Canonical SQL DDL for observability tables
│
├── orchestrator/               # Workflow Orchestration Engine
│   ├── __init__.py
│   ├── graph.py                # Execution graph, parallel dispatch, conflict logging
│   └── state.py                # AdvisoryState dataclass & state transitions
│
├── rag/                        # Retrieval-Augmented Generation Engine
│   ├── __init__.py
│   ├── icar_ingest.py          # PDF document ingestion and chunking utility
│   ├── metadata.py             # ICAR chunk metadata schema & regional zone tags
│   └── retriever.py            # Hybrid BM25 retriever with regional agroclimatic reranker
│
├── web/                        # Next.js 16 Web Dashboard Application
│   ├── app/
│   │   ├── components/         # 19 Modular React 19 UI Components
│   │   │   ├── ActionPlan.tsx
│   │   │   ├── AdvisoryHero.tsx
│   │   │   ├── AgentContributions.tsx
│   │   │   ├── AuditPanel.tsx
│   │   │   ├── DecisionChangeTriggers.tsx
│   │   │   ├── DecisionPath.tsx
│   │   │   ├── DecisionSignals.tsx
│   │   │   ├── DiseaseActionCard.tsx
│   │   │   ├── EvidencePanel.tsx
│   │   │   ├── FarmContextCard.tsx
│   │   │   ├── FarmInputForm.tsx
│   │   │   ├── FeedbackCard.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── NearbyStoresCard.tsx
│   │   │   ├── NutrientSupportCard.tsx
│   │   │   ├── OrchestrationLoader.tsx
│   │   │   ├── PriceCard.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   └── WhyDecisionCard.tsx
│   │   ├── globals.css         # Modern design tokens, dark mode, animations
│   │   ├── layout.tsx          # Root HTML layout and metadata
│   │   └── page.tsx            # Reactive dashboard controller
│   ├── next.config.ts          # Next.js configuration
│   ├── package.json            # Node.js dependencies (Next 16, React 19, Lucide)
│   ├── package-lock.json       # Pinned npm dependency lockfile
│   └── tsconfig.json           # TypeScript configuration
│
├── .env.example                # Configuration template with safe defaults
├── .gitignore                  # Git exclusions for venv, build caches, and databases
├── Dockerfile                  # Container definition for FastAPI backend
├── docker-compose.yml          # Multi-container orchestration (Backend + Frontend)
├── main.py                     # CLI verification script executing 3 test scenarios
├── package.json                # Root package configuration
├── requirements.txt            # Python dependencies (FastAPI, PyTorch, Transformers)
├── start.ps1                   # Single-command automated startup script for Windows
├── start.sh                    # Single-command automated startup script for Linux/macOS
├── PACKAGE_CONTENTS.md         # Package inclusions, exclusions, and quick-start guide
└── AgriMind_Complete_Documentation.md # This comprehensive technical manual
```

---

## 4. End-to-End Workflow

When a request reaches AgriMind (via JSON payload or multipart form with a leaf photo), it transitions through 10 sequential stages:

```
[1. API Ingestion & Validation]
               │
               ▼
[2. Farm & Crop Context Resolution]
               │
               ▼
[3. Atmospheric & Geocoding Telemetry]
               │
               ▼
[4. Soil Stoichiometry & NPK Deficit]
               │
               ▼
[5. Leaf Vision Inference & Pathology Diagnosis]
               │
               ▼
[6. Parallel Evidence Aggregation & Safety Vetoes (Stage 1)]
               │
               ▼
[7. Multi-Criteria Scoring & Synthesis (Stage 2)]
               │
               ▼
[8. Market Intelligence & Harvest Timing]
               │
               ▼
[9. RAG Knowledge Retrieval & LLM Explanation]
               │
               ▼
[10. Audit Persistence & User Interface Display]
```

### Step 1: API Validation & Security Sanitization
The FastAPI gateway receives the request. If an image is present, `_read_valid_image()` checks that the payload is $\le 5\text{ MB}$, validates MIME types against `ALLOWED_IMAGE_TYPES` (`jpeg`, `png`, `webp`), and executes `Image.open().verify()` using PIL to catch malformed bytes. The temporary image is saved securely with automatic deletion upon request termination.

### Step 2: Farm and Crop Context Resolution
`data_sources/crops.py` normalizes crop names (e.g., mapping `"paddy"` $\to$ `"Rice"`, `"tamatar"` $\to$ `"Tomato"`). Growth stages are checked against `STAGE_REGISTRY` (`vegetative`, `flowering`, `fruiting`, `maturity`). If a text location is provided without GPS coordinates, `data_sources/geocoding.py` queries Open-Meteo Geocoding to resolve latitude and longitude.

### Step 3: Weather and Geocoding Retrieval
The `WeatherAgent` calls `data_sources/weather.py` using farm coordinates. It retrieves hourly precipitation probabilities, estimated rain amounts in mm, and temperature forecasts. It calculates `rainfall_risk` ($0.0 \le r \le 1.0$) and categorizes risk into `LOW`, `MODERATE`, `HIGH`, or `SEVERE`.

### Step 4: Soil Nutrient Analysis
The `SoilAgent` inspects nitrogen ($N$), phosphorus ($P$), and potassium ($K$) values. If provided, `data_sources/soil.py` evaluates elemental availability against stoichiometric requirements for the specific crop and growth stage, deriving an `overall_deficiency` score ($0.0 \le d \le 1.0$) and identifying the primary limiting nutrient. If NPK is omitted, `npk_available` is set to `False`.

### Step 5: Leaf-Image Disease Inference
If an image is uploaded, the `DiseaseAgent` invokes `ml/dinov2_adapter.py`. The image is resized to $224 \times 224$ and normalized using ImageNet parameters. The DINOv2-Small backbone extracts a 384-dimensional feature vector, which passes through Rank-4 LoRA layers on blocks 8–11 and a linear classification head. If `crop` is specified, crop-constrained filtering eliminates cross-crop false positives. If top class probability is $< 0.60$, the diagnosis is flagged as ambiguous.

### Step 6: Evidence & Safety Veto Checks (Stage 1)
All agent evidence is aggregated into `AdvisoryState`. The deterministic `safety_guard.py` evaluates Rules A through F:
- If `rainfall_risk >= 0.70`, a hard veto enforces `DELAY` regardless of soil nutrient deficits.
- If disease confidence $< 0.60$ or disease model is unavailable, chemical treatments are blocked.
- If crop mismatch is detected, disease-specific advice is blocked.

### Step 7: Fertilizer and Advisory Synthesis (Stage 2)
If no hard safety veto fires in Stage 1, `decision/scoring.py` evaluates surviving candidate actions (`apply_fertilizer`, `delay`, `monitor`) using weighted multi-criteria scoring:
$$S(a) = w_{\text{soil}} S_{\text{soil}}(a) + w_{\text{weather}} S_{\text{weather}}(a) + w_{\text{disease}} S_{\text{disease}}(a) + w_{\text{crop}} S_{\text{crop}}(a)$$
Weights: $w_{\text{soil}} = 0.35, w_{\text{weather}} = 0.30, w_{\text{disease}} = 0.15, w_{\text{crop}} = 0.20$.

### Step 8: Market Intelligence
The `MarketAgent` inspects spot price trends and arrival volumes. It computes a market timing score and determines whether market dynamics favor selling immediately or holding stock.

### Step 9: Final Advisory Compilation & Grounded RAG
The `KnowledgeRetriever` in `rag/retriever.py` searches `knowledge/icar_chunks.json` using the crop, growth stage, detected disease, and location. It scores chunks via BM25 and boosts regional matches. `llm/explainer.py` then passes this factual evidence to the LLM (or deterministic template) to formulate a clear, multi-section explanation for the farmer.

### Step 10: Observability Persistence & User Display
`observability/database.py` commits the run to `runs`, `agent_logs`, `decisions`, and `conflicts` tables. The serialized payload returns to the Next.js frontend, populating the interactive dashboard, metrics meters, and audit trails.

---

## 5. AI and Specialist Agent Design

Every agent in AgriMind is an autonomous specialist operating over a bounded domain. Agents emit standard dictionaries containing `status`, `confidence`, `evidence`, and domain-specific telemetry.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BLACKBOARD STATE ACCUMULATOR                   │
│                                                                        │
│  WeatherAgent   ──> {rainfall_risk: 0.83, status: AVAILABLE}           │
│  SoilAgent      ──> {overall_deficiency: 0.51, npk_available: True}    │
│  DiseaseAgent   ──> {predicted_class: "Early_blight", conf: 0.78}      │
│  MarketAgent    ──> {signal: "sell", score: 0.89}                      │
│  AdvisoryAgent  ──> {preliminary: "delay"}                              │
│                                                                        │
│                 ▼                                                      │
│  Stage 1 Veto Arbitration ──> Weather safety overrides Soil & Disease  │
│  Stage 2 Scoring           ──> Final Action: DELAY                     │
│  Safety Guard (Rules A-F)  ──> Confirmed DELAY, Log Conflict           │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Weather Agent (`agents/weather_agent.py`)
- **Purpose:** Ingest atmospheric telemetry and evaluate risks of agrochemical wash-off, leaching, and thermal stress.
- **Inputs:** `lat` (float), `lon` (float), or `weather_override` (dict for testing).
- **Outputs:** `rainfall_risk` ($0.0 \text{ to } 1.0$), `risk_level` (`LOW`, `MODERATE`, `HIGH`, `SEVERE`), `precipitation_probability` (%), `rainfall_amount_mm` (float), `freshness_status` (`REAL_DATA` or `STALE_CACHE`).
- **Dependencies:** `data_sources/weather.py`, Open-Meteo REST API.
- **Decision Authority:** Holds **Priority 1 veto power**. If `rainfall_risk >= 0.70`, chemical spraying or fertilizer top-dressing is deferred.
- **Failure Behavior:** If the network fails or times out, cached data is used if $< 15\text{ min}$ old. Otherwise, marks status as `UNAVAILABLE`, assumes a conservative neutral risk ($0.50$), and logs a confidence penalty to prevent artificially safe fertilizer approvals.

### 5.2 Soil Agent (`agents/soil_agent.py`)
- **Purpose:** Assess soil fertility and calculate chemical nutrient deficits for Nitrogen, Phosphorus, and Potassium.
- **Inputs:** `crop` (str), `growth_stage` (str), `n` (float), `p` (float), `k` (float), `soil_type` (str).
- **Outputs:** `nutrient_status` (`DEFICIENT`, `BALANCED`, `OPTIMAL`), `npk_available` (bool), `overall_deficiency` ($0.0 \text{ to } 1.0$), `priority_nutrient` (`N`, `P`, or `K`).
- **Dependencies:** `data_sources/soil.py`.
- **Decision Authority:** Recommends nutrient supplementation. If measured NPK is absent, Rule A prohibits exact chemical dosage.
- **Failure Behavior:** If NPK values are omitted, marks `npk_available = False`, provides general organic recommendations, and defers chemical dosage.

### 5.3 Disease Agent (`agents/disease_agent.py`)
- **Purpose:** Analyze crop foliar imagery, classify pathologies across 38 classes, and flag crop mismatches.
- **Inputs:** `image_path` (str), `selected_crop` (str), `disease_model` (str, optional).
- **Outputs:** `predicted_class` (str), `confidence` ($0.0 \text{ to } 1.0$), `crop_detected` (str), `crop_mismatch` (bool), `ambiguous` (bool), `top_alternatives` (list).
- **Dependencies:** `ml/dinov2_adapter.py`, `ml/disease_model.py`, `ml/model_registry.py`.
- **Decision Authority:** Triggers pathogen treatments. Governed by Rule B (blocked if confidence $< 0.60$) and Rule C (blocked if detected crop contradicts selected crop).
- **Failure Behavior:** If image is corrupted or missing weights, emits status `INVALID_IMAGE` or `MODEL_UNAVAILABLE`. Upstream decision engine falls back to non-chemical cultural practices.

### 5.4 Market Agent (`agents/market_agent.py`)
- **Purpose:** Ingest regional mandi prices and price histories to optimize harvest timing.
- **Inputs:** `current_price` (float), `price_history` (list[float]), `crop` (str).
- **Outputs:** `market_score` ($0.0 \text{ to } 1.0$), `signal` (`sell`, `hold`, `neutral`), `confidence` (float).
- **Dependencies:** `data_sources/market.py`.
- **Decision Authority:** Recommends commercial market actions. Subordinate to agronomic safety vetoes (cannot override weather or disease urgency).
- **Failure Behavior:** If market data is absent, uses seasonal moving averages and baseline historical MSP floors.

### 5.5 Advisory Agent (`agents/advisory_agent.py`)
- **Purpose:** Formulate the baseline preliminary agronomic action plan before conflict arbitration.
- **Inputs:** Intermediate states of Weather, Soil, and Disease agents.
- **Outputs:** `preliminary_action` (`apply_fertilizer`, `delay`, `monitor`, `disease_control`), `reason` (str).
- **Decision Authority:** Synthesizes initial recommendation; submitted to `rules.py` for Stage 1/2 arbitration.

### 5.6 LLM Explainer Agent (`llm/explainer.py`)
- **Purpose:** Synthesize evidence, decisions, safety constraints, and RAG knowledge into structured, plain-language farmer guidance.
- **Inputs:** Full immutable `AdvisoryState` and retrieved ICAR evidence chunks.
- **Outputs:** `LLMExplanationResult` with `structured_explanation` (sections: `summary`, `action_steps`, `safety_warnings`, `market_context`, `sources`).
- **Dependencies:** `openai`, `llm/config.py`.
- **Constraints:** **Zero decision authority.** The LLM cannot alter recommendations, safety vetoes, or chemical dosages. If all LLM APIs fail, the built-in Deterministic Template Explainer generates complete guidance instantly.

---

## 6. Disease Detection Model & Vision System

### 6.1 DINOv2-Small + Rank-4 LoRA Champion Architecture
AgriMind's default vision model employs Meta AI's self-supervised **DINOv2-Small** (`facebook/dinov2-small`) foundation model:
- **Backbone Architecture:** Vision Transformer (ViT-S/14), 12 transformer encoder blocks, 384 embedding dimensions, 6 heads, patch size 14.
- **Parameter Adaptation:** Low-Rank Adaptation (LoRA) applied to blocks 8, 9, 10, and 11 on the query ($W_q$) and value ($W_v$) projection matrices:
  $$W = W_0 + \Delta W = W_0 + \frac{\alpha}{r} (B \cdot A)$$
  where rank $r=4$, scaling factor $\alpha=8$, and dropout $p=0.05$.
- **Trainable Parameters:** Only ~156 KB of LoRA parameters and classifier weights are trained (18 tensors); the early transformer blocks remain frozen, preserving general semantic visual features. The complete saved checkpoint file `dinov2_lora_r4_b4_best.pt` is 88.48 MB (88,480,982 bytes) containing the integrated backbone and LoRA state dict.
- **Classification Head:** Linear layer projecting 384 dimensions to 38 output logits.

```
Input Image (224x224x3)
        │
        ▼
Patch Embedding (14x14 patches -> 256 tokens)
        │
        ▼
Transformer Blocks 0 to 7  [FROZEN DINOv2 Backbone]
        │
        ▼
Transformer Blocks 8 to 11 [Rank-4 LoRA Adapted: W_q, W_v]
        │
        ▼
CLS Token Pooling (384-dimensional representation)
        │
        ▼
Linear Classifier Head (384 -> 38 Classes) -> Softmax Probabilities
```

### 6.2 38-Class Taxonomic Mapping
The model classifies across 14 crops and 38 distinct conditions:
```
Apple___Apple_scab                  Corn_(maize)___Common_rust_         Squash___Powdery_mildew
Apple___Black_rot                   Corn_(maize)___Northern_Leaf_Blight Strawberry___Leaf_scorch
Apple___Cedar_apple_rust            Corn_(maize)___healthy              Strawberry___healthy
Apple___healthy                     Grape___Black_rot                   Tomato___Bacterial_spot
Blueberry___healthy                 Grape___Esca_(Black_Measles)        Tomato___Early_blight
Cherry___Powdery_mildew             Grape___Leaf_blight_                Tomato___Late_blight
Cherry___healthy                    Grape___healthy                     Tomato___Leaf_Mold
Orange___Haunglongbing              Peach___Bacterial_spot              Tomato___Septoria_leaf_spot
Peach___healthy                     Pepper__bell___Bacterial_spot       Tomato___Spider_mites_Two_spotted
Potato___Early_blight               Pepper__bell___healthy              Tomato___Target_Spot
Potato___Late_blight                Raspberry___healthy                 Tomato___Tomato_mosaic_virus
Potato___healthy                    Soybean___healthy                   Tomato___Tomato_Yellow_Leaf_Curl_Virus
Tomato___healthy
```

### 6.3 Preprocessing, Normalization & Image Validation
- **Resolution:** Resized and center-cropped to $224 \times 224$ pixels.
- **Normalization:** Standard ImageNet statistics:
  $$\mu = [0.485, 0.456, 0.406], \quad \sigma = [0.229, 0.224, 0.225]$$
- **Security Validation:** Enforces strict image file checks: MIME type verification (`image/jpeg`, `image/png`, `image/webp`), $5\text{ MB}$ size ceiling, and structural PIL image byte verification to prevent buffer exploits.

### 6.4 Crop-Constrained Diagnostics vs. Unconstrained Mode
In field settings, visual symptoms of different diseases can look alike across plant species (e.g., Tomato Early Blight vs. Potato Early Blight). AgriMind introduces **Crop-Constrained Diagnostics**:
- **Unconstrained Inference:** Evaluates probabilities across all 38 classes.
- **Crop-Constrained Inference:** When the farmer specifies the host crop (e.g., `"Tomato"`), the adapter masks out classes belonging to other crops and renormalizes probabilities over valid candidate classes:
  $$P(c_i \mid \text{crop} = K) = \frac{\exp(z_i)}{\sum_{j \in \text{classes}(K)} \exp(z_j)}$$
- **Crop Mismatch Flag:** If the unconstrained top prediction belongs to a different crop with high confidence ($> 0.70$), the system raises `crop_mismatch = True` and activates **Rule C**, preventing misdiagnoses caused by misidentified photos.

### 6.5 Verified Evaluation Benchmarks
The DINOv2-Small LoRA model was benchmarked against the MobileNetV3 baseline across multiple test sets:

| Evaluation Dataset | Metric | MobileNetV3 Baseline | DINOv2 LoRA Champion | Improvement |
| :--- | :--- | :---: | :---: | :---: |
| **Field Validation (Held-out)** | Top-1 Accuracy | 39.81% | **64.81%** | +25.00% |
| | Macro-F1 (27 represented classes) | 0.3760 | **0.6510** | +0.2750 |
| | Expected Calibration Error (ECE) | 0.1420 | **0.0573** | -59.6% (calibrated) |
| | Cross-Crop Confusion Rate | 18.52% | **10.19%** | -8.33% |
| **PlantDoc Field Test** | Unconstrained Accuracy | 44.07% | **56.78%** | +12.71% |
| | Macro-F1 | 0.4359 | **0.5532** | +0.1173 |
| | Crop-Constrained Accuracy | 59.32% | **72.46%** | +13.14% |
| **Independent Field Test** | Unconstrained Accuracy | 44.34% | **66.06%** | +21.72% |
| | Macro-F1 | 0.4236 | **0.6301** | +0.2065 |
| | Crop-Constrained Accuracy | 60.18% | **73.30%** | +13.12% |

*Interpretation Note:* These empirical metrics reflect performance on the benchmark datasets. Unconstrained accuracy accounts for complex field backgrounds and clutter. When the user's selected crop is verified, crop-constrained accuracy reaches **72.46% to 73.30%**.

### 6.6 MobileNetV3 Rollback Option
To ensure operational resilience, MobileNetV3-Large (`ml/artifacts/best.pt`, 17.2 MB, SHA-256: `c362915969e3d08c86cfa687bb3bbc51e2549be3ade3e0addb5bcc12560ed58e`) remains available as an immediate rollback model. It can be invoked on-demand via the API parameter `disease_model="production"` or the `.env` variable `DISEASE_MODEL_BACKBONE=production`.

---

## 7. Data Sources & External Integrations

AgriMind integrates verified external data providers with automatic local fallback mechanisms.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCE ORCHESTRATION                       │
│                                                                        │
│   Open-Meteo Weather API    ──> Hourly Precip, Temp, Risk Scoring      │
│   Open-Meteo Geocoding API  ──> Lat/Lon Search, Centroid Fallbacks     │
│   Agmarknet Mandi API       ──> Spot Prices, Volumes, Moving Averages  │
│   Overpass OSM API          ──> Verified Local Agrochemical Stores     │
│   ICAR Knowledge Corpus     ──> Chunked RAG Vector Retrieval           │
│   LLM Gateway (OpenAI/xAI)  ──> Multimodal Explanation Layer           │
└────────────────────────────────────────────────────────────────────────┘
```

### 7.1 Open-Meteo Weather & Geocoding APIs
- **Endpoints:**  
  `OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1/forecast`  
  `GEOCODING_BASE_URL=https://geocoding-api.open-meteo.com/v1/search`
- **Data Retrieved:** Hourly precipitation probability (%), precipitation amount (mm), 2-meter air temperature (°C), weather interpretation codes (WMO).
- **Authentication:** None required (free tier, no API keys).
- **Failure Strategy:** Disk-based cache with a 15-minute validity window. If unavailable, flags `weather_status = UNAVAILABLE`, assigns a conservative risk value ($0.50$), and triggers Rule E.

### 7.2 Agmarknet & Mandi Market Pricing
- **Endpoint:** Configurable via `AGMARKNET_BASE_URL`.
- **Data Retrieved:** Modal price (₹/quintal), daily arrivals (metric tonnes), primary district mandi name.
- **Failure Strategy:** Employs regional statutory Minimum Support Price (MSP) baselines combined with a historical 30-day moving average model.

### 7.3 Soil Data & Stoichiometric Nutrient Model
- **Mechanism:** Ingests soil test kit inputs: Nitrogen ($N$), Phosphorus ($P$), Potassium ($K$) in kg/ha or ppm, along with soil texture (Alluvial, Black, Clay, Loamy, Red, Sandy).
- **Calculation:** Compares available elemental NPK against standard crop uptake requirements across phenological growth stages:
  $$\Delta N = N_{\text{target}}(\text{crop}, \text{stage}) - N_{\text{measured}}$$
- **Failure Strategy:** If measurements are omitted, Rule A blocks exact chemical dosage and provides cultural/organic soil guidance.

### 7.4 OpenStreetMap Overpass Store Discovery
- **Endpoint:** `https://overpass-api.de/api/interpreter`
- **Query:** Geospatial query scanning for tags `shop=agrarian`, `shop=farm`, `shop=fertilizer`, `shop=trade` within a configurable radius ($10 \text{ to } 50\text{ km}$).
- **Output:** Returns verified store names, distances, phone numbers, and coordinates to help farmers source recommended inputs.

### 7.5 LLM Provider Chain & Masking
- **Primary:** OpenAI (`gpt-4o-mini`, controlled via `OPENAI_API_KEY`).
- **Secondary:** xAI Grok (`grok-2-latest`, via `XAI_API_KEY` at `https://api.x.ai/v1`).
- **Tertiary:** Deterministic Template Explainer (zero external dependencies).
- **Security:** Strict regex filters in `llm/config.py` sanitize logs, automatically redacting API keys (`sk-***`, `xai-***`, `Bearer ***`).

---

## 8. RAG and Agricultural Knowledge Engine

### 8.1 Document Ingestion & Chunking
AgriMind incorporates the official Indian Council of Agricultural Research (**ICAR**) advisory corpus:
- **Source:** *ICAR Kharif Agro-Advisories for Farmers 2025*.
- **Runtime Asset:** `knowledge/icar_chunks.json` (2.36 MB).
- **Chunk Structure:** Each chunk includes clean text, target crop, target growth stage, identified diseases, regional state/zone applicability, and ICAR source page citations.

```json
{
  "chunk_id": "icar_2025_tomato_early_blight_01",
  "crop": "Tomato",
  "growth_stage": "vegetative",
  "disease": "Early blight",
  "regions": ["south_india", "central_india"],
  "text": "For Early Blight management in Tomato, spray Mancozeb 75% WP @ 2.0 g/litre of water or Chlorothalonil 75% WP @ 2.0 g/litre...",
  "source_doc": "ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf",
  "page": 42
}
```

### 8.2 Hybrid Lexical & Regional Agroclimatic Reranker
The retrieval engine (`rag/retriever.py`) uses a weighted multi-factor scoring algorithm:
$$\text{Score} = w_{\text{crop}} S_{\text{crop}} + w_{\text{loc}} S_{\text{loc}} + w_{\text{stage}} S_{\text{stage}} + w_{\text{bm25}} S_{\text{bm25}} + w_{\text{rel}} S_{\text{rel}} + w_{\text{temp}} S_{\text{temp}}$$
- $w_{\text{crop}} = 0.30$: Matches crop synonyms (e.g., `"paddy"` $\leftrightarrow$ `"rice"`).
- $w_{\text{loc}} = 0.25$: Matches geographic zones (South, North, West, Central, East, North-East).
- $w_{\text{stage}} = 0.15$: Matches phenological growth stage.
- $w_{\text{bm25}} = 0.15$: BM25 token overlap on agronomic and pathological terms.
- $w_{\text{rel}} = 0.10$: Source credibility rating.
- $w_{\text{temp}} = 0.05$: Seasonal timeliness.

### 8.3 Citation Grounding
Retrieved knowledge chunks are passed directly into the explanation prompt. The LLM is instructed to cite these chunks explicitly (e.g., `[ICAR 2025, p. 42]`), providing users with direct references to authoritative literature.

---

## 9. Decision Safety, Guardrails & Explainability

```
                                  [Candidate Action from Stage 1/2]
                                                   │
         ┌─────────────────────────────────────────┴─────────────────────────────────────────┐
         ▼                                         ▼                                         ▼
   [Rule A: Soil]                           [Rule B: Disease]                         [Rule C: Match]
Missing NPK? Block dosage.             Conf < 0.60? Block treatment.            Crop mismatch? Block action.
         │                                         │                                         │
         └─────────────────────────────────────────┬─────────────────────────────────────────┘
                                                   │
         ┌─────────────────────────────────────────┴─────────────────────────────────────────┐
         ▼                                         ▼                                         ▼
   [Rule D: Weather]                         [Rule E: Stale Data]                      [Rule F: Conflict]
Rain Risk >= 0.70? Enforce DELAY.       Telemetry stale? Penalize Conf.          Agents disagree? Lower DSS.
         │                                         │                                         │
         └─────────────────────────────────────────┬─────────────────────────────────────────┘
                                                   │
                                                   ▼
                                  [Authoritative Final Advisory]
                                                   │
                       ┌───────────────────────────┴───────────────────────────┐
                       ▼                                                       ▼
        Decision Stability Score (DSS)                          Evidence Quality Score (EQS)
          Internal Agent Consistency                              Trustworthiness of Inputs
```

### 9.1 Deterministic Agronomic Safety Guard (Rules A through F)
Implemented in `decision/safety_guard.py`, the Safety Guard executes deterministic checks that cannot be overridden by statistical models:
- **Rule A (Soil Safety):** If measured NPK is absent, exact chemical fertilizer dosages are blocked; recommendations are limited to soil testing advice and organic compost.
- **Rule B (Disease Confidence Gate):** If disease confidence is $< 0.60$ or the model is unavailable, disease-specific chemical interventions are blocked.
- **Rule C (Crop Match Guard):** If the detected crop from the leaf image does not match the selected crop, disease treatments are blocked to prevent cross-crop errors.
- **Rule D (Weather Safety Veto):** If `rainfall_risk >= 0.70`, chemical spraying and fertilizer applications are blocked with an immediate **`DELAY`** directive.
- **Rule E (Data Freshness Guard):** If weather or disease telemetry is unverified or timed out, a confidence penalty is subtracted ($0.10 \text{ to } 0.15$).
- **Rule F (Conflict Resolution Guard):** If agents issue opposing recommendations, the recommendation defaults to a safe agronomic action (e.g., `monitor` or `delay`).

### 9.2 Decision Stability Score (DSS)
DSS evaluates internal consistency across agents and conflict arbitration ($0.0 \le \text{DSS} \le 1.0$):
$$\text{DSS} = 0.25 C_{\text{agent}} + 0.20 R_{\text{source}} + 0.15 T_{\text{temporal}} + 0.25 E_{\text{completeness}} + 0.15 A_{\text{agreement}} - (\text{Conflicts} \times 0.12)$$
- $\text{DSS} \ge 0.80$: **HIGH** (Stable, consistent, highly actionable).
- $0.60 \le \text{DSS} < 0.80$: **MODERATE** (Actionable with minor caution).
- $0.40 \le \text{DSS} < 0.60$: **LOW** (Significant missing data or minor conflict).
- $\text{DSS} < 0.40$: **INSUFFICIENT** (Severe conflicts or high missingness; action deferred).

### 9.3 Evidence Quality Score (EQS)
EQS measures the quality, precision, and timeliness of incoming data:
$$\text{EQS} = 0.20 Q_{\text{crop}} + 0.20 Q_{\text{loc}} + 0.15 Q_{\text{stage}} + 0.15 Q_{\text{source}} + 0.10 Q_{\text{time}} + 0.20 Q_{\text{complete}}$$
Classified as: **GOOD** ($\ge 0.75$), **MODERATE** ($0.55\text{--}0.74$), **LOW** ($0.35\text{--}0.54$), or **INSUFFICIENT** ($< 0.35$).

### 9.4 Decision Change Triggers
The system outputs specific conditions that would cause the current recommendation to change:
- *"Rainfall risk decreases below 0.30 (clears weather safety block)."*
- *"Measured NPK values are supplied (enables exact fertilizer dosage)."*
- *"High-confidence leaf image (> 0.60) confirms active pathogen infection."*

---

## 10. Observability, Telemetry & Persistence

### 10.1 Database Architecture
Implemented in `observability/database.py`, AgriMind uses an environment-aware SQLAlchemy abstraction:
- **Local Development:** Default SQLite database (`sqlite:///agrimind_local.db`).
- **Production:** Configurable PostgreSQL / Supabase instance via `DATABASE_URL`.
- **Thread Safety:** Configured with `check_same_thread=False` and lazy connection pooling.

### 10.2 Database Schema (`observability/schema.sql`)
1. **`runs`**: Captures top-level run metadata, inputs, coordinates, resolved location, DSS, EQS, and latencies.
2. **`agent_logs`**: Records every specialist agent call, inputs, outputs, status, confidence, latency in ms, and evidence sources.
3. **`decisions`**: Stores final recommendations, reasons, stability scores, and re-evaluation triggers.
4. **`conflicts`**: Logs every detected agent conflict, involved agents, severity, and resolution.
5. **`feedback`**: Farmer-reported outcomes, crop health improvements, and operational feedback.

---

## 11. API Reference & Route Specifications

The FastAPI application (`api/main.py`) exposes the following endpoints:

### 11.1 Health & Diagnostics
- **`GET /`**  
  Returns service status and API version: `{"status": "ok", "service": "agrimind-api", "version": "1.2.0"}`.
- **`GET /health`**  
  Standard readiness probe: `{"status": "ok", "service": "agrimind-api", "version": "1.1.0"}`.
- **`GET /health/model?model=dinov2_lora`**  
  Reports model status, checkpoint path, SHA-256 verification, and device placement (`cpu` or `cuda`).
- **`GET /health/models`**  
  Reports readiness status for all registered vision models (DINOv2 LoRA and MobileNetV3).

### 11.2 Agricultural Data & Location
- **`GET /api/crops`**  
  Returns the 12 supported crop categories, varieties, phenological growth stages, and normalization aliases.
- **`GET /api/location/search?q=Nashik`**  
  Performs forward geocoding using Open-Meteo, returning matching municipal locations with coordinates.
- **`GET /api/nearby-stores?lat=20.0&lon=73.78&radius=25`**  
  Queries OpenStreetMap Overpass for nearby verified agricultural suppliers and pesticide stores.

### 11.3 Advisory Generation Endpoints
- **`POST /api/advisory`**  
  Generates an advisory from JSON inputs (without leaf photo):
  ```json
  {
    "crop": "Tomato",
    "growth_stage": "vegetative",
    "location_name": "Nashik, Maharashtra",
    "lat": 19.9975,
    "lon": 73.7898,
    "n": 25.0,
    "p": 40.0,
    "k": 65.0,
    "current_price": 2200.0,
    "price_history": [1900, 2000, 2150, 2200]
  }
  ```
- **`POST /api/advisory/upload`**  
  Multipart form endpoint accepting both tabular parameters and a leaf photo file (`image`).
- **`POST /api/internal/test-advisory`**  
  Internal testing endpoint supporting synthetic overrides. Blocked when `ENVIRONMENT=production`.

### 11.4 Observability & Feedback
- **`GET /api/runs/{run_id}`**  
  Retrieves full execution audit trails, agent logs, decision metrics, and resolved conflicts for a run.
- **`POST /api/feedback`**  
  Submits farmer action logs and observed field outcomes.

---

## 12. Frontend Architecture & Components

The frontend is built with Next.js 16 (App Router) and React 19 in `web/`:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AGRIMIND WEB DASHBOARD                          │
│                                                                        │
│   Header ──> Branding, Mode Toggles, Server Connection Status          │
│   FarmInputForm ──> Crop, Stage, GPS/Location Search, NPK, Photo       │
│   OrchestrationLoader ──> Real-Time Multi-Agent Execution Pipeline     │
│   AdvisoryHero ──> Authoritative Recommendation & Safety Badges        │
│   DiseaseActionCard ──> Pathogen Probability, LoRA Confidence, Alts    │
│   NutrientSupportCard ──> Stoichiometric NPK Deficits & Dosage         │
│   DecisionSignals ──> Real-Time Weather Risk, Market Price Trends      │
│   ActionPlan ──> Step-by-Step Field Instructions & Chemical Safety     │
│   WhyDecisionCard ──> Grounded Agronomic Explanation & Citations       │
│   DecisionPath ──> Stage 1 Veto Trace & Stage 2 Scoring Breakdown      │
│   NearbyStoresCard ──> Mapped Verified Local Input Retailers           │
│   AuditPanel ──> Raw Agent Logs, Telemetry Latencies, Decision Trail   │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Reference (19 Modules in `web/app/components/`)
1. **`Header.tsx`**: Navigation, system status indicators, and responsive theme toggles.
2. **`FarmInputForm.tsx`**: Dynamic farm parameters, Open-Meteo autocomplete, NPK sliders, and drag-and-drop leaf image upload.
3. **`OrchestrationLoader.tsx`**: Animated execution status displaying active agent progress.
4. **`AdvisoryHero.tsx`**: Top-level recommendation card with DSS and EQS visual meters.
5. **`DiseaseActionCard.tsx`**: Disease diagnosis breakdown, confidence meters, alternative diagnoses, and crop mismatch warnings.
6. **`NutrientSupportCard.tsx`**: Stoichiometric NPK balance display with deficit bar charts.
7. **`DecisionSignals.tsx`**: Side-by-side cards for weather risk and market price trends.
8. **`ActionPlan.tsx`**: Chronological field actions (immediate, 24–48 hours, and cultural precautions).
9. **`WhyDecisionCard.tsx`**: Plain-language agronomic rationale with ICAR citations.
10. **`DecisionPath.tsx`**: Visual flowchart illustrating Stage 1 vetoes and Stage 2 weighted scoring.
11. **`DecisionChangeTriggers.tsx`**: Interactive list of conditions that would alter the current advisory.
12. **`NearbyStoresCard.tsx`**: Map-linked cards of nearby input stores from OpenStreetMap.
13. **`AgentContributions.tsx`**: Visual breakdown of individual agent votes and confidence scores.
14. **`EvidencePanel.tsx`**: Retrieved ICAR knowledge chunks and regional validity tags.
15. **`AuditPanel.tsx`**: Collapsible drawer with raw JSON traces and latencies.
16. **`FarmContextCard.tsx`**: Compact summary of current farm parameters and coordinates.
17. **`PriceCard.tsx`**: Mandi price trend chart and market timing signals.
18. **`FeedbackCard.tsx`**: Form allowing farmers to log actions taken and field outcomes.
19. **`StatusBadge.tsx`**: Reusable semantic status chip for consistency.

---

## 13. Environment Configuration

All environment settings are managed via `.env` (configured using `.env.example` as a template):

| Variable | Description | Default Value | Required? |
| :--- | :--- | :--- | :---: |
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///agrimind_local.db` | No |
| `OPEN_METEO_BASE_URL` | Open-Meteo forecast API | `https://api.open-meteo.com/v1/forecast` | No |
| `GEOCODING_BASE_URL` | Open-Meteo geocoding search | `https://geocoding-api.open-meteo.com/v1/search` | No |
| `AGMARKNET_BASE_URL` | Optional Agmarknet mandi endpoint | `""` (uses local heuristics) | No |
| `DISEASE_MODEL_BACKBONE` | Active vision backbone | `dinov2_lora` | No |
| `DINOV2_LORA_CHECKPOINT_PATH`| Path to LoRA weights file | `ml/artifacts/dinov2_lora_r4_b4_best.pt` | Yes (for DINOv2) |
| `DISEASE_MODEL_PATH` | Path to MobileNetV3 weights | `ml/artifacts/best.pt` | Yes (for rollback) |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000,http://127.0.0.1:3000` | No |
| `NEXT_PUBLIC_API_URL` | API URL for frontend client | `http://localhost:8000` | Yes |
| `LLM_PRIMARY_PROVIDER` | Primary explanation provider | `openai` | No |
| `LLM_FALLBACK_PROVIDER` | Fallback explanation provider | `grok` | No |
| `LLM_TEMPLATE_FALLBACK` | Allow template fallback if APIs fail | `true` | No |
| `OPENAI_API_KEY` | OpenAI API access key | `""` (triggers template fallback) | Optional |
| `OPENAI_MODEL` | OpenAI model ID | `gpt-4o-mini` | No |
| `XAI_API_KEY` | xAI Grok API access key | `""` (triggers template fallback) | Optional |
| `XAI_MODEL` | xAI model ID | `grok-2-latest` | No |

---

## 14. Installation & Setup Guide

### 14.1 Prerequisites
- **Python:** Version 3.10, 3.11, or 3.12 (64-bit).
- **Node.js:** Version 18.18+, 20.x, or 22.x LTS with `npm`.
- **Operating System:** Windows 10/11 (PowerShell), Ubuntu 20.04+, or macOS 12+.

### 14.2 Automated Single-Command Startup

#### Windows PowerShell
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start.ps1
```

#### Linux / macOS Bash
```bash
chmod +x start.sh
./start.sh
```

### 14.3 Manual Step-by-Step Installation

#### Step 1: Environment Setup
```bash
# Clone or extract archive, navigate to root
cd AgriMind_Core_Modules

# Create and activate Python virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install Python backend dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 2: Frontend Setup
```bash
cd web
npm install
cd ..
```

#### Step 3: Configure Environment
```bash
cp .env.example .env
```

#### Step 4: Run the Backend & Frontend
```bash
# Terminal 1: Backend API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend Dashboard
cd web
npm run dev
```

Visit the web dashboard at `http://localhost:3000` and the interactive API documentation at `http://localhost:8000/docs`.

---

## 15. Practical Usage Examples

### 15.1 Headless System Verification
Verify the entire pipeline across 3 multi-agent scenarios without launching a browser:
```bash
python main.py
```

### 15.2 Submitting an Advisory via cURL
```bash
curl -X POST "http://localhost:8000/api/advisory" \
  -H "Content-Type: application/json" \
  -d '{
    "crop": "Tomato",
    "growth_stage": "flowering",
    "location_name": "Nashik, Maharashtra",
    "lat": 19.9975,
    "lon": 73.7898,
    "n": 22.0,
    "p": 45.0,
    "k": 70.0,
    "current_price": 2400.0,
    "price_history": [2100, 2200, 2350, 2400]
  }'
```

### 15.3 Uploading a Leaf Image for Disease Diagnosis
```bash
curl -X POST "http://localhost:8000/api/advisory/upload" \
  -F "crop=Tomato" \
  -F "growth_stage=vegetative" \
  -F "lat=19.9975" \
  -F "lon=73.7898" \
  -F "location_name=Nashik" \
  -F "disease_model=dinov2_lora" \
  -F "image=@sample_leaf.jpg;type=image/jpeg"
```

### 15.4 Checking Vision Model Health
```bash
curl "http://localhost:8000/health/model?model=dinov2_lora"
```
Response:
```json
{
  "model": "dinov2_lora",
  "status": "ready",
  "device": "cuda",
  "lora_checkpoint": "ml/artifacts/dinov2_lora_r4_b4_best.pt",
  "sha256": "8ae555c2054fd518edb5382519cca4fba9d2bff4bc039636fddc4b14edf1aa68",
  "lora_rank": 4,
  "lora_blocks": [8, 9, 10, 11],
  "num_classes": 38
}
```

---

## 16. Model Evaluation, Benchmarking & Training

### 16.1 Training Pipelines
- **DINOv2 LoRA Fine-Tuning (`ml/train_field_finetune.py`):** Trains LoRA adapters on transformer blocks 8–11 using AdamW ($\text{lr} = 5 \times 10^{-4}$ for LoRA parameters, weight decay $0.01$, batch size 32, cross-entropy loss with label smoothing $0.1$).
- **MobileNetV3 Baseline Training (`ml/train_disease.py`):** Trains MobileNetV3-Large with cosine learning rate scheduling and standard data augmentations (RandomResizedCrop, ColorJitter, RandomHorizontalFlip).

### 16.2 Evaluation Protocols
- Evaluated using `evaluation/evaluate_disease_model.py` across three held-out sets:
  1. **Field Validation Set:** 108 field images across 27 represented classes.
  2. **PlantDoc Benchmark:** Challenging public benchmark with complex field clutter.
  3. **Independent Field Test:** Field imagery from real-world farm conditions.

---

## 17. Performance, Hardware & Deployment

### 17.1 Latency Benchmarks
- **DINOv2 LoRA Inference:**
  - NVIDIA RTX 4090 / A100 GPU: ~14.4 ms per image.
  - Modern 8-Core Intel/AMD CPU: ~85 ms per image.
- **Decision Engine & Safety Guard:** $< 2.5 \text{ ms}$.
- **RAG Semantic Search:** $\sim 8.0 \text{ ms}$ over 2.36 MB corpus.
- **LLM Explanation:** $800\text{--}1400 \text{ ms}$ (network-bound) or $< 1.0 \text{ ms}$ for deterministic template fallback.

### 17.2 Resource Footprint
- **RAM:** Minimum 2 GB (idle: ~450 MB; peak during vision inference: ~1.2 GB).
- **VRAM (Optional GPU):** ~1.1 GB VRAM for DINOv2-Small backbone + LoRA head.
- **Storage:** ~350 MB total application footprint (excluding external HF cache).

### 17.3 Containerized Deployment
Deploy using Docker Compose:
```bash
docker-compose up --build
```
This launches the FastAPI service on port 8000 and the Next.js service on port 3000 with volume mounts for model checkpoints and SQLite persistence.

---

## 18. Troubleshooting & Diagnostics

### 1. `ModuleNotFoundError: No module named 'transformers'`
- **Cause:** Backend started outside the configured virtual environment.
- **Remedy:** Ensure the virtual environment is activated (`.venv\Scripts\activate` or `source .venv/bin/activate`) and run `pip install -r requirements.txt`.

### 2. Port 8000 or 3000 Already in Use
- **Diagnostic:** `netstat -ano | findstr :8000` (Windows) or `lsof -i :8000` (Linux).
- **Remedy:** Terminate the conflicting process or specify alternative ports:  
  `uvicorn api.main:app --port 8001` and set `NEXT_PUBLIC_API_URL=http://localhost:8001`.

### 3. DINOv2 Backbone Download Fails (Air-Gapped Environment)
- **Diagnostic:** `ConnectionError` during `AutoModel.from_pretrained("facebook/dinov2-small")`.
- **Remedy:** Download the backbone on an internet-connected machine, transfer the cache directory (`~/.cache/huggingface/hub`), and set `HF_HUB_OFFLINE=1`.

### 4. Image Upload Rejected with HTTP 415 or 413
- **Cause:** Unsupported MIME type or image exceeds the $5\text{ MB}$ limit.
- **Remedy:** Upload JPEG, PNG, or WebP images under $5\text{ MB}$.

### 5. Weather Telemetry Times Out
- **Behavior:** System logs a weather timeout warning and activates Rule E.
- **Remedy:** Normal automatic behavior. The system applies a neutral risk ($0.50$), falls back to cached data, and prevents unsafe fertilizer applications.

### 6. SQLite Database Locks (`database is locked`)
- **Cause:** Concurrent multi-threaded writes on low-spec hardware.
- **Remedy:** AgriMind configures `check_same_thread=False`. For high-concurrency production deployments, switch to PostgreSQL by setting `DATABASE_URL=postgresql://user:password@host:5432/dbname`.

---

## 19. Security, Privacy & Open-Source Licensing

### 19.1 Credential & Secret Management
- API keys (`OPENAI_API_KEY`, `XAI_API_KEY`) are loaded strictly from environment variables.
- The logging layer in `llm/config.py` runs regex filters to sanitize credentials from logs, console output, and database records.

### 19.2 Image Validation & Upload Security
- Uploaded files are verified via binary header inspection (`Image.open().verify()`).
- Images are written to randomized temporary files and deleted immediately after inference in a `finally:` block.

### 19.3 Licensing & Open-Source Compliance
- **AgriMind Source Code:** Released under the MIT License.
- **DINOv2 Backbone:** Apache 2.0 License (Meta AI).
- **MobileNetV3 Backbone:** BSD 3-Clause License (PyTorch / Torchvision).
- **ICAR Advisory Corpus:** Public agricultural extension literature (Government of India).

---

## 20. Known Limitations & Roadmap

### 20.1 Current Limitations
1. **Class Distribution Skew:** The 38-class taxonomy has uneven class distribution, with abundant data for Tomato and Potato and fewer samples for crops like Raspberry and Soybean.
2. **Field Clutter Sensitivity:** Extreme background clutter (e.g., weeds, soil, hands) can lower unconstrained confidence; farmers are advised to take close-up photos of leaves.
3. **Market Data Coverage:** Live mandi prices depend on reported transactions in APMC mandis; coverage is sparse in some remote districts.

### 20.2 Planned Enhancements
- **Multi-Leaf & Canopy Segmentation:** Incorporating YOLOv11 for automatic leaf localization before classification.
- **Voice-First Vernacular Interfaces:** Adding speech-to-text and text-to-speech for regional Indian languages (Hindi, Marathi, Tamil, Telugu).
- **Edge Deployment:** Exporting quantized INT8 ONNX models for mobile edge inference directly on farmer smartphones.

---

## 21. Glossary & References

### 21.1 Key Technical Terms
- **LoRA (Low-Rank Adaptation):** Parameter-efficient fine-tuning technique decomposing weight updates into low-rank matrices.
- **DSS (Decision Stability Score):** Quantitative metric ($0.0 \text{ to } 1.0$) measuring internal agent agreement and stability.
- **EQS (Evidence Quality Score):** Quantitative metric ($0.0 \text{ to } 1.0$) measuring input data completeness and reliability.
- **NPK:** Elemental Nitrogen, Phosphorus, and Potassium soil macronutrients.
- **Mandi:** Regulated wholesale agricultural produce market in India (APMC).
- **ECE (Expected Calibration Error):** Difference between model prediction confidence and empirical accuracy.

### 21.2 Official References & Links
- **FastAPI Documentation:** [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
- **Next.js 16 App Router:** [https://nextjs.org/docs](https://nextjs.org/docs)
- **Meta AI DINOv2:** [https://github.com/facebookresearch/dinov2](https://github.com/facebookresearch/dinov2)
- **Open-Meteo Weather API:** [https://open-meteo.com/](https://open-meteo.com/)
- **Indian Council of Agricultural Research (ICAR):** [https://icar.org.in/](https://icar.org.in/)
- **Hugging Face Transformers:** [https://huggingface.co/docs/transformers](https://huggingface.co/docs/transformers)
