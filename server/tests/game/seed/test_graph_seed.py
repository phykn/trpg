from src.game.domain.entities import (
    Chapter,
    Character,
    Connection,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Race,
    Skill,
)
from src.game.flow.init import PlayerInput
from src.game.seed.graph_seed import build_seed_graph


def _skill() -> Skill:
    return Skill(
        id="slash",
        name="베기",
        type="attack",
        target="single",
        primary_stat="STR",
    )


def test_build_seed_graph_creates_nodes_edges_and_progress():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={
            "human": Race(
                id="human",
                name="인간",
                description="",
                racial_skill_ids=["slash"],
            )
        },
        locations={
            "town": Location(
                id="town",
                name="마을",
                item_ids=["potion"],
                connections=[Connection(target_id="forest", difficulty="normal")],
            ),
            "forest": Location(id="forest", name="숲"),
        },
        items={"potion": Item(id="potion", name="물약")},
        skills={"slash": _skill()},
        npcs={},
        quests={},
        chapters={
            "chapter_01": Chapter(
                id="chapter_01",
                title="첫 장",
                quest_ids=[],
            )
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
    assert "default" not in graph.nodes
    assert graph.edges["located_at:player_01:town"].type == "located_at"
    assert graph.edges["belongs_to_race:player_01:human"].type == "belongs_to_race"
    assert (
        graph.edges["knows_skill:racial:player_01:slash"].properties["source"]
        == "racial"
    )
    assert graph.edges["grants_skill:human:slash"].type == "grants_skill"
    assert graph.edges["located_at:potion:town"].type == "located_at"
    assert graph.edges["connects_to:town:forest"].properties["difficulty"] == "normal"
    assert bundle.progress.game_id == "game-1"
    assert bundle.progress.player_id == "player_01"
    assert bundle.progress.locale == "ko"


def test_build_seed_graph_keeps_reward_items_out_of_visible_placement():
    reward = Item(id="reward_sword", name="보상 검")
    elder = Character(
        id="elder",
        name="장로",
        race_id="human",
        location_id="town",
        level=1,
    )
    quest = Quest(
        id="quest_01",
        title="첫 의뢰",
        giver_id="elder",
        difficulty="easy",
        triggers=[
            QuestTrigger(
                id="reach_forest",
                name="숲 도착",
                type="location_enter",
                target_id="forest",
            )
        ],
        rewards=QuestRewards(items=["reward_sword"]),
        status="pending",
    )

    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": Race(id="human", name="인간", description="")},
        locations={
            "town": Location(id="town", name="마을"),
            "forest": Location(id="forest", name="숲"),
        },
        items={"reward_sword": reward},
        skills={},
        npcs={"elder": elder},
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


def test_build_seed_graph_links_quests_to_chapters():
    quest = Quest(
        id="quest_01",
        title="첫 의뢰",
        giver_id="elder",
        difficulty="easy",
        status="active",
    )
    chapter = Chapter(id="chapter_01", title="첫 장", quest_ids=["quest_01"])

    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": Race(id="human", name="인간", description="")},
        locations={"town": Location(id="town", name="마을")},
        items={},
        skills={},
        npcs={
            "elder": Character(
                id="elder",
                name="장로",
                race_id="human",
                location_id="town",
                level=1,
            )
        },
        quests={"quest_01": quest},
        chapters={"chapter_01": chapter},
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
