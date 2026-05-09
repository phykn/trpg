from __future__ import annotations

from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph_query import location_of
from src.game.domain.memory import ActLogEntry

from .dispatch import GraphActionDispatchResult
from .state import GameRuntimeState


def build_graph_action_card(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
) -> ActLogEntry:
    return ActLogEntry(
        id=after.progress.next_log_id,
        kind="act",
        text=_card_text(before, after, action, dispatch),
    )


def build_graph_quest_offer_card(
    runtime: GameRuntimeState,
    quest_id: str,
    log_id: int,
) -> ActLogEntry:
    quest = _quest_title(runtime.graph, quest_id)
    return ActLogEntry(
        id=log_id,
        kind="act",
        text=f"새 의뢰가 도착합니다: {quest}.",
    )


def _card_text(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
) -> str:
    if dispatch.kind == "move":
        destination_id = location_of(after.graph, after.progress.player_id)
        destination = _node_label(after.graph, destination_id, fallback="목적지")
        return f"당신은 {destination}{_direction_particle(destination)} 이동합니다."

    if dispatch.kind == "combat":
        return _combat_text(before, after, action)

    if dispatch.kind == "quest_accept":
        quest = _quest_title(after.graph, _single(action.what) or _single(action.to))
        return f"당신은 {quest} 퀘스트를 시작합니다."

    if dispatch.kind == "quest_abandon":
        quest = _quest_title(after.graph, _single(action.what) or _single(action.to))
        return f"당신은 {quest} 퀘스트를 포기합니다."

    if dispatch.kind == "rest":
        return "당신은 휴식을 취합니다."

    if dispatch.kind == "equip":
        item = _node_label(after.graph, _single(action.what) or _single(action.with_))
        return f"당신은 {item}을 장비합니다."

    if dispatch.kind == "unequip":
        item = _node_label(after.graph, _single(action.what) or _single(action.with_))
        return f"당신은 {item}을 해제합니다."

    if dispatch.kind == "use":
        item = _node_label(after.graph, _single(action.what) or _single(action.with_))
        return f"당신은 {item}을 사용합니다."

    if dispatch.kind == "transfer":
        item = _node_label(after.graph, _single(action.what) or _single(action.with_))
        return f"당신은 {item}을 옮깁니다."

    return "당신의 행동이 처리됩니다."


def _combat_text(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
) -> str:
    if before.progress.graph_combat_state is None:
        target_id = _single(action.what) or _single(action.to)
        target = _node_label(after.graph, target_id, fallback="대상")
        return f"당신은 {target}을 공격해 전투를 시작합니다."
    outcome = after.progress.graph_combat_state.outcome if after.progress.graph_combat_state else "victory"
    if outcome == "fled":
        return "당신은 전투에서 벗어납니다."
    if outcome == "defeat":
        return "당신은 전투에서 패배합니다."
    if outcome == "victory":
        return "당신은 전투에서 승리합니다."
    return "당신은 전투를 이어갑니다."


def _quest_title(graph: Graph, quest_id: str | None) -> str:
    node = graph.nodes.get(quest_id or "")
    if node is None or node.type != "quest":
        return "해당"
    title = node.properties.get("title")
    if isinstance(title, str) and title:
        return title
    return _label(node)


def _node_label(
    graph: Graph,
    node_id: str | None,
    *,
    fallback: str = "대상",
) -> str:
    node = graph.nodes.get(node_id or "")
    return _label(node) if node is not None else fallback


def _label(node: GraphNode) -> str:
    name = node.properties.get("name")
    if isinstance(name, str) and name:
        return name
    title = node.properties.get("title")
    if isinstance(title, str) and title:
        return title
    return node.id


def _direction_particle(value: str) -> str:
    if value == "":
        return "로"
    code = ord(value[-1])
    if code < 0xAC00 or code > 0xD7A3:
        return "로"
    final = (code - 0xAC00) % 28
    return "로" if final in (0, 8) else "으로"


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None
