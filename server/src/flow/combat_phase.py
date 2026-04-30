"""Combat-phase orchestration. Drives NPC turns automatically, dispatches the
player's chosen action mid-combat, and bridges to /roll when the player
reaches for the environment.
"""
import random
from collections.abc import AsyncIterator
from typing import Literal

from ..agents.dc_judge.schema import (
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
from ..mapping.josa import eun_neun, gwa_wa, i_ga
from ..rules import RULES
from .actions import (
    emit_attack,
    emit_equip,
    emit_roll_pending,
    emit_skill_cast,
    emit_unequip,
    emit_use,
)
from .clock import tick_turn_buffs
from .dirty import Dirty, ToFrontFn, finalize, push_act, push_turn_log
from .format import format_combat_end_text
from .judge import run_judge
from .subject import refresh_active_subject


# --- NPC phase -------------------------------------------------------------


async def _handle_surprise_skip(
    state: GameState, dirty: Dirty, actor_id: str
) -> AsyncIterator[dict]:
    """First-round surprise — yield the skip GM line + combat_turn event,
    advance the turn. Caller decides whether the skip applies."""
    actor_name = (
        state.characters[actor_id].name
        if actor_id in state.characters
        else actor_id
    )
    yield push_act(
        state, dirty,
        f"{actor_name}{eun_neun(actor_name)} 기습당해 첫 라운드 행동하지 못한다.",
    )
    yield {
        "type": "combat_turn",
        "data": {"actor": actor_id, "action": "skip", "grade": "success"},
    }
    combat_engine.advance_turn(state)


def _is_surprise_skip(state: GameState, actor_id: str) -> bool:
    cs = state.combat_state
    if cs is None or cs.round != 1 or cs.surprise is None:
        return False
    is_player = actor_id == state.player_id
    return (cs.surprise == "enemy" and is_player) or (
        cs.surprise == "player" and not is_player
    )


async def run_combat_npc_phase(
    state: GameState,
    dirty: Dirty,
    rng: random.Random | None,
) -> AsyncIterator[dict]:
    """Auto-run NPC turns until the current actor is the player, or combat
    ends. On end, emits combat_end + clears combat_state."""
    while True:
        end = combat_engine.check_combat_end(state)
        if end is not None:
            yield push_act(state, dirty, format_combat_end_text(end))
            yield {"type": "combat_end", "data": {"outcome": end}}
            combat_engine.end_combat(state)
            return

        actor_id = combat_engine.current_actor_id(state)
        if actor_id is None:
            yield {"type": "combat_end", "data": {"outcome": "victory"}}
            combat_engine.end_combat(state)
            return

        if _is_surprise_skip(state, actor_id):
            async for ev in _handle_surprise_skip(state, dirty, actor_id):
                yield ev
            continue

        if actor_id == state.player_id:
            return

        actor = state.characters.get(actor_id)
        if actor is None or not actor.alive:
            combat_engine.advance_turn(state)
            continue

        # NPC flee
        if combat_engine.should_attempt_flee(actor, rng=rng):
            ok, _roll = combat_engine.try_flee(actor, rng=rng)
            if ok:
                yield push_act(state, dirty, f"{actor.name}{i_ga(actor.name)} 전투에서 도주했다.")
                yield {
                    "type": "combat_turn",
                    "data": {"actor": actor_id, "action": "flee", "grade": "success"},
                }
                combat_engine.remove_from_combat(state, actor_id)
                continue
            yield push_act(state, dirty, f"{actor.name}{i_ga(actor.name)} 도주를 시도했으나 실패했다.")
            yield {
                "type": "combat_turn",
                "data": {"actor": actor_id, "action": "flee", "grade": "failure"},
            }
            combat_engine.advance_turn(state)
            continue

        # NPC attack
        target = combat_engine.pick_npc_target(state, actor_id, rng=rng)
        if target is None:
            combat_engine.advance_turn(state)
            continue
        outcome = combat_engine.attack(actor, target, state.items, rng=rng)
        async for ev in emit_attack(state, actor_id, target.id, outcome, dirty):
            yield ev
        combat_engine.advance_turn(state)


async def start_combat_and_run_npc_phase(
    state: GameState,
    enemy_ids: list[str],
    dirty: Dirty,
    rng: random.Random | None,
    surprise: Literal["player", "enemy"] | None = None,
) -> AsyncIterator[dict]:
    # /turn routes through run_combat_player_turn whenever combat_state is
    # set, so we should never reach this with a live combat already pinned.
    # If we do, that's a state-machine bug (something forgot to call
    # end_combat); silently re-using stale combat_state with brand-new
    # enemy_ids would mask it.
    if state.combat_state is not None:
        raise CombatStateInvalid(
            "start_combat called while combat_state is already set "
            f"(stale enemy_ids={list(state.combat_state.enemy_ids)}, "
            f"new enemy_ids={enemy_ids})"
        )
    cs = combat_engine.start_combat(state, enemy_ids, rng=rng, surprise=surprise)
    yield push_act(state, dirty, "전투 개시!")
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
                state, first_enemy.id,
                f"{first_enemy.name}{gwa_wa(first_enemy.name)} 전투 개시",
                dirty,
            )
    async for ev in run_combat_npc_phase(state, dirty, rng):
        yield ev


# --- player turn while in combat ------------------------------------------


async def _flush_player_turn(
    state: GameState,
    saves_dir: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    """Common tail after the player's combat action: NPC phase → bump turn →
    advance time → finalize."""
    async for ev in run_combat_npc_phase(state, dirty, rng):
        yield ev
    state.turn_count += 1
    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev


async def _handle_death_save(
    state: GameState,
    saves_dir: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    player = state.characters[state.player_id]
    status, roll = combat_engine.tick_death_save(
        state, state.player_id, rng=rng, dirty=dirty.entities
    )
    ds_grade = "success" if roll >= RULES.death.save_dc else "failure"
    text = f"{player.name} 죽음 굴림 (d20={roll}) — "
    if status == "stable":
        text += "안정화 — 의식을 회복했다."
    elif status == "dead":
        text += "사망."
    else:
        ds = player.death_saves
        text += (
            f"성공 {ds.successes}/3, 실패 {ds.failures}/3."
            if ds is not None
            else "성공/실패."
        )
    yield push_act(state, dirty, text)
    yield {
        "type": "combat_turn",
        "data": {"actor": state.player_id, "action": "death_save", "grade": ds_grade},
    }
    if status != "dead":
        combat_engine.advance_turn(state)
    async for ev in _flush_player_turn(state, saves_dir, dirty, rng, to_front_fn):
        yield ev


async def _handle_combat_action(
    state: GameState,
    saves_dir: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    result: CombatAction,
) -> AsyncIterator[dict]:
    player = state.characters[state.player_id]
    target_id = result.targets[0]
    target = state.characters.get(target_id)
    if target_id == state.player_id or target is None or not target.alive:
        yield push_act(state, dirty, "그 대상은 공격할 수 없다.")
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return
    if result.skill_id:
        async for ev in emit_skill_cast(
            state, state.player_id, result.skill_id, list(result.targets), dirty, rng=rng
        ):
            yield ev
    else:
        outcome = combat_engine.attack(player, target, state.items, rng=rng)
        async for ev in emit_attack(state, state.player_id, target_id, outcome, dirty):
            yield ev
    combat_engine.advance_turn(state)
    async for ev in _flush_player_turn(state, saves_dir, dirty, rng, to_front_fn):
        yield ev


async def _handle_flee(
    state: GameState,
    saves_dir: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    player = state.characters[state.player_id]
    ok, roll_total = combat_engine.try_flee(player, rng=rng)
    if ok:
        yield push_act(
            state, dirty,
            f"{player.name}{i_ga(player.name)} 전투에서 도주했다 (굴림 {roll_total}).",
        )
        yield {
            "type": "combat_turn",
            "data": {"actor": state.player_id, "action": "flee", "grade": "success"},
        }
        yield {"type": "combat_end", "data": {"outcome": "fled"}}
        combat_engine.end_combat(state)
        state.turn_count += 1
        tick_turn_buffs(state, dirty)
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return
    yield push_act(
        state, dirty,
        f"{player.name}{i_ga(player.name)} 도주를 시도했으나 실패했다 (굴림 {roll_total}).",
    )
    yield {
        "type": "combat_turn",
        "data": {"actor": state.player_id, "action": "flee", "grade": "failure"},
    }
    combat_engine.advance_turn(state)
    async for ev in _flush_player_turn(state, saves_dir, dirty, rng, to_front_fn):
        yield ev


async def _handle_passive_in_combat(
    state: GameState,
    saves_dir: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    *,
    emit: AsyncIterator[dict],
    action_label: str,
    item_id: str,
) -> AsyncIterator[dict]:
    """Shared shape for non-attack player actions in combat (use, equip,
    unequip). The engine action runs, a combat_turn event signals the
    action consumed the player turn, NPC phase follows."""
    async for ev in emit:
        yield ev
    yield {
        "type": "combat_turn",
        "data": {
            "actor": state.player_id,
            "action": action_label,
            "grade": "success",
            "item_id": item_id,
        },
    }
    combat_engine.advance_turn(state)
    async for ev in _flush_player_turn(state, saves_dir, dirty, rng, to_front_fn):
        yield ev


async def run_combat_player_turn(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    player_input: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    """Dispatch the player's mid-combat turn. death_save bypasses judge —
    everything else goes through judge → branch."""
    player = state.characters[state.player_id]

    if player.death_saves is not None:
        async for ev in _handle_death_save(state, saves_dir, dirty, rng, to_front_fn):
            yield ev
        return

    try:
        result = await run_judge(client, state, player_input)
    except JudgeMalformed as e:
        yield {"type": "error", "data": {"message": str(e), "code": "JudgeMalformed"}}
        return

    yield {"type": "judge", "data": result.model_dump()}

    refresh_active_subject(state, result)

    if isinstance(result, CombatAction):
        async for ev in _handle_combat_action(state, saves_dir, dirty, rng, to_front_fn, result):
            yield ev
        return

    if isinstance(result, FleeAction):
        async for ev in _handle_flee(state, saves_dir, dirty, rng, to_front_fn):
            yield ev
        return

    if isinstance(result, RollAction):
        # Environment roll — same shape as out-of-combat. /roll resumes NPC phase.
        async for ev in emit_roll_pending(state, saves_dir, player_input, result, dirty):
            yield ev
        return

    if isinstance(result, PassAction):
        yield push_act(
            state, dirty,
            f"{player.name}{eun_neun(player.name)} 자세를 가다듬으며 한 차례를 보낸다.",
        )
        yield {
            "type": "combat_turn",
            "data": {"actor": state.player_id, "action": "pass", "grade": "success"},
        }
        combat_engine.advance_turn(state)
        async for ev in _flush_player_turn(state, saves_dir, dirty, rng, to_front_fn):
            yield ev
        return

    if isinstance(result, RestAction):
        yield push_act(state, dirty, "전투 중에는 잠들 수 없다.")
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, UseAction):
        async for ev in _handle_passive_in_combat(
            state, saves_dir, dirty, rng, to_front_fn,
            emit=emit_use(state, state.player_id, result.item_id, result.target_id, dirty),
            action_label="use",
            item_id=result.item_id,
        ):
            yield ev
        return

    if isinstance(result, (EquipAction, UnequipAction)):
        if isinstance(result, EquipAction):
            emit = emit_equip(state, state.player_id, result.item_id, dirty)
            label = "equip"
        else:
            emit = emit_unequip(state, state.player_id, result.item_id, dirty)
            label = "unequip"
        async for ev in _handle_passive_in_combat(
            state, saves_dir, dirty, rng, to_front_fn,
            emit=emit, action_label=label, item_id=result.item_id,
        ):
            yield ev
        return

    # Reject in combat, or any growth/trade action that doesn't belong here.
    if isinstance(result, RejectAction):
        text = "그 말은 무시된다."
    else:
        text = "전투 중에는 그 행동을 할 수 없다."
    yield push_act(state, dirty, text)
    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
