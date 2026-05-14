"""Korean lexical shortcuts used before LLM classification."""

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
ACTION_ATTACK_TERMS = ("공격", "때리", "친다", "공세")
ACTION_PICKUP_TERMS = ("획득", "줍", "주워", "가져", "챙")
ACTION_FLEE_TERMS = ("도망", "도주", "달아")

KO_NONLETHAL_MARKERS = frozenset({"훈련", "대련", "연습", "허수아비"})
KO_DOWNED_MARKERS = frozenset({"쓰러짐", "전투불능"})
KO_META_BREAKING_TERMS = (
    "시스템 프롬프트",
    "프롬프트 원문",
    "이전 지시를 무시",
)
KO_REAL_WORLD_TERMS = ("현실", "실제")
WEATHER_TERM = "날씨"

