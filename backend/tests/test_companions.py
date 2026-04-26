"""동반자 시스템 (P3 §2.9) — 위치 동기화 + combat 합류 + 진영 기반 적 식별."""
import random

from src.domain.entities import Character, CombatBehavior, Stats
from src.pipeline import combat as combat_eng
from src.pipeline.apply import apply_changes


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


# --- 위치 동기화 ----------------------------------------------------------


def test_apply_move_drags_companions(fresh_state):
    p = _player(companions=["pet_01"])
    pet = _npc("pet_01", location_id="plaza_01")
    fresh_state.characters["player_01"] = p
    fresh_state.characters["pet_01"] = pet
    from src.domain.entities import Location

    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.locations["gate_01"] = Location(id="gate_01", name="성문")

    dirty: set[tuple[str, str]] = set()
    result = apply_changes(
        fresh_state,
        [{"type": "move", "target": "player_01", "destination": "gate_01"}],
        dirty,
    )
    assert result["applied"] == 1
    assert p.location_id == "gate_01"
    assert pet.location_id == "gate_01"  # 동반자 따라옴
    assert ("characters", "pet_01") in dirty


# --- combat 자동 합류 -----------------------------------------------------


def test_start_combat_auto_includes_player_companions(fresh_state):
    p = _player(companions=["pet_01"])
    pet = _npc("pet_01")
    enemy = _npc("goblin_01")
    fresh_state.characters.update({"player_01": p, "pet_01": pet, "goblin_01": enemy})

    cs = combat_eng.start_combat(fresh_state, ["goblin_01"], rng=random.Random(0))
    assert set(cs.turn_order) == {"player_01", "pet_01", "goblin_01"}
    # enemy_ids 는 명시한 그대로 — 동반자 안 들어감
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
    # pet 이 enemy 로도 명시 (이상한 케이스지만 dedupe 검증)
    cs = combat_eng.start_combat(fresh_state, ["pet_01"], rng=random.Random(0))
    assert cs.turn_order.count("pet_01") == 1


# --- 진영 기반 적 식별 ----------------------------------------------------


def test_player_companion_targets_enemy_side(fresh_state):
    """플레이어 동반자가 npc_target 으로 enemy 를 고른다 (player 가 아닌)."""
    p = _player(companions=["pet_01"])
    pet = _npc("pet_01", combat_behavior=CombatBehavior(attack_priority="nearest"))
    enemy = _npc("goblin_01")
    fresh_state.characters.update({"player_01": p, "pet_01": pet, "goblin_01": enemy})
    combat_eng.start_combat(fresh_state, ["goblin_01"], rng=random.Random(0))

    target = combat_eng.pick_npc_target(fresh_state, "pet_01", rng=random.Random(0))
    assert target is not None
    assert target.id == "goblin_01"  # 같은 patron (player) 인 player 는 안 침


def test_enemy_companion_targets_player_side(fresh_state):
    """적 동반자가 player 또는 player.companion 을 고른다."""
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

    target = combat_eng.pick_npc_target(
        fresh_state, "minion_01", rng=random.Random(0)
    )
    assert target is not None
    assert target.id in {"player_01", "pet_01"}  # 같은 patron (boss) 인 boss 는 안 침
