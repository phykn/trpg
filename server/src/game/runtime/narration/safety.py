import re

from src.game.domain.action import Action
from src.game.domain.content import node_label
from src.locale.render import render

from ..state import GameRuntimeState
from .result import GraphNarrationResult


def guard_speak_narration_player_quote(
    runtime: GameRuntimeState,
    action: Action,
    subject_id: str | None,
    result: GraphNarrationResult,
    player_input: str | None,
) -> GraphNarrationResult:
    if action.verb != "speak" or subject_id is None or not result.narration:
        return result
    subject = runtime.graph.nodes.get(subject_id)
    if subject is None:
        return result
    target_name = node_label(runtime.content, subject)
    replacement = render(
        "runtime.input.speak_generic",
        runtime.progress.locale,
        target=target_name,
    )
    lines: list[str] = []
    inserted_replacement = False
    changed = False
    for line in result.narration.splitlines():
        if _line_invents_player_direct_speech(line, target_name, player_input or ""):
            if not inserted_replacement:
                lines.append(replacement)
                inserted_replacement = True
            changed = True
            continue
        lines.append(line)
    if not changed:
        return result
    return result.model_copy(update={"narration": "\n".join(lines).strip()})


def _line_invents_player_direct_speech(
    line: str,
    target_name: str,
    player_input: str,
) -> bool:
    to_particle = f"(?:{_text(0xC5D0, 0xAC8C)}|{_text(0xD55C, 0xD14C)})"
    quote_marker = _text(0xB77C, 0xACE0)
    player_subject = _text(0xB2F9, 0xC2E0, 0xC740)
    open_quote = chr(0x300C)
    close_quote = chr(0x300D)
    quoted = rf"{open_quote}([^{close_quote}]+){close_quote}\s*{quote_marker}"
    patterns = (
        rf"{re.escape(target_name)}{to_particle}\s*{quoted}",
        rf"[^{open_quote}\n]{{1,80}}{to_particle}\s*{quoted}",
        rf"{player_subject}\s*{quoted}",
    )
    quoted_parts = [
        next(group for group in match.groups() if group is not None)
        for pattern in patterns
        for match in re.finditer(pattern, line)
    ]
    return any(
        _normalize_speech_text(quote)
        and _normalize_speech_text(quote) not in _normalize_speech_text(player_input)
        for quote in quoted_parts
    )


def _normalize_speech_text(text: str) -> str:
    hangul_range = f"{chr(0xAC00)}-{chr(0xD7A3)}"
    return re.sub(rf"[^0-9A-Za-z{hangul_range}]+", "", text).lower()


def _text(*codepoints: int) -> str:
    return "".join(chr(codepoint) for codepoint in codepoints)
