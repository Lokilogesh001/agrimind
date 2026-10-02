"""Lightweight metadata extraction for ICAR agronomy chunks.

The ICAR PDF is a compiled advisory document rather than a clean database. This
module derives conservative, searchable tags from the extracted text. Tags are
context labels only; they are not treated as ground-truth agronomic facts.
"""
from __future__ import annotations

import re
import unicodedata

CROP_ALIASES = {
    "rice": ("rice", "paddy"),
    "maize": ("maize", "corn"),
    "pigeonpea": ("pigeonpea", "pigeon pea", "red gram"),
    "blackgram": ("blackgram", "black gram"),
    "greengram": ("greengram", "green gram", "mung bean", "moong"),
    "bengalgram": ("bengalgram", "bengal gram", "chickpea", "chick pea"),
    "groundnut": ("groundnut", "peanut"),
    "cotton": ("cotton",),
    "soybean": ("soybean", "soya bean"),
    "sunflower": ("sunflower",),
    "sesame": ("sesame",),
    "castor": ("castor",),
    "sorghum": ("sorghum", "jowar"),
    "pearl_millet": ("pearl millet", "bajra"),
    "finger_millet": ("finger millet", "ragi"),
    "tomato": ("tomato",),
    "potato": ("potato",),
    "brinjal": ("brinjal", "eggplant", "aubergine"),
    "bell_pepper": ("bell pepper", "capsicum"),
    "chilli": ("chilli", "chili", "hot pepper"),
    "okra": ("okra", "bhindi", "lady's finger", "lady finger"),
    "onion": ("onion",),
    "garlic": ("garlic",),
    "turmeric": ("turmeric",),
    "yam": ("yam",),
    "banana": ("banana",),
    "citrus": ("citrus", "orange", "mandarin", "lemon"),
    "apple": ("apple",),
    "grape": ("grape", "grapes"),
    "pomegranate": ("pomegranate",),
    "mango": ("mango",),
    "guava": ("guava",),
    "papaya": ("papaya",),
    "watermelon": ("watermelon",),
    "muskmelon": ("muskmelon",),
    "cucumber": ("cucumber",),
    "bottle_gourd": ("bottle gourd",),
    "bitter_gourd": ("bitter gourd",),
}

TOPIC_PATTERNS = {
    "disease": ("disease", "blight", "wilt", "rot", "canker", "mosaic", "mildew", "spot", "scab", "rust", "leaf curl"),
    "pest": ("pest", "insect", "aphid", "thrips", "borer", "worm", "miner", "mite", "fly", "beetle"),
    "fertilizer": ("fertilizer", "fertiliser", "nutrient", "nitrogen", "phosphorus", "potassium", "npk", "manure", "micronutrient"),
    "irrigation": ("irrigation", "irrigate", "water management", "moisture", "drought", "dry spell"),
    "sowing": ("sowing", "sown", "seed rate", "seed treatment", "planting", "transplanting"),
    "weather": ("rainfall", "rain", "storm", "weather", "drought", "dry spell", "flood"),
    "harvest": ("harvest", "harvesting", "maturity", "mature", "storage", "post-harvest"),
}

REGION_PATTERNS = (
    "andhra pradesh", "telangana", "tamil nadu", "karnataka", "kerala", "maharashtra",
    "punjab", "haryana", "uttar pradesh", "madhya pradesh", "rajasthan", "bihar",
    "west bengal", "odisha", "assam", "jammu and kashmir", "kashmir", "himachal pradesh",
    "uttarakhand", "chhattisgarh", "jharkhand", "gujarat", "india",
)


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\|\s*", " ", text)
    return text.strip()


def _find_tags(text: str, patterns: dict[str, tuple[str, ...]]) -> list[str]:
    low = text.lower()
    found = []
    for tag, aliases in patterns.items():
        if any(re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low) for alias in aliases):
            found.append(tag)
    return found


DISEASE_TERMS = (
    "early blight", "late blight", "bacterial wilt", "fungal wilt", "leaf spot",
    "fruit rot", "powdery mildew", "downy mildew", "bacterial canker", "leaf curl virus",
    "mosaic virus", "spotted wilt virus", "anthracnose", "rust", "scab", "blast",
    "collar rot", "rhizome rot", "root rot", "stem rot", "fruit cracking", "phyllody",
)


def extract_metadata(text: str, page_no: int, chunk_no: int) -> dict:
    cleaned = clean_text(text)
    low = cleaned.lower()
    crops = []
    for canonical, aliases in CROP_ALIASES.items():
        if any(re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low) for alias in aliases):
            crops.append(canonical)

    diseases = [term for term in DISEASE_TERMS if term in low]
    topics = _find_tags(cleaned, TOPIC_PATTERNS)
    regions = [r for r in REGION_PATTERNS if r in low]

    return {
        "source_page": page_no,
        "chunk": chunk_no,
        "crops": ",".join(crops),
        "topics": ",".join(topics),
        "diseases": ",".join(diseases[:8]),
        "regions": ",".join(regions),
        "text_cleaned": "true",
    }
