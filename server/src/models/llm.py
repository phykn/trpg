import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from .decision import ModelUnavailable


@dataclass(frozen=True)
class LLM:
    ids: tuple[str, ...]          # substrings of the server's model id, any of which is this model
    sampling: dict[str, Any] = field(default_factory=dict)


# local-models llm.toml: the non-thinking sampling from each model card.
LLM_MODELS = {
    "qwen": LLM(("Qwen3.8-27B", "Qwen3.6-35B-A3B"),
                {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5}),
    "gemma4": LLM(("gemma-4-26B-A4B",), {"temperature": 1.0, "top_p": 0.95, "top_k": 64}),
    "minicpm": LLM(("MiniCPM-V-4.7",), {"temperature": 0.7, "top_p": 0.95, "top_k": 100, "repetition_penalty": 1.03}),
}


class LLMClient:
    def __init__(self, base_url: str, *, model: str = "qwen", sampling: dict[str, Any] | None = None,
                 timeout_s: float = 120.0, transport: httpx.AsyncBaseTransport | None = None):
        if model not in LLM_MODELS:
            raise ValueError(f"unknown llm {model!r}; one of {sorted(LLM_MODELS)}")
        self.base_url = base_url.rstrip("/")
        self.name = model
        self.model: str | None = None            # the server's id, found by resolve_model
        self.sampling = sampling or dict(LLM_MODELS[model].sampling)
        self.timeout_s = timeout_s
        self.transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout_s, transport=self.transport)

    async def resolve_model(self) -> str:
        """mlx-vlm wants the snapshot path as the id. A model that is not loaded is an error: the server never
        loads one for us."""
        if self.model is not None:
            return self.model
        try:
            async with self._client() as client:
                response = await client.get(f"{self.base_url}/models")
            response.raise_for_status()
            models = response.json()["data"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ModelUnavailable(f"llm: {type(exc).__name__}: {exc}") from exc
        ids = LLM_MODELS[self.name].ids
        mine = [m for m in models if any(i.lower() in m["id"].lower() for i in ids)]
        loaded = [m for m in mine if m.get("loaded", len(models) == 1)]
        if not loaded:
            others = [m["id"] for m in models if m.get("loaded")]
            raise ModelUnavailable(f"llm: {self.name} is configured but not loaded (loaded: {others or 'nothing'})")
        self.model = loaded[0]["id"]
        return self.model

    async def pick(self, messages: list[dict[str, str]], max_tokens: int = 12) -> str:
        # Greedy for this call only: the narrator streams on the same client meanwhile.
        chunks = self.stream(messages, max_tokens, seed=1, sampling={"temperature": 0.0})
        return "".join([chunk async for chunk in chunks])

    def body(self, messages: list[dict[str, str]], max_tokens: int, seed: int | None = None,
             sampling: dict[str, Any] | None = None) -> dict[str, Any]:
        # mlx-lm reads chat_template_kwargs, mlx-vlm reads the top-level flag; send both, always off.
        # The server samples with a fixed seed unless told otherwise, so a rewrite needs its own seed.
        return {
            "model": self.model, "messages": messages, "stream": True, "max_tokens": max_tokens,
            "enable_thinking": False, "chat_template_kwargs": {"enable_thinking": False},
            **(self.sampling if sampling is None else sampling), **({"seed": seed} if seed is not None else {}),
        }

    async def stream(self, messages: list[dict[str, str]], max_tokens: int = 500,
                     seed: int | None = None, sampling: dict[str, Any] | None = None) -> AsyncIterator[str]:
        if self.model is None:
            await self.resolve_model()
        try:
            url, body = f"{self.base_url}/chat/completions", self.body(messages, max_tokens, seed, sampling)
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
            raise ModelUnavailable(f"llm: {type(exc).__name__}: {exc}") from exc
