"""Engine-error → Korean GM phrase translation table.

Single concern: take an English exception message raised by an engine
(InventoryInvalid / LevelUpInvalid / SkillInvalid / ...) and return a
one-line Korean phrase safe to surface as GM text. Pulled out of
flow/format.py so the format module stays focused on log-line builders.
"""

# Substring → Korean phrase. Order in this literal is for readability;
# `_ERROR_PHRASES_SORTED` below scans longest-needle-first so a more specific
# match (e.g. "npc has not enough gold") always wins over a shorter prefix
# of itself ("not enough gold"). Add new entries here without worrying about
# position — the sort handles precedence.
_ERROR_PHRASES_RAW: list[tuple[str, str]] = [
    ("hp already full", "이미 체력이 가득해 회복약을 쓸 필요가 없습니다"),
    ("mp already full", "이미 마력이 가득해 마력 음료를 쓸 필요가 없습니다"),
    ("affinity too low to trade", "친밀도가 부족해 거래가 되지 않습니다"),
    (
        "can't sell equipped item",
        "장착 중인 물건은 팔 수 없습니다 (먼저 해제하셔야 합니다)",
    ),
    ("npc has not enough gold", "상대의 금화가 부족합니다"),
    ("not enough gold", "금화가 부족합니다"),
    ("npc has no such item", "그쪽은 그 물건을 가지고 있지 않습니다"),
    ("player has no such item", "그 물건을 가지고 있지 않습니다"),
    ("item not in inventory", "그 물건을 가지고 있지 않습니다"),
    ("unknown item", "그런 물건은 없습니다"),
    ("is not consumable", "소모할 수 있는 물건이 아닙니다"),
    ("damage item requires target", "대상을 지정해야 합니다"),
    ("unsupported consumable effect", "이 물건은 그 방식으로 쓸 수 없습니다"),
    ("consumable items can't be equipped", "소모품은 장착할 수 없습니다"),
    ("weapon must go in the weapon slot", "무기는 무기 슬롯에만 장착할 수 있습니다"),
    (
        "defense item must go in armor or accessory slot",
        "방어 효과 물건은 갑옷이나 악세사리 슬롯에 장착할 수 있습니다",
    ),
    (
        "decorative item must go in the accessory slot",
        "장식품은 악세사리 슬롯에만 장착할 수 있습니다",
    ),
    ("required stats not met", "능력치 요구 조건을 충족하지 못합니다"),
    ("has no equippable effect", "이 물건은 장착할 수 없습니다"),
    ("weight cap exceeded", "들 수 있는 무게 한도를 넘어섰습니다"),
    ("not enough xp", "성장에 필요한 경험이 부족합니다"),
    ("already at max level", "이미 최고 레벨입니다"),
    ("already at cap 20", "그 능력치는 이미 한계입니다"),
    ("pair-trade blocked", "페어 능력치가 0이라 더 떨어뜨릴 수 없습니다"),
    ("invalid stat_up", "성장시킬 능력치가 잘못되었습니다"),
    ("actor has no such skill", "그런 기술은 익히지 않았습니다"),
    ("not in skills pool", "그런 기술은 시나리오에 없습니다"),
]

_ERROR_PHRASES_SORTED: list[tuple[str, str]] = sorted(
    _ERROR_PHRASES_RAW, key=lambda kv: len(kv[0]), reverse=True
)


def humanize_engine_error(err: Exception) -> str:
    """Translate an engine-raised English error string into a one-line
    Korean phrase safe to surface as GM text. Falls back to a generic
    phrase if no pattern matches — never expose the raw English to the
    player.
    """
    low = str(err).lower()
    for needle, korean in _ERROR_PHRASES_SORTED:
        if needle.lower() in low:
            return korean
    return "지금은 그 행동이 통하지 않습니다"


# --- runtime/transport-level error messages (SSE `error` event) -------------


# Exception class name → Korean message shown to the player. Keyed by
# `type(exc).__name__` so the table matches what `api/sse.py` already puts in
# the SSE `code` field. Raw `str(exc)` (English stack noise, upstream API
# JSON, traceback fragments) is never shipped to the client — it goes to
# server logs only. Add a row here when a new exception class becomes
# reachable from a turn/intro/roll stream; the generic fallback is intentionally
# vague so unknown failures don't leak internals.
_RUNTIME_PHRASES: dict[str, str] = {
    "JudgeMalformed": "행동을 해석하지 못했습니다. 다시 시도해 주세요.",
    "PersistenceFailed": "저장 중 문제가 생겼습니다. 잠시 후 다시 시도해 주세요.",
    "LLMUnavailable": "이야기꾼이 잠시 길을 잃었습니다. 다시 시도해 주세요.",
    "NarrateUnavailable": "이야기꾼이 잠시 길을 잃었습니다. 다시 시도해 주세요.",
    "NarrateMalformed": "이야기 한 줄을 마저 잇지 못했습니다. 다시 시도해 주세요.",
    "InvariantViolation": "세계의 규칙이 어긋났습니다. 다시 시도해 주세요.",
}

_GENERIC_RUNTIME_PHRASE = "지금은 응답할 수 없습니다. 잠시 후 다시 시도해 주세요."


def humanize_runtime_error(exc: Exception) -> str:
    """Map an unhandled/SSE-stream exception class to a player-safe Korean
    one-liner. Use at every `{"type":"error", "data":...}` emit site so the
    client never sees raw English / upstream API payloads. Caller still logs
    the original exception for debugging."""
    return _RUNTIME_PHRASES.get(type(exc).__name__, _GENERIC_RUNTIME_PHRASE)
