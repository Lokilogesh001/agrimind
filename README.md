# AgriMind

**Observable multi-agent orchestration system for intelligent crop advisory.**

## Product flow

Farmer context + optional leaf image → Weather, Soil, Disease, Advisory and Market agents → deterministic conflict resolver → source-grounded explanation → auditable observability trail.

### Safety policy
1. **P1 rainfall safety:** rainfall risk > 0.70 → `DELAY`.
2. **P2 disease confidence gate:** confidence < 0.60 makes the disease finding non-actionable; the run continues.
3. **P3 disease urgency:** actionable + high severity → `DISEASE_MANAGEMENT_FIRST`.
4. **P4 nutrient requirement:** overall soil deficiency > 0.60 → `apply_fertilizer`.
5. **P5 market:** economic signal is a Stage-2 tie-breaker only and cannot override agronomic safety.

## Run locally

```bash
python -m venv .venv
# activate it
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

The frontend lives in `web/`:

```bash
cd web
npm install
npm run dev # or npm run build
```

## Disease model

The PlantVillage training pipeline uses the official color manifests and keeps the official test set untouched until final evaluation. A leaf-grouped validation split is created from the training manifest. MobileNetV3-Large uses ImageNet transfer learning, class-weighted cross-entropy, augmentation, label smoothing, AdamW, cosine scheduling, mixed precision on CUDA, early stopping, and macro-F1 model selection.

Colab example:

```bash
python -m ml.train_disease \
  --root /content/agrimind_plantvillage/data \
  --train-manifest /content/agrimind_plantvillage/download/splits/color_train.txt \
  --test-manifest /content/agrimind_plantvillage/download/splits/color_test.txt \
  --epochs 15 --batch-size 64 --num-workers 2 \
  --output ml/artifacts/best.pt
```

PlantVillage is a disease-classification source; **severity is not claimed to be learned from it**. The current Disease Agent uses an explicitly provisional severity heuristic until a severity-labelled source is validated.

## ICAR RAG

Ingest the uploaded/official ICAR agro-advisory PDF after installing `pypdf` and `chromadb`:

```bash
python -m rag.icar_ingest path/to/ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf
```

Chunks retain source document and page metadata. RAG evidence explains recommendations but cannot override deterministic safety policy.

## API

- `GET /health`
- `POST /api/advisory`
- `POST /api/advisory/upload`
- `GET /api/runs/{run_id}`
- `POST /api/feedback`

The explanation layer uses xAI/Grok first, then optional Groq/Gemini fallbacks, and finally a deterministic template. The LLM never selects or overrides the safety action. Each LLM/fallback attempt is persisted as `llm_explainer` in the observability trail with provider, model, status, fallback flag, cache flag, latency, and error information. Environment variables are loaded from `.env`.

## Verification

```bash
python scripts/verify_product.py
pytest -q
python -m compileall -q .
```

The repository includes the ICAR Kharif Agro-Advisories 2025 PDF and a page-provenance corpus generated from it. The document emphasizes location-specific, science-backed advisories and soil/weather-aware crop management. The product therefore exposes retrieved evidence with document/page metadata rather than presenting the LLM as the source of agronomic truth. 
