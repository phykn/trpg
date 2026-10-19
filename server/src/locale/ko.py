from __future__ import annotations

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
TAG_DEFAULT = {"edge": "유리함", "snag": "불리함"}
TAG_KEYS = {"@suspicion": "의심", "@broken_promise": "약속을 어김", "@scar": "흉터"}

# How a person regards the player, by trust; fear above this shows instead.
TRUST_WORDS = {-3: "적대", -2: "불신", -1: "경계", 0: "무덤덤", 1: "호의", 2: "신뢰", 3: "유대"}
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
    "claim": "{h}에게 {claim}",
    "try_self": "{approach}{으로} 해 본다",
    "try": "{x}에 {approach}{으로} 맞선다",
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
NO_RELY = "기대지 않음"
CONSUMED = {"tag": "쓰면 사라짐", "trait": "장에 한 번"}

# Effect names on confirm cards and favors.
EFFECT = {
    "move_player": "{y}{으로} 감",
    "gain": "{x}{을} 받음",
    "move": "{x}: {y}",
    "fill": "{o} {v}",
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
    "text": "아직 문장을 읽을 수 없습니다. 버튼을 눌러 주세요.",
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
    "fill": "{o}: {n}/{boxes}",
    "trust": "{g}{은} 당신을 {word}",
    "fear": "{g}{은} 당신을 {word}",
    "stat": "당신의 {item}: {n}",
    "trait": "당신의 특성: {name}",
    "promise": "당신은 {h}에게 {name}{을} 약속했습니다",
    "kindness": "{g}{은} 당신에게 신세를 졌습니다",
    "belief": "당신이 믿는 것: {text}",
    "memory": "지난 일: {label}",
    "senses": "{x}: {text}",
    "voice": "{x}의 말투: {text}",
    "desire": "{x}{이} 바라는 것: {text}",
    "fear_of": "{x}{이} 두려워하는 것: {text}",
    "look": "{x}의 생김새: {text}",
    "topics": "{x}에게 물을 수 있는 것: {text}",
    "wants": "{x}{이} 반길 물건: {text}",
}
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
END = "더 하는 것이 없다"
STEP_QUESTION = {1: "플레이어 문장이 맨 처음 하려는 일은 무엇입니까?",
                 2: "그 다음에 이어서 하는 일은 무엇입니까?",
                 3: "그 다음에 또 이어서 하는 일은 무엇입니까?"}
SLOT_QUESTION = {
    "intent": "플레이어 문장에서 이 행동이 가리키는 것은 무엇입니까?",
    "target": "플레이어가 맞서거나 해 보려는 대상은 무엇입니까?",
    "approach": "플레이어는 어떤 방식으로 합니까?",
    "strain": "이 장면에서 그 행동은 어떻습니까?",
    "tone": "플레이어는 어떤 태도로 말합니까?",
    "claim": "플레이어는 어떤 거짓 주장을 합니까?",
}
STRAIN_DESC = {"natural": "자연스럽게 할 수 있음", "forced": "할 수는 있지만 무리함", "impossible": "이 장면에서 할 수 없음"}
TONE_DESC = {"polite": "정중하게 묻거나 부탁함", "friendly": "친근하게 말함", "plead": "간청하거나 호소함",
             "threaten": "겁을 주거나 위협함", "deceive": "거짓말을 하거나 속임"}
APPROACH_DESC = {"force": "힘으로 밀어붙이거나 부수거나 버팀", "finesse": "손재주, 몸놀림, 몰래 움직임",
                 "wits": "관찰, 계획, 꾀, 시선 돌리기", "charm": "말이나 태도로 마음을 움직임"}
NO_CLAIM = "거짓 주장이 없음"
NOT_IN_WORLD = "이 세계에는 없는 것입니다."
NOT_POSSIBLE = "이 장면에서는 할 수 없는 일입니다."
META_REPLY = "이야기 속에서 당신이 하는 일을 적어 주세요. 저장은 저절로 됩니다."
META = ("저장", "다시 시작", "처음부터", "규칙", "도움말", "게임", "인공지능", "치트")
# Layer 0 cues for try's approach (engine.md 3.1). One matching approach fills the slot.
APPROACH_WORDS = {
    "force": ("밀어", "밀치", "부수", "부숴", "때려", "힘껏", "들이받", "걷어차", "비틀", "버텨", "당겨"),
    "finesse": ("몰래", "살금", "슬쩍", "조심스레", "살살", "재빨리", "기어", "타고", "넘어", "따고", "따서"),
    "wits": ("살펴", "꾀", "재치", "속여", "유인", "시선을 돌", "던져", "계획", "궁리", "고쳐", "다듬"),
    "charm": ("달래", "설득", "부탁", "어르", "다독", "호소", "구슬"),
}
TO_PERSON = ("에게", "한테", "께")
CLARIFY_SLOT = {"intent": "무엇을 말씀하신 건가요?", "target": "무엇에 맞서나요?"}
CHOOSER = """당신은 한국어 TRPG의 입력 분류기입니다. 플레이어 문장이 맨 처음 하려는 일을 선택지에서 번호 하나로 고릅니다. 번호만 답합니다."""
CHOOSER_PROMPT = "플레이어 문장: {text}\n선택지:\n{options}\n번호:"
NO_TARGET = "특정한 대상 없이"


# Change frames of 𝔗 by step-record change kind; no numbers reach the narrator.
CHANGE = {
    "fill": "{name}{이} 조금 풀렸습니다",
    "fill_done": "{name}{이} 다 풀렸습니다",
    "clock": "{name}{이} 다가왔습니다",
    "crisis": "{name}{이} 조금 물러났습니다",
    "arrival": "{name}{이} 들이닥쳤습니다",
    "tag_add": "{owner}에 {name}{이} 생겼습니다",
    "scar": "당신에게 {name}{이} 남았습니다",
    "tag_remove": "{owner}의 {name}{이} 사라졌습니다",
    "wound_up": "당신이 다쳤습니다",
    "wound_down": "당신의 상처가 조금 나았습니다",
    "move_get": "{to}{이} {name}{을} 얻었습니다",
    "move_lose": "{from}{이} {name}{을} 내주었습니다",
    "move_place": "{name}{이} {to}에 왔습니다",
    "reveal": "당신은 새로 알게 되었습니다: {text}",
    "reveal_hidden": "{name}{이} 드러났습니다",
    "link_open": "{name}{으로} 가는 길이 열렸습니다",
    "link_close": "{name}{으로} 가는 길이 끊겼습니다",
    "regards_up": "{name}의 마음이 당신 쪽으로 움직였습니다",
    "regards_down": "{name}의 마음이 당신에게서 멀어졌습니다",
    "promise_made": "당신은 {name}에게 {promise}{을} 약속했습니다",
    "kindness_made": "{name}{이} 당신에게 신세를 졌습니다",
    "promise_kept": "당신은 {name}과의 약속을 지켰습니다",
    "promise_broken": "당신은 {name}과의 약속을 어겼습니다",
    "promise_closed": "{name}과의 빚이 정리되었습니다",
    "chapter": "새 장이 시작됩니다: {name}",
    "ending": "이야기가 끝납니다: {name}",
}
STEP_LINE = "{label}: {result}"
NARRATOR = """당신은 한국어 TRPG의 서술자입니다. [일어난 일]을 장면으로 보여 줍니다.
- 플레이어를 '당신'이라 부르고, 대사 밖의 모든 문장을 합니다체(-습니다/-ㅂ니다)로 끝냅니다.
- {sentences}문장 이하, 공백 포함 {chars}자 이하로 씁니다. 마지막 문장은 지금 상황입니다.
- 선택지를 늘어놓거나 목록을 쓰지 않습니다. 플레이어의 감정이나 생각을 정하지 않습니다.
- 숫자, 주사위, 규칙 용어를 쓰지 않습니다.
- [일어난 일]의 행동과 변화만 일어납니다. 당신은 그 밖의 행동을 하지 않고, 아직 얻지 않은 것을 얻거나 지닌 것을 넘기지 않습니다.
- [문맥]에 없는 사람, 물건, 길을 만들지 않습니다. 냄새, 날씨, 소리, 표정은 자유롭게 씁니다.
- [일어난 일]에 성공이나 실패가 있으면 첫 문장에서 그 결과가 분명히 드러나게 씁니다. 실패는 일이 틀어지는 모습으로 씁니다.
- [플레이어 문장]은 뜻을 헤아려 읽습니다. 줄임말, 오타, 말투를 그대로 옮기지 않고 당신의 자연스러운 행동과 말로 보여 줍니다.
- 플레이어가 묻거나 알고 싶어 하는 것은 [문맥]으로 답할 수 있는 만큼 장면 속에서 답합니다. [문맥]에 없는 것은 당신이 아직 알아낼 수 없는 모습으로 씁니다."""
STYLE = "[문체]"
HEAD = {"context": "[문맥]", "happened": "[일어난 일]", "tags": "[새 태그]", "previous": "[앞 서술] (이미 보여 줌, 되풀이 금지)",
        "player": "[플레이어 문장]", "ending": "[결말]", "feedback": "[고칠 점]", "notable": "[이 장의 일]"}
NAMING = "이번에 생긴 태그마다 서술 뒤에 한 줄씩 '태그: 이름'을 적으십시오. 이름은 12자 이하의 짧은 말입니다. 기본 이름: {names}"
ENDING_FRAME = "이 서술로 이야기가 끝납니다. 다음 틀로 마무리하고 다음 행동을 묻지 않습니다: {frame}"
RECAP_TASK = "장 '{title}'이 끝났습니다. 아래 일들을 되짚는 짧은 문단 하나를 쓰십시오. {sentences}문장 이하, {chars}자 이하, 합니다체."
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
    "contradicts": "문맥의 사실과 어긋납니다.",
    "invents": "문맥에 없는 사람, 물건, 길을 지어냈습니다.",
}
REWRITE = "아래 문장을 받지 않았습니다. 이유를 고쳐 처음부터 다시 쓰십시오."
CHECK = {"contradicts": "이 문장은 문맥의 사실과 어긋납니까?",
         "invents": "이 문장은 문맥에 없는 사람, 물건, 길을 지어냈습니까?"}
YES, NO = "그렇다", "아니다"
GETS = ("얻", "손에 넣", "집어 들", "집어", "주웠", "쥐었", "받았", "받아 들", "챙겼", "챙깁")
GIVES = ("건넸", "건넵", "내주었", "내줍", "넘겼", "넘깁", "내밀었", "쥐여 주")
RULE_WORDS = ("주사위", "판정", "굴림", "칸", "점수", "성공입니다", "실패입니다", "보정")
NARRATION_ERROR = "서술 모델이 응답하지 않습니다. 다시 시도해 주세요."
NOTHING_CHANGED = "조용히 시간이 흐릅니다."
OPENS = ("열렸", "열린", "열립", "열리", "풀렸", "풀립", "무너졌", "무너집", "부서졌", "부서집", "뚫렸", "뚫립", "활짝")
