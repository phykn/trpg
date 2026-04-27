import json
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI


class LLMClient:
    def __init__(
        self,
        base_url: str,
        model: str = "local",
        api_key: str = "none",
        log_dir: Path | None = None,
    ):
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model = model
        self._log_dir = log_dir

    def _params(self, messages: list[dict], think: bool) -> dict:
        # `extra_body.chat_template_kwargs.enable_thinking` toggles thinking on llama.cpp / Qwen.
        return {
            "model": self._model,
            "messages": messages,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": think}},
        }

    def _log_basename(self, agent: str | None) -> Path | None:
        """Return `<log_dir>/<agent>/<ts>` (no suffix). Caller appends
        `_query.json` / `_answer.json` so the pair shares a stem."""
        if self._log_dir is None:
            return None
        sub = agent or "_unknown"
        d = self._log_dir / sub
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
        return d / ts

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def chat(
        self,
        messages: list[dict],
        think: bool = True,
        agent: str | None = None,
    ) -> dict:
        base = self._log_basename(agent)
        if base is not None:
            self._write_json(base.with_name(base.name + "_query.json"), {
                "agent": agent,
                "mode": "chat",
                "model": self._model,
                "think": think,
                "messages": messages,
            })
        params = self._params(messages, think)
        response = await self._client.chat.completions.create(**params)
        msg = response.choices[0].message
        extra = msg.model_extra or {}
        result = {"think": extra.get("reasoning_content"), "answer": msg.content}
        if base is not None:
            self._write_json(base.with_name(base.name + "_answer.json"), {
                "agent": agent,
                "mode": "chat",
                "model": self._model,
                "think": think,
                "response": result,
            })
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        think: bool = True,
        agent: str | None = None,
    ) -> AsyncIterator[dict]:
        base = self._log_basename(agent)
        if base is not None:
            self._write_json(base.with_name(base.name + "_query.json"), {
                "agent": agent,
                "mode": "stream",
                "model": self._model,
                "think": think,
                "messages": messages,
            })
        params = self._params(messages, think)
        stream = await self._client.chat.completions.create(**params, stream=True)
        chunks: list[dict] = []
        accum_think: list[str] = []
        accum_answer: list[str] = []
        try:
            async for chunk in stream:
                delta = chunk.choices[0].delta
                extra = delta.model_extra or {}
                item = {"think": extra.get("reasoning_content"), "answer": delta.content}
                chunks.append(item)
                if item["think"]:
                    accum_think.append(item["think"])
                if item["answer"]:
                    accum_answer.append(item["answer"])
                yield item
        finally:
            if base is not None:
                self._write_json(base.with_name(base.name + "_answer.json"), {
                    "agent": agent,
                    "mode": "stream",
                    "model": self._model,
                    "think": think,
                    "chunks": chunks,
                    "accumulated": {
                        "think": "".join(accum_think) or None,
                        "answer": "".join(accum_answer) or None,
                    },
                })
