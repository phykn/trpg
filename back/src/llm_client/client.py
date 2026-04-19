from collections.abc import Iterator
from pathlib import Path

from openai import OpenAI


class LLMClient:
    def __init__(self, base_url: str, model: str = "local", api_key: str = "none"):
        self._client = OpenAI(base_url=base_url, api_key=api_key)
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

    def _build(self, system: str | Path | None, query: str, think: bool) -> dict:
        messages = []
        sys_text = self._resolve_system(system)
        if sys_text:
            messages.append({"role": "system", "content": sys_text})
        messages.append({"role": "user", "content": query})
        return {
            "model": self._model,
            "messages": messages,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": think}},
        }

    def stream(
        self, system: str | Path | None, query: str, think: bool = True
    ) -> Iterator[dict]:
        params = self._build(system, query, think)
        for chunk in self._client.chat.completions.create(**params, stream=True):
            delta = chunk.choices[0].delta
            extra = delta.model_extra or {}
            yield {"think": extra.get("reasoning_content"), "answer": delta.content}

    def complete(
        self, system: str | Path | None, query: str, think: bool = True
    ) -> dict:
        params = self._build(system, query, think)
        msg = self._client.chat.completions.create(**params).choices[0].message
        extra = msg.model_extra or {}
        return {"think": extra.get("reasoning_content"), "answer": msg.content}
