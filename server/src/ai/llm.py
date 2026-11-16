from dataclasses import dataclass

import httpx
import openai
from openai import AsyncOpenAI

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
    """gemma4 behind an OpenAI-compatible server, through the openai SDK."""

    def __init__(self, base_url, model, transport=None):
        if model not in LLM_MODELS:
            raise ValueError(f"unknown llm {model!r}; one of {sorted(LLM_MODELS)}")
        self.base_url = base_url
        self.name = model
        self.spec = LLM_MODELS[model]
        self.model = None
        self.transport = transport

    def connect(self):
        # A client per call: startup checks run in their own event loop, and a pooled connection cannot cross loops.
        # The local server needs no key; retries would hide a model that is down.
        http = httpx.AsyncClient(transport=self.transport) if self.transport else None
        return AsyncOpenAI(base_url=self.base_url, api_key="local", max_retries=0, http_client=http)

    async def check(self):
        try:
            async with self.connect() as client:
                listed = await client.models.list(timeout=30.0)
            ids = [m.id for m in listed.data if (m.model_extra or {}).get("loaded")]
        except (openai.APIError, ValueError) as exc:
            raise ModelUnavailable(f"llm: {type(exc).__name__}: {exc}") from None
        mine = [i for i in ids if any(name.lower() in i.lower() for name in self.spec.ids)]
        if not mine:
            raise ModelUnavailable(f"llm: {self.name} is configured but not loaded (loaded: {ids or 'nothing'})")
        self.model = mine[0]
        async for _ in self.stream([{"role": "user", "content": "안녕하십니까"}], 4, timeout=300.0):
            pass

    async def stream(self, messages, max_tokens, timeout=120.0):
        # mlx-lm reads chat_template_kwargs and mlx-vlm the top-level flag, so both go, always off.
        sampling = dict(self.spec.sampling)
        extra = {"top_k": sampling.pop("top_k"), "enable_thinking": False,
                 "chat_template_kwargs": {"enable_thinking": False}}
        try:
            async with self.connect() as client:
                chunks = await client.chat.completions.create(
                    model=self.model, messages=messages, stream=True, max_tokens=max_tokens, timeout=timeout,
                    extra_body=extra, **sampling)
                async for chunk in chunks:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield delta
        except (openai.APIError, ValueError) as exc:
            raise ModelUnavailable(f"llm: {type(exc).__name__}: {exc}") from None
