"""enum 값 ↔ catalog .toml 키 정합 검사. 새 enum 값을 추가했는데 catalog 빠뜨리거나 그 반대를 잡는다."""
import tomllib
from pathlib import Path

from typing import get_args

from src.domain.types import EncounterRisk, Phase, StatKey, Tier


CATALOG = Path(__file__).resolve().parents[2] / "src" / "locale" / "catalog"


def _keys(toml_name: str, domain: str) -> set[str]:
    data = tomllib.loads((CATALOG / toml_name).read_text(encoding="utf-8"))
    return set(data.get(domain, {}).keys())


def test_tier_catalog_covers_enum() -> None:
    expected = set(get_args(Tier))
    assert _keys("tier.toml", "tier") == expected


def test_phase_catalog_covers_enum() -> None:
    expected = set(get_args(Phase))
    assert _keys("phase.toml", "phase") == expected


def test_stat_catalog_covers_enum() -> None:
    expected = set(get_args(StatKey))
    assert _keys("stat.toml", "stat") == expected


def test_encounter_risk_no_catalog_yet() -> None:
    """1.1 시점: EncounterRisk는 catalog 라벨 안 가짐 (RISK_PAYLOAD가 1.3에서 ui.toml로 흡수). 이 테스트는 1.3에서 _keys('ui.toml', 'risk') == get_args(EncounterRisk)로 갱신."""
    assert set(get_args(EncounterRisk)) == {"safe", "risky", "dangerous"}
