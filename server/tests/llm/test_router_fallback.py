"""Router fallback: optional LLM_ROUTE_<AGENT>_FALLBACK env triggers a secondary
profile used when the primary raises RateLimitError."""

from unittest.mock import MagicMock

import httpx
import pytest
from openai import RateLimitError
from pydantic import BaseModel, ValidationError

from src.game.domain.errors import LLMUnavailable
from src.llm.client import LLMClient
from src.llm.calls._runner import run_with_retries


def _set_env(monkeypatch, **overrides):
    base = {
        "LLM_GOOGLE_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "LLM_GOOGLE_API_KEYS": "k1",
        "LLM_GOOGLE_THINK_OPT": "model_a",
        "LLM_GOOGLE_THINK_OPT_ON": "model_b",
        "LLM_ROUTE_DEFAULT": "google/model_a",
        "LLM_ROUTE_CLASSIFY": "google/model_a",
        "LLM_ROUTE_CLASSIFY_FALLBACK": "google/model_b",
    }
    base.update(overrides)
    # Strip any pre-existing LLM_* env so the parser sees only what we set.
    for key in list(__import__("os").environ):
        if key.startswith("LLM_"):
            monkeypatch.delenv(key, raising=False)
    for k, v in base.items():
        monkeypatch.setenv(k, v)


def _rate_limit_error(message: str = "quota exceeded") -> RateLimitError:
    response = httpx.Response(
        status_code=429, request=httpx.Request("POST", "http://x")
    )
    return RateLimitError(message, response=response, body=None)


def test_parse_fallback_creates_secondary_profile(monkeypatch):
    _set_env(monkeypatch)
    c = LLMClient.from_env()
    fallback = c.pick_fallback("classify")
    assert fallback is not None
    assert fallback.model == "model_b"


def test_pick_fallback_returns_none_when_unset(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.delenv("LLM_ROUTE_CLASSIFY_FALLBACK", raising=False)
    c = LLMClient.from_env()
    assert c.pick_fallback("classify") is None


def test_pick_fallback_returns_none_for_unknown_agent(monkeypatch):
    _set_env(monkeypatch)
    c = LLMClient.from_env()
    assert c.pick_fallback("nonexistent") is None
    assert c.pick_fallback(None) is None


def test_primary_route_regex_does_not_eat_fallback(monkeypatch):
    """LLM_ROUTE_CLASSIFY_FALLBACK must not be parsed as a primary agent
    'classify_fallback' — it'd shadow real agents and break dispatch."""
    _set_env(monkeypatch)
    c = LLMClient.from_env()
    assert "classify_fallback" not in c._providers


@pytest.mark.asyncio
async def test_rate_limit_engages_fallback(monkeypatch):
    """When primary raises RateLimitError, the next attempt uses fallback."""
    _set_env(monkeypatch)
    c = LLMClient.from_env()

    primary = c._providers["classify"]
    fallback = c._fallbacks["classify"]
    seen_models: list[str] = []

    async def fake_create(**kwargs):
        seen_models.append(kwargs["model"])
        if kwargs["model"] == primary.model:
            raise _rate_limit_error()
        return MagicMock(
            choices=[
                MagicMock(message=MagicMock(content='{"ok":true}', model_extra=None))
            ]
        )

    for client in primary._chat_clients + fallback._chat_clients:
        client.chat.completions.create = fake_create

    result = await run_with_retries(
        c,
        system_prompt="sys",
        user_payload="usr",
        parse=lambda s: s,
        agent="classify",
    )
    assert result == '{"ok":true}'
    assert seen_models == [primary.model, fallback.model]


@pytest.mark.asyncio
async def test_no_fallback_raises_llm_unavailable(monkeypatch):
    """Primary RateLimitError with no fallback configured → LLMUnavailable."""
    _set_env(monkeypatch)
    monkeypatch.delenv("LLM_ROUTE_CLASSIFY_FALLBACK", raising=False)
    c = LLMClient.from_env()

    primary = c._providers["classify"]
    seen_models: list[str] = []

    async def fake_create(**kwargs):
        seen_models.append(kwargs["model"])
        raise _rate_limit_error()

    for client in primary._chat_clients:
        client.chat.completions.create = fake_create

    with pytest.raises(LLMUnavailable):
        await run_with_retries(
            c,
            system_prompt="sys",
            user_payload="usr",
            parse=lambda s: s,
            agent="classify",
        )
    assert seen_models == [primary.model]


@pytest.mark.asyncio
async def test_fallback_also_rate_limited_raises_llm_unavailable(monkeypatch):
    """Primary AND fallback rate-limited → LLMUnavailable (no infinite loop)."""
    _set_env(monkeypatch)
    c = LLMClient.from_env()

    primary = c._providers["classify"]
    fallback = c._fallbacks["classify"]
    seen_models: list[str] = []

    async def fake_create(**kwargs):
        seen_models.append(kwargs["model"])
        raise _rate_limit_error()

    for client in primary._chat_clients + fallback._chat_clients:
        client.chat.completions.create = fake_create

    with pytest.raises(LLMUnavailable):
        await run_with_retries(
            c,
            system_prompt="sys",
            user_payload="usr",
            parse=lambda s: s,
            agent="classify",
        )
    assert seen_models == [primary.model, fallback.model]


@pytest.mark.asyncio
async def test_validation_error_does_not_engage_fallback(monkeypatch):
    """ValidationError is a schema issue, not a quota one — must stay on primary
    and exhaust the self-correction budget there. Engaging fallback would mask
    a prompt/schema bug behind a model swap."""
    _set_env(monkeypatch)
    c = LLMClient.from_env()

    primary = c._providers["classify"]
    fallback = c._fallbacks["classify"]
    seen_models: list[str] = []

    async def fake_create(**kwargs):
        seen_models.append(kwargs["model"])
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json", model_extra=None))]
        )

    for client in primary._chat_clients + fallback._chat_clients:
        client.chat.completions.create = fake_create

    class M(BaseModel):
        ok: bool

    def parse(s: str) -> M:
        return M.model_validate_json(s)

    with pytest.raises(ValidationError):
        await run_with_retries(
            c,
            system_prompt="sys",
            user_payload="usr",
            parse=parse,
            agent="classify",
            retries=3,
        )
    assert seen_models == [primary.model] * 3
