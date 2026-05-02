"""String builders for log lines and a few small label helpers.

Pure functions — no state mutation, no SSE, no I/O. Anything that returns a
string for a log entry lives here.
"""

from ..domain.state import GameState
from ..mapping.josa import eul_reul, eun_neun, gwa_wa, i_ga
from .error_phrases import humanize_engine_error


GAME_OVER_TEXT = "당신의 이야기가 여기서 끝납니다."
NO_COMBAT_TARGETS_TEXT = "공격할 수 있는 대상이 없습니다."
SUMMON_FAILED_TEXT = "허공을 가르지만 적은 보이지 않습니다."
FLEE_OUTSIDE_COMBAT_TEXT = "지금은 도망칠 전투가 없습니다."
REST_BLOCKED_IN_COMBAT_TEXT = "전투 중에는 잠들 수 없습니다."
INPUT_REJECTED_TEXT = "그 말은 받아들여지지 않습니다."
ACTION_FORBIDDEN_IN_COMBAT_TEXT = "전투 중에는 그 행동을 할 수 없습니다."


def format_combat_start_turn_log(first_enemy_name: str) -> str:
    return f"{first_enemy_name}{gwa_wa(first_enemy_name)} 전투 개시"


def format_action_fail(actor_name: str, attempt: str, err: Exception) -> str:
    """Generic failure line: '<actor>이 <attempt> <korean error>.'"""
    return f"{actor_name}{i_ga(actor_name)} {attempt} {humanize_engine_error(err)}."


def format_equip_log(actor_name: str, item_name: str) -> str:
    return f"{actor_name}{i_ga(actor_name)} 「{item_name}」{eul_reul(item_name)} 장비했습니다."


def format_equip_fail(actor_name: str, item_name: str, err: Exception) -> str:
    return format_action_fail(
        actor_name, f"「{item_name}」{eul_reul(item_name)} 장비하려 했지만", err
    )


def format_unequip_log(actor_name: str, item_name: str) -> str:
    return f"{actor_name}{i_ga(actor_name)} 「{item_name}」{eul_reul(item_name)} 해제했습니다."


def format_unequip_fail(actor_name: str, item_name: str, err: Exception) -> str:
    return format_action_fail(
        actor_name, f"「{item_name}」{eul_reul(item_name)} 해제하려 했지만", err
    )


def format_unequip_not_equipped(actor_name: str, item_name: str) -> str:
    return f"{actor_name}{eun_neun(actor_name)} 「{item_name}」{eul_reul(item_name)} 장비하고 있지 않습니다."


def format_learn_skill_no_candidate(actor_name: str) -> str:
    return f"{actor_name}{i_ga(actor_name)} 익힐 만한 기술을 찾지 못했습니다."


def format_learn_skill_log(actor_name: str, skill_name: str) -> str:
    return f"{actor_name}{i_ga(actor_name)} 「{skill_name}」{eul_reul(skill_name)} 익혔습니다."


def format_use_fail(actor_name: str, item_name: str, err: Exception) -> str:
    return format_action_fail(
        actor_name, f"「{item_name}」{eul_reul(item_name)} 쓰려 했지만", err
    )


def format_use_target_turn_log(item_name: str, target_name: str) -> str:
    return f"{item_name}{eul_reul(item_name)} {target_name}에게 사용"


def format_trade_no_partner(actor_name: str) -> str:
    return f"{actor_name}{i_ga(actor_name)} 거래할 상대를 찾지 못했습니다."


def format_trade_log(
    actor_name: str,
    npc_name: str,
    item_name: str,
    price: int,
    *,
    direction: str,
) -> str:
    if direction == "buy":
        return f"{actor_name}{i_ga(actor_name)} {npc_name}에게서 「{item_name}」{eul_reul(item_name)} {price} 금화에 샀습니다."
    return f"{actor_name}{i_ga(actor_name)} {npc_name}에게 「{item_name}」{eul_reul(item_name)} {price} 금화에 팔았습니다."


def format_trade_turn_log(npc_name: str, item_name: str, *, direction: str) -> str:
    label = "구매" if direction == "buy" else "판매"
    return f"{npc_name}에게 「{item_name}」 {label}"


def format_give_no_partner(actor_name: str) -> str:
    return f"{actor_name}{i_ga(actor_name)} 양도 상대를 찾지 못했습니다."


def format_give_log(
    src_name: str, dst_name: str, item_name: str, *, dst_is_player: bool
) -> str:
    if dst_is_player:
        return f"{src_name}에게서 {dst_name}{i_ga(dst_name)} 「{item_name}」{eul_reul(item_name)} 받았습니다."
    return f"{src_name}{i_ga(src_name)} {dst_name}에게 「{item_name}」{eul_reul(item_name)} 건넸습니다."


def format_give_turn_log(src_name: str, dst_name: str, item_name: str) -> str:
    return f"「{item_name}」 양도 ({src_name} → {dst_name})"


def format_move_no_path(actor_name: str) -> str:
    return f"{actor_name}{i_ga(actor_name)} 그곳으로 가는 길을 찾지 못했습니다."


def format_move_blocked(actor_name: str, loc_name: str, reason: str) -> str:
    suffix = f" ({reason})" if reason else ""
    return f"{actor_name}{i_ga(actor_name)} {loc_name}{eul_reul(loc_name)} 향했지만 닿지 못했습니다.{suffix}"


def format_move_log(actor_name: str, loc_name: str) -> str:
    return f"{actor_name}{i_ga(actor_name)} {loc_name}에 들어섭니다."


def format_level_up_log(
    actor_name: str,
    level: int,
    stat_up: str,
    stat_down: str,
    max_hp: int,
    max_mp: int,
) -> str:
    return (
        f"{actor_name}의 레벨이 올랐습니다 "
        f"(레벨 {level}, {stat_up} ↑ / {stat_down} ↓, HP {max_hp} / MP {max_mp})."
    )


def format_skill_candidates_log(skill_names: list[str]) -> str:
    names = ", ".join(f"「{n}」" for n in skill_names)
    return f"새 기술 후보: {names}"


def format_attack_turn_log(target_name: str) -> str:
    return f"{target_name}{eul_reul(target_name)} 공격"


def front_grade(grade: str) -> str:
    if grade in ("critical_success", "success"):
        return "success"
    if grade == "partial_success":
        return "partial"
    return "fail"


def format_combat_end_text(outcome: str) -> str:
    if outcome == "victory":
        return "적을 모두 제압했습니다."
    if outcome == "defeat":
        return GAME_OVER_TEXT
    if outcome == "downed":
        return "의식을 되찾았습니다."
    return "도망쳤습니다."


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
        head += f" ({result.get('description', '')}, {result.get('duration', 0)} 턴)"
    elif kind == "trigger":
        on_use = result.get("on_use")
        if on_use:
            head += f" ({on_use})"
    return head
