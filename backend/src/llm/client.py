import json
from collections.abc import AsyncIterator
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI

from ..rules.config import RULES

# Tag subsequent LLM calls so logs land under `<log_dir>/<session_id>/<agent>/`.
# Outermost callers — QA runner per agent, story runner per scenario, the backend
# flow per game — set this once. `set_llm_session_if_unset` lets the backend
# defer to an outer tag (e.g. QA's "qa-diplomat") instead of clobbering it with
# the in-process game_id.
_SESSION_ID: ContextVar[str | None] = ContextVar("llm_session_id", default=None)


def set_llm_session(session_id: str | None) -> None:
    _SESSION_ID.set(session_id)


def set_llm_session_if_unset(session_id: str) -> None:
    if _SESSION_ID.get() is None:
        _SESSION_ID.set(session_id)


class LLMClient:
    def __init__(
        self,
        base_url: str,
        model: str = "local",
        api_key: str = "none",
        log_dir: Path | None = None,
        chat_timeout_s: float | None = None,
        stream_timeout_s: float | None = None,
    ):
        # Bound chat() and chat_stream() so a stalled LLM raises TimeoutError
        # instead of hanging the whole turn (the OpenAI client's default is
        # roughly 10 minutes — far too long for a per-turn interaction).
        # Long-running offline jobs (story scenario build) can override.
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=chat_timeout_s or RULES.llm.chat_timeout_s,
        )
        self._stream_client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=stream_timeout_s or RULES.llm.stream_timeout_s,
        )
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
        """Return `<log_dir>/[<session>/]<agent>/<ts>` (no suffix). Caller
        appends `_query.json` and `_answer.{json,txt}` so the pair shares a
        stem. The optional session segment groups logs by caller (game id /
        QA agent / scenario)."""
        if self._log_dir is None:
            return None
        sub = agent or "_unknown"
        session = _SESSION_ID.get()
        d = self._log_dir / session / sub if session else self._log_dir / sub
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
        return d / ts

    def _log_query(self, base: Path | None, messages: list[dict]) -> None:
        """Write query as `<role>: <content>` blocks. System messages are
        dropped (always identical), and JSON-shaped content is pretty-printed
        inside its block so retry-loop traces stay readable."""
        if base is None:
            return
        parts: list[str] = []
        for m in messages:
            if m.get("role") == "system":
                continue
            role = m.get("role", "?")
            content = m.get("content", "")
            if isinstance(content, str):
                try:
                    parsed = json.loads(content)
                    content = json.dumps(parsed, ensure_ascii=False, indent=2)
                except (ValueError, TypeError):
                    pass
            elif isinstance(content, (dict, list)):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            parts.append(f"## {role}\n{content}")
        base.with_name(base.name + "_query.txt").write_text(
            "\n\n".join(parts), encoding="utf-8",
        )

    def _log_answer(self, base: Path | None, answer: str) -> None:
        """Write the bare assistant content. JSON-shaped output is
        pretty-printed inside the same .txt for readability."""
        if base is None:
            return
        content = answer
        try:
            parsed = json.loads(answer)
            content = json.dumps(parsed, ensure_ascii=False, indent=2)
        except (ValueError, TypeError):
            pass
        base.with_name(base.name + "_answer.txt").write_text(
            content, encoding="utf-8",
        )

    async def chat(
        self,
        messages: list[dict],
        think: bool = True,
        agent: str | None = None,
    ) -> dict:
        base = self._log_basename(agent)
        self._log_query(base, messages)
        params = self._params(messages, think)
        response = await self._client.chat.completions.create(**params)
        msg = response.choices[0].message
        extra = msg.model_extra or {}
        result = {"think": extra.get("reasoning_content"), "answer": msg.content}
        self._log_answer(base, msg.content or "")
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        think: bool = True,
        agent: str | None = None,
    ) -> AsyncIterator[dict]:
        base = self._log_basename(agent)
        self._log_query(base, messages)
        params = self._params(messages, think)
        stream = await self._stream_client.chat.completions.create(**params, stream=True)
        accum_answer: list[str] = []
        try:
            async for chunk in stream:
                delta = chunk.choices[0].delta
                extra = delta.model_extra or {}
                item = {"think": extra.get("reasoning_content"), "answer": delta.content}
                if item["answer"]:
                    accum_answer.append(item["answer"])
                yield item
        finally:
            self._log_answer(base, "".join(accum_answer))
