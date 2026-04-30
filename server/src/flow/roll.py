"""/roll — resolve the pending check, narrate the outcome, and resume any
in-flight combat."""
import random
from collections.abc import AsyncIterator

from ..domain.errors import PendingCheckExpected
from ..domain.memory import RollLogEntry
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..engines.growth import grant_roll_xp
from ..llm.client import LLMClient, set_llm_session_if_unset
from ..mapping.josa import i_ga
from ..mapping.to_front import pending_check_to_front, stat_label
from ..rules.config import RULES
from ..rules.dc import compute_grade
from .combat_oneshot import (
    apply_combat_outcome,
    arm_death_save_pending,
    build_oneshot_narrate_input,
    format_combat_outcome_text,
)
from ..agents.combat_narrate import stream_combat_narrate
from .combat_phase import run_combat_npc_phase
from .clock import tick_turn_buffs
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    next_log_id,
    push_act,
    push_gm,
    push_log_entry,
)
from .format import (
    format_combat_end_text,
    front_grade,
)
from .narrate import consume_narrate, run_narrate


# --- combat-roll resolution ------------------------------------------------


async def _resolve_combat_roll(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    dirty: Dirty,
    dice: int,
    pending,
) -> AsyncIterator[dict]:
    """One-roll combat resolution. The d20 + STR vs DC produces a grade,
    grade drives mechanical outcome (kills/HP/XP), and combat_narrate
    streams a 5-10 sentence cinematic of the entire fight."""
    total = dice + pending.mod
    grade = compute_grade(dice, total, pending.required_roll)

    roll_log = RollLogEntry(
        id=next_log_id(state),
        kind="roll",
        check=stat_label(pending.stat),
        roll=dice,
        margin=total - pending.required_roll,
        result=front_grade(grade),
    )
    push_log_entry(state, roll_log, dirty)
    yield {"type": "log_entry", "data": roll_log.model_dump()}

    roll_xp = grant_roll_xp(state, grade, dirty=dirty.entities)

    # Apply mechanical outcome — kill enemies / damage player / award XP
    target_ids = list(pending.targets)
    report = apply_combat_outcome(state, target_ids, grade, dirty)
    killed = [h.id for h in report.enemy_hits if h.killed]

    # Stream the cinematic scene
    if client is not None:
        narrate_input = build_oneshot_narrate_input(
            state, profile_dir,
            player_input=pending.player_input,
            target_ids=target_ids,
            grade=grade,
            player_damage=report.player_damage,
            killed_enemy_ids=killed,
        )
        body_chunks: list[str] = []
        async for chunk in stream_combat_narrate(client, narrate_input):
            body_chunks.append(chunk)
            yield {"type": "narrative_delta", "data": {"text": chunk}}
        body = "".join(body_chunks).strip()
        if body:
            yield push_gm(state, dirty, body)

    # Numeric outcome breakdown — pushed after the cinematic so the prose
    # lands first and the player can then read off the actual damage/HP/XP.
    outcome_text = format_combat_outcome_text(report, roll_xp)
    if outcome_text:
        yield push_act(state, dirty, outcome_text)

    # Outcome bookkeeping: death-save arming if player went down,
    # combat_end semantic flag. Clear the combat_roll pending here for
    # terminal outcomes; for "downed" we replace it with a death_save
    # pending instead, which the caller must NOT overwrite.
    player = state.characters[state.player_id]
    if not player.alive:
        yield push_act(state, dirty, format_combat_end_text("defeat"))
        yield {"type": "combat_end", "data": {"outcome": "defeat"}}
        state.pending_check = None
    elif player.death_saves is not None:
        yield push_act(
            state, dirty,
            "당신은 쓰러져 의식을 잃어갑니다 — 죽음 굴림을 시작합니다.",
        )
        yield {"type": "combat_end", "data": {"outcome": "downed"}}
        arm_death_save_pending(state)
        yield {
            "type": "pending_check",
            "data": pending_check_to_front(state, state.pending_check),
        }
    elif killed:
        yield push_act(state, dirty, format_combat_end_text("victory"))
        yield {"type": "combat_end", "data": {"outcome": "victory"}}
        state.pending_check = None
    else:
        yield push_act(state, dirty, "전투가 멈췄습니다 — 적은 살아 있습니다.")
        yield {"type": "combat_end", "data": {"outcome": "broken_off"}}
        state.pending_check = None


# --- death-save resolution -------------------------------------------------


async def _resolve_death_save(
    state: GameState,
    dirty: Dirty,
    dice: int,
) -> AsyncIterator[dict]:
    """Tick one death save with the player's d20. Re-arms `pending_check`
    on progress; clears it on stable/dead. Pushes a roll log + a short
    narrative gm line so the player sees the outcome."""
    player = state.characters[state.player_id]
    status, _ = combat_engine.tick_death_save(
        state, state.player_id, d20=dice, dirty=dirty.entities,
    )
    grade = "success" if dice >= RULES.death.save_dc else "failure"
    roll_log = RollLogEntry(
        id=next_log_id(state),
        kind="roll",
        check="죽음 굴림",
        roll=dice,
        margin=dice - RULES.death.save_dc,
        result=front_grade(grade if status != "dead" else "critical_failure"),
    )
    push_log_entry(state, roll_log, dirty)
    yield {"type": "log_entry", "data": roll_log.model_dump()}

    if status == "stable":
        state.pending_check = None
        yield push_act(state, dirty, f"{player.name}{i_ga(player.name)} 의식을 되찾았습니다.")
    elif status == "dead":
        state.pending_check = None
        yield push_act(state, dirty, f"{player.name}{i_ga(player.name)} 숨을 거두었습니다.")
    else:
        # progress — re-arm the dice prompt
        arm_death_save_pending(state)
        ds = player.death_saves
        if ds is not None:
            yield push_act(
                state, dirty,
                f"죽음 굴림 — 성공 {ds.successes}/{RULES.death.successes_to_stabilize}, "
                f"실패 {ds.failures}/{RULES.death.failures_to_die}.",
            )
        yield {
            "type": "pending_check",
            "data": pending_check_to_front(state, state.pending_check),
        }


# --- run_roll dispatcher ---------------------------------------------------


async def run_roll(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    *,
    to_front_fn: ToFrontFn | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    set_llm_session_if_unset(state.game_id)
    if state.pending_check is None:
        raise PendingCheckExpected("no pending_check; call /turn first")

    dirty = Dirty()
    pending = state.pending_check
    state.turn_count += 1

    rng_obj = rng or random
    dice = rng_obj.randint(1, 20)

    if pending.kind == "death_save":
        async for ev in _resolve_death_save(state, dirty, dice):
            yield ev
        tick_turn_buffs(state, dirty)
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if pending.kind == "combat_roll":
        async for ev in _resolve_combat_roll(
            client, state, profile_dir, dirty, dice, pending,
        ):
            yield ev
        tick_turn_buffs(state, dirty)
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    total = dice + pending.mod
    grade = compute_grade(dice, total, pending.required_roll)

    roll_log = RollLogEntry(
        id=next_log_id(state),
        kind="roll",
        check=stat_label(pending.stat),
        roll=dice,
        margin=total - pending.required_roll,
        result=front_grade(grade),
    )
    push_log_entry(state, roll_log, dirty)
    yield {"type": "log_entry", "data": roll_log.model_dump()}

    grant_roll_xp(state, grade, dirty=dirty.entities)

    judge_result = {
        "action": "roll",
        "tier": pending.tier,
        "stat": pending.stat,
        "targets": pending.targets,
    }
    stream = run_narrate(
        client,
        state,
        profile_dir,
        pending.player_input,
        judge_result=judge_result,
        grade=grade,
        target_id=pending.target,
    )
    async for ev in consume_narrate(
        state,
        dirty,
        stream,
        target_for_log=pending.target,
        dialogue_input=pending.player_input,
    ):
        yield ev

    state.pending_check = None
    tick_turn_buffs(state, dirty)

    if state.combat_state is not None:
        # Environment rolls cost the player one combat turn — NPC phase resumes.
        combat_engine.advance_turn(state)
        async for ev in run_combat_npc_phase(state, dirty, rng):
            yield ev

    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
