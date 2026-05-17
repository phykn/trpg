from typing import Any

from src.game.domain.combat import GraphCombatTraceEvent
from src.game.domain.content import node_label
from src.game.domain.graph import GraphNode
from src.locale.terms import nonlethal_markers
from src.locale.render import render

from ..state import GameRuntimeState


COMBAT_CONDITION_KEYS = {"healthy", "hurt", "critical"}
COMBAT_MOTION_KEYS = {
    "combat_started",
    "player_attacked",
    "player_defended",
    "player_fled",
    "player_precise_success",
    "player_precise_failure",
    "player_guarded_success",
    "player_guarded_failure",
    "player_reckless_success",
    "player_reckless_failure",
    "player_create_distance_success",
    "player_create_distance_failure",
    "player_talk_success",
    "player_talk_failure",
    "enemy_pressed",
    "enemy_defeated",
    "player_defeated",
    "forced_end",
    "combat_stopped",
}
COMBAT_ACTION_KEYS = {
    "attack",
    "defend",
    "flee",
    "precise",
    "guarded",
    "reckless",
    "create_distance",
    "talk",
}


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
        "exchange_result": _exchange_result(events),
        "exchange_result_label": _exchange_result_label(
            runtime.progress.locale,
            _exchange_result(events),
        ),
        "escape_ready": state.escape_ready if state is not None else False,
        "enemy_pressure": state.enemy_pressure if state is not None else 0,
        "outcome": outcome or (state.outcome if state is not None else None),
        "events": [_event_view(runtime, event) for event in events],
        "support_effect": _support_effect_view(runtime),
        "statuses": _status_views(runtime),
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
        "result": _event_result(event.kind),
        "result_label": _exchange_result_label(
            runtime.progress.locale,
            _event_result(event.kind),
        ),
        "target_condition": _condition_label(runtime.progress.locale, event.state),
    }


def _support_effect_view(runtime: GameRuntimeState) -> dict[str, Any] | None:
    state = runtime.progress.graph_combat_state
    if state is None or state.last_support_id is None:
        return None
    support = runtime.graph.nodes.get(state.last_support_id)
    if support is None:
        return None
    effect_id = support.properties.get("effect_template")
    if not isinstance(effect_id, str) or not effect_id:
        return None
    effect = runtime.graph.nodes.get(effect_id)
    if effect is None or effect.type != "support_effect":
        return None
    payload: dict[str, Any] = {
        "id": effect.id,
        "name": node_label(runtime.content, effect),
    }
    record = runtime.content.support_effects.get(effect.id, {})
    description = record.get("description")
    if isinstance(description, str) and description:
        payload["description"] = description
    traits = record.get("traits")
    if isinstance(traits, list):
        payload["traits"] = [item for item in traits if isinstance(item, str) and item]
    return payload


def _status_views(runtime: GameRuntimeState) -> list[dict[str, Any]]:
    state = runtime.progress.graph_combat_state
    if state is None or state.last_support_id is None:
        return []
    support = runtime.graph.nodes.get(state.last_support_id)
    if support is None:
        return []
    statuses: list[dict[str, Any]] = []
    for status_id in _str_list(support.properties.get("status_ids")):
        status = runtime.graph.nodes.get(status_id)
        if status is None or status.type != "status":
            continue
        statuses.append(_status_view(runtime, status))
    return statuses


def _status_view(runtime: GameRuntimeState, status: GraphNode) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": status.id,
        "name": node_label(runtime.content, status),
    }
    record = runtime.content.statuses.get(status.id, {})
    description = record.get("description")
    if isinstance(description, str) and description:
        payload["description"] = description
    traits = record.get("traits")
    if isinstance(traits, list):
        payload["traits"] = [item for item in traits if isinstance(item, str) and item]
    return payload


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _exchange_result(events: list[GraphCombatTraceEvent]) -> str:
    for event in reversed(events):
        result = _event_result(event.kind)
        if result != "neutral":
            return result
    return "neutral"


def _event_result(kind: str) -> str:
    if kind.endswith("_success") or kind in {"enemy_defeated", "combat_stopped"}:
        return "success"
    if kind.endswith("_failure") or kind == "player_defeated":
        return "failure"
    return "neutral"


def _exchange_result_label(locale: str, result: str) -> str:
    key = result if result in {"success", "failure"} else "neutral"
    return render(f"runtime.combat.exchange_result.{key}", locale)


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
