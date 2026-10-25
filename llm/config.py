"""Configuration loader for AgriMind LLM explanation layer.

Loads and validates settings for multi-provider explanation chain:
OpenAI -> xAI Grok -> Deterministic Template Fallback.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


def _parse_bool(val: Any, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("1", "true", "yes", "on", "y")


def _parse_float(val: Any, default: float) -> float:
    try:
        return float(val) if val is not None and str(val).strip() else default
    except (ValueError, TypeError):
        return default


def _parse_int(val: Any, default: int) -> int:
    try:
        return int(val) if val is not None and str(val).strip() else default
    except (ValueError, TypeError):
        return default


@dataclass
class LLMConfig:
    primary_provider: str = "openai"
    fallback_provider: str = "grok"
    template_fallback: bool = True
    max_retries: int = 1
    timeout_seconds: float = 30.0

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    openai_base_url: str | None = None

    xai_api_key: str | None = None
    xai_model: str | None = None
    xai_base_url: str = "https://api.x.ai/v1"
    xai_timeout_seconds: float = 30.0


def get_llm_config() -> LLMConfig:
    """Read LLM configuration dynamically from the environment."""
    timeout = _parse_float(os.getenv("LLM_TIMEOUT_SECONDS"), default=30.0)
    openai_timeout = _parse_float(
        os.getenv("OPENAI_TIMEOUT_SECONDS"),
        default=timeout,
    )
    xai_timeout = _parse_float(
        os.getenv("XAI_TIMEOUT_SECONDS"),
        default=timeout,
    )

    primary = os.getenv("LLM_PRIMARY_PROVIDER", "openai").strip().lower()
    fallback = os.getenv("LLM_FALLBACK_PROVIDER", "grok").strip().lower()
    template_fb = _parse_bool(os.getenv("LLM_TEMPLATE_FALLBACK"), default=True)
    max_retries = _parse_int(os.getenv("LLM_MAX_RETRIES"), default=1)

    openai_key = os.getenv("OPENAI_API_KEY")
    openai_key = openai_key.strip() if openai_key else None
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None

    xai_key = os.getenv("XAI_API_KEY")
    xai_key = xai_key.strip() if xai_key else None
    # Read model name from configuration without inventing unverified identifier
    xai_model_raw = os.getenv("XAI_MODEL")
    xai_model = xai_model_raw.strip() if xai_model_raw else None
    xai_base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip() or "https://api.x.ai/v1"

    return LLMConfig(
        primary_provider=primary,
        fallback_provider=fallback,
        template_fallback=template_fb,
        max_retries=max_retries,
        timeout_seconds=timeout,
        openai_api_key=openai_key,
        openai_model=openai_model,
        openai_timeout_seconds=openai_timeout,
        openai_base_url=openai_base_url,
        xai_api_key=xai_key,
        xai_model=xai_model,
        xai_base_url=xai_base_url,
        xai_timeout_seconds=xai_timeout,
    )
