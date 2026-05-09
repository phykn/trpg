"""Behavior test: in-combat trade/gift transfer is rejected.

`run_combat_player_turn` routes a `transfer(mode=trade)` or `mode=gift` Verb
through `_judge_to_player_action`, which returns None for non-equip transfer.
The dispatcher then surfaces ACTION_FORBIDDEN_IN_COMBAT_TEXT and finalizes
the turn without entering the auto-sim — the equip/unequip passive path stays
the only allowed in-combat transfer."""

import pytest

from src.game.domain.entities import Character, Item, Stats
from src.game.domain.state import CombatState
from src.game.flow.format import ACTION_FORBIDDEN_IN_COMBAT_TEXT
from src.game.flow.turn import run_turn
from src.llm.calls.classify.schema import Verb
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


def _setup_in_combat_state(fresh_state):
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=20,
        max_hp=20,
        inventory_ids=["potion_01"],  # ssot-allow: test setup
    )
    fresh_state.characters["npc.goblin"] = Character(
        id="npc.goblin",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=10,
    )
    fresh_state.items["potion_01"] = Item(
        id="potion_01",
        name="치료 물약",
    )
    fresh_state.combat_state = CombatState(
        turn_order=["player_01", "npc.goblin"],
        enemy_ids=["npc.goblin"],
    )
    return fresh_state


@pytest.mark.parametrize("mode", ["trade", "gift"])
async def test_in_combat_transfer_trade_or_gift_is_forbidden(
    fresh_state, tmp_data, judge_returns, collect, mode
):
    state = _setup_in_combat_state(fresh_state)
    judge_returns(
        Verb(
            name="transfer",
            modifiers={
                "mode": mode,
                "from_id": "player_01",
                "to_id": "npc.goblin",
                "item_id": "potion_01",
            },
        )
    )

    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="물약을 건넨다",
        )
    )

    forbidden_acts = [
        ev
        for ev in events
        if ev.get("type") == "log_entry"
        and (ev.get("data") or {}).get("kind") == "act"
        and (ev.get("data") or {}).get("text") == ACTION_FORBIDDEN_IN_COMBAT_TEXT
    ]
    assert len(forbidden_acts) == 1, (
        f"expected one ACTION_FORBIDDEN_IN_COMBAT_TEXT act for mode={mode}, "
        f"got {len(forbidden_acts)}"
    )
    assert state.combat_state is not None, (
        "combat_state must persist after rejection — auto-sim was not run"
    )
    assert state.items["potion_01"].id in state.characters["player_01"].inventory_ids, (
        "potion stays with player — no transfer was applied"
    )
