from typing import Any

from src.game.domain.combat import GraphCombatTraceEvent
from src.game.domain.content import node_label
from src.locale.terms import downed_markers, nonlethal_markers
from src.locale.render import render

from .state import GameRuntimeState


COMBAT_CONDITION_KEYS = {"healthy", "hurt", "critical", "downed"}
COMBAT_MOTION_KEYS = {
    "combat_started",
    "player_attacked",
    "player_cast",
    "player_defended",
    "player_fled",
    "enemy_pressed",
    "enemy_defeated",
    "player_downed",
    "forced_end",
}
COMBAT_ACTION_KEYS = {"attack", "cast", "defend", "flee"}


def combat_narration_view(
    runtime: GameRuntimeState,
    *,
    trace: list[GraphCombatTraceEvent] | None = None,
    outcome: str | None = None,
) -> dict[str, Any] | None:
    state = runtime.progress.graph_combat_state
    events = trace if trace is not None else (state.trace if state is not None else [])
    if not events:
        return None
    return {
        "kind": "combat_exchange",
        "round": state.round if state is not None else None,
        "player_can_act": _player_can_act(runtime),
        "player_action": _action_label(
            runtime.progress.locale,
            state.last_action if state is not None else None,
        ),
        "outcome": outcome or (state.outcome if state is not None else None),
        "events": [_event_view(runtime, event) for event in events],
        "tone": _combat_tone(runtime),
    }


def _event_view(
    runtime: GameRuntimeState,
    event: GraphCombatTraceEvent,
) -> dict[str, Any]:
    return {
        "actor": _node_ref(runtime, event.actor_id),
        "target": _node_ref(runtime, event.target_id),
        "motion": _motion_label(runtime.progress.locale, event.kind),
        "target_condition": _condition_label(runtime.progress.locale, event.state),
    }


def _node_ref(runtime: GameRuntimeState, node_id: str | None) -> dict[str, str] | None:
    node = runtime.graph.nodes.get(node_id or "")
    if node is None:
        return None
    return {"id": node.id, "name": node_label(runtime.content, node)}


def _condition_label(locale: str, value: str | None) -> str | None:
    if value is None:
        return None
    key = value if value in COMBAT_CONDITION_KEYS else "changed"
    return render(f"runtime.combat.condition.{key}", locale)


def _motion_label(locale: str, value: str) -> str:
    key = value if value in COMBAT_MOTION_KEYS else "changed"
    return render(f"runtime.combat.motion.{key}", locale)


def _action_label(locale: str, value: str | None) -> str | None:
    if value is None:
        return None
    key = value if value in COMBAT_ACTION_KEYS else "generic"
    return render(f"runtime.combat.action.{key}", locale)


def _combat_tone(runtime: GameRuntimeState) -> dict[str, str]:
    state = runtime.progress.graph_combat_state
    participant_ids = state.participant_ids if state is not None else []
    for participant_id in participant_ids:
        node = runtime.graph.nodes.get(participant_id)
        if node is None:
            continue
        if _has_nonlethal_marker(node.properties, runtime.progress.locale):
            return {"lethality": "nonlethal", "style": "training"}
    return {"lethality": "dangerous", "style": "adventure"}


def _player_can_act(runtime: GameRuntimeState) -> bool:
    player = runtime.graph.nodes.get(runtime.progress.player_id)
    if player is None:
        return False
    if player.properties.get("alive") is False:
        return False
    hp = player.properties.get("hp")
    if isinstance(hp, int | float) and hp <= 0:
        return False
    status = player.properties.get("status")
    markers = downed_markers(runtime.progress.locale)
    if isinstance(status, list) and any(
        isinstance(item, str) and item.lower() in markers
        for item in status
    ):
        return False
    return True


def _has_nonlethal_marker(properties: dict[str, Any], locale: str) -> bool:
    markers = nonlethal_markers(locale)
    lower_markers = {marker.lower() for marker in markers}
    for key, value in properties.items():
        lowered_key = key.lower()
        if lowered_key in lower_markers and value:
            return True
        if isinstance(value, str) and value.lower() in lower_markers:
            return True
        if isinstance(value, str) and any(marker in value for marker in markers):
            return True
        if isinstance(value, list) and any(
            isinstance(item, str)
            and (
                item.lower() in lower_markers
                or any(marker in item for marker in markers)
            )
            for item in value
        ):
            return True
    return False
