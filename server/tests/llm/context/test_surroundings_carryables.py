"""NPC entries carry a transferable-items list (excluding equipped/quest-locked)."""

from src.llm.context.surroundings import build_surroundings
from src.game.domain.entities import (
    Character,
    Equipment,
    Item,
    Location,
    Race,
    Stats,
)
from src.game.domain.state import GameState


def _state() -> GameState:
    state = GameState(game_id="g", profile="p", player_id="player_01")
    state.locations["loc_01"] = Location(id="loc_01", name="망루")
    state.races["human"] = Race(id="human", name="인간", description="")
    state.items["dagger_01"] = Item(id="dagger_01", name="단검")
    state.items["sword_01"] = Item(id="sword_01", name="장검")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        stats=Stats(),
        location_id="loc_01",
    )
    npc = Character(
        id="scout_01",
        name="카리스",
        race_id="human",
        gender="male",
        stats=Stats(),
        location_id="loc_01",
        inventory_ids=["dagger_01", "sword_01"],
        equipment=Equipment(weapon="sword_01"),
    )
    state.characters["scout_01"] = npc
    return state


def test_carryables_excludes_equipped_items():
    state = _state()
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "scout_01")
    ids = [c["id"] for c in npc.get("carryables", [])]
    assert "dagger_01" in ids
    assert "sword_01" not in ids  # equipped


def test_carryables_omitted_when_empty():
    state = _state()
    state.characters["scout_01"].inventory_ids = []
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "scout_01")
    assert "carryables" not in npc
