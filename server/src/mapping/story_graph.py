"""Story-graph projection for the client's map view; characters are limited to player + current scene + companions + active subject so it can't become a spoiler dump."""

from typing import Literal

from ..domain.clock import day_phase
from ..domain.entities import Character, Location, Quest
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ..ontology.queries import (
    companions_of,
    connections_of,
    giver_of,
    inhabitants_of,
    location_of,
    trigger_targets_of,
)
from .labels import (
    RISK_PAYLOAD,
    gender_label,
    giver_with_location_label,
    race_job_label,
)


NodeStatus = Literal[
    "current",
    "engaged",
    "reachable_move",
    "reachable_meet",
    "unreachable_move",
    "unreachable_meet",
]
EdgeKind = Literal[
    "current_pin",
    "observe",
    "progress",
    "move",
    "meet",
    "quest_giver",
    "quest_target",
]


def _edge_id(source: str, target: str, label: str) -> str:
    return f"{source}->{target}:{label}"


def _reachable_location_ids(
    state: GameState, graph: GameGraph, start_location_id: str | None
) -> set[str]:
    if start_location_id is None or start_location_id not in state.locations:
        return set()
    seen = {start_location_id}
    queue = [start_location_id]
    while queue:
        location_id = queue.pop(0)
        for edge in connections_of(graph, location_id):
            target_id = edge.to_id
            if target_id not in state.locations or target_id in seen:
                continue
            seen.add(target_id)
            queue.append(target_id)
    return seen


def _visible_character_ids(
    state: GameState, graph: GameGraph, player: Character | None
) -> set[str]:
    if player is None:
        return set()

    visible = {player.id}
    if state.active_subject_id in state.characters:
        visible.add(state.active_subject_id)
    visible.update(
        cid for cid in companions_of(graph, player.id) if cid in state.characters
    )

    if player.location_id is not None:
        for cid in inhabitants_of(graph, player.location_id):
            if cid in state.characters:
                visible.add(cid)

    return visible


def _character_identity(state: GameState, graph: GameGraph, char: Character) -> dict:
    """Identity fields shared by every character-kind node (hero / subject /
    target). `role` and kind-specific extras (`known`, `trust`, `status`,
    `reachable`) are left to each builder — target uses appearance for its
    role label rather than `char.role`, hero has no `trust` against itself."""
    return {
        "id": char.id,
        "label": char.name,
        "level": char.level,
        "raceJob": race_job_label(state, graph, char),
        "gender": gender_label(char),
    }


def _hero_node(state: GameState, graph: GameGraph, player: Character) -> dict:
    return {
        **_character_identity(state, graph, player),
        "kind": "hero",
        "status": None,
        "reachable": True,
        "alive": player.alive,
        "role": player.role,
        "known": [player.appearance] if player.appearance else [],
    }


def _subject_node(
    state: GameState, graph: GameGraph, subject: Character, player: Character
) -> dict:
    known = [subject.appearance] if subject.appearance else []
    known += [m.content for m in player.memories if m.target_id == subject.id]
    return {
        **_character_identity(state, graph, subject),
        "kind": "subject",
        "status": "engaged",
        "reachable": True,
        "alive": subject.alive,
        "role": subject.role,
        "trust": subject.relations.get(player.id, 0),
        "known": known,
    }


def _target_node(
    state: GameState,
    graph: GameGraph,
    target: Character,
    player: Character,
    same_location: bool,
) -> dict:
    return {
        **_character_identity(state, graph, target),
        "kind": "target",
        "status": "reachable_meet" if same_location else "unreachable_meet",
        "reachable": same_location,
        "alive": target.alive,
        "role": target.appearance or target.description,
        "trust": target.relations.get(player.id, 0),
    }


def _place_node(loc: Location, state: GameState) -> dict:
    return {
        "id": loc.id,
        "kind": "place",
        "label": loc.name,
        "status": "current",
        "reachable": True,
        "description": loc.description,
        "risk": RISK_PAYLOAD[loc.sleep_risk],
        "dayPhase": day_phase(state.turn_count),
        "weather": list(loc.weather),
    }


def _location_node(loc: Location, move_difficulty: str | None, adjacent: bool) -> dict:
    return {
        "id": loc.id,
        "kind": "location",
        "label": loc.name,
        "status": "reachable_move" if adjacent else "unreachable_move",
        "reachable": adjacent,
        "description": loc.description,
        "risk": RISK_PAYLOAD[loc.sleep_risk],
        "moveDifficulty": move_difficulty,
    }


def _quest_node(quest: Quest, state: GameState, graph: GameGraph) -> dict:
    return {
        "id": quest.id,
        "kind": "quest",
        "label": quest.title,
        "status": None,
        "reachable": True,
        "questDifficulty": quest.difficulty,
        "rewards": {"gold": quest.rewards.gold, "exp": quest.rewards.exp},
        "giver": giver_with_location_label(state, graph, quest.id),
        "goals": [t.name for t in quest.triggers],
        "summary": quest.summary or "",
    }


def to_story_graph(state: GameState, graph: GameGraph | None = None) -> dict:
    """Project the server-side state into the client's story graph contract.

    Each node carries the kind-specific fields the panel renders
    (level/raceJob/risk/...); the panel reads them directly without
    re-deriving from a display string.
    """
    if graph is None:
        graph = state.graph()

    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    player = state.characters.get(state.player_id)
    player_location_id = player.location_id if player else None
    visible_location_ids = _reachable_location_ids(state, graph, player_location_id)
    visible_character_ids = _visible_character_ids(state, graph, player)

    # Adjacent (one-hop) move difficulties keyed by neighbor location id —
    # used to populate `moveDifficulty` on adjacent location nodes only.
    # Multi-hop reachable locations get null; the panel only acts on
    # one-hop neighbors anyway.
    adjacent_move_difficulty: dict[str, str | None] = {}
    if player_location_id in state.locations:
        for edge in connections_of(graph, player_location_id):
            attrs = edge.attrs or {}
            adjacent_move_difficulty[edge.to_id] = attrs.get("difficulty")

    def add_edge(
        source: str | None, target: str | None, label: str, kind: EdgeKind
    ) -> None:
        if not source or not target or source == target:
            return
        if source not in nodes or target not in nodes:
            return
        edge_id = _edge_id(source, target, label)
        edges[edge_id] = {
            "id": edge_id,
            "source": source,
            "target": target,
            "label": label,
            "kind": kind,
        }

    if player is not None and player.id in visible_character_ids:
        nodes[player.id] = _hero_node(state, graph, player)

    adjacent_location_ids = set(adjacent_move_difficulty.keys())
    for location_id, location in state.locations.items():
        if location_id not in visible_location_ids:
            continue
        if location_id == player_location_id:
            nodes[location_id] = _place_node(location, state)
        else:
            nodes[location_id] = _location_node(
                location,
                adjacent_move_difficulty.get(location_id),
                adjacent=location_id in adjacent_location_ids,
            )

    for character_id in visible_character_ids:
        if character_id == state.player_id:
            continue
        character = state.characters.get(character_id)
        if character is None or player is None:
            continue
        if character_id == state.active_subject_id:
            nodes[character_id] = _subject_node(state, graph, character, player)
        else:
            same_location = location_of(graph, character_id) == player_location_id
            nodes[character_id] = _target_node(
                state, graph, character, player, same_location=same_location
            )

    quest_ids = (
        {state.active_quest_id} if state.active_quest_id in state.quests else set()
    )
    for quest_id in quest_ids:
        nodes[quest_id] = _quest_node(state.quests[quest_id], state, graph)

    add_edge(state.player_id, player_location_id, "현재 위치", "current_pin")
    add_edge(state.player_id, state.active_subject_id, "주시", "observe")
    add_edge(state.player_id, state.active_quest_id, "진행 중", "progress")

    for location_id in visible_location_ids:
        for edge in connections_of(graph, location_id):
            add_edge(location_id, edge.to_id, "이동", "move")

    for character_id in visible_character_ids:
        if character_id == state.player_id:
            continue
        loc_id = location_of(graph, character_id)
        if loc_id == player_location_id:
            add_edge(character_id, loc_id, "등장", "meet")

    for quest_id in quest_ids:
        add_edge(giver_of(graph, quest_id), quest_id, "의뢰", "quest_giver")
        for target_id in trigger_targets_of(graph, quest_id):
            add_edge(target_id, quest_id, "목표", "quest_target")

    count_by_kind: dict[str, int] = {
        "hero": 0,
        "place": 0,
        "location": 0,
        "subject": 0,
        "target": 0,
        "quest": 0,
    }
    for node in nodes.values():
        count_by_kind[node["kind"]] = count_by_kind.get(node["kind"], 0) + 1

    active_quest = (
        state.quests.get(state.active_quest_id) if state.active_quest_id else None
    )
    summary = " · ".join(
        part
        for part in [
            "주인공" if player is not None else None,
            f"현재 위치 {state.locations[player_location_id].name}"
            if player_location_id in state.locations
            else None,
            f"퀘스트 {active_quest.title}" if active_quest is not None else None,
            f"등장인물 {count_by_kind['target'] + count_by_kind['subject']}",
            f"장소 {count_by_kind['location'] + count_by_kind['place']}",
        ]
        if part
    )

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "summary": summary or "스토리 데이터 없음",
    }
