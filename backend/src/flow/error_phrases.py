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
    """Translate an engine-raised English error string into a one-line
    Korean phrase safe to surface as GM text. Falls back to a generic
    phrase if no pattern matches — never expose the raw English to the
    player.
    """
    low = str(err).lower()
    for needle, korean in _ERROR_PHRASES_SORTED:
        if needle.lower() in low:
            return korean
    return "지금은 그 행동이 통하지 않는다"
