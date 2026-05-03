"""Combat dispatch — auto-mode. Each combat turn: judge → PlayerAction → run_auto_combat → stream cinematic → push summary → end-event if terminal."""

from __future__ import annotations

import random
from collections.abc import AsyncIterator
from typing import Literal

from ..llm_calls.combat_narrate import stream_combat_narrate
from ..llm_calls.classify.schema import (
    CombatAction,
    EquipAction,
    FleeAction,
    PassAction,
    RejectAction,
    RestAction,
    RollAction,
    UnequipAction,
    UseAction,
)
from ..domain.errors import CombatStateInvalid, JudgeMalformed
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..llm.client import LLMClient
from ..ontology.graph import GameGraph
from ..ontology.queries import location_of
from ..persistence.repo import SaveRepo, ScenarioRepo
from .actions import (
    emit_equip,
    emit_roll_pending,
    emit_unequip,
    emit_use,
)
from .combat_auto import (
    AutoCombatResult,
    PlayerAction,
    build_narrate_input,
    run_auto_combat,
)
from .dirty import Dirty, ToFrontFn, finalize, push_act, push_gm, push_turn_log
from .error_phrases import humanize_runtime_error
from .format import (
    ACTION_FORBIDDEN_IN_COMBAT_TEXT,
    INPUT_REJECTED_TEXT,
    NO_COMBAT_TARGETS_TEXT,
    REST_BLOCKED_IN_COMBAT_TEXT,
    format_combat_end_text,
    format_combat_outcome_summary,
    format_combat_start_turn_log,
)
from .judge import run_judge
from .narrate import stream_narrate_tail
from .subject import refresh_active_subject


async def emit_combat_cinematic_and_end(
    client: LLMClient | None,
    state: GameState,
    scenario_repo: ScenarioRepo,
    dirty: Dirty,
    *,
    player_input: str,
    result: AutoCombatResult,
) -> AsyncIterator[dict]:
    """Stream combat_narrate cinematic, push numeric summary, emit end.
    Shared tail of one auto-combat sim — used by _drive_auto_combat (in-combat
    /turn) and roll._resume_auto_combat (post-roll combat resume)."""
    if client is not None:
        narrate_input = await build_narrate_input(
            state,
            scenario_repo,
            player_input=player_input,
            result=result,
        )
        body_chunks: list[str] = []
        async for chunk in stream_combat_narrate(client, narrate_input):
            body_chunks.append(chunk)
            yield {"type": "narrative_delta", "data": {"text": chunk}}
        body = "".join(body_chunks).strip()
        if body:
            yield push_gm(state, dirty, body)

    summary = format_combat_outcome_summary(result)
    # When player_revived, the "가까스로 일어남 (Revival N/M)" line in summary already serves as the end label — appending end_text would duplicate.
    if result.player_revived:
        combined = summary or format_combat_end_text(result.outcome)
    else:
        end_text = format_combat_end_text(result.outcome)
        combined = f"{summary}\n{end_text}" if summary else end_text
    yield push_act(state, dirty, combined)
    yield {"type": "combat_end", "data": {"outcome": result.outcome}}


async def _drive_auto_combat(
    client: LLMClient | None,
    state: GameState,
    scenario_repo: ScenarioRepo,
    dirty: Dirty,
    *,
    player_input: str,
    player_action: PlayerAction,
    rng: random.Random | None,
    cap: int | None = None,
    graph: GameGraph,
) -> AsyncIterator[dict]:
    """Run the auto-combat sim, stream the cinematic, push numeric summary
    and combat_end. Caller must have already set combat_state."""
    if state.combat_state is None:
        raise CombatStateInvalid("_drive_auto_combat called without combat_state")

    kwargs = {"player_action": player_action, "rng": rng}
    if cap is not None:
        kwargs["cap"] = cap
    result = run_auto_combat(state, dirty, **kwargs)

    for tev in result.turn_events:
        yield {"type": "combat_turn", "data": tev}

    async for ev in emit_combat_cinematic_and_end(
        client,
        state,
        scenario_repo,
        dirty,
        player_input=player_input,
        result=result,
    ):
        yield ev


async def start_combat_and_drive_auto(
    client: LLMClient | None,
    state: GameState,
    scenario_repo: ScenarioRepo,
    enemy_ids: list[str],
    dirty: Dirty,
    rng: random.Random | None,
    *,
    player_input: str,
    player_action: PlayerAction,
    surprise: Literal["player", "enemy"] | None = None,
    cap: int | None = None,
    graph: GameGraph,
) -> AsyncIterator[dict]:
    """Open a fresh fight (no existing combat_state) and run one auto-sim.
    Used by /turn's CombatAction / SummonCombatAction entry and by rest's
    ambush branch."""
    if state.combat_state is not None:
        raise CombatStateInvalid(
            "start_combat called while combat_state is already set "
            f"(stale enemy_ids={list(state.combat_state.enemy_ids)}, "
            f"new enemy_ids={enemy_ids})"
        )
    cs = combat_engine.start_combat(state, enemy_ids, rng=rng, surprise=surprise)
    yield {
        "type": "combat_start",
        "data": {
            "turn_order": list(cs.turn_order),
            "round": cs.round,
            "surprise": cs.surprise,
            "enemy_ids": list(cs.enemy_ids),
        },
    }
    if enemy_ids:
        first_enemy = state.characters.get(enemy_ids[0])
        if first_enemy is not None:
            push_turn_log(
                state,
                first_enemy.id,
                format_combat_start_turn_log(first_enemy.name),
                dirty,
            )

    async for ev in _drive_auto_combat(
        client,
        state,
        scenario_repo,
        dirty,
        player_input=player_input,
        player_action=player_action,
        rng=rng,
        cap=cap,
        graph=graph,
    ):
        yield ev


def has_invalid_combat_targets(
    state: GameState, graph: GameGraph, requested: list[str]
) -> bool:
    """True if any requested target isn't a valid attackable enemy in the
    player's location: self-target, missing, dead, or in a different location.
    Shared by turn.py (out-of-combat CombatAction) and run_combat_player_turn
    (in-combat CombatAction)."""
    actor_loc = location_of(graph, state.player_id)
    return any(
        t == state.player_id
        or t not in state.characters
        or not state.characters[t].alive
        or location_of(graph, t) != actor_loc
        for t in requested
    )


def _judge_to_player_action(result, state: GameState) -> PlayerAction | None:
    """Distil a judge action into a PlayerAction for the auto-sim. Returns
    None if the action is not allowed in combat (rest, move, etc.)."""
    if isinstance(result, CombatAction):
        return PlayerAction(
            kind="skill" if result.skill_id else "attack",
            skill_id=result.skill_id,
            targets=list(result.targets),
        )
    if isinstance(result, FleeAction):
        return PlayerAction(kind="flee")
    if isinstance(result, PassAction):
        return PlayerAction(kind="pass")
    if isinstance(result, (UseAction, EquipAction, UnequipAction)):
        return PlayerAction(kind="pass")
    return None


async def _passive_pre_emit(
    state: GameState,
    dirty: Dirty,
    result,
) -> AsyncIterator[dict]:
    """For UseAction / EquipAction / UnequipAction inside combat: apply the
    item engine action before the auto-sim sees a `pass` round, so the
    cinematic narrates a fight where the player consumed/swapped this turn.
    Emits a combat_turn event so the client can attribute the round to the
    item interaction, mirroring the round events the auto-sim produces."""
    label: str
    if isinstance(result, UseAction):
        async for ev in emit_use(
            state, state.player_id, result.item_id, result.target_id, dirty
        ):
            yield ev
        label = "use"
    elif isinstance(result, EquipAction):
        async for ev in emit_equip(state, state.player_id, result.item_id, dirty):
            yield ev
        label = "equip"
    elif isinstance(result, UnequipAction):
        async for ev in emit_unequip(state, state.player_id, result.item_id, dirty):
            yield ev
        label = "unequip"
    else:
        return
    yield {
        "type": "combat_turn",
        "data": {
            "actor": state.player_id,
            "action": label,
            "item_id": result.item_id,
        },
    }


async def run_combat_player_turn(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    player_input: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    *,
    graph: GameGraph,
) -> AsyncIterator[dict]:
    """One in-combat /turn step. Always runs an auto-sim cycle (cap rounds
    or until terminal). The `ongoing` outcome leaves combat_state in place
    so the next /turn picks up where this one left off."""
    try:
        result = await run_judge(client, state, player_input, graph=graph)
    except JudgeMalformed as e:
        yield {
            "type": "error",
            "data": {
                "message": humanize_runtime_error(e),
                "code": "JudgeMalformed",
            },
        }
        return

    yield {"type": "judge", "data": result.model_dump()}
    refresh_active_subject(state, result)

    if isinstance(result, RestAction):
        yield push_act(state, dirty, REST_BLOCKED_IN_COMBAT_TEXT)
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, RollAction):
        async for ev in emit_roll_pending(
            state, save_repo, player_input, result, dirty
        ):
            yield ev
        return

    if isinstance(result, RejectAction):
        yield push_act(state, dirty, INPUT_REJECTED_TEXT)
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    player_action = _judge_to_player_action(result, state)
    if player_action is None:
        yield push_act(state, dirty, ACTION_FORBIDDEN_IN_COMBAT_TEXT)
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, CombatAction):
        if has_invalid_combat_targets(state, graph, result.targets):
            yield push_act(state, dirty, NO_COMBAT_TARGETS_TEXT)
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return

    # Passive in-combat actions emit their engine effect first; the auto-sim
    # then runs to terminal outcome with the player falling back to attack
    # from round 2 onwards.
    if isinstance(result, (UseAction, EquipAction, UnequipAction)):
        async for ev in _passive_pre_emit(state, dirty, result):
            yield ev

    async for ev in _drive_auto_combat(
        client,
        state,
        scenario_repo,
        dirty,
        player_input=player_input,
        player_action=player_action,
        rng=rng,
        graph=graph,
    ):
        yield ev

    state.turn_count += 1
    # Post-combat narrate when this in-combat turn ended the fight (coin-revive 'downed' or victory/defeat reached) — same pattern as _enter_combat_and_finalize so the system card isn't the terminal UI line. player_input="" because combat_narrate already consumed the original input; this beat is the recovery / aftermath. Skipped on client=None (engine-only test path).
    if (
        client is not None
        and state.combat_state is None
        and state.characters[state.player_id].alive
    ):
        state.invalidate_graph()
        graph_post = state.graph()
        signal = state.previous_phase_signal
        state.previous_phase_signal = None
        async for ev in stream_narrate_tail(
            client,
            state,
            scenario_repo,
            "",
            dirty,
            to_front_fn,
            PassAction(action="pass"),
            graph=graph_post,
            previous_phase_signal=signal,
        ):
            yield ev
    # Buffs already ticked per-round inside run_auto_combat; no /turn-end tick here.
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev
