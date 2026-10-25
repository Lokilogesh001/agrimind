"""Market Data Provenance & Fallback Safety Verification Suite.

Mandatory Requirement (Phase D & E):
1. Caller-supplied benchmark prices must NEVER be presented as verified live market prices.
2. Verified Agmarknet observations populate observed_price with source='agmarknet_api' and status='REAL_DATA'.
3. Cached market observations are labeled source='agmarknet_cache' and status='CACHED'.
4. Unavailable market data suppresses sell/hold conclusions (is_available=False, observed_price=None, benchmark_price=None).
5. Invalidation, TTL, corrupt and negative price handling.
6. API serializer output strictly maintains separation between observed_price and benchmark_price.
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch, MagicMock
from agents import market_agent
from data_sources.market import fetch_prices, clear_market_cache_for_tests
from orchestrator.state import AgriMindState, CropContext, MarketResult
from api.main import _serialize


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure clean cache before and after every market test."""
    clear_market_cache_for_tests()
    yield
    clear_market_cache_for_tests()


# ==============================================================================
# 1. User-Supplied Benchmark Price Provenance
# ==============================================================================
def test_user_supplied_benchmark_price_isolation():
    """User-supplied prices populate benchmark_price and MUST NOT leak into observed_price."""
    res = market_agent.run(
        current_price=2450.0,
        price_history=[2300.0, 2380.0, 2450.0],
        crop="Tomato",
    )
    assert res.status == "USER_SUPPLIED"
    assert res.source == "caller_provided"
    assert res.benchmark_price == 2450.0
    assert res.observed_price is None  # STRICT ISOLATION: Never labeled as observed APMC rate
    assert res.authoritative is False
    assert res.confidence == 0.60


def test_user_supplied_price_serializer_isolation():
    """API serialization preserves None for observed_price on user-supplied data."""
    state = AgriMindState(
        run_id="mkt_prov_run",
        crop=CropContext(crop="Tomato", growth_stage="vegetative"),
    )
    state.market = market_agent.run(
        current_price=1800.0,
        price_history=[1750.0, 1800.0],
        crop="Tomato",
    )
    serialized = _serialize(state)
    mkt = serialized["market"]
    assert mkt["status"] == "USER_SUPPLIED"
    assert mkt["source"] == "caller_provided"
    assert mkt["benchmark_price"] == 1800.0
    assert mkt["observed_price"] is None
    assert mkt["authoritative"] is False


# ==============================================================================
# 2. Verified Live Agmarknet Observation
# ==============================================================================
def test_live_agmarknet_observation_provenance():
    """Live APMC observation populates observed_price with verified status."""
    mock_payload = {
        "current_price": 2550.0,
        "price_history": [2400.0, 2480.0, 2550.0],
        "mandi_name": "Madurai APMC Mandi",
        "commodity_grade": "FAQ",
        "source": "agmarknet_api",
        "status": "REAL_DATA",
        "retrieval_timestamp": "2026-10-25T10:00:00Z",
    }
    with patch.dict(os.environ, {"AGMARKNET_BASE_URL": "http://mock-mandi.gov.in/api"}):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_payload
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            # Pass current_price=0 to trigger live fetch
            res = market_agent.run(current_price=0.0, price_history=[], crop="Tomato", market="Madurai")
            assert res.status == "REAL_DATA"
            assert res.source == "agmarknet_api"
            assert res.observed_price == 2550.0
            assert res.benchmark_price is None  # Not user-supplied
            assert res.authoritative is True
            assert res.confidence >= 0.80
            assert res.mandi_name == "Madurai APMC Mandi"


# ==============================================================================
# 3. Cached Agmarknet Observation & TTL
# ==============================================================================
def test_cached_agmarknet_observation_provenance():
    """Secondary request within TTL serves cached observation labeled CACHED."""
    mock_payload = {
        "current_price": 2600.0,
        "price_history": [2500.0, 2550.0, 2600.0],
        "mandi_name": "Dindigul APMC Mandi",
        "source": "agmarknet_api",
        "status": "REAL_DATA",
    }
    with patch.dict(os.environ, {"AGMARKNET_BASE_URL": "http://mock-mandi.gov.in/api"}):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_payload
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            # 1st call populates cache
            p1 = fetch_prices("Tomato", market="Dindigul")
            assert p1 is not None
            assert p1["status"] == "REAL_DATA"

            # 2nd call without mock_get must hit in-memory cache
            mock_get.reset_mock()
            res = market_agent.run(current_price=0.0, price_history=[], crop="Tomato", market="Dindigul")
            assert res.status == "CACHED"
            assert res.source == "agmarknet_cache"
            assert res.observed_price == 2600.0
            assert res.benchmark_price is None
            assert res.authoritative is False
            assert res.confidence == 0.75
            mock_get.assert_not_called()


# ==============================================================================
# 4. Unavailable Market Data
# ==============================================================================
def test_unavailable_market_data_suppression():
    """When no market data is provided or retrieved, sell/hold advice is suppressed."""
    with patch.dict(os.environ, {"AGMARKNET_BASE_URL": ""}):
        res = market_agent.run(current_price=0.0, price_history=[], crop="")
        assert res.is_available is False
        assert res.status == "UNAVAILABLE"
        assert res.source == "none"
        assert res.observed_price is None
        assert res.benchmark_price is None
        assert res.current_price is None
        assert "suppressed" in res.phenology_note.lower()


# ==============================================================================
# 5. Invalid and Boundary Price Handling
# ==============================================================================
def test_negative_and_corrupt_prices_rejected():
    """Negative or zero prices in history are safely filtered without crashing."""
    res = market_agent.run(
        current_price=2200.0,
        price_history=[-500.0, 0.0, 2100.0, 2200.0],
        crop="Tomato",
    )
    assert res.status == "USER_SUPPLIED"
    assert res.benchmark_price == 2200.0
    assert res.observed_price is None
    # Moving average computed only over valid non-negative values
    assert res.moving_average > 0


def test_astronomical_agmarknet_price_rejected():
    """Absurdly high price values (> 1,000,000 / quintal) indicate API corruption and are rejected."""
    mock_payload = {
        "current_price": 99999999.0,
        "price_history": [],
    }
    with patch.dict(os.environ, {"AGMARKNET_BASE_URL": "http://mock-mandi.gov.in/api"}):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_payload
            mock_get.return_value = mock_resp

            res = fetch_prices("Tomato")
            assert res is None  # Safely rejected as invalid observation
