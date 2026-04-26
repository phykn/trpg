"""String builders for log lines and a few small label helpers.

Pure functions — no state mutation, no SSE, no I/O. Anything that returns a
string for a log entry lives here.
"""
from ..agents.dc_judge.schema import RollAction
from ..domain.state import GameState
from ..engines.combat import AttackOutcome


GRADE_LABEL: dict[str, str] = {
    "critical_success": "치명타",
    "success": "명중",
    "partial_success": "겨우 명중",
    "failure": "빗나감",
    "critical_failure": "대실패",
}


def front_grade(grade: str) -> str:
    if grade in ("critical_success", "success"):
        return "success"
    if grade == "partial_success":
        return "partial"
    return "fail"


def label_for_target(state: GameState, target_id: str) -> str:
    if target_id in state.characters:
        return state.characters[target_id].name
    if target_id in state.locations:
        return state.locations[target_id].name
    if target_id in state.items:
        return state.items[target_id].name
    return target_id


def format_roll_announce(
    state: GameState,
    result: RollAction,
    target: str,
    mod: int,
    required_roll: int,
) -> str:
    target_name = label_for_target(state, target)
    mod_str = f", {mod:+d}" if mod else ""
    return (
        f"{result.reason} — {target_name}에게 {result.stat} 판정 "
        f"({result.tier}{mod_str}, {required_roll}+ 필요)"
    )


def format_attack_log(
    state: GameState,
    attacker_id: str,
    target_id: str,
    outcome: AttackOutcome,
    apply_result: dict | None,
) -> str:
    attacker = state.characters[attacker_id]
    target = state.characters[target_id]
    hand_label = "주 손" if outcome.hand == "main" else "보조 손"
    grade_label = GRADE_LABEL[outcome.grade]
    head = (
        f"{attacker.name} → {target.name} "
        f"({hand_label}, d20={outcome.nat_d20}): {grade_label}"
    )
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


def format_combat_end_text(outcome: str) -> str:
    if outcome == "victory":
        return "전투 종료 — 적을 모두 제압했다."
    if outcome == "defeat":
        return "전투 종료 — 쓰러졌다."
    return "전투 종료 — 도주."


def format_skill_log(
    state: GameState,
    actor_id: str,
    cast_result: dict,
    grade: str = "success",
) -> str:
    actor_name = state.characters[actor_id].name
    skill_name = cast_result["skill_name"]
    grade_label = GRADE_LABEL.get(grade, "")
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
                f"{tname} 효과 부여 "
                f"({buff.get('description', '')}, {buff.get('duration', 0)} 턴)"
            )
    return " — ".join(parts)


def format_use_log(state: GameState, actor_id: str, result: dict) -> str:
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
        head += (
            f" ({result.get('description', '')}, "
            f"{result.get('duration', 0)} 턴)"
        )
    elif kind == "trigger":
        on_use = result.get("on_use")
        if on_use:
            head += f" ({on_use})"
    return head
