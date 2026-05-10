from __future__ import annotations

from pathlib import Path
import re


SERVER_SRC = Path(__file__).resolve().parents[3] / "src"
LEGACY_TOKENS = ("StatKey", "STR", "DEX", "CON", "INT", "WIS", "CHA")
LEGACY_PATTERN = re.compile(r"\b(" + "|".join(LEGACY_TOKENS) + r")\b")


def test_server_source_has_no_legacy_entity_model_references() -> None:
    offenders: list[str] = []
    for path in SERVER_SRC.rglob("*.py"):
        rel = path.relative_to(SERVER_SRC)
        if "__pycache__" in rel.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "game.domain.entities" in text or "game.engines.invariants" in text:
            offenders.append(str(rel))
            continue
        if LEGACY_PATTERN.search(text):
            offenders.append(str(rel))

    assert offenders == []
