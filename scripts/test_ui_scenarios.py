import os
import sys
import requests

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

API_URL = "http://127.0.0.1:8000/api/advisory"

def _post(payload: dict) -> dict:
    try:
        r = requests.post(API_URL, json=payload, timeout=1.0)
        return r.json()
    except Exception:
        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app)
        return client.post("/api/advisory", json=payload).json()


def test_scenarios():
    print("Testing AgriMind API Scenarios...")

    # SCENARIO 1: Healthy crop
    p1 = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
        "disease_override": {"predicted_class": "healthy", "confidence": 0.95},
    }
    r1 = _post(p1)
    assert "healthy" in r1["disease"]["predicted_class"].lower()
    assert r1["recommendation"] != "DISEASE_MANAGEMENT_FIRST"
    print("✓ Scenario 1 (Healthy crop): PASSED -> disease is healthy, no disease treatment priority")

    # SCENARIO 2: Disease detected + nutrient deficiency
    p2 = {
        "crop": "Tomato",
        "growth_stage": "flowering",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
        "n": 20, "p": 30, "k": 40,
        "soil_type": "red_soil",
        "soil_mode": "MEASURED",
        "disease_override": {"predicted_class": "Tomato___Late_blight", "confidence": 0.89},
    }
    r2 = _post(p2)
    assert r2["recommendation"] == "DISEASE_MANAGEMENT_FIRST"
    assert r2["soil"]["npk_available"] is True
    assert r2["soil"]["overall_deficiency"] > 0.5
    print("✓ Scenario 2 (Disease detected + nutrient deficiency): PASSED -> DISEASE_MANAGEMENT_FIRST prioritized; soil deficiency tracked separately")

    # SCENARIO 3: Disease detected + no nutrient deficiency
    p3 = {
        "crop": "Tomato",
        "growth_stage": "flowering",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
        "n": 250, "p": 120, "k": 250,  # Adequate nutrients
        "soil_type": "red_soil",
        "soil_mode": "MEASURED",
        "disease_override": {"predicted_class": "Tomato___Late_blight", "confidence": 0.89},
    }
    r3 = _post(p3)
    assert r3["recommendation"] == "DISEASE_MANAGEMENT_FIRST"
    assert r3["soil"]["overall_deficiency"] == 0.0
    print("✓ Scenario 3 (Disease detected + no nutrient deficiency): PASSED -> Disease management prioritized; zero soil deficiency")

    # SCENARIO 4: Low-confidence disease prediction
    p4 = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
        "disease_override": {"predicted_class": "Tomato___Late_blight", "confidence": 0.42},
    }
    r4 = _post(p4)
    assert r4["disease"]["confidence"] < 0.60
    assert r4["disease"]["actionable"] is False
    assert r4["recommendation"] != "DISEASE_MANAGEMENT_FIRST"
    print("✓ Scenario 4 (Low-confidence disease prediction): PASSED -> Action blocked (<60% confidence gate)")

    # SCENARIO 5: Safe weather vs rain risk delay
    p5 = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
        "weather_override": {"precip_prob": 0.95, "intensity": 0.9, "duration": 0.8},
    }
    r5 = _post(p5)
    assert r5["recommendation"] == "DELAY"
    assert r5["weather_risk"]["level"] in ("HIGH", "SEVERE")
    print("✓ Scenario 5 (Heavy rain risk): PASSED -> DELAY enforced due to precipitation safety rule")

    # SCENARIO 6: Missing soil data (unmeasured NPK)
    p6 = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
    }
    r6 = _post(p6)
    assert r6["soil"]["npk_available"] is False
    assert r6["soil_nutrient_status"]["npk_available"] is False
    print("✓ Scenario 6 (Missing soil NPK): PASSED -> Soil deficiency not fabricated; unmeasured mode enforced")

    # SCENARIO 7: Soil deficiency fertilizer recommendation
    p7 = {
        "crop": "Tomato",
        "growth_stage": "vegetative",
        "location_name": "Madurai, Tamil Nadu",
        "lat": 9.9252,
        "lon": 78.1198,
        "n": 20, "p": 45, "k": 70,
        "soil_type": "red_soil",
        "soil_mode": "MEASURED",
        "weather_override": {"precip_prob": 0.05, "intensity": 0.0, "duration": 0.0},
        "disease_override": {"predicted_class": "healthy", "confidence": 0.95},
    }
    r7 = _post(p7)
    assert r7["recommendation"] == "apply_fertilizer"
    print("✓ Scenario 7 (Fertilizer recommended): PASSED -> apply_fertilizer when deficiency exists and weather is safe")

    print("\nAll 7 live API scenarios verified successfully!")

if __name__ == "__main__":
    test_scenarios()
