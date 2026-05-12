from src.game.seed.graph_seed import build_seed_graph
from src.game.seed.player import PlayerInput


def _skill() -> dict:
    return {
        "id": "slash",
        "name": "베기",
        "kind": "attack",
        "target": "single",
    }


def test_build_seed_graph_creates_nodes_edges_and_progress():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={
            "human": {
                "id": "human",
                "name": "인간",
                "description": "",
                "racial_skill_ids": ["slash"],
            }
        },
        locations={
            "town": {
                "id": "town",
                "name": "마을",
                "item_ids": ["potion"],
                "connections": [{"target_id": "forest", "difficulty": "normal"}],
            },
            "forest": {"id": "forest", "name": "숲"},
        },
        items={"potion": {"id": "potion", "name": "물약"}},
        skills={"slash": _skill()},
        npcs={},
        quests={},
        chapters={
            "chapter_01": {
                "id": "chapter_01",
                "title": "첫 장",
                "quest_ids": [],
            }
        },
        start={
            "start_location_id": "town",
            "active_subject_id": None,
            "active_quest_id": None,
        },
        template={
            "id": "player_01",
            "inventory_ids": [],
            "equipment": {},
            "gold": 0,
            "xp_pool": 0,
        },
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph

    assert graph.nodes["player_01"].type == "character"
    assert graph.nodes["player_01"].properties["stats"] == {
        "body": 10,
        "agility": 10,
        "mind": 10,
        "presence": 10,
    }
    assert graph.nodes["player_01"].properties["level"] == 1
    assert graph.nodes["player_01"].properties["max_hp"] == 5
    assert graph.nodes["player_01"].properties["hp"] == 5
    assert graph.nodes["player_01"].properties["max_mp"] == 5
    assert graph.nodes["player_01"].properties["mp"] == 5
    assert "default" not in graph.nodes
    assert graph.edges["located_at:player_01:town"].type == "located_at"
    assert graph.edges["belongs_to_race:player_01:human"].type == "belongs_to_race"
    assert (
        graph.edges["knows_skill:racial:player_01:slash"].properties["source"]
        == "racial"
    )
    assert graph.edges["knows_skill:racial:player_01:slash"].properties["tier"] == 1
    assert graph.edges["grants_skill:human:slash"].type == "grants_skill"
    assert graph.edges["located_at:potion:town"].type == "located_at"
    assert graph.edges["connects_to:town:forest"].properties["difficulty"] == "normal"
    assert bundle.progress.game_id == "game-1"
    assert bundle.progress.profile_id == "default"
    assert bundle.progress.player_id == "player_01"
    assert bundle.progress.locale == "ko"


def test_build_seed_graph_keeps_static_content_out_of_seed_nodes():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={
            "human": {
                "id": "human",
                "name": "인간",
                "description": "사람입니다.",
                "racial_skill_ids": ["slash"],
            }
        },
        locations={
            "town": {
                "id": "town",
                "name": "마을",
                "description": "작은 마을입니다.",
                "item_ids": ["potion"],
            }
        },
        items={
            "potion": {
                "id": "potion",
                "name": "물약",
                "description": "붉은 회복 물약입니다.",
            }
        },
        skills={
            "slash": {
                "id": "slash",
                "name": "베기",
                "description": "검으로 벱니다.",
                "kind": "attack",
            }
        },
        npcs={
            "elder": {
                "id": "elder",
                "name": "장로",
                "description": "마을의 장로입니다.",
                "race_id": "human",
                "location_id": "town",
                "level": 1,
            }
        },
        quests={
            "quest_01": {
                "id": "quest_01",
                "title": "첫 의뢰",
                "summary": "마을 일을 돕습니다.",
                "description": "장로의 부탁을 해결합니다.",
                "giver_id": "elder",
                "status": "pending",
            }
        },
        chapters={
            "chapter_01": {
                "id": "chapter_01",
                "title": "첫 장",
                "description": "시작 장입니다.",
                "quest_ids": ["quest_01"],
            }
        },
        start={
            "start_location_id": "town",
            "active_subject_id": "elder",
            "active_quest_id": "quest_01",
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    for node_id in ("town", "potion", "slash", "elder", "quest_01", "chapter_01"):
        properties = bundle.graph.nodes[node_id].properties
        assert properties["source"] == "scenario"
        assert properties["source_id"] == node_id
        for static_key in ("name", "title", "description", "summary"):
            assert static_key not in properties

    assert bundle.content.locations["town"]["name"] == "마을"
    assert bundle.content.items["potion"]["description"] == "붉은 회복 물약입니다."
    assert bundle.content.quests["quest_01"]["title"] == "첫 의뢰"


def test_build_seed_graph_keeps_reward_items_out_of_visible_placement():
    quest = {
        "id": "quest_01",
        "title": "첫 의뢰",
        "giver_id": "elder",
        "difficulty": "easy",
        "triggers": [
            {
                "id": "reach_forest",
                "name": "숲 도착",
                "type": "location_enter",
                "target_id": "forest",
            }
        ],
        "rewards": {"gold": 0, "exp": 0, "items": ["reward_sword"]},
        "status": "pending",
    }

    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={
            "town": {"id": "town", "name": "마을"},
            "forest": {"id": "forest", "name": "숲"},
        },
        items={"reward_sword": {"id": "reward_sword", "name": "보상 검"}},
        skills={},
        npcs={
            "elder": {
                "id": "elder",
                "name": "장로",
                "race_id": "human",
                "location_id": "town",
                "level": 1,
            }
        },
        quests={"quest_01": quest},
        chapters={},
        start={
            "start_location_id": "town",
            "active_subject_id": "elder",
            "active_quest_id": None,
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    edge_types = {
        edge.type
        for edge in bundle.graph.edges.values()
        if edge.from_node_id == "reward_sword"
    }
    assert edge_types == {"reward_of"}
    quest_node = bundle.graph.nodes["quest_01"]
    assert quest_node.properties["triggers"] == [
        {
            "id": "reach_forest",
            "type": "location_enter",
            "target_id": "forest",
        }
    ]
    assert bundle.content.quests["quest_01"]["triggers"][0]["name"] == "숲 도착"
    assert quest_node.properties["rewards"] == {"gold": 0, "exp": 0}


def test_build_seed_graph_links_quests_to_chapters():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={},
        skills={},
        npcs={
            "elder": {
                "id": "elder",
                "name": "장로",
                "race_id": "human",
                "location_id": "town",
                "level": 1,
            }
        },
        quests={
            "quest_01": {
                "id": "quest_01",
                "title": "첫 의뢰",
                "giver_id": "elder",
                "difficulty": "easy",
                "status": "active",
            }
        },
        chapters={
            "chapter_01": {
                "id": "chapter_01",
                "title": "첫 장",
                "quest_ids": ["quest_01"],
            }
        },
        start={
            "start_location_id": "town",
            "active_subject_id": "elder",
            "active_quest_id": "quest_01",
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    assert (
        bundle.graph.edges["part_of_chapter:quest_01:chapter_01"].type
        == "part_of_chapter"
    )
    assert bundle.progress.active_subject_id == "elder"
    assert bundle.progress.active_quest_id == "quest_01"


def test_build_seed_graph_links_missing_supplies_social_quest():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"hub": {"id": "hub", "name": "허브"}},
        items={
            "missing_supply_bundle": {
                "id": "missing_supply_bundle",
                "name": "누락된 보급품",
            }
        },
        skills={},
        npcs={
            "quartermaster_npc": {
                "id": "quartermaster_npc",
                "name": "보급 담당자",
                "race_id": "human",
                "location_id": "hub",
                "level": 1,
                "relations": {"player_01": 20},
            },
            "village_resident": {
                "id": "village_resident",
                "name": "마을 주민",
                "race_id": "human",
                "location_id": "hub",
                "level": 1,
                "relations": {"player_01": 0},
            },
            "guide_npc": {
                "id": "guide_npc",
                "name": "테스트 가이드",
                "race_id": "human",
                "location_id": "hub",
                "level": 1,
                "relations": {"player_01": 0},
            },
        },
        quests={
            "q_missing_supplies": {
                "id": "q_missing_supplies",
                "title": "보급품 누락",
                "summary": "보급품 누락을 관계 선택으로 해결합니다.",
                "giver_id": "quartermaster_npc",
                "difficulty": "easy",
                "status": "pending",
                "triggers": [
                    {
                        "id": "resolve_missing_supplies",
                        "name": "보급품 누락 해결",
                        "type": "item_use",
                        "target_id": "missing_supply_bundle",
                    }
                ],
                "rewards": {"gold": 1, "exp": 0},
            }
        },
        chapters={
            "ch_dev_test": {
                "id": "ch_dev_test",
                "title": "개발 테스트",
                "quest_ids": ["q_missing_supplies"],
            }
        },
        start={
            "start_location_id": "hub",
            "active_subject_id": None,
            "active_quest_id": None,
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert (
        graph.edges["gives_quest:quartermaster_npc:q_missing_supplies"].type
        == "gives_quest"
    )
    assert (
        graph.edges[
            "target_of:resolve_missing_supplies:missing_supply_bundle:"
            "q_missing_supplies"
        ].type
        == "target_of"
    )
    assert (
        graph.edges["part_of_chapter:q_missing_supplies:ch_dev_test"].type
        == "part_of_chapter"
    )
    assert (
        graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"]
        == 20
    )
    assert (
        graph.edges["relation:village_resident:player_01"].properties["affinity"]
        == 0
    )
    assert graph.edges["relation:guide_npc:player_01"].properties["affinity"] == 0
