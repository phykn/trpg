"""enum 값 ↔ catalog .toml 키 정합 검사. 새 enum 값을 추가했는데 catalog 빠뜨리거나 그 반대를 잡는다."""

import tomllib
from pathlib import Path

from typing import get_args

from src.game.domain.types import EncounterRisk, GraphStatKey, Tier


CATALOG = Path(__file__).resolve().parents[2] / "src" / "locale" / "catalog"
REQUIRED_LOCALES = {"ko", "en"}


def _keys(toml_name: str, domain: str) -> set[str]:
    data = tomllib.loads((CATALOG / toml_name).read_text(encoding="utf-8"))
    return set(data.get(domain, {}).keys())


def test_every_catalog_entry_has_required_locales() -> None:
    missing: list[str] = []
    for path in sorted(CATALOG.glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for domain, entries in data.items():
            for key, locales in entries.items():
                missing_locales = REQUIRED_LOCALES - set(locales)
                if missing_locales:
                    missing.append(
                        f"{path.name}:{domain}.{key}:{','.join(sorted(missing_locales))}"
                    )

    assert missing == []


def test_tier_catalog_covers_enum() -> None:
    expected = set(get_args(Tier))
    assert _keys("tier.toml", "tier") == expected


def test_stat_catalog_covers_enum() -> None:
    expected = set(get_args(GraphStatKey))
    assert _keys("stat.toml", "stat") == expected


def test_risk_catalog_covers_enum() -> None:
    """ui.toml의 risk.<value>.label 키 set이 EncounterRisk와 정합."""
    import tomllib as _tl

    data = _tl.loads((CATALOG / "ui.toml").read_text(encoding="utf-8"))
    risk_values = {
        k.split(".")[1]
        for k in data["ui"].keys()
        if k.startswith("risk.") and k.endswith(".label")
    }
    assert risk_values == set(get_args(EncounterRisk))
