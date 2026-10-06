from types import SimpleNamespace

from llm import explainer


def make_state():
    return SimpleNamespace(
        run_id="test-run",
        final_recommendation="DELAY",
        execution_trace=["orchestrator -> DELAY (rainfall_risk)"],
        weather=SimpleNamespace(rainfall_risk=0.92, temperature_risk=0.1),
        soil=SimpleNamespace(overall_deficiency=0.2, priority_nutrient="nitrogen"),
        disease=SimpleNamespace(predicted_class="Tomato___healthy", confidence=0.95, actionable=True),
        advisory=SimpleNamespace(scores={"delay": 0.7}),
        market=SimpleNamespace(signal="hold", market_score=0.2),
        crop=SimpleNamespace(crop="Tomato", growth_stage="vegetative"),
    )


def test_grok_success_is_observable(monkeypatch):
    state = make_state()
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "xai")
    explainer._CACHE.clear()
    calls = []
    monkeypatch.setattr(explainer.obs, "log_agent_call", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(explainer, "_openai_compatible", lambda provider, key, model, messages: "Delay because heavy rain is expected.")

    result = explainer.explain_with_metadata(state, [{"text": "ICAR rain guidance"}])

    assert result.provider == "xai"
    assert result.model == "grok-4.6"
    assert result.status == "success"
    assert result.fallback_used is False
    assert result.text.startswith("Delay")
    assert calls[-1][1] == "llm_explainer"
    assert calls[-1][3]["provider"] == "xai"


def test_llm_failure_falls_back_and_is_observable(monkeypatch):
    state = make_state()
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "xai")
    explainer._CACHE.clear()
    calls = []
    monkeypatch.setattr(explainer.obs, "log_agent_call", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(explainer, "_openai_compatible", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = explainer.explain_with_metadata(state)

    assert result.provider == "deterministic"
    assert result.status == "fallback"
    assert result.fallback_used is True
    assert "Recommendation: DELAY." in result.text
    assert "boom" in (result.error or "")
    assert calls[-1][3]["status"] == "fallback"


def test_no_key_uses_deterministic_fallback(monkeypatch):
    state = make_state()
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "xai,groq,gemini")
    explainer._CACHE.clear()
    monkeypatch.setattr(explainer.obs, "log_agent_call", lambda *args, **kwargs: None)

    result = explainer.explain_with_metadata(state)

    assert result.provider == "deterministic"
    assert result.status == "deterministic"
    assert result.fallback_used is False
    assert result.error is None


def test_openai_compatible_uses_current_xai_safe_payload(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        reason = "OK"
        text = '{"choices":[{"message":{"content":"Keep the recommendation unchanged."}}]}'

        def raise_for_status(self):
            raise AssertionError("raise_for_status should not be called for 200")

        def json(self):
            return {"choices": [{"message": {"content": "Keep the recommendation unchanged."}}]}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, kwargs=kwargs)
        return Response()

    monkeypatch.setattr(explainer.requests, "request", fake_request)
    monkeypatch.setenv("LLM_RETRIES", "0")
    result = explainer._openai_compatible(
        "xai", "test-key", "grok-4.6",
        [{"role": "user", "content": "hello"}],
    )

    assert result == "Keep the recommendation unchanged."
    assert captured["url"] == "https://api.x.ai/v1/chat/completions"
    assert captured["kwargs"]["json"] == {
        "model": "grok-4.6",
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_provider_http_error_keeps_safe_response_detail(monkeypatch):
    class Response:
        status_code = 400
        reason = "Bad Request"
        text = '{"error":{"message":"model is not available"}}'

        def raise_for_status(self):
            raise AssertionError("custom error path should be used")

    def fake_request(method, url, **kwargs):
        return Response()

    monkeypatch.setattr(explainer.requests, "request", fake_request)
    monkeypatch.setenv("LLM_RETRIES", "0")

    try:
        explainer._openai_compatible(
            "xai", "test-key", "grok-4.6",
            [{"role": "user", "content": "hello"}],
        )
    except RuntimeError as exc:
        assert "HTTP 400" in str(exc)
        assert "model is not available" in str(exc)
        assert "test-key" not in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
