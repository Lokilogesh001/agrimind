"""Market Agent — trend and sell/hold signal.

Market information is advisory context only. The conflict resolver prevents
this signal from overriding agronomic safety rules.
"""
from __future__ import annotations
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
) -> MarketResult:
    weights = weights or {"trend": 0.5, "volatility": 0.3, "arrival": 0.2}
    price_history = price_history or []

    # If caller provided no price data, attempt live fetch from Agmarknet adapter
    if current_price <= 0 and not price_history and crop:
        market_data = fetch_prices(crop=crop, market=market)
        if market_data and isinstance(market_data, dict):
            current_price = float(market_data.get("current_price", current_price))
            price_history = [float(x) for x in market_data.get("price_history", price_history)]

    prices = [float(x) for x in price_history if float(x) >= 0]

    # If market data is still absent, report unavailable safely without fabricating prices
    if current_price <= 0 and not prices:
        return MarketResult(
            price_change_pct=0.0,
            moving_average=0.0,
            market_score=0.5,
            signal="hold",
            confidence=0.0,
            is_available=False,
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
    confidence = 0.85 if len(prices) >= 3 else 0.70

    return MarketResult(
        price_change_pct=pct_change,
        moving_average=ma,
        market_score=score,
        signal=signal,
        confidence=confidence,
        is_available=True,
    )
