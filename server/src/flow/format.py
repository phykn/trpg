"""String builders for log lines and a few small label helpers.

Pure functions — no state mutation, no SSE, no I/O. Anything that returns a
string for a log entry lives here.
"""

from ..domain.state import GameState


def front_grade(grade: str) -> str:
    if grade in ("critical_success", "success"):
        return "success"
    if grade == "partial_success":
        return "partial"
    return "fail"


def format_combat_end_text(outcome: str) -> str:
    if outcome == "victory":
        return "전투 종료 — 적을 모두 제압했습니다."
    if outcome == "defeat":
        return "전투 종료 — 사망."
    if outcome == "downed":
        return "전투 종료 — 의식을 잃었다 깨어났습니다."
    return "전투 종료 — 도주."


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
