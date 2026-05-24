import re
import difflib

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
        if _line_has_unsafe_speech(line, target_name, player_input or ""):
            if not inserted_replacement:
                lines.append(replacement)
                inserted_replacement = True
            changed = True
            continue
        lines.append(line)
    if not changed:
        return result
    return result.model_copy(update={"narration": "\n".join(lines).strip()})


def _line_has_unsafe_speech(
    line: str,
    target_name: str,
    player_input: str,
) -> bool:
    return _line_invents_player_direct_speech(
        line,
        target_name,
        player_input,
    ) or any(
        _echoes_player_question(quote, player_input)
        for quote in _target_speech_parts(line, target_name)
    )


def _line_invents_player_direct_speech(
    line: str,
    target_name: str,
    player_input: str,
) -> bool:
    return any(
        _invents_player_direct_speech(quote, player_input)
        for quote in _quoted_speech_parts(line, target_name)
    )


def _quoted_speech_parts(line: str, target_name: str) -> list[str]:
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
    return [
        next(group for group in match.groups() if group is not None)
        for pattern in patterns
        for match in re.finditer(pattern, line)
    ]


def _target_speech_parts(line: str, target_name: str) -> list[str]:
    subject_particle = f"(?:{_text(0xC774, 0xAC00)}|{_text(0xAC00)}|{_text(0xC740, 0xB294)}|{_text(0xB294)})"
    quote_marker = _text(0xB77C, 0xACE0)
    open_quote = chr(0x300C)
    close_quote = chr(0x300D)
    quoted = rf"{open_quote}([^{close_quote}]+){close_quote}\s*{quote_marker}"
    pattern = rf"{re.escape(target_name)}{subject_particle}?\s*{quoted}"
    return [
        match.group(1)
        for match in re.finditer(pattern, line)
    ]


def _invents_player_direct_speech(quote: str, player_input: str) -> bool:
    normalized_quote = _normalize_speech_text(quote)
    return (
        bool(normalized_quote)
        and normalized_quote not in _normalize_speech_text(player_input)
    )


def _echoes_player_question(quote: str, player_input: str) -> bool:
    normalized_quote = _normalize_speech_text(quote)
    normalized_input = _normalize_speech_text(player_input)
    if len(normalized_quote) < 12 or len(normalized_input) < 12:
        return False
    if normalized_quote in normalized_input or normalized_input in normalized_quote:
        return True
    return difflib.SequenceMatcher(None, normalized_quote, normalized_input).ratio() >= 0.62


def _normalize_speech_text(text: str) -> str:
    hangul_range = f"{chr(0xAC00)}-{chr(0xD7A3)}"
    return re.sub(rf"[^0-9A-Za-z{hangul_range}]+", "", text).lower()


def _text(*codepoints: int) -> str:
    return "".join(chr(codepoint) for codepoint in codepoints)
