from src.game.domain.entities import (
    Character,
    Chapter,
    Connection,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Race,
    Skill,
)
from src.game.domain.state import GameState
from src.game.ontology.contract_graph import build_contract_graph


def test_build_contract_graph_projects_location_inventory_and_quest_edges():
    state = GameState(game_id="g", profile="p", player_id="player")
    state.characters = {
        "player": Character(
            id="player",
            name="Player",
            race_id="human",
            location_id="town",
            inventory_ids=["potion"],
            learned_skill_ids=["slash"],
            relations={"elder": 25},
        ),
        "elder": Character(
            id="elder",
            name="Elder",
            race_id="human",
            location_id="town",
        ),
        "rat": Character(
            id="rat",
            name="Rat",
            race_id="beast",
            location_id="cellar",
        ),
    }
    state.items = {
        "rusty_sword": Item(id="rusty_sword", name="Rusty Sword"),
        "potion": Item(id="potion", name="Potion"),
        "reward_gem": Item(id="reward_gem", name="Reward Gem"),
    }
    state.locations = {
        "town": Location(
            id="town",
            name="Town",
            item_ids=["rusty_sword"],
            connections=[
                Connection(
                    target_id="cellar",
                    difficulty="easy",
                    key_item_id="rusty_sword",
                )
            ],
        ),
        "cellar": Location(id="cellar", name="Cellar"),
    }
    state.skills = {
        "slash": Skill(
            id="slash",
            name="Slash",
            type="attack",
            target="single",
            primary_stat="STR",
        )
    }
    state.races = {
        "human": Race(
            id="human",
            name="Human",
            description="Human race",
            racial_skill_ids=["slash"],
        ),
        "beast": Race(id="beast", name="Beast", description="Beast race"),
    }
    state.quests = {
        "rat_quest": Quest(
            id="rat_quest",
            title="Rat Quest",
            giver_id="elder",
            difficulty="easy",
            triggers=[
                QuestTrigger(
                    id="kill_rat",
                    name="Kill Rat",
                    type="character_death",
                    target_id="rat",
                )
            ],
            rewards=QuestRewards(gold=5, exp=10, items=["reward_gem"]),
        )
    }
    state.chapters = {
        "chapter_1": Chapter(
            id="chapter_1",
            title="Chapter 1",
            quest_ids=["rat_quest"],
        )
    }

    graph = build_contract_graph(state)

    assert graph.nodes["player"].type == "character"
    assert graph.nodes["town"].type == "location"
    assert graph.nodes["rusty_sword"].type == "item"
    assert graph.nodes["rat_quest"].type == "quest"

    edge_types = {
        (edge.type, edge.from_node_id, edge.to_node_id)
        for edge in graph.edges.values()
    }

    assert ("located_at", "player", "town") in edge_types
    assert ("located_at", "rusty_sword", "town") in edge_types
    assert ("connects_to", "town", "cellar") in edge_types
    assert ("carries", "player", "potion") in edge_types
    assert ("knows_skill", "player", "slash") in edge_types
    assert ("belongs_to_race", "player", "human") in edge_types
    assert ("grants_skill", "human", "slash") in edge_types
    assert ("relation", "player", "elder") in edge_types
    assert ("gives_quest", "elder", "rat_quest") in edge_types
    assert ("target_of", "rat", "rat_quest") in edge_types
    assert ("reward_of", "reward_gem", "rat_quest") in edge_types
    assert ("part_of_chapter", "rat_quest", "chapter_1") in edge_types

    connection_edge = graph.edges["connects_to:town:cellar"]
    assert connection_edge.properties == {
        "difficulty": "easy",
        "key_item_id": "rusty_sword",
    }

    relation_edge = graph.edges["relation:player:elder"]
    assert relation_edge.properties == {"affinity": 25}
