"""Qwen narration model over an OpenAI-compatible server, always non-thinking."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .kev import ModelUnavailable

AUTO = "auto"
NON_THINKING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5}


class QwenClient:
    def __init__(self, base_url: str, *, model: str = AUTO, sampling: dict[str, Any] | None = None,
                 timeout_s: float = 120.0, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.sampling = sampling or dict(NON_THINKING)
        self.timeout_s = timeout_s
        self.transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout_s, transport=self.transport)

    async def resolve_model(self) -> str:
        """Replace `auto` with the id the server marks loaded; mlx-vlm wants its snapshot path."""
        if self.model != AUTO:
            return self.model
        try:
            async with self._client() as client:
                response = await client.get(f"{self.base_url}/models")
            response.raise_for_status()
            models = response.json()["data"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ModelUnavailable(f"qwen: {type(exc).__name__}: {exc}") from exc
        loaded = [m for m in models if m.get("loaded")] or (models if len(models) == 1 else [])
        if not loaded:
            raise ModelUnavailable(f"qwen: no loaded model among {len(models)}")
        self.model = loaded[0]["id"]
        return self.model

    async def pick(self, messages: list[dict[str, str]], max_tokens: int = 6) -> str:
        """A short deterministic answer (a number from a closed list), never sampled."""
        saved = self.sampling
        self.sampling = {"temperature": 0.0}
        try:
            return "".join([chunk async for chunk in self.stream(messages, max_tokens, seed=1)])
        finally:
            self.sampling = saved

    def body(self, messages: list[dict[str, str]], max_tokens: int, seed: int | None = None) -> dict[str, Any]:
        # mlx-lm reads chat_template_kwargs, mlx-vlm reads the top-level flag; send both, always off.
        # The server samples with a fixed seed unless told otherwise, so a rewrite needs its own seed.
        return {
            "model": self.model, "messages": messages, "stream": True, "max_tokens": max_tokens,
            "enable_thinking": False, "chat_template_kwargs": {"enable_thinking": False},
            **self.sampling, **({"seed": seed} if seed is not None else {}),
        }

    async def stream(self, messages: list[dict[str, str]], max_tokens: int = 500,
                     seed: int | None = None) -> AsyncIterator[str]:
        if self.model == AUTO:
            await self.resolve_model()
        try:
            url, body = f"{self.base_url}/chat/completions", self.body(messages, max_tokens, seed)
            async with self._client() as client, client.stream("POST", url, json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    delta = json.loads(data)["choices"][0].get("delta", {}).get("content") or ""
                    if delta:
                        yield delta
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            raise ModelUnavailable(f"qwen: {type(exc).__name__}: {exc}") from exc
