import tomllib
from pathlib import Path

_CATALOG_DIR = Path(__file__).parent / "catalog"
_CACHE: dict[str, dict] = {}


def _load(name: str) -> dict:
    if name not in _CACHE:
        with (_CATALOG_DIR / f"{name}.toml").open("rb") as f:
            _CACHE[name] = tomllib.load(f)
    return _CACHE[name]


def render(key: str, locale: str, **vars) -> str:
    """Look up 'domain.name' in catalog/<domain>.toml at [locale], format with vars."""
    domain, _, name = key.partition(".")
    if not name:
        raise KeyError(f"render key must be 'domain.name', got {key!r}")
    table = _load(domain)
    entry = table[domain][name]
    template = entry[locale]
    return template.format_map(vars) if vars else template
