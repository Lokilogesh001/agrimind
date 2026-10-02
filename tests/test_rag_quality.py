"""Tests for crop/topic-aware ICAR retrieval and evidence quality."""
from pathlib import Path
import json

from rag.retriever import KnowledgeRetriever


CORPUS = Path(__file__).resolve().parents[1] / "knowledge" / "icar_chunks.json"


def test_icar_corpus_has_searchable_metadata():
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert data
    metadata = [x.get("metadata", {}) for x in data]
    assert sum(bool(m.get("crops")) for m in metadata) > 100
    assert sum(bool(m.get("topics")) for m in metadata) > 100
    assert any("early blight" in m.get("diseases", "") for m in metadata)


def test_tomato_retrieval_prefers_tomato_context():
    r = KnowledgeRetriever(corpus_path=str(CORPUS))
    hits = r.search(
        "Tomato Early blight disease management",
        n_results=4,
        crop="tomato",
        disease="early blight",
        topic="disease",
    )
    assert hits
    assert any("tomato" in h.get("metadata", {}).get("crops", "") for h in hits)
    assert any("disease" in h.get("metadata", {}).get("topics", "") for h in hits)
    assert any("early blight" in h.get("text", "").lower() for h in hits)


def test_potato_query_does_not_return_zero_relevance():
    r = KnowledgeRetriever(corpus_path=str(CORPUS))
    hits = r.search("potato disease rainfall", n_results=4, crop="potato", topic="disease")
    assert hits
    assert all(float(h.get("score", 0)) > 0 for h in hits)
    assert any("early blight" in h.get("text", "").lower() or "late blight" in h.get("text", "").lower() for h in hits)


def test_metadata_filter_supports_tag_values():
    r = KnowledgeRetriever(corpus_path=str(CORPUS))
    hits = r.search("fertilizer tomato", n_results=4, where={"crops": "tomato"}, crop="tomato")
    assert hits
    assert all("tomato" in h.get("metadata", {}).get("crops", "") for h in hits)
