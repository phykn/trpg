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
    SkillInvalid,
)
from ..domain.memory import PendingCheck
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..engines import inventory as inventory_engine
from ..engines import skill as skill_engine
from ..engines.growth import (
    award_kill_xp,
    level_up as level_up_engine,
)
from ..engines.invariants import InvariantViolation, check_character
from ..engines.quest import check_quests
from ..llm.client import LLMClient
from ..mapping.to_front import pending_check_to_front
from ..rules.dc import pick_dc, sigmoid_required_roll, social_bonus
from .dirty import (
    Dirty,
    flush,
    next_log_id,
    push_act,
    push_turn_log,
)
from .format import (
    format_attack_log,
    format_roll_announce,
    format_skill_log,
    format_use_log,
    humanize_engine_error,
)
from .skill_recommend import recommend_skill_candidates


# --- attack / skill cast ---------------------------------------------------


async def emit_attack(
    state: GameState,
    attacker_id: str,
    target_id: str,
    outcomes: list[combat_engine.AttackOutcome],
    dirty: Dirty,
) -> AsyncIterator[dict]:
    """Apply attack outcomes + emit SSE/log. If first hit kills the target,
    skip the second swing's narration."""
    target = state.characters[target_id]
    for outcome in outcomes:
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
        text = format_attack_log(state, attacker_id, target_id, outcome, apply_result)
        yield push_act(state, dirty, text)
        yield {
            "type": "combat_turn",
            "data": {
                "actor": attacker_id,
                "action": "attack",
                "grade": outcome.grade,
                "damage": outcome.damage,
                "target": target_id,
                "hand": outcome.hand,
            },
        }
        if not target.alive:
            award_kill_xp(state, attacker_id, target_id, dirty=dirty.entities)
            break
    if attacker_id == state.player_id:
        push_turn_log(state, target_id, f"{target.name}을 공격", dirty)


async def emit_skill_cast(
    state: GameState,
    actor_id: str,
    skill_id: str,
    targets: list[str],
    dirty: Dirty,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    """In-combat skill cast. attack/debuff roll d20 vs target defense / WIS
    resist. heal/buff/self stay at success."""
    actor = state.characters[actor_id]
    try:
        skill_obj = skill_engine.find_skill(actor, skill_id, state)
    except SkillInvalid as e:
        yield push_act(state, dirty, f"{actor.name}이(가) 스킬을 발동하려 했지만, {humanize_engine_error(e)}.")
        return
    grade, _nat, _req = skill_engine.compute_cast_grade(
        actor, skill_obj, state, targets, rng=rng
    )
    try:
        cast_result = skill_engine.cast(
            actor, skill_id, state, targets, grade=grade, dirty=dirty.entities
        )
    except SkillInvalid as e:
        yield push_act(state, dirty, f"{actor.name}이(가) 스킬을 발동하려 했지만, {humanize_engine_error(e)}.")
        return
    for eff in cast_result["effects"]:
        if eff.get("kind") == "attack":
            combat_engine.record_damage(state, actor_id, int(eff.get("damage", 0)))
            if eff.get("dead"):
                award_kill_xp(state, actor_id, eff["target"], dirty=dirty.entities)
    yield push_act(state, dirty, format_skill_log(state, actor_id, cast_result, grade))
    yield {
        "type": "combat_turn",
        "data": {
            "actor": actor_id,
            "action": "skill",
            "grade": grade,
            "skill_id": cast_result["skill_id"],
            "skill_name": cast_result["skill_name"],
            "effects": cast_result["effects"],
        },
    }
    if actor_id == state.player_id and targets:
        first_t = state.characters.get(targets[0])
        if first_t is not None and first_t.id != actor_id:
            push_turn_log(
                state, first_t.id,
                f"「{cast_result['skill_name']}」 → {first_t.name}",
                dirty,
            )


# --- equip / unequip / use -------------------------------------------------


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
        yield push_act(state, dirty, f"{actor.name}이(가) 「{item_name}」을(를) 차려 했지만, {humanize_engine_error(e)}.")
        return
    dirty.entities.add(("characters", actor_id))
    yield push_act(state, dirty, f"{actor.name}이(가) 「{item_name}」을(를) 차렸다.")


async def emit_unequip(
    state: GameState,
    actor_id: str,
    item_id: str,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    item = state.items.get(item_id)
    item_name = item.name if item else item_id
    try:
        slot = inventory_engine.unequip_by_item(actor, item_id, state.items)
    except InventoryInvalid as e:
        yield push_act(state, dirty, f"{actor.name}이(가) 「{item_name}」을(를) 풀려 했지만, {humanize_engine_error(e)}.")
        return
    if slot is None:
        text = f"{actor.name}은(는) 「{item_name}」을(를) 차고 있지 않다."
    else:
        text = f"{actor.name}이(가) 「{item_name}」을(를) 풀었다."
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
        item = state.items.get(item_id)
        item_name = item.name if item else item_id
        yield push_act(state, dirty, f"{actor.name}이(가) 「{item_name}」을(를) 쓰려 했지만, {humanize_engine_error(e)}.")
        return
    check_quests(state, "item_use", item_id, dirty.entities)
    yield push_act(state, dirty, format_use_log(state, actor_id, result))
    if target is not None:
        item = state.items.get(item_id)
        iname = item.name if item else item_id
        push_turn_log(state, target.id, f"{iname}을 {target.name}에게 사용", dirty)


# --- growth / trade --------------------------------------------------------


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
        yield push_act(state, dirty, f"{actor.name}이(가) 한 단계 오르려 했지만, {humanize_engine_error(e)}.")
        return
    violations = check_character(actor)
    if violations:
        raise InvariantViolation(
            "post-level_up invariant violation:\n" + "\n".join(violations)
        )
    dirty.entities.add(("characters", actor_id))
    yield push_act(
        state, dirty,
        f"{actor.name}이(가) 한 단계 올라 레벨 {actor.level}이(가) 됐다 "
        f"({stat_up} ↑ / {stat_down} ↓, HP {actor.max_hp} / MP {actor.max_mp}).",
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
        yield push_act(state, dirty, f"새 스킬 후보: {names}")


async def emit_learn_skill(
    state: GameState,
    actor_id: str,
    index: int,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    candidates = list(state.pending_skill_candidates)
    if not candidates or index < 0 or index >= len(candidates):
        yield push_act(state, dirty, f"{actor.name}이(가) 익힐 만한 갈래를 잡지 못했다.")
        return
    chosen = candidates[index]
    state.skills[chosen.id] = chosen
    actor.learned_skill_ids.append(chosen.id)
    state.pending_skill_candidates = []
    dirty.entities.add(("characters", actor_id))
    dirty.entities.add(("skills", chosen.id))
    yield push_act(state, dirty, f"{actor.name}이(가) 「{chosen.name}」을(를) 익혔다.")


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
        yield push_act(state, dirty, f"{player.name}이(가) 거래할 상대를 찾지 못했다.")
        return
    try:
        if direction == "buy":
            price = inventory_engine.buy(player, npc, item_id, state.items)
        else:
            price = inventory_engine.sell(player, npc, item_id, state.items)
    except InventoryInvalid as e:
        yield push_act(state, dirty, f"{player.name}이(가) 거래를 시도했지만, {humanize_engine_error(e)}.")
        return
    dirty.entities.add(("characters", actor_id))
    dirty.entities.add(("characters", npc.id))
    item = state.items.get(item_id)
    iname = item.name if item else item_id
    if direction == "buy":
        text = f"{player.name}이(가) {npc.name}에게서 「{iname}」을(를) {price} 금에 사 갔다."
    else:
        text = f"{player.name}이(가) {npc.name}에게 「{iname}」을(를) {price} 금에 넘겼다."
    yield push_act(state, dirty, text)
    push_turn_log(state, npc.id, f"{npc.name}에게 「{iname}」 {'구매' if direction == 'buy' else '판매'}", dirty)


# --- pending roll ----------------------------------------------------------


async def emit_roll_pending(
    state: GameState,
    saves_dir: str,
    player_input: str,
    result: RollAction,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    """Set pending_check, flush, emit pending_check SSE. Shared between
    /turn and the in-combat roll branch."""
    actor = state.characters[state.player_id]
    target = min(result.targets, key=lambda t: actor.relations.get(t, 0))
    dc = pick_dc(result.tier)
    stat_value = getattr(actor.stats, result.stat)
    required_roll = sigmoid_required_roll(dc, stat_value)
    mod = social_bonus(actor, target)
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
    yield push_act(
        state, dirty,
        format_roll_announce(state, result, target, dc),
    )
    try:
        await flush(state, saves_dir, dirty)
    except PersistenceFailed as e:
        yield {
            "type": "error",
            "data": {"message": str(e), "code": "PersistenceFailed"},
        }
        return
    yield {
        "type": "pending_check",
        "data": pending_check_to_front(state.pending_check),
    }
