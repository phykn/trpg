"""String builders for log lines and a few small label helpers.

Pure functions — no state mutation, no SSE, no I/O. Anything that returns a
string for a log entry lives here.
"""

from typing import TYPE_CHECKING

from ..domain.state import GameState
from ..locale import render
from ..locale.particles import i_ga
from ..mapping.labels import stat_label
from .error_phrases import humanize_engine_error

if TYPE_CHECKING:
    from .combat_auto import AutoCombatResult


GAME_OVER_TEXT = render("log.game_over", "ko")
NO_COMBAT_TARGETS_TEXT = render("log.no_combat_targets", "ko")
SUMMON_FAILED_TEXT = render("log.summon_failed", "ko")
FLEE_OUTSIDE_COMBAT_TEXT = render("log.flee_outside_combat", "ko")
REST_BLOCKED_IN_COMBAT_TEXT = render("log.rest_blocked_in_combat", "ko")
INPUT_REJECTED_TEXT = render("log.input_rejected", "ko")
ACTION_FORBIDDEN_IN_COMBAT_TEXT = render("log.action_forbidden_in_combat", "ko")


def format_combat_start_turn_log(first_enemy_name: str) -> str:
    return render("log.combat_start_turn", "ko", enemy=first_enemy_name)


def format_action_fail(actor_name: str, attempt: str, err: Exception) -> str:
    """Generic failure line: '<actor>이 <attempt> <korean error>.'"""
    return render(
        "log.action_fail", "ko",
        actor=actor_name, attempt=attempt, err=humanize_engine_error(err),
    )


def format_equip_log(actor_name: str, item_name: str) -> str:
    return render("log.equip", "ko", actor=actor_name, item=item_name)


def format_equip_fail(actor_name: str, item_name: str, err: Exception) -> str:
    attempt = render("log.equip_attempt", "ko", item=item_name)
    return format_action_fail(actor_name, attempt, err)


def format_unequip_log(actor_name: str, item_name: str) -> str:
    return render("log.unequip", "ko", actor=actor_name, item=item_name)


def format_unequip_fail(actor_name: str, item_name: str, err: Exception) -> str:
    attempt = render("log.unequip_attempt", "ko", item=item_name)
    return format_action_fail(actor_name, attempt, err)


def format_unequip_not_equipped(actor_name: str, item_name: str) -> str:
    return render("log.unequip_not_equipped", "ko", actor=actor_name, item=item_name)


def format_rest_log(actor_name: str, cost_gold: int = 0) -> str:
    base = render("log.rest_base", "ko", actor=actor_name)
    if cost_gold > 0:
        return render("log.rest_with_cost", "ko", base=base, cost=cost_gold)
    return base


def format_learn_skill_log(actor_name: str, skill_name: str) -> str:
    return render("log.learn_skill", "ko", actor=actor_name, skill=skill_name)


def format_use_fail(actor_name: str, item_name: str, err: Exception) -> str:
    attempt = render("log.use_attempt", "ko", item=item_name)
    return format_action_fail(actor_name, attempt, err)


def format_use_target_turn_log(item_name: str, target_name: str) -> str:
    return render("log.use_target_turn", "ko", item=item_name, target=target_name)


def format_equip_turn_log(item_name: str) -> str:
    return render("log.equip_turn", "ko", item=item_name)


def format_unequip_turn_log(item_name: str) -> str:
    return render("log.unequip_turn", "ko", item=item_name)


def format_use_self_turn_log(item_name: str) -> str:
    return render("log.use_self_turn", "ko", item=item_name)


def format_trade_no_partner(actor_name: str) -> str:
    return render("log.trade_no_partner", "ko", actor=actor_name)


def format_trade_log(
    actor_name: str,
    npc_name: str,
    item_name: str,
    price: int,
    *,
    direction: str,
) -> str:
    key = "log.trade_buy" if direction == "buy" else "log.trade_sell"
    return render(key, "ko", actor=actor_name, npc=npc_name, item=item_name, price=price)


def format_trade_turn_log(npc_name: str, item_name: str, *, direction: str) -> str:
    key = "log.trade_turn_buy" if direction == "buy" else "log.trade_turn_sell"
    return render(key, "ko", npc=npc_name, item=item_name)


def format_give_no_partner(actor_name: str) -> str:
    return render("log.give_no_partner", "ko", actor=actor_name)


def format_give_log(
    src_name: str, dst_name: str, item_name: str, *, dst_is_player: bool
) -> str:
    key = "log.give_to_player" if dst_is_player else "log.give_from_player"
    return render(key, "ko", src=src_name, dst=dst_name, item=item_name)


def format_give_turn_log(src_name: str, dst_name: str, item_name: str) -> str:
    return render("log.give_turn", "ko", src=src_name, dst=dst_name, item=item_name)


def format_move_no_path(actor_name: str) -> str:
    return render("log.move_no_path", "ko", actor=actor_name)


def format_move_blocked(actor_name: str, loc_name: str, reason: str) -> str:
    if reason:
        return render(
            "log.move_blocked_with_reason", "ko",
            actor=actor_name, loc=loc_name, reason=reason,
        )
    return render("log.move_blocked", "ko", actor=actor_name, loc=loc_name)


def format_location_enter_log(location_name: str) -> str:
    return render("log.location_enter", "ko", location=location_name)


def format_location_enter_turn_log(location_name: str) -> str:
    return render("log.location_enter_turn", "ko", location=location_name)


def format_quest_start_log(quest_title: str) -> str:
    return render("log.quest_start", "ko", title=quest_title)


# Same body as format_quest_start_log; kept paired (cf. format_location_enter_*) so future SSE/turn_log tone divergence is a one-line edit.
def format_quest_start_turn_log(quest_title: str) -> str:
    return render("log.quest_start", "ko", title=quest_title)


def format_quest_success_log(title: str, exp: int, gold: int, items: list[str]) -> str:
    head = render("log.quest_success_head", "ko", title=title)
    rewards: list[str] = []
    if exp > 0:
        rewards.append(render("log.reward_exp", "ko", exp=exp))
    if gold > 0:
        rewards.append(render("log.reward_gold", "ko", gold=gold))
    if items:
        rewards.append(" / ".join(items))
    if rewards:
        return f"{head} — " + " · ".join(rewards)
    return head


def format_quest_fail_log(title: str, reason: str) -> str:
    return render("log.quest_fail", "ko", title=title, reason=reason)


def format_affinity_card_log(npc_name: str, delta: int) -> str:
    sign = "+" if delta >= 0 else ""
    return render("log.affinity_card", "ko", npc=npc_name, sign=sign, delta=delta)


def format_affinity_card_turn_log(npc_name: str, delta: int) -> str:
    sign = "+" if delta >= 0 else ""
    return render("log.affinity_card", "ko", npc=npc_name, sign=sign, delta=delta)


def format_recruit_success_log(name: str) -> str:
    return render("log.recruit_success", "ko", name=name)


def format_recruit_failure_log(name: str) -> str:
    return render("log.recruit_failure", "ko", name=name)


def format_recruit_critical_failure_log(name: str) -> str:
    return render("log.recruit_critical_failure", "ko", name=name)


def format_dismiss_log(name: str) -> str:
    return render("log.dismiss", "ko", name=name)


def format_dismiss_turn_log(name: str) -> str:
    return render("log.dismiss_turn", "ko", name=name)


def format_recruit_success_turn_log(name: str) -> str:
    return render("log.recruit_success_turn", "ko", name=name)


def format_recruit_failure_turn_log(name: str) -> str:
    return render("log.recruit_failure_turn", "ko", name=name)


def format_level_up_log(
    actor_name: str,
    level: int,
    stat_up: str,
    stat_down: str,
    max_hp: int,
    max_mp: int,
) -> str:
    return render(
        "log.level_up", "ko",
        actor=actor_name, level=level,
        up=stat_label(stat_up), down=stat_label(stat_down),
        hp=max_hp, mp=max_mp,
    )


def format_death_log(name: str) -> str:
    return render("log.death", "ko", name=name)


def format_attack_turn_log(target_name: str) -> str:
    return render("log.attack_turn", "ko", target=target_name)


def front_grade(grade: str) -> str:
    if grade in ("critical_success", "success"):
        return "success"
    if grade == "partial_success":
        return "partial"
    return "fail"


def format_combat_end_text(
    outcome: str, enemies_remaining: list[dict] | None = None
) -> str:
    if outcome == "defeat":
        return "패배했습니다."
    if outcome == "fled":
        return "전투에서 이탈했습니다."
    if outcome == "downed":
        return "의식을 되찾았습니다."
    enemies_remaining = enemies_remaining or []
    survivors = [e for e in enemies_remaining if e.get("hp", 0) > 0]
    if survivors:
        names = [e.get("name", "") for e in survivors if e.get("name")]
        if names:
            joined = ", ".join(names)
            return f"{joined}{i_ga(joined)} 도망쳤습니다."
        return "적이 도망쳤습니다."
    return "적을 처치했습니다."


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


# ----- Combat outcome summary (one act-line after the cinematic) -----

_COMBAT_PLAYER_FALLBACK_NAME = "주인공"


def format_combat_enemy_killed(name: str, damage: int) -> str:
    return f"{name} {damage} 피해 — 쓰러짐"


def format_combat_enemy_hit(name: str, damage: int, hp_after: int, max_hp: int) -> str:
    return f"{name} {damage} 피해 (HP {hp_after}/{max_hp})"


def format_combat_player_hit(name: str, damage: int, hp_after: int, max_hp: int) -> str:
    return f"{name} {damage} 피해 (HP {hp_after}/{max_hp})"


def format_combat_player_downed(name: str, damage: int, hp_before: int) -> str:
    """Player hit reduces HP to 0 (revival imminent on next event)."""
    return f"{name} {damage} 피해 (HP {hp_before}→0, 사망 직전)"


def format_combat_revived(coins_after: int, coins_max: int, hp_after: int) -> str:
    """Player revival: dropped to 0, came back at hp_after."""
    if coins_after == 0:
        return f"최후의 호흡 (소생 0/{coins_max}, HP 0→{hp_after})"
    return f"가까스로 일어남 (소생 {coins_after}/{coins_max}, HP 0→{hp_after})"


def format_combat_outcome_summary(result: "AutoCombatResult") -> str | None:
    """Numeric breakdown rendered as ordered act-lines after the cinematic.

    Revival splits into two lines to surface the intermediate HP 0 state:
      line 1 — hit that downed the player (HP X→0, 사망 직전)
      line 2 — coin revival (HP 0→auto_revive_hp)
    """
    lines: list[str] = []
    for h in result.enemy_hits:
        if h.killed:
            lines.append(format_combat_enemy_killed(h.name, h.damage_total))
        elif h.damage_total > 0:
            lines.append(
                format_combat_enemy_hit(h.name, h.damage_total, h.hp_after, h.max_hp)
            )
    if result.player_damage_total > 0 or result.player_revived:
        player_name = result.player_name or _COMBAT_PLAYER_FALLBACK_NAME
        if result.player_revived:
            # Show chronological two-step: downed at 0, then revived.
            lines.append(
                format_combat_player_downed(
                    player_name, result.player_damage_total, result.player_hp_before
                )
            )
            lines.append(
                format_combat_revived(
                    result.player_revive_coins_after,
                    result.player_revive_coins_max,
                    result.player_hp_after,
                )
            )
        else:
            lines.append(
                format_combat_player_hit(
                    player_name,
                    result.player_damage_total,
                    result.player_hp_after,
                    result.player_max_hp,
                )
            )
    if not lines:
        return None
    return "전투 결과\n" + "\n".join(lines)


def format_combat_event_summary(result: "AutoCombatResult") -> str:
    """One-line Korean summary of a combat result for injection into narrate prompt."""
    player_name = result.player_name or _COMBAT_PLAYER_FALLBACK_NAME
    parts: list[str] = []
    for h in result.enemy_hits:
        if h.killed:
            parts.append(
                f"{player_name}{i_ga(player_name)} {h.name}에게 {h.damage_total} 피해 — {h.name} 쓰러짐"
            )
        elif h.damage_total > 0:
            parts.append(
                f"{player_name}{i_ga(player_name)} {h.name}에게 {h.damage_total} 피해 (적 HP {h.hp_after}/{h.max_hp})"
            )
    if result.player_damage_total > 0:
        parts.append(
            f"{player_name} {result.player_damage_total} 피해 입음 (HP {result.player_hp_after}/{result.player_max_hp})"
        )
    if result.player_revived:
        parts.append("가까스로 소생")
    outcome_map = {
        "victory": "전투 승리",
        "defeat": "전투 패배",
        "fled": "전투 이탈",
        "downed": "전투 중 쓰러짐",
    }
    outcome_label = outcome_map.get(result.outcome, result.outcome)
    summary = ", ".join(parts) if parts else outcome_label
    if parts:
        summary += f" — {outcome_label}"
    return summary
