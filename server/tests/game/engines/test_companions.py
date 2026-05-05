"""Companion system (P3 §2.9) — location sync + combat join + faction-based enemy targeting."""

import random

from src.game.domain.entities import Character, CombatBehavior, Stats
from src.game.engines import combat as combat_eng
from src.game.engines.apply import apply_changes


def _player(**kw):
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        location_id="plaza_01",
        hp=20,
        max_hp=20,
        relations={},
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def _npc(cid, **kw):
    n = Character(
        id=cid,
        name=cid,
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        hp=20,
        max_hp=20,
    )
    for k, v in kw.items():
        setattr(n, k, v)
    return n


# --- Location sync --------------------------------------------------------


def test_apply_move_drags_companions(fresh_state):
    p = _player(companions=["pet_01"])
    pet = _npc("pet_01", location_id="plaza_01")
    fresh_state.characters["player_01"] = p
    fresh_state.characters["pet_01"] = pet
    from src.game.domain.entities import Connection, Location

    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01", name="광장", connections=[Connection(target_id="gate_01")]
    )
    fresh_state.locations["gate_01"] = Location(
        id="gate_01", name="성문", connections=[Connection(target_id="plaza_01")]
    )

    dirty: set[tuple[str, str]] = set()
    result = apply_changes(
        fresh_state,
        [{"type": "move", "target": "player_01", "destination": "gate_01"}],
        dirty,
    )
    assert result["applied"] == 1
    assert p.location_id == "gate_01"
    assert pet.location_id == "gate_01"  # companion follows
    assert ("characters", "pet_01") in dirty


# --- Auto-join in combat --------------------------------------------------


def test_start_combat_auto_includes_player_companions(fresh_state):
    p = _player(companions=["pet_01"])
    pet = _npc("pet_01")
    enemy = _npc("goblin_01")
    fresh_state.characters.update({"player_01": p, "pet_01": pet, "goblin_01": enemy})

    cs = combat_eng.start_combat(fresh_state, ["goblin_01"], rng=random.Random(0))
    assert set(cs.turn_order) == {"player_01", "pet_01", "goblin_01"}
    # enemy_ids stays as supplied — companions do not enter it
    assert cs.enemy_ids == ["goblin_01"]


def test_start_combat_auto_includes_enemy_companions(fresh_state):
    p = _player()
    boss = _npc("boss_01", companions=["minion_01"])
    minion = _npc("minion_01")
    fresh_state.characters.update(
        {"player_01": p, "boss_01": boss, "minion_01": minion}
    )

    cs = combat_eng.start_combat(fresh_state, ["boss_01"], rng=random.Random(0))
    assert set(cs.turn_order) == {"player_01", "boss_01", "minion_01"}


def test_start_combat_dedupes_repeats(fresh_state):
    p = _player(companions=["pet_01"])
    pet = _npc("pet_01")
    fresh_state.characters.update({"player_01": p, "pet_01": pet})
    # pet is also listed as an enemy (weird case, but verifies dedupe)
    cs = combat_eng.start_combat(fresh_state, ["pet_01"], rng=random.Random(0))
    assert cs.turn_order.count("pet_01") == 1


# --- Faction-based enemy targeting ----------------------------------------


def test_player_companion_targets_enemy_side(fresh_state):
    """A player's companion targets an enemy via npc_target (not the player)."""
    p = _player(companions=["pet_01"])
    pet = _npc("pet_01", combat_behavior=CombatBehavior(attack_priority="nearest"))
    enemy = _npc("goblin_01")
    fresh_state.characters.update({"player_01": p, "pet_01": pet, "goblin_01": enemy})
    combat_eng.start_combat(fresh_state, ["goblin_01"], rng=random.Random(0))

    target = combat_eng.pick_npc_target(fresh_state, "pet_01", rng=random.Random(0))
    assert target is not None
    assert target.id == "goblin_01"  # does not hit the player (same patron)


def test_enemy_companion_targets_player_side(fresh_state):
    """An enemy's companion targets the player or one of player.companions."""
    p = _player(companions=["pet_01"])
    pet = _npc("pet_01")
    boss = _npc("boss_01", companions=["minion_01"])
    minion = _npc(
        "minion_01", combat_behavior=CombatBehavior(attack_priority="nearest")
    )
    fresh_state.characters.update(
        {
            "player_01": p,
            "pet_01": pet,
            "boss_01": boss,
            "minion_01": minion,
        }
    )
    combat_eng.start_combat(fresh_state, ["boss_01"], rng=random.Random(0))

    target = combat_eng.pick_npc_target(fresh_state, "minion_01", rng=random.Random(0))
    assert target is not None
    assert target.id in {"player_01", "pet_01"}  # does not hit boss (same patron)
