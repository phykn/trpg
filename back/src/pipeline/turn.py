import random
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

from ..domain.entities import Character
from ..domain.memory import (
    ActLogEntry,
    DialoguePair,
    GMLogEntry,
    PendingCheck,
    PlayerLogEntry,
    RollLogEntry,
    TurnLogEntry,
)
from ..errors import (
    CombatNotSupported,
    JudgeMalformed,
    PendingCheckActive,
    PendingCheckExpected,
    PersistenceFailed,
)
from ..llm_client.agents.dc_judge.schema import (
    ClarifyAction,
    CombatAction,
    PassAction,
    RejectAction,
    RollAction,
)
from ..llm_client.agents.narrate import NarrativeDelta, NarrativeFinal
from ..llm_client.client import LLMClient
from ..rules import RULES
from ..state.models import GameState
from ..state.store import save_game
from .apply import apply_changes
from .dc import compute_grade, pick_dc, sigmoid_required_roll, social_bonus, tier_to_int
from .judge import run_judge
from .memory_writer import write_memories
from .narrate import run_narrate

ToFrontFn = Callable[[GameState], dict]


# --- helpers ---------------------------------------------------------------


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


def _push_log_entry(state: GameState, entry) -> None:
    state.log_entries.append(entry)
    _trim(state.log_entries, RULES.log.display_turns)


def _push_turn_log(state: GameState, target: str | None, summary: str) -> None:
    state.turn_log.append(
        TurnLogEntry(turn=state.turn_count, target=target, summary=summary)
    )
    _trim(state.turn_log, RULES.memory.turn_log_size)


def _push_dialogue(state: GameState, player: str, narrator: str) -> None:
    state.recent_dialogue.append(
        DialoguePair(turn=state.turn_count, player=player, narrator=narrator)
    )
    _trim(state.recent_dialogue, RULES.memory.recent_dialogue_turns)


def _choose_bonus_target(actor: Character, targets: list[str]) -> str:
    return min(targets, key=lambda t: actor.relations.get(t, 0))


def _front_grade(grade: str) -> str:
    return "success" if grade in ("critical_success", "success", "partial_success") else "fail"


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
    mod_str = f", +{mod}" if mod > 0 else f", {mod}" if mod < 0 else ""
    return (
        f"{result.reason} — {target_name}에게 {result.stat} 판정 "
        f"({result.tier}{mod_str}, {required_roll}+ 필요)"
    )


# --- /turn -----------------------------------------------------------------


async def run_turn(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    data_dir: str,
    player_input: str,
    *,
    to_front_fn: ToFrontFn | None = None,
) -> AsyncIterator[dict]:
    if state.pending_check is not None:
        raise PendingCheckActive("a pending_check is already active; call /roll instead")

    # player log entry — 입력 자체는 모든 분기에서 영속
    player_log = PlayerLogEntry(id=_next_log_id(state), kind="player", text=player_input)
    _push_log_entry(state, player_log)
    yield {"type": "log_entry", "data": player_log.model_dump()}

    # judge
    try:
        result = await run_judge(client, state, player_input)
    except JudgeMalformed as e:
        yield {"type": "error", "data": {"message": str(e), "code": "JudgeMalformed"}}
        return

    yield {"type": "judge", "data": result.model_dump()}

    # 분기
    if isinstance(result, CombatAction):
        # P1 미구현
        raise CombatNotSupported("combat is not implemented in P1")

    if isinstance(result, ClarifyAction):
        act_log = ActLogEntry(id=_next_log_id(state), kind="act", text=result.question)
        _push_log_entry(state, act_log)
        yield {"type": "log_entry", "data": act_log.model_dump()}
        # turn_count·시간·turn_log 모두 변경 안 함 — 다음 /turn 에서 재시작
        try:
            await save_game(state, data_dir)
        except PersistenceFailed as e:
            yield {"type": "error", "data": {"message": str(e), "code": "PersistenceFailed"}}
            return
        if to_front_fn:
            yield {"type": "state", "data": to_front_fn(state)}
        yield {"type": "done", "data": {}}
        return

    if isinstance(result, RollAction):
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
        _push_log_entry(state, act_log)
        yield {"type": "log_entry", "data": act_log.model_dump()}
        try:
            await save_game(state, data_dir)
        except PersistenceFailed as e:
            yield {"type": "error", "data": {"message": str(e), "code": "PersistenceFailed"}}
            return
        yield {
            "type": "pending_check",
            "data": {
                "dc": dc,
                "stat": result.stat,
                "mod": mod,
                "required_roll": required_roll,
                "tier": {"value": tier_to_int(result.tier), "max": 7, "label": result.tier},
                "target": target,
            },
        }
        return  # /roll 호출 대기 — done 보내지 않음

    # action == pass / reject — narrator 진입
    assert isinstance(result, (PassAction, RejectAction))
    state.turn_count += 1
    targets_for_log = getattr(result, "targets", None)
    target_for_log = targets_for_log[0] if targets_for_log else None

    body = ""
    final: NarrativeFinal | None = None
    async for item in run_narrate(
        client, state, profile_dir, player_input,
        judge_result=result.model_dump(),
        grade=None,
    ):
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
            body += item.text
        else:
            final = item
    assert final is not None

    apply_changes(state, final.output.state_changes)
    _push_turn_log(state, target_for_log, final.output.turn_summary)
    _push_dialogue(state, player_input, body)
    write_memories(state, final.output, turn=state.turn_count)

    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=body)
    _push_log_entry(state, gm_log)

    _advance_time(state)

    try:
        await save_game(state, data_dir)
    except PersistenceFailed as e:
        yield {"type": "error", "data": {"message": str(e), "code": "PersistenceFailed"}}
        return
    if to_front_fn:
        yield {"type": "state", "data": to_front_fn(state)}
    yield {"type": "done", "data": {}}


# --- /intro ----------------------------------------------------------------


async def run_intro(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    data_dir: str,
    *,
    to_front_fn: ToFrontFn | None = None,
) -> AsyncIterator[dict]:
    """게임 시작 직후 한 번만 호출되는 첫 GM intro.

    judge 를 거치지 않고 narrate 만 호출. player_input 은 비어 있음.
    turn_count·world_time 은 진행하지 않음 (장면 도입은 한 호흡이 0턴).
    """
    judge_result = {"action": "intro"}
    body = ""
    final: NarrativeFinal | None = None
    async for item in run_narrate(
        client, state, profile_dir, "",
        judge_result=judge_result,
        grade=None,
    ):
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
            body += item.text
        else:
            final = item
    assert final is not None

    apply_changes(state, final.output.state_changes)
    _push_turn_log(state, None, final.output.turn_summary)
    write_memories(state, final.output, turn=state.turn_count)

    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=body)
    _push_log_entry(state, gm_log)

    try:
        await save_game(state, data_dir)
    except PersistenceFailed as e:
        yield {"type": "error", "data": {"message": str(e), "code": "PersistenceFailed"}}
        return
    if to_front_fn:
        yield {"type": "state", "data": to_front_fn(state)}
    yield {"type": "done", "data": {}}


# --- /roll -----------------------------------------------------------------


async def run_roll(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    data_dir: str,
    *,
    to_front_fn: ToFrontFn | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    if state.pending_check is None:
        raise PendingCheckExpected("no pending_check; call /turn first")

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
    _push_log_entry(state, roll_log)
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
        client, state, profile_dir, pending.player_input,
        judge_result=judge_result, grade=grade, target_id=pending.target,
    ):
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
            body += item.text
        else:
            final = item
    assert final is not None

    apply_changes(state, final.output.state_changes)
    _push_turn_log(state, pending.target, final.output.turn_summary)
    _push_dialogue(state, pending.player_input, body)
    write_memories(state, final.output, turn=state.turn_count)

    gm_log = GMLogEntry(id=_next_log_id(state), kind="gm", text=body)
    _push_log_entry(state, gm_log)

    state.pending_check = None
    _advance_time(state)

    try:
        await save_game(state, data_dir)
    except PersistenceFailed as e:
        yield {"type": "error", "data": {"message": str(e), "code": "PersistenceFailed"}}
        return
    if to_front_fn:
        yield {"type": "state", "data": to_front_fn(state)}
    yield {"type": "done", "data": {}}
