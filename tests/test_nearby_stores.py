"""Tests for AgriMind Nearby Agricultural Stores Discovery Feature.

Covers all 20 required verification criteria:
1. Valid farm location
2. Multiple nearby stores
3. One nearby store
4. No nearby stores
5. Missing phone number
6. Missing opening hours
7. Missing website
8. Missing rating
9. Business API failure
10. Invalid coordinates
11. Distance calculation
12. Search radius
13. Store result serialization
14. Frontend rendering contract
15. Call button contact integrity
16. Directions button URL format
17. No fabricated stock
18. No fabricated price
19. OpenAI remains unrelated to store discovery
20. Existing advisory remains functional
"""
from __future__ import annotations

import math
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from api.main import app
from data_sources.stores import (
    DEFAULT_SEARCH_RADIUS_KM,
    VerifiedStore,
    find_nearby_stores,
    haversine_distance_km,
    query_verified_registry,
)


@pytest.fixture
def client():
    return TestClient(app)


# 1. Valid farm location
def test_valid_farm_location(client):
    """Test store discovery near valid farm location (Madurai)."""
    response = client.get("/api/nearby-stores?lat=9.9252&lon=78.1198&radius=15")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["count"] > 0
    assert len(data["stores"]) > 0
    for store in data["stores"]:
        assert store["name"]
        assert store["address"]
        assert store["verified"] is True
        assert -90.0 <= store["latitude"] <= 90.0
        assert -180.0 <= store["longitude"] <= 180.0
        assert store["distance_km"] <= 15.0


# 2. Multiple nearby stores
def test_multiple_nearby_stores(client):
    """Test retrieving multiple stores within a 20 km radius around Madurai."""
    result = find_nearby_stores(lat=9.9500, lon=78.1500, radius_km=20.0)
    assert result["status"] == "success"
    assert result["count"] >= 2
    assert len(result["stores"]) >= 2
    # Check that stores are sorted by distance ascending
    distances = [s["distance_km"] for s in result["stores"]]
    assert distances == sorted(distances)


# 3. One nearby store
def test_one_nearby_store():
    """Test search with a radius calibrated to yield exactly one store."""
    # Near Othakadai AC&RI campus (9.9723, 78.1887) with a tiny 0.5 km radius
    result = find_nearby_stores(lat=9.9723, lon=78.1887, radius_km=0.5)
    assert result["status"] == "success"
    assert result["count"] == 1
    assert "AC&RI" in result["stores"][0]["name"]


# 4. No nearby stores
def test_no_nearby_stores(client):
    """Test remote oceanic coordinates where no stores exist."""
    response = client.get("/api/nearby-stores?lat=0.0&lon=65.0&radius=15")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["count"] == 0
    assert data["stores"] == []


# 5. Missing phone number
def test_missing_phone_number():
    """When a store's public phone is not provided, phone must be null/None, never fabricated."""
    stores = query_verified_registry(farm_lat=10.0, farm_lon=78.2, radius_km=5.0)
    pacs_store = next((s for s in stores if "Primary Agricultural Cooperative" in s.name), None)
    assert pacs_store is not None
    assert pacs_store.phone is None
    # Serialized dict must also have phone as None
    assert pacs_store.to_dict()["phone"] is None


# 6. Missing opening hours
def test_missing_opening_hours():
    """When opening hours are missing, opening_hours must be null/None."""
    store = VerifiedStore(
        id="test_store_1",
        name="District Input Centre",
        address="Main Road, Rural District",
        latitude=10.0,
        longitude=78.0,
        distance_km=2.5,
        phone=None,
        website=None,
        opening_hours=None,
        rating=None,
        category="Agricultural Input Store",
        maps_url="https://www.google.com/maps",
        source="TEST",
    )
    d = store.to_dict()
    assert d["opening_hours"] is None


# 7. Missing website
def test_missing_website():
    """When website is not provided, website must be null/None."""
    stores = query_verified_registry(farm_lat=13.0, farm_lon=80.2, radius_km=10.0)
    tnaic = next((s for s in stores if "TNAIC" in s.name), None)
    assert tnaic is not None
    assert tnaic.website is None
    assert tnaic.to_dict()["website"] is None


# 8. Missing rating
def test_missing_rating():
    """When rating is unavailable, rating must be null/None."""
    stores = query_verified_registry(farm_lat=10.0, farm_lon=78.2, radius_km=5.0)
    pacs = next((s for s in stores if "Primary Agricultural Cooperative" in s.name), None)
    assert pacs is not None
    assert pacs.rating is None
    assert pacs.to_dict()["rating"] is None


# 9. Business API failure
def test_business_api_failure(client):
    """Simulate backend store lookup exception: returns fallback payload without crashing."""
    with patch("api.main.find_nearby_stores", side_effect=RuntimeError("Connection to Overpass failed")):
        response = client.get("/api/nearby-stores?lat=9.9252&lon=78.1198")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unavailable"
        assert "temporarily unavailable" in data["message"]
        assert data["stores"] == []


# 10. Invalid coordinates
def test_invalid_coordinates(client):
    """Reject out-of-bounds coordinates with HTTP 422."""
    res_lat = client.get("/api/nearby-stores?lat=120.0&lon=78.0")
    assert res_lat.status_code == 422
    assert "out of bounds" in res_lat.json()["detail"].lower()

    res_lon = client.get("/api/nearby-stores?lat=12.0&lon=-200.0")
    assert res_lon.status_code == 422
    assert "out of bounds" in res_lon.json()["detail"].lower()


# 11. Distance calculation
def test_distance_calculation():
    """Verify accuracy of Haversine distance calculation."""
    # Distance from Chennai (13.0827, 80.2707) to Madurai (9.9252, 78.1198)
    # Great circle distance is ~420 km
    dist = haversine_distance_km(13.0827, 80.2707, 9.9252, 78.1198)
    assert 415.0 <= dist <= 430.0

    # Same point distance must be 0.0
    zero_dist = haversine_distance_km(9.9252, 78.1198, 9.9252, 78.1198)
    assert zero_dist == 0.0


# 12. Search radius
def test_search_radius():
    """Verify stores outside search radius are excluded."""
    # AC&RI Madurai is at ~9.9723, 78.1887. Distance from Madurai center is ~9 km.
    # Searching with 5 km radius should exclude it.
    res_tight = find_nearby_stores(lat=9.9252, lon=78.1198, radius_km=5.0)
    for s in res_tight["stores"]:
        assert s["distance_km"] <= 5.0

    # Searching with 20 km radius should include it.
    res_wide = find_nearby_stores(lat=9.9252, lon=78.1198, radius_km=20.0)
    acri = next((s for s in res_wide["stores"] if "AC&RI" in s["name"]), None)
    assert acri is not None
    assert acri["distance_km"] <= 20.0


# 13. Store result serialization
def test_store_result_serialization():
    """Verify serialized store schema contains all required contract fields."""
    store = VerifiedStore(
        id="test_01",
        name="Agro Seva Kendra",
        address="Kachhwa Road, Karnal, Haryana",
        latitude=29.7040,
        longitude=76.9530,
        distance_km=3.2,
        phone="+91 184 229 0501",
        website="https://cssri.res.in",
        opening_hours="Mon-Fri 09:00 - 17:00",
        rating=4.6,
        category="Farm Input Center",
        maps_url="https://www.google.com/maps/dir/?api=1&destination=29.704,76.953",
        source="ICAR_KVK_REGISTRY",
    )
    d = store.to_dict()
    required_keys = {
        "id", "name", "address", "latitude", "longitude", "distance_km",
        "phone", "website", "opening_hours", "rating", "category",
        "maps_url", "source", "verified", "product_stock", "retailer_price"
    }
    assert required_keys.issubset(d.keys())
    assert d["verified"] is True
    assert d["product_stock"] == "Not verified"
    assert d["retailer_price"] == "Not verified"


# 14. Frontend rendering contract
def test_frontend_rendering_contract(client):
    """Test that location resolver works seamlessly with store lookup."""
    response = client.get("/api/nearby-stores?location=Madurai&radius=15")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "location" in data
    assert "Madurai" in data["location"]["location_name"]
    assert data["location"]["latitude"] is not None


# 15. Call button contact integrity
def test_call_button_contact_integrity(client):
    """Ensure phone numbers are genuine and non-empty when present."""
    response = client.get("/api/nearby-stores?lat=9.9252&lon=78.1198&radius=15")
    data = response.json()
    stores_with_phone = [s for s in data["stores"] if s["phone"] is not None]
    assert len(stores_with_phone) > 0
    for s in stores_with_phone:
        phone = s["phone"]
        # Ensure it has digits and reasonable length for a phone number
        digits = [c for c in phone if c.isdigit()]
        assert len(digits) >= 6
        assert len(phone) >= 6


# 16. Directions button URL format
def test_directions_button_url(client):
    """Directions URL must use verified latitude and longitude coordinates."""
    response = client.get("/api/nearby-stores?lat=9.9252&lon=78.1198&radius=15")
    data = response.json()
    for store in data["stores"]:
        maps_url = store["maps_url"]
        assert "https://www.google.com/maps/dir/?api=1&destination=" in maps_url
        lat_str = str(store["latitude"])
        lon_str = str(store["longitude"])
        assert lat_str in maps_url or f"{store['latitude']:.4f}" in maps_url
        assert lon_str in maps_url or f"{store['longitude']:.4f}" in maps_url


# 17. No fabricated stock
def test_no_fabricated_stock(client):
    """MANDATORY: Never claim specific stock like 'Urea available' without real inventory."""
    response = client.get("/api/nearby-stores?lat=9.9252&lon=78.1198&radius=15")
    data = response.json()
    for store in data["stores"]:
        assert store["product_stock"] == "Not verified"
        assert "available" not in store["product_stock"].lower() or store["product_stock"] == "Not verified"


# 18. No fabricated price
def test_no_fabricated_price(client):
    """MANDATORY: Never claim fabricated retailer price."""
    response = client.get("/api/nearby-stores?lat=9.9252&lon=78.1198&radius=15")
    data = response.json()
    for store in data["stores"]:
        assert store["retailer_price"] == "Not verified"


# 19. OpenAI remains unrelated to store discovery
def test_openai_remains_unrelated_to_store_discovery():
    """Verify OpenAI is NOT imported or called anywhere in stores.py."""
    import inspect
    import data_sources.stores as stores_module

    source_code = inspect.getsource(stores_module)
    assert "openai" not in source_code.lower()
    assert "chat.completions" not in source_code.lower()
    assert "gpt" not in source_code.lower()


# 20. Existing advisory remains functional
def test_existing_advisory_remains_functional(client):
    """Ensure running an advisory returns recommendation and populates nearby_stores."""
    payload = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "location_name": "Madurai",
        "lat": 9.9252,
        "lon": 78.1198,
        "n": 120.0,
        "p": 45.0,
        "k": 50.0,
        "soil_mode": "MEASURED",
        "current_price": 25.0,
    }
    response = client.post("/api/advisory", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Check deterministic recommendation intact
    assert data["recommendation"]
    assert "confidence" in data
    # Check that nearby_stores is included in the advisory response
    assert "nearby_stores" in data
    assert isinstance(data["nearby_stores"], list)
    assert len(data["nearby_stores"]) > 0
    assert data["nearby_stores"][0]["verified"] is True
    assert data["nearby_stores"][0]["product_stock"] == "Not verified"
    assert data["nearby_stores"][0]["retailer_price"] == "Not verified"
