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


def test_mixed_unrelated_rag_chunk_penalized():
    """Verify that chunks with substantial unrelated crops (mango orchards, cucurbits, cotton) are penalized."""
    r = KnowledgeRetriever(corpus_path=str(CORPUS))
    from rag.retriever import _calculate_crop_relevance
    # p52-c2 contains cucurbits/sugarcane and only brief mention of tomato
    cucurbit_sugarcane_text = (
        "Suitable varieties of cucurbits such as bottle gourd, bitter gourd, cucumber, "
        "sponge gourd, ridge gourd should be sown. Wilting in brinjal and tomato plants can be controlled. "
        "Sugarcane enters its early vegetative and grand growth phase."
    )
    rel = _calculate_crop_relevance("tomato", "tomato,brinjal,okra,cucumber,bottle_gourd,bitter_gourd", cucurbit_sugarcane_text)
    assert rel <= 0.50, f"Expected penalized crop relevance <= 0.50, got {rel}"


def test_tomato_evidence_retrieval_madurai_vegetative():
    """Verify that Tomato + Madurai + Vegetative returns chunk-level scored evidence with correct location and crop badges."""
    r = KnowledgeRetriever(corpus_path=str(CORPUS))
    hits = r.search(
        "Tomato vegetative Madurai agronomy",
        n_results=4,
        crop="tomato",
        growth_stage="vegetative",
        location="Madurai, Tamil Nadu",
    )
    assert hits
    top_hit = hits[0]
    # Top hit should be the Tamil Nadu advisory chunk
    assert "256" in top_hit["id"]
    assert top_hit["location_relevance"] == 1.0
    assert top_hit["relevance_badges"]["location_match"] == "HIGH"
    # Excerpt should focus on the tomato micronutrient spray
    assert "tomato" in top_hit["text"].lower()
    # A non-Tamil Nadu chunk (e.g. Karnataka) must not be marked HIGH location match
    for h in hits:
        if "tamil nadu" not in (h.get("metadata", {}).get("regions", "")).lower():
            assert h["relevance_badges"]["location_match"] != "HIGH"
