"""/level_up — UI button-driven level-up (skips judge LLM). Applies stat
pair-trade, optionally learns a chosen skill, then runs narrate to describe
the moment briefly while continuing the prior scene."""

from collections.abc import AsyncIterator

from pydantic import ValidationError

from ..domain.errors import LevelUpInvalid, LLMUnavailable
from ..domain.state import GameState
from ..domain.types import STAT_PAIRS, StatKey
from ..engines.growth import level_up as level_up_engine
from ..engines.invariants import InvariantViolation
from ..engines.invariants.character import check_character
from ..llm.client import LLMClient, set_llm_session_if_unset
from ..persistence.repo import SaveRepo, ScenarioRepo
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    push_act,
)
from .format import format_learn_skill_log, format_level_up_log
from .narrate import consume_narrate, run_narrate


async def run_level_up(
    client: LLMClient | None,
    state: GameState,
    scenario_repo: ScenarioRepo | None,
    save_repo: SaveRepo,
    *,
    stat_up: StatKey,
    skill_id: str | None,
    to_front_fn: ToFrontFn | None = None,
) -> AsyncIterator[dict]:
    set_llm_session_if_unset(state.game_id)

    if state.pending_check is not None:
        yield {
            "type": "error",
            "data": {
                "message": "굴림이 진행 중입니다. 먼저 주사위를 굴려 주세요.",
                "code": "PendingCheckActive",
            },
        }
        return

    dirty = Dirty()
    actor = state.characters[state.player_id]
    stat_down = STAT_PAIRS.get(stat_up)
    if stat_down is None:
        yield {
            "type": "error",
            "data": {
                "message": f"잘못된 능력치입니다: {stat_up}",
                "code": "LevelUpInvalid",
            },
        }
        return

    try:
        level_up_engine(actor, stat_up, stat_down)
    except LevelUpInvalid as e:
        yield {
            "type": "error",
            "data": {"message": str(e), "code": "LevelUpInvalid"},
        }
        return

    state.pending_growth = None
    violations = check_character(actor)
    if violations:
        raise InvariantViolation(
            "post-level_up invariant violation:\n" + "\n".join(violations)
        )
    dirty.entities.add(("characters", actor.id))

    level_up_text = format_level_up_log(
        actor.name, actor.level, stat_up, stat_down, actor.max_hp, actor.max_mp
    )
    yield push_act(state, dirty, level_up_text)
    act_log_lines: list[str] = [level_up_text]

    if skill_id is not None and skill_id in state.skills:
        skill = state.skills[skill_id]
        if skill_id not in actor.learned_skill_ids:
            actor.learned_skill_ids.append(skill_id)
        learned_skill_text = format_learn_skill_log(actor.name, skill.name)
        yield push_act(state, dirty, learned_skill_text)
        act_log_lines.append(learned_skill_text)

    state.invalidate_graph()

    # Narrate is optional — without an LLM client (test path) we skip the prose.
    if client is not None and scenario_repo is not None:
        graph = state.graph()
        judge_result = {"action": "pass", "targets": []}
        stream = run_narrate(
            client,
            state,
            scenario_repo,
            player_input="",
            judge_result=judge_result,
            graph=graph,
            grade=None,
            target_id=None,
            act_log_lines=act_log_lines,
        )
        try:
            async for ev in consume_narrate(
                state,
                dirty,
                stream,
                target_for_log=None,
                dialogue_input=None,
                graph=graph,
            ):
                yield ev
        except (ValidationError, LLMUnavailable, OSError, TimeoutError) as e:
            yield {
                "type": "error",
                "data": {"message": str(e), "code": "NarrateFailed"},
            }

    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev
