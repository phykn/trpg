"""Steal action — DEX vs DC roll. Success picks one random non-equipped item
from the target's inventory and forces it into player inventory; failure drops
target.relations[player] and emits a system card. /turn dispatch builds a
PendingCheck(kind="steal") here; /roll resolves via handle_steal_roll_result.

Mirrors flow/companion.py recruit pattern — same pending_check shape, same
narrate hand-off via previous_phase_signal."""

import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from src.db.repo import SaveRepo
from src.locale import render
from src.wire.emit import emit_error, emit_pending_check

from ..domain.errors import PersistenceFailed
from ..domain.memory import PendingCheck
from ..domain.state import GameState
from ..engines import inventory as inventory_engine
from ..ontology.queries import equipment_of, inventory_of
from ..rules import RULES
from ..rules.dc import compute_required_roll, pick_dc
from .dirty import Dirty, ToFrontFn, flush, push_act
from .format import (
    format_steal_failure_log,
    format_steal_failure_turn_log,
    format_steal_no_carryables_log,
    format_steal_success_log,
    format_steal_success_turn_log,
)


_STEAL_TIER = "normal"
_STEAL_STAT = "DEX"


def _stealable_item_ids(state: GameState, target_id: str) -> list[str]:
    """NPC inventory minus equipped — same filter as surroundings.carryables.
    Caller already validated target exists; guard returns empty for missing."""
    graph = state.graph()
    equipped = {edge.to_id for edge in equipment_of(graph, target_id)}
    return [iid for iid in inventory_of(graph, target_id) if iid not in equipped]


async def run_steal(
    state: GameState,
    save_repo: SaveRepo,
    player_input: str,
    target_id: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    """Set a steal-kind pending_check and emit pending_check SSE.
    The /roll endpoint resolves the result via handle_steal_roll_result."""
    actor = state.characters[state.player_id]

    if target_id not in state.characters:
        return

    if not _stealable_item_ids(state, target_id):
        # Defensive — semantic check already requires non-empty carryables.
        target = state.characters.get(target_id)
        target_name = target.name if target else target_id
        yield push_act(state, dirty, format_steal_no_carryables_log(target_name))
        return

    dc = pick_dc(_STEAL_TIER)
    stat_value = actor.stats.DEX
    required_roll = compute_required_roll(dc, stat_value)

    state.pending_check = PendingCheck(
        player_input=player_input,
        kind="steal",
        tier=_STEAL_TIER,
        stat=_STEAL_STAT,
        target=target_id,
        targets=[target_id],
        dc=dc,
        mod=0,
        required_roll=required_roll,
        reason=render("log.steal.reason", "ko"),
        created_at=datetime.now(UTC).isoformat(),
    )
    try:
        await flush(state, save_repo, dirty)
    except PersistenceFailed as e:
        yield emit_error(e)
        return
    yield emit_pending_check(state, state.pending_check)


async def handle_steal_roll_result(
    state: GameState,
    pending: PendingCheck,
    grade: str,
    dirty: Dirty,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    """Apply steal roll outcome:
    - success branches → pick random non-equipped item, transfer to player,
      push success card.
    - failure / critical_failure → drop target.relations[player] and push
      failure card. No combat trigger (Stage-1 keeps it simple)."""
    target_id = pending.target
    target = state.characters.get(target_id)
    if target is None:
        return
    target_name = target.name
    player = state.characters[state.player_id]
    rng_obj = rng or random

    if grade in ("critical_success", "success", "partial_success"):
        stealable = _stealable_item_ids(state, target_id)
        if not stealable:
            yield push_act(state, dirty, format_steal_no_carryables_log(target_name))
            return
        item_id = rng_obj.choice(stealable)
        item = state.items.get(item_id)
        item_name = item.name if item else item_id
        try:
            inventory_engine.steal(target, player, item_id, state.items)
        except Exception:
            yield push_act(state, dirty, format_steal_no_carryables_log(target_name))
            return
        state.invalidate_graph()
        dirty.entities.add(("characters", state.player_id))
        dirty.entities.add(("characters", target_id))
        yield push_act(
            state,
            dirty,
            format_steal_success_log(target_name, item_name),
            turn_summary=format_steal_success_turn_log(target_name, item_name),
        )
        state.previous_phase_signal = f"stole:{target_name}:{item_name}"
        return

    # failure / critical_failure → relations drop + system card.
    drop = RULES.social.combat_affinity_drop
    target.relations[state.player_id] = (
        target.relations.get(state.player_id, 0) - drop
    )
    dirty.entities.add(("characters", target_id))
    yield push_act(
        state,
        dirty,
        format_steal_failure_log(target_name),
        turn_summary=format_steal_failure_turn_log(target_name),
    )
    state.previous_phase_signal = f"steal_caught:{target_name}"
