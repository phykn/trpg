from typing import Any

from src.game.domain.action import Action
from src.game.domain.graph import GraphNode
from src.game.domain.graph.query import location_of
from src.game.domain.memory import DialoguePair

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


def recent_dialogue_payload(
    runtime: GameRuntimeState,
    *,
    limit: int = 5,
) -> list[dict]:
    return [entry.model_dump(mode="json") for entry in runtime.recent_dialogue[-limit:]]


def classify_recent_dialogue_payload(
    runtime: GameRuntimeState,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    limit = env_nonnegative_int("MAX_RECENT_DIALOGUE", 5) if limit is None else limit
    return [
        {"turn": entry.turn, "player": entry.player, "summary": entry.narrator}
        for entry in runtime.recent_dialogue[-limit:]
    ]


def narrate_recent_dialogue_payload(
    runtime: GameRuntimeState,
    *,
    target: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    limit = env_nonnegative_int("MAX_RECENT_DIALOGUE", 5) if limit is None else limit
    entries = _target_first_dialogue(runtime, target, limit)
    return [
        {
            "turn": entry.turn,
            "player": entry.player,
            "narrator": entry.narrator,
            "target": entry.target,
        }
        for entry in entries
    ]


def _target_first_dialogue(
    runtime: GameRuntimeState,
    target: str | None,
    limit: int,
) -> list[DialoguePair]:
    if target is None:
        return runtime.recent_dialogue[-limit:]
    recent = list(runtime.recent_dialogue)
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


def related_memory_payload(
    runtime: GameRuntimeState,
    *,
    action: Action | None,
    target: GraphNode | None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    limit = (
        env_nonnegative_int("MAX_NARRATE_RELATED_MEMORY", 15)
        if limit is None
        else limit
    )
    related_ids = _related_ids(runtime, action=action, target=target)
    ranked = sorted(
        runtime.turn_log,
        key=lambda entry: (
            0 if entry.target in related_ids else 1,
            -entry.importance,
            -entry.turn,
        ),
    )
    return [
        {
            "turn": entry.turn,
            "target": entry.target,
            "summary": entry.summary,
            "importance": entry.importance,
        }
        for entry in ranked
        if entry.target in related_ids
    ][:limit]


def _related_ids(
    runtime: GameRuntimeState,
    *,
    action: Action | None,
    target: GraphNode | None,
) -> set[str | None]:
    ids: set[str | None] = {
        location_of(runtime.graph_index, runtime.progress.player_id),
        runtime.progress.active_subject_id,
        runtime.progress.active_quest_id,
    }
    if target is not None:
        ids.add(target.id)
    if action is not None:
        for value in (
            action.what,
            action.from_,
            action.to,
            action.with_,
        ):
            if isinstance(value, str):
                ids.add(value)
            elif isinstance(value, list):
                ids.update(item for item in value if isinstance(item, str))
    combat = runtime.progress.graph_combat_state
    if combat is not None:
        ids.update(combat.participant_ids)
        ids.update(combat.enemy_ids)
        ids.add(combat.location_id)
    return ids


