"""Per-action emit handlers — each one mutates state via an engine, pushes a
log entry, and yields SSE events. Used by both combat and non-combat dispatch.
"""
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal

from ..agents.dc_judge.schema import RollAction
from ..domain.errors import (
    InventoryInvalid,
    LevelUpInvalid,
    PersistenceFailed,
    SkillInvalid,
)
from ..domain.memory import ActLogEntry, GMLogEntry, PendingCheck
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..engines import inventory as inventory_engine
from ..engines import skill as skill_engine
from ..engines.growth import level_up as level_up_engine
from ..llm.client import LLMClient
from ..rules.dc import pick_dc, sigmoid_required_roll, social_bonus, tier_to_int
from .dirty import Dirty, flush, next_log_id, push_log_entry
from .format import (
    format_attack_log,
    format_roll_announce,
    format_skill_log,
    format_use_log,
)
from .skill_recommend import recommend_skill_candidates


def _push_gm(state: GameState, dirty: Dirty, text: str) -> dict:
    log = GMLogEntry(id=next_log_id(state), kind="gm", text=text)
    push_log_entry(state, log, dirty)
    return {"type": "log_entry", "data": log.model_dump()}


def _push_act(state: GameState, dirty: Dirty, text: str) -> dict:
    log = ActLogEntry(id=next_log_id(state), kind="act", text=text)
    push_log_entry(state, log, dirty)
    return {"type": "log_entry", "data": log.model_dump()}


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
        yield _push_gm(state, dirty, text)
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
            break


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
        skill_obj = skill_engine.find_skill(actor, skill_id)
    except SkillInvalid as e:
        yield _push_gm(state, dirty, f"{actor.name} — 스킬 발동 실패 ({e}).")
        return
    grade, _nat, _req = skill_engine.compute_cast_grade(
        actor, skill_obj, state, targets, rng=rng
    )
    try:
        cast_result = skill_engine.cast(
            actor, skill_id, state, targets, grade=grade, dirty=dirty.entities
        )
    except SkillInvalid as e:
        yield _push_gm(state, dirty, f"{actor.name} — 스킬 발동 실패 ({e}).")
        return
    for eff in cast_result["effects"]:
        if eff.get("kind") == "attack":
            combat_engine.record_damage(state, actor_id, int(eff.get("damage", 0)))
    yield _push_gm(state, dirty, format_skill_log(state, actor_id, cast_result, grade))
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
        slot = inventory_engine.equip_auto(actor, item_id, state.items)
    except InventoryInvalid as e:
        yield _push_gm(state, dirty, f"{actor.name} — 장착 실패 ({e}).")
        return
    dirty.entities.add(("characters", actor_id))
    yield _push_gm(state, dirty, f"{actor.name} — 「{item_name}」 장착 ({slot})")


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
        yield _push_gm(state, dirty, f"{actor.name} — 해제 실패 ({e}).")
        return
    if slot is None:
        text = f"{actor.name} — 「{item_name}」 은(는) 장착돼 있지 않다."
    else:
        text = f"{actor.name} — 「{item_name}」 해제 ({slot})"
        dirty.entities.add(("characters", actor_id))
    yield _push_gm(state, dirty, text)


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
        result = inventory_engine.use_with_quest_hook(
            actor, item_id, target, state.items, state, dirty=dirty.entities
        )
    except InventoryInvalid as e:
        yield _push_gm(state, dirty, f"{actor.name} — 아이템 사용 실패 ({e}).")
        return
    yield _push_gm(state, dirty, format_use_log(state, actor_id, result))


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
        yield _push_gm(state, dirty, f"{actor.name} — 성장 실패 ({e}).")
        return
    dirty.entities.add(("characters", actor_id))
    yield _push_gm(
        state, dirty,
        f"{actor.name} — 레벨 {actor.level} 도달 "
        f"({stat_up} ↑ / {stat_down} ↓, HP {actor.max_hp} / MP {actor.max_mp})",
    )
    if client is None:
        state.pending_skill_candidates = []
        return
    try:
        state.pending_skill_candidates = await recommend_skill_candidates(client, state)
    except Exception:
        state.pending_skill_candidates = []
    if state.pending_skill_candidates:
        names = ", ".join(f"「{s.name}」" for s in state.pending_skill_candidates)
        yield _push_act(state, dirty, f"새 스킬 후보: {names}")


async def emit_learn_skill(
    state: GameState,
    actor_id: str,
    index: int,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    candidates = list(state.pending_skill_candidates)
    if not candidates or index < 0 or index >= len(candidates):
        yield _push_gm(state, dirty, f"{actor.name} — 익힐 후보가 없거나 잘못된 선택.")
        return
    chosen = candidates[index]
    actor.learned_skills.append(chosen)
    state.pending_skill_candidates = []
    dirty.entities.add(("characters", actor_id))
    yield _push_gm(state, dirty, f"{actor.name} — 「{chosen.name}」 습득.")


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
        yield _push_gm(state, dirty, f"{player.name} — 거래 상대를 찾을 수 없다.")
        return
    try:
        if direction == "buy":
            price = inventory_engine.buy(player, npc, item_id, state.items)
        else:
            price = inventory_engine.sell(player, npc, item_id, state.items)
    except InventoryInvalid as e:
        yield _push_gm(state, dirty, f"{player.name} — 거래 실패 ({e}).")
        return
    dirty.entities.add(("characters", actor_id))
    dirty.entities.add(("characters", npc.id))
    item = state.items.get(item_id)
    iname = item.name if item else item_id
    verb = "구매" if direction == "buy" else "판매"
    yield _push_gm(
        state, dirty,
        f"{player.name} — {npc.name}에게 「{iname}」 {verb} ({price} 금)",
    )


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
    yield _push_act(
        state, dirty,
        format_roll_announce(state, result, target, mod, required_roll),
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
        "data": {
            "dc": dc,
            "stat": result.stat,
            "mod": mod,
            "required_roll": required_roll,
            "tier": {
                "value": tier_to_int(result.tier),
                "max": 7,
                "label": result.tier,
            },
            "target": target,
        },
    }
