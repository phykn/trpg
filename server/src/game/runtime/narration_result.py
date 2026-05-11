import json

from pydantic import BaseModel, Field, ValidationError

from src.db.repo import GraphRepo
from src.game.domain.memory import DialoguePair, TurnLogEntry

from .state import GameRuntimeState
from .suggestions import GraphSuggestion, GraphSuggestionValue, normalize_suggestion


NARRATION_META_MARKER = "---TRPG_META---"
_MAX_SUGGESTIONS = 3
_MAX_SUGGESTION_CHARS = 80


class GraphNarrationResult(BaseModel):
    narration: str = ""
    turn_summary: str = ""
    importance: int = Field(default=1, ge=1, le=3)
    suggestions: list[GraphSuggestionValue] = Field(default_factory=list)


class VisibleNarrationStream:
    def __init__(self) -> None:
        self._raw: list[str] = []
        self._pending = ""
        self._found_marker = False

    def push(self, chunk: str) -> list[str]:
        self._raw.append(chunk)
        if self._found_marker:
            return []
        combined = f"{self._pending}{chunk}"
        marker_at = combined.find(NARRATION_META_MARKER)
        if marker_at >= 0:
            self._found_marker = True
            self._pending = ""
            visible = combined[:marker_at].rstrip("\r\n")
            return [visible] if visible else []

        keep = min(len(combined), len(NARRATION_META_MARKER) - 1)
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
    marker_at = answer.find(NARRATION_META_MARKER)
    if marker_at < 0:
        return GraphNarrationResult(narration=answer)

    narration = answer[:marker_at].rstrip("\r\n")
    meta_text = answer[marker_at + len(NARRATION_META_MARKER) :].strip()
    try:
        raw = json.loads(meta_text)
        parsed = GraphNarrationResult.model_validate(
            {"narration": narration, **raw}
        )
    except (json.JSONDecodeError, TypeError, ValidationError):
        return GraphNarrationResult(narration=narration)
    return parsed.model_copy(update={"suggestions": _clean_suggestions(parsed.suggestions)})


async def persist_graph_narration_result(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    result: GraphNarrationResult,
    *,
    target_id: str | None = None,
    player_input: str | None = None,
) -> GameRuntimeState:
    history_entries = _history_entries(runtime, result, target_id)
    dialogue_entries = _dialogue_entries(
        runtime,
        result,
        player_input=player_input,
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
    target_id: str | None,
) -> list[TurnLogEntry]:
    summary = result.turn_summary.strip()
    if not summary:
        return []
    return [
        TurnLogEntry(
            turn=runtime.progress.turn_count,
            target=target_id,
            summary=summary,
            importance=result.importance,
        )
    ]


def _dialogue_entries(
    runtime: GameRuntimeState,
    result: GraphNarrationResult,
    *,
    player_input: str | None,
) -> list[DialoguePair]:
    if not player_input or not result.narration:
        return []
    return [
        DialoguePair(
            turn=runtime.progress.turn_count,
            player=player_input,
            narrator=result.narration,
        )
    ]


def _clean_suggestions(
    values: list[GraphSuggestionValue],
) -> list[GraphSuggestionValue]:
    out: list[GraphSuggestionValue] = []
    seen: set[str] = set()
    for value in values:
        suggestion = normalize_suggestion(value)
        if suggestion is None:
            continue
        key = suggestion if isinstance(suggestion, str) else suggestion.input_text
        if key in seen:
            continue
        seen.add(key)
        out.append(_truncate_suggestion(suggestion))
        if len(out) == _MAX_SUGGESTIONS:
            break
    return out


def _truncate_suggestion(value: GraphSuggestionValue) -> GraphSuggestionValue:
    if isinstance(value, str):
        return value[:_MAX_SUGGESTION_CHARS]
    return GraphSuggestion(
        label=value.label[:32],
        input_text=value.input_text[:_MAX_SUGGESTION_CHARS],
        intent=value.intent,
        action=value.action,
    )
