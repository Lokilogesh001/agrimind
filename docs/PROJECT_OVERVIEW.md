# AgriMind — Project Overview

## 1. Executive Summary & Motivation
Smallholder farming in India and developing regions faces complex, interconnected agronomic challenges:
1. **Nutrient Management & Fertilizer Leaching:** Over-application of chemical nitrogen prior to unexpected precipitation causes catastrophic environmental runoff and financial waste.
2. **Crop Disease Misdiagnosis:** Visual symptoms are frequently misidentified by untrained operators, leading to incorrect fungicide or pesticide usage.
3. **Price Volatility & Harvesting Losses:** Lack of local mandi market intelligence forces distressed selling at low harvest prices.
4. **Hallucination in Generic AI Advisors:** Generic Large Language Models (LLMs) hallucinate agricultural chemicals, ignore regional climatic thresholds, and lack grounding in authoritative institutional advisories (e.g., ICAR — Indian Council of Agricultural Research).

**AgriMind** is a production-grade, multi-agent agronomic advisory and decision-support system designed to solve these challenges. It integrates specialized autonomous agents, a deterministic two-stage conflict resolution engine, local computer vision models, and retrieval-augmented generation (RAG) grounded in the official 2025 ICAR Kharif advisories.

---

## 2. Problem Statement
Agricultural decision-making requires reconciling conflicting signals across disparate domains:
- **Agronomic vs. Meteorological Conflict:** Soil sensors indicate severe nitrogen deficiency (suggesting immediate fertilizer application), while satellite weather forecasts predict heavy rainfall within 24 hours (which would wash away applied fertilizer).
- **Phytosanitary vs. Timing Conflict:** High disease pressure demands immediate curative spraying, but high wind speeds or precipitation preclude chemical application.
- **Economic vs. Harvest Timing Conflict:** Falling local market prices pressure early harvesting, but crop maturity indices advise delaying.

Standard generative AI approaches fail because LLMs cannot be trusted with safety-critical agricultural interventions. AgriMind establishes a strict separation of concerns:
- **Agents gather evidence** from specialized sources (weather, soil, disease vision, market trends).
- **The Decision Engine deterministically computes recommendations** using safety vetoes and multi-criteria scoring.
- **The LLM is restricted solely to the explanatory layer**, translating deterministic findings into transparent farmer-facing vernacular.

---

## 3. Project Objectives
1. **Deterministic Safety:** Enforce hard, non-overridable safety rules (e.g., rainfall safety vetoes preventing chemical application during predicted rainfall events).
2. **Multi-Agent Orchestration:** Coordinate 5 specialist agents (Weather, Soil, Disease, Market Intelligence, and Advisory) within a stateful LangGraph pipeline.
3. **Institutional Grounding (RAG):** Ground all recommendations in official 2025 ICAR Kharif advisory corpus using TF-IDF candidate generation and multi-criteria reranking.
4. **On-Device Vision Inference:** Provide leaf disease classification using a custom PyTorch MobileNetV3 model trained on 38 plant disease classes.
5. **Traceability & Observability:** Maintain an immutable relational audit trail covering execution traces, agent outputs, decision stability scores (DSS), conflict events, and farmer feedback.
6. **Zero-Friction Developer Experience:** Enable single-command local orchestration (`npm run dev`) launching both the FastAPI backend and Next.js frontend concurrently.

---

## 4. System Scope & Boundaries

### In Scope
- Real-time weather ingestion via Open-Meteo API (temperature, precipitation probability, rainfall amount).
- Offline & online soil nutrient assessment across Nitrogen, Phosphorus, Potassium (NPK), pH, and moisture.
- PyTorch leaf disease inference with PlantVillage label normalization and 60% confidence gating.
- Agmarknet commodity market price trend evaluation.
- Deterministic P1–P5 conflict resolution and Stage-1 Hard Safety Guards (A–F).
- Calculation of Decision Stability Score (DSS) and re-evaluation trigger recommendations.
- ICAR RAG evidence retrieval and metadata filtering.
- Complete REST API and responsive Next.js web application.

### Out of Scope (Current Release)
- Autonomous robotic hardware control or valve actuation.
- Direct financial transactions or trade execution on mandis.
- Unvalidated custom pesticide chemical recipes (all chemical guidance adheres strictly to ICAR guidelines).

---

## 5. Implementation Status Matrix

| Component | Status | Implementation Details |
| :--- | :--- | :--- |
| **FastAPI Backend** | Production Ready | Version 1.2.0, lifespan DB init, CORS enabled, Pydantic extra-forbid validation |
| **Next.js Frontend** | Production Ready | Next.js 16.3.4 (Turbopack), React 19, responsive agronomic dashboard |
| **Weather Agent** | Production Ready | Open-Meteo live integration with deterministic risk heuristics & fallback |
| **Soil Agent** | Production Ready | Crop-specific target benchmarking across 32 registered crops |
| **Disease Vision** | Production Ready | MobileNetV3 PyTorch model (`ml/artifacts/best.pt`) with validation gates |
| **Market Agent** | Production Ready | Price momentum and volatility tracking with degraded status handling |
| **Orchestrator** | Production Ready | LangGraph state graph with parallel evaluation and deterministic decision |
| **ICAR RAG** | Production Ready | 2025 Kharif advisory PDF chunk corpus, TF-IDF + metadata reranking |
| **Observability** | Production Ready | SQLite / PostgreSQL relational schema with 5 audit tables and latency metrics |
| **Test Suite** | Production Ready | 130 automated pytest tests passing (100% success rate) |
