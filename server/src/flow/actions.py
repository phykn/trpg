"""Per-action emit handlers — each one mutates state via an engine, pushes a
log entry, and yields SSE events. Used by both combat and non-combat dispatch.
"""

import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal

from pydantic import ValidationError

from ..llm_calls.classify.schema import RollAction
from ..domain.errors import (
    InventoryInvalid,
    LevelUpInvalid,
    LLMUnavailable,
    PersistenceFailed,
)
from ..domain.memory import PendingCheck, PendingGrowth
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..engines import inventory as inventory_engine
from ..engines import skill as skill_engine
from ..engines.apply import apply_changes, apply_combat_affinity_drop
from ..engines.growth import (
    award_kill_xp,
    level_up as level_up_engine,
)
from ..engines.invariants import InvariantViolation, check_character
from ..engines.quest import check_quests
from ..llm.client import LLMClient
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
from .error_phrases import humanize_runtime_error
from .format import (
    format_action_fail,
    format_attack_turn_log,
    format_equip_fail,
    format_equip_log,
    format_give_log,
    format_give_no_partner,
    format_give_turn_log,
    format_learn_skill_log,
    format_learn_skill_no_candidate,
    format_level_up_log,
    format_move_blocked,
    format_move_log,
    format_move_no_path,
    format_skill_candidates_log,
    format_trade_log,
    format_trade_no_partner,
    format_trade_turn_log,
    format_unequip_fail,
    format_unequip_log,
    format_unequip_not_equipped,
    format_use_fail,
    format_use_log,
    format_use_target_turn_log,
)
from .skill_recommend import recommend_skill_candidates


def _item_name(state: GameState, item_id: str) -> str:
    item = state.items.get(item_id)
    return item.name if item else item_id


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
        # Drop affinity only when the strike actually lands. Whiffed swings still register
        # as hostile intent narratively, but compounding the drop on misses pushes NPCs
        # past the trade-gating threshold far faster than the design intends.
        apply_combat_affinity_drop(state, attacker_id, target_id, dirty=dirty.entities)
    killed = not target.alive
    if killed:
        award_kill_xp(state, attacker_id, target_id, dirty=dirty.entities)
        register_kill(state, target_id, dirty)
    elif attacker_id == state.player_id:
        push_turn_log(state, target_id, format_attack_turn_log(target.name), dirty)
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
        yield push_act(state, dirty, format_equip_fail(actor.name, item_name, e))
        return
    dirty.entities.add(("characters", actor_id))
    yield push_act(state, dirty, format_equip_log(actor.name, item_name))


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
        yield push_act(state, dirty, format_unequip_fail(actor.name, item_name, e))
        return
    if slot is None:
        text = format_unequip_not_equipped(actor.name, item_name)
    else:
        text = format_unequip_log(actor.name, item_name)
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
        yield push_act(
            state, dirty, format_use_fail(actor.name, _item_name(state, item_id), e)
        )
        return
    check_quests(state, "item_use", item_id, dirty.entities)
    yield push_act(state, dirty, format_use_log(state, actor_id, result))
    if target is not None:
        push_turn_log(
            state,
            target.id,
            format_use_target_turn_log(_item_name(state, item_id), target.name),
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
    state.pending_growth = (
        None  # answered (or never asked) — clear the pending question
    )
    actor = state.characters[actor_id]
    try:
        level_up_engine(actor, stat_up, stat_down)  # type: ignore[arg-type]
    except LevelUpInvalid as e:
        yield push_act(
            state, dirty, format_action_fail(actor.name, "레벨업하려 했지만", e)
        )
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
        format_level_up_log(
            actor.name, actor.level, stat_up, stat_down, actor.max_hp, actor.max_mp
        ),
    )
    if client is None:
        state.pending_skill_candidates = []
        return
    try:
        state.pending_skill_candidates = await recommend_skill_candidates(client, state)
    except (ValidationError, LLMUnavailable, OSError, TimeoutError):
        state.pending_skill_candidates = []
    if state.pending_skill_candidates:
        yield push_act(
            state,
            dirty,
            format_skill_candidates_log(
                [s.name for s in state.pending_skill_candidates]
            ),
        )


async def emit_learn_skill(
    state: GameState,
    actor_id: str,
    index: int,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    candidates = list(state.pending_skill_candidates)
    if not candidates or index < 0 or index >= len(candidates):
        yield push_act(state, dirty, format_learn_skill_no_candidate(actor.name))
        return
    chosen = candidates[index]
    state.skills[chosen.id] = chosen
    if chosen.id not in actor.learned_skill_ids:
        actor.learned_skill_ids.append(
            chosen.id
        )  # ssot-allow: write path — graph rebuilds at next turn boundary.
    state.pending_skill_candidates = []
    dirty.entities.add(("characters", actor_id))
    dirty.entities.add(("skills", chosen.id))
    yield push_act(state, dirty, format_learn_skill_log(actor.name, chosen.name))


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
        yield push_act(state, dirty, format_trade_no_partner(player.name))
        return
    try:
        if direction == "buy":
            price = inventory_engine.buy(player, npc, item_id, state.items)
        else:
            price = inventory_engine.sell(player, npc, item_id, state.items)
    except InventoryInvalid as e:
        yield push_act(
            state, dirty, format_action_fail(player.name, "거래를 시도했지만", e)
        )
        return
    dirty.entities.add(("characters", actor_id))
    dirty.entities.add(("characters", npc.id))
    item_name = _item_name(state, item_id)
    yield push_act(
        state,
        dirty,
        format_trade_log(player.name, npc.name, item_name, price, direction=direction),
    )
    push_turn_log(
        state,
        npc.id,
        format_trade_turn_log(npc.name, item_name, direction=direction),
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
        yield push_act(state, dirty, format_give_no_partner(actor_name))
        return
    try:
        inventory_engine.transfer(src, dst, item_id, state.items)
    except InventoryInvalid as e:
        yield push_act(
            state, dirty, format_action_fail(actor_name, "양도를 시도했지만", e)
        )
        return
    dirty.entities.add(("characters", from_id))
    dirty.entities.add(("characters", to_id))
    item_name = _item_name(state, item_id)
    yield push_act(
        state,
        dirty,
        format_give_log(src.name, dst.name, item_name, dst_is_player=dst.is_player),
    )
    push_turn_log(
        state,
        to_id if dst.is_player else from_id,
        format_give_turn_log(src.name, dst.name, item_name),
        dirty,
    )


async def emit_move(
    state: GameState,
    actor_id: str,
    destination: str,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    loc = state.locations.get(destination)
    if loc is None:
        yield push_act(state, dirty, format_move_no_path(actor.name))
        return
    result = apply_changes(
        state,
        [{"type": "move", "target": actor_id, "destination": destination}],
        dirty.entities,
    )
    if result["applied"] == 0:
        reason = result["rejected"][0]["reason"] if result["rejected"] else ""
        yield push_act(state, dirty, format_move_blocked(actor.name, loc.name, reason))
        return
    state.invalidate_graph()
    if actor_id == state.player_id:
        from .subject import reconcile_subject_after_move

        reconcile_subject_after_move(state)
    yield push_act(state, dirty, format_move_log(actor.name, loc.name))


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


async def emit_growth_pending(
    state: GameState,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    state.pending_growth = PendingGrowth(stage="asking_stat")
    return
    yield  # makes this an async generator


async def emit_cancel_growth(
    state: GameState,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    state.pending_growth = None
    return
    yield  # makes this an async generator
