from src.domain.entities import (
    Character,
    Connection,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Stats,
)
from src.ontology.graph import build_graph
from src.ontology.target_view import build_target_view


def _seed(state):
    state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="광장",
        connections=[Connection(target_id="gate_01", key_item_id="key_01")],
    )
    state.locations["gate_01"] = Location(id="gate_01", name="성문")
    state.items["sword_01"] = Item(id="sword_01", name="검")
    state.items["key_01"] = Item(id="key_01", name="열쇠")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        inventory_ids=["key_01"],
        relations={"guard_01": -25},
    )
    state.characters["guard_01"] = Character(
        id="guard_01",
        name="경비",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        appearance="갑옷",
        tone_hint="격식",
    )
    state.quests["q1"] = Quest(
        id="q1",
        title="t",
        giver_id="guard_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="x", name="처치", type="character_death", target_id="goblin_01"
            )
        ],
        rewards=QuestRewards(items=["sword_01"]),
    )
    return state


def test_graph_node_types(fresh_state):
    g = build_graph(_seed(fresh_state))
    assert g.get_node_type("player_01") == "character"
    assert g.get_node_type("plaza_01") == "location"
    assert g.get_node_type("sword_01") == "item"
    assert g.get_node_type("q1") == "quest"
    assert g.get_node_type("ghost") is None


def test_graph_edges(fresh_state):
    g = build_graph(_seed(fresh_state))
    assert any(e.to_id == "plaza_01" for e in g.get_edges("player_01", "located_at"))
    assert any(e.to_id == "key_01" for e in g.get_edges("player_01", "carries"))
    assert any(e.to_id == "gate_01" for e in g.get_edges("plaza_01", "connects_to"))
    assert any(e.to_id == "gate_01" for e in g.get_edges("key_01", "unlocks"))
    assert any(e.to_id == "q1" for e in g.get_edges("guard_01", "gives_quest"))
    assert any(e.to_id == "q1" for e in g.get_edges("sword_01", "reward_of"))


def test_target_view_npc(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "guard_01", actor_id="player_01")
    assert v["type"] == "npc" and v["name"] == "경비"
    assert v["affinity"] == -25
    assert v["appearance"] == "갑옷"


def test_target_view_location(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "plaza_01", actor_id="player_01")
    assert v["type"] == "location" and v["name"] == "광장"


def test_target_view_item(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "key_01", actor_id="player_01")
    assert v["type"] == "item" and v["name"] == "열쇠"


def test_target_view_unknown_returns_none(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    assert build_target_view(state, g, "ghost", actor_id="player_01") is None
