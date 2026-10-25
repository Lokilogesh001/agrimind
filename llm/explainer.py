"""Observable, source-grounded multi-provider explanation layer for AgriMind.

AUTHORITATIVE ARCHITECTURE:
Farm Input -> Specialist Agents -> Deterministic Decision Engine ->
Agronomic Safety Guard -> Authoritative Final Decision ->
LLM Explanation Layer (OpenAI -> xAI Grok -> Deterministic Template) -> Farmer-Facing Output

The deterministic policy remains authoritative. The LLM serves strictly as an
explanation and evidence-synthesis layer. It CANNOT alter or override:
- Final recommendation
- Agronomic safety constraints
- Disease-treatment gate & precedence
- Fertilizer approval or dosage constraints
- Weather veto (DELAY)
- Market-vs-agronomy conflict resolution

PROVIDER CHAIN:
1. Primary Provider: OpenAI (gpt-4o-mini / configured model)
2. Fallback Provider: xAI Grok (via https://api.x.ai/v1 with configured XAI_MODEL)
3. Deterministic Template Fallback: Guaranteed rule-based fallback if all providers fail or are unconfigured.

Every invocation is recorded in the agent_logs observability table.
API keys and sensitive request credentials are NEVER logged or stored.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Any

from llm.config import LLMConfig, get_llm_config
from observability import database as obs

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
    structured_explanation: dict[str, Any] | None = None
    cache_hit: bool = False
    tokens: dict | None = None
    evidence_sources_count: int = 0
    error: str | None = None
    api_attempt_latency_ms: float = 0.0
    fallback_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    failure_category: str | None = None

    @property
    def explanation(self) -> str:
        return self.text

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sanitize_log_text(text: str | None) -> str | None:
    """Mask potential API keys or Bearer tokens in logs and error strings."""
    if not text:
        return text
    sanitized = str(text)
    sanitized = re.sub(r'sk-[a-zA-Z0-9_\-]{20,}', 'sk-***[REDACTED]***', sanitized)
    sanitized = re.sub(r'xai-[a-zA-Z0-9_\-]{20,}', 'xai-***[REDACTED]***', sanitized)
    sanitized = re.sub(r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}', 'Bearer ***[REDACTED]***', sanitized, flags=re.IGNORECASE)
    for env_var in ("OPENAI_API_KEY", "XAI_API_KEY"):
        val = os.getenv(env_var)
        if val and len(val) > 8:
            sanitized = sanitized.replace(val, f"***[REDACTED_{env_var}]***")
    return sanitized


def deterministic_structured_explanation(state, evidence=None) -> dict[str, Any]:
    """Generate structured fallback explanation grounded in deterministic state."""
    rec_raw = getattr(state, "final_recommendation", None) or getattr(state, "recommendation", None) or "monitor"
    rec = rec_raw.replace("_", " ")
    norm_rec = str(rec).lower()

    # Weather findings
    w_risk = getattr(state.weather, "rainfall_risk", 0.0)
    from agents.weather_agent import get_weather_risk_explanation, get_weather_risk_level
    w_level = getattr(state.weather, "risk_level", None) or get_weather_risk_level(w_risk)
    w_exp = getattr(state.weather, "risk_explanation", None) or get_weather_risk_explanation(w_risk, w_level)

    # Soil findings
    npk_avail = getattr(state.soil, "npk_available", False)
    overall_def = getattr(state.soil, "overall_deficiency", None)
    priority_nut = getattr(state.soil, "priority_nutrient", None)

    # Disease findings
    dis_class = getattr(state.disease, "predicted_class", None)
    dis_conf = getattr(state.disease, "confidence", 0.0)
    dis_actionable = getattr(state.disease, "actionable", False)
    dis_mismatch = getattr(state.disease, "crop_mismatch", False)

    # Market findings
    m_sig = getattr(state.market, "signal", "hold")

    # Synthesize why_this_decision & immediate_guidance
    if "delay" in norm_rec:
        why = f"High rainfall risk ({w_risk:.2f}, {w_level}) triggers a safety veto. {w_exp}"
        immediate = "Postpone all foliar spraying, chemical fertilizer application, and machine field operations."
        cautions = [
            "Applying chemicals before heavy precipitation leads to wash-off, nutrient leaching, and environmental contamination.",
            "Excessive soil moisture impedes field equipment access and risks root suffocation.",
        ]
        triggers = ["Cease delay when rainfall probability drops below safety thresholds and surface water drains."]
    elif "disease" in norm_rec:
        why = f"Active disease signal ({dis_class or 'foliar pathogen'}) at {round(dis_conf * 100)}% confidence requires phytosanitary intervention before nutritional corrective measures."
        immediate = "Scout crop foliage, isolate symptomatic areas, and apply verified phytosanitary management."
        cautions = [
            "Disease management strictly takes precedence over fertilizer replenishment to avoid pathogen proliferation.",
            "Exact chemical treatments require confirmation with local agronomic extension guidelines.",
        ]
        triggers = ["Re-evaluate once disease symptoms are contained and secondary spread is halted."]
    elif "fertilizer" in norm_rec:
        def_str = f"{overall_def:.2f}" if overall_def is not None else "unspecified"
        why = f"Verified soil deficiency ({def_str}) identified with {priority_nut or 'balanced nutrients'} as priority."
        immediate = "Apply scheduled fertilizer replenishment adhering to basal or top-dressing guidelines for current crop stage."
        cautions = [
            "Exact application rate requires verification against the applicable agronomic recommendation for the crop, soil and field conditions.",
            "Avoid over-application to protect groundwater and soil microbial balance.",
        ]
        triggers = ["Conduct follow-up leaf tissue or soil testing after scheduled vegetative stage."]
    else:
        why = "Routine crop monitoring. Specialist agents confirm conditions remain within normal seasonal parameters."
        immediate = "Continue regular crop management, irrigation scheduling, and weekly pest scouting."
        cautions = [
            "Exact chemical applications require verified soil testing or confirmed pest presence before intervention."
        ]
        triggers = ["Re-evaluate upon sudden weather shifts or emergence of foliar discoloration."]

    # Context items
    context = []
    if npk_avail and overall_def is not None:
        context.append(f"Soil nutrient assessment: Deficiency score {overall_def:.2f}, prioritizing {priority_nut or 'balanced'}.")
    else:
        context.append("Soil nutrient assessment: Unmeasured. Field-measured NPK data was not provided.")
    context.append(f"Weather condition: {w_level} rainfall risk ({w_risk:.2f}). {w_exp}")
    if m_sig == "sell":
        context.append("Market signal indicates favorable selling window, but current crop growth stage maintains field agronomy as primary.")

    # Evidence used
    ev_used = []
    if evidence:
        for doc in evidence[:3]:
            title = doc.get("title") or doc.get("source") or doc.get("category") or "ICAR agronomic guidance"
            ev_used.append(str(title))
    if not ev_used:
        ev_used.append("AgriMind deterministic rule template")

    # Uncertainty
    uncertainty_notes = []
    if not npk_avail:
        uncertainty_notes.append("Soil NPK measurements unverified; exact dosage requires lab testing.")
    if dis_class and not dis_actionable:
        uncertainty_notes.append("Disease confidence below 0.60 safety threshold; visual field verification needed.")
    if not uncertainty_notes:
        uncertainty_notes.append("Advisory calibrated from regional weather telemetry and verified crop stage baselines.")

    summary_text = (
        f"Recommendation: {rec}. {w_exp} "
        + (f"Disease detected: {dis_class} ({round(dis_conf * 100)}%). " if dis_class else "")
        + (f"Soil deficiency: {overall_def:.2f}. " if npk_avail and overall_def is not None else "")
        + f"Safety guard verified: {immediate}"
    )

    return {
        "summary": summary_text.strip(),
        "why_this_decision": why,
        "immediate_guidance": immediate,
        "additional_agronomic_context": context,
        "important_cautions": cautions,
        "what_could_change_decision": triggers,
        "evidence_used": ev_used,
        "uncertainty": " ".join(uncertainty_notes),
        "llm_role": "explanation_only",
    }


def deterministic_explanation(state, evidence=None) -> str:
    """Backward-compatible text explanation."""
    parts = [f"Recommendation: {state.final_recommendation.replace('_', ' ')}."]
    from agents.weather_agent import get_weather_risk_explanation, get_weather_risk_level
    w_risk = getattr(state.weather, "rainfall_risk", 0.0)
    w_level = getattr(state.weather, "risk_level", None) or get_weather_risk_level(w_risk)
    w_exp = getattr(state.weather, "risk_explanation", None) or get_weather_risk_explanation(w_risk, w_level)
    parts.append(f"Rainfall risk: {w_risk:.2f} ({w_level}). {w_exp}".strip())
    if getattr(state.soil, "npk_available", False) and state.soil.overall_deficiency is not None:
        parts.append(
            f"Overall soil deficiency is {state.soil.overall_deficiency:.2f}, "
            f"with {state.soil.priority_nutrient or 'balanced'} as the priority nutrient."
        )
    else:
        parts.append(
            "Soil nutrient assessment: Unavailable. NPK measurements were not provided, "
            "so nutrient deficiency was not calculated."
        )
    if state.disease.predicted_class:
        dis_conf_pct = round(state.disease.confidence * 100)
        parts.append(
            f"Disease signal: {state.disease.predicted_class} at {dis_conf_pct}% confidence."
        )
        if getattr(state.disease, "crop_mismatch", False):
            selected_c = (getattr(getattr(state, "crop", None), "crop", "") or "selected crop").capitalize()
            detected_c = (getattr(state.disease, "crop_detected", "") or "Tomato").capitalize()
            parts.append(
                f"Disease confidence: {dis_conf_pct}%. Confidence gate: PASSED. Crop match: FAILED. "
                f"Disease action: BLOCKED. Reason: Predicted crop is {detected_c} but selected crop is {selected_c}."
            )
        elif not state.disease.actionable:
            parts.append(
                f"Disease confidence: {dis_conf_pct}%. Confidence gate: FAILED. Crop match: PASSED. "
                f"Disease action: BLOCKED. Reason: The disease signal is below the 0.60 confidence gate."
            )
    m_sig = getattr(state.market, "signal", "hold")
    if m_sig == "sell":
        parts.append(
            f"Market signal indicates favorable selling window ('sell'), but agronomic decision "
            f"({state.final_recommendation.replace('_', ' ')}) remains authoritative."
        )
    else:
        parts.append(f"Market signal: {m_sig}.")
    if evidence:
        parts.append(f"{len(evidence)} source-grounded agronomy record(s) were retrieved for context.")
    return " ".join(parts)


def _messages(state, evidence) -> list[dict[str, str]]:
    system = (
        "You are the explanation and evidence synthesis layer of AgriMind, an observable agricultural "
        "decision-support system. The deterministic Agronomic Safety Engine has ALREADY made the authoritative "
        "final decision. You MUST preserve that exact decision.\n\n"
        "STRICT AUTHORITATIVE RULES:\n"
        "1. You are an EXPLANATION-ONLY layer. You CANNOT change, override, or alter:\n"
        "   - The final recommendation\n"
        "   - Safety constraints\n"
        "   - Disease treatment precedence (disease ALWAYS precedes fertilizer)\n"
        "   - Weather veto (DELAY is non-negotiable)\n"
        "   - Market-vs-agronomy resolution (agronomic stage always overrides market signal)\n"
        "2. ZERO FABRICATION:\n"
        "   - Do NOT invent specific chemical dosages (e.g., kg/ha or ml/L) for fertilizers or pesticides "
        "unless explicitly present in the provided evidence. If absent, state: 'Exact application rate requires "
        "verification against the applicable agronomic recommendation for the crop, soil and field conditions.'\n"
        "   - Do NOT invent commercial product names, pesticide registrations, market prices, store names, MRPs, or citations.\n"
        "   - If evidence is unavailable, state: 'Not available from the provided evidence.' or 'Additional evidence-grounded context is unavailable.'\n"
        "3. EVIDENCE GROUNDING:\n"
        "   - Clearly distinguish PRIMARY RETRIEVED EVIDENCE (from ICAR/scientific documents) from ADDITIONAL AGRONOMIC INSIGHT.\n"
        "   - Ground all insights in the retrieved documents or sound agronomic biology for the specified crop and stage.\n"
        "4. SPECIFIC SCENARIO INSTRUCTIONS:\n"
        "   - If recommendation is DISEASE MANAGEMENT FIRST: Explain why phytosanitary control must precede nutrition, "
        "how weather conditions affect pathogen spread, and necessary field scouting. Never recommend fertilizer or selling.\n"
        "   - If recommendation is DELAY: Explain why precipitation/weather conditions make application ineffective or hazardous "
        "(wash-off, runoff, root saturation).\n"
        "   - If recommendation is APPLY FERTILIZER: Explain why the deficient nutrient is critical at the current crop stage, "
        "optimal application timing, and precautions.\n"
        "   - If market signal is SELL but crop is vegetative: Clarify that the crop cannot be harvested early despite favorable prices, "
        "maintaining field management.\n\n"
        "OUTPUT FORMAT:\n"
        "You MUST respond with a valid JSON object matching this schema:\n"
        "{\n"
        '  "summary": "Concise 2-3 sentence farmer-friendly explanation of today\'s decision.",\n'
        '  "why_this_decision": "Clear explanation of the primary agronomic and safety reasons behind this decision.",\n'
        '  "immediate_guidance": "Clear, practical action the farmer should take immediately in the field.",\n'
        '  "additional_agronomic_context": ["Context 1", "Context 2"],\n'
        '  "important_cautions": ["Caution 1"],\n'
        '  "what_could_change_decision": ["Trigger 1"],\n'
        '  "evidence_used": ["Evidence 1"],\n'
        '  "uncertainty": "Uncertainty or verification note.",\n'
        '  "llm_role": "explanation_only"\n'
        "}"
    )
    payload = {
        "deterministic_recommendation_locked": getattr(state, "final_recommendation", "monitor"),
        "decision_trace": getattr(state, "execution_trace", []),
        "safety_constraints": getattr(state, "safety_constraints", []),
        "crop": getattr(state, "crop", None).__dict__ if getattr(state, "crop", None) else {},
        "weather": getattr(state, "weather", None).__dict__ if getattr(state, "weather", None) else {},
        "soil": getattr(state, "soil", None).__dict__ if getattr(state, "soil", None) else {},
        "disease": getattr(state, "disease", None).__dict__ if getattr(state, "disease", None) else {},
        "market": getattr(state, "market", None).__dict__ if getattr(state, "market", None) else {},
        "conflicts": getattr(state, "conflicts", []),
        "retrieved_evidence": evidence or [],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, default=str)},
    ]


def _parse_json_payload(raw_content: str) -> dict[str, Any]:
    """Parse JSON payload handling markdown fencing if present."""
    text = (raw_content or "{}").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _call_chat_completion(
    api_key: str,
    base_url: str | None,
    model: str,
    messages: list[dict[str, str]],
    timeout: float = 30.0,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Execute chat completion request against an OpenAI-compatible API endpoint."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except Exception as exc:
        if "response_format" in str(exc).lower():
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
            )
        else:
            raise

    raw_content = response.choices[0].message.content or "{}"
    data = _parse_json_payload(raw_content)
    tokens = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
        "completion_tokens": getattr(response.usage, "completion_tokens", None),
        "total_tokens": getattr(response.usage, "total_tokens", None),
    } if response.usage else None
    return data, tokens


def _call_openai(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Execute request against OpenAI API."""
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT_SECONDS", "30")))
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    return _call_chat_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
        timeout=timeout,
    )


def _call_grok(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Execute request against xAI Grok API via https://api.x.ai/v1."""
    timeout = float(os.getenv("XAI_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT_SECONDS", "30")))
    base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip() or "https://api.x.ai/v1"
    return _call_chat_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
        timeout=timeout,
    )


def _validate_and_sanitize(data: dict[str, Any], state, evidence) -> dict[str, Any]:
    """Validate LLM response structure and enforce immutability of decision."""
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")

    summary = str(data.get("summary") or "").strip()
    why = str(data.get("why_this_decision") or "").strip()
    guidance = str(data.get("immediate_guidance") or "").strip()

    if not summary or not why:
        raise ValueError("LLM response missing summary or why_this_decision")

    context = data.get("additional_agronomic_context")
    if not isinstance(context, list):
        context = [str(context)] if context else []
    context = [str(c) for c in context if c]

    cautions = data.get("important_cautions")
    if not isinstance(cautions, list):
        cautions = [str(cautions)] if cautions else []
    cautions = [str(c) for c in cautions if c]

    triggers = data.get("what_could_change_decision")
    if not isinstance(triggers, list):
        triggers = [str(triggers)] if triggers else []
    triggers = [str(t) for t in triggers if t]

    evidence_used = data.get("evidence_used")
    if not isinstance(evidence_used, list):
        evidence_used = [str(evidence_used)] if evidence_used else []
    evidence_used = [str(e) for e in evidence_used if e]

    uncertainty = str(data.get("uncertainty") or "Field agronomic verification recommended.").strip()

    return {
        "summary": summary,
        "why_this_decision": why,
        "immediate_guidance": guidance or "Follow standard field protocol.",
        "additional_agronomic_context": context,
        "important_cautions": cautions,
        "what_could_change_decision": triggers,
        "evidence_used": evidence_used,
        "uncertainty": uncertainty,
        "llm_role": "explanation_only",
    }


def _cache_key(state, evidence) -> str:
    config = get_llm_config()
    payload = {
        "recommendation": getattr(state, "final_recommendation", ""),
        "trace": getattr(state, "execution_trace", []),
        "weather": getattr(getattr(state, "weather", None), "__dict__", {}),
        "soil": getattr(getattr(state, "soil", None), "__dict__", {}),
        "disease": getattr(getattr(state, "disease", None), "__dict__", {}),
        "advisory": getattr(getattr(state, "advisory", None), "__dict__", {}),
        "market": getattr(getattr(state, "market", None), "__dict__", {}),
        "crop": getattr(getattr(state, "crop", None), "__dict__", {}),
        "evidence": evidence or [],
        "primary_provider": config.primary_provider,
        "fallback_provider": config.fallback_provider,
        "openai_model": config.openai_model,
        "xai_model": config.xai_model,
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
        {"provider": result.provider, "model": result.model},
        {
            "provider": result.provider,
            "model": result.model,
            "role": "Explanation and evidence synthesis only",
            "decision_authority": "Deterministic Agronomic Safety Engine",
            "status": result.status,
            "fallback_used": result.fallback_used,
            "cache_hit": result.cache_hit,
            "tokens": result.tokens,
            "latency_ms": result.latency_ms,
            "evidence_sources_count": result.evidence_sources_count,
            "output_summary": _sanitize_log_text(result.text[:200]) if result.text else "",
            "error": _sanitize_log_text(error or result.error),
        },
        status,
        1.0 if result.status == "success" else 0.0,
        result.latency_ms,
    )


def _categorize_error(exc: Exception) -> str:
    """Categorize an exception for observability telemetry."""
    exc_str = f"{type(exc).__name__} {exc}".lower()
    if isinstance(exc, TimeoutError) or "timeout" in exc_str or "timed out" in exc_str:
        return "TIMEOUT"
    if any(k in exc_str for k in ("401", "auth", "unauthorized", "api_key", "forbidden", "403")):
        return "AUTHENTICATION_ERROR"
    if any(k in exc_str for k in ("429", "rate", "quota")):
        return "RATE_LIMITED"
    if any(k in exc_str for k in ("connection", "connect", "dns", "network")):
        return "NETWORK_ERROR"
    if any(k in exc_str for k in ("json", "validation", "missing summary")):
        return "MALFORMED_OUTPUT"
    return "API_ERROR"


def _is_retryable_error(exc: Exception) -> bool:
    """Determine whether an error is transient and eligible for bounded retry."""
    cat = _categorize_error(exc)
    # Auth errors and unconfigured identifiers should never be retried
    if cat == "AUTHENTICATION_ERROR":
        return False
    if "not configured" in str(exc).lower():
        return False
    return True


def explain_with_metadata(state, evidence=None) -> LLMExplanationResult:
    """Generate source-grounded explanation through provider chain (OpenAI -> Grok -> Template)."""
    evidence = evidence or []
    cache_key = _cache_key(state, evidence)
    cached = _cache_get(cache_key)
    if cached:
        _log(state.run_id, cached)
        return cached

    config = get_llm_config()
    messages = _messages(state, evidence)

    # Build sequence of active providers to attempt
    chain: list[str] = []
    if config.primary_provider and config.primary_provider != "none":
        chain.append(config.primary_provider)
    if config.fallback_provider and config.fallback_provider != "none" and config.fallback_provider not in chain:
        chain.append(config.fallback_provider)

    chain_start = time.perf_counter()
    accumulated_api_latency = 0.0
    last_failure_category: str | None = None
    last_error_msg: str | None = None
    attempted_providers = 0

    for provider in chain:
        if provider == "openai":
            key = config.openai_api_key
            model = config.openai_model
            timeout = config.openai_timeout_seconds

            if not key:
                last_failure_category = last_failure_category or "KEY_NOT_CONFIGURED"
                last_error_msg = last_error_msg or "OPENAI_API_KEY omitted in environment; engaged fallback"
                continue

            attempted_providers += 1
            max_attempts = max(1, 1 + config.max_retries)
            for attempt in range(max_attempts):
                call_start = time.perf_counter()
                try:
                    data, tokens = _call_openai(key, model, messages)
                    structured = _validate_and_sanitize(data, state, evidence)
                    attempt_latency = round((time.perf_counter() - call_start) * 1000, 2)
                    total_latency = round((time.perf_counter() - chain_start) * 1000, 2)
                    accumulated_api_latency += attempt_latency

                    is_fallback = (provider != config.primary_provider)
                    result = LLMExplanationResult(
                        text=structured["summary"],
                        provider="openai",
                        model=model,
                        status="success",
                        latency_ms=total_latency,
                        fallback_used=is_fallback,
                        structured_explanation=structured,
                        tokens=tokens,
                        evidence_sources_count=len(evidence),
                        api_attempt_latency_ms=accumulated_api_latency,
                        fallback_latency_ms=0.0,
                        total_latency_ms=total_latency,
                        failure_category=None,
                    )
                    _cache_put(cache_key, result)
                    _log(state.run_id, result)
                    return result
                except Exception as exc:
                    attempt_latency = round((time.perf_counter() - call_start) * 1000, 2)
                    accumulated_api_latency += attempt_latency
                    cat = _categorize_error(exc)
                    last_failure_category = cat
                    clean_err = _sanitize_log_text(f"OpenAI error [{cat}]: {type(exc).__name__}: {exc}")
                    last_error_msg = clean_err

                    if not _is_retryable_error(exc) or attempt >= max_attempts - 1:
                        break
                    time.sleep(0.05)

        elif provider == "grok":
            key = config.xai_api_key
            model = config.xai_model
            timeout = config.xai_timeout_seconds

            if not key:
                last_failure_category = last_failure_category or "KEY_NOT_CONFIGURED"
                last_error_msg = last_error_msg or "XAI_API_KEY omitted in environment; engaged fallback"
                continue

            if not model:
                last_failure_category = "MODEL_NOT_CONFIGURED"
                last_error_msg = "XAI_MODEL omitted in environment; engaged fallback"
                continue

            attempted_providers += 1
            max_attempts = max(1, 1 + config.max_retries)
            for attempt in range(max_attempts):
                call_start = time.perf_counter()
                try:
                    data, tokens = _call_grok(key, model, messages)
                    structured = _validate_and_sanitize(data, state, evidence)
                    attempt_latency = round((time.perf_counter() - call_start) * 1000, 2)
                    total_latency = round((time.perf_counter() - chain_start) * 1000, 2)
                    accumulated_api_latency += attempt_latency

                    is_fallback = (provider != config.primary_provider)
                    result = LLMExplanationResult(
                        text=structured["summary"],
                        provider="grok",
                        model=model,
                        status="success",
                        latency_ms=total_latency,
                        fallback_used=is_fallback,
                        structured_explanation=structured,
                        tokens=tokens,
                        evidence_sources_count=len(evidence),
                        api_attempt_latency_ms=accumulated_api_latency,
                        fallback_latency_ms=0.0,
                        total_latency_ms=total_latency,
                        failure_category=None,
                    )
                    _cache_put(cache_key, result)
                    _log(state.run_id, result)
                    return result
                except Exception as exc:
                    attempt_latency = round((time.perf_counter() - call_start) * 1000, 2)
                    accumulated_api_latency += attempt_latency
                    cat = _categorize_error(exc)
                    last_failure_category = cat
                    clean_err = _sanitize_log_text(f"xAI Grok error [{cat}]: {type(exc).__name__}: {exc}")
                    last_error_msg = clean_err

                    if not _is_retryable_error(exc) or attempt >= max_attempts - 1:
                        break
                    time.sleep(0.05)

    # --------------------------------------------------------------------------
    # Deterministic Template Fallback
    # --------------------------------------------------------------------------
    if config.template_fallback:
        fb_start = time.perf_counter()
        structured = deterministic_structured_explanation(state, evidence)
        fb_latency = round((time.perf_counter() - fb_start) * 1000, 2)

        # If no external provider was attempted (e.g. no keys configured in env)
        if attempted_providers == 0:
            result = LLMExplanationResult(
                text=structured["summary"],
                provider="deterministic",
                model="rule-based-template",
                status="deterministic",
                latency_ms=0.0,
                fallback_used=False,
                structured_explanation=structured,
                evidence_sources_count=len(evidence),
                api_attempt_latency_ms=0.0,
                fallback_latency_ms=fb_latency,
                total_latency_ms=fb_latency,
                failure_category=last_failure_category or "KEY_NOT_CONFIGURED",
                error=last_error_msg if last_failure_category and last_failure_category != "KEY_NOT_CONFIGURED" else None,
            )
            _log(state.run_id, result)
            return result

        # An external provider was configured and attempted, but failed
        total_latency = round(accumulated_api_latency + fb_latency, 2)
        result = LLMExplanationResult(
            text=structured["summary"],
            provider="deterministic",
            model="rule-based-template",
            status="fallback",
            latency_ms=total_latency,
            fallback_used=True,
            structured_explanation=structured,
            evidence_sources_count=len(evidence),
            api_attempt_latency_ms=accumulated_api_latency,
            fallback_latency_ms=fb_latency,
            total_latency_ms=total_latency,
            failure_category=last_failure_category or "API_ERROR",
            error=last_error_msg,
        )
        _log(state.run_id, result, error=last_error_msg)
        return result

    # If template fallback is explicitly disabled and all providers failed
    raise RuntimeError(f"All LLM providers failed and LLM_TEMPLATE_FALLBACK is false. Last error: {last_error_msg}")


def explain(state, evidence=None) -> str:
    """Backward-compatible text-only interface."""
    return explain_with_metadata(state, evidence).text
