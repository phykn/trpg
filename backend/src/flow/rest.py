"""Long-rest branch. Risk-roll for full recovery vs. ambush. If the seed pool
is empty and an LLM is wired, summon an ad-hoc enemy."""
import random
from collections.abc import AsyncIterator

from ..domain.state import GameState
from ..engines import recovery as recovery_engine
from ..llm.client import LLMClient
from ..rules import RULES
from . import encounter as encounter_engine
from .combat_phase import start_combat_and_run_npc_phase
from .dirty import Dirty, ToFrontFn, advance_time, finalize, next_log_id, push_log_entry

from ..domain.memory import GMLogEntry


def _push_gm(state: GameState, dirty: Dirty, text: str) -> dict:
    log = GMLogEntry(id=next_log_id(state), kind="gm", text=text)
    push_log_entry(state, log, dirty)
    return {"type": "log_entry", "data": log.model_dump()}


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
        yield _push_gm(state, dirty, f"{actor.name}이(가) 잠들기 직전 적의 습격을 받는다.")
        async for ev in start_combat_and_run_npc_phase(
            state, enemy_ids, dirty, rng, surprise="enemy"
        ):
            yield ev
        advance_time(state)
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    hours = RULES.time.sleep_hours
    yield _push_gm(
        state, dirty,
        f"{actor.name}은(는) 자리를 잡고 잠을 청한다. "
        f"{hours}시간 후 푹 쉬고 일어나, HP/MP 가 모두 회복됐다.",
    )
    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
