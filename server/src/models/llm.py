import json
from dataclasses import dataclass

import httpx

from . import ModelUnavailable


@dataclass(frozen=True)
class LLM:
    ids: tuple
    sampling: dict


# The server lists a model by its repo name or by its snapshot path, where "/" becomes "--".
# Sampling is the model card's non-thinking setting.
LLM_MODELS = {
    "gemma4": LLM(("mlx-community/gemma-4-26B-A4B-it-qat-4bit", "mlx-community--gemma-4-26B-A4B-it-qat-4bit"),
                  {"temperature": 1.0, "top_p": 0.95, "top_k": 64}),
}


class LLMClient:
    def __init__(self, base_url, model, transport=None):
        if model not in LLM_MODELS:
            raise ValueError(f"unknown llm {model!r}; one of {sorted(LLM_MODELS)}")
        self.base_url = base_url.rstrip("/")
        self.name = model
        self.model = None
        self.transport = transport

    async def check(self):
        try:
            async with httpx.AsyncClient(timeout=30.0, transport=self.transport) as client:
                response = await client.get(f"{self.base_url}/models")
            response.raise_for_status()
            ids = [m["id"] for m in response.json()["data"] if m.get("loaded")]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ModelUnavailable(f"llm: {type(exc).__name__}: {exc}") from None
        mine = [i for i in ids if any(name.lower() in i.lower() for name in LLM_MODELS[self.name].ids)]
        if not mine:
            raise ModelUnavailable(f"llm: {self.name} is configured but not loaded (loaded: {ids or 'nothing'})")
        self.model = mine[0]
        async for _ in self.stream([{"role": "user", "content": "안녕하십니까"}], max_tokens=4, timeout=300.0):
            pass

    async def stream(self, messages, max_tokens, timeout=120.0):
        # mlx-lm reads chat_template_kwargs and mlx-vlm the top-level flag, so both go, always off.
        body = {"model": self.model, "messages": messages, "stream": True, "max_tokens": max_tokens,
                "enable_thinking": False, "chat_template_kwargs": {"enable_thinking": False},
                **LLM_MODELS[self.name].sampling}
        try:
            async with (httpx.AsyncClient(timeout=timeout, transport=self.transport) as client,
                        client.stream("POST", f"{self.base_url}/chat/completions", json=body) as response):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    data = line[5:].strip() if line.startswith("data:") else None
                    if data == "[DONE]":
                        return
                    delta = data and json.loads(data)["choices"][0].get("delta", {}).get("content")
                    if delta:
                        yield delta
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            raise ModelUnavailable(f"llm: {type(exc).__name__}: {exc}") from None
