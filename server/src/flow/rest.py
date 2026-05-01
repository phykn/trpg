"""Long-rest branch. Risk-roll for full recovery vs. ambush. If the seed pool
is empty and an LLM is wired, summon an ad-hoc enemy."""

import random
from collections.abc import AsyncIterator

from ..domain.state import GameState
from ..engines import recovery as recovery_engine
from ..llm.client import LLMClient
from ..mapping.to_front import rest_ambush_text, rest_completed_text
from ..ontology.graph import build_graph
from . import encounter as encounter_engine
from .combat_auto import PlayerAction
from .combat_phase import start_combat_and_drive_auto
from .clock import tick_turn_buffs
from .dirty import Dirty, ToFrontFn, finalize, push_act


async def run_rest(
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    client: LLMClient | None = None,
) -> AsyncIterator[dict]:
    state.turn_count += 1

    summon_cb: recovery_engine.SummonCallable | None = None
    if client is not None:

        async def _summon(s: GameState, loc_id: str) -> str | None:
            location = s.locations.get(loc_id)
            if location is None:
                return None
            char = await encounter_engine.summon_encounter(
                client, s, location, profile_dir, s.profile, dirty=dirty.entities
            )
            return char.id if char else None

        summon_cb = _summon

    outcome, enemy_ids = await recovery_engine.attempt_rest(
        state, state.player_id, rng=rng, dirty=dirty.entities, summon=summon_cb
    )
    actor = state.characters[state.player_id]

    if outcome == "encounter":
        yield push_act(state, dirty, rest_ambush_text(actor.name))
        # attempt_rest may have spawned an enemy; build graph fresh so the
        # new located_at edge is visible to the combat path's downstream reads.
        graph = build_graph(state)
        async for ev in start_combat_and_drive_auto(
            client,
            state,
            profile_dir,
            enemy_ids,
            dirty,
            rng,
            player_input="잠들기 직전 적의 습격에 대비합니다",
            player_action=PlayerAction(kind="pass"),
            surprise="enemy",
            cap=1,
            graph=graph,
        ):
            yield ev
        tick_turn_buffs(state, dirty)
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    yield push_act(state, dirty, rest_completed_text(actor.name))
    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
