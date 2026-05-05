from ...locale import render

# Substring(English) → catalog key. _ERROR_KEYS_SORTED scans longest-needle-first
# so order here is irrelevant.
_ERROR_KEYS_RAW: list[tuple[str, str]] = [
    ("hp already full", "log.error.hp_full"),
    ("mp already full", "log.error.mp_full"),
    ("affinity too low to trade", "log.error.affinity_too_low"),
    ("can't sell equipped item", "log.error.cant_sell_equipped"),
    ("npc has not enough gold", "log.error.npc_not_enough_gold"),
    ("rest insufficient gold", "log.error.rest_insufficient_gold"),
    ("not enough gold", "log.error.not_enough_gold"),
    ("npc has no such item", "log.error.npc_no_such_item"),
    ("player has no such item", "log.error.player_no_such_item"),
    ("item not in inventory", "log.error.item_not_in_inventory"),
    ("unknown item", "log.error.unknown_item"),
    ("is not consumable", "log.error.not_consumable"),
    ("damage item requires target", "log.error.damage_needs_target"),
    ("unsupported consumable effect", "log.error.unsupported_consumable"),
    ("consumable items can't be equipped", "log.error.consumable_not_equippable"),
    ("weapon must go in the weapon slot", "log.error.weapon_slot_only"),
    (
        "defense item must go in armor or accessory slot",
        "log.error.defense_slot",
    ),
    (
        "decorative item must go in the accessory slot",
        "log.error.decorative_slot",
    ),
    ("required stats not met", "log.error.stats_unmet"),
    ("has no equippable effect", "log.error.no_equippable"),
    ("weight cap exceeded", "log.error.weight_cap"),
    ("not enough xp", "log.error.not_enough_xp"),
    ("already at max level", "log.error.max_level"),
    ("already at cap 20", "log.error.cap_20"),
    ("pair-trade blocked", "log.error.pair_blocked"),
    ("invalid stat_up", "log.error.invalid_stat_up"),
    ("actor has no such skill", "log.error.no_such_skill"),
    ("not in skills pool", "log.error.skill_not_in_pool"),
]

_ERROR_KEYS_SORTED: list[tuple[str, str]] = sorted(
    _ERROR_KEYS_RAW, key=lambda kv: len(kv[0]), reverse=True
)


def humanize_engine_error(err: Exception) -> str:
    """Translate an engine-raised English error string into a one-line
    Korean phrase via the locale catalog. Falls back to a generic phrase if
    no pattern matches — never expose the raw English to the player.
    """
    low = str(err).lower()
    for needle, key in _ERROR_KEYS_SORTED:
        if needle.lower() in low:
            return render(key, "ko")
    return render("log.error.generic_block", "ko")


# Receipt actions skip narrate by default. These error substrings escalate a
# failure back to a narrated reaction — they're moments worth GM prose because
# the player misjudged a social/threshold gate, not a typo-shaped slip.
_DRAMATIC_FAIL_KEYS: frozenset[str] = frozenset(
    {
        "affinity too low to trade",
        "required stats not met",
        "npc has not enough gold",
    }
)


def is_dramatic_fail(err: Exception | str) -> bool:
    """True if the engine error matches a key worth a narrated reaction."""
    text = err if isinstance(err, str) else str(err)
    low = text.lower()
    return any(needle in low for needle in _DRAMATIC_FAIL_KEYS)
