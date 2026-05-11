from pathlib import Path
import re


SERVER_SRC = Path(__file__).resolve().parents[2] / "src"


def _source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if "locale" in path.relative_to(root).parts:
            continue
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


def test_server_source_keeps_korean_text_in_locale_package() -> None:
    offenders = [
        str(path.relative_to(SERVER_SRC))
        for path in _source_files(SERVER_SRC)
        if _contains_korean_text(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_combat_nonlethal_markers_live_in_locale_package() -> None:
    source = (
        SERVER_SRC / "game" / "runtime" / "combat_narration_view.py"
    ).read_text(encoding="utf-8")

    assert re.search(r"(?m)^\s*markers\s*=\s*\{", source) is None
    assert "KOREAN_NONLETHAL_MARKERS" not in source


def _contains_korean_text(source: str) -> bool:
    return _contains_literal_hangul(source) or _contains_escaped_hangul(source)


def _contains_literal_hangul(source: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in source)


def _contains_escaped_hangul(source: str) -> bool:
    for match in re.finditer(r"\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})", source):
        raw = match.group(1) or match.group(2)
        codepoint = int(raw, 16)
        if 0xAC00 <= codepoint <= 0xD7A3:
            return True
    return False
