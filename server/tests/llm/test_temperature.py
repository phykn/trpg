"""LLMClient.chat / chat_stream propagates temperature to OpenAI SDK params when set."""

from unittest.mock import MagicMock

import pytest

from src.llm.client import LLMClient, LLMProfile, force_think


def _client(model: str = "test-model") -> LLMClient:
    profile = LLMProfile(
        base_url="http://localhost",
        model=model,
        api_keys=("k",),
        thinking_mode="off",
        supports_system=True,
    )
    return LLMClient(profiles={"default": profile})


def test_client_uses_env_timeouts(monkeypatch):
    captured: list[float] = []

    class _FakeOpenAI:
        def __init__(self, *, base_url, api_key, timeout):
            captured.append(timeout)

    monkeypatch.setenv("LLM_CHAT_TIMEOUT_S", "12.5")
    monkeypatch.setenv("LLM_STREAM_TIMEOUT_S", "45.5")
    monkeypatch.setattr("src.llm.client.AsyncOpenAI", _FakeOpenAI)

    _client()

    assert captured == [12.5, 45.5]


def test_client_explicit_timeouts_override_env(monkeypatch):
    captured: list[float] = []

    class _FakeOpenAI:
        def __init__(self, *, base_url, api_key, timeout):
            captured.append(timeout)

    monkeypatch.setenv("LLM_CHAT_TIMEOUT_S", "12.5")
    monkeypatch.setenv("LLM_STREAM_TIMEOUT_S", "45.5")
    monkeypatch.setattr("src.llm.client.AsyncOpenAI", _FakeOpenAI)

    profile = LLMProfile(
        base_url="http://localhost",
        model="test-model",
        api_keys=("k",),
        thinking_mode="off",
        supports_system=True,
    )
    LLMClient(
        profiles={"default": profile},
        chat_timeout_s=3.0,
        stream_timeout_s=4.0,
    )

    assert captured == [3.0, 4.0]


@pytest.mark.asyncio
async def test_chat_omits_temperature_when_none(monkeypatch):
    """When temperature is None (default), the param dict has no 'temperature' key.
    Preserves the model default for callers that don't opt in."""
    client = _client()
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok", model_extra=None))]
        )

    fake_inner = MagicMock()
    fake_inner.chat.completions.create = fake_create
    fake_provider = MagicMock()
    fake_provider.next_chat_client.return_value = fake_inner
    fake_provider.thinking_mode = "off"
    fake_provider.toggle_style = "local"
    fake_provider.supports_system = True
    fake_provider.model = "test-model"

    monkeypatch.setattr(client, "_pick", lambda agent, *, fallback=False: fake_provider)

    await client.chat(messages=[{"role": "user", "content": "x"}], log=False)
    assert "temperature" not in captured


@pytest.mark.asyncio
async def test_chat_passes_temperature_when_set(monkeypatch):
    """When temperature is set, it appears in the OpenAI SDK call params."""
    client = _client()
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok", model_extra=None))]
        )

    fake_inner = MagicMock()
    fake_inner.chat.completions.create = fake_create
    fake_provider = MagicMock()
    fake_provider.next_chat_client.return_value = fake_inner
    fake_provider.thinking_mode = "off"
    fake_provider.toggle_style = "local"
    fake_provider.supports_system = True
    fake_provider.model = "test-model"

    monkeypatch.setattr(client, "_pick", lambda agent, *, fallback=False: fake_provider)

    await client.chat(
        messages=[{"role": "user", "content": "x"}], temperature=0.2, log=False
    )
    assert captured.get("temperature") == 0.2


@pytest.mark.asyncio
async def test_chat_passes_local_think_toggle(monkeypatch):
    client = _client()
    captured: list[dict] = []

    async def fake_create(**kwargs):
        captured.append(kwargs)
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok", model_extra=None))]
        )

    fake_inner = MagicMock()
    fake_inner.chat.completions.create = fake_create
    fake_provider = MagicMock()
    fake_provider.next_chat_client.return_value = fake_inner
    fake_provider.thinking_mode = "opt"
    fake_provider.toggle_style = "local"
    fake_provider.supports_system = True
    fake_provider.model = "test-model"

    monkeypatch.setattr(client, "_pick", lambda agent, *, fallback=False: fake_provider)

    await client.chat(
        messages=[{"role": "user", "content": "x"}], think=False, log=False
    )
    await client.chat(
        messages=[{"role": "user", "content": "x"}], think=True, log=False
    )

    assert captured[0]["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert captured[1]["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": True}
    }


@pytest.mark.asyncio
async def test_force_think_override_is_scoped(monkeypatch):
    client = _client()
    captured: list[dict] = []

    async def fake_create(**kwargs):
        captured.append(kwargs)
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok", model_extra=None))]
        )

    fake_inner = MagicMock()
    fake_inner.chat.completions.create = fake_create
    fake_provider = MagicMock()
    fake_provider.next_chat_client.return_value = fake_inner
    fake_provider.thinking_mode = "opt"
    fake_provider.toggle_style = "local"
    fake_provider.supports_system = True
    fake_provider.model = "test-model"

    monkeypatch.setattr(client, "_pick", lambda agent, *, fallback=False: fake_provider)

    with force_think(True):
        await client.chat(
            messages=[{"role": "user", "content": "x"}],
            think=False,
            log=False,
        )
    await client.chat(
        messages=[{"role": "user", "content": "x"}],
        think=False,
        log=False,
    )

    assert captured[0]["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": True}
    }
    assert captured[1]["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


@pytest.mark.asyncio
async def test_chat_diag_includes_provider_route(monkeypatch, capsys):
    monkeypatch.setenv("FLOW_DEBUG", "1")
    client = _client()

    async def fake_create(**kwargs):
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok", model_extra=None))]
        )

    fake_inner = MagicMock()
    fake_inner.chat.completions.create = fake_create
    fake_provider = MagicMock()
    fake_provider.next_chat_client.return_value = fake_inner
    fake_provider.base_url = "http://127.0.0.1:8000/v1"
    fake_provider.thinking_mode = "off"
    fake_provider.toggle_style = "local"
    fake_provider.supports_system = True
    fake_provider.model = "gemma-local.gguf"

    monkeypatch.setattr(client, "_pick", lambda agent, *, fallback=False: fake_provider)

    await client.chat(
        messages=[{"role": "user", "content": "x"}],
        agent="classify",
        log=False,
    )
    stderr = capsys.readouterr().err

    assert "llm:request" in stderr
    assert "agent='classify'" in stderr
    assert "model='gemma-local.gguf'" in stderr
    assert "base_url='http://127.0.0.1:8000/v1'" in stderr
    assert "thinking_mode='off'" in stderr
    assert "think_requested=True" in stderr
