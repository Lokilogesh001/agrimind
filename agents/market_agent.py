"""Market Agent — trend and sell/hold signal with strict data provenance.

Market information is advisory context only. Agronomic and safety rules strictly
take precedence over market selling opportunities.

PROVENANCE GUARANTEE:
1. Live APMC Mandi feeds are labeled source='agmarknet_api', status='REAL_DATA', observed_price=float.
2. Cached APMC observations are labeled source='agmarknet_cache', status='CACHED', observed_price=float.
3. Farmer/caller-entered prices are labeled source='caller_provided', status='USER_SUPPLIED', benchmark_price=float.
   Caller benchmark prices are NEVER populated as observed_price or presented as live telemetry.
4. When no market data is available, status='UNAVAILABLE', is_available=False, and sell/hold conclusions are suppressed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from data_sources.market import fetch_prices
from orchestrator.state import MarketResult


def _pct_change(current: float, previous: float) -> float:
    return 0.0 if previous == 0 else round(((current - previous) / previous) * 100, 2)


def _moving_average(prices: list[float]) -> float:
    return round(sum(prices) / len(prices), 2) if prices else 0.0


def run(
    current_price: float = 0.0,
    price_history: list[float] | None = None,
    crop: str = "",
    market: str | None = None,
    weights: dict | None = None,
    growth_stage: str = "",
) -> MarketResult:
    weights = weights or {"trend": 0.5, "volatility": 0.3, "arrival": 0.2}
    price_history = price_history or []

    # 1. Determine if caller provided benchmark prices
    caller_has_price = (current_price > 0 or bool(price_history))
    source = "caller_provided" if caller_has_price else "none"
    status = "USER_SUPPLIED" if caller_has_price else "UNAVAILABLE"

    observed_apmc_price: float | None = None
    retrieval_timestamp: str | None = None
    mandi_name = market or "Regional APMC Mandi"
    commodity_grade = "FAQ (Fair Average Quality)"

    # 2. If caller provided no price data, attempt live/cached fetch from Agmarknet adapter
    if not caller_has_price and crop:
        market_data = fetch_prices(crop=crop, market=market)
        if market_data and isinstance(market_data, dict):
            cp = market_data.get("current_price")
            if cp is not None and float(cp) > 0:
                current_price = float(cp)
                price_history = [float(x) for x in market_data.get("price_history", []) if float(x) >= 0]
                source = market_data.get("source", "agmarknet_api")
                status = market_data.get("status", "REAL_DATA")
                observed_apmc_price = float(cp)
                retrieval_timestamp = market_data.get("retrieval_timestamp")
                mandi_name = market_data.get("mandi_name", mandi_name)
                commodity_grade = market_data.get("commodity_grade", commodity_grade)

    prices = [float(x) for x in price_history if float(x) >= 0]

    # 3. If market data is absent, report unavailable safely without fabricating prices
    if current_price <= 0 and not prices:
        return MarketResult(
            price_change_pct=0.0,
            moving_average=0.0,
            market_score=0.0,
            signal="hold",
            confidence=0.0,
            is_available=False,
            status="UNAVAILABLE",
            source="none",
            authoritative=False,
            benchmark_price=None,
            current_price=None,
            observed_price=None,
            mandi_name=mandi_name,
            commodity_grade=commodity_grade,
            retrieval_timestamp=None,
            market_formula="None (market telemetry unavailable; sell/hold recommendation suppressed)",
            phenology_override_applied=False,
            phenology_note="Market telemetry unavailable. Selling and holding recommendations suppressed.",
        )

    effective_price = float(current_price) if current_price > 0 else (prices[-1] if prices else 0.0)
    ma = _moving_average(prices) if prices else effective_price
    pct_change = _pct_change(effective_price, prices[-1]) if prices else 0.0
    trend = 1.0 if effective_price > ma else 0.0

    if len(prices) > 1 and ma > 0:
        variance = sum((p - ma) ** 2 for p in prices) / len(prices)
        volatility = min((variance ** 0.5) / ma, 1.0)
    else:
        volatility = 0.3

    arrival_indicator = 0.5
    score = round(
        weights["trend"] * trend
        + weights["volatility"] * (1 - volatility)
        + weights["arrival"] * arrival_indicator,
        4,
    )
    signal = "sell" if score > 0.65 else ("hold" if score > 0.4 else "caution")

    # Set confidence based strictly on verified source reliability
    if status == "REAL_DATA":
        confidence = 0.90 if len(prices) >= 3 else 0.80
        authoritative = True
    elif status == "CACHED":
        confidence = 0.75
        authoritative = False
    else:  # USER_SUPPLIED / DEMO_DATA
        confidence = 0.60
        authoritative = False

    now_iso = retrieval_timestamp or datetime.now(timezone.utc).isoformat()

    # STRICT PROVENANCE ASSIGNMENT:
    # Caller prices populate benchmark_price.
    # Observed APMC prices populate observed_price.
    # They are NEVER conflated.
    if status in ("REAL_DATA", "CACHED"):
        benchmark_val = None
        observed_val = effective_price
    else:
        benchmark_val = effective_price
        observed_val = None  # Crucial: User input is NEVER labeled as observed APMC rate

    # Phenology check: if growth stage is specified and not harvest/maturity, flag caution
    phenology_override = False
    phenology_msg = ""
    if growth_stage and growth_stage.lower() not in ("harvest", "mature", "maturity", "ripening"):
        phenology_override = True
        phenology_msg = f"Crop is currently in '{growth_stage}' stage. Immediate harvest for market sale is agronomically unadvised."

    formula_str = (
        f"Score {score:.4f} = (0.50 * Trend:{trend:.0f}) + "
        f"(0.30 * Stability:{1 - volatility:.2f}) + (0.20 * Arrival:{arrival_indicator:.1f})"
    )

    return MarketResult(
        price_change_pct=pct_change,
        moving_average=ma,
        market_score=score,
        signal=signal,
        confidence=confidence,
        is_available=True,
        status=status,
        source=source,
        authoritative=authoritative,
        benchmark_price=benchmark_val,
        current_price=effective_price,
        observed_price=observed_val,
        mandi_name=mandi_name,
        commodity_grade=commodity_grade,
        retrieval_timestamp=now_iso,
        market_formula=formula_str,
        phenology_override_applied=phenology_override,
        phenology_note=phenology_msg,
    )
