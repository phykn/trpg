import json
import os
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from src.db.repo import GraphRepo
from src.game.domain.memory import DialoguePair, GMLogEntry, NarrationCue, TurnLogEntry
from src.llm.diag import llm_diag

from ..env import env_nonnegative_int
from ..state import GameRuntimeState
from .suggestions import GraphSuggestion, normalize_suggestion


def _narration_meta_marker(default: str = "---TRPG_META---") -> str:
    return os.getenv("GRAPH_NARRATION_META_MARKER") or default


def _private_narration_markers() -> tuple[str, ...]:
    return ("<GM_PLAN>", "<RESULT_PLAN>", "<GM_DATA>", "<STATE_PATCH>")


def _visible_stop_markers() -> tuple[str, ...]:
    return (_narration_meta_marker(), *_private_narration_markers())


def _max_suggestions(default: int = 3) -> int:
    return env_nonnegative_int("GRAPH_NARRATION_MAX_SUGGESTIONS", default)


def _max_suggestion_chars(default: int = 80) -> int:
    return env_nonnegative_int("GRAPH_NARRATION_MAX_SUGGESTION_CHARS", default)


def _max_ui_cues(default: int = 3) -> int:
    return env_nonnegative_int("GRAPH_NARRATION_MAX_UI_CUES", default)


def _max_ui_cue_chars(default: int = 48) -> int:
    return env_nonnegative_int("GRAPH_NARRATION_MAX_UI_CUE_CHARS", default)


class GraphNarrationResult(BaseModel):
    narration: str = ""
    turn_summary: str = ""
    importance: int = Field(default=1, ge=1, le=3)
    suggestions: list[GraphSuggestion] = Field(default_factory=list)
    ui_cues: list[NarrationCue] = Field(default_factory=list)


class VisibleNarrationStream:
    def __init__(self) -> None:
        self._raw: list[str] = []
        self._pending = ""
        self._found_marker = False
        self._markers = _visible_stop_markers()
        self._keep_len = max(len(marker) for marker in self._markers) - 1

    def push(self, chunk: str) -> list[str]:
        self._raw.append(chunk)
        if self._found_marker:
            return []
        combined = f"{self._pending}{chunk}"
        marker_at = _first_marker_at(combined, self._markers)
        if marker_at >= 0:
            self._found_marker = True
            self._pending = ""
            visible = combined[:marker_at].rstrip("\r\n")
            return [visible] if visible else []

        keep = min(len(combined), self._keep_len)
        visible = combined[:-keep] if keep else combined
        self._pending = combined[-keep:] if keep else ""
        return [visible] if visible else []

    def finish(self) -> list[str]:
        if self._found_marker or not self._pending:
            return []
        visible = self._pending
        self._pending = ""
        return [visible]

    def answer(self) -> str:
        return "".join(self._raw)


def parse_graph_narration_answer(answer: str) -> GraphNarrationResult:
    marker = _narration_meta_marker()
    marker_at = answer.find(marker)
    visible_marker_at = _first_marker_at(answer, _visible_stop_markers())
    narration_end = visible_marker_at if visible_marker_at >= 0 else marker_at
    if marker_at < 0:
        llm_diag("llm:graph_narrate_meta_missing", answer_len=len(answer))
        if narration_end >= 0:
            return GraphNarrationResult(
                narration=_clean_narration(answer[:narration_end].rstrip("\r\n"))
            )
        return GraphNarrationResult(narration=_clean_narration(answer))

    narration = _clean_narration(answer[:narration_end].rstrip("\r\n"))
    meta_text = answer[marker_at + len(marker) :].strip()
    try:
        raw = json.loads(meta_text)
        suggestions = raw.pop("suggestions", [])
        ui_cues = raw.pop("ui_cues", [])
        parsed = GraphNarrationResult.model_validate(
            {
                "narration": narration,
                **raw,
                "suggestions": _clean_suggestions(suggestions),
                "ui_cues": _clean_ui_cues(ui_cues),
            }
        )
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        llm_diag(
            "llm:graph_narrate_meta_invalid",
            err=type(exc).__name__,
            meta_len=len(meta_text),
        )
        return GraphNarrationResult(narration=narration)
    return parsed


def _clean_narration(text: str) -> str:
    lines = [
        _normalize_ascii_direct_speech(
            _strip_trailing_ascii_quote_junk(line)
        )
        for line in text.splitlines()
        if line.strip() and not re.fullmatch(r'(?:「\s*」|"\s*")', line.strip())
    ]
    return "\n".join(lines).strip()


def _strip_trailing_ascii_quote_junk(line: str) -> str:
    return re.sub(r'(?:\\?["`]){2,}$', "", line.rstrip())


def _normalize_ascii_direct_speech(line: str) -> str:
    line = line.replace(r"\"", '"')
    if '"' not in line:
        return line.rstrip()
    out: list[str] = []
    in_quote = False
    for char in line:
        if char != '"':
            out.append(char)
            continue
        out.append("」" if in_quote else "「")
        in_quote = not in_quote
    if in_quote:
        out.append("」")
    return "".join(out).rstrip()


def _first_marker_at(text: str, markers: tuple[str, ...]) -> int:
    positions = [index for marker in markers if (index := text.find(marker)) >= 0]
    return min(positions) if positions else -1


def gm_log_entry_from_narration(
    log_id: int,
    result: GraphNarrationResult,
    *,
    outcome: Literal["success", "failure", "neutral"] | None = None,
) -> GMLogEntry:
    return GMLogEntry(
        id=log_id,
        kind="gm",
        text=result.narration,
        outcome=outcome,
        cues=result.ui_cues,
    )


async def persist_graph_narration_result(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    result: GraphNarrationResult,
    *,
    target: str | None = None,
    player_input: str | None = None,
) -> GameRuntimeState:
    history_entries = _history_entries(runtime, result, target)
    dialogue_entries = _dialogue_entries(
        runtime,
        result,
        player_input=player_input,
        target=target,
    )
    if history_entries:
        await repo.append_history_entries(runtime.progress.game_id, history_entries)
    if dialogue_entries:
        await repo.append_dialogue_entries(runtime.progress.game_id, dialogue_entries)
    if not history_entries and not dialogue_entries:
        return runtime
    return runtime.model_copy(
        update={
            "turn_log": [*runtime.turn_log, *history_entries],
            "recent_dialogue": [*runtime.recent_dialogue, *dialogue_entries],
        }
    )


def _history_entries(
    runtime: GameRuntimeState,
    result: GraphNarrationResult,
    target: str | None,
) -> list[TurnLogEntry]:
    summary = result.turn_summary.strip()
    if not summary:
        return []
    return [
        TurnLogEntry(
            turn=runtime.progress.turn_count,
            target=target,
            summary=summary,
            importance=result.importance,
        )
    ]


def _dialogue_entries(
    runtime: GameRuntimeState,
    result: GraphNarrationResult,
    *,
    player_input: str | None,
    target: str | None,
) -> list[DialoguePair]:
    if not player_input or not result.narration:
        return []
    return [
        DialoguePair(
            turn=runtime.progress.turn_count,
            player=player_input,
            narrator=result.narration,
            target=target,
        )
    ]


def _clean_suggestions(
    values: object,
) -> list[GraphSuggestion]:
    if not isinstance(values, list):
        return []
    out: list[GraphSuggestion] = []
    seen: set[str] = set()
    for value in values:
        suggestion = normalize_suggestion(value)
        if suggestion is None:
            continue
        key = suggestion.input_text
        if key in seen:
            continue
        seen.add(key)
        out.append(_truncate_suggestion(suggestion))
        if len(out) == _max_suggestions():
            break
    return out


def _truncate_suggestion(value: GraphSuggestion) -> GraphSuggestion:
    max_chars = _max_suggestion_chars()
    return GraphSuggestion(
        label=value.label[:32],
        input_text=value.input_text[:max_chars],
        intent=value.intent,
        action=value.action,
    )


def _clean_ui_cues(values: object) -> list[NarrationCue]:
    if not isinstance(values, list):
        return []
    max_cues = _max_ui_cues()
    if max_cues <= 0:
        return []
    out: list[NarrationCue] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        cue = _normalize_ui_cue(value)
        if cue is None:
            continue
        key = (cue.kind, cue.text)
        if key in seen:
            continue
        seen.add(key)
        out.append(cue)
        if len(out) == max_cues:
            break
    return out


def _normalize_ui_cue(value: object) -> NarrationCue | None:
    if not isinstance(value, dict):
        return None
    kind = value.get("kind")
    label = value.get("label")
    text = value.get("text")
    scope = value.get("scope", "delta")
    if not isinstance(kind, str) or not isinstance(label, str):
        return None
    if not isinstance(text, str) or not isinstance(scope, str):
        return None
    label = label.strip()[:12]
    text = text.strip()[: _max_ui_cue_chars()]
    if not label or not text:
        return None
    try:
        return NarrationCue(kind=kind, label=label, text=text, scope=scope)
    except ValidationError:
        return None


