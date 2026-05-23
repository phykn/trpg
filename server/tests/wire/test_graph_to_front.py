from src.game.domain.combat import GraphCombatState
from src.game.domain.memory import ActLogEntry, GMLogEntry, NarrationCue, RollLogEntry
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.domain.content import RuntimeContent
from src.wire.graph.to_front import graph_to_front_state


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
                    "effect": "heal",
                    "amount": 8,
                },
            ),
            "heal": GraphNode(
                id="heal",
                type="effect",
                properties={"kind": "heal"},
            ),
            "sword_01": GraphNode(
                id="sword_01",
                type="item",
                properties={
                    "name": "낡은 검",
                    "slot": "weapon",
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
            "fang_01": GraphNode(
                id="fang_01",
                type="item",
                properties={
                    "name": "날카로운 송곳니",
                    "slot": "weapon",
                },
            ),
            "pelt_01": GraphNode(
                id="pelt_01",
                type="item",
                properties={"name": "늑대 가죽", "qty": 1},
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
                            "type": "character_death",
                            "target": "goblin_01",
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
            "carries:goblin_01:fang_01": GraphEdge(
                id="carries:goblin_01:fang_01",
                type="carries",
                from_node_id="goblin_01",
                to_node_id="fang_01",
            ),
            "carries:goblin_01:pelt_01": GraphEdge(
                id="carries:goblin_01:pelt_01",
                type="carries",
                from_node_id="goblin_01",
                to_node_id="pelt_01",
            ),
        },
    )
    graph_combat_state = None
    if combat:
        graph_combat_state = GraphCombatState(
            location_id="town",
            player_id="player_01",
            active_enemy_id="goblin_01",
            enemy_ids=["goblin_01"],
            participant_ids=["player_01", "goblin_01"],
            sides={"player_01": "player", "goblin_01": "enemy"},
            player_hearts=2,
            enemy_hearts=1,
            round=2,
            last_roll=16,
            last_dc=12,
        )
    return GameRuntimeState(
        graph=graph,
        content=RuntimeContent(
            effects={
                "heal": {
                    "id": "heal",
                    "name": "HP 회복",
                    "kind": "heal",
                }
            }
        ),
        progress=GameProgress(
            game_id="game-1",
            player_id="player_01",
            graph_combat_state=graph_combat_state,
        ),
        log_entries=[
            ActLogEntry(id=1, kind="act", text="당신은 Town에 있습니다."),
            GMLogEntry(
                id=2,
                kind="gm",
                text="나레이션입니다.",
                outcome="success",
                cues=[
                    NarrationCue(
                        kind="constraint",
                        label="잠김",
                        text="북쪽 문이 잠김",
                    )
                ],
            ),
        ],
    )


def _contains_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(
            _contains_key(child, key) for child in value.values()
        )
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
    assert payload.hero.exp_max == 2
    assert payload.hero.can_level_up is True
    assert payload.hero.stats == {"agility": 2, "body": 3, "mind": 1, "presence": 0}
    assert payload.log[0].text == "당신은 Town에 있습니다."
    assert payload.log[1].outcome == "success"
    assert payload.log[1].cues[0].text == "북쪽 문이 잠김"


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
    runtime.graph.nodes["goblin_01"].properties["role"] = "숲의 포식자"
    runtime.graph.nodes["goblin_01"].properties["job"] = "레거시 직업"
    runtime.graph.nodes["goblin_01"].properties["gold"] = 2
    runtime.graph.nodes["goblin_01"].properties["status"] = ["경계 중"]
    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert payload.place.id == "town"
    assert [exit_.id for exit_ in payload.place.exits] == ["forest"]
    assert [target.id for target in payload.place.targets] == ["goblin_01"]
    target = payload.place.targets[0]
    assert target.kind == "npc"
    assert target.role == "숲의 포식자"
    assert target.race_job == "숲의 포식자"
    assert target.model_dump(
        by_alias=True,
        exclude_none=True,
    ) == {
        "id": "goblin_01",
        "name": "goblin_01",
        "kind": "npc",
        "alive": True,
        "level": 2,
        "raceJob": "숲의 포식자",
        "gender": "",
        "role": "숲의 포식자",
    }


def test_graph_front_state_hides_locked_place_exits():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "active"
    runtime.graph.edges["connects_to:town:forest"].properties["requires_quest"] = "quest_01"

    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert payload.place.id == "town"
    assert payload.place.exits == []


def test_graph_front_state_shows_place_exit_after_required_quest_completed():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "completed"
    runtime.graph.edges["connects_to:town:forest"].properties["requires_quest"] = "quest_01"

    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert [exit_.id for exit_ in payload.place.exits] == ["forest"]


def test_graph_front_state_exposes_visible_place_items_and_hides_hidden_items():
    runtime = _runtime()
    runtime.graph.nodes["supply_token"] = GraphNode(
        id="supply_token",
        type="item",
        properties={
            "name": "보급 표식",
            "description": "바닥에 놓인 작은 표식입니다.",
        },
    )
    runtime.graph.nodes["hidden_wire"] = GraphNode(
        id="hidden_wire",
        type="item",
        properties={"name": "숨은 철사"},
    )
    runtime.graph.edges["located_at:supply_token:town"] = GraphEdge(
        id="located_at:supply_token:town",
        type="located_at",
        from_node_id="supply_token",
        to_node_id="town",
    )
    runtime.graph.edges["hidden_at:hidden_wire:town"] = GraphEdge(
        id="hidden_at:hidden_wire:town",
        type="hidden_at",
        from_node_id="hidden_wire",
        to_node_id="town",
    )

    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert [item.id for item in payload.place.items] == ["supply_token"]
    assert payload.place.items[0].name == "보급 표식"
    assert payload.place.items[0].description == "바닥에 놓인 작은 표식입니다."
    assert not _contains_key(payload.model_dump(mode="json"), "hidden_wire")


def test_graph_front_state_resolves_static_content_from_runtime_content():
    runtime = _runtime()
    runtime.graph.nodes["town"].properties = {
        "source": "scenario",
        "source_id": "town",
    }
    runtime.graph.nodes["forest"].properties = {
        "source": "scenario",
        "source_id": "forest",
    }
    runtime.graph.nodes["goblin_01"].properties = {
        **{
            key: runtime.graph.nodes["goblin_01"].properties[key]
            for key in ("hp", "max_hp", "mp", "max_mp", "stats", "level")
        },
        "source": "scenario",
        "source_id": "goblin_01",
        "xp_reward": 10,
    }
    runtime.graph.nodes["fang_01"].properties = {
        "source": "scenario",
        "source_id": "fang_01",
        "slot": "weapon",
    }
    runtime.graph.nodes["quest_01"].properties = {
        "source": "scenario",
        "source_id": "quest_01",
        "status": "pending",
        "triggers": [
            {
                "id": "trigger_01",
                "name": "늑대 쫓아내기",
                "type": "character_death",
                "target": "goblin_01",
            }
        ],
        "triggers_met": [False],
        "rewards": {"gold": 5, "exp": 10, "items": []},
    }
    runtime = runtime.model_copy(
        update={
            "content": RuntimeContent(
                locations={
                    "town": {"id": "town", "name": "광장", "description": "넓은 광장."},
                    "forest": {
                        "id": "forest",
                        "name": "숲",
                        "description": "오래된 숲.",
                    },
                },
                characters={
                    "goblin_01": {
                        "id": "goblin_01",
                        "name": "떠돌이 적",
                        "role": "숲의 포식자",
                    }
                },
                items={"fang_01": {"id": "fang_01", "name": "날카로운 송곳니"}},
                effects={
                    "heal": {
                        "id": "heal",
                        "name": "HP 회복",
                        "kind": "heal",
                    }
                },
                quests={
                    "quest_01": {
                        "id": "quest_01",
                        "title": "첫 의뢰",
                        "summary": "광장의 문제를 해결합니다.",
                        "difficulty": "normal",
                    }
                },
            )
        }
    )

    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert payload.place.name == "광장"
    assert payload.place.description == "넓은 광장."
    assert payload.place.exits[0].name == "숲"
    assert payload.place.targets[0].name == "떠돌이 적"
    assert payload.place.targets[0].role == "숲의 포식자"
    assert payload.place.targets[0].race_job == "숲의 포식자"
    assert [offer.title for offer in payload.quest_offers] == ["첫 의뢰"]
    assert payload.quest_offers[0].giver == "떠돌이 적"


def test_graph_front_state_hides_dead_place_targets():
    runtime = _runtime()
    runtime.graph.nodes["goblin_01"].properties["alive"] = False
    runtime.graph.nodes["goblin_01"].properties["status"] = ["dead"]

    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert payload.place.targets == []


def test_graph_front_state_hides_exits_requiring_inactive_quest():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "pending"
    runtime.graph.edges["connects_to:town:forest"].properties[
        "requires_active_quest"
    ] = "quest_01"

    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert payload.place.exits == []

    runtime.graph.nodes["quest_01"].properties["status"] = "active"

    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert [exit.id for exit in payload.place.exits] == ["forest"]


def test_graph_front_state_exposes_non_player_target_without_resources():
    runtime = _runtime()
    target = runtime.graph.nodes["goblin_01"].properties
    for key in ("hp", "max_hp", "mp", "max_mp"):
        target.pop(key)

    payload = graph_to_front_state(runtime)

    assert payload.place is not None
    assert payload.place.targets[0].id == "goblin_01"
    assert payload.place.targets[0].alive is True


def test_graph_front_state_builds_pending_quest_offer():
    payload = graph_to_front_state(_runtime())

    assert payload.quest is None
    assert len(payload.quest_offers) == 1
    offer = payload.quest_offers[0]
    assert offer.id == "quest_01"
    assert offer.title == "첫 의뢰"
    assert offer.giver == "goblin_01"
    assert offer.goals == ["늑대 쫓아내기"]
    assert offer.status == "pending"
    assert offer.actions == ["accept"]
    assert offer.choices == []


def test_graph_front_state_builds_abandoned_quest_offer():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "abandoned"

    payload = graph_to_front_state(runtime)

    assert payload.quest is None
    assert len(payload.quest_offers) == 1
    offer = payload.quest_offers[0]
    assert offer.id == "quest_01"
    assert offer.title == "첫 의뢰"
    assert offer.giver == "goblin_01"
    assert offer.goals == ["늑대 쫓아내기"]
    assert offer.rewards.gold == 5
    assert offer.rewards.exp == 10
    assert offer.status == "abandoned"
    assert offer.actions == ["accept"]
    assert offer.choices == []


def test_graph_front_state_hides_locked_quest_offer():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "locked"

    payload = graph_to_front_state(runtime)

    assert payload.quest_offers == []


def test_graph_front_state_exposes_active_quest_choices():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "active"
    runtime.graph.nodes["quest_01"].properties["triggers_met"] = [True]
    runtime.graph.nodes["quest_01"].properties["choices"] = {
        "public_record": {"label": "기록으로 남깁니다"},
        "quiet_release": {"label": "조용히 돌려보냅니다"},
    }
    runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(
                update={"active_quest_id": "quest_01"}
            )
        }
    )

    payload = graph_to_front_state(runtime)

    assert payload.quest is not None
    assert payload.quest.actions == ["abandon"]
    assert [choice.model_dump() for choice in payload.quest.choices] == [
        {"id": "public_record", "label": "기록으로 남깁니다"},
        {"id": "quiet_release", "label": "조용히 돌려보냅니다"},
    ]


def test_graph_front_state_hides_choice_buttons_until_goals_are_met():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties.update(
        {
            "status": "active",
            "choices": {"public_record": {"label": "기록으로 남깁니다"}},
        }
    )
    runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(
                update={"active_quest_id": "quest_01"}
            )
        }
    )

    payload = graph_to_front_state(runtime)
    assert payload.quest is not None
    assert payload.quest.choices == []

    runtime.graph.nodes["quest_01"].properties["triggers_met"] = [True]

    payload = graph_to_front_state(runtime)
    assert payload.quest is not None
    assert [choice.id for choice in payload.quest.choices] == ["public_record"]


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


def test_graph_front_state_includes_route_step_for_non_adjacent_location_goal():
    runtime = _runtime()
    runtime.graph.nodes["forest"].properties["name"] = "숲"
    runtime.graph.nodes["market"] = GraphNode(
        id="market",
        type="location",
        properties={"name": "시장", "description": "Stalls."},
    )
    runtime.graph.edges["connects_to:forest:market"] = GraphEdge(
        id="connects_to:forest:market",
        type="connects_to",
        from_node_id="forest",
        to_node_id="market",
    )
    runtime.graph.nodes["quest_01"].properties["status"] = "active"
    runtime.graph.nodes["quest_01"].properties["triggers"] = [
        {
            "id": "enter_market",
            "type": "location_enter",
            "target": "market",
            "name": "시장으로 향합니다",
        }
    ]

    payload = graph_to_front_state(runtime)

    assert payload.quest is not None
    assert payload.quest.goals == ["숲을 거쳐 시장으로 향합니다"]


def test_graph_front_state_keeps_direct_location_goal_label():
    runtime = _runtime()
    runtime.graph.nodes["forest"].properties["name"] = "숲"
    runtime.graph.nodes["quest_01"].properties["status"] = "active"
    runtime.graph.nodes["quest_01"].properties["triggers"] = [
        {
            "id": "enter_forest",
            "type": "location_enter",
            "target": "forest",
            "name": "숲으로 향합니다",
        }
    ]

    payload = graph_to_front_state(runtime)

    assert payload.quest is not None
    assert payload.quest.goals == ["숲으로 향합니다"]


def test_graph_front_state_marks_failed_social_check_goal_as_retryable():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "active"
    runtime.graph.nodes["quest_01"].properties["triggers"] = [
        {
            "id": "convince_goblin",
            "type": "social_check",
            "target": "goblin_01",
            "name": "고블린을 설득합니다",
        }
    ]
    runtime.graph.nodes["quest_01"].properties["triggers_met"] = [False]
    runtime = runtime.model_copy(
        update={
            "log_entries": [
                *runtime.log_entries,
                RollLogEntry(
                    id=3,
                    kind="roll",
                    check="매력",
                    roll=2,
                    margin=-8,
                    result="fail",
                ),
            ]
        }
    )

    payload = graph_to_front_state(runtime)

    assert payload.quest is not None
    assert payload.quest.goals == ["다시 고블린을 설득합니다"]


def test_graph_front_state_keeps_failed_social_check_retry_after_narration():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "active"
    runtime.graph.nodes["quest_01"].properties["triggers"] = [
        {
            "id": "convince_goblin",
            "type": "social_check",
            "target": "goblin_01",
            "name": "고블린을 설득합니다",
        }
    ]
    runtime.graph.nodes["quest_01"].properties["triggers_met"] = [False]
    runtime = runtime.model_copy(
        update={
            "log_entries": [
                *runtime.log_entries,
                RollLogEntry(
                    id=3,
                    kind="roll",
                    check="매력",
                    roll=2,
                    margin=-8,
                    result="fail",
                ),
                GMLogEntry(
                    id=4,
                    kind="gm",
                    text="고블린은 아직 마음을 열지 않습니다.",
                    outcome="failure",
                ),
            ]
        }
    )

    payload = graph_to_front_state(runtime)

    assert payload.quest is not None
    assert payload.quest.goals == ["다시 고블린을 설득합니다"]


def test_graph_front_state_marks_scenario_completed_when_required_quests_are_done():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "completed"

    payload = graph_to_front_state(runtime)

    assert payload.scenario_completed is True
    assert payload.quest is None


def test_graph_front_state_does_not_add_scenario_completion_log_line():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "completed"

    payload = graph_to_front_state(runtime)

    assert all(
        entry.text
        != "모든 이야기가 끝났습니다. 원한다면 이 세계에 머물러 더 이어갈 수 있습니다."
        for entry in payload.log
    )


def test_graph_front_state_preserves_roll_entries_after_completion():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"].properties["status"] = "completed"
    runtime = runtime.model_copy(
        update={
            "log_entries": [
                *runtime.log_entries,
                RollLogEntry(
                    id=3,
                    kind="roll",
                    check="매력",
                    roll=17,
                    margin=7,
                    result="success",
                ),
            ]
        }
    )

    payload = graph_to_front_state(runtime)

    assert payload.log[-1].kind == "roll"
    assert all(
        getattr(entry, "text", None)
        != "모든 이야기가 끝났습니다. 원한다면 이 세계에 머물러 더 이어갈 수 있습니다."
        for entry in payload.log
    )


def test_graph_front_state_exposes_active_chapter():
    runtime = _runtime()
    runtime.graph.nodes["chapter_01"] = GraphNode(
        id="chapter_01",
        type="chapter",
        properties={
            "title": "돌아갈 배는 없었다",
            "summary": "당신은 안개 숲에서 흰섬의 규칙을 듣습니다.",
            "status": "active",
        },
    )

    payload = graph_to_front_state(runtime)

    assert payload.chapter is not None
    assert payload.chapter.id == "chapter_01"
    assert payload.chapter.title == "돌아갈 배는 없었다"
    assert payload.chapter.summary == "당신은 안개 숲에서 흰섬의 규칙을 듣습니다."
    assert payload.chapter.status == "active"


def test_graph_front_state_uses_chapter_description_as_summary_fallback():
    runtime = _runtime()
    runtime.graph.nodes["chapter_01"] = GraphNode(
        id="chapter_01",
        type="chapter",
        properties={
            "title": "돌아갈 배는 없었다",
            "description": "당신은 선착장에 남겨지고, 안개 숲에서 흰섬의 규칙을 듣습니다.",
            "status": "active",
        },
    )

    payload = graph_to_front_state(runtime)

    assert payload.chapter is not None
    assert payload.chapter.summary == (
        "당신은 선착장에 남겨지고, 안개 숲에서 흰섬의 규칙을 듣습니다."
    )


def test_graph_front_state_builds_combat_view_when_progress_exists():
    runtime = _runtime(combat=True)
    target = runtime.graph.nodes["goblin_01"].properties
    for key in ("hp", "max_hp", "mp", "max_mp"):
        target.pop(key)
    payload = graph_to_front_state(runtime)

    assert payload.combat is not None
    assert payload.combat.round == 2
    assert payload.combat.outcome == "ongoing"
    assert payload.combat.active_enemy_id == "goblin_01"
    assert payload.combat.player_hearts.current == 2
    assert payload.combat.player_hearts.maximum == 3
    assert payload.combat.enemy_hearts.current == 1
    assert payload.combat.enemy_hearts.maximum == 3
    assert payload.combat.last_roll == 16
    assert payload.combat.last_dc == 12
    assert [p.id for p in payload.combat.participants] == ["player_01", "goblin_01"]
    assert payload.combat.participants[0].hp is not None
    assert payload.combat.participants[1].hp is None
    assert payload.combat.participants[1].mp is None


def test_graph_front_state_exposes_usable_combat_skill_supports():
    runtime = _runtime(combat=True)
    runtime.graph.nodes["basic_strike"].properties.update(
        {
            "name": "그림자 찌르기",
            "action": "attack",
            "mp_cost": 2,
        }
    )

    payload = graph_to_front_state(runtime).model_dump(mode="json", by_alias=True)

    assert payload["combat"]["availableSupports"] == [
        {
            "id": "basic_strike",
            "kind": "skill",
            "name": "그림자 찌르기",
            "action": "attack",
            "mpCost": 2,
            "usable": True,
        }
    ]


def test_graph_front_state_omits_unusable_combat_skill_supports():
    runtime = _runtime(combat=True)
    runtime.graph.nodes["basic_strike"].properties.update(
        {
            "name": "그림자 찌르기",
            "action": "attack",
            "mp_cost": 3,
        }
    )

    payload = graph_to_front_state(runtime).model_dump(mode="json", by_alias=True)

    assert payload["combat"]["availableSupports"] == []


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
                        "confirm_label": "전투",
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
    assert payload["pendingConfirmation"]["confirmLabel"] == "전투"
    assert payload["pendingConfirmation"]["cancelLabel"] == "취소"
    assert payload["pendingConfirmation"]["targetLabel"] == "goblin_01"
    assert "payload" not in payload["pendingConfirmation"]


def test_graph_front_state_exposes_pending_roll_without_payload():
    runtime = _runtime()
    runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(
                update={
                    "pending_roll": {
                        "id": "roll-1",
                        "kind": "perceive",
                        "title": "지력 판정이 필요합니다",
                        "body": "자세히 살펴보려면 집중해야 합니다.",
                        "stat": "mind",
                        "stat_label": "지력",
                        "required_roll": 13,
                        "payload": {"kind": "graph_action", "action": {}},
                    }
                }
            )
        }
    )

    payload = graph_to_front_state(runtime).model_dump(mode="json", by_alias=True)

    assert payload["pendingRoll"]["kind"] == "perceive"
    assert payload["pendingRoll"]["title"] == "지력 판정이 필요합니다"
    assert payload["pendingRoll"]["body"] == "자세히 살펴보려면 집중해야 합니다."
    assert payload["pendingRoll"]["stat"] == "mind"
    assert payload["pendingRoll"]["statLabel"] == "지력"
    assert payload["pendingRoll"]["requiredRoll"] == 13
    assert "payload" not in payload["pendingRoll"]


def test_graph_front_state_omits_internal_change_and_edge_ids():
    dumped = graph_to_front_state(_runtime(combat=True)).model_dump()

    assert _contains_key(dumped, "changes") is False
    assert _contains_key(dumped, "edge_id") is False
    assert _contains_key(dumped, "edgeId") is False
