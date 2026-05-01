import json
import os
import re
from collections.abc import AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, NamedTuple

from openai import AsyncOpenAI

from ..rules.config import RULES

# Logs land under `<log_dir>/<session_id>/<agent>/`. Outermost callers set
# this; `set_llm_session_if_unset` lets a server flow defer to an outer tag.
_SESSION_ID: ContextVar[str | None] = ContextVar("llm_session_id", default=None)

# Per-task override that wins over the agent's hardcoded `think` default.
# ContextVar is task-scoped so concurrent requests don't leak.
_THINK_OVERRIDE: ContextVar[bool | None] = ContextVar("llm_think_override", default=None)


def set_llm_session(session_id: str) -> None:
    _SESSION_ID.set(session_id)


def set_llm_session_if_unset(session_id: str) -> None:
    if _SESSION_ID.get() is None:
        _SESSION_ID.set(session_id)


def set_think_override(value: bool | None) -> None:
    _THINK_OVERRIDE.set(value)


# off: model can't think (e.g. Gemma 3, GPT-4o)
# opt: caller picks per call via `think` flag (e.g. Qwen3 with extra_body)
# on:  model always thinks, no toggle (reasoning-only models)
ThinkingMode = Literal["off", "opt", "on"]

# How an OPT-mode provider toggles thinking on a per-call basis.
#   qwen:   extra_body.chat_template_kwargs.enable_thinking — llama.cpp / Qwen3
#   gemini: extra_body.reasoning_effort — Google Gemini OpenAI-compat
# Derived from base_url at provider construction; sniffed for googleapis.com.
ToggleStyle = Literal["qwen", "gemini"]


@dataclass(frozen=True)
class LLMProfile:
    base_url: str
    model: str
    api_keys: tuple[str, ...]
    thinking_mode: ThinkingMode


_PROVIDER_RE = re.compile(
    r"^LLM_(?!ROUTE_)([A-Z0-9_]+?)_(BASE_URL|API_KEYS|THINK_OFF|THINK_OPT|THINK_ON)$"
)
_ROUTE_RE = re.compile(r"^LLM_ROUTE_([A-Z0-9_]+)$")


class _ProviderEnv(NamedTuple):
    base_url: str
    api_keys: tuple[str, ...]
    modes: dict[str, ThinkingMode]  # model_name → thinking_mode


def _parse_env_profiles() -> dict[str, LLMProfile]:
    """Build agent profiles from `LLM_<NAME>_*` and `LLM_ROUTE_<AGENT>` env vars.

    `LLM_ROUTE_DEFAULT` is required; unmatched agents fall back to default at
    call time. THINK_* lists per provider are disjoint and together name every
    model the provider serves.
    """

    def csv(s: str) -> tuple[str, ...]:
        return tuple(p.strip() for p in s.split(",") if p.strip())

    def collect_modes(upper: str) -> dict[str, ThinkingMode]:
        modes: dict[str, ThinkingMode] = {}
        for suffix, mode in (("THINK_OFF", "off"), ("THINK_OPT", "opt"), ("THINK_ON", "on")):
            for model in csv(os.environ.get(f"LLM_{upper}_{suffix}", "")):
                if model in modes:
                    raise ValueError(
                        f"LLM_{upper}_{suffix} duplicates model {model!r} "
                        f"already in another THINK_* category"
                    )
                modes[model] = mode  # type: ignore[assignment]
        if not modes:
            raise ValueError(
                f"LLM_{upper} must declare at least one of "
                f"THINK_OFF / THINK_OPT / THINK_ON"
            )
        return modes

    # Phase 1: read each LLM_<NAME>_* block.
    providers: dict[str, _ProviderEnv] = {}
    for upper in {m[1] for k in os.environ if (m := _PROVIDER_RE.match(k))}:
        api_keys = csv(os.environ[f"LLM_{upper}_API_KEYS"])
        if not api_keys:
            raise ValueError(f"LLM_{upper}_API_KEYS must list at least one key")
        providers[upper.lower()] = _ProviderEnv(
            base_url=os.environ[f"LLM_{upper}_BASE_URL"],
            api_keys=api_keys,
            modes=collect_modes(upper),
        )

    # Phase 2: read each LLM_ROUTE_<AGENT> = <provider>/<model>.
    routes: dict[str, tuple[str, str]] = {}
    for key, value in os.environ.items():
        if not (m := _ROUTE_RE.match(key)):
            continue
        spec = value.strip()
        if "/" not in spec:
            raise ValueError(f"{key} must be '<provider>/<model>' (got {value!r})")
        prov, model = spec.split("/", 1)
        routes[m[1].lower()] = (prov.strip(), model.strip())
    if "default" not in routes:
        raise ValueError("LLM_ROUTE_DEFAULT must be set")

    # Phase 3: resolve each route into a profile.
    profiles: dict[str, LLMProfile] = {}
    for agent, (prov_name, model_name) in routes.items():
        if prov_name not in providers:
            raise ValueError(
                f"LLM_ROUTE_{agent.upper()} references unknown provider "
                f"{prov_name!r} (no LLM_{prov_name.upper()}_BASE_URL)"
            )
        prov = providers[prov_name]
        if model_name not in prov.modes:
            raise ValueError(
                f"LLM_ROUTE_{agent.upper()} references unknown model "
                f"{model_name!r} for provider {prov_name!r} (not in any "
                f"LLM_{prov_name.upper()}_THINK_* list)"
            )
        profiles[agent] = LLMProfile(
            base_url=prov.base_url,
            model=model_name,
            api_keys=prov.api_keys,
            thinking_mode=prov.modes[model_name],
        )
    return profiles


class _ThoughtSplitter:
    """Routes inline `<thought>...</thought>` from a token stream to the think channel.

    Used for models like Gemma 4 that emit reasoning at the head of the answer
    body. Buffers up to LOOKAHEAD chars to detect tags split across chunk
    seams; falls through to answer-only when no tag appears.
    """

    OPEN = "<thought>"
    CLOSE = "</thought>"
    LOOKAHEAD = max(len(OPEN), len(CLOSE)) - 1

    def __init__(self) -> None:
        self._buf = ""
        self._mode = "preopen"  # preopen → think → answer

    def feed(self, chunk: str) -> tuple[str, str]:
        if not chunk:
            return "", ""
        self._buf += chunk
        think = ""
        answer = ""
        if self._mode == "preopen":
            if self._buf.startswith(self.OPEN):
                self._buf = self._buf[len(self.OPEN):]
                self._mode = "think"
            elif self.OPEN.startswith(self._buf):
                return "", ""  # may still grow into the open tag
            else:
                self._mode = "answer"
        if self._mode == "think":
            idx = self._buf.find(self.CLOSE)
            if idx >= 0:
                think = self._buf[:idx]
                self._buf = self._buf[idx + len(self.CLOSE):]
                self._mode = "answer"
            else:
                safe = max(0, len(self._buf) - self.LOOKAHEAD)
                think = self._buf[:safe]
                self._buf = self._buf[safe:]
                return think, ""
        if self._mode == "answer":
            answer = self._buf
            self._buf = ""
        return think, answer

    def flush(self) -> tuple[str, str]:
        if not self._buf:
            return "", ""
        if self._mode == "think":
            out = (self._buf, "")
        else:
            out = ("", self._buf)
        self._buf = ""
        return out


class _Provider:
    """Per-profile transport: round-robins one AsyncOpenAI client per API key.

    Index increment is atomic under the GIL, so no lock is needed.
    """

    def __init__(
        self,
        profile: LLMProfile,
        chat_timeout_s: float,
        stream_timeout_s: float,
    ):
        if not profile.api_keys:
            raise ValueError(f"profile model={profile.model!r} has no api_keys")
        self.model = profile.model
        self.thinking_mode = profile.thinking_mode
        self.toggle_style: ToggleStyle = (
            "gemini" if "googleapis.com" in profile.base_url else "qwen"
        )
        self._chat_clients = [
            AsyncOpenAI(base_url=profile.base_url, api_key=k, timeout=chat_timeout_s)
            for k in profile.api_keys
        ]
        self._stream_clients = [
            AsyncOpenAI(
                base_url=profile.base_url, api_key=k, timeout=stream_timeout_s
            )
            for k in profile.api_keys
        ]
        self._idx = 0

    def next_chat_client(self) -> AsyncOpenAI:
        c = self._chat_clients[self._idx % len(self._chat_clients)]
        self._idx += 1
        return c

    def next_stream_client(self) -> AsyncOpenAI:
        c = self._stream_clients[self._idx % len(self._stream_clients)]
        self._idx += 1
        return c


class LLMClient:
    """Routes chat calls to per-agent profiles, falling back to 'default'.

    Timeouts override the OpenAI client's ~10-minute default so a stalled LLM
    raises instead of hanging the turn; offline jobs can pass longer values.
    """

    def __init__(
        self,
        profiles: dict[str, LLMProfile],
        log_dir: Path | None = None,
        chat_timeout_s: float | None = None,
        stream_timeout_s: float | None = None,
    ):
        if "default" not in profiles:
            raise ValueError("profiles must include a 'default' entry")
        chat_t = chat_timeout_s or RULES.llm.chat_timeout_s
        stream_t = stream_timeout_s or RULES.llm.stream_timeout_s
        self._providers: dict[str, _Provider] = {
            name: _Provider(p, chat_t, stream_t) for name, p in profiles.items()
        }
        self._log_dir = log_dir

    @classmethod
    def from_single(
        cls,
        *,
        base_url: str,
        model: str = "local",
        api_key: str = "none",
        thinking_mode: ThinkingMode = "opt",
        log_dir: Path | None = None,
        chat_timeout_s: float | None = None,
        stream_timeout_s: float | None = None,
    ) -> "LLMClient":
        profile = LLMProfile(
            base_url=base_url,
            model=model,
            api_keys=(api_key,),
            thinking_mode=thinking_mode,
        )
        return cls(
            profiles={"default": profile},
            log_dir=log_dir,
            chat_timeout_s=chat_timeout_s,
            stream_timeout_s=stream_timeout_s,
        )

    @classmethod
    def from_env(
        cls,
        *,
        log_dir: Path | None = None,
        chat_timeout_s: float | None = None,
        stream_timeout_s: float | None = None,
    ) -> "LLMClient":
        return cls(
            profiles=_parse_env_profiles(),
            log_dir=log_dir,
            chat_timeout_s=chat_timeout_s,
            stream_timeout_s=stream_timeout_s,
        )

    def _pick(self, agent: str | None) -> _Provider:
        if agent and agent in self._providers:
            return self._providers[agent]
        return self._providers["default"]

    def _params(
        self, provider: _Provider, messages: list[dict], think: bool
    ) -> dict:
        params: dict = {"model": provider.model, "messages": messages}
        # Only the `opt` mode toggles via extra_body — `off` and `on` models
        # decide for themselves and reject (or ignore) the unknown extra_body.
        if provider.thinking_mode == "opt":
            override = _THINK_OVERRIDE.get()
            effective = think if override is None else override
            if provider.toggle_style == "gemini":
                # Gemini defaults to minimal thinking; only opt-in when asked.
                if effective:
                    params["extra_body"] = {"reasoning_effort": "medium"}
            else:
                params["extra_body"] = {
                    "chat_template_kwargs": {"enable_thinking": effective}
                }
        return params

    def _log_basename(self, agent: str | None) -> Path | None:
        if self._log_dir is None:
            return None
        sub = agent or "_unknown"
        session = _SESSION_ID.get()
        d = self._log_dir / session / sub if session else self._log_dir / sub
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
        return d / ts

    @staticmethod
    def _pretty(content: object) -> str:
        """Pretty-print JSON-shaped content; pass strings through if not JSON."""
        if isinstance(content, str):
            try:
                return json.dumps(json.loads(content), ensure_ascii=False, indent=2)
            except (ValueError, TypeError):
                return content
        if isinstance(content, (dict, list)):
            return json.dumps(content, ensure_ascii=False, indent=2)
        return str(content)

    def _log_query(self, base: Path | None, messages: list[dict]) -> None:
        if base is None:
            return
        parts = [
            f"## {m.get('role', '?')}\n{self._pretty(m.get('content', ''))}"
            for m in messages
            if m.get("role") != "system"
        ]
        base.with_name(base.name + "_query.txt").write_text(
            "\n\n".join(parts), encoding="utf-8"
        )

    def _log_answer(self, base: Path | None, answer: str) -> None:
        if base is None:
            return
        base.with_name(base.name + "_answer.txt").write_text(
            self._pretty(answer), encoding="utf-8"
        )

    async def chat(
        self,
        messages: list[dict],
        think: bool = True,
        agent: str | None = None,
        log: bool = True,
    ) -> dict:
        provider = self._pick(agent)
        base = self._log_basename(agent) if log else None
        self._log_query(base, messages)
        params = self._params(provider, messages, think)
        response = await provider.next_chat_client().chat.completions.create(
            **params
        )
        msg = response.choices[0].message
        extra = msg.model_extra or {}
        think = extra.get("reasoning_content")
        answer = msg.content or ""
        if provider.thinking_mode == "on":
            sp = _ThoughtSplitter()
            t1, a1 = sp.feed(answer)
            t2, a2 = sp.flush()
            inline_think = t1 + t2
            answer = a1 + a2
            if inline_think:
                think = (think or "") + inline_think
        result = {"think": think, "answer": answer}
        self._log_answer(base, answer)
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        think: bool = True,
        agent: str | None = None,
        log: bool = True,
    ) -> AsyncIterator[dict]:
        provider = self._pick(agent)
        base = self._log_basename(agent) if log else None
        self._log_query(base, messages)
        params = self._params(provider, messages, think)
        stream = await provider.next_stream_client().chat.completions.create(
            **params, stream=True
        )
        splitter = (
            _ThoughtSplitter() if provider.thinking_mode == "on" else None
        )
        accum_answer: list[str] = []
        try:
            async for chunk in stream:
                delta = chunk.choices[0].delta
                extra = delta.model_extra or {}
                think = extra.get("reasoning_content")
                answer = delta.content or ""
                if splitter:
                    sp_think, answer = splitter.feed(answer)
                    if sp_think:
                        think = (think or "") + sp_think
                if answer:
                    accum_answer.append(answer)
                yield {"think": think, "answer": answer or None}
            if splitter:
                sp_think, sp_answer = splitter.flush()
                if sp_answer:
                    accum_answer.append(sp_answer)
                if sp_think or sp_answer:
                    yield {"think": sp_think or None, "answer": sp_answer or None}
        finally:
            self._log_answer(base, "".join(accum_answer))
