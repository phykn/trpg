from __future__ import annotations

from pathlib import Path


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
        if any("\uac00" <= char <= "\ud7a3" for char in path.read_text(encoding="utf-8"))
    ]

    assert offenders == []
