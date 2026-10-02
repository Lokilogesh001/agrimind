# AgriMind RAG

AgriMind uses validated agricultural guidance as evidence context. The current
corpus is the ICAR *Kharif Agro-Advisories for Farmers 2025* document.

## Retrieval design

- PDF pages are cleaned and chunked with overlap.
- Each chunk receives conservative metadata for crop, topic, disease, region,
  source page, and chunk number.
- Local retrieval uses TF-IDF candidate generation followed by metadata-aware
  reranking. Crop context is a relevance constraint when tagged material exists.
- Duplicate evidence text is removed from the final result set.
- The API passes crop, growth stage, predicted disease, and recommendation context
  into retrieval.
- Evidence is explanatory/grounding context only. It never overrides the
  deterministic Stage-1/Stage-2 decision policy.

The metadata is derived from document text for retrieval convenience; it is not
additional ground truth. Exact treatment or fertilizer rates must be interpreted
against the cited ICAR page and local agronomic guidance rather than blindly
converted into a universal recommendation.

## Rebuild

```bash
python -m rag.icar_ingest knowledge/ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf
```

The local JSON corpus is replaced during ingestion so stale chunks from an
older extraction do not remain in the index.
