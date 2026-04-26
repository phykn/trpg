from collections.abc import AsyncIterator
from pathlib import Path

from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, base_url: str, model: str = "local", api_key: str = "none"):
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    @staticmethod
    def _resolve_system(system: str | Path | None) -> str | None:
        if system is None:
            return None
        if isinstance(system, Path):
            return system.read_text(encoding="utf-8")
        s = system.strip()
        if s.endswith(".md") and Path(s).is_file():
            return Path(s).read_text(encoding="utf-8")
        return system

    def _single_turn(self, system: str | Path | None, query: str) -> list[dict]:
        messages: list[dict] = []
        sys_text = self._resolve_system(system)
        if sys_text:
            messages.append({"role": "system", "content": sys_text})
        messages.append({"role": "user", "content": query})
        return messages

    def _params(self, messages: list[dict], think: bool) -> dict:
        return {
            "model": self._model,
            "messages": messages,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": think}},
        }

    async def chat(self, messages: list[dict], think: bool = True) -> dict:
        params = self._params(messages, think)
        response = await self._client.chat.completions.create(**params)
        msg = response.choices[0].message
        extra = msg.model_extra or {}
        return {"think": extra.get("reasoning_content"), "answer": msg.content}

    async def chat_stream(
        self, messages: list[dict], think: bool = True
    ) -> AsyncIterator[dict]:
        params = self._params(messages, think)
        stream = await self._client.chat.completions.create(**params, stream=True)
        async for chunk in stream:
            delta = chunk.choices[0].delta
            extra = delta.model_extra or {}
            yield {"think": extra.get("reasoning_content"), "answer": delta.content}

    async def complete(
        self, system: str | Path | None, query: str, think: bool = True
    ) -> dict:
        return await self.chat(self._single_turn(system, query), think)

    async def stream(
        self, system: str | Path | None, query: str, think: bool = True
    ) -> AsyncIterator[dict]:
        async for chunk in self.chat_stream(self._single_turn(system, query), think):
            yield chunk
