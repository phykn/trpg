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
            "level": 2,
            "gold": 7,
            "xp_pool": 11,
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
            "potion_01": GraphNode(
                id="potion_01",
                type="item",
                properties={
                    "name": "회복 물약",
                    "qty": 2,
                    "consumable": True,
                    "effects": {"type": "consumable", "effect": "heal", "amount": 8},
                },
            ),
            "sword_01": GraphNode(
                id="sword_01",
                type="item",
                properties={
                    "name": "낡은 검",
                    "effects": {"type": "weapon", "weapon_dice": "1d6"},
                },
            ),
            "basic_strike": GraphNode(
                id="basic_strike",
                type="skill",
                properties={"name": "기본 타격"},
            ),
            "goblin_01": _character(
                "goblin_01",
                hp=5,
                max_hp=24,
                mp=0,
                max_mp=0,
            ),
            "quest_01": GraphNode(
                id="quest_01",
                type="quest",
                properties={
                    "title": "첫 의뢰",
                    "summary": "광장의 문제를 해결합니다.",
                    "difficulty": "normal",
                    "status": "pending",
                    "triggers": [
                        {
                            "id": "trigger_01",
                            "name": "늑대 쫓아내기",
                            "type": "character_defeat",
                            "target_id": "goblin_01",
                        }
                    ],
                    "triggers_met": [False],
                    "rewards": {"gold": 5, "exp": 10, "items": []},
                },
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
            "carries:player_01:potion_01": GraphEdge(
                id="carries:player_01:potion_01",
                type="carries",
                from_node_id="player_01",
                to_node_id="potion_01",
            ),
            "equips:player_01:sword_01": GraphEdge(
                id="equips:player_01:sword_01",
                type="equips",
                from_node_id="player_01",
                to_node_id="sword_01",
                properties={"slot": "weapon"},
            ),
            "knows_skill:player_01:basic_strike": GraphEdge(
                id="knows_skill:player_01:basic_strike",
                type="knows_skill",
                from_node_id="player_01",
                to_node_id="basic_strike",
            ),
            "gives_quest:goblin_01:quest_01": GraphEdge(
                id="gives_quest:goblin_01:quest_01",
                type="gives_quest",
                from_node_id="goblin_01",
                to_node_id="quest_01",
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
    assert payload.hero.level == 2
    assert payload.hero.gold == 7
    assert payload.hero.exp == 11
    assert payload.hero.exp_max > payload.hero.exp
    assert payload.hero.stats == {"agility": 2, "body": 3, "mind": 1, "presence": 0}
    assert payload.log[0].text == "당신은 Town에 있습니다."


def test_graph_front_state_builds_hero_assets_from_graph_edges():
    runtime = _runtime()
    runtime.graph.nodes["player_01"].properties["status"] = ["축복"]

    payload = graph_to_front_state(runtime)

    assert payload.hero.inventory[0].id == "potion_01"
    assert payload.hero.inventory[0].name == "회복 물약"
    assert payload.hero.inventory[0].qty == 2
    assert payload.hero.inventory[0].can_use is True
    assert payload.hero.inventory[0].equip_slots == []
    assert payload.hero.equipment.weapon is not None
    assert payload.hero.equipment.weapon.id == "sword_01"
    assert payload.hero.equipment.weapon.name == "낡은 검"
    assert payload.hero.equipment.armor is None
    assert payload.hero.skills == ["기본 타격"]
    assert payload.hero.status == ["축복"]


def test_graph_front_state_builds_place_from_visible_graph_edges():
    runtime = _runtime()
    runtime.graph.nodes["goblin_01"].properties["xp_reward"] = 10
    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert payload.place.id == "town"
    assert [exit_.id for exit_ in payload.place.exits] == ["forest"]
    assert [target.id for target in payload.place.targets] == ["goblin_01"]
    assert payload.place.targets[0].kind == "enemy"


def test_graph_front_state_hides_defeated_place_targets():
    runtime = _runtime()
    runtime.graph.nodes["goblin_01"].properties["hp"] = 0
    runtime.graph.nodes["goblin_01"].properties["status"] = ["defeated"]

    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert payload.place.targets == []


def test_graph_front_state_builds_visible_quest_offer():
    payload = graph_to_front_state(_runtime())

    assert payload.quest is None
    assert len(payload.quest_offers) == 1
    offer = payload.quest_offers[0]
    assert offer.id == "quest_01"
    assert offer.title == "첫 의뢰"
    assert offer.giver == "goblin_01"
    assert offer.goals == ["늑대 쫓아내기"]
    assert offer.rewards.gold == 5
    assert offer.rewards.exp == 10
    assert offer.status == "pending"
    assert offer.actions == ["accept"]


def test_graph_front_state_prefers_progress_active_quest():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "active"
    runtime.graph.nodes["quest_02"] = GraphNode(
        id="quest_02",
        type="quest",
        properties={
            "title": "두 번째 의뢰",
            "status": "active",
            "triggers": [],
            "triggers_met": [],
        },
    )
    runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(
                update={"active_quest_id": "quest_02"}
            )
        }
    )

    payload = graph_to_front_state(runtime)

    assert payload.quest is not None
    assert payload.quest.id == "quest_02"


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
