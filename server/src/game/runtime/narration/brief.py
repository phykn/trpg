from typing import Any

from ..env import env_nonnegative_int


def build_narration_brief(payload: dict[str, Any]) -> str:
    event = _dict(payload.get("engine_event"))
    if _dict(event.get("story_transition")):
        return _story_transition_brief(payload, event)
    if event.get("kind") == "combat":
        return build_combat_narration_brief(payload)
    if event.get("kind") == "roll":
        return _roll_brief(payload, event)
    return _action_brief(payload, event)


def build_combat_narration_brief(payload: dict[str, Any]) -> str:
    event = _dict(payload.get("engine_event"))
    combat = _dict(payload.get("combat_view"))
    lines = _recent_context_lines(payload)
    lines.extend(
        [
            "장면 유형: 전투",
            f"행동: {_combat_action(combat, event)}",
            f"결과: {_combat_result(combat)}",
        ]
    )
    outcome = combat.get("outcome")
    if isinstance(outcome, str) and outcome:
        lines.append(f"전투 상태: {outcome}")
    target = _combat_target(combat) or _target_name(payload)
    if target:
        lines.append(f"대상: {target}")
    facts = _combat_facts(event, combat, payload)
    if facts:
        lines.append("확정:")
        lines.extend(f"- {fact}" for fact in facts)
    lines.extend(
        [
            "금지: 피해량, HP 숫자, 새 상태 변화, 새 보상, 전투 종료 창작",
            "목표: 확정된 전투 결과를 몸의 반응, 거리, 자세, 압박으로 장면화합니다.",
        ]
    )
    return "\n".join(lines)


def _story_transition_brief(
    payload: dict[str, Any],
    event: dict[str, Any],
) -> str:
    transition = _dict(event.get("story_transition"))
    completed = ", ".join(
        item["name"] for item in _dicts(transition.get("completed_quests"))
    )
    chapter = _dict(transition.get("opened_chapter")).get("name")
    quest = _dict(transition.get("next_quest")).get("name")
    next_text = " / ".join(
        value for value in (chapter, quest) if isinstance(value, str) and value
    )
    lines = _recent_context_lines(payload)
    lines.extend(
        [
            "장면 유형: 사건 전환",
            f"장소: {_place_name(payload)}",
        ]
    )
    if completed:
        lines.append(f"완료: {completed}")
    if next_text:
        lines.append(f"다음: {next_text}")
    handoff = transition.get("handoff")
    if isinstance(handoff, str) and handoff:
        lines.append(f"전환 단서: {handoff}")
    lines.extend(
        [
            "금지: 정답 지시, 선택 평가, 다음 사건 결론 공개",
            "목표: 끝난 사건은 정리하고 다음 사건의 첫 단서만 자연스럽게 남깁니다.",
        ]
    )
    return "\n".join(lines)


def _combat_action(combat: dict[str, Any], event: dict[str, Any]) -> str:
    value = combat.get("player_action")
    if isinstance(value, str) and value:
        return value
    action = _dict(event.get("action"))
    verb = action.get("verb")
    labels = {
        "attack": "공격",
        "defend": "방어",
        "move": "이동",
        "speak": "대화",
        "pass": "대기",
    }
    return labels.get(verb, "전투 행동") if isinstance(verb, str) else "전투 행동"


def _combat_result(combat: dict[str, Any]) -> str:
    value = combat.get("exchange_result_label")
    if isinstance(value, str) and value:
        return value
    result = combat.get("exchange_result")
    if result == "success":
        return "성공"
    if result == "failure":
        return "실패"
    return "중립"


def _combat_target(combat: dict[str, Any]) -> str:
    for event in _dicts(combat.get("events")):
        target = _dict(event.get("target"))
        name = target.get("name")
        if isinstance(name, str) and name:
            return name
    return ""


def _combat_facts(
    event: dict[str, Any],
    combat: dict[str, Any],
    payload: dict[str, Any],
) -> list[str]:
    facts = _strings(event.get("resolved_results"))
    for item in _dicts(combat.get("events"))[:3]:
        line = _combat_event_fact(item)
        if line:
            facts.append(line)
    effect = _dict(combat.get("effect"))
    effect_name = effect.get("name")
    if isinstance(effect_name, str) and effect_name:
        facts.append(f"효과: {effect_name}")
    for status in _dicts(combat.get("statuses"))[:3]:
        status_name = status.get("name")
        if isinstance(status_name, str) and status_name:
            facts.append(f"상태: {status_name}")
    cards = [
        text
        for item in _dicts(payload.get("result_cards"))
        if isinstance(text := item.get("text"), str) and text
    ]
    return _dedupe([*facts, *cards])


def _combat_event_fact(event: dict[str, Any]) -> str:
    actor = _dict(event.get("actor")).get("name")
    target = _dict(event.get("target")).get("name")
    motion = event.get("motion")
    result = event.get("result_label")
    condition = event.get("target_condition")
    parts = [
        value
        for value in (actor, motion, target, result, condition)
        if isinstance(value, str) and value
    ]
    return " / ".join(parts)


def _roll_brief(payload: dict[str, Any], event: dict[str, Any]) -> str:
    outcome = event.get("outcome")
    result = "성공" if outcome == "success" else "실패"
    lines = _recent_context_lines(payload)
    lines.extend(
        [
            "장면 유형: 판정 후",
            f"장소: {_place_name(payload)}",
            f"대상: {_target_name(payload)}",
            f"플레이어 입력: {_player_input(payload)}",
            f"결과: {result}",
        ]
    )
    resolved = _strings(event.get("resolved_results"))
    if resolved:
        lines.append(f"확정: {' / '.join(resolved)}")
    if outcome == "success":
        lines.append("금지: 실패처럼 흐리는 반응, 확정되지 않은 보상, 새 퀘스트 창작")
        lines.append("목표: 성공의 귀결을 분명히 쓰고, 근거에 있는 반응이나 다음 여지를 남깁니다.")
    else:
        lines.append("금지: 성공처럼 읽히는 단서 획득, 설득 성공, 관계 변화 확정")
        lines.append("목표: 실패가 분명히 보이되 대화나 재시도 여지는 남깁니다.")
    return "\n".join(lines)


def _action_brief(payload: dict[str, Any], event: dict[str, Any]) -> str:
    kind = event.get("kind")
    lines = _recent_context_lines(payload)
    lines.extend(
        [
            f"장면 유형: {kind if isinstance(kind, str) and kind else '일반 행동'}",
            f"장소: {_place_name(payload)}",
        ]
    )
    target = _target_name(payload)
    if target:
        lines.append(f"대상: {target}")
    player_input = _player_input(payload)
    if player_input != "없음":
        lines.append(f"플레이어 입력: {player_input}")
    resolved = _strings(event.get("resolved_results"))
    if resolved:
        lines.append(f"확정: {' / '.join(resolved)}")
    lines.extend(
        [
            "금지: payload에 없는 새 결과, 새 보상, 새 관계 변화",
            "목표: 확정된 행동 결과를 짧고 구체적인 장면으로 바꿉니다.",
        ]
    )
    return "\n".join(lines)


def _recent_context_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    context = _dict(payload.get("reference_context"))
    screen_log = _dicts(context.get("screen_log"))[
        -env_nonnegative_int("GRAPH_NARRATION_SCREEN_LOG_ENTRIES", 8) :
    ]
    recent_entries = env_nonnegative_int("GRAPH_NARRATION_BRIEF_RECENT_ENTRIES", 2)
    narration = _dicts(context.get("recent_narration"))[-recent_entries:]
    dialogue = _dicts(context.get("recent_dialogue"))[-recent_entries:]

    visible_log = [_screen_log_line(item) for item in screen_log]
    visible_log = [line for line in visible_log if line]
    if visible_log:
        lines.append("화면 로그:")
        lines.extend(f"- {line}" for line in visible_log)
        return lines

    recent_narration = [
        _clip(text)
        for item in narration
        if isinstance(text := item.get("text"), str) and text
    ]
    if recent_narration:
        lines.append("최근 로그:")
        lines.extend(f"- {text}" for text in recent_narration)

    recent_dialogue = []
    for item in dialogue:
        player = item.get("player")
        narrator = item.get("narrator")
        player_text = player if isinstance(player, str) and player else ""
        narrator_text = narrator if isinstance(narrator, str) and narrator else ""
        if player_text or narrator_text:
            recent_dialogue.append((player_text, narrator_text))
    if recent_dialogue:
        lines.append("최근 대화:")
        for player, narrator in recent_dialogue:
            if player:
                lines.append(f"- 플레이어: {_clip(player)}")
            if narrator:
                lines.append(f"- GM: {_clip(narrator)}")
    return lines


def _screen_log_line(entry: dict[str, Any]) -> str:
    kind = entry.get("kind")
    if kind == "gm":
        text = entry.get("text")
        return f"GM: {_clip(text)}" if isinstance(text, str) and text else ""
    if kind == "player":
        text = entry.get("text")
        return f"플레이어: {_clip(text)}" if isinstance(text, str) and text else ""
    if kind == "act":
        text = entry.get("text")
        return f"행동: {_clip(text)}" if isinstance(text, str) and text else ""
    if kind == "roll":
        return _screen_roll_line(entry)
    return ""


def _screen_roll_line(entry: dict[str, Any]) -> str:
    result = "성공" if entry.get("result") == "success" else "실패"
    check = entry.get("check")
    roll = entry.get("roll")
    if not isinstance(check, str) or not isinstance(roll, int):
        return ""
    parts = ["판정:", result, check, f"d20 {roll}"]
    total_bonus = sum(
        item["value"]
        for item in _dicts(entry.get("bonus_breakdown"))[1:]
        if isinstance(item.get("value"), int)
    )
    if total_bonus != 0:
        parts.append(f"({_signed(total_bonus)})")
    margin = entry.get("margin")
    if isinstance(margin, int) and roll not in {1, 20}:
        if margin > 0:
            parts.append(f"+{margin} 초과")
        elif margin < 0:
            parts.append(f"{-margin} 부족")
    return " ".join(parts)


def _player_input(payload: dict[str, Any]) -> str:
    request = _dict(payload.get("user_request"))
    value = request.get("player_input")
    return value if isinstance(value, str) and value else "없음"


def _place_name(payload: dict[str, Any]) -> str:
    scene = _dict(payload.get("scene_state"))
    place = _dict(scene.get("current_place"))
    if not place:
        anchor = _dict(scene.get("scene_anchor"))
        place = _dict(anchor.get("location"))
    value = place.get("name")
    return value if isinstance(value, str) and value else "알 수 없음"


def _target_name(payload: dict[str, Any]) -> str:
    scene = _dict(payload.get("scene_state"))
    target = _dict(scene.get("target_view"))
    value = target.get("name")
    return value if isinstance(value, str) and value else ""


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _dedupe(values: list[str]) -> list[str]:
    out = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _clip(value: str, limit: int | None = None) -> str:
    limit = env_nonnegative_int("GRAPH_NARRATION_BRIEF_LINE_CHARS", 120) if limit is None else limit
    text = " ".join(value.split())
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _signed(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)
