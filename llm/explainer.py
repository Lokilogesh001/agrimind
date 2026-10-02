"""Observable, source-grounded LLM explanation layer for AgriMind.

The deterministic policy remains authoritative. This module may only explain
an already-selected recommendation using the structured agent outputs and
retrieved evidence. It supports a provider chain (xAI/Grok -> Groq -> Gemini)
with deterministic fallback, bounded retries, and a small process-local cache.
Every attempt is written to the existing ``agent_logs`` observability table.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

import requests

from observability import database as obs


DEFAULT_PROVIDER_ORDER = ("xai", "groq", "gemini")
_CACHE: dict[str, tuple[float, "LLMExplanationResult"]] = {}
_CACHE_TTL_SECONDS = 300.0
_CACHE_MAX_ITEMS = 128


@dataclass
class LLMExplanationResult:
    text: str
    provider: str
    model: str
    status: str
    latency_ms: float
    fallback_used: bool
    cache_hit: bool = False
    tokens: dict | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def deterministic_explanation(state, evidence=None) -> str:
    parts = [f"Recommendation: {state.final_recommendation.replace('_', ' ')}."]
    parts.append(f"Rainfall risk is {state.weather.rainfall_risk:.2f}.")
    parts.append(
        f"Overall soil deficiency is {state.soil.overall_deficiency:.2f}, "
        f"with {state.soil.priority_nutrient} as the priority nutrient."
    )
    if state.disease.predicted_class:
        parts.append(
            f"Disease signal: {state.disease.predicted_class} at "
            f"{state.disease.confidence:.2f} confidence."
        )
        if not state.disease.actionable:
            parts.append(
                "The disease signal is below the 0.60 confidence gate, so it "
                "is not used as an actionable disease decision."
            )
    parts.append(f"Market signal: {state.market.signal}.")
    if evidence:
        parts.append(f"{len(evidence)} source-grounded agronomy record(s) were retrieved for context.")
    return " ".join(parts)


def _provider_order() -> list[str]:
    raw = os.getenv("LLM_PROVIDER_ORDER", ",".join(DEFAULT_PROVIDER_ORDER))
    order = [x.strip().lower() for x in raw.split(",") if x.strip()]
    return [x for x in order if x in {"xai", "groq", "gemini"}] or list(DEFAULT_PROVIDER_ORDER)


def _model(provider: str) -> str:
    defaults = {
        "xai": "grok-4.6",
        "groq": "llama-3.3-70b-versatile",
        "gemini": "gemini-2.5-flash",
    }
    return os.getenv(f"{provider.upper()}_MODEL", defaults[provider])


def _key(provider: str) -> str | None:
    names = {"xai": "XAI_API_KEY", "groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}
    return os.getenv(names[provider]) or None


def _request_with_retry(method: str, url: str, **kwargs):
    retries = max(0, int(os.getenv("LLM_RETRIES", "2")))
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    kwargs["timeout"] = timeout
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.request(method, url, **kwargs)
            if response.status_code not in {429} and response.status_code < 500:
                if response.status_code >= 400:
                    detail = response.text[:1000].strip()
                    raise RuntimeError(
                        f"HTTP {response.status_code} from {url}: {detail or response.reason}"
                    )
                return response
            response.raise_for_status()
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                raise
            time.sleep(min(2.0 ** attempt, 4.0))
    if last_exc:
        raise last_exc
    raise RuntimeError("LLM request failed")


def _messages(state, evidence) -> list[dict[str, str]]:
    system = (
        "You are the explanation layer of AgriMind. The deterministic policy has "
        "already selected the recommendation. You MUST preserve that exact action. "
        "Never override safety rules, change the recommendation, invent fertilizer "
        "or pesticide doses, invent diagnoses, or claim evidence that is not supplied. "
        "Use the supplied ICAR evidence when relevant. Clearly mention uncertainty "
        "when a disease signal is below the 0.60 actionable threshold. Give a concise, "
        "farmer-friendly explanation in plain language."
    )
    payload = {
        "recommendation_locked": state.final_recommendation,
        "decision_reason": state.execution_trace[-1] if state.execution_trace else "",
        "weather": state.weather.__dict__,
        "soil": state.soil.__dict__,
        "disease": state.disease.__dict__,
        "advisory": state.advisory.__dict__,
        "market": state.market.__dict__,
        "crop": state.crop.__dict__,
        "evidence": evidence or [],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, default=str)},
    ]


class LLMContent(str):
    tokens: dict | None = None


def _openai_compatible(provider: str, key: str, model: str, messages: list[dict[str, str]]) -> str:
    base_urls = {
        "xai": "https://api.x.ai/v1/chat/completions",
        "groq": "https://api.groq.com/openai/v1/chat/completions",
    }
    response = _request_with_retry(
        "POST",
        base_urls[provider],
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages},
    )
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("LLM returned an empty explanation")
    result = LLMContent(text.strip())
    result.tokens = data.get("usage")
    return result


def _gemini(key: str, model: str, messages: list[dict[str, str]]) -> str:
    system_text = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_text = next((m["content"] for m in messages if m["role"] == "user"), "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = _request_with_retry(
        "POST",
        url,
        params={"key": key},
        headers={"Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {"temperature": 0.1},
        },
    )
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Gemini returned an empty explanation")
    result = LLMContent(text.strip())
    result.tokens = data.get("usageMetadata")
    return result


def _cache_key(state, evidence) -> str:
    payload = {
        "recommendation": state.final_recommendation,
        "trace": state.execution_trace,
        "weather": state.weather.__dict__,
        "soil": state.soil.__dict__,
        "disease": state.disease.__dict__,
        "advisory": state.advisory.__dict__,
        "market": state.market.__dict__,
        "crop": state.crop.__dict__,
        "evidence": evidence or [],
        "provider_order": _provider_order(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _cache_get(key: str) -> LLMExplanationResult | None:
    item = _CACHE.get(key)
    if not item:
        return None
    created, result = item
    if time.monotonic() - created > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return LLMExplanationResult(**{**result.to_dict(), "cache_hit": True})


def _cache_put(key: str, result: LLMExplanationResult) -> None:
    if len(_CACHE) >= _CACHE_MAX_ITEMS:
        oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
        _CACHE.pop(oldest, None)
    _CACHE[key] = (time.monotonic(), result)


def _log(run_id: str, result: LLMExplanationResult, error: str | None = None) -> None:
    status = "ok" if result.status == "success" else "degraded"
    obs.log_agent_call(
        run_id,
        "llm_explainer",
        {"provider_order": _provider_order()},
        {
            "provider": result.provider,
            "model": result.model,
            "status": result.status,
            "fallback_used": result.fallback_used,
            "cache_hit": result.cache_hit,
            "tokens": result.tokens,
            "error": error or result.error,
        },
        status,
        1.0 if result.status == "success" else 0.0,
        result.latency_ms,
    )


def explain_with_metadata(state, evidence=None) -> LLMExplanationResult:
    """Generate an explanation and persist one observable LLM-layer record."""
    evidence = evidence or []
    cache_key = _cache_key(state, evidence)
    cached = _cache_get(cache_key)
    if cached:
        _log(state.run_id, cached)
        return cached

    messages = _messages(state, evidence)
    errors: list[str] = []
    providers = _provider_order()
    attempted = False

    for index, provider in enumerate(providers):
        key = _key(provider)
        if not key:
            continue
        attempted = True
        model = _model(provider)
        start = time.perf_counter()
        try:
            if provider in {"xai", "groq"}:
                text = _openai_compatible(provider, key, model, messages)
            else:
                text = _gemini(key, model, messages)
            tokens = getattr(text, "tokens", None)
            result = LLMExplanationResult(
                text=str(text),
                provider=provider,
                model=model,
                status="success",
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
                fallback_used=index > 0,
                tokens=tokens,
            )
            _cache_put(cache_key, result)
            _log(state.run_id, result)
            return result
        except Exception as exc:
            errors.append(f"{provider}: {type(exc).__name__}: {exc}")

    text = deterministic_explanation(state, evidence)
    result = LLMExplanationResult(
        text=text,
        provider="deterministic",
        model="rule-based-template",
        status="fallback",
        latency_ms=0.0,
        fallback_used=attempted,
        error="; ".join(errors) if errors else "No LLM API key configured",
    )
    _log(state.run_id, result)
    return result


def explain(state, evidence=None) -> str:
    """Backward-compatible text-only interface used by existing callers/tests."""
    return explain_with_metadata(state, evidence).text
