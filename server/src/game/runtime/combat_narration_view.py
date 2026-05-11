from typing import Any

from src.game.domain.combat import GraphCombatTraceEvent
from src.game.domain.content import node_label

from .state import GameRuntimeState


COMBAT_CONDITION_LABELS = {
    "healthy": "버티고 있음",
    "hurt": "흔들림",
    "critical": "위태로움",
    "downed": "쓰러짐",
}

COMBAT_MOTION_LABELS = {
    "combat_started": "교전이 시작됨",
    "player_attacked": "공격을 시도함",
    "player_cast": "기술을 사용함",
    "player_defended": "방어 자세를 취함",
    "player_fled": "거리를 벌림",
    "enemy_pressed": "압박함",
    "enemy_defeated": "상대가 쓰러짐",
    "player_downed": "플레이어가 쓰러짐",
    "forced_end": "교전이 멈춤",
}

COMBAT_ACTION_LABELS = {
    "attack": "공격",
    "cast": "기술",
    "defend": "방어",
    "flee": "이탈",
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
        "player_action": _action_label(state.last_action if state is not None else None),
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
        "motion": COMBAT_MOTION_LABELS.get(event.kind, "상황이 바뀜"),
        "target_condition": _condition_label(event.state),
    }


def _node_ref(runtime: GameRuntimeState, node_id: str | None) -> dict[str, str] | None:
    node = runtime.graph.nodes.get(node_id or "")
    if node is None:
        return None
    return {"id": node.id, "name": node_label(runtime.content, node)}


def _condition_label(value: str | None) -> str | None:
    if value is None:
        return None
    return COMBAT_CONDITION_LABELS.get(value, "상태가 바뀜")


def _action_label(value: str | None) -> str | None:
    if value is None:
        return None
    return COMBAT_ACTION_LABELS.get(value, "행동")


def _combat_tone(runtime: GameRuntimeState) -> dict[str, str]:
    state = runtime.progress.graph_combat_state
    participant_ids = state.participant_ids if state is not None else []
    for participant_id in participant_ids:
        node = runtime.graph.nodes.get(participant_id)
        if node is None:
            continue
        if _has_nonlethal_marker(node.properties):
            return {"lethality": "nonlethal", "style": "training"}
    return {"lethality": "dangerous", "style": "adventure"}


def _has_nonlethal_marker(properties: dict[str, Any]) -> bool:
    markers = {
        "training",
        "sparring",
        "tutorial",
        "practice",
        "nonlethal",
        "non-lethal",
    }
    korean_markers = {"훈련", "대련", "연습", "허수아비"}
    for key, value in properties.items():
        lowered_key = key.lower()
        if lowered_key in markers and value:
            return True
        if isinstance(value, str) and value.lower() in markers:
            return True
        if isinstance(value, str) and any(marker in value for marker in korean_markers):
            return True
        if isinstance(value, list) and any(
            isinstance(item, str)
            and (item.lower() in markers or any(marker in item for marker in korean_markers))
            for item in value
        ):
            return True
    return False
