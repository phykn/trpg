import os
import re
from dataclasses import dataclass
from typing import Literal, NamedTuple


# off / on: forced; opt / opt_on: per-call `think` flag with that default.
ThinkingMode = Literal["off", "opt", "opt_on", "on"]


@dataclass(frozen=True)
class LLMProfile:
    base_url: str
    model: str
    api_keys: tuple[str, ...]
    thinking_mode: ThinkingMode
    supports_system: bool


class _ProviderEnv(NamedTuple):
    base_url: str
    api_keys: tuple[str, ...]
    modes: dict[str, ThinkingMode]
    no_system: frozenset[str]


_PROVIDER_RE = re.compile(
    r"^LLM_(?!ROUTE_)([A-Z0-9_]+?)_(BASE_URL|API_KEYS|THINK_OFF|THINK_OPT_ON|THINK_OPT|THINK_ON|NO_SYSTEM)$"
)
_ROUTE_RE = re.compile(r"^LLM_ROUTE_([A-Z0-9_]+)$")
_FALLBACK_RE = re.compile(r"^LLM_ROUTE_([A-Z0-9_]+)_FALLBACK$")


def parse_env_profiles() -> tuple[dict[str, LLMProfile], dict[str, LLMProfile]]:
    def csv(s: str) -> tuple[str, ...]:
        return tuple(p.strip() for p in s.split(",") if p.strip())

    def parse_spec(key: str, value: str) -> tuple[str, str]:
        spec = value.strip()
        if "/" not in spec:
            raise ValueError(f"{key} must be '<provider>/<model>' (got {value!r})")
        prov, model = spec.split("/", 1)
        return prov.strip(), model.strip()

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

    providers = _collect_providers(csv, collect_modes)
    routes, fallback_routes = _collect_routes(parse_spec)
    if "default" not in routes:
        raise ValueError("LLM_ROUTE_DEFAULT must be set")

    profiles = {
        agent: _resolve_profile(f"LLM_ROUTE_{agent.upper()}", providers, spec)
        for agent, spec in routes.items()
    }
    fallbacks = {
        agent: _resolve_profile(f"LLM_ROUTE_{agent.upper()}_FALLBACK", providers, spec)
        for agent, spec in fallback_routes.items()
    }
    return profiles, fallbacks


def _collect_providers(csv, collect_modes) -> dict[str, _ProviderEnv]:
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
    return providers


def _collect_routes(
    parse_spec,
) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]]]:
    routes: dict[str, tuple[str, str]] = {}
    fallback_routes: dict[str, tuple[str, str]] = {}
    for key, value in os.environ.items():
        m_fb = _FALLBACK_RE.match(key)
        if m_fb:
            fallback_routes[m_fb[1].lower()] = parse_spec(key, value)
            continue
        m = _ROUTE_RE.match(key)
        if m:
            routes[m[1].lower()] = parse_spec(key, value)
    return routes, fallback_routes


def _resolve_profile(
    label: str,
    providers: dict[str, _ProviderEnv],
    spec: tuple[str, str],
) -> LLMProfile:
    prov_name, model_name = spec
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
