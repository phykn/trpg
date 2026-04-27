"""String builders for log lines and a few small label helpers.

Pure functions — no state mutation, no SSE, no I/O. Anything that returns a
string for a log entry lives here.
"""
from ..agents.dc_judge.schema import RollAction
from ..domain.state import GameState
from ..engines.combat import AttackOutcome


# --- Labels and grade helpers ----------------------------------------------


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


# --- Engine-error → Korean GM phrase ---------------------------------------


# Substring → Korean phrase. Order in this literal is for readability;
# `_ERROR_PHRASES_SORTED` below scans longest-needle-first so a more specific
# match (e.g. "npc has not enough gold") always wins over a shorter prefix
# of itself ("not enough gold"). Add new entries here without worrying about
# position — the sort handles precedence.
_ERROR_PHRASES_RAW: list[tuple[str, str]] = [
    ("hp already full", "이미 체력이 가득해 회복약을 쓸 필요가 없다"),
    ("mp already full", "이미 마력이 가득해 마력 음료를 쓸 필요가 없다"),
    ("affinity too low to trade", "친밀도가 부족해 거래가 안 된다"),
    ("can't sell equipped item", "장착 중인 물건은 팔 수 없다 (먼저 해제하라)"),
    ("npc has not enough gold", "상대의 소지금이 부족하다"),
    ("not enough gold", "금화가 부족하다"),
    ("npc has no such item", "그쪽이 그 물건을 가지고 있지 않다"),
    ("player has no such item", "그 물건을 가지고 있지 않다"),
    ("item not in inventory", "그 물건을 가지고 있지 않다"),
    ("unknown item", "그런 물건은 없다"),
    ("is not consumable", "소모할 수 있는 물건이 아니다"),
    ("damage item requires target", "대상을 지정해야 한다"),
    ("unsupported consumable effect", "이 물건은 그 방식으로 쓸 수 없다"),
    ("consumable items can't be equipped", "소모품은 장착할 수 없다"),
    ("weapon must go in leftHand or rightHand", "무기는 손 슬롯에만 장착할 수 있다"),
    ("armor must go in head", "방어구는 머리·상의·하의·신발 슬롯에만 장착할 수 있다"),
    ("required stats not met", "능력치 요구 조건이 모자라다"),
    ("has no equippable effect", "이 물건은 장착할 수 없다"),
    ("weight cap exceeded", "들 수 있는 무게 한도를 넘어섰다"),
    ("unknown slot", "잘못된 슬롯이다"),
    ("not enough xp", "성장에 필요한 경험이 모자라다"),
    ("already at max level", "이미 최고 레벨이다"),
    ("already at cap 20", "그 능력치는 이미 한계다"),
    ("pair-trade blocked", "페어 능력치가 0이라 더 떨어뜨릴 수 없다"),
    ("invalid stat_up", "성장시킬 능력치가 잘못됐다"),
    ("actor has no such skill", "그런 스킬은 익히지 않았다"),
    ("not in skills pool", "그런 스킬은 시나리오에 없다"),
]

_ERROR_PHRASES_SORTED: list[tuple[str, str]] = sorted(
    _ERROR_PHRASES_RAW, key=lambda kv: len(kv[0]), reverse=True
)


def humanize_engine_error(err: Exception) -> str:
    """Translate engine-raised English error strings (InventoryInvalid /
    LevelUpInvalid / SkillInvalid / etc.) into a one-line Korean phrase
    safe to surface as GM text. Falls back to a generic phrase if no
    pattern matches — never expose the raw English to the player.
    """
    low = str(err).lower()
    for needle, korean in _ERROR_PHRASES_SORTED:
        if needle.lower() in low:
            return korean
    return "지금은 그 행동이 통하지 않는다"


# --- GM log line builders --------------------------------------------------


def format_roll_announce(
    state: GameState,
    result: RollAction,
    target: str,
    dc: int,
) -> str:
    target_name = label_for_target(state, target)
    return (
        f"{result.reason}\n"
        f"{target_name}에게 {result.stat} 판정 (난이도 {dc})"
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
    if outcome.damage > 0:
        head = (
            f"{attacker.name}이(가) {hand_label}으로 {target.name}에게 "
            f"{outcome.damage} 피해를 입혔다 ({grade_label}, 굴림 {outcome.nat_d20})."
        )
    elif outcome.grade == "critical_failure":
        head = (
            f"{attacker.name}이(가) {hand_label}으로 공격하다 "
            f"{grade_label}했다 (굴림 {outcome.nat_d20})."
        )
    else:
        head = (
            f"{attacker.name}이(가) {hand_label}으로 {target.name}을(를) "
            f"노렸으나 빗나갔다 (굴림 {outcome.nat_d20})."
        )
    if apply_result is None:
        return head
    if apply_result.get("revived"):
        return f"{head} {target.name}이(가) 부활 코인을 사용해 HP를 회복했다."
    if apply_result.get("dead"):
        return f"{head} {target.name}이(가) 쓰러졌다."
    if apply_result.get("dying"):
        return f"{head} {target.name}이(가) 의식을 잃었다."
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
