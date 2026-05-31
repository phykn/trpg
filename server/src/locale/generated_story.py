"""Generated story helper terms for projection and contract checks."""

ACTIONABLE_PATCH_MARKERS = (
    "가려면",
    "가야",
    "먼저",
    "해야",
    "셔야",
    "나아가",
    "벗어나",
    "찾",
    "가리",
    "이야기",
    "관리인",
    "담당자",
    "길목",
    "길드",
    "건물",
)
QUEST_BEAT_FALLBACK = {
    "title": "다음 단서 확인",
    "summary": "방금 확인한 목표를 진행하기 위한 다음 단서를 찾습니다.",
}
LOCATION_DESCRIPTION_SUFFIX = "더 살펴볼 수 있는 장소입니다."
LEGACY_LOCATION_DESCRIPTION_SUFFIX = "can be investigated further."
GENERATED_OPEN_MOVE_TERMS = ("이동", "갑니다", "가요", "나아", "향해")
GENERATED_OPEN_MOVE_TARGET_TERMS = ("가리키", "길목", "방향", "북쪽")
GENERATED_SPEAK_WORLD_LEAD_MARKERS = (
    "가려면",
    "관리인",
    "담당자",
    *GENERATED_OPEN_MOVE_TARGET_TERMS,
)


def is_generic_quest_beat(title: object, summary: object) -> bool:
    return title == QUEST_BEAT_FALLBACK["title"] and summary == QUEST_BEAT_FALLBACK["summary"]


def is_generated_current_location_memory(
    *,
    kind: object,
    title: object,
    summary: object,
) -> bool:
    if kind != "memory":
        return False
    return _matches_current_location_text(title) or _matches_current_location_text(summary)


def location_description(location_name: str) -> str:
    return f"{location_name}은 {LOCATION_DESCRIPTION_SUFFIX}"


def normalize_location_description(description: str) -> str:
    if description.endswith(f" {LEGACY_LOCATION_DESCRIPTION_SUFFIX}"):
        location_name = description[: -len(LEGACY_LOCATION_DESCRIPTION_SUFFIX)].strip()
        if location_name:
            return location_description(location_name)
    return description


def _matches_current_location_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return text.startswith("현재 위치는 ") and text.rstrip(".").endswith("입니다")


def looks_actionable_for_story_patch(text: str) -> bool:
    return any(marker in text for marker in ACTIONABLE_PATCH_MARKERS)
