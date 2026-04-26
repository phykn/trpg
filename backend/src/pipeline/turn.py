import random
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from ..domain.entities import Character
from ..domain.memory import (
    ActLogEntry,
    DialoguePair,
    GMLogEntry,
    LogEntry,
    PendingCheck,
    PlayerLogEntry,
    RollLogEntry,
    TurnLogEntry,
)
from ..domain.errors import (
    JudgeMalformed,
    PendingCheckActive,
    PendingCheckExpected,
    PersistenceFailed,
)
from ..agents.dc_judge.schema import (
    BuyAction,
    ClarifyAction,
    CombatAction,
    EquipAction,
    FleeAction,
    LearnSkillAction,
    LevelUpAction,
    PassAction,
    RejectAction,
    RestAction,
    RollAction,
    SellAction,
    UnequipAction,
    UseAction,
)
from ..agents.narrate import NarrativeDelta, NarrativeFinal
from ..llm.client import LLMClient
from ..rules import RULES
from ..domain.state import GameState
from ..persistence.store import (
    append_dialogue_entries,
    append_history_entries,
    append_log_entries,
    save_entity,
    save_meta,
)
from ..domain.errors import InventoryInvalid, LevelUpInvalid, SkillInvalid
from .apply import apply_changes
from . import combat as combat_engine
from . import encounter as encounter_engine
from . import inventory as inventory_engine
from . import recovery as recovery_engine
from . import skill as skill_engine
from ..rules.dc import compute_grade, pick_dc, sigmoid_required_roll, social_bonus, tier_to_int
from .growth import level_up as level_up_engine
from .judge import run_judge
from .memory_writer import write_memories
from .narrate import run_narrate
from .skill_recommend import recommend_skill_candidates

ToFrontFn = Callable[[GameState], dict]


# --- helpers ---------------------------------------------------------------


@dataclass
class _Dirty:
    """Persistence work accumulated during one turn.

    `entities`: (kind, id) pairs whose JSON file must be rewritten.
    `log/history/dialogue`: new entries to append to their respective jsonl.
    Meta is always saved at finalize, no flag needed.
    """

    entities: set[tuple[str, str]] = field(default_factory=set)
    log: list[LogEntry] = field(default_factory=list)
    history: list[TurnLogEntry] = field(default_factory=list)
    dialogue: list[DialoguePair] = field(default_factory=list)


def _trim(items: list, cap: int) -> None:
    while len(items) > cap:
        items.pop(0)


def _advance_time(state: GameState) -> None:
    dt = datetime.fromisoformat(state.world_time)
    dt += timedelta(minutes=RULES.time.turn_min)
    state.world_time = dt.isoformat()


def _next_log_id(state: GameState) -> int:
    nid = state.next_log_id
    state.next_log_id += 1
    return nid


def _push_log_entry(state: GameState, entry, dirty: _Dirty) -> None:
    state.log_entries.append(entry)
    _trim(state.log_entries, RULES.log.display_turns)
    dirty.log.append(entry)


def _push_turn_log(
    state: GameState,
    target: str | None,
    summary: str,
    dirty: _Dirty,
) -> None:
    entry = TurnLogEntry(turn=state.turn_count, target=target, summary=summary)
    state.turn_log.append(entry)
    _trim(state.turn_log, RULES.memory.turn_log_size)
    dirty.history.append(entry)


def _push_dialogue(
    state: GameState,
    player: str,
    narrator: str,
    dirty: _Dirty,
) -> None:
    entry = DialoguePair(turn=state.turn_count, player=player, narrator=narrator)
    state.recent_dialogue.append(entry)
    _trim(state.recent_dialogue, RULES.memory.recent_dialogue_turns)
    dirty.dialogue.append(entry)


def _choose_bonus_target(actor: Character, targets: list[str]) -> str:
    return min(targets, key=lambda t: actor.relations.get(t, 0))


def _front_grade(grade: str) -> str:
    if grade in ("critical_success", "success"):
        return "success"
    if grade == "partial_success":
        return "partial"
    return "fail"


def _label_for_target(state: GameState, target_id: str) -> str:
    if target_id in state.characters:
        return state.characters[target_id].name
    if target_id in state.locations:
        return state.locations[target_id].name
    if target_id in state.items:
        return state.items[target_id].name
    return target_id


def _format_roll_announce(
    state: GameState,
    result: RollAction,
    target: str,
    mod: int,
    required_roll: int,
) -> str:
    target_name = _label_for_target(state, target)
    mod_str = f", {mod:+d}" if mod else ""
    return (
        f"{result.reason} — {target_name}에게 {result.stat} 판정 "
        f"({result.tier}{mod_str}, {required_roll}+ 필요)"
    )


# --- combat helpers --------------------------------------------------------


_GRADE_LABEL = {
    "critical_success": "치명타",
    "success": "명중",
    "partial_success": "겨우 명중",
    "failure": "빗나감",
    "critical_failure": "대실패",
}


def _format_attack_log(
    state: GameState,
    attacker_id: str,
    target_id: str,
    outcome: combat_engine.AttackOutcome,
    apply_result: dict | None,
) -> str:
    attacker = state.characters[attacker_id]
    target = state.characters[target_id]
    hand_label = "주 손" if outcome.hand == "main" else "보조 손"
    grade_label = _GRADE_LABEL[outcome.grade]
    head = f"{attacker.name} → {target.name} ({hand_label}, d20={outcome.nat_d20}): {grade_label}"
    if outcome.damage > 0:
        head += f" — {outcome.damage} 데미지"
    if apply_result is None:
        return head
    if apply_result.get("revived"):
        head += f" ({target.name} 부활 코인 사용, HP 회복)"
    elif apply_result.get("dead"):
        head += f" ({target.name} 쓰러짐)"
    elif apply_result.get("dying"):
        head += f" ({target.name} 의식 잃음)"
    return head


def _format_combat_end_text(outcome: str) -> str:
    if outcome == "victory":
        return "전투 종료 — 적을 모두 제압했다."
    if outcome == "defeat":
        return "전투 종료 — 쓰러졌다."
    return "전투 종료 — 도주."


async def _emit_attack(
    state: GameState,
    attacker_id: str,
    target_id: str,
    outcomes: list[combat_engine.AttackOutcome],
    dirty: _Dirty,
) -> AsyncIterator[dict]:
    """attack outcomes 의 데미지 적용 + SSE/log 발행. 첫 데미지로 target 사망 시 두 번째 손은 묘사 안 함."""
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
        text = _format_attack_log(state, attacker_id, target_id, outcome, apply_result)
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
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


def _format_skill_log(state: GameState, actor_id: str, cast_result: dict, grade: str = "success") -> str:
    """「스킬명」 발동 + 대상별 효과 한 줄."""
    actor_name = state.characters[actor_id].name
    skill_name = cast_result["skill_name"]
    grade_label = _GRADE_LABEL.get(grade, "")
    head_grade = f" ({grade_label})" if grade_label and grade != "success" else ""
    parts: list[str] = [f"{actor_name} — 「{skill_name}」 발동{head_grade}"]
    for eff in cast_result["effects"]:
        tid = eff["target"]
        tname = state.characters[tid].name if tid in state.characters else tid
        kind = eff["kind"]
        if kind == "attack":
            dmg = eff.get("damage", 0)
            tail = f" ({tname} 쓰러짐)" if eff.get("dead") else ""
            parts.append(f"{tname} {dmg} 데미지{tail}")
        elif kind == "heal":
            parts.append(f"{tname} {eff.get('healed', 0)} 회복")
        elif kind in ("buff", "debuff"):
            buff = eff.get("buff", {})
            parts.append(
                f"{tname} 효과 부여 ({buff.get('description', '')}, {buff.get('duration', 0)} 턴)"
            )
    return " — ".join(parts)


async def _emit_skill_cast(
    state: GameState,
    actor_id: str,
    skill_id: str,
    targets: list[str],
    dirty: _Dirty,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    """combat 중 skill cast — d20 grade 굴림 → cast 호출 → log_entry + combat_turn SSE.

    attack/debuff 는 target defense / WIS 저항 vs actor primary_stat 굴림.
    heal/buff/self 는 grade=success (multiplier 1.0).
    """
    actor = state.characters[actor_id]
    try:
        skill_obj = skill_engine.find_skill(actor, skill_id)
    except SkillInvalid as e:
        text = f"{actor.name} — 스킬 발동 실패 ({e})."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        return
    grade, _nat, _req = skill_engine.compute_cast_grade(
        actor, skill_obj, state, targets, rng=rng
    )
    try:
        cast_result = skill_engine.cast(
            actor, skill_id, state, targets, grade=grade, dirty=dirty.entities
        )
    except SkillInvalid as e:
        text = f"{actor.name} — 스킬 발동 실패 ({e})."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        return
    for eff in cast_result["effects"]:
        if eff.get("kind") == "attack":
            combat_engine.record_damage(state, actor_id, int(eff.get("damage", 0)))
    text = _format_skill_log(state, actor_id, cast_result, grade)
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
    _push_log_entry(state, gm_log, dirty)
    yield {"type": "log_entry", "data": gm_log.model_dump()}
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


def _format_use_log(state: GameState, actor_id: str, result: dict) -> str:
    actor = state.characters.get(actor_id)
    actor_name = actor.name if actor else actor_id
    item_id = result.get("item_id")
    item = state.items.get(item_id) if item_id else None
    item_name = item.name if item else (item_id or "아이템")
    kind = result.get("kind")
    head = f"{actor_name} — 「{item_name}」 사용"
    if kind == "heal":
        head += f" ({result.get('amount', 0)} 회복)"
    elif kind == "damage":
        target_id = result.get("target")
        tname = (
            state.characters[target_id].name
            if target_id and target_id in state.characters
            else target_id or ""
        )
        tail = f" ({tname} 쓰러짐)" if result.get("dead") else ""
        head += f" ({tname}에게 {result.get('amount', 0)} 데미지{tail})"
    elif kind == "mp_restore":
        head += f" ({result.get('amount', 0)} MP 회복)"
    elif kind == "buff":
        head += f" ({result.get('description', '')}, {result.get('duration', 0)} 턴)"
    elif kind == "trigger":
        on_use = result.get("on_use")
        if on_use:
            head += f" ({on_use})"
    return head


async def _emit_equip(
    state: GameState,
    actor_id: str,
    item_id: str,
    dirty: _Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    item = state.items.get(item_id)
    item_name = item.name if item else item_id
    try:
        slot = inventory_engine.equip_auto(actor, item_id, state.items)
    except InventoryInvalid as e:
        text = f"{actor.name} — 장착 실패 ({e})."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        return
    dirty.entities.add(("characters", actor_id))
    text = f"{actor.name} — 「{item_name}」 장착 ({slot})"
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
    _push_log_entry(state, gm_log, dirty)
    yield {"type": "log_entry", "data": gm_log.model_dump()}


async def _emit_unequip(
    state: GameState,
    actor_id: str,
    item_id: str,
    dirty: _Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    item = state.items.get(item_id)
    item_name = item.name if item else item_id
    try:
        slot = inventory_engine.unequip_by_item(actor, item_id, state.items)
    except InventoryInvalid as e:
        text = f"{actor.name} — 해제 실패 ({e})."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        return
    if slot is None:
        text = f"{actor.name} — 「{item_name}」 은(는) 장착돼 있지 않다."
    else:
        text = f"{actor.name} — 「{item_name}」 해제 ({slot})"
        dirty.entities.add(("characters", actor_id))
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
    _push_log_entry(state, gm_log, dirty)
    yield {"type": "log_entry", "data": gm_log.model_dump()}


async def _emit_use(
    state: GameState,
    actor_id: str,
    item_id: str,
    target_id: str | None,
    dirty: _Dirty,
) -> AsyncIterator[dict]:
    """use_with_quest_hook 호출 + log/SSE. 검증 실패 시 메시지 한 줄."""
    actor = state.characters[actor_id]
    target = state.characters.get(target_id) if target_id else None
    try:
        result = inventory_engine.use_with_quest_hook(
            actor, item_id, target, state.items, state, dirty=dirty.entities
        )
    except InventoryInvalid as e:
        text = f"{actor.name} — 아이템 사용 실패 ({e})."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        return
    text = _format_use_log(state, actor_id, result)
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
    _push_log_entry(state, gm_log, dirty)
    yield {"type": "log_entry", "data": gm_log.model_dump()}


async def _emit_level_up(
    state: GameState,
    actor_id: str,
    stat_up: str,
    stat_down: str,
    client: LLMClient | None,
    dirty: _Dirty,
) -> AsyncIterator[dict]:
    """level_up 적용 + 후보 추천 (silent fallback)."""
    actor = state.characters[actor_id]
    try:
        level_up_engine(actor, stat_up, stat_down)  # type: ignore[arg-type]
    except LevelUpInvalid as e:
        text = f"{actor.name} — 성장 실패 ({e})."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        return
    dirty.entities.add(("characters", actor_id))
    text = (
        f"{actor.name} — 레벨 {actor.level} 도달 "
        f"({stat_up} ↑ / {stat_down} ↓, HP {actor.max_hp} / MP {actor.max_mp})"
    )
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
    _push_log_entry(state, gm_log, dirty)
    yield {"type": "log_entry", "data": gm_log.model_dump()}
    if client is None:
        state.pending_skill_candidates = []
        return
    try:
        candidates = await recommend_skill_candidates(client, state)
        state.pending_skill_candidates = candidates
    except Exception:
        state.pending_skill_candidates = []
    if state.pending_skill_candidates:
        names = ", ".join(f"「{s.name}」" for s in state.pending_skill_candidates)
        cand_text = f"새 스킬 후보: {names}"
        cand_log = ActLogEntry(id=_next_log_id(state), kind="act", text=cand_text)
        _push_log_entry(state, cand_log, dirty)
        yield {"type": "log_entry", "data": cand_log.model_dump()}


async def _emit_learn_skill(
    state: GameState,
    actor_id: str,
    index: int,
    dirty: _Dirty,
) -> AsyncIterator[dict]:
    actor = state.characters[actor_id]
    candidates = list(state.pending_skill_candidates)
    if not candidates or index < 0 or index >= len(candidates):
        text = f"{actor.name} — 익힐 후보가 없거나 잘못된 선택."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        return
    chosen = candidates[index]
    actor.learned_skills.append(chosen)
    state.pending_skill_candidates = []
    dirty.entities.add(("characters", actor_id))
    text = f"{actor.name} — 「{chosen.name}」 습득."
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
    _push_log_entry(state, gm_log, dirty)
    yield {"type": "log_entry", "data": gm_log.model_dump()}


async def _emit_trade(
    state: GameState,
    actor_id: str,
    npc_id: str,
    item_id: str,
    dirty: _Dirty,
    *,
    direction: Literal["buy", "sell"],
) -> AsyncIterator[dict]:
    player = state.characters[actor_id]
    npc = state.characters.get(npc_id)
    if npc is None:
        text = f"{player.name} — 거래 상대를 찾을 수 없다."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        return
    try:
        if direction == "buy":
            price = inventory_engine.buy(player, npc, item_id, state.items)
        else:
            price = inventory_engine.sell(player, npc, item_id, state.items)
    except InventoryInvalid as e:
        text = f"{player.name} — 거래 실패 ({e})."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        return
    dirty.entities.add(("characters", actor_id))
    dirty.entities.add(("characters", npc.id))
    item = state.items.get(item_id)
    iname = item.name if item else item_id
    verb = "구매" if direction == "buy" else "판매"
    text = f"{player.name} — {npc.name}에게 「{iname}」 {verb} ({price} 금)"
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
    _push_log_entry(state, gm_log, dirty)
    yield {"type": "log_entry", "data": gm_log.model_dump()}


async def _run_combat_npc_phase(
    state: GameState,
    dirty: _Dirty,
    rng: random.Random | None,
) -> AsyncIterator[dict]:
    """현재 actor 가 player 가 될 때까지 NPC 차례 자동 진행. 종료 조건이면 combat_end 발행 후 정리."""
    while True:
        end = combat_engine.check_combat_end(state)
        if end is not None:
            text = _format_combat_end_text(end)
            gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
            _push_log_entry(state, gm_log, dirty)
            yield {"type": "log_entry", "data": gm_log.model_dump()}
            yield {"type": "combat_end", "data": {"outcome": end}}
            combat_engine.end_combat(state)
            return

        actor_id = combat_engine.current_actor_id(state)
        if actor_id is None:
            yield {"type": "combat_end", "data": {"outcome": "victory"}}
            combat_engine.end_combat(state)
            return

        # 첫 라운드 기습 대상은 행동 불가 (docs §1.2). player 차례여도 자동 skip.
        cs = state.combat_state
        if cs is not None and cs.round == 1 and cs.surprise is not None:
            is_player = actor_id == state.player_id
            skip = (cs.surprise == "enemy" and is_player) or (
                cs.surprise == "player" and not is_player
            )
            if skip:
                actor_name = (
                    state.characters[actor_id].name
                    if actor_id in state.characters
                    else actor_id
                )
                text = f"{actor_name}은(는) 기습당해 첫 라운드 행동하지 못한다."
                gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
                _push_log_entry(state, gm_log, dirty)
                yield {"type": "log_entry", "data": gm_log.model_dump()}
                yield {
                    "type": "combat_turn",
                    "data": {"actor": actor_id, "action": "skip", "grade": "success"},
                }
                combat_engine.advance_turn(state)
                continue

        if actor_id == state.player_id:
            return

        actor = state.characters.get(actor_id)
        if actor is None or not actor.alive:
            combat_engine.advance_turn(state)
            continue

        # flee
        if combat_engine.should_attempt_flee(actor, rng=rng):
            ok, _roll = combat_engine.try_flee(actor, rng=rng)
            if ok:
                text = f"{actor.name}이(가) 전투에서 도주했다."
                gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
                _push_log_entry(state, gm_log, dirty)
                yield {"type": "log_entry", "data": gm_log.model_dump()}
                yield {
                    "type": "combat_turn",
                    "data": {"actor": actor_id, "action": "flee", "grade": "success"},
                }
                combat_engine.remove_from_combat(state, actor_id)
                continue
            text = f"{actor.name}이(가) 도주를 시도했으나 실패했다."
            gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
            _push_log_entry(state, gm_log, dirty)
            yield {"type": "log_entry", "data": gm_log.model_dump()}
            yield {
                "type": "combat_turn",
                "data": {"actor": actor_id, "action": "flee", "grade": "failure"},
            }
            combat_engine.advance_turn(state)
            continue

        # attack
        target = combat_engine.pick_npc_target(state, actor_id, rng=rng)
        if target is None:
            combat_engine.advance_turn(state)
            continue
        outcomes = combat_engine.attack(actor, target, state.items, rng=rng)
        async for ev in _emit_attack(state, actor_id, target.id, outcomes, dirty):
            yield ev
        combat_engine.advance_turn(state)


async def _start_combat_and_run_npc_phase(
    state: GameState,
    enemy_ids: list[str],
    dirty: _Dirty,
    rng: random.Random | None,
    surprise: Literal["player", "enemy"] | None = None,
) -> AsyncIterator[dict]:
    cs = combat_engine.start_combat(state, enemy_ids, rng=rng, surprise=surprise)
    text = "전투 개시!"
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
    _push_log_entry(state, gm_log, dirty)
    yield {"type": "log_entry", "data": gm_log.model_dump()}
    yield {
        "type": "combat_start",
        "data": {
            "turn_order": list(cs.turn_order),
            "round": cs.round,
            "surprise": cs.surprise,
            "enemy_ids": list(cs.enemy_ids),
        },
    }
    async for ev in _run_combat_npc_phase(state, dirty, rng):
        yield ev


async def _run_combat_player_turn(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    player_input: str,
    dirty: _Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    """player 차례에서 들어온 input 처리. combat_state 가 살아있을 때만 호출.

    death_save 활성: input 무시하고 자동 d20 굴림.
    그 외: judge → 분기.
    """
    player = state.characters[state.player_id]

    # death-save 자동 진행
    if player.death_saves is not None:
        status, roll = combat_engine.tick_death_save(
            state, state.player_id, rng=rng, dirty=dirty.entities
        )
        ds_grade = "success" if roll >= RULES.death.save_dc else "failure"
        text = f"{player.name} 죽음 저항 (d20={roll}) — "
        if status == "stable":
            text += "안정화. 의식을 회복했다."
        elif status == "dead":
            text += "사망."
        else:
            ds = player.death_saves
            if ds is None:
                text += "성공/실패."  # shouldn't happen
            else:
                text += f"성공 {ds.successes}/3, 실패 {ds.failures}/3."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        yield {
            "type": "combat_turn",
            "data": {"actor": state.player_id, "action": "death_save", "grade": ds_grade},
        }
        if status != "dead":
            combat_engine.advance_turn(state)
        async for ev in _run_combat_npc_phase(state, dirty, rng):
            yield ev
        state.turn_count += 1
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    # 정상 input → judge
    try:
        result = await run_judge(client, state, player_input)
    except JudgeMalformed as e:
        yield {"type": "error", "data": {"message": str(e), "code": "JudgeMalformed"}}
        return

    yield {"type": "judge", "data": result.model_dump()}

    if isinstance(result, CombatAction):
        target_id = result.targets[0]
        target = state.characters.get(target_id)
        if target is None or not target.alive:
            text = "그 대상은 이미 무력화돼 있다."
            gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
            _push_log_entry(state, gm_log, dirty)
            yield {"type": "log_entry", "data": gm_log.model_dump()}
            async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
                yield ev
            return
        if result.skill_id:
            async for ev in _emit_skill_cast(
                state, state.player_id, result.skill_id, list(result.targets), dirty, rng=rng
            ):
                yield ev
        else:
            outcomes = combat_engine.attack(player, target, state.items, rng=rng)
            async for ev in _emit_attack(
                state, state.player_id, target_id, outcomes, dirty
            ):
                yield ev
        combat_engine.advance_turn(state)
        async for ev in _run_combat_npc_phase(state, dirty, rng):
            yield ev
        state.turn_count += 1
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, FleeAction):
        ok, roll_total = combat_engine.try_flee(player, rng=rng)
        if ok:
            text = f"{player.name}이(가) 전투에서 도주했다 (굴림 {roll_total})."
            gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
            _push_log_entry(state, gm_log, dirty)
            yield {"type": "log_entry", "data": gm_log.model_dump()}
            yield {
                "type": "combat_turn",
                "data": {"actor": state.player_id, "action": "flee", "grade": "success"},
            }
            yield {"type": "combat_end", "data": {"outcome": "fled"}}
            combat_engine.end_combat(state)
            state.turn_count += 1
            _advance_time(state)
            async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
                yield ev
            return
        text = f"{player.name}이(가) 도주를 시도했으나 실패했다 (굴림 {roll_total})."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        yield {
            "type": "combat_turn",
            "data": {"actor": state.player_id, "action": "flee", "grade": "failure"},
        }
        combat_engine.advance_turn(state)
        async for ev in _run_combat_npc_phase(state, dirty, rng):
            yield ev
        state.turn_count += 1
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, RollAction):
        # 환경 활용 — 평시 RollAction 분기와 동일 흐름. /roll 이 끝낼 때 NPC phase 자동 진행.
        async for ev in _emit_roll_pending(state, saves_dir, player_input, result, dirty):
            yield ev
        return

    if isinstance(result, PassAction):
        text = f"{player.name}은(는) 자세를 가다듬으며 한 차례를 보낸다."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        yield {
            "type": "combat_turn",
            "data": {"actor": state.player_id, "action": "pass", "grade": "success"},
        }
        combat_engine.advance_turn(state)
        async for ev in _run_combat_npc_phase(state, dirty, rng):
            yield ev
        state.turn_count += 1
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, ClarifyAction):
        # 평시와 동일 — turn 안 늘림, 다음 input 대기.
        act_log = ActLogEntry(id=_next_log_id(state), kind="act", text=result.question)
        _push_log_entry(state, act_log, dirty)
        yield {"type": "log_entry", "data": act_log.model_dump()}
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, RestAction):
        # 전투 중엔 잠 못 잠. judge prompt 가 막아줄 일이지만 방어.
        text = "전투 중에는 잠들 수 없다."
        act_log = ActLogEntry(id=_next_log_id(state), kind="act", text=text)
        _push_log_entry(state, act_log, dirty)
        yield {"type": "log_entry", "data": act_log.model_dump()}
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, UseAction):
        # 전투 중 use — 한 차례 소비. 효과는 같은 함수.
        async for ev in _emit_use(
            state, state.player_id, result.item_id, result.target_id, dirty
        ):
            yield ev
        yield {
            "type": "combat_turn",
            "data": {
                "actor": state.player_id,
                "action": "use",
                "grade": "success",
                "item_id": result.item_id,
            },
        }
        combat_engine.advance_turn(state)
        async for ev in _run_combat_npc_phase(state, dirty, rng):
            yield ev
        state.turn_count += 1
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, (EquipAction, UnequipAction)):
        # 전투 중 장비 변경 — 한 차례 소비.
        if isinstance(result, EquipAction):
            async for ev in _emit_equip(state, state.player_id, result.item_id, dirty):
                yield ev
            action_label = "equip"
        else:
            async for ev in _emit_unequip(state, state.player_id, result.item_id, dirty):
                yield ev
            action_label = "unequip"
        yield {
            "type": "combat_turn",
            "data": {
                "actor": state.player_id,
                "action": action_label,
                "grade": "success",
                "item_id": result.item_id,
            },
        }
        combat_engine.advance_turn(state)
        async for ev in _run_combat_npc_phase(state, dirty, rng):
            yield ev
        state.turn_count += 1
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    # RejectAction 또는 전투 중 부적합 액션 (level_up/learn_skill/buy/sell).
    # 모두 짧게 거절, turn 안 늘림.
    if isinstance(result, RejectAction):
        text = "그 발화는 무시된다."
    else:
        text = "전투 중에는 그 행동을 할 수 없다."
    act_log = ActLogEntry(id=_next_log_id(state), kind="act", text=text)
    _push_log_entry(state, act_log, dirty)
    yield {"type": "log_entry", "data": act_log.model_dump()}
    async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
        yield ev


async def _run_rest(
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    dirty: _Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    client: LLMClient | None = None,
) -> AsyncIterator[dict]:
    """평시 rest 분기. 위험도 굴림으로 풀회복 vs 인카운터 분기.

    sleep_encounters 풀이 비어 있고 client 가 살아 있으면 LLM 으로 적 한 마리 즉석 생성.
    """
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
        text = f"{actor.name}이(가) 잠들기 직전 적의 습격을 받는다."
        gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
        _push_log_entry(state, gm_log, dirty)
        yield {"type": "log_entry", "data": gm_log.model_dump()}
        async for ev in _start_combat_and_run_npc_phase(
            state, enemy_ids, dirty, rng, surprise="enemy"
        ):
            yield ev
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    hours = RULES.time.sleep_hours
    text = (
        f"{actor.name}은(는) 자리를 잡고 잠을 청한다. "
        f"{hours}시간 후 푹 쉬고 일어나, HP/MP 가 모두 회복됐다."
    )
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=text)
    _push_log_entry(state, gm_log, dirty)
    yield {"type": "log_entry", "data": gm_log.model_dump()}
    async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
        yield ev


async def _emit_roll_pending(
    state: GameState,
    saves_dir: str,
    player_input: str,
    result: RollAction,
    dirty: _Dirty,
) -> AsyncIterator[dict]:
    """평시·전투 공용: pending_check 세팅 + flush + pending_check SSE."""
    actor = state.characters[state.player_id]
    target = _choose_bonus_target(actor, result.targets)
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
    announce = _format_roll_announce(state, result, target, mod, required_roll)
    act_log = ActLogEntry(id=_next_log_id(state), kind="act", text=announce)
    _push_log_entry(state, act_log, dirty)
    yield {"type": "log_entry", "data": act_log.model_dump()}
    try:
        await _flush(state, saves_dir, dirty)
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


async def _flush(state: GameState, saves_dir: str, dirty: _Dirty) -> None:
    """Persist a turn's worth of changes. Order: entities + jsonls first,
    meta last (meta = commit point on partial-failure recovery).
    """
    for kind, eid in dirty.entities:
        await save_entity(state, saves_dir, kind, eid)
    await append_log_entries(saves_dir, state.game_id, dirty.log)
    await append_history_entries(saves_dir, state.game_id, dirty.history)
    await append_dialogue_entries(saves_dir, state.game_id, dirty.dialogue)
    await save_meta(state, saves_dir)


def _commit_narrate(
    state: GameState,
    dirty: _Dirty,
    final: NarrativeFinal,
    *,
    body: str,
    target_for_log: str | None,
    dialogue_input: str | None,
) -> None:
    """Shared post-narrate finalization: apply state_changes → turn_log →
    (optional) dialogue → memories → gm_log. dialogue_input=None skips the
    dialogue step (intro)."""
    apply_changes(state, final.output.state_changes, dirty.entities)
    _push_turn_log(state, target_for_log, final.output.turn_summary, dirty)
    if dialogue_input is not None:
        _push_dialogue(state, dialogue_input, body, dirty)
    write_memories(state, final.output, turn=state.turn_count, dirty=dirty.entities)
    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=body)
    _push_log_entry(state, gm_log, dirty)


async def _finalize(
    state: GameState,
    saves_dir: str,
    dirty: _Dirty,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    try:
        await _flush(state, saves_dir, dirty)
    except PersistenceFailed as e:
        yield {
            "type": "error",
            "data": {"message": str(e), "code": "PersistenceFailed"},
        }
        return
    if to_front_fn:
        yield {"type": "state", "data": to_front_fn(state)}
    yield {"type": "done", "data": {}}


# --- /turn -----------------------------------------------------------------


async def run_turn(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    player_input: str,
    *,
    to_front_fn: ToFrontFn | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    if state.pending_check is not None:
        raise PendingCheckActive(
            "a pending_check is already active; call /roll instead"
        )

    dirty = _Dirty()

    # Player input is persisted on every branch.
    player_log = PlayerLogEntry(
        id=_next_log_id(state), kind="player", text=player_input
    )
    _push_log_entry(state, player_log, dirty)
    yield {"type": "log_entry", "data": player_log.model_dump()}

    if state.combat_state is not None:
        async for ev in _run_combat_player_turn(
            client, state, profile_dir, saves_dir, player_input, dirty, rng, to_front_fn
        ):
            yield ev
        return

    try:
        result = await run_judge(client, state, player_input)
    except JudgeMalformed as e:
        yield {"type": "error", "data": {"message": str(e), "code": "JudgeMalformed"}}
        return

    yield {"type": "judge", "data": result.model_dump()}

    if isinstance(result, CombatAction):
        state.turn_count += 1
        async for ev in _start_combat_and_run_npc_phase(
            state, list(result.targets), dirty, rng
        ):
            yield ev
        # skill_id 가 매칭됐으면 player 첫 차례를 cast 로 즉시 소비.
        if result.skill_id and state.combat_state is not None:
            async for ev in _emit_skill_cast(
                state, state.player_id, result.skill_id, list(result.targets), dirty, rng=rng
            ):
                yield ev
            combat_engine.advance_turn(state)
            async for ev in _run_combat_npc_phase(state, dirty, rng):
                yield ev
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, ClarifyAction):
        act_log = ActLogEntry(id=_next_log_id(state), kind="act", text=result.question)
        _push_log_entry(state, act_log, dirty)
        yield {"type": "log_entry", "data": act_log.model_dump()}
        # Don't bump turn_count, time, or turn_log — next /turn restarts the same turn.
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, RollAction):
        async for ev in _emit_roll_pending(state, saves_dir, player_input, result, dirty):
            yield ev
        return  # Wait for the /roll call — don't emit `done`.

    if isinstance(result, RestAction):
        async for ev in _run_rest(
            state, profile_dir, saves_dir, dirty, rng, to_front_fn, client=client
        ):
            yield ev
        return

    if isinstance(result, UseAction):
        state.turn_count += 1
        async for ev in _emit_use(
            state, state.player_id, result.item_id, result.target_id, dirty
        ):
            yield ev
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, EquipAction):
        state.turn_count += 1
        async for ev in _emit_equip(state, state.player_id, result.item_id, dirty):
            yield ev
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, UnequipAction):
        state.turn_count += 1
        async for ev in _emit_unequip(state, state.player_id, result.item_id, dirty):
            yield ev
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, FleeAction):
        # 평시 flee — 의미 없음, narrate 없이 짧은 안내만. turn 안 늘림.
        text = "지금은 도망쳐 달아날 전투가 없다."
        act_log = ActLogEntry(id=_next_log_id(state), kind="act", text=text)
        _push_log_entry(state, act_log, dirty)
        yield {"type": "log_entry", "data": act_log.model_dump()}
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, LevelUpAction):
        state.turn_count += 1
        async for ev in _emit_level_up(
            state, state.player_id, result.stat_up, result.stat_down, client, dirty
        ):
            yield ev
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, LearnSkillAction):
        state.turn_count += 1
        async for ev in _emit_learn_skill(
            state, state.player_id, result.index, dirty
        ):
            yield ev
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, BuyAction):
        state.turn_count += 1
        async for ev in _emit_trade(
            state, state.player_id, result.npc_id, result.item_id, dirty, direction="buy"
        ):
            yield ev
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, SellAction):
        state.turn_count += 1
        async for ev in _emit_trade(
            state, state.player_id, result.npc_id, result.item_id, dirty, direction="sell"
        ):
            yield ev
        _advance_time(state)
        async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    # action == pass / reject — enter the narrator.
    assert isinstance(result, (PassAction, RejectAction))
    state.turn_count += 1
    targets_for_log = getattr(result, "targets", None)
    target_for_log = targets_for_log[0] if targets_for_log else None

    body = ""
    final: NarrativeFinal | None = None
    async for item in run_narrate(
        client,
        state,
        profile_dir,
        player_input,
        judge_result=result.model_dump(),
        grade=None,
    ):
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
            body += item.text
        else:
            final = item
    assert final is not None

    _commit_narrate(
        state,
        dirty,
        final,
        body=body,
        target_for_log=target_for_log,
        dialogue_input=player_input,
    )
    _advance_time(state)

    async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
        yield ev


# --- /intro ----------------------------------------------------------------


async def run_intro(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    *,
    to_front_fn: ToFrontFn | None = None,
) -> AsyncIterator[dict]:
    """First GM intro, called once right after game start.

    Skips judge and only calls narrate. player_input is empty.
    turn_count and world_time do not advance (scene intro counts as turn 0).
    """
    dirty = _Dirty()
    judge_result = {"action": "intro"}
    body = ""
    final: NarrativeFinal | None = None
    async for item in run_narrate(
        client,
        state,
        profile_dir,
        "",
        judge_result=judge_result,
        grade=None,
    ):
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
            body += item.text
        else:
            final = item
    assert final is not None

    _commit_narrate(
        state,
        dirty,
        final,
        body=body,
        target_for_log=None,
        dialogue_input=None,
    )

    async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
        yield ev


# --- /roll -----------------------------------------------------------------


async def run_roll(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    *,
    to_front_fn: ToFrontFn | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    if state.pending_check is None:
        raise PendingCheckExpected("no pending_check; call /turn first")

    dirty = _Dirty()
    pending = state.pending_check
    state.turn_count += 1

    rng_obj = rng or random
    dice = rng_obj.randint(1, 20)
    total = dice + pending.mod
    grade = compute_grade(dice, total, pending.required_roll)

    target_name = _label_for_target(state, pending.target)
    check_label = f"{pending.stat} · {pending.reason} (→ {target_name})"
    roll_log = RollLogEntry(
        id=_next_log_id(state),
        kind="roll",
        check=check_label,
        dc=pending.dc,
        roll=dice,
        mod=pending.mod,
        result=_front_grade(grade),
    )
    _push_log_entry(state, roll_log, dirty)
    yield {"type": "log_entry", "data": roll_log.model_dump()}

    judge_result = {
        "action": "roll",
        "tier": pending.tier,
        "stat": pending.stat,
        "targets": pending.targets,
    }

    body = ""
    final: NarrativeFinal | None = None
    async for item in run_narrate(
        client,
        state,
        profile_dir,
        pending.player_input,
        judge_result=judge_result,
        grade=grade,
        target_id=pending.target,
    ):
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
            body += item.text
        else:
            final = item
    assert final is not None

    _commit_narrate(
        state,
        dirty,
        final,
        body=body,
        target_for_log=pending.target,
        dialogue_input=pending.player_input,
    )

    state.pending_check = None
    _advance_time(state)

    if state.combat_state is not None:
        # 환경 활용 굴림은 player 의 한 차례를 소비. 다음 NPC 차례부터 자동.
        combat_engine.advance_turn(state)
        async for ev in _run_combat_npc_phase(state, dirty, rng):
            yield ev

    async for ev in _finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
