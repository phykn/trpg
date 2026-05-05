"""Combat dispatch — auto-mode. Each combat turn: judge → PlayerAction → run_auto_combat → stream cinematic → push summary → end-event if terminal."""

from __future__ import annotations

import random
from collections.abc import AsyncIterator
from typing import Literal

from src.llm.calls.combat_narrate import stream_combat_narrate
from src.llm.calls.classify.schema import Verb
from ..domain.errors import CombatStateInvalid, JudgeMalformed
from ..domain.state import GameState
from ..engines import combat as combat_engine
from src.llm.client import LLMClient
from ..ontology.graph import GameGraph
from ..ontology.queries import location_of
from src.db.repo import SaveRepo, ScenarioRepo
from .actions import (
    emit_equip,
    emit_unequip,
    emit_use,
)
from .combat_auto import (
    AutoCombatResult,
    PlayerAction,
    build_narrate_input,
    run_auto_combat,
)
from src.wire.emit import (
    emit_combat_end,
    emit_combat_start,
    emit_combat_turn,
    emit_error,
    emit_judge_pending_check_trigger,
    emit_judge_verb,
    emit_narrative_delta,
)
from src.wire.models import CombatTurnPayload
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    flush_deferred_act_cards,
    push_act,
    push_gm,
    push_turn_log,
)
from .format import (
    ACTION_FORBIDDEN_IN_COMBAT_TEXT,
    INPUT_REJECTED_TEXT,
    NO_COMBAT_TARGETS_TEXT,
    REST_BLOCKED_IN_COMBAT_TEXT,
    format_combat_end_text,
    format_combat_event_summary,
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
            yield emit_narrative_delta(chunk)
        body = "".join(body_chunks).strip()
        if body:
            yield push_gm(state, dirty, body)

    summary = format_combat_outcome_summary(result)
    enemies_remaining = [
        {"id": h.id, "name": h.name, "hp": h.hp_after, "hp_max": h.max_hp}
        for h in result.enemy_hits
        if not h.killed
    ]
    # When player_revived, the revive line in summary ("가까스로 일어남" or "최후의 호흡") already serves as the end label — appending end_text would duplicate.
    if result.player_revived:
        combined = summary or format_combat_end_text(result.outcome, enemies_remaining)
    else:
        end_text = format_combat_end_text(result.outcome, enemies_remaining)
        combined = f"{summary}\n{end_text}" if summary else end_text
    yield push_act(state, dirty, combined)
    # Reaction cards (quest success/failure, etc.) flush AFTER cinematic
    # + outcome summary. Order: combat narration → outcome → reward cards.
    for ev in flush_deferred_act_cards(state, dirty):
        yield ev
    yield emit_combat_end(result.outcome)


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
    _result_out: list | None = None,
) -> AsyncIterator[dict]:
    """Run the auto-combat sim, stream the cinematic, push numeric summary
    and combat_end. Caller must have already set combat_state.
    If _result_out is provided, appends the AutoCombatResult to it."""
    if state.combat_state is None:
        raise CombatStateInvalid("_drive_auto_combat called without combat_state")

    kwargs = {"player_action": player_action, "rng": rng}
    if cap is not None:
        kwargs["cap"] = cap
    result = run_auto_combat(state, dirty, **kwargs)
    if _result_out is not None:
        _result_out.append(result)

    for tev in result.turn_events:
        yield emit_combat_turn(tev)

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
    _result_out: list | None = None,
) -> AsyncIterator[dict]:
    """Open a fresh fight (no existing combat_state) and run one auto-sim.
    Used by /turn's attack verb entry and by rest's ambush branch."""
    if state.combat_state is not None:
        raise CombatStateInvalid(
            "start_combat called while combat_state is already set "
            f"(stale enemy_ids={list(state.combat_state.enemy_ids)}, "
            f"new enemy_ids={enemy_ids})"
        )
    cs = combat_engine.start_combat(state, enemy_ids, rng=rng, surprise=surprise)
    yield emit_combat_start(
        turn_order=cs.turn_order,
        round=cs.round,
        surprise=cs.surprise,
        enemy_ids=cs.enemy_ids,
    )
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
        _result_out=_result_out,
    ):
        yield ev


def has_invalid_combat_targets(
    state: GameState, graph: GameGraph, requested: list[str]
) -> bool:
    """True if any requested target isn't a valid attackable enemy in the
    player's location: self-target, missing, dead, or in a different location.
    Shared by turn.py (out-of-combat attack verb) and run_combat_player_turn
    (in-combat attack verb)."""
    actor_loc = location_of(graph, state.player_id)
    return any(
        t == state.player_id
        or t not in state.characters
        or not state.characters[t].alive
        or location_of(graph, t) != actor_loc
        for t in requested
    )


def _judge_to_player_action(verb: Verb, state: GameState) -> PlayerAction | None:
    """Distil a verb into a PlayerAction for the auto-sim. Returns None if the
    verb is not allowed in combat (rest, move outside flee, etc.). Non-equip
    transfer (trade/gift) is meaningless mid-fight, so it returns None and
    falls through to ACTION_FORBIDDEN_IN_COMBAT_TEXT."""
    n = verb.name
    m = verb.modifiers or {}
    if n == "attack":
        return PlayerAction(
            kind="skill" if m.get("skill_id") else "attack",
            skill_id=m.get("skill_id"),
            targets=list(verb.target_ids),
        )
    if n == "cast":
        return PlayerAction(
            kind="skill",
            skill_id=m.get("skill_id"),
            targets=list(verb.target_ids),
        )
    if n == "move" and m.get("manner") == "hasty":
        return PlayerAction(kind="flee")
    if n == "wait":
        return PlayerAction(kind="pass")
    if n == "use":
        # bookkeeping verb — combat treats this as a pass round.
        return PlayerAction(kind="pass")
    if n == "transfer":
        # Only equip/unequip are allowed as in-combat passives. trade/gift
        # return None and fall through to ACTION_FORBIDDEN_IN_COMBAT_TEXT
        # (avoids a silent pass round on a meaningless trade attempt).
        from_id = m.get("from_id", "")
        to_id = m.get("to_id", "")
        if "<self>.equipped" in from_id or "<self>.equipped" in to_id:
            return PlayerAction(kind="pass")
        return None
    return None


async def _passive_pre_emit(
    state: GameState,
    dirty: Dirty,
    verb: Verb,
) -> AsyncIterator[dict]:
    """For passive in-combat verbs: apply the item/transfer engine action
    before the auto-sim sees a `pass` round, so the cinematic narrates a fight
    where the player consumed/swapped this turn."""
    label: str
    item_id_carried: str
    n = verb.name
    m = verb.modifiers or {}
    if n == "use":
        async for ev in emit_use(
            state, state.player_id, m["item_id"], m.get("target_id"), dirty
        ):
            yield ev
        label = "use"
        item_id_carried = m["item_id"]
    elif n == "transfer":
        from_id = m.get("from_id", "")
        to_id = m.get("to_id", "")
        item_id_carried = m["item_id"]
        if "<self>.equipped" in to_id:
            async for ev in emit_equip(state, state.player_id, item_id_carried, dirty):
                yield ev
            label = "equip"
        elif "<self>.equipped" in from_id:
            async for ev in emit_unequip(state, state.player_id, item_id_carried, dirty):
                yield ev
            label = "unequip"
        else:
            # Other transfer modes (gift/trade) — not a combat passive
            return
    else:
        return
    yield emit_combat_turn(CombatTurnPayload(
        actor=state.player_id,
        action=label,
        round=state.combat_state.round,
        item_id=item_id_carried,
    ))


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
        yield emit_error(e)
        return

    # PendingCheckTrigger → emit_roll_pending_from_trigger directly.
    from .judge import PendingCheckTrigger
    if isinstance(result, PendingCheckTrigger):
        from .actions import emit_roll_pending_from_trigger
        yield emit_judge_pending_check_trigger(
            tier=result.tier,
            stat=result.stat,
            targets=result.targets,
            reason=result.reason,
        )
        async for ev in emit_roll_pending_from_trigger(
            state, save_repo, player_input, result, dirty,
        ):
            yield ev
        return

    # JudgeOutput (verb-based): refuse → INPUT_REJECTED; otherwise take the
    # first verb (in-combat assumes a single action — chains are out-of-combat
    # only).
    if result.refuse is not None:
        yield push_act(state, dirty, INPUT_REJECTED_TEXT)
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return
    # _exactly_one validator guarantees actions is 1+ when refuse is None.
    verb = result.actions[0]

    yield emit_judge_verb(verb)
    refresh_active_subject(state, [verb])

    if verb.name == "rest":
        yield push_act(state, dirty, REST_BLOCKED_IN_COMBAT_TEXT)
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    player_action = _judge_to_player_action(verb, state)
    if player_action is None:
        yield push_act(state, dirty, ACTION_FORBIDDEN_IN_COMBAT_TEXT)
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    if verb.name == "attack":
        if has_invalid_combat_targets(state, graph, list(verb.target_ids)):
            yield push_act(state, dirty, NO_COMBAT_TARGETS_TEXT)
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return

    # Passive in-combat verb: use, or transfer(equip/unequip).
    is_passive = (
        verb.name == "use"
        or (verb.name == "transfer"
            and ("<self>.equipped" in (verb.modifiers or {}).get("from_id", "")
                 or "<self>.equipped" in (verb.modifiers or {}).get("to_id", "")))
    )
    if is_passive:
        async for ev in _passive_pre_emit(state, dirty, verb):
            yield ev

    combat_results: list[AutoCombatResult] = []
    async for ev in _drive_auto_combat(
        client,
        state,
        scenario_repo,
        dirty,
        player_input=player_input,
        player_action=player_action,
        rng=rng,
        graph=graph,
        _result_out=combat_results,
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
        recent_events: list[dict] = []
        if combat_results:
            recent_events.append(
                {
                    "type": "combat",
                    "summary": format_combat_event_summary(combat_results[0]),
                }
            )
        async for ev in stream_narrate_tail(
            client,
            state,
            scenario_repo,
            "",
            dirty,
            to_front_fn,
            Verb(name="wait"),
            graph=graph_post,
            previous_phase_signal=signal,
            recent_engine_events=recent_events,
        ):
            yield ev
    # Buffs already ticked per-round inside run_auto_combat; no /turn-end tick here.
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev
