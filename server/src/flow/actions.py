"""Per-action emit handlers — each one mutates state via an engine, pushes a
log entry, and yields SSE events. Used by both combat and non-combat dispatch.
"""

import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal

from pydantic import ValidationError

from ..agents.dc_judge.schema import RollAction
from ..domain.errors import (
    InventoryInvalid,
    LevelUpInvalid,
    LLMUnavailable,
    PersistenceFailed,
)
from ..domain.memory import PendingCheck
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..engines import inventory as inventory_engine
from ..engines import skill as skill_engine
from ..engines.apply import apply_combat_affinity_drop
from ..engines.growth import (
    award_kill_xp,
    level_up as level_up_engine,
)
from ..engines.invariants import InvariantViolation, check_character
from ..engines.quest import check_quests
from ..llm.client import LLMClient
from ..mapping.josa import eul_reul, eun_neun, i_ga
from ..mapping.to_front import pending_check_to_front
from ..persistence.repo import SaveRepo
from ..rules.dc import compute_required_roll, pick_dc, social_bonus
from .dirty import (
    Dirty,
    flush,
    push_act,
    push_turn_log,
    register_kill,
)
from .error_phrases import humanize_engine_error, humanize_runtime_error
from .format import format_use_log
from .skill_recommend import recommend_skill_candidates


def _item_name(state: GameState, item_id: str) -> str:
    item = state.items.get(item_id)
    return item.name if item else item_id


def _fail_text(actor_name: str, attempt: str, e: Exception) -> str:
    return f"{actor_name}{i_ga(actor_name)} {attempt} {humanize_engine_error(e)}."


def apply_attack_action(
    state: GameState,
    attacker_id: str,
    target_id: str,
    outcome: combat_engine.AttackOutcome,
    dirty: Dirty,
) -> dict:
    """Silent attack effect: damage routing → affinity drop → kill XP.
    No SSE, no log_entry, no push_act. Returns the apply_attack_to_defender
    result (or a no-op dict when no damage was applied) plus a `killed` flag."""
    target = state.characters[target_id]
    apply_result: dict | None = None
    if outcome.damage > 0 and target.alive:
        apply_result = combat_engine.apply_attack_to_defender(
            state,
            target_id,
            outcome.damage,
            nat_d20=outcome.nat_d20,
            dirty=dirty.entities,
        )
        combat_engine.record_damage(state, attacker_id, outcome.damage)
    apply_combat_affinity_drop(state, attacker_id, target_id, dirty=dirty.entities)
    killed = not target.alive
    if killed:
        award_kill_xp(state, attacker_id, target_id, dirty=dirty.entities)
        register_kill(state, target_id, dirty)
    elif attacker_id == state.player_id:
        push_turn_log(
            state, target_id, f"{target.name}{eul_reul(target.name)} 공격", dirty
        )
    return {
        "apply_result": apply_result
        or {
            "hp_before": target.hp,
            "hp_after": target.hp,
            "downed": False,
            "dying": False,
            "dead": False,
            "revived": False,
        },
        "killed": killed,
    }


def apply_skill_action(
    state: GameState,
    actor_id: str,
    skill_id: str,
    targets: list[str],
    dirty: Dirty,
    rng: random.Random | None = None,
) -> dict:
    """Silent skill cast: validate, roll grade, apply effects, route kills.
    No SSE, no log_entry, no push_act. Raises SkillInvalid on validation
    failure. Returns the cast_result dict augmented with `grade`,
    `skill_type`, and `killed_ids`."""
    actor = state.characters[actor_id]
    skill_obj = skill_engine.find_skill(actor, skill_id, state)
    grade, _nat, _req = skill_engine.compute_cast_grade(
        actor, skill_obj, state, targets, rng=rng
    )
    cast_result = skill_engine.cast(
        actor, skill_id, state, targets, grade=grade, dirty=dirty.entities
    )
    killed_ids: list[str] = []
    for eff in cast_result["effects"]:
        if eff.get("kind") == "attack":
            combat_engine.record_damage(state, actor_id, int(eff.get("damage", 0)))
            if eff.get("dead"):
                award_kill_xp(state, actor_id, eff["target"], dirty=dirty.entities)
                register_kill(state, eff["target"], dirty)
                killed_ids.append(eff["target"])
    if skill_obj.type in ("attack", "debuff"):
        for tid in targets:
            apply_combat_affinity_drop(state, actor_id, tid, dirty=dirty.entities)
    if actor_id == state.player_id and targets:
        first_t = state.characters.get(targets[0])
        if first_t is not None and first_t.id != actor_id:
            push_turn_log(
                state,
                first_t.id,
                f"「{cast_result['skill_name']}」 → {first_t.name}",
                dirty,
            )
    return {
        **cast_result,
        "grade": grade,
        "skill_type": skill_obj.type,
        "killed_ids": killed_ids,
    }


async def emit_equip(
    state: GameState,
    actor_id: str,
    item_id: str,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    item = state.items.get(item_id)
    item_name = item.name if item else item_id
    try:
        if item is None:
            raise InventoryInvalid(f"unknown item: {item_id}")
        slot = inventory_engine.auto_equip_slot(actor, item)
        inventory_engine.equip(actor, item_id, slot, state.items)
    except InventoryInvalid as e:
        yield push_act(
            state,
            dirty,
            _fail_text(
                actor.name, f"「{item_name}」{eul_reul(item_name)} 장비하려 했지만", e
            ),
        )
        return
    dirty.entities.add(("characters", actor_id))
    yield push_act(
        state,
        dirty,
        f"{actor.name}{i_ga(actor.name)} 「{item_name}」{eul_reul(item_name)} 장비했습니다.",
    )


async def emit_unequip(
    state: GameState,
    actor_id: str,
    item_id: str,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    item_name = _item_name(state, item_id)
    try:
        slot = inventory_engine.unequip_by_item(actor, item_id)
    except InventoryInvalid as e:
        yield push_act(
            state,
            dirty,
            _fail_text(
                actor.name, f"「{item_name}」{eul_reul(item_name)} 해제하려 했지만", e
            ),
        )
        return
    if slot is None:
        text = f"{actor.name}{eun_neun(actor.name)} 「{item_name}」{eul_reul(item_name)} 장비하고 있지 않습니다."
    else:
        text = f"{actor.name}{i_ga(actor.name)} 「{item_name}」{eul_reul(item_name)} 해제했습니다."
        dirty.entities.add(("characters", actor_id))
    yield push_act(state, dirty, text)


async def emit_use(
    state: GameState,
    actor_id: str,
    item_id: str,
    target_id: str | None,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    target = state.characters.get(target_id) if target_id else None
    try:
        result = inventory_engine.use(
            actor, item_id, target, state, dirty=dirty.entities
        )
    except InventoryInvalid as e:
        item_name = _item_name(state, item_id)
        yield push_act(
            state,
            dirty,
            _fail_text(
                actor.name, f"「{item_name}」{eul_reul(item_name)} 쓰려 했지만", e
            ),
        )
        return
    check_quests(state, "item_use", item_id, dirty.entities)
    yield push_act(state, dirty, format_use_log(state, actor_id, result))
    if target is not None:
        item_name = _item_name(state, item_id)
        push_turn_log(
            state,
            target.id,
            f"{item_name}{eul_reul(item_name)} {target.name}에게 사용",
            dirty,
        )


async def emit_level_up(
    state: GameState,
    actor_id: str,
    stat_up: str,
    stat_down: str,
    client: LLMClient | None,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    try:
        level_up_engine(actor, stat_up, stat_down)  # type: ignore[arg-type]
    except LevelUpInvalid as e:
        yield push_act(state, dirty, _fail_text(actor.name, "레벨업하려 했지만", e))
        return
    violations = check_character(actor)
    if violations:
        raise InvariantViolation(
            "post-level_up invariant violation:\n" + "\n".join(violations)
        )
    dirty.entities.add(("characters", actor_id))
    yield push_act(
        state,
        dirty,
        f"{actor.name}의 레벨이 올랐습니다 "
        f"(레벨 {actor.level}, {stat_up} ↑ / {stat_down} ↓, HP {actor.max_hp} / MP {actor.max_mp}).",
    )
    if client is None:
        state.pending_skill_candidates = []
        return
    try:
        state.pending_skill_candidates = await recommend_skill_candidates(client, state)
    except (ValidationError, LLMUnavailable, OSError, TimeoutError):
        state.pending_skill_candidates = []
    if state.pending_skill_candidates:
        names = ", ".join(f"「{s.name}」" for s in state.pending_skill_candidates)
        yield push_act(state, dirty, f"새 기술 후보: {names}")


async def emit_learn_skill(
    state: GameState,
    actor_id: str,
    index: int,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    candidates = list(state.pending_skill_candidates)
    if not candidates or index < 0 or index >= len(candidates):
        yield push_act(
            state,
            dirty,
            f"{actor.name}{i_ga(actor.name)} 익힐 만한 기술을 찾지 못했습니다.",
        )
        return
    chosen = candidates[index]
    state.skills[chosen.id] = chosen
    actor.learned_skill_ids.append(
        chosen.id
    )  # ssot-allow: write path — graph rebuilds at next turn boundary.
    state.pending_skill_candidates = []
    dirty.entities.add(("characters", actor_id))
    dirty.entities.add(("skills", chosen.id))
    yield push_act(
        state,
        dirty,
        f"{actor.name}{i_ga(actor.name)} 「{chosen.name}」{eul_reul(chosen.name)} 익혔습니다.",
    )


async def emit_trade(
    state: GameState,
    actor_id: str,
    npc_id: str,
    item_id: str,
    dirty: Dirty,
    *,
    direction: Literal["buy", "sell"],
) -> AsyncIterator[dict]:
    player = state.characters[actor_id]
    npc = state.characters.get(npc_id)
    if npc is None:
        yield push_act(
            state,
            dirty,
            f"{player.name}{i_ga(player.name)} 거래할 상대를 찾지 못했습니다.",
        )
        return
    try:
        if direction == "buy":
            price = inventory_engine.buy(player, npc, item_id, state.items)
        else:
            price = inventory_engine.sell(player, npc, item_id, state.items)
    except InventoryInvalid as e:
        yield push_act(state, dirty, _fail_text(player.name, "거래를 시도했지만", e))
        return
    dirty.entities.add(("characters", actor_id))
    dirty.entities.add(("characters", npc.id))
    item_name = _item_name(state, item_id)
    if direction == "buy":
        text = f"{player.name}{i_ga(player.name)} {npc.name}에게서 「{item_name}」{eul_reul(item_name)} {price} 금화에 샀습니다."
    else:
        text = f"{player.name}{i_ga(player.name)} {npc.name}에게 「{item_name}」{eul_reul(item_name)} {price} 금화에 팔았습니다."
    yield push_act(state, dirty, text)
    push_turn_log(
        state,
        npc.id,
        f"{npc.name}에게 「{item_name}」 {'구매' if direction == 'buy' else '판매'}",
        dirty,
    )


async def emit_give(
    state: GameState,
    from_id: str,
    to_id: str,
    item_id: str,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    src = state.characters.get(from_id)
    dst = state.characters.get(to_id)
    actor_name = state.characters[state.player_id].name
    if src is None or dst is None:
        yield push_act(
            state,
            dirty,
            f"{actor_name}{i_ga(actor_name)} 양도 상대를 찾지 못했습니다.",
        )
        return
    try:
        inventory_engine.transfer(src, dst, item_id, state.items)
    except InventoryInvalid as e:
        yield push_act(state, dirty, _fail_text(actor_name, "양도를 시도했지만", e))
        return
    dirty.entities.add(("characters", from_id))
    dirty.entities.add(("characters", to_id))
    item_name = _item_name(state, item_id)
    text = f"{src.name}에게서 {dst.name}{i_ga(dst.name)} 「{item_name}」{eul_reul(item_name)} 받았습니다." if dst.is_player else f"{src.name}{i_ga(src.name)} {dst.name}에게 「{item_name}」{eul_reul(item_name)} 건넸습니다."
    yield push_act(state, dirty, text)
    push_turn_log(
        state,
        to_id if dst.is_player else from_id,
        f"「{item_name}」 양도 ({src.name} → {dst.name})",
        dirty,
    )


async def emit_roll_pending(
    state: GameState,
    save_repo: SaveRepo,
    player_input: str,
    result: RollAction,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    """Set pending_check, flush, emit pending_check SSE. Shared between
    /turn and the in-combat roll branch."""
    actor = state.characters[state.player_id]
    # Pick the candidate who likes the actor least — the "hardest" target.
    # Non-character entries (locations, items) score 0, so character targets
    # with negative aff lose the tiebreak first, neutral ties fall through.
    def _aff_against_actor(t: str) -> int:
        npc = state.characters.get(t)
        return 0 if npc is None else npc.relations.get(actor.id, 0)

    target = min(result.targets, key=_aff_against_actor)
    dc = pick_dc(result.tier)
    stat_value = getattr(actor.stats, result.stat)
    required_roll = compute_required_roll(dc, stat_value)
    target_char = state.characters.get(target)
    mod = social_bonus(target_char, actor.id) if target_char is not None else 0
    state.pending_check = PendingCheck(
        player_input=player_input,
        tier=result.tier,
        stat=result.stat,
        target=target,
        targets=list(result.targets),
        dc=dc,
        mod=mod,
        required_roll=required_roll,
        reason=result.reason,
        created_at=datetime.now(UTC).isoformat(),
    )
    try:
        await flush(state, save_repo, dirty)
    except PersistenceFailed as e:
        yield {
            "type": "error",
            "data": {
                "message": humanize_runtime_error(e),
                "code": "PersistenceFailed",
            },
        }
        return
    yield {
        "type": "pending_check",
        "data": pending_check_to_front(state, state.pending_check),
    }
