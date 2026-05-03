"""Chain action with CombatAction at the tail — engine runs prefix parts
(equip / move / etc.) then transitions to the combat phase. Without the tail
combat handling, classify chain output gets stripped (combat dropped, narrate
hallucinates the attack outcome) — the live-test bug being fixed here."""

import random

import pytest

from src.domain.entities import (
    Character,
    CombatBehavior,
    Connection,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.flow.turn import run_turn
from src.llm_calls.classify.schema import (
    ChainAction,
    CombatAction,
    EquipAction,
    MoveAction,
)
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


@pytest.fixture
def chain_combat_state(fresh_state):
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="광장",
        connections=[Connection(target_id="forge_01")],
    )
    fresh_state.locations["forge_01"] = Location(id="forge_01", name="대장간")
    fresh_state.items["dagger_01"] = Item(
        id="dagger_01",
        name="단검",
        effects=WeaponEffect(type="weapon", weapon_dice="1d6"),
    )
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=14, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=20,
        max_hp=20,
        inventory_ids=["dagger_01"],
    )
    fresh_state.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=8,
        max_hp=8,
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )
    fresh_state.characters["talc_01"] = Character(
        id="talc_01",
        name="탈크",
        race_id="human",
        location_id="forge_01",
        stats=Stats(STR=10, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=8,
        max_hp=8,
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )
    return fresh_state


async def test_chain_equip_then_attack_routes_to_combat(
    chain_combat_state, tmp_data, judge_returns, collect
):
    """[Equip, Combat] — engine equips the weapon then transitions to combat
    against the named target. Without the chain-tail handling, combat is
    dropped and narrate has to invent the attack outcome."""
    chain = ChainAction(
        action="chain",
        parts=[
            EquipAction(action="equip", item_id="dagger_01"),
            CombatAction(action="combat", targets=["goblin_01"]),
        ],
    )
    judge_returns(chain)

    events = await collect(
        run_turn(
            client=None,
            state=chain_combat_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="단검을 뽑아 공격한다",
            rng=random.Random(123),
        )
    )

    types = [e["type"] for e in events]
    assert "combat_start" in types, types
    # Equip prefix part actually ran — weapon now equipped.
    assert chain_combat_state.characters["player_01"].equipment.weapon == "dagger_01"
    # Goblin received damage or died.
    g = chain_combat_state.characters["goblin_01"]
    assert g.hp < 8 or not g.alive


async def test_chain_move_then_attack_at_destination(
    chain_combat_state, tmp_data, judge_returns, collect
):
    """[Move, Combat] — engine moves to the named location then attacks the
    target there. The live test failure: 'classify produced [MoveAction], dropped
    CombatAction; narrate then invented "공격을 단숨에 쳐냅니다"'. With combat at
    the chain tail, the attack actually fires."""
    chain = ChainAction(
        action="chain",
        parts=[
            MoveAction(action="move", destination="forge_01"),
            CombatAction(action="combat", targets=["talc_01"]),
        ],
    )
    judge_returns(chain)

    events = await collect(
        run_turn(
            client=None,
            state=chain_combat_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="대장간으로 가서 탈크를 공격한다",
            rng=random.Random(7),
        )
    )

    types = [e["type"] for e in events]
    assert "combat_start" in types, types
    # Move prefix part actually ran — player is in forge_01.
    assert chain_combat_state.characters["player_01"].location_id == "forge_01"
    # Talc received damage or died.
    t = chain_combat_state.characters["talc_01"]
    assert t.hp < 8 or not t.alive


async def test_chain_combat_invalid_target_does_not_double_consume_turn(
    chain_combat_state, tmp_data, judge_returns, collect
):
    """Tail Combat with an invalid target (different location, dead, missing)
    must not enter combat. Prefix parts still run, but no combat_start fires
    and combat_state stays clear — symmetrical with the standalone CombatAction
    invalid-target branch."""
    chain = ChainAction(
        action="chain",
        parts=[
            EquipAction(action="equip", item_id="dagger_01"),
            # talc_01 is in forge_01, player is in plaza_01 — invalid same-loc rule.
            CombatAction(action="combat", targets=["talc_01"]),
        ],
    )
    judge_returns(chain)

    events = await collect(
        run_turn(
            client=None,
            state=chain_combat_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="단검을 뽑고 탈크를 친다",
            rng=random.Random(1),
        )
    )

    types = [e["type"] for e in events]
    assert "combat_start" not in types, types
    assert chain_combat_state.combat_state is None
    # Equip prefix still ran — weapon is on the player.
    assert chain_combat_state.characters["player_01"].equipment.weapon == "dagger_01"


def test_chain_schema_accepts_combat_at_tail():
    """Schema-level: ChainAction validates [Equip, Combat]."""
    chain = ChainAction(
        action="chain",
        parts=[
            EquipAction(action="equip", item_id="sword_01"),
            CombatAction(action="combat", targets=["bandit_01"]),
        ],
    )
    assert len(chain.parts) == 2
    assert chain.parts[-1].action == "combat"


def test_chain_schema_rejects_combat_in_middle():
    """Schema-level: CombatAction in non-tail slot raises a validation error.
    Combat only valid at chain tail (engine runs prefix then transitions to
    combat phase)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ChainAction(
            action="chain",
            parts=[
                CombatAction(action="combat", targets=["bandit_01"]),
                EquipAction(action="equip", item_id="sword_01"),
            ],
        )
