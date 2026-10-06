"""Hybrid ICAR knowledge retrieval with metadata-aware reranking and local fallback."""
from __future__ import annotations

import json
import math
import re
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


DEFAULT_RAG_WEIGHTS = {
    "crop_relevance": 0.30,
    "location_relevance": 0.25,
    "growth_stage": 0.15,
    "semantic_similarity": 0.15,
    "source_reliability": 0.10,
    "temporal_relevance": 0.05,
}

REGIONAL_ZONES: dict[str, set[str]] = {
    "south_india": {"tamil nadu", "kerala", "karnataka", "andhra pradesh", "telangana", "puducherry"},
    "north_india": {"punjab", "haryana", "uttar pradesh", "himachal pradesh", "jammu and kashmir", "kashmir", "uttarakhand", "delhi", "rajasthan"},
    "west_india": {"maharashtra", "gujarat", "goa"},
    "central_india": {"madhya pradesh", "chhattisgarh"},
    "east_india": {"bihar", "west bengal", "odisha", "jharkhand"},
    "north_east_india": {"assam", "meghalaya", "manipur", "mizoram", "nagaland", "tripura", "arunachal pradesh", "sikkim"},
}


CROP_SYNONYMS: dict[str, set[str]] = {
    "rice": {"rice", "paddy", "paddies", "oryza", "dhan"},
    "paddy": {"rice", "paddy", "paddies", "oryza", "dhan"},
    "wheat": {"wheat", "triticum", "gehun"},
    "maize": {"maize", "corn", "zea", "makka"},
    "cotton": {"cotton", "kapas"},
    "sugarcane": {"sugarcane", "cane", "ganna"},
    "soybean": {"soybean", "soya"},
    "groundnut": {"groundnut", "peanut", "moongfali"},
    "tomato": {"tomato", "tamatar"},
    "potato": {"potato", "aloo"},
    "chilli": {"chilli", "chili", "mirch"},
    "onion": {"onion", "pyaz"},
    "chickpea": {"chickpea", "gram", "chana"},
    "pigeonpea": {"pigeonpea", "arhar", "tur", "redgram"},
}


def _calculate_location_relevance(location: str | None, chunk_regions: str, chunk_text: str) -> float:
    if not location or not location.strip():
        return 0.40

    loc_lower = location.lower()
    regions_lower = (chunk_regions or "").lower()
    text_lower = chunk_text.lower()

    target_state = None
    target_zone = None
    for zone, states in REGIONAL_ZONES.items():
        for s in states:
            if s in loc_lower:
                target_state = s
                target_zone = zone
                break
        if target_state:
            break

    if not target_state:
        loc_tokens = _tokens(location)
        if loc_tokens & _tokens(regions_lower):
            return 0.80
        if "india" in regions_lower:
            return 0.40
        return 0.20

    # 1. Direct state match in chunk metadata regions or text
    if target_state in regions_lower or target_state in text_lower:
        return 1.00

    # 2. Regional zone match (e.g. South India)
    if target_zone:
        zone_states = REGIONAL_ZONES[target_zone]
        if any(zs in regions_lower or zs in text_lower for zs in zone_states):
            return 0.55

    # 3. National / Pan-India match
    if "india" in regions_lower or "all india" in text_lower or "national" in text_lower:
        return 0.35

    # 4. Unknown/unspecified chunk location (do not pretend it matches)
    if not regions_lower.strip():
        return 0.15

    # 5. Weakly related / different region
    return 0.05


UNRELATED_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bgoats?\b", r"\bkidding\b", r"\bdeworming\b", r"\balbendazole\b", r"\bfenbendazole\b",
        r"\bpigs?\b", r"\bswine\b", r"\b(pregnant|lactating)\s+sow\b", r"calcium to the lactating",
        r"mineral mixture\s*@", r"\bdairy\b", r"\bcattle\b", r"\bmilking cows?\b", r"\bbovines?\b",
        r"\bfmd\b", r"\bblack quarter\b", r"hemorrhagic septicemia", r"haemorrhagic septicaemia",
        r"\bpoultry\b", r"\bfowls?\b", r"\branikhet\b", r"fowl pox", r"marek", r"\bbroilers?\b",
        r"\blayer (flock|bird|ration)\b", r"\bfisheries?\b", r"\bfish culture\b", r"pond fertility",
        r"\bfingerlings?\b", r"\baquaculture\b", r"gill rot", r"broodstock", r"mastitis", r"milk fever",
        r"teat dip", r"isheries?", r"ish culture", r"breed ish", r"breeding ish"
    ]
]

UNRELATED_CROP_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\borchards?\b", r"\bmango(es)?\b", r"\bcitrus\b", r"\bguava\b", r"\bapples?\b",
        r"\bcotton\b", r"\bkapas\b", r"\bsugarcane\b",
        r"\bcucurbits?\b", r"\bbottle gourd\b", r"\bbitter gourd\b", r"\bridge gourd\b",
        r"\bwatermelon\b", r"\bmuskmelon\b", r"\bsericulture\b", r"\bsilkworm\b",
    ]
]


def _calculate_crop_relevance(crop: str | None, meta_crops_str: str, chunk_text: str) -> float:
    if not crop or not crop.strip():
        return 0.30

    clean_crop = crop.lower().replace("_", " ").strip()
    target_synonyms = CROP_SYNONYMS.get(clean_crop, {clean_crop})
    meta_crops = {c.strip().lower() for c in (meta_crops_str or "").split(",") if c.strip()}
    text_lower = chunk_text.lower()

    # 1. Strictly penalize or disqualify unrelated animal / livestock / dairy / poultry / fisheries domains
    unrelated_count = sum(1 for p in UNRELATED_PATTERNS if p.search(chunk_text))
    opens_with_unrelated = any(p.search(chunk_text[:250]) for p in UNRELATED_PATTERNS)

    if unrelated_count >= 2 or opens_with_unrelated:
        # A chunk dominated by or opening with animal husbandry is rejected for crop advisory
        return 0.0
    elif unrelated_count > 0:
        # Heavily penalize any residual contamination
        return 0.10

    # 2. Check if target crop is actually present in the chunk text
    # Avoid counting animal feed like 'paddy straw' or 'rice bran' when crop advisory is absent
    has_target_crop_word = any(syn in text_lower for syn in target_synonyms)
    if not has_target_crop_word:
        return 0.0

    # Check for feed mentions vs genuine crop advisory
    if "paddy straw" in text_lower or "rice bran" in text_lower:
        has_real_crop_advisory = any(w in text_lower for w in (
            "spray", "fertilizer", "yield", "booting", "heading", "varieties", "transplanting",
            "fym", "rdf", "tnau", "seed", "nursery", "weeding", "borer", "blast", "blight", "foliar"
        ))
        if not has_real_crop_advisory:
            return 0.0

    # 3. Penalize compound/mixed chunks dominated by unrelated crops/orchards
    unrelated_crop_matches = [
        pat.pattern for pat in UNRELATED_CROP_PATTERNS
        if not any(syn in pat.pattern for syn in target_synonyms) and pat.search(chunk_text)
    ]
    opens_with_unrelated_crop = any(
        pat.search(chunk_text[:200]) for pat in UNRELATED_CROP_PATTERNS
        if not any(syn in pat.pattern for syn in target_synonyms)
    )
    other_crops_count = len([c for c in meta_crops if not any(s in c for s in target_synonyms)])

    if opens_with_unrelated_crop or len(unrelated_crop_matches) >= 2:
        return 0.35
    elif other_crops_count >= 4 or len(unrelated_crop_matches) == 1:
        return 0.50

    crop_in_meta = any(syn in meta_crops or any(syn in mc for mc in meta_crops) for syn in target_synonyms)

    # 4. Target crop is genuinely present and focused in text
    if crop_in_meta:
        return 1.00
    return 0.85


def _calculate_stage_relevance(stage: str | None, chunk_text: str, crop_rel: float = 1.0) -> float:
    if crop_rel < 0.20:
        return 0.0

    if not stage or not stage.strip() or stage.lower() in {"unknown", "all", "unspecified"}:
        return 0.40

    clean_stage = stage.lower().replace("_", " ").replace("/", " ").replace("-", " ")
    clean_stage = " ".join(clean_stage.split())
    if "grain" in clean_stage or "filling" in clean_stage or "fruiting" in clean_stage:
        clean_stage = "grain_filling"
    elif "flower" in clean_stage or "bloom" in clean_stage or "heading" in clean_stage:
        clean_stage = "flowering"
    elif "veg" in clean_stage or "seedling" in clean_stage or "tillering" in clean_stage:
        clean_stage = "vegetative"
    elif "matur" in clean_stage or "harvest" in clean_stage:
        clean_stage = "harvest"

    text_lower = chunk_text.lower()

    stage_synonyms = {
        "flowering": [
            "flowering", "bloom", "heading", "anthesis", "panicle", "spikelet",
            "booting", "silking", "tasseling", "lowering", "lower initiation", "reproductive stage"
        ],
        "vegetative": ["vegetative", "nursery", "seedling", "tillering", "transplanting", "stem elongation", "growth"],
        "grain_filling": ["grain filling", "grain illing", "milking", "dough stage", "pod development", "fruiting", "heading", "booting"],
        "fruiting": ["fruiting", "grain filling", "grain illing", "milking", "dough stage", "pod development", "bloom", "heading", "booting"],
        "maturity": ["maturity", "harvest", "ripening", "curing"],
        "harvest": ["harvest", "maturity", "ripening", "curing"],
    }
    syns = stage_synonyms.get(clean_stage, [clean_stage])
    if any(s in text_lower for s in syns):
        return 1.00

    return 0.15


def _calculate_source_reliability(doc_name: str, chunk_text: str) -> float:
    text_lower = (doc_name + " " + chunk_text).lower()
    if "icar" in text_lower or "indian council of agricultural research" in text_lower:
        return 1.00
    if "kvk" in text_lower or "krishi vigyan kendra" in text_lower or "sau" in text_lower:
        return 0.90
    if "university" in text_lower or "dept of agriculture" in text_lower:
        return 0.85
    return 0.70


def _calculate_temporal_relevance(doc_name: str, chunk_text: str) -> float:
    combined = (doc_name + " " + chunk_text).lower()
    if "2025" in combined:
        return 1.00
    if "2024" in combined:
        return 0.85
    if "2023" in combined:
        return 0.70
    return 0.60


def _extract_focused_excerpt(text: str, crop: str | None, location: str | None) -> str:
    """Extract the most relevant agricultural excerpt from a chunk for clean display."""
    if not text:
        return ""
    text_lower = text.lower()

    if crop and crop.strip():
        c_clean = crop.lower().strip()
        c_syns = CROP_SYNONYMS.get(c_clean, {c_clean})
        crop_positions = [text_lower.find(s) for s in c_syns if text_lower.find(s) != -1]
        if crop_positions:
            first_pos = min(crop_positions)
            if first_pos > 30:
                nl_pos = text.rfind("\n", 0, first_pos)
                start_idx = nl_pos + 1 if nl_pos != -1 else first_pos
                return text[start_idx:].strip()

    candidates = []
    if location and location.lower() in text_lower:
        candidates.append(text_lower.find(location.lower()))

    candidates = [pos for pos in candidates if pos > 30]
    if candidates:
        first_pos = min(candidates)
        nl_pos = text.rfind("\n", 0, first_pos)
        start_idx = nl_pos + 1 if nl_pos != -1 else first_pos
        return text[start_idx:].strip()
    return text.strip()


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

    def _local_candidates(self, query: str, corpus: list[dict], limit: int = 48) -> list[tuple[dict, float]]:
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

    @classmethod
    def _rerank(cls, candidates: list[tuple[dict, float]], query: str, crop: str | None,
                growth_stage: str | None, disease: str | None, topic: str | None,
                location: str | None = None, weights: dict | None = None) -> list[dict]:
        w = dict(DEFAULT_RAG_WEIGHTS)
        if weights:
            w.update(weights)

        clean_disease = _clean_disease_str(disease)
        ranked = []
        for item, base in candidates:
            meta = item.get("metadata", {}) or {}
            text = item.get("text", "")

            crop_rel = _calculate_crop_relevance(crop, meta.get("crops", ""), text)
            # Exclude irrelevant crops or non-crop topics when a specific crop is requested
            if crop and crop.strip() and crop_rel < 0.25:
                continue

            loc_rel = _calculate_location_relevance(location, meta.get("regions", ""), text)
            stage_rel = _calculate_stage_relevance(growth_stage, text, crop_rel)
            src_rel = _calculate_source_reliability(meta.get("source_document", ""), text)
            temp_rel = _calculate_temporal_relevance(meta.get("source_document", ""), text)

            # Normalized semantic similarity
            sem_sim = min(max(float(base), 0.0), 1.0)
            if clean_disease and clean_disease != "healthy" and clean_disease in text.lower():
                sem_sim = min(1.0, sem_sim + 0.35)
            if topic:
                topic_terms = _tokens(topic)
                if topic_terms & _tokens(meta.get("topics", "")):
                    sem_sim = min(1.0, sem_sim + 0.15)
            if "disease" in (topic or "").lower() or "disease" in query.lower():
                if any(t in text.lower() for t in ("blight", "early blight", "late blight", "wilt", "rot", "canker", "mosaic", "mildew", "spot", "rust")):
                    sem_sim = min(1.0, sem_sim + 0.25)

            # Agronomic topic relevance evaluated on the actual chunk
            agronomic_terms = (
                "fertilizer", "nutrient", "foliar", "spray", "npk", "zinc", "fym", "rdf",
                "compost", "urea", "pest", "disease", "weed", "borer", "blast", "blight",
                "irrigation", "water management", "yield", "sowing", "transplanting",
                "heading", "booting", "grain filling", "grain illing", "spikelet"
            )
            topic_rel = 1.00 if any(t in text.lower() for t in agronomic_terms) else 0.40

            # Deterministic evidence selection hierarchy:
            # 1. State + Crop + Stage (e.g. Tamil Nadu + Rice + Fruiting/Grain Filling)
            # 2. State + Crop (Tamil Nadu + Rice)
            # 3. Regional Zone + Crop (South India + Rice)
            # 4. Pan-India + Crop (India + Rice)
            # 5. Generic Crop
            tier_score = 0.0
            if crop and crop.strip() and crop_rel >= 0.70:
                if loc_rel >= 0.90 and stage_rel >= 0.70:
                    tier_score = 0.40
                elif loc_rel >= 0.90:
                    tier_score = 0.28
                elif loc_rel >= 0.60:
                    tier_score = 0.18
                elif loc_rel >= 0.35:
                    tier_score = 0.08
                else:
                    tier_score = 0.00

            final_rank_score = (
                w["crop_relevance"] * crop_rel
                + w["location_relevance"] * loc_rel
                + w["growth_stage"] * stage_rel
                + w["semantic_similarity"] * sem_sim
                + w["source_reliability"] * src_rel
                + w["temporal_relevance"] * temp_rel
                + (0.10 * topic_rel)
                + tier_score
            )

            score = round(final_rank_score + (float(base) * 0.05), 4)

            item_out = dict(item)
            item_out["source"] = "ICAR Kharif Agro-Advisories 2025"
            item_out["document"] = meta.get("source_document", "ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf")
            item_out["page"] = meta.get("source_page", 1)
            item_out["chunk"] = meta.get("chunk", 1)
            item_out["score"] = score
            item_out["crop_relevance"] = round(crop_rel, 4)
            item_out["location_relevance"] = round(loc_rel, 4)
            item_out["stage_relevance"] = round(stage_rel, 4)
            item_out["topic_relevance"] = round(topic_rel, 4)
            item_out["semantic_similarity"] = round(sem_sim, 4)
            item_out["source_reliability"] = round(src_rel, 4)
            item_out["temporal_relevance"] = round(temp_rel, 4)
            item_out["final_rank_score"] = round(final_rank_score, 4)
            item_out["text"] = _extract_focused_excerpt(text, crop, location)
            item_out["relevance_badges"] = {
                "crop_match": "HIGH" if crop_rel >= 0.75 else ("MEDIUM" if crop_rel >= 0.35 else "LOW"),
                "location_match": "HIGH" if loc_rel >= 0.85 else ("MEDIUM" if loc_rel >= 0.40 else "LOW"),
                "stage_match": "HIGH" if stage_rel >= 0.70 else ("MEDIUM" if stage_rel >= 0.30 else "LOW"),
                "source_authority": "HIGH" if src_rel >= 0.85 else "MEDIUM",
            }
            ranked.append(item_out)

        ranked.sort(key=lambda x: (-x["score"], int(x.get("metadata", {}).get("source_page", 0))))
        return ranked

    def search(self, query: str, n_results: int = 4, where=None, *, crop: str | None = None,
               growth_stage: str | None = None, disease: str | None = None,
               topic: str | None = None, location: str | None = None,
               weights: dict | None = None, min_score: float = 0.0) -> list[dict]:
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
            scored = self._local_candidates(query, corpus, limit=max(120, n_results * 30))
            # Also guarantee that crop and location matches are included in candidates
            scored_ids = {x[0]["id"] for x in scored}
            extra: list[tuple[dict, float]] = []
            if crop:
                c_clean = crop.lower().replace("_", " ").strip()
                c_syns = CROP_SYNONYMS.get(c_clean, {c_clean})
                for item in corpus:
                    if item["id"] not in scored_ids:
                        txt_l = item.get("text", "").lower()
                        meta_crops = item.get("metadata", {}).get("crops", "").lower()
                        if any(s in txt_l or s in meta_crops for s in c_syns):
                            extra.append((item, 0.05))
            scored = scored + extra

        ranked = self._rerank(scored, query, crop, growth_stage, disease, topic, location=location, weights=weights)
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
