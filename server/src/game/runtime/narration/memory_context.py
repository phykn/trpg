from typing import Any

from src.game.domain.memory import ExchangePair

from ..env import env_nonnegative_int
from ..state import GameRuntimeState


def important_history_payload(
    runtime: GameRuntimeState,
    *,
    limit: int = 20,
) -> list[dict]:
    ranked = sorted(
        enumerate(runtime.turn_log),
        key=lambda item: (item[1].importance, item[1].turn, item[0]),
        reverse=True,
    )
    selected = sorted(ranked[:limit], key=lambda item: (item[1].turn, item[0]))
    return [entry.model_dump(mode="json") for _, entry in selected]


def recent_exchanges_payload(
    runtime: GameRuntimeState,
    *,
    limit: int = 5,
) -> list[dict]:
    return [entry.model_dump(mode="json") for entry in runtime.recent_exchanges[-limit:]]


def classify_recent_exchanges_payload(
    runtime: GameRuntimeState,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    limit = env_nonnegative_int("MAX_RECENT_EXCHANGES", 3) if limit is None else limit
    return [
        {"turn": entry.turn, "player": entry.player, "summary": entry.narrator}
        for entry in runtime.recent_exchanges[-limit:]
    ]


def narrate_recent_exchanges_payload(
    runtime: GameRuntimeState,
    *,
    target: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    limit = env_nonnegative_int("MAX_RECENT_EXCHANGES", 3) if limit is None else limit
    entries = _target_first_exchanges(runtime, target, limit)
    return [
        _drop_none_and_empty(
            {
                "turn": entry.turn,
                "player": entry.player,
                "narrator": entry.narrator,
                "target": entry.target,
                "cues": [cue.model_dump(mode="json") for cue in entry.cues],
            }
        )
        for entry in entries
    ]


def previous_scene_payload(
    runtime: GameRuntimeState,
    *,
    limit: int | None = None,
    recent_exchange_limit: int | None = None,
) -> list[dict[str, Any]]:
    limit = env_nonnegative_int("MAX_PREVIOUS_SCENE", 3) if limit is None else limit
    recent_exchange_limit = (
        env_nonnegative_int("MAX_RECENT_EXCHANGES", 3)
        if recent_exchange_limit is None
        else recent_exchange_limit
    )
    recent_turns = {
        entry.turn for entry in runtime.recent_exchanges[-recent_exchange_limit:]
    }
    entries = [
        entry
        for entry in runtime.turn_log
        if entry.summary and entry.turn not in recent_turns
    ][-limit:]
    return [
        _drop_none_and_empty(
            {
                "turn": entry.turn,
                "target": entry.target,
                "summary": entry.summary,
                "importance": entry.importance if entry.importance != 1 else None,
            }
        )
        for entry in entries
    ]


def _drop_none_and_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item is not None and item != [] and item != {}
    }


def _target_first_exchanges(
    runtime: GameRuntimeState,
    target: str | None,
    limit: int,
) -> list[ExchangePair]:
    if target is None:
        return runtime.recent_exchanges[-limit:]
    recent = list(runtime.recent_exchanges)
    targeted = [entry for entry in recent if entry.target == target]
    selected = targeted[-limit:]
    if len(selected) < limit:
        seen = {(entry.turn, entry.player, entry.narrator) for entry in selected}
        for entry in reversed(recent):
            key = (entry.turn, entry.player, entry.narrator)
            if key in seen:
                continue
            selected.append(entry)
            seen.add(key)
            if len(selected) == limit:
                break
    return sorted(selected[-limit:], key=lambda entry: entry.turn)

