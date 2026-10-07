from types import SimpleNamespace
from unittest.mock import MagicMock

from llm import explainer


def make_state(recommendation="DELAY"):
    return SimpleNamespace(
        run_id="test-run",
        final_recommendation=recommendation,
        execution_trace=[f"orchestrator -> {recommendation}"],
        weather=SimpleNamespace(rainfall_risk=0.92, temperature_risk=0.1, risk_level="HIGH", risk_explanation="Heavy rain expected."),
        soil=SimpleNamespace(npk_available=True, overall_deficiency=0.2, priority_nutrient="nitrogen"),
        disease=SimpleNamespace(predicted_class="Tomato___healthy", confidence=0.95, actionable=True, crop_mismatch=False),
        advisory=SimpleNamespace(scores={"delay": 0.7}),
        market=SimpleNamespace(signal="hold", market_score=0.2),
        crop=SimpleNamespace(crop="Tomato", growth_stage="vegetative"),
        safety_constraints=["Weather Safety: Delay field operations during rainfall risk."],
        conflicts=[],
    )


def test_openai_success_is_observable(monkeypatch):
    """Test that a successful OpenAI response is correctly observed, parsed, and logged."""
    state = make_state()
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    explainer._CACHE.clear()

    calls = []
    monkeypatch.setattr(explainer.obs, "log_agent_call", lambda *args, **kwargs: calls.append(args))

    mock_json = {
        "summary": "Postpone chemical application due to high precipitation risk.",
        "why_this_decision": "Heavy rainfall causes pesticide wash-off and environmental leaching.",
        "immediate_guidance": "Suspend all spraying and wait for soil to drain.",
        "additional_agronomic_context": ["Moisture increases fungal risk but immediate wash-off prevents effective uptake."],
        "important_cautions": ["Do not apply foliar sprays before rain."],
        "what_could_change_decision": ["Rainfall probability dropping below 30%."],
        "evidence_used": ["ICAR Weather Advisory Guidelines"],
        "uncertainty": "Calibrated against regional short-range precipitation forecast.",
        "llm_role": "explanation_only",
    }
    mock_tokens = {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200}
    monkeypatch.setattr(explainer, "_call_openai", lambda key, model, messages: (mock_json, mock_tokens))

    result = explainer.explain_with_metadata(state, [{"title": "ICAR rain guidance"}])

    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.status == "success"
    assert result.fallback_used is False
    assert "Postpone" in result.text
    assert result.structured_explanation is not None
    assert result.structured_explanation["why_this_decision"] == mock_json["why_this_decision"]
    assert result.structured_explanation["llm_role"] == "explanation_only"
    assert result.tokens == mock_tokens
    assert calls[-1][1] == "llm_explainer"
    assert calls[-1][3]["provider"] == "openai"
    assert calls[-1][3]["model"] == "gpt-4o-mini"
    assert calls[-1][3]["status"] == "success"


def test_openai_failure_falls_back_and_is_observable(monkeypatch):
    """Test that an OpenAI API error triggers a clean deterministic fallback without crashing."""
    state = make_state()
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    explainer._CACHE.clear()

    calls = []
    monkeypatch.setattr(explainer.obs, "log_agent_call", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("OpenAI API rate limit exceeded")))

    result = explainer.explain_with_metadata(state)

    assert result.provider == "deterministic"
    assert result.model == "rule-based-template"
    assert result.status == "fallback"
    assert result.fallback_used is True
    assert "Recommendation: DELAY." in result.text
    assert "OpenAI API rate limit exceeded" in (result.error or "")
    assert result.structured_explanation is not None
    assert "Postpone" in result.structured_explanation["immediate_guidance"]
    assert calls[-1][3]["status"] == "fallback"
    assert calls[-1][3]["provider"] == "deterministic"


def test_no_key_uses_deterministic_fallback(monkeypatch):
    """Test that missing OPENAI_API_KEY immediately uses deterministic template with zero latency."""
    state = make_state()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    explainer._CACHE.clear()

    calls = []
    monkeypatch.setattr(explainer.obs, "log_agent_call", lambda *args, **kwargs: calls.append(args))

    result = explainer.explain_with_metadata(state)

    assert result.provider == "deterministic"
    assert result.model == "rule-based-template"
    assert result.status == "deterministic"
    assert result.fallback_used is False
    assert result.error is None
    assert result.latency_ms == 0.0
    assert result.structured_explanation is not None
    assert calls[-1][3]["status"] == "deterministic"


def test_openai_conflicting_decision_ignored(monkeypatch):
    """Test that the deterministic engine decision remains authoritative even if LLM attempts conflict."""
    state = make_state(recommendation="DELAY")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    explainer._CACHE.clear()

    # Model attempts to suggest applying fertilizer despite DELAY
    rogue_output = {
        "summary": "Ignore rain and apply 50 kg urea immediately.",
        "why_this_decision": "Nitrogen deficiency is high.",
        "immediate_guidance": "Apply fertilizer now.",
        "additional_agronomic_context": [],
        "important_cautions": [],
        "what_could_change_decision": [],
        "evidence_used": [],
        "uncertainty": "None",
        "llm_role": "explanation_only",
    }
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (rogue_output, None))

    result = explainer.explain_with_metadata(state)

    # The deterministic recommendation on state CANNOT be overridden by LLM
    assert state.final_recommendation == "DELAY"
    assert result.structured_explanation["llm_role"] == "explanation_only"


def test_invalid_json_triggers_deterministic_fallback(monkeypatch):
    """Test that invalid/malformed response from OpenAI triggers deterministic fallback cleanly."""
    state = make_state()
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    explainer._CACHE.clear()

    # Returns incomplete schema missing mandatory fields
    broken_output = {"random_key": "unstructured text"}
    monkeypatch.setattr(explainer, "_call_openai", lambda *args, **kwargs: (broken_output, None))

    result = explainer.explain_with_metadata(state)

    assert result.provider == "deterministic"
    assert result.status == "fallback"
    assert result.fallback_used is True
    assert "Recommendation: DELAY." in result.text


def test_no_old_providers_in_explainer():
    """Verify that old multi-provider chains (xAI, Groq, Gemini) have been completely removed."""
    assert not hasattr(explainer, "DEFAULT_PROVIDER_ORDER")
    assert not hasattr(explainer, "_gemini")
    assert not hasattr(explainer, "_provider_order")
