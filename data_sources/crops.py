"""Standardized Crop Registry for AgriMind.

Provides stable crop IDs, categorized listings, alias normalization,
and growth stage definitions.
"""
from __future__ import annotations

import re
from typing import Any

# Standardized Categories
CATEGORIES = [
    "Cereals",
    "Pulses",
    "Oilseeds",
    "Vegetables",
    "Fruits",
    "Commercial crops",
]

# Standardized Crops
CROPS_REGISTRY: list[dict[str, Any]] = [
    # Cereals
    {
        "id": "rice",
        "name": "Rice",
        "category": "Cereals",
        "aliases": ["paddy", "dhan", "rice (paddy)"],
        "common_regions": ["Punjab", "West Bengal", "Tamil Nadu", "Andhra Pradesh", "Odisha", "Bihar"],
    },
    {
        "id": "wheat",
        "name": "Wheat",
        "category": "Cereals",
        "aliases": ["gehun", "sharbati"],
        "common_regions": ["Uttar Pradesh", "Punjab", "Haryana", "Madhya Pradesh", "Rajasthan"],
    },
    {
        "id": "maize",
        "name": "Maize",
        "category": "Cereals",
        "aliases": ["corn", "makka", "corn_(maize)"],
        "common_regions": ["Karnataka", "Madhya Pradesh", "Bihar", "Tamil Nadu", "Telangana"],
    },
    {
        "id": "millets",
        "name": "Millets",
        "category": "Cereals",
        "aliases": ["bajra", "jowar", "ragi", "pearl millet", "sorghum", "finger millet"],
        "common_regions": ["Rajasthan", "Maharashtra", "Karnataka", "Tamil Nadu"],
    },
    {
        "id": "barley",
        "name": "Barley",
        "category": "Cereals",
        "aliases": ["jau"],
        "common_regions": ["Rajasthan", "Uttar Pradesh", "Haryana"],
    },

    # Pulses
    {
        "id": "chickpea",
        "name": "Chickpea",
        "category": "Pulses",
        "aliases": ["gram", "chana", "bengal gram"],
        "common_regions": ["Madhya Pradesh", "Maharashtra", "Rajasthan", "Karnataka"],
    },
    {
        "id": "pigeonpea",
        "name": "Pigeonpea",
        "category": "Pulses",
        "aliases": ["tur", "arhar", "red gram"],
        "common_regions": ["Maharashtra", "Madhya Pradesh", "Karnataka", "Uttar Pradesh"],
    },
    {
        "id": "soybean",
        "name": "Soybean",
        "category": "Pulses",
        "aliases": ["soya", "soyabean"],
        "common_regions": ["Madhya Pradesh", "Maharashtra", "Rajasthan"],
    },
    {
        "id": "groundnut",
        "name": "Groundnut",
        "category": "Pulses",
        "aliases": ["peanut", "moongphali"],
        "common_regions": ["Gujarat", "Andhra Pradesh", "Tamil Nadu", "Karnataka"],
    },
    {
        "id": "blackgram",
        "name": "Blackgram",
        "category": "Pulses",
        "aliases": ["urad", "urad dal"],
        "common_regions": ["Madhya Pradesh", "Uttar Pradesh", "Andhra Pradesh"],
    },
    {
        "id": "greengram",
        "name": "Greengram",
        "category": "Pulses",
        "aliases": ["moong", "mung"],
        "common_regions": ["Rajasthan", "Karnataka", "Maharashtra"],
    },

    # Oilseeds
    {
        "id": "mustard",
        "name": "Mustard",
        "category": "Oilseeds",
        "aliases": ["sarson", "rapeseed", "rai"],
        "common_regions": ["Rajasthan", "Haryana", "Madhya Pradesh", "Uttar Pradesh"],
    },
    {
        "id": "sunflower",
        "name": "Sunflower",
        "category": "Oilseeds",
        "aliases": ["surajmukhi"],
        "common_regions": ["Karnataka", "Andhra Pradesh", "Maharashtra"],
    },
    {
        "id": "sesame",
        "name": "Sesame",
        "category": "Oilseeds",
        "aliases": ["til", "gingelly"],
        "common_regions": ["Gujarat", "West Bengal", "Rajasthan"],
    },

    # Vegetables
    {
        "id": "tomato",
        "name": "Tomato",
        "category": "Vegetables",
        "aliases": ["tamatar"],
        "common_regions": ["Andhra Pradesh", "Madhya Pradesh", "Karnataka", "Odisha", "Gujarat"],
    },
    {
        "id": "potato",
        "name": "Potato",
        "category": "Vegetables",
        "aliases": ["aloo", "alu"],
        "common_regions": ["Uttar Pradesh", "West Bengal", "Bihar", "Gujarat"],
    },
    {
        "id": "chilli",
        "name": "Chilli",
        "category": "Vegetables",
        "aliases": ["mirch", "green chilli", "red chilli", "bell pepper", "capsicum"],
        "common_regions": ["Andhra Pradesh", "Telangana", "Madhya Pradesh", "Karnataka"],
    },
    {
        "id": "onion",
        "name": "Onion",
        "category": "Vegetables",
        "aliases": ["pyaz", "kanda"],
        "common_regions": ["Maharashtra", "Madhya Pradesh", "Karnataka", "Gujarat"],
    },
    {
        "id": "brinjal",
        "name": "Brinjal",
        "category": "Vegetables",
        "aliases": ["eggplant", "baingan", "aubergine"],
        "common_regions": ["West Bengal", "Odisha", "Gujarat", "Bihar"],
    },
    {
        "id": "cabbage",
        "name": "Cabbage",
        "category": "Vegetables",
        "aliases": ["patta gobhi", "bandha kobi"],
        "common_regions": ["West Bengal", "Odisha", "Bihar", "Assam"],
    },
    {
        "id": "cauliflower",
        "name": "Cauliflower",
        "category": "Vegetables",
        "aliases": ["phool gobhi"],
        "common_regions": ["Bihar", "Uttar Pradesh", "West Bengal"],
    },
    {
        "id": "okra",
        "name": "Okra",
        "category": "Vegetables",
        "aliases": ["bhindi", "ladyfinger", "ladies finger"],
        "common_regions": ["Gujarat", "West Bengal", "Bihar"],
    },

    # Fruits
    {
        "id": "apple",
        "name": "Apple",
        "category": "Fruits",
        "aliases": ["seb"],
        "common_regions": ["Jammu and Kashmir", "Himachal Pradesh", "Uttarakhand"],
    },
    {
        "id": "banana",
        "name": "Banana",
        "category": "Fruits",
        "aliases": ["kela"],
        "common_regions": ["Tamil Nadu", "Maharashtra", "Gujarat", "Andhra Pradesh"],
    },
    {
        "id": "mango",
        "name": "Mango",
        "category": "Fruits",
        "aliases": ["aam"],
        "common_regions": ["Uttar Pradesh", "Andhra Pradesh", "Karnataka", "Bihar"],
    },
    {
        "id": "citrus",
        "name": "Citrus",
        "category": "Fruits",
        "aliases": ["orange", "lemon", "lime", "kinnow", "santre", "mosambi"],
        "common_regions": ["Maharashtra", "Andhra Pradesh", "Punjab"],
    },
    {
        "id": "grapes",
        "name": "Grapes",
        "category": "Fruits",
        "aliases": ["angoor"],
        "common_regions": ["Maharashtra", "Karnataka", "Tamil Nadu"],
    },

    # Commercial crops
    {
        "id": "cotton",
        "name": "Cotton",
        "category": "Commercial crops",
        "aliases": ["kapas"],
        "common_regions": ["Gujarat", "Maharashtra", "Telangana", "Andhra Pradesh", "Rajasthan"],
    },
    {
        "id": "sugarcane",
        "name": "Sugarcane",
        "category": "Commercial crops",
        "aliases": ["ganna"],
        "common_regions": ["Uttar Pradesh", "Maharashtra", "Karnataka", "Tamil Nadu"],
    },
    {
        "id": "tobacco",
        "name": "Tobacco",
        "category": "Commercial crops",
        "aliases": ["tambaku"],
        "common_regions": ["Andhra Pradesh", "Gujarat", "Karnataka"],
    },
    {
        "id": "tea",
        "name": "Tea",
        "category": "Commercial crops",
        "aliases": ["chai"],
        "common_regions": ["Assam", "West Bengal", "Tamil Nadu", "Kerala"],
    },
    {
        "id": "coffee",
        "name": "Coffee",
        "category": "Commercial crops",
        "aliases": ["kafi"],
        "common_regions": ["Karnataka", "Kerala", "Tamil Nadu"],
    },
]

# Growth stages
STAGE_REGISTRY: list[dict[str, str]] = [
    {"id": "seedling", "name": "Seedling"},
    {"id": "vegetative", "name": "Vegetative"},
    {"id": "flowering", "name": "Flowering"},
    {"id": "fruiting_grain_filling", "name": "Fruiting / Grain Filling"},
    {"id": "maturity", "name": "Maturity"},
    {"id": "harvest", "name": "Harvest"},
    {"id": "unknown", "name": "Unknown"},
]

_STAGE_ALIASES: dict[str, str] = {
    "seedling": "seedling",
    "sprout": "seedling",
    "nursery": "seedling",
    "vegetative": "vegetative",
    "growth": "vegetative",
    "tillering": "vegetative",
    "flowering": "flowering",
    "bloom": "flowering",
    "anthesis": "flowering",
    "fruiting": "fruiting_grain_filling",
    "grain_filling": "fruiting_grain_filling",
    "grain filling": "fruiting_grain_filling",
    "fruiting / grain filling": "fruiting_grain_filling",
    "pod formation": "fruiting_grain_filling",
    "maturity": "maturity",
    "ripening": "maturity",
    "harvest": "harvest",
    "harvesting": "harvest",
    "post_harvest": "harvest",
    "unknown": "unknown",
}


def get_crop_registry() -> list[dict[str, Any]]:
    return CROPS_REGISTRY


def get_crops_by_category() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {c: [] for c in CATEGORIES}
    for item in CROPS_REGISTRY:
        cat = item.get("category", "Vegetables")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(item)
    return grouped


def normalize_crop(query: str | None) -> dict[str, Any] | None:
    """Normalize user input to a canonical crop item from the registry."""
    if not query:
        return None

    clean = re.sub(r"[_\-\(\)]+", " ", str(query).strip().lower())
    clean = " ".join(clean.split())

    # Exact ID check
    for item in CROPS_REGISTRY:
        if item["id"].lower() == clean:
            return item

    # Display name check
    for item in CROPS_REGISTRY:
        if item["name"].lower() == clean:
            return item

    # Alias check
    for item in CROPS_REGISTRY:
        aliases = [a.lower() for a in item.get("aliases", [])]
        if clean in aliases:
            return item
        for alias in aliases:
            if clean in alias or alias in clean:
                return item

    # Substring / partial match on name or ID
    for item in CROPS_REGISTRY:
        if clean in item["name"].lower() or item["name"].lower() in clean:
            return item
        if clean in item["id"].lower() or item["id"].lower() in clean:
            return item

    return None


def normalize_crop_stage(stage: str | None) -> str:
    """Normalize user-entered crop stage to stable ID."""
    if not stage:
        return "unknown"
    clean = re.sub(r"[\s\-_/]+", " ", str(stage).strip().lower())
    clean = " ".join(clean.split())
    if clean in _STAGE_ALIASES:
        return _STAGE_ALIASES[clean]
    for k, v in _STAGE_ALIASES.items():
        if k in clean:
            return v
    return "unknown"
