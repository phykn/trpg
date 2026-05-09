from src.game.domain.combat import GraphCombatState
from src.game.domain.memory import ActLogEntry
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.wire.graph_to_front import graph_to_front_state


def _character(
    character_id: str,
    *,
    hp: int,
    max_hp: int,
    mp: int,
    max_mp: int,
) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "hp": hp,
            "max_hp": max_hp,
            "mp": mp,
            "max_mp": max_mp,
            "stats": {"body": 3, "agility": 2, "mind": 1, "presence": 0},
        },
    )


def _runtime(*, combat: bool = False) -> GameRuntimeState:
    graph = Graph(
        nodes={
            "town": GraphNode(
                id="town",
                type="location",
                properties={"name": "Town", "description": "A small town."},
            ),
            "forest": GraphNode(
                id="forest",
                type="location",
                properties={"name": "Forest", "description": "Old trees."},
            ),
            "player_01": _character(
                "player_01",
                hp=18,
                max_hp=30,
                mp=2,
                max_mp=10,
            ),
            "goblin_01": _character(
                "goblin_01",
                hp=5,
                max_hp=24,
                mp=0,
                max_mp=0,
            ),
            "hidden_01": _character(
                "hidden_01",
                hp=10,
                max_hp=10,
                mp=0,
                max_mp=0,
            ),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
            "located_at:goblin_01:town": GraphEdge(
                id="located_at:goblin_01:town",
                type="located_at",
                from_node_id="goblin_01",
                to_node_id="town",
            ),
            "hidden_at:hidden_01:town": GraphEdge(
                id="hidden_at:hidden_01:town",
                type="hidden_at",
                from_node_id="hidden_01",
                to_node_id="town",
            ),
            "connects_to:town:forest": GraphEdge(
                id="connects_to:town:forest",
                type="connects_to",
                from_node_id="town",
                to_node_id="forest",
            ),
        },
    )
    graph_combat_state = None
    if combat:
        graph_combat_state = GraphCombatState(
            location_id="town",
            player_id="player_01",
            enemy_ids=["goblin_01"],
            participant_ids=["player_01", "goblin_01"],
            sides={"player_01": "player", "goblin_01": "enemy"},
            round=2,
        )
    return GameRuntimeState(
        graph=graph,
        progress=GameProgress(
            game_id="game-1",
            player_id="player_01",
            graph_combat_state=graph_combat_state,
        ),
        log_entries=[ActLogEntry(id=1, kind="act", text="당신은 Town에 있습니다.")],
    )


def _contains_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(child, key) for child in value.values())
    if isinstance(value, list):
        return any(_contains_key(child, key) for child in value)
    return False


def test_graph_front_state_builds_hero_resource_state_words():
    payload = graph_to_front_state(_runtime())

    assert payload.hero.id == "player_01"
    assert payload.hero.resources["hp"].current == 18
    assert payload.hero.resources["hp"].maximum == 30
    assert payload.hero.resources["hp"].state == "hurt"
    assert payload.hero.resources["mp"].state == "drained"
    assert payload.hero.stats == {"agility": 2, "body": 3, "mind": 1, "presence": 0}
    assert payload.log[0].text == "당신은 Town에 있습니다."


def test_graph_front_state_builds_place_from_visible_graph_edges():
    payload = graph_to_front_state(_runtime())

    assert payload.place is not None
    assert payload.place.id == "town"
    assert [exit_.id for exit_ in payload.place.exits] == ["forest"]
    assert [target.id for target in payload.place.targets] == ["goblin_01"]


def test_graph_front_state_builds_combat_view_when_progress_exists():
    payload = graph_to_front_state(_runtime(combat=True))

    assert payload.combat is not None
    assert payload.combat.round == 2
    assert payload.combat.outcome == "ongoing"
    assert [p.id for p in payload.combat.participants] == ["player_01", "goblin_01"]
    assert payload.combat.participants[1].hp.state == "critical"


def test_graph_front_state_exposes_pending_confirmation_without_payload():
    runtime = _runtime()
    runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(
                update={
                    "pending_confirmation": {
                        "id": "confirm-1",
                        "kind": "attack_start",
                        "title": "공격하시겠습니까?",
                        "body": "goblin_01 공격해 전투를 시작합니다.",
                        "confirm_label": "공격",
                        "cancel_label": "취소",
                        "target_label": "goblin_01",
                        "payload": {"kind": "graph_action", "action": {}},
                    }
                }
            )
        }
    )

    payload = graph_to_front_state(runtime).model_dump(mode="json", by_alias=True)

    assert payload["pendingConfirmation"]["kind"] == "attack_start"
    assert payload["pendingConfirmation"]["target_label"] == "goblin_01"
    assert "payload" not in payload["pendingConfirmation"]


def test_graph_front_state_omits_internal_change_and_edge_ids():
    dumped = graph_to_front_state(_runtime(combat=True)).model_dump()

    assert _contains_key(dumped, "changes") is False
    assert _contains_key(dumped, "edge_id") is False
    assert _contains_key(dumped, "edgeId") is False
