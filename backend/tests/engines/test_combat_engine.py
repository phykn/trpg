"""S2 — combat engine core unit tests. No LLM calls, deterministic RNG."""
import random

import pytest

from src.domain.entities import (
    ArmorEffect,
    Character,
    CombatBehavior,
    Equipment,
    Item,
    Skill,
    Stats,
    WeaponEffect,
)
from src.engines.combat import (
    AttackOutcome,
    attack,
    enemy_defense,
    pick_target,
    primary_stat_for_weapon,
    roll_dice,
    roll_initiative,
    should_attempt_flee,
    stat_modifier,
    try_flee,
)


# --- Deterministic RNG helpers -----------------------------------------------


class _SeqRandom(random.Random):
    """randint stub returning a fixed sequence in order. Other methods (choice, etc.) still work via super()."""

    def __init__(self, seq, *, seed=0):
        super().__init__(seed)
        self._seq = list(seq)

    def randint(self, lo, hi):
        if not self._seq:
            raise AssertionError("randint sequence exhausted")
        v = self._seq.pop(0)
        assert lo <= v <= hi, f"stubbed {v} outside [{lo}, {hi}]"
        return v


def _wpn_item(id_: str, dice: str = "1d8", range_m: float = 1.5, two_handed: bool = False) -> Item:
    return Item(
        id=id_,
        name=id_,
        effects=WeaponEffect(type="weapon", weapon_dice=dice, range=range_m, two_handed=two_handed),
    )


def _arm_item(id_: str, defense: int) -> Item:
    return Item(id=id_, name=id_, effects=ArmorEffect(type="armor", defense=defense))


def _char(
    id_: str,
    *,
    str_: int = 10,
    dex: int = 10,
    hp: int = 20,
    max_hp: int = 20,
    location: str | None = "loc_01",
    equipment: Equipment | None = None,
    behavior: CombatBehavior | None = None,
    dominant: str = "right",
    skills: list[Skill] | None = None,
) -> Character:
    return Character(
        id=id_,
        name=id_,
        race_id="human",
        stats=Stats(STR=str_, DEX=dex, CON=10, INT=10, WIS=10, CHA=10),
        hp=hp,
        max_hp=max_hp,
        location_id=location,
        equipment=equipment or Equipment(),
        combat_behavior=behavior,
        dominant_hand=dominant,  # type: ignore[arg-type]
        learned_skills=skills or [],
    )


# --- Unit helpers ------------------------------------------------------------


def test_stat_modifier_dnd5e_table():
    assert stat_modifier(0) == -5
    assert stat_modifier(8) == -1
    assert stat_modifier(9) == -1
    assert stat_modifier(10) == 0
    assert stat_modifier(11) == 0
    assert stat_modifier(12) == 1
    assert stat_modifier(20) == 5


def test_roll_dice_specs():
    rng = random.Random(42)
    # 1d1 → always 1
    assert roll_dice("1d1", rng) == 1
    # 2d1+3 → always 5
    assert roll_dice("2d1+3", rng) == 5
    # 1d1-1 → always 0
    assert roll_dice("1d1-1", rng) == 0
    # malformed spec
    with pytest.raises(ValueError):
        roll_dice("d8", rng)
    with pytest.raises(ValueError):
        roll_dice("1x8", rng)


def test_primary_stat_by_range():
    assert primary_stat_for_weapon_for_range(1.0) == "STR"
    assert primary_stat_for_weapon_for_range(1.5) == "STR"
    assert primary_stat_for_weapon_for_range(1.6) == "DEX"
    assert primary_stat_for_weapon_for_range(20.0) == "DEX"


def primary_stat_for_weapon_for_range(r: float) -> str:
    """convenience for the table check above — wraps the engine helper."""
    from src.engines.combat import _Weapon
    return primary_stat_for_weapon(_Weapon(item_id="x", dice="1d4", range_m=r, two_handed=False))


def test_enemy_defense_sums_armor_slots_only():
    items = {
        "helm": _arm_item("helm", defense=2),
        "boots": _arm_item("boots", defense=1),
        "shield": _arm_item("shield", defense=3),
        "ring": Item(id="ring", name="ring"),  # no effect
        "sword": _wpn_item("sword"),  # weapons do not contribute to defense even when held
    }
    defender = _char(
        "d",
        equipment=Equipment(head="helm", feet="boots", leftHand="sword", acc1="ring"),
    )
    assert enemy_defense(defender, items) == 10 + 2 + 1  # helm + boots only

    # acc1/leftHand are outside the 4 armor slots — they do not add defense.
    # Even with a shield in leftHand, defense sums only head/top/bottom/feet.
    defender2 = _char("d2", equipment=Equipment(leftHand="shield"))
    assert enemy_defense(defender2, items) == 10


# --- attack -------------------------------------------------------------------


def test_attack_unarmed_no_weapon_uses_str_and_1d4():
    """Empty hands with no weapon → STR-based + 1d4 damage. nat=15 hits, dice=3."""
    attacker = _char("a", str_=14)  # STR mod = +2
    defender = _char("d")
    # randint sequence: [nat_d20=15, damage_d4=3]
    rng = _SeqRandom([15, 3])
    outs = attack(attacker, defender, items={}, rng=rng)
    assert len(outs) == 1
    o = outs[0]
    assert o.weapon_id is None
    assert o.primary_stat == "STR"
    assert o.nat_d20 == 15
    assert o.mod == 2
    assert o.total == 17
    assert o.grade == "success"
    assert o.damage == 3 + 2  # 1d4=3, +STR mod


def test_attack_critical_doubles_dice_keeps_mod_once():
    """nat 20 → critical_success, damage = (n+n) dice + mod (added once)."""
    attacker = _char("a", str_=14, equipment=Equipment(rightHand="sword_01"))
    defender = _char("d")
    items = {"sword_01": _wpn_item("sword_01", dice="1d8")}
    # nat=20, first d8=4, crit extra d8=7. damage = 4+7+2 = 13.
    rng = _SeqRandom([20, 4, 7])
    [o] = attack(attacker, defender, items, rng=rng)
    assert o.grade == "critical_success"
    assert o.damage == 13


def test_attack_natural_one_is_critical_failure_zero_damage():
    attacker = _char("a", str_=14, equipment=Equipment(rightHand="sword_01"))
    defender = _char("d")
    items = {"sword_01": _wpn_item("sword_01")}
    rng = _SeqRandom([1])
    [o] = attack(attacker, defender, items, rng=rng)
    assert o.grade == "critical_failure"
    assert o.damage == 0


def test_attack_dual_wield_off_hand_loses_modifier():
    """Main hand adds mod, off-hand drops the mod and rolls dice only."""
    attacker = _char(
        "a",
        str_=14,  # mod +2
        equipment=Equipment(rightHand="main", leftHand="off"),
        dominant="right",
    )
    defender = _char("d")
    items = {
        "main": _wpn_item("main", dice="1d6"),
        "off": _wpn_item("off", dice="1d6"),
    }
    # main: nat=15, d6=4 → damage = 4 + 2 = 6
    # off:  nat=12, d6=3 → damage = 3 (no mod)
    rng = _SeqRandom([15, 4, 12, 3])
    outs = attack(attacker, defender, items, rng=rng)
    assert [o.hand for o in outs] == ["main", "off"]
    assert outs[0].damage == 6
    assert outs[1].damage == 3


def test_attack_two_handed_weapon_one_swing_only():
    attacker = _char("a", str_=12, equipment=Equipment(rightHand="great"))
    defender = _char("d")
    items = {"great": _wpn_item("great", dice="2d6", two_handed=True)}
    rng = _SeqRandom([15, 4, 5])
    outs = attack(attacker, defender, items, rng=rng)
    assert len(outs) == 1
    assert outs[0].weapon_id == "great"
    assert outs[0].damage == 4 + 5 + 1  # 2d6 + STR mod (+1 from STR=12)


def test_attack_ranged_weapon_uses_dex():
    attacker = _char("a", str_=8, dex=16, equipment=Equipment(rightHand="bow"))  # STR mod -1, DEX mod +3
    defender = _char("d")
    items = {"bow": _wpn_item("bow", dice="1d8", range_m=20.0)}
    rng = _SeqRandom([15, 5])
    [o] = attack(attacker, defender, items, rng=rng)
    assert o.primary_stat == "DEX"
    assert o.mod == 3
    assert o.damage == 5 + 3


def test_attack_armor_raises_required_roll():
    """Heavier armor can split grade outcomes for the same nat."""
    attacker = _char("a", str_=10)  # mod 0
    light = _char("d_light")
    heavy = _char(
        "d_heavy",
        equipment=Equipment(head="h", top="t", bottom="b", feet="f"),
    )
    items = {
        "h": _arm_item("h", 3),
        "t": _arm_item("t", 3),
        "b": _arm_item("b", 3),
        "f": _arm_item("f", 3),
    }
    # defense_light = 10, defense_heavy = 22.
    # required_roll(10, 10, k=0.5) = round(20/(1+1)) = 10
    # required_roll(22, 10, k=0.5) = round(20/(1+e^-6)) ≈ 20
    # nat=11 → clears 10 (partial or success), but fails against 22.
    rng_light = _SeqRandom([11, 4])
    rng_heavy = _SeqRandom([11])  # miss → no damage roll
    [ol] = attack(attacker, light, items, rng=rng_light)
    [oh] = attack(attacker, heavy, items, rng=rng_heavy)
    assert ol.required_roll < oh.required_roll
    assert ol.grade in ("success", "partial_success")
    assert oh.grade == "failure"
    assert oh.damage == 0


# --- Initiative --------------------------------------------------------------


def test_initiative_sorts_descending_by_d20_plus_dex_mod():
    a = _char("a", dex=10)  # mod 0
    b = _char("b", dex=18)  # mod +4
    c = _char("c", dex=14)  # mod +2
    rng = _SeqRandom([10, 12, 8])  # a:10, b:16, c:10
    order = roll_initiative([a, b, c], rng=rng)
    # b: 12+4=16, a: 10+0=10, c: 8+2=10
    # tiebreak: higher raw DEX first → c(14) before a(10)
    assert order == ["b", "c", "a"]


def test_initiative_id_alphabetical_tiebreak_when_dex_equal():
    a = _char("alpha", dex=10)
    b = _char("beta", dex=10)
    rng = _SeqRandom([10, 10])  # both 10
    order = roll_initiative([a, b], rng=rng)
    assert order == ["alpha", "beta"]


# --- pick_target --------------------------------------------------------------


def test_pick_target_filters_dead_self_and_other_locations():
    actor = _char("actor", behavior=CombatBehavior(attack_priority="random"))
    here_alive = _char("h1")
    here_dead = _char("h2")
    here_dead.alive = False
    elsewhere = _char("e1", location="other_loc")
    rng = random.Random(0)
    result = pick_target(actor, [actor, here_alive, here_dead, elsewhere], rng=rng)
    assert result is not None and result.id == "h1"


def test_pick_target_empty_pool_returns_none():
    actor = _char("actor")
    assert pick_target(actor, [actor], rng=random.Random(0)) is None


def test_pick_target_nearest_returns_first_in_pool():
    actor = _char("actor", behavior=CombatBehavior(attack_priority="nearest"))
    pool = [actor, _char("first"), _char("second"), _char("third")]
    assert pick_target(actor, pool).id == "first"


def test_pick_target_lowest_hp():
    actor = _char("actor", behavior=CombatBehavior(attack_priority="lowest_hp"))
    pool = [actor, _char("a", hp=20), _char("b", hp=5), _char("c", hp=10)]
    assert pick_target(actor, pool).id == "b"


def test_pick_target_healer_first_prefers_heal_skill_holder():
    healer_skill = Skill(id="heal_01", name="치유", type="heal", target="single", primary_stat="WIS")
    healer = _char("doc", hp=20, skills=[healer_skill])
    tank = _char("tank", hp=10)
    actor = _char("actor", behavior=CombatBehavior(attack_priority="healer_first"))
    pool = [actor, tank, healer]
    assert pick_target(actor, pool).id == "doc"


def test_pick_target_healer_first_falls_back_to_lowest_hp_when_no_healer():
    actor = _char("actor", behavior=CombatBehavior(attack_priority="healer_first"))
    pool = [actor, _char("a", hp=20), _char("b", hp=5)]
    assert pick_target(actor, pool).id == "b"


def test_pick_target_random_uses_rng_uniform():
    actor = _char("actor", behavior=CombatBehavior(attack_priority="random"))
    pool = [actor, _char("a"), _char("b"), _char("c")]
    rng = random.Random(0)
    picks = {pick_target(actor, pool, rng=rng).id for _ in range(40)}
    assert picks == {"a", "b", "c"}


def test_pick_target_weighted_mode_with_zero_random_always_nearest():
    actor = _char(
        "actor",
        behavior=CombatBehavior(attack_priority=None, nearest_weight=100, random_weight=0),
    )
    pool = [actor, _char("first"), _char("second"), _char("third")]
    rng = random.Random(0)
    for _ in range(20):
        assert pick_target(actor, pool, rng=rng).id == "first"


def test_pick_target_no_behavior_falls_back_to_first():
    actor = _char("actor", behavior=None)
    pool = [actor, _char("first"), _char("second")]
    assert pick_target(actor, pool, rng=random.Random(0)).id == "first"


def test_pick_target_highest_threat_uses_damage_dealt():
    """Pick the candidate with the highest damage_dealt — fall back to nearest when no data."""
    actor = _char("actor", behavior=CombatBehavior(attack_priority="highest_threat"))
    pool = [actor, _char("a", hp=20), _char("b", hp=20), _char("c", hp=20)]
    damage_dealt = {"a": 5, "b": 12, "c": 3}
    assert pick_target(actor, pool, damage_dealt=damage_dealt).id == "b"


def test_pick_target_highest_threat_no_damage_falls_back_to_nearest():
    actor = _char("actor", behavior=CombatBehavior(attack_priority="highest_threat"))
    pool = [actor, _char("first"), _char("second")]
    assert pick_target(actor, pool, damage_dealt={}).id == "first"


def test_pick_target_highest_threat_tiebreaker_lowest_hp():
    """Tied damage breaks toward the lower-hp candidate."""
    actor = _char("actor", behavior=CombatBehavior(attack_priority="highest_threat"))
    pool = [actor, _char("a", hp=20), _char("b", hp=5)]
    damage_dealt = {"a": 10, "b": 10}
    assert pick_target(actor, pool, damage_dealt=damage_dealt).id == "b"


# --- flee ---------------------------------------------------------------------


def test_should_attempt_flee_above_threshold_returns_false():
    actor = _char("a", hp=15, max_hp=20, behavior=CombatBehavior(flee_hp_percent=50))
    assert should_attempt_flee(actor, rng=random.Random(0)) is False


def test_should_attempt_flee_below_threshold_uses_probability():
    # hp 10/20 = 50%, threshold 60% → diff 10 → prob 20%.
    # If the first randint(1,100) call from _SeqRandom returns ≤ 20, expect True.
    actor = _char("a", hp=10, max_hp=20, behavior=CombatBehavior(flee_hp_percent=60))
    assert should_attempt_flee(actor, rng=_SeqRandom([15])) is True
    assert should_attempt_flee(actor, rng=_SeqRandom([21])) is False


def test_should_attempt_flee_no_behavior_returns_false():
    actor = _char("a", behavior=None)
    assert should_attempt_flee(actor) is False


def test_try_flee_passes_when_roll_meets_dc():
    actor = _char("a", dex=14)  # DEX mod +2
    # 1d20=10 → 10+2 = 12 = base_dc → success
    ok, total = try_flee(actor, rng=_SeqRandom([10]))
    assert ok is True
    assert total == 12


def test_try_flee_fails_when_below_dc():
    actor = _char("a", dex=10)
    ok, total = try_flee(actor, rng=_SeqRandom([5]))
    assert ok is False
    assert total == 5


# --- AttackOutcome shape ------------------------------------------------------


def test_attack_outcome_shape():
    o = AttackOutcome(
        hand="main",
        weapon_id=None,
        primary_stat="STR",
        nat_d20=10,
        mod=0,
        total=10,
        required_roll=10,
        grade="partial_success",
        damage=2,
    )
    assert o.weapon_id is None
    assert o.grade == "partial_success"


# --- Lifecycle ---------------------------------------------------------------


from src.domain.entities import DeathSaveState
from src.domain.state import CombatState
from src.engines.combat import (
    advance_turn,
    apply_attack_to_defender,
    check_combat_end,
    current_actor_id,
    end_combat,
    pick_npc_target,
    remove_from_combat,
    start_combat,
    tick_death_save,
)
from src.domain.state import GameState


def _state_with(
    *chars: Character,
    items: dict | None = None,
    player_id: str = "p",
) -> GameState:
    s = GameState(
        game_id="g",
        profile="default",
        player_id=player_id,
        world_time="0812-01-01T00:00:00",
        characters={c.id: c for c in chars},
        items=items or {},
    )
    return s


def _player(id_: str = "p", **kw) -> Character:
    c = _char(id_, **kw)
    c.is_player = True
    return c


def test_start_combat_seeds_state_and_orders_initiative():
    p = _player(dex=14)  # mod +2
    g = _char("g", dex=10)  # mod 0
    state = _state_with(p, g, player_id="p")
    rng = _SeqRandom([15, 12])  # p:15+2=17, g:12+0=12
    cs = start_combat(state, ["g"], rng=rng)
    assert state.combat_state is cs
    assert cs.turn_order == ["p", "g"]
    assert cs.enemy_ids == ["g"]
    assert cs.round == 1
    assert cs.current_turn == 0
    assert cs.surprise is None


def test_current_actor_and_advance_turn_wraps_round():
    p = _player()
    g1 = _char("g1")
    g2 = _char("g2")
    state = _state_with(p, g1, g2, player_id="p")
    state.combat_state = CombatState(
        turn_order=["p", "g1", "g2"], enemy_ids=["g1", "g2"]
    )
    assert current_actor_id(state) == "p"
    advance_turn(state)
    assert current_actor_id(state) == "g1"
    advance_turn(state)
    assert current_actor_id(state) == "g2"
    advance_turn(state)  # full loop → round +1
    assert current_actor_id(state) == "p"
    assert state.combat_state.round == 2


def test_remove_from_combat_corrects_current_turn():
    p = _player()
    g1 = _char("g1")
    g2 = _char("g2")
    state = _state_with(p, g1, g2, player_id="p")
    state.combat_state = CombatState(turn_order=["p", "g1", "g2"], current_turn=2, enemy_ids=["g1", "g2"])
    remove_from_combat(state, "g1")  # remove index 1 (before current turn 2)
    assert state.combat_state.turn_order == ["p", "g2"]
    assert state.combat_state.enemy_ids == ["g2"]
    assert state.combat_state.current_turn == 1  # g2 is now at index 1, same actor


def test_apply_attack_to_defender_npc_dies_on_zero_hp():
    g = _char("g", hp=5, max_hp=10)
    state = _state_with(_player(), g, player_id="p")
    dirty: set = set()
    out = apply_attack_to_defender(state, "g", damage=10, dirty=dirty)
    assert out["dead"] is True
    assert g.alive is False
    assert g.hp == 0
    assert ("characters", "g") in dirty


def test_apply_attack_to_player_uses_revive_coin():
    p = _player(hp=5, max_hp=20)
    p.revive_coins = 1
    state = _state_with(p, _char("g"), player_id="p")
    out = apply_attack_to_defender(state, "p", damage=10)
    assert out["revived"] is True
    assert p.alive is True
    assert p.revive_coins == 0
    # max_hp * revive_ratio = 20 * 0.5 = 10
    assert p.hp == 10


def test_apply_attack_to_player_starts_death_save_when_no_coin():
    p = _player(hp=5, max_hp=20)
    p.revive_coins = 0
    state = _state_with(p, _char("g"), player_id="p")
    out = apply_attack_to_defender(state, "p", damage=10)
    assert out["dying"] is True
    assert out["dead"] is False
    assert p.alive is True
    assert p.hp == 0
    assert p.death_saves == DeathSaveState(successes=0, failures=0)


def test_extra_damage_during_death_save_increments_failures():
    p = _player(hp=0, max_hp=20)
    p.death_saves = DeathSaveState(successes=1, failures=1)
    state = _state_with(p, _char("g"), player_id="p")
    out = apply_attack_to_defender(state, "p", damage=3, nat_d20=1)  # crit fail
    # Normal hit +1, crit +2 — nat_d20=1 so +2 → failures 1+2=3 → death
    assert out["dead"] is True
    assert p.alive is False


def test_tick_death_save_three_successes_stabilize():
    p = _player(hp=0, max_hp=20)
    p.death_saves = DeathSaveState(successes=2, failures=0)
    state = _state_with(p, _char("g"), player_id="p")
    status, roll = tick_death_save(state, "p", rng=_SeqRandom([15]))
    assert status == "stable"
    assert p.hp == 1  # auto_revive_hp default
    assert p.death_saves is None


def test_tick_death_save_three_failures_dies():
    p = _player(hp=0, max_hp=20)
    p.death_saves = DeathSaveState(successes=0, failures=2)
    state = _state_with(p, _char("g"), player_id="p")
    status, roll = tick_death_save(state, "p", rng=_SeqRandom([5]))
    assert status == "dead"
    assert p.alive is False
    assert p.death_saves is None


def test_tick_death_save_progress_keeps_dying():
    p = _player(hp=0, max_hp=20)
    p.death_saves = DeathSaveState(successes=0, failures=0)
    state = _state_with(p, _char("g"), player_id="p")
    status, _ = tick_death_save(state, "p", rng=_SeqRandom([15]))
    assert status == "progress"
    assert p.death_saves is not None
    assert p.death_saves.successes == 1


def test_check_combat_end_victory_when_enemies_dead():
    p = _player()
    g = _char("g")
    g.alive = False
    state = _state_with(p, g, player_id="p")
    state.combat_state = CombatState(turn_order=["p"], enemy_ids=["g"])
    assert check_combat_end(state) == "victory"


def test_check_combat_end_defeat_when_player_dead():
    p = _player()
    p.alive = False
    g = _char("g")
    state = _state_with(p, g, player_id="p")
    state.combat_state = CombatState(turn_order=["p", "g"], enemy_ids=["g"])
    assert check_combat_end(state) == "defeat"


def test_check_combat_end_none_when_both_alive():
    p = _player()
    g = _char("g")
    state = _state_with(p, g, player_id="p")
    state.combat_state = CombatState(turn_order=["p", "g"], enemy_ids=["g"])
    assert check_combat_end(state) is None


def test_pick_npc_target_for_enemy_picks_player():
    g = _char("g", behavior=CombatBehavior(attack_priority="nearest"))
    p = _player()
    state = _state_with(p, g, player_id="p")
    state.combat_state = CombatState(turn_order=["p", "g"], enemy_ids=["g"])
    chosen = pick_npc_target(state, "g")
    assert chosen is not None and chosen.id == "p"


def test_end_combat_clears_state():
    p = _player()
    state = _state_with(p, player_id="p")
    state.combat_state = CombatState(turn_order=["p"])
    end_combat(state)
    assert state.combat_state is None
