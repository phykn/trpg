from __future__ import annotations

from collections.abc import AsyncIterator

from src.db.repo import SaveRepo
from src.game.domain.memory import GMLogEntry
from src.game.domain.state import GameState
from src.llm.context import build_surroundings
from src.wire.emit import emit_log_entry

from .dirty import Dirty, ToFrontFn, finalize, next_log_id, push_log_entry


async def run_query(
    state: GameState,
    save_repo: SaveRepo,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    topic: str | None,
) -> AsyncIterator[dict]:
    text = build_query_response(state, topic)
    entry = GMLogEntry(id=next_log_id(state), kind="gm", text=text)
    push_log_entry(state, entry, dirty)
    yield emit_log_entry(entry)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev


def build_query_response(state: GameState, topic: str | None) -> str:
    graph = state.graph()
    surroundings = build_surroundings(state, state.player_id, graph)
    topic = topic or "surroundings"
    if topic == "exits":
        return _exits_text(surroundings)
    if topic == "inventory":
        return _inventory_text(surroundings)
    if topic == "quests":
        return _quests_text(state)
    if topic == "status":
        return _status_text(state)
    return _surroundings_text(surroundings)


def _exits_text(surroundings: dict) -> str:
    names = _entity_names(surroundings, "connection")
    if not names:
        return "보이는 이동 경로가 없습니다."
    return f"보이는 이동 경로는 {_join_names(names)}입니다."


def _inventory_text(surroundings: dict) -> str:
    names = _names_from_entries(surroundings.get("inventory"))
    if not names:
        return "가지고 있는 물건이 없습니다."
    return f"가지고 있는 물건은 {_join_names(names)}입니다."


def _quests_text(state: GameState) -> str:
    active = [quest.title for quest in state.quests.values() if quest.status == "active"]
    offers = [quest.title for quest in state.quests.values() if quest.status == "pending"]
    parts: list[str] = []
    if active:
        parts.append(f"진행 중인 퀘스트는 {_join_names(active)}입니다")
    if offers:
        parts.append(f"시작 가능한 퀘스트는 {_join_names(offers)}입니다")
    if not parts:
        return "확인할 수 있는 퀘스트가 없습니다."
    return " ".join(parts) + "."


def _status_text(state: GameState) -> str:
    player = state.characters[state.player_id]
    return f"현재 상태는 체력 {player.hp}/{player.max_hp}, 마나 {player.mp}/{player.max_mp}입니다."


def _surroundings_text(surroundings: dict) -> str:
    location = surroundings.get("location") or {}
    location_name = location.get("name") if isinstance(location, dict) else None
    parts: list[str] = []
    if location_name:
        parts.append(f"현재 위치는 {location_name}입니다")
    npcs = _entity_names(surroundings, "npc")
    if npcs:
        parts.append(f"보이는 인물은 {_join_names(npcs)}입니다")
    items = _entity_names(surroundings, "item")
    if items:
        parts.append(f"보이는 물건은 {_join_names(items)}입니다")
    exits = _entity_names(surroundings, "connection")
    if exits:
        parts.append(f"이동 경로는 {_join_names(exits)}입니다")
    if not parts:
        return "지금 확인할 수 있는 공개 정보가 없습니다."
    return " ".join(parts) + "."


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


def _join_names(names: list[str]) -> str:
    return ", ".join(names)
