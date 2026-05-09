from __future__ import annotations

from src.game.domain.action import Action
from src.llm.context.graph_surroundings import build_graph_surroundings
from src.wire.graph_to_front import graph_to_front_state

from .state import GameRuntimeState


def answer_graph_query(runtime: GameRuntimeState, action: Action) -> str:
    topic = _single(action.what) or "surroundings"
    surroundings = build_graph_surroundings(runtime)
    if topic == "exits":
        return _exits_text(surroundings)
    if topic == "inventory":
        return _inventory_text(surroundings)
    if topic == "status":
        return _status_text(runtime)
    return _surroundings_text(surroundings)


def _surroundings_text(surroundings: dict) -> str:
    location = surroundings.get("location") or {}
    location_name = location.get("name") or "알 수 없는 곳"
    npcs = _entity_names(surroundings, "npc")
    items = _entity_names(surroundings, "item")
    exits = _entity_names(surroundings, "connection")

    pieces = [f"현재 위치는 {location_name}입니다."]
    pieces.append(
        f"주변에는 {_join(npcs + items)}이 있습니다."
        if npcs or items
        else "주변에 눈에 띄는 대상은 없습니다."
    )
    pieces.append(
        f"이동할 수 있는 곳은 {_join(exits)}입니다."
        if exits
        else "지금 이동할 수 있는 곳은 없습니다."
    )
    return " ".join(pieces)


def _exits_text(surroundings: dict) -> str:
    exits = _entity_names(surroundings, "connection")
    if not exits:
        return "지금 이동할 수 있는 곳은 없습니다."
    return f"이동할 수 있는 곳은 {_join(exits)}입니다."


def _inventory_text(surroundings: dict) -> str:
    names = _names_from_entries(surroundings.get("inventory"))
    if not names:
        return "소지품이 없습니다."
    return f"소지품은 {_join(names)}입니다."


def _status_text(runtime: GameRuntimeState) -> str:
    hero = graph_to_front_state(runtime).hero
    hp = _resource_label(hero.resources["hp"].state)
    mp = _resource_label(hero.resources["mp"].state)
    return f"당신의 체력은 {hp} 상태이고 마나는 {mp} 상태입니다."


def _entity_names(surroundings: dict, entity_type: str) -> list[str]:
    names: list[str] = []
    for entry in surroundings.get("entities") or []:
        if not isinstance(entry, dict) or entry.get("type") != entity_type:
            continue
        name = entry.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _names_from_entries(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _resource_label(state: str) -> str:
    return {
        "healthy": "양호한",
        "hurt": "다친",
        "critical": "위급한",
        "downed": "쓰러진",
        "ready": "충분한",
        "strained": "부족한",
        "drained": "고갈된",
    }.get(state, state)


def _join(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names)


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None
