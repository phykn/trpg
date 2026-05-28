"""Korean fallback terms for generated story patch recovery."""

import re


CHARACTER_ROLES = ("관리인", "담당자", "상인", "목격자")
LOCATION_NOUNS = ("길목", "길드", "건물", "사무소", "시장", "창고")
QUEST_BEAT_MARKERS = (
    "가려면",
    "가야",
    "해야",
    "셔야",
    "나아가",
    "벗어나",
    "찾",
    "방법",
    "단서",
)
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
    "말을",
    "관리인",
    "담당자",
    "길목",
    "길드",
    "건물",
    "선착장",
)
ROMANIZED_TERMS = {
    "관리인": "manager",
    "담당자": "contact",
    "상인": "merchant",
    "목격자": "witness",
    "길드": "guild",
    "건물": "building",
    "사무소": "office",
    "시장": "market",
    "창고": "warehouse",
    "단서": "clue",
    "길목": "road",
}
QUEST_BEAT_FALLBACK = {
    "title": "다음 단서 확인",
    "summary": "방금 확인한 목표를 진행하기 위한 다음 단서를 찾습니다.",
}
LOCATION_DESCRIPTION_SUFFIX = "더 살펴볼 수 있는 장소입니다."
LEGACY_LOCATION_DESCRIPTION_SUFFIX = "can be investigated further."
GENERATED_OPEN_MOVE_TERMS = ("이동", "갑니다", "가요", "나아", "향해")
GENERATED_OPEN_MOVE_TARGET_TERMS = ("가리키", "길목", "방향", "북쪽")


def candidate_character_name(text: str) -> str | None:
    for role in CHARACTER_ROLES:
        match = re.search(rf"([가-힣]{{1,12}}\s+{role})", text)
        if match:
            return match.group(1)
        if role in text:
            return role
    return None


def candidate_character_role(name: str) -> str:
    if "상인" in name:
        return "merchant"
    if "목격자" in name:
        return "witness"
    if "관리인" in name or "담당자" in name:
        return "quest_giver"
    return "bystander"


def candidate_location_name(text: str) -> str | None:
    for noun in LOCATION_NOUNS:
        match = re.search(rf"([가-힣]{{1,12}}\s+{noun})", text)
        if match:
            return match.group(1)
    return None


def candidate_quest_beat(text: str) -> dict[str, str] | None:
    if not any(marker in text for marker in QUEST_BEAT_MARKERS):
        return None
    return dict(QUEST_BEAT_FALLBACK)


def location_description(location_name: str) -> str:
    return f"{location_name}은 {LOCATION_DESCRIPTION_SUFFIX}"


def normalize_location_description(description: str) -> str:
    if description.endswith(f" {LEGACY_LOCATION_DESCRIPTION_SUFFIX}"):
        location_name = description[: -len(LEGACY_LOCATION_DESCRIPTION_SUFFIX)].strip()
        if location_name:
            return location_description(location_name)
    return description


def node_id_suffix(name: str) -> str:
    parts = [value for word, value in ROMANIZED_TERMS.items() if word in name]
    return "_".join(parts) if parts else "lead"


def looks_actionable_for_story_patch(text: str) -> bool:
    return any(marker in text for marker in ACTIONABLE_PATCH_MARKERS)
