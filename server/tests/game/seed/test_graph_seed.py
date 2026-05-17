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
        graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 20
    )
    assert (
        graph.edges["relation:village_resident:player_01"].properties["affinity"] == 0
    )
    assert graph.edges["relation:guide_npc:player_01"].properties["affinity"] == 0


def test_build_seed_graph_links_support_effects_from_skills_and_items():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={
            "practice_dagger": {
                "id": "practice_dagger",
                "name": "훈련 단검",
                "support_action": "attack",
                "effect_template": "dc_down",
            }
        },
        skills={
            "training_strike": {
                "id": "training_strike",
                "name": "훈련 일격",
                "action": "attack",
                "effect_template": "dc_down",
            }
        },
        support_effects={
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
            "start_location_id": "town",
            "active_subject_id": None,
            "active_quest_id": None,
        },
        template={
            "id": "player_01",
            "inventory_ids": ["practice_dagger"],
            "equipment": {},
        },
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["dc_down"].type == "support_effect"
    assert (
        graph.edges["uses_support_effect:practice_dagger:dc_down"].type
        == "uses_support_effect"
    )
    assert (
        graph.edges["uses_support_effect:training_strike:dc_down"].type
        == "uses_support_effect"
    )
    assert bundle.content.support_effects["dc_down"]["name"] == "난이도 감소"


def test_build_seed_graph_links_statuses_from_skills_and_items():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"town": {"id": "town", "name": "마을"}},
        items={
            "focus_charm": {
                "id": "focus_charm",
                "name": "집중 부적",
                "status_ids": ["focused"],
            }
        },
        skills={
            "focus_bolt": {
                "id": "focus_bolt",
                "name": "집중 화살",
                "status_ids": ["focused"],
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
            "start_location_id": "town",
            "active_subject_id": None,
            "active_quest_id": None,
        },
        template={
            "id": "player_01",
            "inventory_ids": ["focus_charm"],
            "equipment": {},
        },
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["focused"].type == "status"
    assert graph.edges["applies_status:focus_charm:focused"].type == "applies_status"
    assert graph.edges["applies_status:focus_bolt:focused"].type == "applies_status"
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
                "race_id": "human",
                "location_id": "town",
                "faction_id": "test_staff",
            }
        },
        quests={},
        chapters={},
        start={
            "start_location_id": "town",
            "active_subject_id": None,
            "active_quest_id": None,
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


def test_build_seed_graph_links_skills_to_action_categories():
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
                "action_category_id": "combat_attack",
            }
        },
        action_categories={
            "combat_attack": {
                "id": "combat_attack",
                "name": "공격",
                "default_stat": "body",
            }
        },
        npcs={},
        quests={},
        chapters={},
        start={
            "start_location_id": "town",
            "active_subject_id": None,
            "active_quest_id": None,
        },
        template={"id": "player_01", "learned_skill_ids": ["spark"]},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.nodes["combat_attack"].type == "action_category"
    assert graph.edges["uses_action_category:spark:combat_attack"].type == (
        "uses_action_category"
    )
    assert bundle.content.action_categories["combat_attack"]["default_stat"] == "body"


def test_build_seed_graph_links_knowledge_from_world_records():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={
            "archive": {
                "id": "archive",
                "name": "기록실",
                "knowledge_ids": ["report_clue"],
            }
        },
        items={
            "sealed_report": {
                "id": "sealed_report",
                "name": "밀봉된 보고서",
                "knowledge_ids": ["report_clue"],
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
                "race_id": "human",
                "location_id": "archive",
                "knowledge_ids": ["report_clue"],
            }
        },
        quests={},
        chapters={},
        start={
            "start_location_id": "archive",
            "active_subject_id": None,
            "active_quest_id": None,
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
                "race_id": "human",
                "location_id": "town",
                "dialogue_style_id": "procedural",
            }
        },
        quests={},
        chapters={},
        start={
            "start_location_id": "town",
            "active_subject_id": None,
            "active_quest_id": None,
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
                "race_id": "human",
                "location_id": "town",
                "mbti": "ENFP",
            }
        },
        quests={},
        chapters={},
        start={
            "start_location_id": "town",
            "active_subject_id": None,
            "active_quest_id": None,
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
