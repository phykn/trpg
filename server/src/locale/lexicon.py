"""Locale-owned lexical shortcuts used before LLM classification."""

from collections.abc import Iterable

DIALOGUE_TERMS = (
    "말",
    "묻",
    "물어",
    "대화",
    "인사",
    "질문",
    "대답",
)
HOSTILE_TERMS = (
    "협박",
    "위협",
    "화내",
    "적대",
    "따져",
    "도발",
)
DECEPTIVE_TERMS = (
    "거짓",
    "속이",
    "속여",
    "기만",
)
RECRUIT_TERMS = (
    "동료",
    "합류",
    "함께",
    "같이",
)
PART_TERMS = (
    "헤어",
    "각자",
    "떠나",
    "그만",
)
ACCEPT_TERMS = ("수락", "받아들")
ABANDON_TERMS = ("포기", "거절", "취소")

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
    "ko": frozenset({"훈련", "대련", "연습", "허수아비"}),
}

META_BREAKING_TERMS = (
    "시스템 프롬프트",
    "프롬프트 원문",
    "이전 지시를 무시",
    "ignore previous",
    "system prompt",
)
REAL_WORLD_TERMS = ("현실", "실제", "real world")
WEATHER_TERM = "날씨"


def nonlethal_markers(locale: str) -> frozenset[str]:
    markers: set[str] = set(_terms_for_locale("en", NONLETHAL_MARKERS_BY_LOCALE))
    markers.update(_terms_for_locale(locale, NONLETHAL_MARKERS_BY_LOCALE))
    return frozenset(markers)


def _terms_for_locale(
    locale: str,
    terms_by_locale: dict[str, Iterable[str]],
) -> Iterable[str]:
    language = locale.split("-", 1)[0].lower()
    return terms_by_locale.get(language, ())
