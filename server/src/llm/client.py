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
from . import gemini, llama_cpp

# Logs land under `<log_dir>/<session_id>/<agent>/`; outer callers set this and inner ones can defer.
_SESSION_ID: ContextVar[str | None] = ContextVar("llm_session_id", default=None)

# Task-scoped override so concurrent requests can't leak each other's `think` choice.
_THINK_OVERRIDE: ContextVar[bool | None] = ContextVar(
    "llm_think_override", default=None
)


def set_llm_session(session_id: str) -> None:
    _SESSION_ID.set(session_id)


def set_llm_session_if_unset(session_id: str) -> None:
    if _SESSION_ID.get() is None:
        _SESSION_ID.set(session_id)


def set_think_override(value: bool | None) -> None:
    _THINK_OVERRIDE.set(value)


# off / on: forced; opt / opt_on: per-call `think` flag with that default.
ThinkingMode = Literal["off", "opt", "opt_on", "on"]

# Picks the `extra_body` builder + response parser; derived from base_url.
ToggleStyle = Literal["llama_cpp", "gemini"]


@dataclass(frozen=True)
class LLMProfile:
    base_url: str
    model: str
    api_keys: tuple[str, ...]
    thinking_mode: ThinkingMode
    supports_system: bool


_PROVIDER_RE = re.compile(
    r"^LLM_(?!ROUTE_)([A-Z0-9_]+?)_(BASE_URL|API_KEYS|THINK_OFF|THINK_OPT_ON|THINK_OPT|THINK_ON|NO_SYSTEM)$"
)
_ROUTE_RE = re.compile(r"^LLM_ROUTE_([A-Z0-9_]+)$")
_FALLBACK_RE = re.compile(r"^LLM_ROUTE_([A-Z0-9_]+)_FALLBACK$")


class _ProviderEnv(NamedTuple):
    base_url: str
    api_keys: tuple[str, ...]
    modes: dict[str, ThinkingMode]  # model_name → thinking_mode
    no_system: frozenset[str]  # models that reject `role: system`


def _parse_env_profiles() -> tuple[dict[str, LLMProfile], dict[str, LLMProfile]]:
    """Build agent (primary, fallback) profiles from env.

    `LLM_ROUTE_DEFAULT` is required; unmatched agents fall back to default at
    call time. Optional `LLM_ROUTE_<AGENT>_FALLBACK` defines a secondary
    profile reached on quota errors. THINK_* lists per provider are disjoint
    and together name every model the provider serves.
    """

    def csv(s: str) -> tuple[str, ...]:
        return tuple(p.strip() for p in s.split(",") if p.strip())

    def collect_modes(upper: str) -> dict[str, ThinkingMode]:
        modes: dict[str, ThinkingMode] = {}
        for suffix, mode in (
            ("THINK_OFF", "off"),
            ("THINK_OPT", "opt"),
            ("THINK_OPT_ON", "opt_on"),
            ("THINK_ON", "on"),
        ):
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
                f"THINK_OFF / THINK_OPT / THINK_OPT_ON / THINK_ON"
            )
        return modes

    # Phase 1: read each LLM_<NAME>_* block.
    providers: dict[str, _ProviderEnv] = {}
    for upper in {m[1] for k in os.environ if (m := _PROVIDER_RE.match(k))}:
        api_keys = csv(os.environ[f"LLM_{upper}_API_KEYS"])
        if not api_keys:
            raise ValueError(f"LLM_{upper}_API_KEYS must list at least one key")
        modes = collect_modes(upper)
        no_system = frozenset(csv(os.environ.get(f"LLM_{upper}_NO_SYSTEM", "")))
        unknown = no_system - modes.keys()
        if unknown:
            raise ValueError(
                f"LLM_{upper}_NO_SYSTEM lists unknown model(s) "
                f"{sorted(unknown)} (not in any LLM_{upper}_THINK_* list)"
            )
        providers[upper.lower()] = _ProviderEnv(
            base_url=os.environ[f"LLM_{upper}_BASE_URL"],
            api_keys=api_keys,
            modes=modes,
            no_system=no_system,
        )

    # Phase 2: read each LLM_ROUTE_<AGENT> = <provider>/<model>; route _FALLBACK
    # variants to a separate map so the primary regex doesn't capture them.
    routes: dict[str, tuple[str, str]] = {}
    fallback_routes: dict[str, tuple[str, str]] = {}
    for key, value in os.environ.items():
        m_fb = _FALLBACK_RE.match(key)
        if m_fb:
            spec = value.strip()
            if "/" not in spec:
                raise ValueError(f"{key} must be '<provider>/<model>' (got {value!r})")
            prov, model = spec.split("/", 1)
            fallback_routes[m_fb[1].lower()] = (prov.strip(), model.strip())
            continue
        m = _ROUTE_RE.match(key)
        if not m:
            continue
        spec = value.strip()
        if "/" not in spec:
            raise ValueError(f"{key} must be '<provider>/<model>' (got {value!r})")
        prov, model = spec.split("/", 1)
        routes[m[1].lower()] = (prov.strip(), model.strip())
    if "default" not in routes:
        raise ValueError("LLM_ROUTE_DEFAULT must be set")

    def _resolve(label: str, prov_name: str, model_name: str) -> LLMProfile:
        if prov_name not in providers:
            raise ValueError(
                f"{label} references unknown provider "
                f"{prov_name!r} (no LLM_{prov_name.upper()}_BASE_URL)"
            )
        prov = providers[prov_name]
        if model_name not in prov.modes:
            raise ValueError(
                f"{label} references unknown model "
                f"{model_name!r} for provider {prov_name!r} (not in any "
                f"LLM_{prov_name.upper()}_THINK_* list)"
            )
        return LLMProfile(
            base_url=prov.base_url,
            model=model_name,
            api_keys=prov.api_keys,
            thinking_mode=prov.modes[model_name],
            supports_system=model_name not in prov.no_system,
        )

    # Phase 3: resolve each route into a profile.
    profiles: dict[str, LLMProfile] = {
        agent: _resolve(f"LLM_ROUTE_{agent.upper()}", prov_name, model_name)
        for agent, (prov_name, model_name) in routes.items()
    }
    fallbacks: dict[str, LLMProfile] = {
        agent: _resolve(f"LLM_ROUTE_{agent.upper()}_FALLBACK", prov_name, model_name)
        for agent, (prov_name, model_name) in fallback_routes.items()
    }
    return profiles, fallbacks


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
            "gemini" if "googleapis.com" in profile.base_url else "llama_cpp"
        )
        self.supports_system = profile.supports_system
        self._chat_clients = [
            AsyncOpenAI(base_url=profile.base_url, api_key=k, timeout=chat_timeout_s)
            for k in profile.api_keys
        ]
        self._stream_clients = [
            AsyncOpenAI(base_url=profile.base_url, api_key=k, timeout=stream_timeout_s)
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
        fallbacks: dict[str, LLMProfile] | None = None,
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
        self._fallbacks: dict[str, _Provider] = {
            name: _Provider(p, chat_t, stream_t)
            for name, p in (fallbacks or {}).items()
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
        supports_system: bool = True,
        log_dir: Path | None = None,
        chat_timeout_s: float | None = None,
        stream_timeout_s: float | None = None,
    ) -> "LLMClient":
        profile = LLMProfile(
            base_url=base_url,
            model=model,
            api_keys=(api_key,),
            thinking_mode=thinking_mode,
            supports_system=supports_system,
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
        primary, fallbacks = _parse_env_profiles()
        return cls(
            profiles=primary,
            fallbacks=fallbacks,
            log_dir=log_dir,
            chat_timeout_s=chat_timeout_s,
            stream_timeout_s=stream_timeout_s,
        )

    def _pick(self, agent: str | None, *, fallback: bool = False) -> _Provider:
        if fallback and agent and agent in self._fallbacks:
            return self._fallbacks[agent]
        if agent and agent in self._providers:
            return self._providers[agent]
        return self._providers["default"]

    def pick_fallback(self, agent: str | None) -> "_Provider | None":
        if not agent:
            return None
        return self._fallbacks.get(agent)

    @staticmethod
    def _inline_system(messages: list[dict]) -> list[dict]:
        """Fold system messages into the first user message for providers that
        reject `role: system` (e.g. Gemma via Gemini OpenAI-compat)."""
        sys_chunks = [
            str(m.get("content", "")) for m in messages if m.get("role") == "system"
        ]
        if not sys_chunks:
            return messages
        prefix = "\n\n".join(c for c in sys_chunks if c)
        out: list[dict] = []
        prefixed = False
        for m in messages:
            if m.get("role") == "system":
                continue
            if not prefixed and m.get("role") == "user":
                out.append({**m, "content": f"{prefix}\n\n{m.get('content', '')}"})
                prefixed = True
            else:
                out.append(m)
        if not prefixed:
            out.insert(0, {"role": "user", "content": prefix})
        return out

    @staticmethod
    def _effective_think(think: bool) -> bool:
        override = _THINK_OVERRIDE.get()
        return think if override is None else override

    @staticmethod
    def _toggle(provider: _Provider):
        return gemini if provider.toggle_style == "gemini" else llama_cpp

    def _params(
        self,
        provider: _Provider,
        messages: list[dict],
        think: bool,
        temperature: float | None,
    ) -> dict:
        if not provider.supports_system:
            messages = self._inline_system(messages)
        params: dict = {"model": provider.model, "messages": messages}
        if temperature is not None:
            params["temperature"] = temperature
        extra = self._toggle(provider).extra_body(
            provider.thinking_mode, self._effective_think(think)
        )
        if extra is not None:
            params["extra_body"] = extra
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
        temperature: float | None = None,
        use_fallback: bool = False,
    ) -> dict:
        provider = self._pick(agent, fallback=use_fallback)
        base = self._log_basename(agent) if log else None
        self._log_query(base, messages)
        params = self._params(provider, messages, think, temperature)
        response = await provider.next_chat_client().chat.completions.create(**params)
        msg = response.choices[0].message
        extra = msg.model_extra or {}
        thought = extra.get("reasoning_content")
        answer = msg.content or ""
        sp = self._toggle(provider).make_splitter(
            provider.thinking_mode, self._effective_think(think)
        )
        if sp is not None:
            t1, a1 = sp.feed(answer)
            t2, a2 = sp.flush()
            inline_think = t1 + t2
            answer = a1 + a2
            if inline_think:
                thought = (thought or "") + inline_think
        result = {"think": thought, "answer": answer}
        self._log_answer(base, answer)
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        think: bool = True,
        agent: str | None = None,
        log: bool = True,
        temperature: float | None = None,
        use_fallback: bool = False,
    ) -> AsyncIterator[dict]:
        provider = self._pick(agent, fallback=use_fallback)
        base = self._log_basename(agent) if log else None
        self._log_query(base, messages)
        params = self._params(provider, messages, think, temperature)
        stream = await provider.next_stream_client().chat.completions.create(
            **params, stream=True
        )
        splitter = self._toggle(provider).make_splitter(
            provider.thinking_mode, self._effective_think(think)
        )
        accum_answer: list[str] = []
        try:
            async for chunk in stream:
                delta = chunk.choices[0].delta
                extra = delta.model_extra or {}
                thought = extra.get("reasoning_content")
                answer = delta.content or ""
                if splitter:
                    sp_think, answer = splitter.feed(answer)
                    if sp_think:
                        thought = (thought or "") + sp_think
                if answer:
                    accum_answer.append(answer)
                yield {"think": thought, "answer": answer or None}
            if splitter:
                sp_think, sp_answer = splitter.flush()
                if sp_answer:
                    accum_answer.append(sp_answer)
                if sp_think or sp_answer:
                    yield {"think": sp_think or None, "answer": sp_answer or None}
        finally:
            self._log_answer(base, "".join(accum_answer))
