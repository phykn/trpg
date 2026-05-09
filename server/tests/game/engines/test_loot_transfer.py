"""Verify dead entity's loot transfers to the killer."""

from src.game.domain.entities import Character, Equipment
from src.game.engines.combat import transfer_loot_on_death
from src.game.engines.invariants import check_item_locality


def _make_char(
    id_: str,
    inventory_ids: list[str],
    gold: int,
    equipment: Equipment | None = None,
) -> Character:
    return Character.model_construct(
        id=id_,
        name=id_,
        race_id="human",
        inventory_ids=list(inventory_ids),
        gold=gold,
        equipment=equipment or Equipment(),
    )


def test_dead_entity_loot_to_killer():
    """inventory_ids + gold move from dead to winner."""
    dead = _make_char("enemy", ["녹슨 도끼", "조잡한 가죽 조끼"], 5)
    winner = _make_char("player", ["정찰병의 단검"], 15)
    transfer_loot_on_death(dead=dead, winner=winner)
    assert "녹슨 도끼" in winner.inventory_ids
    assert "조잡한 가죽 조끼" in winner.inventory_ids
    assert winner.gold == 20
    assert dead.inventory_ids == []
    assert dead.gold == 0


def test_empty_inventory_no_op():
    """Empty inventory + zero gold → no error, winner unchanged."""
    dead = _make_char("enemy", [], 0)
    winner = _make_char("player", ["x"], 1)
    transfer_loot_on_death(dead=dead, winner=winner)
    assert winner.inventory_ids == ["x"]
    assert winner.gold == 1


def test_gold_only_transfer():
    """No inventory items, only gold transfers."""
    dead = _make_char("enemy", [], 50)
    winner = _make_char("player", [], 10)
    transfer_loot_on_death(dead=dead, winner=winner)
    assert winner.gold == 60
    assert dead.gold == 0
    assert winner.inventory_ids == []


def test_dead_entity_equipped_items_unequipped_to_winner():
    """Equipped items on the corpse must clear from equipment slots and land in
    winner's inventory only — not stay referenced by both, which would trip the
    locality invariant guard and (pre-fix) leak an English warning to the GM log
    while erasing the loot from the player."""
    dead = _make_char(
        "edrik_chief",
        ["chief_robe", "chief_signet"],
        0,
        equipment=Equipment(armor="chief_robe", accessory="chief_signet"),
    )
    winner = _make_char("player_01", [], 0)
    transfer_loot_on_death(dead=dead, winner=winner)
    assert winner.inventory_ids == ["chief_robe", "chief_signet"]
    assert dead.inventory_ids == []
    assert dead.equipment.armor is None
    assert dead.equipment.accessory is None
    assert dead.equipment.weapon is None


def test_transfer_marks_both_entities_dirty():
    """Loot transfer mutates winner inventory/gold and dead equipment/inventory;
    both must be added to dirty.entities so Supabase persists the change. Skip
    this and a companion-kill (no kill XP) silently loses the loot on reload."""
    dead = _make_char("enemy", ["sword"], 5)
    winner = _make_char("companion", [], 0)
    dirty: set[tuple[str, str]] = set()
    transfer_loot_on_death(dead=dead, winner=winner, dirty=dirty)
    assert ("characters", "companion") in dirty
    assert ("characters", "enemy") in dirty


def test_transfer_dirty_optional():
    """Without `dirty`, the function still transfers loot — used by older tests
    and combat paths where the caller dirties separately."""
    dead = _make_char("enemy", ["sword"], 5)
    winner = _make_char("player", [], 0)
    transfer_loot_on_death(dead=dead, winner=winner)
    assert "sword" in winner.inventory_ids
    assert winner.gold == 5


def test_winner_already_owns_same_item_no_duplicate():
    """If killer already owns the same item id, transfer must not push a second
    copy into inventory_ids — duplicates within a single inventory still trip the
    locality guard. The corpse's copy is dropped; winner keeps theirs."""
    dead = _make_char("enemy", ["chief_robe"], 0)
    winner = _make_char("player_01", ["chief_robe"], 0)
    transfer_loot_on_death(dead=dead, winner=winner)
    assert winner.inventory_ids == ["chief_robe"]
    assert dead.inventory_ids == []


def test_loot_transfer_leaves_state_locality_clean():
    """End-to-end: after transfer, check_item_locality reports zero violations
    so narrate's enforcer never has to fire an auto-repair (which used to leak
    the English 'item X was duplicated' line into the player's GM log)."""
    from src.game.domain.entities import Item, Location, Race, Stats
    from src.game.domain.state import GameState

    state = GameState(game_id="g_test", profile="p_test", player_id="player_01")
    state.races["race_human"] = Race(id="race_human", name="인간", description="d")
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.items["chief_robe"] = Item(
        id="chief_robe", name="촌장의 외투", weight=1, price=10
    )
    state.items["chief_signet"] = Item(
        id="chief_signet", name="촌장의 인장", weight=1, price=10
    )

    player = Character(
        id="player_01",
        name="당신",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
        is_player=True,
    )
    player.max_hp = player.hp = 20
    player.max_mp = player.mp = 10
    state.characters["player_01"] = player

    dead = Character(
        id="edrik_chief",
        name="에드릭",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
        inventory_ids=["chief_robe", "chief_signet"],
        equipment=Equipment(armor="chief_robe", accessory="chief_signet"),
    )
    dead.max_hp = dead.hp = 10
    dead.max_mp = dead.mp = 5
    dead.alive = False
    state.characters["edrik_chief"] = dead

    transfer_loot_on_death(dead=dead, winner=player)

    assert check_item_locality(state) == []
