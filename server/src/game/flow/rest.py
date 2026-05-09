"""Long-rest branch. Risk-roll for full recovery vs. ambush. If the seed pool
is empty and an LLM is wired, summon an ad-hoc enemy."""

import random
from collections.abc import AsyncIterator

from ..domain.errors import RestInsufficientGold
from ..domain.state import GameState
from ..engines import recovery as recovery_engine
from src.locale import render
from src.llm.client import LLMClient
from src.db.repo import SaveRepo, ScenarioRepo
from ..rules import RULES
from . import encounter as encounter_engine
from .buff_tick import tick_turn_buffs
from src.llm.calls.classify.schema import Verb
from .combat_auto import PlayerAction
from .combat_phase import start_combat_and_drive_auto
from .dirty import Dirty, ToFrontFn, drop_pushed_act, finalize, push_act
from .error_phrases import humanize_engine_error
from .format import format_rest_log
from .narrate import stream_narrate_tail


_REST_DEFAULT_INPUT = render("log.rest.default_input", "ko")


def _rest_ambush_text(actor_name: str) -> str:
    return render("log.rest.ambush", "ko", actor=actor_name)


async def run_rest(
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    client: LLMClient | None = None,
    player_input: str = _REST_DEFAULT_INPUT,
) -> AsyncIterator[dict]:
    from ._diag import diag

    state.turn_count += 1
    diag(state.game_id, state.turn_count, "rest:start")

    summon_cb: recovery_engine.SummonCallable | None = None
    if client is not None:

        async def _summon(s: GameState, loc_id: str) -> str | None:
            location = s.locations.get(loc_id)
            if location is None:
                return None
            char = await encounter_engine.summon_encounter(
                client, s, location, scenario_repo, s.profile, dirty=dirty.entities
            )
            return char.id if char else None

        summon_cb = _summon

    try:
        outcome, enemy_ids = await recovery_engine.attempt_rest(
            state, state.player_id, rng=rng, dirty=dirty.entities, summon=summon_cb
        )
    except RestInsufficientGold as exc:
        fail_line = humanize_engine_error(exc)
        if client is None:
            yield push_act(state, dirty, fail_line)
        else:
            # Fold the engine line into narrate prose so it doesn't read as
            # chrome + silence — the LLM gets fail_line as context and
            # describes the player realizing they can't afford the inn.
            fail_evt = push_act(state, dirty, fail_line)
            drop_pushed_act(state, dirty, (fail_evt.get("data") or {}).get("id"))
            graph = state.graph()
            async for ev in stream_narrate_tail(
                client,
                state,
                scenario_repo,
                player_input,
                dirty,
                to_front_fn,
                Verb(name="wait"),
                graph=graph,
                act_log_lines=[fail_line],
            ):
                yield ev
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return
    actor = state.characters[state.player_id]

    diag(
        state.game_id, state.turn_count, "rest:outcome",
        outcome=outcome, enemies=enemy_ids if enemy_ids else None,
        hp=actor.hp, mp=actor.mp,
    )

    if outcome == "encounter":
        yield push_act(state, dirty, _rest_ambush_text(actor.name))
        # attempt_rest may have spawned an enemy; reset the cached graph so
        # downstream reads see the new located_at edge.
        state.invalidate_graph()
        async for ev in start_combat_and_drive_auto(
            client,
            state,
            scenario_repo,
            enemy_ids,
            dirty,
            rng,
            player_input=render("log.rest.ambush_input", "ko"),
            player_action=PlayerAction(kind="pass"),
            surprise="enemy",
            cap=1,
        ):
            yield ev
        tick_turn_buffs(state, dirty)
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    state.invalidate_graph()
    yield push_act(state, dirty, format_rest_log(actor.name, RULES.recovery.cost_gold))
    if to_front_fn is not None:
        yield {"type": "state", "data": to_front_fn(state)}
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev
