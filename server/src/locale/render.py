"""Catalog-backed string render with variable substitution and 조사 token expansion.

Tokens recognized inside a template:
  - `{name}` — substitute from vars[name]; updates the "last variable" tracker
  - `{이/가}` `{은/는}` `{을/를}` `{과/와}` `{으로/로}` — particle picked from the
    last substituted variable's trailing 받침. Particles look back ONLY to the
    most recent {name}, not to plain text in between.
"""

import re
import tomllib
from pathlib import Path

from .particles import eu_ro, eul_reul, eun_neun, gwa_wa, i_ga

_CATALOG_DIR = Path(__file__).parent / "catalog"
_CACHE: dict[str, dict] = {}

_PARTICLES = {
    "이/가": i_ga,
    "은/는": eun_neun,
    "을/를": eul_reul,
    "과/와": gwa_wa,
    "으로/로": eu_ro,
}

_TOKEN = re.compile(r"\{([^}]+)\}")


def _load(name: str) -> dict:
    if name not in _CACHE:
        with (_CATALOG_DIR / f"{name}.toml").open("rb") as f:
            _CACHE[name] = tomllib.load(f)
    return _CACHE[name]


def render(key: str, locale: str, **vars: object) -> str:
    domain, _, name = key.partition(".")
    if not name:
        raise KeyError(f"render key must be 'domain.name', got {key!r}")
    template = _load(domain)[domain][name][locale]
    out: list[str] = []
    last_var = ""
    pos = 0
    for m in _TOKEN.finditer(template):
        out.append(template[pos : m.start()])
        token = m.group(1)
        particle = _PARTICLES.get(token)
        if particle is not None:
            out.append(particle(last_var))
        else:
            value = str(vars[token])
            out.append(value)
            last_var = value
        pos = m.end()
    out.append(template[pos:])
    return "".join(out)
