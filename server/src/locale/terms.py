"""Locale-aware lexical shortcuts used before LLM classification."""

from collections.abc import Iterable

from .ko.terms import (
    ABANDON_TERMS,
    ACCEPT_TERMS,
    ACTION_ATTACK_TERMS,
    ACTION_FLEE_TERMS,
    ACTION_PICKUP_TERMS,
    DECEPTIVE_TERMS,
    DIALOGUE_TERMS,
    HOSTILE_TERMS,
    KO_DOWNED_MARKERS,
    KO_META_BREAKING_TERMS,
    KO_NONLETHAL_MARKERS,
    KO_REAL_WORLD_TERMS,
    PART_TERMS,
    RECRUIT_TERMS,
    WEATHER_TERM,
)

NONLETHAL_MARKERS_BY_LOCALE = {
    "en": frozenset(
        {
            "training",
            "sparring",
            "tutorial",
            "practice",
            "nonlethal",
            "non-lethal",
        }
    ),
    "ko": KO_NONLETHAL_MARKERS,
}

DOWNED_MARKERS_BY_LOCALE = {
    "en": frozenset({"downed"}),
    "ko": KO_DOWNED_MARKERS,
}

META_BREAKING_TERMS = (*KO_META_BREAKING_TERMS, "ignore previous", "system prompt")
REAL_WORLD_TERMS = (*KO_REAL_WORLD_TERMS, "real world")

__all__ = [
    "ABANDON_TERMS",
    "ACCEPT_TERMS",
    "ACTION_ATTACK_TERMS",
    "ACTION_FLEE_TERMS",
    "ACTION_PICKUP_TERMS",
    "DECEPTIVE_TERMS",
    "DIALOGUE_TERMS",
    "DOWNED_MARKERS_BY_LOCALE",
    "HOSTILE_TERMS",
    "META_BREAKING_TERMS",
    "NONLETHAL_MARKERS_BY_LOCALE",
    "PART_TERMS",
    "REAL_WORLD_TERMS",
    "RECRUIT_TERMS",
    "WEATHER_TERM",
    "downed_markers",
    "nonlethal_markers",
]


def nonlethal_markers(locale: str) -> frozenset[str]:
    markers: set[str] = set(_terms_for_locale("en", NONLETHAL_MARKERS_BY_LOCALE))
    markers.update(_terms_for_locale(locale, NONLETHAL_MARKERS_BY_LOCALE))
    return frozenset(markers)


def downed_markers(locale: str) -> frozenset[str]:
    markers: set[str] = set(_terms_for_locale("en", DOWNED_MARKERS_BY_LOCALE))
    markers.update(_terms_for_locale(locale, DOWNED_MARKERS_BY_LOCALE))
    return frozenset(markers)


def _terms_for_locale(
    locale: str,
    terms_by_locale: dict[str, Iterable[str]],
) -> Iterable[str]:
    language = locale.split("-", 1)[0].lower()
    return terms_by_locale.get(language, ())
