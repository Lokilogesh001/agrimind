"""Hybrid ICAR knowledge retrieval with metadata-aware reranking and local fallback."""
from __future__ import annotations

import json
import math
from pathlib import Path

DEFAULT_CORPUS = Path(__file__).resolve().parent.parent / "knowledge" / "icar_chunks.json"


def _tokens(text: str) -> set[str]:
    return {t for t in text.lower().replace("_", " ").replace(",", " ").split() if len(t) > 2}


def _clean_disease_str(d: str | None) -> str:
    if not d:
        return ""
    if "___" in d:
        d = d.split("___", 1)[-1]
    return d.replace("_", " ").strip().lower()


class KnowledgeRetriever:
    def __init__(self, persist_directory: str = "rag/chroma", corpus_path: str | None = None):
        self.persist_directory = persist_directory
        self.corpus_path = Path(corpus_path) if corpus_path else DEFAULT_CORPUS
        self.collection = None
        self._tfidf = None
        self._matrix = None
        self._corpus_cache = None
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=persist_directory)
            self.collection = self.client.get_or_create_collection("agrimind_knowledge")
        except ImportError:
            self.client = None

    def add_documents(self, documents, ids, metadatas=None):
        metadatas = metadatas or [{} for _ in documents]
        if self.collection is not None:
            self.collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
            return
        existing = []
        if self.corpus_path.exists():
            try:
                existing = json.loads(self.corpus_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        by_id = {x["id"]: x for x in existing}
        for doc_id, doc, meta in zip(ids, documents, metadatas):
            by_id[doc_id] = {"id": doc_id, "text": doc, "metadata": meta or {}}
        self.corpus_path.parent.mkdir(parents=True, exist_ok=True)
        self.corpus_path.write_text(json.dumps(list(by_id.values()), ensure_ascii=False), encoding="utf-8")
        self._corpus_cache = None
        self._tfidf = None
        self._matrix = None

    def _load_corpus(self):
        if self._corpus_cache is not None:
            return self._corpus_cache
        if not self.corpus_path.exists():
            return []
        try:
            self._corpus_cache = json.loads(self.corpus_path.read_text(encoding="utf-8"))
        except Exception:
            self._corpus_cache = []
        return self._corpus_cache

    @staticmethod
    def _metadata_match(meta: dict, where: dict | None) -> bool:
        if not where:
            return True
        for key, value in where.items():
            actual = str(meta.get(key, ""))
            if value in {None, ""}:
                continue
            wanted = str(value)
            if actual == wanted:
                continue
            if wanted.lower() not in {x.strip().lower() for x in actual.split(",") if x.strip()}:
                return False
        return True

    def _local_candidates(self, query: str, corpus: list[dict], limit: int = 24) -> list[tuple[dict, float]]:
        texts = [x.get("text", "") for x in corpus]
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import numpy as np
            if self._tfidf is None or self._matrix is None or len(self._matrix) != len(texts):
                self._tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=30000)
                self._matrix = self._tfidf.fit_transform(texts)
            q = self._tfidf.transform([query])
            scores = (self._matrix @ q.T).toarray().ravel()
            order = np.argsort(-scores)[:limit]
            return [(corpus[i], float(scores[i])) for i in order if scores[i] > 0]
        except Exception:
            qtokens = _tokens(query)
            scored = []
            for x in corpus:
                overlap = len(qtokens & _tokens(x.get("text", "")))
                scored.append((x, overlap / max(len(qtokens), 1)))
            scored.sort(key=lambda z: -z[1])
            return scored[:limit]

    @staticmethod
    def _rerank(candidates: list[tuple[dict, float]], query: str, crop: str | None,
                growth_stage: str | None, disease: str | None, topic: str | None) -> list[dict]:
        clean_disease = _clean_disease_str(disease)
        clean_crop = (crop or "").replace("_", " ").strip().lower()
        query_terms = _tokens(query)
        target = {
            "crops": _tokens(clean_crop),
            "topics": _tokens(topic or ""),
            "diseases": _tokens(clean_disease) if clean_disease != "healthy" else set(),
            "stage": _tokens(growth_stage or ""),
        }
        ranked = []
        for item, base in candidates:
            meta = item.get("metadata", {}) or {}
            score = float(base)
            text_terms = _tokens(item.get("text", ""))
            meta_crops = _tokens(meta.get("crops", ""))
            meta_topics = _tokens(meta.get("topics", ""))
            meta_diseases = _tokens(meta.get("diseases", ""))

            if target["crops"]:
                score += 0.24 * len(target["crops"] & meta_crops)
                if target["crops"] & text_terms:
                    score += 0.04
            if target["topics"]:
                score += 0.14 * len(target["topics"] & meta_topics)
            if target["diseases"]:
                score += 0.18 * len(target["diseases"] & meta_diseases)
                if target["diseases"] & text_terms:
                    score += 0.10
                if clean_disease and clean_disease != "healthy" and clean_disease in item.get("text", "").lower():
                    score += 0.30
            if "disease" in target["topics"] and any(
                term in item.get("text", "").lower()
                for term in ("disease", "blight", "wilt", "rot", "canker", "mosaic", "mildew", "spot", "scab", "rust")
            ):
                score += 0.12
            if target["stage"]:
                stage_hits = len(target["stage"] & text_terms)
                score += min(stage_hits, 2) * 0.03

            query_meta_overlap = len(query_terms & (meta_crops | meta_topics | meta_diseases))
            score += min(query_meta_overlap, 4) * 0.02
            item = dict(item)
            item["score"] = round(score, 4)
            ranked.append(item)
        ranked.sort(key=lambda x: (-x["score"], int(x.get("metadata", {}).get("source_page", 0))))
        return ranked

    def search(self, query: str, n_results: int = 4, where=None, *, crop: str | None = None,
               growth_stage: str | None = None, disease: str | None = None,
               topic: str | None = None, min_score: float = 0.0) -> list[dict]:
        query = (query or "").strip()
        if not query or n_results <= 0:
            return []

        if self.collection is not None:
            result = self.collection.query(query_texts=[query], n_results=max(n_results, 12))
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            ids = result.get("ids", [[]])[0]
            candidates = [{"id": i, "text": d, "metadata": m or {}} for i, d, m in zip(ids, docs, metas)]
            candidates = [x for x in candidates if self._metadata_match(x["metadata"], where)]
            scored = [(x, 0.0) for x in candidates]
        else:
            corpus = [x for x in self._load_corpus() if self._metadata_match(x.get("metadata", {}), where)]
            if not corpus:
                return []
            # A supplied crop is a relevance constraint, not merely a ranking hint.
            # If the corpus has tagged material for that crop, search that subset
            # first so generic "rainfall" or "disease" chunks cannot dominate.
            if crop:
                crop_terms = _tokens(crop)
                tagged = [
                    x for x in corpus
                    if crop_terms & _tokens(x.get("metadata", {}).get("crops", ""))
                ]
                if tagged:
                    corpus = tagged
            scored = self._local_candidates(query, corpus, limit=max(100, n_results * 12))

        ranked = self._rerank(scored, query, crop, growth_stage, disease, topic)
        results = []
        seen_text = set()
        for item in ranked:
            if item.get("score", 0.0) < min_score:
                continue
            text_key = " ".join(item.get("text", "").lower().split())
            if text_key in seen_text:
                continue
            seen_text.add(text_key)
            results.append(item)
            if len(results) >= n_results:
                break
        return results
