"""Locale rendering for narration brief lines."""

from src.locale.render import render

_LOCALE = "ko"


def brief(key: str, **vars: object) -> str:
    return render(f"runtime.narration.brief.{key}", _LOCALE, **vars)
