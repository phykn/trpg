"""Korean lexical shortcuts used before LLM classification."""

DIALOGUE_TERMS = (
    "말",
    "묻",
    "물어",
    "대화",
    "인사",
    "질문",
    "대답",
    "농담",
    "수수께끼",
    "정답",
    "재미",
    "뭔 줄 알아",
    "뭔줄 알아",
)
DIALOGUE_TARGET_PARTICLES = ("에게", "한테")
DIALOGUE_REQUEST_TERMS = ("달라고",)
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
QUEST_ACCEPT_TERMS = (*ACCEPT_TERMS, "받", "출항", "떠나", "떠납", "건너")
QUEST_CONTEXT_TERMS = ("의뢰", "일거리", "부탁", "퀘스트", "출항", "항해", "떠나", "떠납", "건너")
QUEST_TRAVEL_TERMS = ("출항", "항해", "떠나", "떠납", "건너", "이동")
ABANDON_TERMS = ("포기", "거절", "취소")
ACTION_ATTACK_TERMS = ("공격", "때리", "친다", "공세")
ACTION_PICKUP_TERMS = ("획득", "줍", "주워", "가져", "챙")
ACTION_CREATE_DISTANCE_TERMS = ("도망", "도주", "달아")
LOOT_TERMS = ("조사", "수색", "뒤져", "루팅")

KO_NONLETHAL_MARKERS = frozenset({"훈련", "대련", "연습", "허수아비"})
KO_META_BREAKING_TERMS = (
    "시스템 프롬프트",
    "프롬프트 원문",
    "이전 지시를 무시",
)
KO_REAL_WORLD_TERMS = ("현실", "실제")
WEATHER_TERM = "날씨"
