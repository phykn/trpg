import json

from src.domain.entities import Character, Equipment, Item, Race, Stats, WeaponEffect
from src.domain.state import GameState
from src.wire.emit import _build_hero_payload
from src.wire.models import Equipment as WireEquipment
from src.wire.models import EquipItem, HeroPayload, StatEntry


def _base_state(gold: int = 0, stats: Stats | None = None) -> GameState:
    state = GameState(game_id="game_test_hero", profile="test", player_id="p1")
    state.races["human"] = Race(id="human", name="인간", description="")
    player = Character(
        id="p1",
        name="레오",
        race_id="human",
        gender="male",
        level=1,
        stats=stats or Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=20,
        max_hp=20,
        mp=10,
        max_mp=10,
        gold=gold,
    )
    state.characters["p1"] = player
    state.invalidate_graph()
    return state


def test_top_level_shape():
    state = _base_state(gold=5)
    payload = _build_hero_payload(state, state.graph())
    assert isinstance(payload, HeroPayload)
    assert payload.name == "레오"
    assert payload.hp == 20
    assert payload.hp_max == 20
    assert payload.gold == 5
    assert isinstance(payload.equipment, WireEquipment)


def test_camel_case_serialization():
    state = _base_state()
    payload = _build_hero_payload(state, state.graph())
    d = payload.model_dump()
    assert "raceJob" in d
    assert "expMax" in d
    assert "hpMax" in d
    assert "mpMax" in d
    assert "canLevelUp" in d
    assert "reviveCoins" in d
    assert "reviveCoinsMax" in d
    assert "race_job" not in d
    assert "exp_max" not in d
    assert "hp_max" not in d
    assert "mp_max" not in d
    assert "can_level_up" not in d
    assert "revive_coins" not in d
    assert "revive_coins_max" not in d


def test_stats_sub_model():
    state = _base_state(stats=Stats(STR=14, DEX=10, CON=10, INT=8, WIS=10, CHA=10))
    payload = _build_hero_payload(state, state.graph())
    assert all(isinstance(s, StatEntry) for s in payload.stats)
    labels = {s.label: s.value for s in payload.stats}
    assert labels["근력"] == 14
    assert labels["지능"] == 8


def test_inventory_gold_row_is_first():
    state = _base_state(gold=42)
    payload = _build_hero_payload(state, state.graph())
    first = payload.inventory[0]
    assert first.name == "금화(42)"
    assert first.qty == 1


def test_equipment_slot_filled():
    state = _base_state()
    state.items["sword_01"] = Item(
        id="sword_01",
        name="강철검",
        effects=WeaponEffect(type="weapon", weapon_dice="1d8"),
    )
    state.characters["p1"].equipment = Equipment(weapon="sword_01")
    state.characters["p1"].inventory_ids = ["sword_01"]
    state.invalidate_graph()
    payload = _build_hero_payload(state, state.graph())
    assert payload.equipment.weapon == EquipItem(name="강철검")
    assert payload.equipment.armor is None
    assert payload.equipment.accessory is None


def test_json_round_trip():
    state = _base_state(gold=7)
    payload = _build_hero_payload(state, state.graph())
    raw = json.dumps(payload.model_dump(), ensure_ascii=False)
    data = json.loads(raw)
    assert data["name"] == "레오"
    assert "raceJob" in data
