"""Korean lexical shortcuts shared by runtime and LLM helpers."""

DIALOGUE_TERMS = (
    "말",
    "묻",
    "물어",
    "대화",
    "인사",
    "질문",
    "대답",
    "뭐야",
    "뭐예",
    "무엇",
    "어디",
    "왜",
    "어떻게",
    "누구",
    "인가",
    "되나요",
    "돼요",
    "농담",
    "수수께끼",
    "정답",
    "재미",
    "뭔 줄 알아",
    "뭔줄 알아",
)
DIALOGUE_QUESTION_TERMS = (
    "뭐야",
    "뭐예",
    "무엇",
    "어디",
    "왜",
    "어떻게",
    "누구",
    "인가",
    "되나요",
    "돼요",
)
DIALOGUE_TARGET_PARTICLES = ("에게", "한테")
DIALOGUE_GENERIC_TARGETS = ("그", "그 사람", "그들", "동료", "상대", "사람")
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
INSPECT_TERMS = ("살피", "살펴", "조사", "확인", "둘러보")
ABANDON_TERMS = ("포기", "거절", "취소")
ACTION_ATTACK_TERMS = ("공격", "때리", "친다", "공세")
ACTION_PICKUP_TERMS = ("획득", "줍", "주워", "가져", "챙")
ACTION_CREATE_DISTANCE_TERMS = ("도망", "도주", "달아")
LOOT_TERMS = ("조사", "수색", "뒤져", "루팅")
ROLL_MEANINGFUL_CLUE_TERMS = ("의미있는",)
ROLL_NO_CLUE_MARKERS = ("없", "보이지않", "못찾")
UNEARNED_ITEM_CLAIM_TOKENS = (
    "획득 아이템",
    "아이템 획득",
    "소지품",
    "인벤토리",
    "손에",
    "손안",
    "오른손",
    "왼손",
    "주머니",
    "가방",
    "챙깁",
    "챙겼",
    "쥡",
    "쥐고",
    "쥐었",
    "받아 듭",
    "받아들고",
    "얻습",
    "얻었",
)

KO_NONLETHAL_MARKERS = frozenset({"훈련", "대련", "연습", "허수아비"})
KO_META_BREAKING_TERMS = (
    "시스템 프롬프트",
    "프롬프트 원문",
    "이전 지시를 무시",
)
KO_REAL_WORLD_TERMS = ("현실", "실제")
WEATHER_TERM = "날씨"
