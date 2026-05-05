"""NPC entries in surroundings.entities carry gender/race/role; state_tags is gone."""

from src.llm.context.surroundings import build_surroundings
from src.game.domain.entities import Character, Location, Race, Stats
from src.game.domain.state import GameState
from src.game.rules import RULES


def _make_state() -> GameState:
    state = GameState(game_id="g", profile="p", player_id="player_01")
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.races["human"] = Race(id="human", name="인간", description="")
    state.races["goblin"] = Race(id="goblin", name="고블린", description="")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        stats=Stats(),
        location_id="loc_01",
    )
    state.characters["scout_01"] = Character(
        id="scout_01",
        name="카리스",
        race_id="human",
        gender="male",
        role="정찰병",
        stats=Stats(),
        location_id="loc_01",
    )
    state.characters["mob_01"] = Character(
        id="mob_01",
        name="고블린 약탈자",
        race_id="goblin",
        stats=Stats(),
        location_id="loc_01",
    )
    return state


def test_npc_entry_carries_gender_race_role():
    state = _make_state()
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "scout_01")

    assert npc["gender"] == "male"
    assert npc["race"] == "인간"
    assert npc["role"] == "정찰병"


def test_npc_entry_omits_gender_when_none():
    state = _make_state()
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "mob_01")

    assert "gender" not in npc
    assert npc["race"] == "고블린"
    assert "role" not in npc  # role/job both empty


def test_npc_entry_no_state_tags():
    state = _make_state()
    sur = build_surroundings(state, "player_01")
    for e in sur["entities"]:
        if e.get("type") == "npc":
            assert "state_tags" not in e


def test_friendly_flag_on_high_affinity_npc():
    state = _make_state()
    state.characters["scout_01"].relations["player_01"] = (
        RULES.social.friendly_threshold
    )
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "scout_01")
    assert npc.get("friendly") is True


def test_friendly_flag_omitted_below_threshold():
    state = _make_state()
    state.characters["scout_01"].relations["player_01"] = (
        RULES.social.friendly_threshold - 1
    )
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "scout_01")
    assert "friendly" not in npc


def test_npc_entry_carries_female_gender():
    state = _make_state()
    state.characters["scout_01"].gender = "female"
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "scout_01")
    assert npc["gender"] == "female"


def test_relations_player_default_zero():
    state = _make_state()
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "scout_01")
    assert npc["relations_player"] == 0


def test_relations_player_positive():
    state = _make_state()
    state.characters["scout_01"].relations["player_01"] = 30
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "scout_01")
    assert npc["relations_player"] == 30


def test_relations_player_negative():
    state = _make_state()
    state.characters["scout_01"].relations["player_01"] = -20
    sur = build_surroundings(state, "player_01")
    npc = next(e for e in sur["entities"] if e["id"] == "scout_01")
    assert npc["relations_player"] == -20
