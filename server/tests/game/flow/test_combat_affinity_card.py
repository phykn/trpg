"""Affinity card emit during combat is suppressed; the relations mutation stays."""

from src.game.domain.entities import Character, Stats
from src.game.domain.state import CombatState, GameState
from src.game.engines.apply import apply_combat_affinity_drop
from src.game.flow.dirty import Dirty
from src.game.rules import RULES


def _state_with_two_chars() -> GameState:
    state = GameState(game_id="g", profile="p", player_id="player_01")
    state.characters["player_01"] = Character(
        id="player_01", name="주인공", race_id="human", is_player=True, stats=Stats()
    )
    state.characters["npc_01"] = Character(
        id="npc_01", name="고블린", race_id="goblin", stats=Stats()
    )
    return state


def test_in_combat_suppresses_card_keeps_mutation():
    state = _state_with_two_chars()
    state.combat_state = CombatState(enemy_ids=["npc_01"])
    dirty = Dirty()

    apply_combat_affinity_drop(state, "player_01", "npc_01", dirty=dirty)

    # mutation: yes
    assert (
        state.characters["npc_01"].relations["player_01"]
        == -RULES.social.combat_affinity_drop
    )
    # card: no
    assert dirty.deferred_act_cards == []


def test_out_of_combat_emits_card():
    state = _state_with_two_chars()
    assert state.combat_state is None
    dirty = Dirty()

    apply_combat_affinity_drop(state, "player_01", "npc_01", dirty=dirty)

    assert (
        state.characters["npc_01"].relations["player_01"]
        == -RULES.social.combat_affinity_drop
    )
    assert len(dirty.deferred_act_cards) == 1
