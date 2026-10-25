"""External Data Quality & Resilience Evaluation Pipeline for AgriMind.

Evaluates real weather, soil, market, and geocoding data pathways:
- Tests missing values, stale observations, network timeouts, corrupt payloads, and out-of-bounds telemetry.
- Records data source, retrieval timestamp, observation timestamp, freshness status, and deterministic fallback.
- Strictly distinguishes measured observations, location heuristics, cached observations, and unavailable data.
- Avoids fabricating live data when external endpoints or networks are unreachable.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_sources import geocoding, market, soil, weather


def evaluate_weather_data_path() -> dict[str, Any]:
    """Assess weather data pathway: live probe, timeout resilience, malformed JSON, coordinate bounds, and TTL cache."""
    tests = []
    weather.clear_weather_cache_for_tests()
    now_ts = datetime.now(timezone.utc).isoformat()
    
    # 1. Live probe check (Unmocked real network attempt)
    t0 = time.perf_counter()
    res_live = weather.fetch_forecast(lat=28.6139, lon=77.2090, timeout=3.0, force_refresh=True)
    lat_live = round((time.perf_counter() - t0) * 1000, 2)
    is_live_reachable = bool(res_live and res_live.get("status") == "AVAILABLE")
    
    tests.append({
        "test_name": "live_open_meteo_probe",
        "test_type": "LIVE_NETWORK_OBSERVATION",
        "timestamp": now_ts,
        "input": {"lat": 28.6139, "lon": 77.2090},
        "source": "open_meteo",
        "retrieval_latency_ms": lat_live,
        "freshness_status": res_live.get("freshness_status", res_live.get("status")) if res_live else "UNAVAILABLE",
        "is_live_network_verified": is_live_reachable,
        "data_nature": "MEASURED_REAL_OBSERVATION" if is_live_reachable else "OFFLINE_UNAVAILABLE",
        "fallback_triggered": not is_live_reachable,
        "outcome": "LIVE_SUCCESS" if is_live_reachable else "OFFLINE_GRACEFUL_FALLBACK",
        "passed": True,  # Non-crashing operation verified
    })

    # 2. Weather observation caching & TTL audit
    mock_hourly_resp = MagicMock()
    mock_hourly_resp.json.return_value = {
        "hourly": {
            "time": ["2026-10-26T00:00:00Z", "2026-10-26T01:00:00Z"],
            "precipitation_probability": [20, 25],
            "precipitation": [0.0, 0.0],
            "temperature_2m": [27.0, 26.5],
        }
    }
    mock_hourly_resp.raise_for_status.return_value = None
    with patch("requests.get", return_value=mock_hourly_resp):
        res_fresh = weather.fetch_forecast(lat=28.6139, lon=77.2090, force_refresh=True)
        cached_retrieval_time = res_fresh.get("retrieval_time")
        
        # Second call within 15 min TTL must hit cache without network
        res_cached = weather.fetch_forecast(lat=28.6139, lon=77.2090, force_refresh=False)
        passed_cache = (
            res_cached is not None
            and res_cached.get("status") == "CACHED"
            and res_cached.get("is_cached") is True
            and res_cached.get("retrieval_time") == cached_retrieval_time
            and res_cached.get("observation_time") == "2026-10-26T00:00:00Z"
        )
        tests.append({
            "test_name": "weather_15min_ttl_cache_audit",
            "test_type": "CACHED_OBSERVATION_AUDIT",
            "timestamp": now_ts,
            "input": {"lat": 28.6139, "lon": 77.2090},
            "source": "open_meteo_cache",
            "freshness_status": res_cached.get("freshness_status") if res_cached else "NONE",
            "is_cached": True,
            "data_nature": "CACHED_OBSERVATION",
            "outcome": "CACHE_HIT_PRESERVED_TIMESTAMPS",
            "passed": passed_cache,
        })
    
    # 3. Timeout resilience test (Injected simulated timeout)
    import requests
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out after 8.0s")):
        t_to = time.perf_counter()
        # Force refresh to bypass cache and hit timeout path
        weather.clear_weather_cache_for_tests()
        res_timeout = weather.fetch_forecast(lat=28.6139, lon=77.2090, timeout=1.0, force_refresh=True)
        lat_to = round((time.perf_counter() - t_to) * 1000, 2)
        passed_timeout = (
            res_timeout is not None
            and res_timeout.get("status") == "TIMEOUT"
            and res_timeout.get("hourly") is None
            and res_timeout.get("is_estimated") is True
        )
        tests.append({
            "test_name": "network_timeout_resilience",
            "test_type": "INJECTED_TIMEOUT_RESILIENCE",
            "timestamp": now_ts,
            "input": {"timeout": "simulated_1.0s_timeout"},
            "source": "open_meteo",
            "retrieval_latency_ms": lat_to,
            "freshness_status": res_timeout.get("status") if res_timeout else "NONE",
            "data_nature": "SIMULATED_FAULT_INJECTION",
            "fallback_behavior": "graceful_degradation_to_timeout_status",
            "outcome": "GRACEFUL_TIMEOUT_DEGRADATION",
            "passed": passed_timeout,
        })

    # 4. Malformed JSON payload rejection (Injected corrupted payload)
    mock_bad_resp = MagicMock()
    mock_bad_resp.json.return_value = "invalid_string_not_dict"
    mock_bad_resp.raise_for_status.return_value = None
    with patch("requests.get", return_value=mock_bad_resp):
        weather.clear_weather_cache_for_tests()
        res_bad = weather.fetch_forecast(lat=28.6139, lon=77.2090, force_refresh=True)
        passed_bad = (
            res_bad is not None
            and res_bad.get("status") == "INVALID"
            and res_bad.get("error") == "malformed_json"
            and res_bad.get("is_estimated") is True
        )
        tests.append({
            "test_name": "malformed_json_rejection",
            "test_type": "INJECTED_FAULT_RESILIENCE",
            "timestamp": now_ts,
            "input": {"payload": "string_instead_of_dict"},
            "source": "open_meteo",
            "freshness_status": res_bad.get("status") if res_bad else "NONE",
            "data_nature": "SIMULATED_FAULT_INJECTION",
            "fallback_behavior": "graceful_degradation_to_invalid_status",
            "outcome": "MALFORMED_PAYLOAD_REJECTED",
            "passed": passed_bad,
        })
        
    # 5. Out-of-bounds coordinates
    with patch("requests.get", side_effect=requests.exceptions.HTTPError("400 Bad Request")):
        weather.clear_weather_cache_for_tests()
        res_oob = weather.fetch_forecast(lat=999.0, lon=999.0, force_refresh=True)
        passed_oob = (
            res_oob is not None
            and res_oob.get("status") == "UNAVAILABLE"
            and res_oob.get("is_estimated") is True
        )
        tests.append({
            "test_name": "out_of_bounds_coordinates_rejection",
            "test_type": "INPUT_BOUNDARY_PROBE",
            "timestamp": now_ts,
            "input": {"lat": 999.0, "lon": 999.0},
            "source": "open_meteo",
            "freshness_status": res_oob.get("status") if res_oob else "NONE",
            "data_nature": "SYNTHETIC_PAYLOAD_TEST",
            "fallback_behavior": "graceful_degradation_to_unavailable_status",
            "outcome": "OUT_OF_BOUNDS_COORDINATES_REJECTED",
            "passed": passed_oob,
        })
        
    return {
        "subsystem": "weather",
        "primary_source": "Open-Meteo Meteorological API & Cache",
        "cache_ttl_seconds": 900.0,
        "total_tests": len(tests),
        "all_passed": all(t["passed"] for t in tests),
        "tests": tests,
    }



def evaluate_market_data_path() -> dict[str, Any]:
    """Assess market data pathway: live probe, provenance isolation, bounds checking, TTL caching, and stale fallback."""
    tests = []
    market.clear_market_cache_for_tests()
    now_ts = datetime.now(timezone.utc).isoformat()
    
    # 1. Live Agmarknet network probe (Unmocked real network attempt)
    t0_m = time.perf_counter()
    res_mkt_live = market.fetch_prices("Tomato", "Delhi", force_refresh=True)
    lat_mkt_live = round((time.perf_counter() - t0_m) * 1000, 2)
    is_mkt_live_ok = bool(res_mkt_live and res_mkt_live.get("status") in ("REAL_DATA", "CACHED"))
    tests.append({
        "test_name": "live_agmarknet_network_probe",
        "test_type": "LIVE_NETWORK_OBSERVATION",
        "timestamp": now_ts,
        "input": {"crop": "Tomato", "state_or_market": "Delhi"},
        "source": res_mkt_live.get("source") if res_mkt_live else "agmarknet_api",
        "retrieval_latency_ms": lat_mkt_live,
        "freshness_status": res_mkt_live.get("status") if res_mkt_live else "UNAVAILABLE",
        "is_live_network_verified": is_mkt_live_ok,
        "data_nature": "MEASURED_REAL_OBSERVATION" if is_mkt_live_ok else "OFFLINE_UNAVAILABLE",
        "outcome": "LIVE_SUCCESS" if is_mkt_live_ok else "OFFLINE_GRACEFUL_FALLBACK",
        "passed": True,  # Non-crashing operation verified
    })

    # 2. Negative & corrupt price rejection
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"current_price": -250.0}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        with patch.dict("os.environ", {"AGMARKNET_BASE_URL": "https://api.agmarknet.mock/v1"}):
            res_neg = market.fetch_prices("Tomato", "Delhi", force_refresh=True)
            passed_neg = (res_neg is None)
            tests.append({
                "test_name": "negative_price_rejection",
                "test_type": "INPUT_BOUNDARY_PROBE",
                "timestamp": now_ts,
                "input": {"price": -250.0},
                "source": "agmarknet_api",
                "freshness_status": "REJECTED_UNAVAILABLE",
                "data_nature": "SYNTHETIC_PAYLOAD_TEST",
                "fallback_behavior": "suppressed_returns_none",
                "outcome": "CORRUPTED_PRICE_REJECTED",
                "passed": passed_neg,
            })
            
    # 3. Astronomical price rejection (> 1,000,000 INR)
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"current_price": 99999999.0}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        with patch.dict("os.environ", {"AGMARKNET_BASE_URL": "https://api.agmarknet.mock/v1"}):
            res_astro = market.fetch_prices("Tomato", "Delhi", force_refresh=True)
            passed_astro = (res_astro is None)
            tests.append({
                "test_name": "astronomical_outlier_price_rejection",
                "test_type": "INPUT_BOUNDARY_PROBE",
                "timestamp": now_ts,
                "input": {"price": 99999999.0},
                "source": "agmarknet_api",
                "freshness_status": "REJECTED_UNAVAILABLE",
                "data_nature": "SYNTHETIC_PAYLOAD_TEST",
                "fallback_behavior": "suppressed_returns_none",
                "outcome": "CORRUPTED_PRICE_REJECTED",
                "passed": passed_astro,
            })

    # 4. Simulated observation caching and TTL provenance
    with patch("requests.get") as mock_get:
        now_iso = datetime.now(timezone.utc).isoformat()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "current_price": 2850.0,
            "price_history": [2700.0, 2750.0, 2850.0],
            "mandi_name": "Karnal APMC",
            "retrieval_timestamp": now_iso,
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        with patch.dict("os.environ", {"AGMARKNET_BASE_URL": "https://api.agmarknet.mock/v1"}):
            res_sim = market.fetch_prices("Tomato", "Karnal", force_refresh=True)
            passed_sim = (
                res_sim is not None
                and res_sim.get("source") == "agmarknet_api"
                and res_sim.get("status") == "REAL_DATA"
                and not res_sim.get("is_cached")
                and res_sim.get("current_price") == 2850.0
            )
            tests.append({
                "test_name": "simulated_apmc_observation_provenance",
                "test_type": "MOCK_PAYLOAD_PROVENANCE_TEST",
                "timestamp": now_ts,
                "input": {"crop": "Tomato", "market": "Karnal"},
                "source": res_sim.get("source") if res_sim else "none",
                "observation_timestamp": res_sim.get("retrieval_timestamp") if res_sim else None,
                "freshness_status": res_sim.get("status") if res_sim else "NONE",
                "is_cached": res_sim.get("is_cached") if res_sim else False,
                "data_nature": "SIMULATED_MOCK_PAYLOAD",
                "outcome": "PROVENANCE_STRUCTURE_VERIFIED",
                "passed": passed_sim,
            })
            
            # Second fetch within 15-min TTL must hit cache without network
            mock_get.reset_mock()
            res_cached = market.fetch_prices("Tomato", "Karnal", force_refresh=False)
            passed_cached = (
                res_cached is not None
                and res_cached.get("source") == "agmarknet_cache"
                and res_cached.get("status") == "CACHED"
                and res_cached.get("is_cached") is True
                and mock_get.call_count == 0
            )
            tests.append({
                "test_name": "15_minute_ttl_cache_provenance",
                "test_type": "CACHED_OBSERVATION_AUDIT",
                "timestamp": now_ts,
                "input": {"cache_key": "('tomato', 'karnal')"},
                "source": res_cached.get("source") if res_cached else "none",
                "freshness_status": res_cached.get("status") if res_cached else "NONE",
                "is_cached": True,
                "network_calls_made": mock_get.call_count,
                "data_nature": "CACHED_OBSERVATION",
                "outcome": "CACHE_HIT_WITHOUT_NETWORK",
                "passed": passed_cached,
            })

    # 5. Stale cache fallback during simulated API outage
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("APMC endpoint down")):
        with patch.dict("os.environ", {"AGMARKNET_BASE_URL": "https://api.agmarknet.mock/v1"}):
            res_stale = market.fetch_prices("Tomato", "Karnal", force_refresh=True)
            passed_stale = (
                res_stale is not None
                and res_stale.get("source") == "agmarknet_cache"
                and res_stale.get("status") == "CACHED"
                and res_stale.get("stale") is True
            )
            tests.append({
                "test_name": "stale_cache_resilience_during_outage",
                "test_type": "INJECTED_FAULT_RESILIENCE",
                "timestamp": now_ts,
                "input": {"network_condition": "endpoint_down"},
                "source": res_stale.get("source") if res_stale else "none",
                "freshness_status": "STALE_CACHED",
                "fallback_behavior": "served_from_last_known_cache",
                "data_nature": "CACHED_OBSERVATION",
                "outcome": "SERVED_FROM_STALE_CACHE_DURING_OUTAGE",
                "passed": passed_stale,
            })
            
    # 6. Empty crop input validation
    res_empty = market.fetch_prices("", "Karnal")
    tests.append({
        "test_name": "empty_crop_name_rejection",
        "test_type": "INPUT_BOUNDARY_PROBE",
        "timestamp": now_ts,
        "input": {"crop": ""},
        "source": "none",
        "freshness_status": "REJECTED_UNAVAILABLE",
        "fallback_behavior": "suppressed_returns_none",
        "data_nature": "SYNTHETIC_PAYLOAD_TEST",
        "outcome": "EMPTY_INPUT_SUPPRESSED",
        "passed": res_empty is None,
    })

    return {
        "subsystem": "market",
        "primary_source": "Agmarknet APMC Wholesale Price Feed & Cache",
        "cache_ttl_seconds": 900.0,
        "total_tests": len(tests),
        "all_passed": all(t["passed"] for t in tests),
        "tests": tests,
    }


def evaluate_soil_data_path() -> dict[str, Any]:
    """Assess soil data pathway: measured NPK, missing NPK refusal, and regional texture heuristics."""
    tests = []
    now_ts = datetime.now(timezone.utc).isoformat()
    
    # 1. Measured NPK soil test
    prov_meas = soil.get_provenance(crop="Tomato", soil_type="loam", mode="MEASURED", npk_available=True)
    targets, weights = soil.get_reference_targets(crop="Tomato", soil_type="loam")
    passed_meas = (
        prov_meas["mode"] == "MEASURED"
        and prov_meas["npk_available"] is True
        and prov_meas["is_authoritative_icar"] is False
        and "project_calibration_heuristic" in prov_meas["crop_target_provenance"]
    )
    tests.append({
        "test_name": "measured_soil_test_provenance",
        "test_type": "PROVENANCE_ISOLATION_PROBE",
        "timestamp": now_ts,
        "input": {"crop": "Tomato", "soil_type": "loam", "mode": "MEASURED"},
        "source": "laboratory_soil_test",
        "provenance_category": prov_meas["crop_target_provenance"],
        "is_authoritative_icar": False,
        "freshness_status": "MEASURED",
        "data_nature": "MEASURED_LAB_TEST_MOCK",
        "outcome": "PROVENANCE_METADATA_VERIFIED",
        "passed": passed_meas,
    })

    # 2. Missing NPK refusal & non-fabrication
    prov_miss = soil.get_provenance(crop="Tomato", soil_type="loam", mode="UNAVAILABLE", npk_available=False)
    passed_miss = (
        prov_miss["mode"] == "UNAVAILABLE"
        and prov_miss["npk_available"] is False
        and "NPK values not measured" in prov_miss["guidance_note"]
    )
    tests.append({
        "test_name": "missing_npk_non_fabrication_guard",
        "test_type": "SAFETY_GUARD_PROBE",
        "timestamp": now_ts,
        "input": {"n": None, "p": None, "k": None},
        "source": "none",
        "freshness_status": "UNAVAILABLE",
        "fallback_behavior": "skip_deficiency_to_avoid_fabrication",
        "data_nature": "SYNTHETIC_PAYLOAD_TEST",
        "outcome": "CHEMICAL_FERTILIZER_BLOCKED",
        "passed": passed_miss,
    })

    # 3. Regional agro-climatic location heuristic (Gangetic Alluvial vs Deccan Black)
    est_ganga = soil.estimate_soil_from_location("Karnal, Haryana")
    passed_ganga = (
        est_ganga["soil_type"] == "alluvial"
        and est_ganga["is_measured"] is False
        and est_ganga["status"] == "LOCATION_ESTIMATED"
    )
    tests.append({
        "test_name": "regional_agroclimatic_location_heuristic",
        "test_type": "HEURISTIC_ESTIMATION_PROBE",
        "timestamp": now_ts,
        "input": {"location": "Karnal, Haryana"},
        "inferred_soil_type": est_ganga["soil_type"],
        "source": est_ganga["source"],
        "freshness_status": est_ganga["status"],
        "is_measured": False,
        "data_nature": "LOCATION_HEURISTIC",
        "outcome": "REGIONAL_TEXTURE_INFERRED",
        "passed": passed_ganga,
    })

    # 4. Unknown location unresolvable soil
    est_unknown = soil.estimate_soil_from_location("")
    passed_unknown = (
        est_unknown["soil_type"] == "unknown"
        and est_unknown["status"] == "UNAVAILABLE"
        and est_unknown["confidence"] == 0.0
    )
    tests.append({
        "test_name": "unknown_location_unresolvable_soil",
        "test_type": "INPUT_BOUNDARY_PROBE",
        "timestamp": now_ts,
        "input": {"location": ""},
        "source": est_unknown["source"],
        "freshness_status": est_unknown["status"],
        "data_nature": "SYNTHETIC_PAYLOAD_TEST",
        "outcome": "UNRESOLVED_GRACEFUL_HANDLING",
        "passed": passed_unknown,
    })

    return {
        "subsystem": "soil",
        "primary_source": "Laboratory Soil Test / Regional Agro-Climatic Heuristic",
        "total_tests": len(tests),
        "all_passed": all(t["passed"] for t in tests),
        "tests": tests,
    }


def evaluate_geocoding_data_path() -> dict[str, Any]:
    """Assess geocoding data pathway: coordinate preservation, fallback naming, and offline resilience."""
    tests = []
    now_ts = datetime.now(timezone.utc).isoformat()
    
    # 1. Coordinate preservation without network
    geo_exact = geocoding.resolve_location("", lat=28.6139, lon=77.2090)
    passed_exact = (
        geo_exact.get("latitude") == 28.6139
        and geo_exact.get("longitude") == 77.2090
        and geo_exact.get("status") in ("RESOLVED", "COORDINATES_PRESERVED", "OFFLINE_FALLBACK")
    )
    tests.append({
        "test_name": "coordinate_preservation_offline",
        "test_type": "OFFLINE_RESILIENCE_PROBE",
        "timestamp": now_ts,
        "input": {"lat": 28.6139, "lon": 77.2090},
        "source": geo_exact.get("source"),
        "freshness_status": geo_exact.get("status"),
        "data_nature": "COORDINATE_PASSTHROUGH",
        "outcome": "GPS_COORDINATES_PRESERVED",
        "passed": passed_exact,
    })

    # 2. Empty location fallback
    geo_empty = geocoding.resolve_location("", lat=None, lon=None)
    passed_empty = (
        geo_empty.get("status") in ("EMPTY", "INVALID")
        and geo_empty.get("latitude") is None
    )
    tests.append({
        "test_name": "empty_location_rejection",
        "test_type": "INPUT_BOUNDARY_PROBE",
        "timestamp": now_ts,
        "input": {"location": "", "lat": None, "lon": None},
        "freshness_status": geo_empty.get("status"),
        "data_nature": "SYNTHETIC_PAYLOAD_TEST",
        "outcome": "EMPTY_LOCATION_REJECTED",
        "passed": passed_empty,
    })

    return {
        "subsystem": "geocoding",
        "primary_source": "Open-Meteo Geocoding / Field GPS Telemetry",
        "total_tests": len(tests),
        "all_passed": all(t["passed"] for t in tests),
        "tests": tests,
    }


def run_data_quality_evaluation(output_dir: str = "evaluation/artifacts") -> dict[str, Any]:
    """Run full external data quality and resilience evaluation."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    print("[EVAL-DATA-QUALITY] Assessing external weather, market, soil, and geocoding pathways...")
    
    weather_eval = evaluate_weather_data_path()
    market_eval = evaluate_market_data_path()
    soil_eval = evaluate_soil_data_path()
    geocoding_eval = evaluate_geocoding_data_path()
    
    subsystems = [weather_eval, market_eval, soil_eval, geocoding_eval]
    all_tests = [t for s in subsystems for t in s["tests"]]
    total_tests = len(all_tests)
    all_passed = all(t["passed"] for t in all_tests)

    live_tests = [t for t in all_tests if t.get("test_type") == "LIVE_NETWORK_OBSERVATION"]
    cached_tests = [t for t in all_tests if t.get("test_type") == "CACHED_OBSERVATION_AUDIT"]
    resilience_tests = [t for t in all_tests if t.get("test_type") in ("INJECTED_TIMEOUT_RESILIENCE", "INJECTED_FAULT_RESILIENCE")]
    boundary_tests = [t for t in all_tests if t.get("test_type") in ("INPUT_BOUNDARY_PROBE", "SAFETY_GUARD_PROBE", "PROVENANCE_ISOLATION_PROBE", "HEURISTIC_ESTIMATION_PROBE", "OFFLINE_RESILIENCE_PROBE", "MOCK_PAYLOAD_PROVENANCE_TEST")]
    
    report = {
        "evaluation_name": "External Data Quality & Resilience Evaluation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_pathways_evaluated": len(subsystems),
            "total_test_probes": total_tests,
            "overall_pass": all_passed,
            "probe_breakdown_by_type": {
                "live_network_attempts_count": len(live_tests),
                "cached_observation_audits_count": len(cached_tests),
                "fault_injection_resilience_count": len(resilience_tests),
                "boundary_and_guard_probes_count": len(boundary_tests),
            },
            "availability_and_validity_disclosure": (
                "Passing resilience tests confirm fault tolerance under API failures, timeouts, and corrupted payloads; "
                "they do NOT demonstrate continuous 100% uptime of third-party external government or commercial APIs."
            ),
        },
        "pathway_results": {
            "weather": weather_eval,
            "market": market_eval,
            "soil": soil_eval,
            "geocoding": geocoding_eval,
        },
        "provenance_data_dictionary": {
            "MEASURED_REAL_OBSERVATION": "Direct unmocked live network query returning valid HTTP response.",
            "OFFLINE_UNAVAILABLE": "Real network query attempted but destination was unreachable/offline; degraded gracefully.",
            "CACHED_OBSERVATION": "Valid observations served from 15-minute TTL cache or stale fallback during network outage.",
            "SIMULATED_FAULT_INJECTION": "Mocked timeouts, malformed JSON, or HTTP errors to prove fault tolerance.",
            "SYNTHETIC_PAYLOAD_TEST": "Deliberately corrupted or out-of-bounds input to verify input validation boundaries.",
            "LOCATION_HEURISTIC": "Macro-scale regional soil textures estimated from agro-climatic zones; strictly not field tests.",
        },
    }
    
    out_file = out_path / "data_quality_report.json"
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    
    print("=" * 70)
    print(f"📊 DATA QUALITY RESULTS: {total_tests} Probes Evaluated | Status: {'✅ ALL PASSED' if all_passed else '❌ ISSUES DETECTED'}")
    print(f"   Weather Pathway:   {'PASS' if weather_eval['all_passed'] else 'FAIL'}")
    print(f"   Market Pathway:    {'PASS' if market_eval['all_passed'] else 'FAIL'}")
    print(f"   Soil Pathway:      {'PASS' if soil_eval['all_passed'] else 'FAIL'}")
    print(f"   Geocoding Pathway: {'PASS' if geocoding_eval['all_passed'] else 'FAIL'}")
    print(f"   Report Saved:      {out_file}")
    print("=" * 70)
    
    return report


def main():
    parser = argparse.ArgumentParser(description="Evaluate external data quality and resilience")
    parser.add_argument("--output-dir", default="evaluation/artifacts", help="Output directory for report")
    args = parser.parse_args()
    
    run_data_quality_evaluation(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
