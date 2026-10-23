from __future__ import annotations

YOU = "당신"
APPROACHES = {"force": "완력", "finesse": "솜씨", "wits": "재치", "charm": "매력"}
APPROACH_HINT = {
    "force": "밀고 버티는 힘",
    "finesse": "섬세한 손과 몸",
    "wits": "살피고 꾀내기",
    "charm": "말로 얻는 마음",
}
TONES = {"polite": "정중하게", "friendly": "친근하게", "plead": "간청하며", "threaten": "위협하며", "deceive": "속여서"}
STRAINS = {"natural": "자연스럽게", "forced": "무리해서"}
RESULTS = {"success": "성공", "fail": "실패", "none": "", "blocked": "막힘"}
SHEET = {"beats": "박자", "wounds": "상처", "growth": "성장"}

# Default tag names: by kind, and the "@" keys the rules give to the tags they place.
# "유리함" was narrated as glass, 유리 (qa_test/runs/play-5-odd 9).
TAG_DEFAULT = {"edge": "이점", "snag": "불리함"}
TAG_KEYS = {"@suspicion": "의심", "@broken_promise": "약속을 어김", "@scar": "흉터"}

# How a person regards the player, by trust; fear above this shows instead. "무덤덤" at zero read as a mood that the
# persona's cheer contradicted in every playtest (play-2-*, play-3-*), so zero names the stance.
TRUST_WORDS = {-3: "적대", -2: "불신", -1: "경계", 0: "중립", 1: "호의", 2: "신뢰", 3: "유대"}
# What a roll leans on in a person: a bond (trust 3) or a companion (rule.md 2).
BOND = "{h}{와}의 유대"
HELPER = "{h}의 도움"
FEARFUL, FEAR_WORD = 2, "두려움"
# A threat meets negative fear, so that chip names its absence.
UNAFRAID = "겁 없음"

# {을}/{이}/{은}/{와}/{으로} follow the value before them.
ACTION = {
    "go": "{q}{으로} 간다",
    "look": "{x}{을} 살핀다",
    "take": "{x}{을} 집는다",
    "give": "{h}에게 {x}{을} 건넨다",
    "talk": "{h}에게 {title}에 대해 묻는다",
    "favor": "{h}에게 {label}",
    "chat": "{h}{와} 이야기한다",
    "come": "{h}에게 같이 가자고 한다",
    "stay": "{h}에게 여기서 기다려 달라고 한다",
    "claim": "{h}에게 {claim}",
    # Changes nothing and stands for whatever the sentence said; "재치로 해 본다" for a greeting said nothing
    # (play-3-odd 1, 10).
    "try_self": "말한 대로 해 본다",
    "try": "{x}{을} {approach}{으로} 다룬다",
    "try_agent": "{x}{을} {approach}{으로} 상대한다",
    "declare": "선언: {name}",
    "pass": "장면을 넘긴다",
    "rest": "쉬어 간다",
    "choose": "{name}",
    "grow": "{approach} {before}→{after}",
    "grow_trait": "특성 바꾸기: {name}",
    "grow_scar": "흉터 지우기: {name}",
}
SWAP = "{old} → {new}"
RELYING = "{rely}에 기대어 "
# Something known about a thing is named apart from the thing: the roll card listed both under the thing's name, and a
# clue about an obstacle read as the obstacle helping against itself (qa_test/runs/play-3-explorer 13, 37; play-3-talker 30).
CLUE = "{name} 단서"
NO_RELY = "기대지 않음"
MOVE_WITH = "{name}{와} 함께"
# A sentence about someone left behind must tell the parting: stay, stop, wait, see off.
PARTING = ("남", "멈춰", "멈추", "머무", "머물", "기다", "배웅", "돌아서", "따라오지", "올라오지", "들어오지")
AFAR = ("멀리", "먼 곳")
MOVE_LEFT = "{name}{은} 남음: {fear}"
# A tag goes for good and a trait returns next chapter, but on the card both are one use away from gone.
CONSUMED = {"tag": "1번 남음", **dict.fromkeys(("trait", "thing", "prop"), "이번 장 1번")}
# The roll card's relevance question (engine.md 4.2): one option per reliance, and none.
ATTEMPT = "시도: {label}"
RELY_QUESTION = "이 시도를 실제로 돕는 것은 무엇입니까?"
RELY_NONE = "아무것도 이 시도를 돕지 않는다"
RELY_DESC = {"tag": "유리한 점 '{name}'", "trait": "특성 '{name}': {text}", "thing": "지닌 물건 '{name}': {text}",
             "prop": "아는 사실: {text}", "bond": "{name}{이} 당신을 깊이 믿는다"}

# Effect names on confirm cards and favors.
EFFECT = {
    "move_player": "{y}{으로} 감",
    "gain": "{x}{을} 받음",
    "move": "{x}{을} {y}에 둠",
    "move_agent": "{x}{이} {y}에게 감",
    "fill": "{o} {v}칸",
    "regards": "{g}의 마음이 움직임",
    "reveal": "새로 앎",
    "tag": "{name}",
    "link": "길이 열림",
    "unlink": "길이 끊김",
    "retire": "{o}{이} 사라짐",
    "flag": "상황이 바뀜",
}

REFUSED = {
    "candidate": "지금은 할 수 없는 행동입니다.",
    "card": "이 카드의 선택지가 아닙니다.",
    "ended": "이야기가 끝났습니다.",
    "text": "지금은 문장을 읽을 수 없습니다.",
}
WHY = {
    "blocked": "{ob}{이} {x}{을} 막고 있습니다.",
    "blocked_way": "{ob}{이} {x}{으로} 가는 길을 막고 있습니다.",
    "away": "{x}{은} 여기 없습니다.",
    "not_held": "{x}{을} 지니고 있지 않습니다.",
}
ERRORS = {
    "missing": "저장된 게임을 찾을 수 없습니다.",
    "invalid": "받아들일 수 없는 요청입니다.",
}


def _final(word: str) -> tuple[bool, bool]:
    """(has a final consonant, the final is ㄹ) for the last Hangul syllable or digit."""
    for char in reversed(word.strip()):
        code = ord(char) - 0xAC00
        if 0 <= code < 11172:
            final = code % 28
            return final != 0, final == 8
        if char.isdigit():
            return char in "013678", char in "178"
        if char.isalpha():
            return False, False
    return False, False


def josa(word: str, form: str) -> str:
    final, rieul = _final(word)
    if form == "으로":
        return "로" if not final or rieul else "으로"
    pairs = {"을": ("을", "를"), "이": ("이", "가"), "은": ("은", "는"), "와": ("과", "와")}
    with_final, without = pairs[form]
    return with_final if final else without


def fill(template: str, **values) -> str:
    """Format a template whose {을}/{이}/{은}/{와}/{으로} follow the preceding value."""
    out, i = "", 0
    while i < len(template):
        if template[i] == "{":
            end = template.index("}", i)
            key = template[i + 1:end]
            out += josa(out, key) if key in ("을", "이", "은", "와", "으로") else str(values[key])
            i = end + 1
        else:
            out += template[i]
            i += 1
    return out


def attitude(trust: int, fear: int) -> str:
    return FEAR_WORD if fear >= FEARFUL else TRUST_WORDS[trust]


# The frame table 𝔗 (engine.md 1): one present frame per predicate.

FRAME = {
    "at_place": "{x}{은} {y}에 있습니다",
    "at_agent": "{y}{이} {x}{을} 지니고 있습니다",
    "link": "{p}에서 {q}{으로} 갈 수 있습니다",
    "mark": "{x}에 {name}{이} 있습니다",
    "mark_agent": "{x}에게 {name}{이} 있습니다",
    "wounded": "당신은 다친 몸입니다",
    "pace": "{o}: {word}",
    "fill": "{o}: {n}/{boxes}",
    "trust": "{g}{은} 당신을 {word}",
    "fear": "{g}{은} 당신을 {word}",
    "stat": "당신의 {item}: {n}",
    "trait": "당신의 특성: {name}",
    "promise": "당신은 {h}에게 지킬 약속이 있습니다: {name}",
    "kindness": "{g}{은} 당신에게 신세를 졌습니다",
    "follows": "{h}{은} 당신과 함께 다닙니다",
    "belief": "당신이 믿는 것: {text}",
    "memory": "지난 일: {label}",
    "senses": "{x}: {text}",
    "persona": "{x}의 성격({type}): {text}",
    "voice": "{x}의 말투: {text}",
    "desire": "{x}{이} 바라는 것: {text}",
    "fear_of": "{x}{이} 두려워하는 것: {text}",
    "knows": "{x}{이} 아는 것: {text}",
    "look": "{x}의 생김새: {text}",
    "topics": "{x}에게 물을 수 있는 것: {text}",
    "wants": "{x}{이} 반길 물건: {text}",
}
# A character's temperament, by the sixteen familiar types: one line on how they speak and react (story.md 3.4).
PERSONAS = {
    "ISTJ": "말수가 적고 사실만 짧게 말합니다. 약속과 규칙을 중히 여기고, 낯선 사람은 쉽게 믿지 않습니다.",
    "ISFJ": "조용하고 다정합니다. 남을 먼저 챙기고, 걱정을 말끝에 흘립니다.",
    "INFJ": "차분하고 속을 잘 드러내지 않습니다. 상대의 속뜻을 헤아리며 조심스럽게 묻습니다.",
    "INTJ": "냉정하고 계산이 빠릅니다. 감정보다 쓸모와 계획을 말합니다.",
    "ISTP": "무뚝뚝하고 손이 먼저 나갑니다. 필요한 말만 툭 던집니다.",
    "ISFP": "수줍고 감정이 얼굴에 먼저 드러납니다. 말보다 몸짓으로 답합니다.",
    "INFP": "여리고 생각이 많습니다. 자기가 믿는 것에는 고집을 부립니다.",
    "INTP": "엉뚱한 데를 캐묻습니다. 사람보다 이치에 관심이 많습니다.",
    "ESTP": "대담하고 장난스럽습니다. 일단 부딪쳐 보고, 말이 거칩니다.",
    "ESFP": "밝고 수다스럽습니다. 분위기를 띄우고 감정을 숨기지 않습니다.",
    "ENFP": "호기심이 많고 쉽게 들뜹니다. 말이 빠르고 금세 친해집니다.",
    "ENTP": "말재주가 좋고 놀리기를 즐깁니다. 반박하며 상대를 떠봅니다.",
    "ESTJ": "단호하고 지시하듯 말합니다. 질서와 책임을 앞세웁니다.",
    "ESFJ": "살갑고 남의 일에 관심이 많습니다. 사정을 묻고 챙겨 줍니다.",
    "ENFJ": "따뜻하고 말에 힘이 있습니다. 상대를 북돋우며 이끕니다.",
    "ENTJ": "거침없고 결론부터 말합니다. 상대가 따르기를 바랍니다.",
}
# How far an obstacle and how near a carried clock or deadline is, in words, for prose that may not say numbers.
# Progress is told as going the player's way: "loosened" was narrated literally, as a lamp or a hound coming loose
# (qa_test/runs/play-2-explorer 38, play-2-odd 30, play-3-bold 9).
OVERCOME = ("조금씩 뜻대로 되어 갑니다", "거의 뜻대로 되었습니다", "뜻대로 되었습니다")
PACE = ("아직 멀었습니다", "다가오고 있습니다", "코앞에 닥쳤습니다")
TRUST_VERBS = {-3: "적대합니다", -2: "믿지 않습니다", -1: "경계합니다", 0: "덤덤하게 대합니다",
               1: "호의적으로 대합니다", 2: "신뢰합니다", 3: "깊이 신뢰합니다"}
FEAR_VERBS = {-3: "업신여깁니다", -2: "얕봅니다", -1: "만만하게 봅니다", 1: "조금 두려워합니다",
              2: "두려워합니다", 3: "몹시 두려워합니다"}
SECTIONS = {"fact": "[사실]", "belief": "[믿음]", "memory": "[기억]", "public": "[알려진 것]"}


# Layer 1 option descriptions, one per schema a sentence can choose.
SCHEMA_DESC = {
    "go": "어딘가로 간다",
    "look": "무언가를 살피거나 읽어 보며, 그것이 어떤지 알아본다",
    "take": "무언가를 집는다",
    "give": "누군가에게 무언가를 건넨다",
    "talk": "누군가와 말한다",
    "try": "무언가에 맞서거나 해 본다",
    "declare": "자신에 대한 사실을 밝힌다",
    "cut": "기다리거나 쉬며 시간을 보낸다",
    "choose": "갈림길에서 하나를 고른다",
}
# Layer 1 options: what each schema covers, with story-free examples aimed at the model's confusions (persuading
# and distracting are try, a decision is choose, a recalled tie is declare); decision-1 REPORT.
SCHEMA_ASK = {
    "go": "어딘가로 간다 (예: 북쪽 문으로 나간다, 위층으로 올라가자)",
    "look": "무언가를 살피거나 읽어 보며, 그것이 어떤지 알아본다 (예: 상자 안을 들여다본다, 저건 뭐지?)",
    "take": "무언가를 집는다 (예: 바닥의 칼을 줍는다)",
    "give": "누군가에게 무언가를 건넨다 (예: 문지기에게 동전을 쥐여 준다)",
    "talk": "누군가에게 묻거나, 부탁하거나, 겁을 주거나, 속이는 말을 한다 (예: 노인에게 길을 묻는다)",
    "try": "무언가를 이루려고 힘, 솜씨, 꾀, 말솜씨로 맞선다 (예: 벽을 부순다, 매듭을 푼다, 미끼로 주의를 끈다, "
           "적의를 품은 상대를 구슬려 마음을 돌린다, 몸을 단련한다)",
    "declare": "자신의 과거나 인연을 새로 밝히거나 떠올린다 (예: 나는 이 마을 출신이다, 그는 내 옛 스승이다)",
    "cut": "기다리거나 쉬며 시간을 보낸다 (예: 날이 밝을 때까지 기다린다, 잠깐 눈을 붙인다)",
    "choose": "어떻게 할지 결정을 내린다 (예: 남은 돈은 고아원에 맡기기로 한다, 두 길 중 강 쪽을 택한다)",
}
# With a fork in the scene its own choices are the examples: the general ones left "pour all the oil on the lamp"
# reading as a try (qa_test/runs/play-1-*).
CHOOSE_HERE = "어떻게 할지 결정을 내린다 (예: {choices})"
STEP_QUESTION = "플레이어 문장에서 가장 먼저 하는 행동은 무엇입니까? 뒤에 이어지는 행동은 보지 않습니다."
# What kind of line it is, judged on the sentence alone; form (quotes, an addressee, politeness) is no signal, since
# players type fragments (engine.md 3.2). Act lists resting, wondering what is about, deciding and recalling: without
# them 36 of 274 bench actions read as speech or musing, with them 6 (qa_test/runs/intent-1-probe).
KIND_QUESTION = "플레이어 문장은 어떤 말입니까?"
KIND = {
    "act": "장면에서 무언가를 한다 (예: 어딘가로 가거나 쉬거나 자거나 기다린다, 주변에 무엇이 있는지 둘러보거나 궁금해한다, "
           "무언가를 살피거나 집거나 건넨다, 무언가에 맞선다, 결정을 내린다, 자신의 과거나 아는 사람을 떠올린다, "
           "누군가에게 무언가를 해 달라고 하거나 같이 가자고 하거나 겁을 주거나 속인다)",
    "say": "곁에 있는 누군가에게 말을 건넬 뿐 아무것도 하지 않는다 (예: 인사, 안부, 잡담, 맞장구, 고맙다는 말, 상대에게 묻는 지나가는 질문)",
    "muse": "혼자 느끼거나 감탄할 뿐 아무것도 하지 않는다 (예: 감탄, 투덜거림, 느낌, 웃음)",
}
# Asking the count beats an "end" option after each step: the model stops adding steps to one-action sentences.
COUNT_QUESTION = "플레이어 문장은 서로 다른 행동을 몇 가지 차례로 합니까?"
COUNT = {"1": "한 가지 행동만 한다", "2": "두 가지 행동을 차례로 한다", "3": "세 가지 이상의 행동을 차례로 한다"}
SLOT_QUESTION = {
    "intent": "플레이어 문장에서 이 행동이 가리키는 것은 무엇입니까?",
    "target": "플레이어가 맞서거나 해 보려는 대상은 무엇입니까?",
    "approach": "플레이어는 어떤 방식으로 합니까?",
    "strain": "이 장면에서 그 행동은 어떻습니까?",
    "tone": "플레이어는 어떤 태도로 말합니까?",
}
CLAIM_QUESTION = '플레이어는 이렇게 말합니까? "{text}"'
YES, NO = "그렇다", "아니다"
STRAIN_DESC = {"natural": "자연스럽게 할 수 있음", "forced": "할 수는 있지만 무리함", "impossible": "이 장면에서 할 수 없음"}
TONE_DESC = {"polite": "정중하게 묻거나 부탁함", "friendly": "친근하게 말함", "plead": "간청하거나 호소함",
             "threaten": "겁을 주거나 위협함", "deceive": "거짓말을 하거나 속임"}
APPROACH_DESC = {"force": "힘으로 밀어붙이거나 부수거나 버팀", "finesse": "손재주, 몸놀림, 몰래 움직임",
                 "wits": "관찰, 계획, 꾀, 시선 돌리기", "charm": "말이나 태도로 마음을 움직임"}
NOT_IN_WORLD = "이 이야기에는 그런 것이 없습니다."
NOT_POSSIBLE = "이 장면에서는 할 수 없는 일입니다."
ALREADY_HERE = "이미 {place}에 있습니다."
NO_FARTHER = "{place} 안에서 따로 갈 곳은 없습니다. 갈 수 있는 곳은 {ways}입니다."
META_REPLY = "이야기 속에서 당신이 하는 일을 적어 주세요. 저장은 저절로 됩니다."
GROWTH_WORD, GROWTH_REPLY = "성장", "성장은 주인공 화면의 '성장'에서 고릅니다."
# Whole phrases, so a storehouse (저장고) or "처음부터 차근차근" stays in the story.
META = ("저장해", "저장하", "저장은", "저장이", "세이브", "다시 시작", "처음부터 다시", "게임 규칙", "규칙이 뭐", "규칙 알려",
        "도움말", "인공지능", "치트")
# Layer 0 cues for try's approach (engine.md 3.1). One matching approach fills the slot.
APPROACH_WORDS = {
    "force": ("밀어", "밀치", "부수", "부숴", "때려", "힘껏", "들이받", "걷어차", "비틀", "버텨", "당겨"),
    "finesse": ("몰래", "살금", "슬쩍", "조심스레", "살살", "재빨리", "기어", "타고", "넘어", "따고", "따서", "비집"),
    "wits": ("살펴", "꾀", "재치", "속여", "유인", "시선을 돌", "던져", "계획", "궁리", "고쳐", "다듬"),
    "charm": ("달래", "설득", "부탁", "어르", "다독", "호소", "구슬"),
}
TO_PERSON = ("에게", "한테", "께")
DETOUR = "{why} 어떻게 할까요?"
CLARIFY_SLOT = {"intent": "무엇을 말씀하신 건가요?", "target": "무엇을 두고 하는 행동인가요?"}
READER = ("당신은 한국어 TRPG의 입력 분류기입니다. 플레이어 문장이 하는 행동을 일어나는 차례대로 선택지 번호로 적습니다. "
          "한 행동을 여러 말로 풀어 쓴 것은 하나로 셉니다. 번호만 쉼표로 나누어 답합니다.")
SENTENCE = "플레이어 문장: {text}"
READER_PROMPT = SENTENCE + "\n선택지:\n{options}\n번호:"
PICKER = "당신은 한국어 TRPG의 입력 분류기입니다. 문맥과 플레이어 문장을 읽고 질문에 맞는 답을 선택지에서 번호 하나로 고릅니다. 번호만 답합니다."
PICKER_PROMPT = "{state}\n\n질문: {question}\n선택지:\n{options}\n번호:"
NO_TARGET = "특정한 대상 없이"


# Change frames of 𝔗 by step-record change kind; no numbers reach the narrator.
CHANGE = {
    "fill": "{name}{이} 조금씩 당신 뜻대로 되어 갑니다",
    "fill_done": "{name}{이} 마침내 당신 뜻대로 되었습니다",
    "fill_back": "{name}{이} 다시 뜻대로 되지 않습니다",
    "clock": "{name}: 다가왔습니다",
    "crisis": "{name}: 끝내 닥쳤습니다",
    "recede": "{name}: 조금 물러났습니다",
    "arrival": "{name}: 들이닥쳤습니다",
    "deadline": "{name}: 목표를 이루지 못한 채 시간이 다 되었습니다",
    "tag_add": "{owner}에 {name}{이} 생겼습니다",
    "tag_add_agent": "{owner}에게 {name}{이} 생겼습니다",
    "scar": "당신에게 {name}{이} 남았습니다",
    "tag_remove": "{owner}의 {name}{이} 사라졌습니다",
    "wound_up": "당신이 다쳤습니다",
    "wound_down": "당신의 상처가 조금 나았습니다",
    "move_get": "{to}{이} {name}{을} 얻었습니다",
    "move_lose": "{from}{이} {name}{을} 내주었습니다",
    "move_place": "{name}{이} {to}에 왔습니다",
    "move_with": "{name}{이} 당신과 함께 {to}에 왔습니다",
    "follow_start": "{name}{이} 당신과 함께 다니기로 했습니다",
    "follow_start_bounded": "{name}{이} 당신과 함께 다니기로 했지만 {places}에는 가지 않습니다",
    "follow_stop": "{name}{은} 이제 당신을 따라다니지 않습니다",
    "reveal": "당신은 새로 알게 되었습니다: {text}",
    "reveal_hidden": "{name}{이} 드러났습니다",
    "link_open": "{name}{으로} 가는 길이 열렸습니다",
    "link_close": "{name}{으로} 가는 길이 끊겼습니다",
    "between_open": "{a}{와} {b} 사이의 길이 열렸습니다",
    "between_close": "{a}{와} {b} 사이의 길이 끊겼습니다",
    "regards_up": "{name}의 마음이 당신 쪽으로 움직였습니다",
    "regards_down": "{name}의 마음이 당신에게서 멀어졌습니다",
    "promise_made": "당신은 {name}에게 약속했습니다: {promise}",
    "kindness_made": "{name}{이} 당신에게 신세를 졌습니다",
    "promise_kept": "당신은 {name}{와}의 약속을 지켰습니다",
    "promise_broken": "당신은 {name}{와}의 약속을 어겼습니다",
    "promise_closed": "{name}{와}의 빚이 정리되었습니다",
    "chapter": "새 장이 시작됩니다: {name}",
    "ending": "이야기가 끝납니다: {name}",
}
STEP_LINE = "{label}: {result}"
NARRATOR = """당신은 한국어 TRPG의 서술자입니다. [일어난 일]을 장면으로 보여 줍니다.
- 플레이어를 '당신'이라 부르고, 대사 밖의 모든 문장을 합니다체(-습니다/-ㅂ니다)로 끝냅니다.
- {sentences}문장 이하, 공백 포함 {chars}자 이하로 씁니다.
- 장면만 보여 줍니다. 선택지, 목록, 숫자, 주사위, 규칙 용어는 쓰지 않고, 플레이어의 감정과 생각은 플레이어에게 맡깁니다.
- [일어난 일]의 행동과 변화만 일어납니다. 당신은 그 밖의 행동을 하지 않고, 아직 얻지 않은 것을 얻거나 지닌 것을 넘기지 않습니다.
- 사람, 물건, 길은 [문맥]에 있는 것만 씁니다. 냄새, 소리, 표정, 몸짓은 자유롭게 씁니다.
- 이 자리의 인물은 [문맥]의 성격, 말투, 마음대로 반응합니다. 당신이 말을 걸거나 무언가를 건네면 그 인물이 큰따옴표 대사로 직접 답합니다. 인물은 제자리에서 표정, 몸짓, 짧은 대사로 반응하고, 대사마다 누가 말하는지 앞뒤 문장에서 밝힙니다. 대사의 말씨는 [문맥]의 말투를 따르되 예시 대사를 그대로 옮기지 않고, 인물은 당신을 호칭 없이 부릅니다.
- 인물은 [문맥]과 [일어난 일]에 적힌 것만 압니다. 그 밖의 것을 물으면 모른다고 하거나 말을 돌립니다.
- [일어난 일]에 성공이나 실패가 있으면 첫 문장에서 그 결과가 분명히 드러나게 씁니다. 실패는 일이 틀어지는 모습으로 씁니다.
- [플레이어 문장]은 뜻을 헤아려 읽습니다. 줄임말, 오타, 말투를 그대로 옮기지 않고 당신의 자연스러운 행동과 말로 보여 줍니다.
- 플레이어가 묻거나 알고 싶어 하는 것은 [문맥]으로 답할 수 있는 만큼 장면 속에서 답합니다. [문맥]에 없는 것은 당신이 아직 알아낼 수 없는 모습으로 씁니다.
- 그림 없이 글로만 보여 주는 게임이니 글솜씨로 승부합니다. '눈을 반짝이며', '코끝을 스칩니다' 같은 흔한 표현 대신, 이 인물과 이 자리에만 있을 선명한 것 하나를 문장마다 고릅니다.
- 인물의 대사는 그 사람만 할 말입니다. 묻는 말에 답하면서도 그 사람의 바람이나 두려움, 버릇이 한 조각 묻어납니다.
- 마지막 문장은 정리하지 않고 여운이나 긴장을 남깁니다."""
STYLE = "[문체]"
HEAD = {"context": "[문맥]", "happened": "[일어난 일]", "tags": "[새 태그]", "previous": "[앞 서술] (이미 보여 준 글)",
        "said": "[앞서 나눈 말]", "shared": "[함께 겪은 일]",
        "now": "[이번 서술]",
        "player": "[플레이어 문장]", "ending": "[결말]", "feedback": "[고칠 점]", "notable": "[이 장의 일]"}
# The steering block closes the prompt: a small model follows the end of its prompt best (narr-2 REPORT).
# Clock and deadline names are events ("배가 암초에 닿는다") that were narrated as happening (qa_test/runs/play-1-bold
# 13–27). Only the steering says so: in the context lines, "아직 일어나지 않았고" made the check call ordinary
# sentences contradictions (narr-2/fix-2).
NOW = {"speaker": "{x}: {persona} 말투는 {voice}",
       "cue": "새로 그릴 감각: {cue}",
       "no_cue": "풍경은 이미 보여 주었으니, 이번에는 인물과 바뀐 것을 그립니다.",
       "pace": "때: {text}. 하늘, 빛, 파도는 이 흐름만큼만 바뀌고, 아직 일어나지 않은 일은 일어난 것처럼 쓰지 않습니다.",
       "worn": "최근 서술에서 거듭 쓴 표현이니 이번에는 다른 말로 씁니다: {words}",
       "left": "{name}{은} {place}에 남았습니다. 까닭: {fear}. 이제 이 자리에 없으니 헤어지는 모습만 그리고 곁에 있는 것처럼 쓰지 않습니다.",
       "bounded": "{name}{은} {places}에는 따라가지 않습니다. 까닭: {fear}. 그곳까지 함께 가겠다고 말하지 않습니다.",
       "partial": "{name}{은} 조금 진척이 있었을 뿐 아직 다 되지 않았습니다. 눈앞의 작은 변화 하나로 보여 주고, 다 된 것처럼 쓰지 않습니다.",
       "done": "{name}{은} 마침내 다 되었습니다. 그것이 눈앞에서 어떻게 달라졌는지 보여 줍니다.",
       "struck": "이번에 닥친 일: {names}. 그 일로 눈앞의 무엇이 달라졌는지 한 문장으로 꼭 보여 줍니다.",
       "missed": "때가 다 된 일: {names}. 이번 장의 목표를 이루지 못했다는 것을 한 문장으로 꼭 보여 줍니다.",
       "blocked": "'{label}'는 무언가에 가로막혀 이루어지지 않았습니다. 상대가 대답하거나 그 일이 된 것처럼 쓰지 않고, 무엇이 가로막았는지 보여 줍니다.",
       "relied": "이번 시도는 {rely}{을} 밑천으로 삼았습니다. 그것이 어떻게 쓰였는지 한 번 보여 줍니다.",
       "looked": "당신이 살펴본 {name}: {text}. 살펴서 알게 된 이 모습이나 글을 꼭 보여 줍니다.",
       "grown": "이번 일은 당신이 고른 성장뿐입니다. 앞 장면을 다시 쓰지 않고, 그 변화가 당신 안에 자리 잡는 짧은 순간만 손이나 숨, 시선으로 그립니다.",
       "waits": "플레이어 문장 가운데 '{label}'부터는 아직 하지 않았습니다. 그 앞에서 멈추고, 그 결과를 미리 쓰지 않습니다.",
       "waits_rest": "플레이어 문장의 나머지 행동은 아직 하지 않았습니다. [일어난 일]까지만 쓰고, 그 결과를 미리 쓰지 않습니다.",
       "talk": "{names}의 대답으로 시작합니다. 그 사람의 몸짓 하나와 대사면 충분하고, 풍경은 그리지 않습니다. 모르는 것은 모른다고 하거나 자기 걱정으로 말을 돌립니다.",
       "muse": "당신은 말하거나 혼잣말을 했을 뿐 아무것도 하지 않았습니다. 당신이 움직이거나 무언가를 했다고 쓰지 않습니다. {names}{이} 그 말에 짧게 반응합니다.",
       "muse_alone": "당신은 혼잣말을 했을 뿐 아무것도 하지 않았습니다. 당신이 움직이거나 무언가를 했다고 쓰지 않습니다. 그 말의 느낌에 주변의 한순간이 응답하게 씁니다.",
       "hint": "{names}의 그 반응이 다음에 해 볼 만한 길 하나를 넌지시 가리킵니다: '{hint}'. 당신이 그것을 했다고 쓰지 않고, 그 길을 위해 문장을 더하지 않습니다.",
       "hint_alone": "응답하는 그 한순간이 다음에 해 볼 만한 길 하나로 눈길을 끕니다: '{hint}'. 당신이 그것을 했다고 쓰지 않고, 그 길을 위해 문장을 더하지 않습니다.",
       "shared": "{names}{은} [함께 겪은 일]을 기억합니다. 이야기가 그쪽으로 가면 자기 말로 떠올리고, 없던 일은 만들지 않습니다.",
       "said": "{names}{은} [앞서 나눈 말]에서 한 말과 어긋나지 않게 말하고, 이미 한 말은 되풀이하지 않습니다.",
       "close": "이번에 바뀐 것을 보여 주고, 마지막 문장은 인물의 반응이나 눈앞의 것으로 끝냅니다.",
       "legacy": "결말에 담을 수 있는 것: {items}",
       "ending": "이 서술로 이야기가 끝납니다. 이번에 바뀐 것을 보여 준 뒤, 마지막 문장은 이 결말을 그립니다: {frame}",
       "ending_legacy": "이 서술로 이야기가 끝납니다. 첫 문장은 이번에 바뀐 것, 다음 문장은 위의 담을 수 있는 것 가운데 하나입니다. 여기 없는 사람은 '멀리'라는 말과 함께, 그가 있는 곳에서 이 결말을 맞는 모습으로만 그리고 그에게 새 일을 만들지 않습니다. 마지막 문장은 이 결말입니다: {frame}"}
HAPPENED_MUSE = "당신이 말하거나 혼잣말을 했습니다"
SAID_LINE = "당신: {text} / {x}: {lines}"
SAID_ALONE = "{x}: {lines}"
SHARED_LINE = "{x}{와} 함께: {line}"
NAMING = "이번에 생긴 태그마다 서술 뒤에 한 줄씩 '태그: 이름'을 적으십시오. 이름은 12자 이하의 짧은 말입니다. 기본 이름: {names}"
ENDING_FRAME = "이 서술로 이야기가 끝납니다. 다음 틀로 마무리하고 다음 행동을 묻지 않습니다: {frame}"
RECAP_TASK = "'{title}' 장이 끝났습니다. 아래 일들을 되짚는 짧은 문단 하나를 쓰십시오. {sentences}문장 이하, {chars}자 이하, 합니다체."
FEEDBACK = {
    "sentences": "문장이 너무 많습니다. {n}문장 이하로 줄이십시오.",
    "chars": "글이 너무 깁니다. {n}자 이하로 줄이십시오.",
    "plain": "합니다체가 아닌 문장이 있습니다.",
    "you": "플레이어를 '당신' 말고 다른 말로 불렀습니다.",
    "list": "목록이나 선택지 꼴을 썼습니다.",
    "number": "숫자나 규칙 용어를 썼습니다.",
    "foreign": "한자나 외국 글자를 썼습니다.",
    "hidden": "아직 드러나지 않은 이름을 썼습니다: {names}",
    "tag": "태그 이름이 너무 길거나 숨은 이름을 담았습니다.",
    "unearned": "아직 얻지 않은 물건을 얻었다고 썼습니다: {names}",
    "handed": "당신이 지닌 물건을 넘겼다고 썼습니다: {names}",
    "claim": "사실과 다른 말을 했습니다: {facts}",
    "absent": "이 자리에 없는 사람을 움직이게 썼습니다: {names}",
    "where": "당신은 지금 {place}에 있습니다.",
    "paren": "괄호를 썼습니다. 소리와 몸짓도 문장으로 쓰십시오.",
    "repeat": "앞 서술이나 예시 대사와 같은 말을 되풀이했습니다: {span}. 새로 바뀐 것을 쓰십시오.",
    "address": "대사에서 당신을 '{word}'(이)라고 불렀습니다. 인물은 당신을 호칭 없이 부릅니다.",
    "contradicts": "문맥의 사실과 어긋납니다.",
    "invents": "문맥에 없는 사람, 물건, 길을 지어냈습니다.",
}
REWRITE = "아래 문장을 받지 않았습니다. 이유를 고쳐 처음부터 다시 쓰십시오."
# One choice per sentence: two yes/no questions let the model answer "no" to both (decision-1 REPORT).
CHECK_QUESTION = "이 문장은 문맥과 비교해 어떻습니까?\n문장: {text}"
CHECK = {"fine": "문맥의 사실과 맞고, 문맥에 없는 것을 지어내지 않았다",
         "contradicts": "문맥의 사실과 어긋난다",
         "invents": "문맥에 없는 사람, 물건, 길을 지어냈다"}
# Vocative forms of address: a narrator that guesses the player's age or sex picks one of these.
ADDRESS = ("아저씨", "아주머니", "아줌마", "아가씨", "총각", "형씨", "젊은이", "언니", "오빠", "누나", "형님", "할아버지", "할머니")
ARRIVES = ("도착", "들어섭", "들어섰", "들어선", "다다릅", "다다랐", "이르렀", "발을 내디", "발을 들여")
GETS = ("얻", "손에 넣", "집어 들", "집어", "주웠", "쥐었", "받았", "받아 들", "챙겼", "챙깁")
GIVES = ("건넸", "건넵", "내주었", "내줍", "넘겼", "넘깁", "내밀었", "쥐여 주")
RULE_WORDS = ("주사위", "판정", "굴림", "칸", "점수", "성공입니다", "실패입니다", "보정")
NARRATION_ERROR = "서술 모델이 응답하지 않습니다. 다시 시도해 주세요."
NOTHING_CHANGED = "조용히 시간이 흐릅니다."
OPENS = ("열렸", "열린", "열립", "열리", "풀렸", "풀립", "무너졌", "무너집", "부서졌", "부서집", "뚫렸", "뚫립", "활짝")
