"""Server-side template suggestion chips: NPC / adjacent location / inventory.
Variable 0-3, one per category, no padding. Empty/combat/downed_recovered → []."""

from src.domain.entities import Character, Connection, Item, Location, Stats
from src.domain.state import CombatState, GameState
from src.mapping.suggestion_chips import build_suggestion_chips


def _seed(
    *,
    npcs: list[tuple[str, str]] | None = None,
    connections: list[tuple[str, str]] | None = None,
    inventory: list[tuple[str, str]] | None = None,
    location_id: str = "loc_a",
) -> GameState:
    """Build a minimal GameState with the player at `location_id`, optional
    co-located NPCs, optional outgoing connections, optional player inventory."""
    s = GameState(game_id="t", profile="default", player_id="player_01")
    s.locations[location_id] = Location(
        id=location_id,
        name="현장",
        connections=[Connection(target_id=cid) for cid, _ in (connections or [])],
    )
    for cid, cname in connections or []:
        s.locations[cid] = Location(id=cid, name=cname)
    inv_ids: list[str] = []
    for item_id, item_name in inventory or []:
        s.items[item_id] = Item(id=item_id, name=item_name)
        inv_ids.append(item_id)
    s.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        gender="male",
        stats=Stats(),
        location_id=location_id,
        inventory_ids=inv_ids,
    )
    for npc_id, npc_name in npcs or []:
        s.characters[npc_id] = Character(
            id=npc_id,
            name=npc_name,
            race_id="human",
            gender="male",
            stats=Stats(),
            location_id=location_id,
        )
    return s


def test_no_targets_yields_empty():
    state = _seed()
    assert build_suggestion_chips(state) == []


def test_one_npc_yields_one_chip():
    state = _seed(npcs=[("npc_1", "탈크")])
    assert build_suggestion_chips(state) == ["탈크에게 말을 건다"]


def test_one_connection_yields_one_chip():
    state = _seed(connections=[("loc_b", "광장")])
    assert build_suggestion_chips(state) == ["광장으로 이동한다"]


def test_one_inventory_item_yields_one_chip():
    state = _seed(inventory=[("item_1", "검")])
    assert build_suggestion_chips(state) == ["검을 살펴본다"]


def test_one_per_category_max_three():
    state = _seed(
        npcs=[("npc_1", "탈크")],
        connections=[("loc_b", "광장")],
        inventory=[("item_1", "검")],
    )
    chips = build_suggestion_chips(state)
    assert len(chips) == 3
    assert "탈크에게 말을 건다" in chips
    assert "광장으로 이동한다" in chips
    assert "검을 살펴본다" in chips


def test_npc_only_caps_at_one():
    """3 NPCs alone → 1 chip (one per category cap; no padding from same bucket)."""
    state = _seed(npcs=[("npc_1", "탈크"), ("npc_2", "마릴린"), ("npc_3", "에드릭")])
    chips = build_suggestion_chips(state)
    assert len(chips) == 1
    assert chips[0].endswith("에게 말을 건다")


def test_dead_npc_skipped():
    state = _seed(npcs=[("npc_1", "탈크")])
    state.characters["npc_1"].alive = False
    assert build_suggestion_chips(state) == []


def test_combat_state_yields_empty():
    state = _seed(
        npcs=[("npc_1", "탈크")],
        connections=[("loc_b", "광장")],
        inventory=[("item_1", "검")],
    )
    state.combat_state = CombatState()
    assert build_suggestion_chips(state) == []


def test_downed_recovered_signal_yields_empty():
    state = _seed(
        npcs=[("npc_1", "탈크")],
        connections=[("loc_b", "광장")],
        inventory=[("item_1", "검")],
    )
    state.previous_phase_signal = "downed_recovered"
    assert build_suggestion_chips(state) == []


def test_josa_picks_eul_for_jongseong_item():
    """검 has 받침 → 을, not 를."""
    state = _seed(inventory=[("item_1", "검")])
    assert build_suggestion_chips(state) == ["검을 살펴본다"]


def test_josa_picks_reul_for_no_jongseong_item():
    """모자 has no 받침 → 를, not 을."""
    state = _seed(inventory=[("item_1", "모자")])
    assert build_suggestion_chips(state) == ["모자를 살펴본다"]
