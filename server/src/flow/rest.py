"""Long-rest branch. Risk-roll for full recovery vs. ambush. If the seed pool
is empty and an LLM is wired, summon an ad-hoc enemy."""

import random
from collections.abc import AsyncIterator

from ..agents.dc_judge.schema import PassAction
from ..domain.state import GameState
from ..engines import recovery as recovery_engine
from ..llm.client import LLMClient
from ..mapping.josa import eun_neun
from ..persistence.repo import SaveRepo, ScenarioRepo
from . import encounter as encounter_engine
from .combat_auto import PlayerAction
from .combat_phase import start_combat_and_drive_auto
from .buff_tick import tick_turn_buffs
from .dirty import Dirty, ToFrontFn, finalize, push_act
from .narrate import consume_narrate, run_narrate


def _rest_completed_text(actor_name: str) -> str:
    return (
        f"{actor_name}{eun_neun(actor_name)} 자리를 잡고 잠을 청했습니다. "
        f"새벽이 밝아오자 푹 쉬고 일어났습니다. HP/MP가 모두 회복됐습니다."
    )


def _rest_ambush_text(actor_name: str) -> str:
    return f"{actor_name}{eun_neun(actor_name)} 잠들기 직전 적의 습격을 받았습니다."


async def run_rest(
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    client: LLMClient | None = None,
    player_input: str = "휴식한다",
) -> AsyncIterator[dict]:
    state.turn_count += 1

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

    outcome, enemy_ids = await recovery_engine.attempt_rest(
        state, state.player_id, rng=rng, dirty=dirty.entities, summon=summon_cb
    )
    actor = state.characters[state.player_id]

    if outcome == "encounter":
        yield push_act(state, dirty, _rest_ambush_text(actor.name))
        # attempt_rest may have spawned an enemy; build graph fresh so the
        # new located_at edge is visible to the combat path's downstream reads.
        state.invalidate_graph()
        graph = state.graph()
        async for ev in start_combat_and_drive_auto(
            client,
            state,
            scenario_repo,
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
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    rest_text = _rest_completed_text(actor.name)
    state.invalidate_graph()
    graph = state.graph()
    if client is not None:
        if to_front_fn is not None:
            yield {"type": "state", "data": to_front_fn(state)}
        fake_pass = PassAction(action="pass")
        stream = run_narrate(
            client,
            state,
            scenario_repo,
            player_input,
            judge_result=fake_pass.model_dump(),
            graph=graph,
            grade=None,
            act_log_lines=[rest_text],
        )
        async for ev in consume_narrate(
            state,
            dirty,
            stream,
            target_for_log=None,
            dialogue_input=player_input,
            graph=graph,
        ):
            yield ev
    else:
        yield push_act(state, dirty, rest_text)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev
