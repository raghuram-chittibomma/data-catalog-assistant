"""Tests for OpenAI vs local Ollama LLM provider resolution."""

from unittest.mock import MagicMock, patch

from src.core.rag_engine import RAGEngine, resolve_llm_call_settings


def test_resolve_openai_defaults():
    settings = resolve_llm_call_settings(
        {"provider": "openai", "model": "gpt-4", "api_key": "sk-test", "timeout_seconds": 45}
    )
    assert settings["provider"] == "openai"
    assert settings["model"] == "gpt-4"
    assert settings["api_key"] == "sk-test"
    assert settings["base_url"] is None
    assert settings["timeout_seconds"] == 45.0


def test_resolve_ollama_from_local_config():
    settings = resolve_llm_call_settings(
        {
            "provider": "openai",
            "local": {
                "base_url": "http://192.168.4.52:11434/v1",
                "model": "qwen3:8b",
                "api_key": "ollama",
                "timeout_seconds": 300,
            },
        },
        provider="local",
    )
    assert settings["provider"] == "ollama"
    assert settings["model"] == "qwen3:8b"
    assert settings["base_url"] == "http://192.168.4.52:11434/v1"
    assert settings["timeout_seconds"] == 300.0


def test_resolve_ollama_appends_v1_when_missing():
    settings = resolve_llm_call_settings(
        {"local": {"base_url": "http://192.168.4.52:11434", "model": "qwen3:8b"}},
        provider="ollama",
    )
    assert settings["base_url"] == "http://192.168.4.52:11434/v1"


def test_per_request_model_override():
    settings = resolve_llm_call_settings(
        {"provider": "openai", "model": "gpt-4", "local": {"model": "qwen3:8b"}},
        provider="ollama",
        model="custom:tag",
    )
    assert settings["model"] == "custom:tag"


def test_unsupported_provider_raises():
    try:
        resolve_llm_call_settings({}, provider="anthropic")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "not supported" in str(e)


def test_generate_query_ollama_override_uses_fake_client():
    class CapturingLLM:
        def __init__(self):
            self.kwargs = None

        def create(self, model, messages, temperature=0.0, max_tokens=512):
            self.kwargs = {"model": model, "messages": messages}
            return {"choices": [{"message": {"content": "SELECT 1\nEXPLANATION: ok"}}]}

    llm = CapturingLLM()
    engine = RAGEngine(
        llm_client=llm,
        config={
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "local": {"model": "qwen3:8b", "base_url": "http://127.0.0.1:11434/v1"},
            }
        },
    )
    out = engine.generate_query("count orders", provider="ollama")
    assert out["query"].startswith("SELECT")
    assert out["provider"] == "ollama"
    assert out["model"] == "qwen3:8b"
    assert llm.kwargs["model"] == "qwen3:8b"


def test_invoke_llm_passes_base_url_for_ollama():
    engine = RAGEngine(config={"llm": {"provider": "openai"}})
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="SELECT 1"))]
    )
    fake_openai = MagicMock()
    fake_openai.OpenAI.return_value = fake_client

    with patch.dict("sys.modules", {"openai": fake_openai}):
        text = engine._invoke_llm(
            [{"role": "user", "content": "hi"}],
            model="qwen3:8b",
            temperature=0.0,
            max_tokens=64,
            api_key="ollama",
            base_url="http://192.168.4.52:11434/v1",
            timeout_seconds=300,
            provider="ollama",
        )

    assert text == "SELECT 1"
    fake_openai.OpenAI.assert_called_once()
    kwargs = fake_openai.OpenAI.call_args.kwargs
    assert kwargs["base_url"] == "http://192.168.4.52:11434/v1"
    assert kwargs["timeout"] == 300
