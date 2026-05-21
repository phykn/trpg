from src.game.domain.graph.query import known_skills_of
from src.game.seed.graph_seed import build_seed_graph
from src.game.seed.player import PlayerInput


def _skill() -> dict:
    return {
        "id": "slash",
        "name": "베기",
        "action": "precise",
        "bonus": 2,
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
                "racial_skills": ["slash"],
            }
        },
        locations={
            "town": {
                "id": "town",
                "name": "마을",
                "items": ["potion"],
                "connections": [{"target": "forest", "difficulty": "normal"}],
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
                "quests": [],
            }
        },
        start={
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
        template={
            "id": "player_01",
            "inventory": [],
            "equipment": {},
            "gold": 0,
            "xp_pool": 0,
        },
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph

    assert graph.nodes["player_01"].type == "character"
    assert graph.nodes["player_01"].properties["is_player"] is True
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
    assert "revive_coins" not in graph.nodes["player_01"].properties
    assert "default" not in graph.nodes
    assert graph.edges["located_at:player_01:town"].type == "located_at"
    assert graph.edges["belongs_to_race:player_01:human"].type == "belongs_to_race"
    assert graph.edges["grants_skill:human:slash"].type == "grants_skill"
    assert "knows_skill:racial:player_01:slash" not in graph.edges
    assert [edge.to_node_id for edge in known_skills_of(graph, "player_01")] == [
        "slash"
    ]
    assert graph.edges["located_at:potion:town"].type == "located_at"
    assert graph.edges["connects_to:town:forest"].properties["difficulty"] == "normal"
    assert bundle.progress.game_id == "game-1"
    assert bundle.progress.profile_id == "default"
    assert bundle.progress.player_id == "player_01"
    assert bundle.progress.locale == "ko"


def test_build_seed_graph_marks_seed_characters_as_non_players():
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
                "race": "human",
                "location": "town",
                "stats": {"body": 99, "agility": 99, "mind": 99, "presence": 99},
            }
        },
        quests={},
        chapters={},
        start={
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    assert "is_player" not in bundle.content.characters["elder"]
    assert bundle.graph.nodes["elder"].properties["is_player"] is False
    assert "stats" not in bundle.graph.nodes["elder"].properties
    assert "status" not in bundle.graph.nodes["elder"].properties


def test_build_seed_graph_keeps_static_content_out_of_seed_nodes():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={
            "human": {
                "id": "human",
                "name": "인간",
                "description": "사람입니다.",
                "racial_skills": ["slash"],
            }
        },
        locations={
            "town": {
                "id": "town",
                "name": "마을",
                "description": "작은 마을입니다.",
                "items": ["potion"],
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
                "action": "precise",
            }
        },
        npcs={
            "elder": {
                "id": "elder",
                "name": "장로",
                "description": "마을의 장로입니다.",
                "race": "human",
                "location": "town",
                "level": 1,
            }
        },
        quests={
            "quest_01": {
                "id": "quest_01",
                "title": "첫 의뢰",
                "summary": "마을 일을 돕습니다.",
                "description": "장로의 부탁을 해결합니다.",
                "giver": "elder",
                "status": "pending",
            }
        },
        chapters={
            "chapter_01": {
                "id": "chapter_01",
                "title": "첫 장",
                "description": "시작 장입니다.",
                "quests": ["quest_01"],
            }
        },
        start={
            "start_location": "town",
            "active_subject": "elder",
            "active_quest": "quest_01",
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
        "giver": "elder",
        "difficulty": "easy",
        "triggers": [
            {
                "id": "reach_forest",
                "name": "숲 도착",
                "type": "location_enter",
                "target": "forest",
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
                "race": "human",
                "location": "town",
                "level": 1,
            }
        },
        quests={"quest_01": quest},
        chapters={},
        start={
            "start_location": "town",
            "active_subject": "elder",
            "active_quest": None,
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
            "target": "forest",
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
                "race": "human",
                "location": "town",
                "level": 1,
            }
        },
        quests={
            "quest_01": {
                "id": "quest_01",
                "title": "첫 의뢰",
                "giver": "elder",
                "difficulty": "easy",
                "status": "active",
            }
        },
        chapters={
            "chapter_01": {
                "id": "chapter_01",
                "title": "첫 장",
                "quests": ["quest_01"],
            }
        },
        start={
            "start_location": "town",
            "active_subject": "elder",
            "active_quest": "quest_01",
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


def test_build_seed_graph_links_missing_supplies_quest():
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
                "race": "human",
                "location": "hub",
                "level": 1,
                "relations": {"player_01": 20},
            },
            "village_resident": {
                "id": "village_resident",
                "name": "마을 주민",
                "race": "human",
                "location": "hub",
                "level": 1,
                "relations": {"player_01": 0},
            },
            "guide_npc": {
                "id": "guide_npc",
                "name": "테스트 가이드",
                "race": "human",
                "location": "hub",
                "level": 1,
                "relations": {"player_01": 0},
            },
        },
        quests={
            "q_missing_supplies": {
                "id": "q_missing_supplies",
                "title": "보급품 누락",
                "summary": "보급품 누락을 관계 선택으로 해결합니다.",
                "giver": "quartermaster_npc",
                "difficulty": "easy",
                "status": "pending",
                "triggers": [
                    {
                        "id": "resolve_missing_supplies",
                        "name": "보급품 누락 해결",
                        "type": "item_use",
                        "target": "missing_supply_bundle",
                    }
                ],
                "rewards": {"gold": 1, "exp": 0},
            }
        },
        chapters={
            "ch_dev_test": {
                "id": "ch_dev_test",
                "title": "개발 테스트",
                "quests": ["q_missing_supplies"],
            }
        },
        start={
            "start_location": "hub",
            "active_subject": None,
            "active_quest": None,
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
        graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 20
    )
    assert (
        graph.edges["relation:village_resident:player_01"].properties["affinity"] == 0
    )
    assert graph.edges["relation:guide_npc:player_01"].properties["affinity"] == 0


def test_build_seed_graph_links_effects_from_items():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={
            "practice_dagger": {
                "id": "practice_dagger",
                "name": "훈련 단검",
                "action": "precise",
                "effect": "dc_down",
            }
        },
        skills={
            "training_strike": {
                "id": "training_strike",
                "name": "훈련 일격",
                "action": "precise",
                "bonus": 2,
            }
        },
        effects={
            "dc_down": {
                "id": "dc_down",
                "name": "난이도 감소",
                "description": "판정 난이도를 낮춥니다.",
            }
        },
        npcs={},
        quests={},
        chapters={},
        start={
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
        template={
            "id": "player_01",
            "inventory": ["practice_dagger"],
            "equipment": {},
        },
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["dc_down"].type == "effect"
    assert (
        graph.edges["uses_effect:practice_dagger:dc_down"].type
        == "uses_effect"
    )
    assert "uses_effect:training_strike:dc_down" not in graph.edges
    assert bundle.content.effects["dc_down"]["name"] == "난이도 감소"


def test_build_seed_graph_keeps_status_records_without_legacy_item_links():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={
            "focus_charm": {
                "id": "focus_charm",
                "name": "집중 부적",
            }
        },
        skills={
            "focus_bolt": {
                "id": "focus_bolt",
                "name": "집중 화살",
                "action": "precise",
                "bonus": 2,
            }
        },
        statuses={
            "focused": {
                "id": "focused",
                "name": "집중",
                "description": "주의가 흐트러지지 않은 상태입니다.",
            }
        },
        npcs={},
        quests={},
        chapters={},
        start={
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
        template={
            "id": "player_01",
            "inventory": ["focus_charm"],
            "equipment": {},
        },
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["focused"].type == "status"
    assert "applies_status:focus_charm:focused" not in graph.edges
    assert bundle.content.statuses["focused"]["name"] == "집중"


def test_build_seed_graph_links_characters_to_factions():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={},
        skills={},
        factions={
            "test_staff": {
                "id": "test_staff",
                "name": "테스트 직원단",
                "description": "테스트 절차를 관리하는 사람들.",
                "relations": {"supply_team": "cooperative"},
            },
            "supply_team": {
                "id": "supply_team",
                "name": "보급팀",
            },
        },
        npcs={
            "guide": {
                "id": "guide",
                "name": "가이드",
                "race": "human",
                "location": "town",
                "faction": "test_staff",
            }
        },
        quests={},
        chapters={},
        start={
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["test_staff"].type == "faction"
    assert graph.nodes["supply_team"].type == "faction"
    assert graph.edges["member_of_faction:guide:test_staff"].type == (
        "member_of_faction"
    )
    assert graph.edges["faction_relation:test_staff:supply_team"].properties == {
        "relation": "cooperative"
    }
    assert bundle.content.factions["test_staff"]["name"] == "테스트 직원단"


def test_build_seed_graph_links_skills_to_actions():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={},
        skills={
            "spark": {
                "id": "spark",
                "name": "불꽃",
                "action": "precise",
            }
        },
        actions={
            "precise": {
                "id": "precise",
                "name": "공격",
            }
        },
        npcs={},
        quests={},
        chapters={},
        start={
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
        template={"id": "player_01", "learned_skills": ["spark"]},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["precise"].type == "action"
    assert graph.edges["uses_action:spark:precise"].type == "uses_action"
    assert bundle.content.actions["precise"]["name"] == "공격"


def test_build_seed_graph_links_items_to_slots():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={
            "ring": {
                "id": "ring",
                "name": "반지",
                "slot": "accessory",
            }
        },
        slots={
            "accessory": {
                "id": "accessory",
                "name": "장신구",
            }
        },
        skills={},
        npcs={},
        quests={},
        chapters={},
        start={
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
        template={"id": "player_01", "inventory": ["ring"]},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["accessory"].type == "slot"
    assert graph.edges["uses_slot:ring:accessory"].type == "uses_slot"
    assert bundle.content.slots["accessory"]["name"] == "장신구"


def test_build_seed_graph_links_knowledge_from_world_records():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={
            "archive": {
                "id": "archive",
                "name": "기록실",
                "knowledge": ["report_clue"],
            }
        },
        items={
            "sealed_report": {
                "id": "sealed_report",
                "name": "밀봉된 보고서",
                "knowledge": ["report_clue"],
            }
        },
        skills={},
        knowledge={
            "report_clue": {
                "id": "report_clue",
                "title": "보고서 단서",
                "visibility": "public",
            }
        },
        npcs={
            "clerk": {
                "id": "clerk",
                "name": "기록 담당자",
                "race": "human",
                "location": "archive",
                "knowledge": ["report_clue"],
            }
        },
        quests={},
        chapters={},
        start={
            "start_location": "archive",
            "active_subject": None,
            "active_quest": None,
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["report_clue"].type == "knowledge"
    assert graph.edges["has_knowledge:archive:report_clue"].type == "has_knowledge"
    assert graph.edges["has_knowledge:sealed_report:report_clue"].type == (
        "has_knowledge"
    )
    assert graph.edges["has_knowledge:clerk:report_clue"].type == "has_knowledge"
    assert bundle.content.knowledge["report_clue"]["title"] == "보고서 단서"


def test_build_seed_graph_links_characters_to_dialogue_styles():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={},
        skills={},
        dialogue_styles={
            "procedural": {
                "id": "procedural",
                "name": "절차형 말투",
                "speech_style": "짧고 기록문 같은 말투",
            }
        },
        npcs={
            "guide": {
                "id": "guide",
                "name": "가이드",
                "race": "human",
                "location": "town",
                "dialogue_style": "procedural",
            }
        },
        quests={},
        chapters={},
        start={
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["procedural"].type == "dialogue_style"
    assert graph.edges["uses_dialogue_style:guide:procedural"].type == (
        "uses_dialogue_style"
    )
    assert bundle.content.dialogue_styles["procedural"]["name"] == "절차형 말투"


def test_build_seed_graph_links_characters_to_mbti_records():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={},
        skills={},
        mbti={
            "ENFP": {
                "id": "ENFP",
                "speech_style": "말이 빠르고 감탄이 많습니다.",
            }
        },
        npcs={
            "guide": {
                "id": "guide",
                "name": "가이드",
                "race": "human",
                "location": "town",
                "mbti": "ENFP",
            }
        },
        quests={},
        chapters={},
        start={
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["ENFP"].type == "mbti"
    assert graph.edges["has_mbti:guide:ENFP"].type == "has_mbti"
    assert bundle.content.mbti["ENFP"]["speech_style"] == (
        "말이 빠르고 감탄이 많습니다."
    )
