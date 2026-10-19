"""Engine-owned Korean text. Story text lives in the scenario, never here."""

import re

PLAYER_NAME = "당신"

APPROACHES = {"force": "힘", "finesse": "재주", "wits": "꾀", "charm": "말솜씨"}
APPROACH_HINT = {
    "force": "힘으로 밀어붙이거나 버팀",
    "finesse": "손재주, 몸놀림, 몰래 움직임",
    "wits": "속임수, 계획, 관찰, 틈 노리기",
    "charm": "말로 설득하거나 마음을 움직임",
}
ATTITUDES = {
    "polite": "정중하게 묻거나 부탁함",
    "empathy": "상대의 사정에 공감하며 말함",
    "persuade": "이유를 들어 설득함",
    "threaten": "겁을 주거나 위협함",
    "deceive": "거짓말을 하거나 속임",
}
PLAUSIBLE = {
    "natural": "이 장면에서 자연스럽게 할 수 있음",
    "stretch": "할 수는 있지만 무리가 큼",
    "impossible": "이 장면에서 할 수 없음",
}
TOUCH = {"desire": "상대가 바라는 것을 건드림", "fear": "상대가 두려워하는 것을 건드림", "none": "어느 쪽도 아님"}
GRADES = {"hit": "성공", "mixed": "대가 있는 성공", "miss": "실패"}
WOUND = "부상"
GOLD = "돈"
MOODS = {-2: "적대", -1: "경계", 0: "무덤덤", 1: "호의", 2: "신뢰"}
COSTS = {
    "danger": "위험 +{n}",
    "snag": "불리한 상황",
    "loss": "가진 것을 잃음",
    "snag_or_loss": "불리한 상황 또는 손실",
    "wound_or_loss": "부상 또는 손실",
}
TAG_DEFAULT = {"edge": "유리한 틈", "snag": "불리한 상황"}
TRACES = {"wanted": "수배", "suspicion": "의심", "reputation": "평판"}
NONE_OPTION = "해당 없음"
CHAT = "특정 화제 없이 나누는 잡담"
WHY_NOT = {
    "absent": "지금 장면에는 그런 대상이 없습니다.",
    "beyond": "지금의 당신으로는 할 수 없는 일입니다.",
    "rule": "이 세계에서는 그렇게 되지 않습니다.",
}
NOT_ACTION = "행동으로 읽히지 않습니다. 당신이 무엇을 하는지 적어 주십시오."
ERRORS = {
    "missing": "저장된 게임을 찾을 수 없습니다.",
    "version": "이 저장은 지금 원고와 맞지 않습니다.",
    "stale": "화면이 최신 상태가 아닙니다. 다시 불러와 주십시오.",
    "invalid": "받아들일 수 없는 요청입니다.",
    "model": "모델이 응답하지 않습니다. 잠시 뒤 다시 시도해 주십시오.",
    "save": "저장하지 못했습니다. 다시 시도해 주십시오.",
}

LABELS = {
    "move": "{name}{으로} 간다",
    "inspect": "{name}{을} 살핀다",
    "talk": "{name}{와} 이야기한다",
    "take": "{name}{을} 집는다",
    "give": "{who}에게 {name}{을} 건넨다",
    "use_tag": "{tag}{을} 이용해 {name}에 맞선다",
    "topic": "{who}에게 {name}에 대해 묻는다",
    "improvise": "다른 행동",
    "overcome": "{approach}{으로} {name}에 맞선다",
    "setup": "{approach}{으로} 유리한 상황을 만든다",
    "clear": "{approach}{으로} {name}{을} 걷어 낸다",
    "flavor": "그 밖의 행동",
    "grow_approach": "{name} {before}→{after}",
    "grow_trait": "특성 바꾸기: {old} → {name}",
}

SOLVE_LABEL = "{label} ({approach})"
IDLE_TALK = "말이 오갔지만 바뀐 것은 없습니다"
CHANGES = {
    "progress": "{name} {before}→{after}/{boxes}",
    "danger": "{name} {before}→{after}/{boxes}",
    "tag_add": "새 상황: {name}",
    "tag_use": "{name}{을} 썼습니다",
    "tag_drop": "{name}{이} 사라졌습니다",
    "relation": "{name}{와}의 관계 {before}→{after}",
    "learn": "알게 됨: {name}",
    "gain": "얻음: {name}",
    "lose": "잃음: {name}",
    "gold": "돈 {before}→{after}",
    "wound": "부상 {before}→{after}/3",
    "move": "{name}: {after}",
    "go": "이동: {name}",
    "leave": "{name}{이} 떠났습니다",
    "open": "길이 열림: {name}",
    "close": "길이 막힘: {name}",
    "quest": "이룸: {name}",
    "complication": "위험이 다 찼습니다: {name}",
    "downed": "당신은 쓰러졌습니다",
    "claim": "{name}에게 주장함",
    "exposed": "{name}{이} 거짓을 알아챘습니다",
    "chapter": "새 장: {name}",
    "ending": "결말: {name}",
    "reveal": "드러남: {name}",
    "companion": "동행: {name}",
    "inspect": "살펴봄: {name}",
    "grow": "성장: {name}",
    "flag": "",
}

ROLL = "주사위 {a}+{b} {mod:+d} = {total}: {grade}"

FIRST_STEP_QUESTION = "플레이어가 맨 처음 하려는 행동은 무엇입니까?"
NEXT_STEP_QUESTION = "앞의 행동을 마친 뒤 이어서 하는 {n}번째 행동은 무엇입니까? 더 없으면 none입니다."
IMPROVISE = "위 목록에 없는 행동을 직접 시도함 (밀기, 부수기, 훔치기, 숨기, 몰래 다가가기, 소란 피우기, 뇌물, 설득해서 무언가를 시키기 등)"
NONE_STEP = "이어지는 행동이 없음"
TARGET_QUESTION = "{n}번째 행동이 노리는 장애물이나 없애려는 불리한 상황은 무엇입니까?"
APPROACH_QUESTION = "{n}번째 행동은 어떤 방식에 가장 가깝습니까?"
PLAUSIBLE_QUESTION = "{n}번째 행동이 이 장면에서 말이 됩니까?"
USES_TAG_QUESTION = "{n}번째 행동이 장면의 유리한 상황 중 하나를 이용합니까?"
USES_THING_QUESTION = "{n}번째 행동이 지닌 물건, 아는 사실, 기술 중 하나를 이용합니까?"
USES_TRAIT_QUESTION = "{n}번째 행동이 플레이어의 특성을 살립니까?"
# Verb stems that name a way of acting. Kev 0.8B picked the approach right 7/16 times on the harbor
# eval set; a single matching cue was right 15/16. Used only when exactly one approach matches.
APPROACH_CUES = {
    "finesse": ["낚아채", "낚아챈", "틈에", "틈을 타", "한눈판", "딴 데 보는", "보는 사이", "훔치", "훔친", "슬쩍", "몰래", "살금", "쌓아", "넘어", "숨어", "숨는", "빼낸", "스며", "기어"],
    "force": ["밀어", "밀치", "부수", "부숴", "때려", "때린", "힘껏", "흔들", "찢", "걷어", "비틀"],
    "charm": ["설득", "호소", "간곡", "빌며", "빈다", "빌어", "거든", "거들", "따지", "따진", "거들", "도와", "사정한", "사정해", "부탁", "달래", "달랜", "다독", "안심시", "돕겠", "쥐여 주며", "간청", "애원"],
    "wits": ["외쳐", "짚어", "속이", "속여", "둘러대", "유인", "시선을 돌", "꾀어"],
}
# Honorifics after a name or role word when the player calls out to someone ("조사관 양반,", "도윤 씨,").
VOCATIVE = ["씨", "양반", "님", "아주머니", "아저씨", "어르신", "아", "야"]
# Speech verbs and the particles that mark who is spoken to. A sentence that names a present person with
# one of these is talk to that person: Kev sent "ask the smuggler the way into the prison" to a move.
TALK_CUES = ["속인", "위협", "으름장", "속삭", "여쭌", "여쭙", "묻", "물어", "물었", "말한", "말해", "말을 건", "거짓말", "둘러대", "속이", "속여", "협박", "얘기", "이야기",
             "따지", "따진", "사정", "부탁", "설득", "달라고", "하라고", "라고 한", "다고 한"]
TO_PERSON = ["에게", "한테", "께", "을 설득", "를 설득", "을 협박", "를 협박", "을 속", "를 속"]
# Movement verbs: with a known place's name they mean going there, even when it is not next door.
MOVE_CUES = ["돌아가", "서두른", "서둘러", "간다", "가자", "가 보", "가서", "가요", "갑니다", "걸어", "올라", "내려", "향한", "향해", "들어간", "돌아간",
             "달려", "이동", "피한다", "빠져나"]
# Giving verbs. A gift loses an item for good, so it needs one of these in the sentence: Kev added
# "give the ledger to Lu" to "open the ledger and read it".
GIVE_CUES = ["내밀", "내민", "주고", "준다", "줘", "주며", "주어", "건네", "건넨", "넘겨", "넘긴", "쥐여", "드린", "드리", "바친", "맡긴", "맡겨"]
# Endings of a request to the game rather than an act in the story ("점심 메뉴 추천해줘").
# Words about the game or the world outside it, turned back when the scene names nothing.
META_WORDS = ["게임", "인공지능", "몇 시", "너는 누구", "넌 누구"]
QUESTION_CUES = ["냐고", "느냐", "는지", "인지", "을까", "ㄹ까"]
META_ENDINGS = ("어때", "추천해줘", "추천해 줘", "알려줘", "알려 줘", "설명해줘", "설명해 줘", "뭐야", "뭐지", "어떻게 해", "도와줘", "도와 줘")
# Attitude verbs, read like APPROACH_CUES: one matching attitude wins over Kev's guess.
ATTITUDE_CUES = {
    "deceive": ["거짓말", "속이", "속여", "속인", "둘러대", "둘러댄", "꾸며"],
    "threaten": ["협박", "위협", "윽박", "겁을 주", "겁준", "으름장"],
    "empathy": ["다정", "위로", "공감", "걱정해", "달래", "달랜"],
    "persuade": ["설득"],
}
# A first-person claim about who the player is: "내가 세관에서 나온 사람이라고", "나는 영주의 사자다".
CLAIM_PATTERN = r"(나는|내가|나도|저는|제가)\s?\S.{0,24}(이라고|라고|이다|입니다|이오|이요|다\.|다$|다 |오$)"
# Verbs that tell a look from a grab when Kev splits between inspect and take of the same thing.
LOOK_CUES = ["훔쳐보", "훔쳐본", "엿보", "엿본", "뜯어보", "뜯어본", "관찰", "쳐다", "살펴", "살피", "살핀", "읽", "훑", "들여다", "확인"]
TAKE_CUES = ["떼어", "뜯어", "감춘", "감추", "숨긴", "숨겨", "품에", "소매에", "집", "챙기", "챙긴", "가져", "줍", "주워", "떼어", "빼낸", "넣는"]
# Looks that read like action verbs ("훔쳐본다" is a peek, not a theft); removed before reading the approach.
PEEKS = ["훔쳐보", "훔쳐본", "엿보", "엿본"]
# Plain sensing ("올려다본다", "냄새를 맡아 본다"): with no approach verb and no obstacle named, a moment
# without a roll rather than an attempt on whatever obstacle is nearby.
SENSE_CUES = ["훔쳐보", "엿보", "관찰", "쳐다", "걸터앉", "쉰다", "쉬며", "살펴", "살피", "살핀", "들여다", "훑어", "둘러보", "올려다", "내려다", "바라본", "바라보", "맡아", "맡는", "귀를 기울", "들어 본", "숨을 고", "둘러본"]
# Getting something ready for later: an edge rather than progress.
SETUP_CUES = ["둔다", "해 두", "해 놓", "돌려 둔", "놓아 둔"]
# Speech verbs strong enough to mean talk to the one person present, even unnamed.
SPEAK_CUES = ["얘기", "이야기", "묻는", "물어", "묻고", "말한다", "말을 건", "말을 꺼"]
PERSUADE_OBJECT = ["설득", "협박", "위협", "속이", "속여", "달래", "달랜", "으름장", "노려보"]
# Offers of help to a person: an attempt on the obstacle that person stands for, not a question.
OFFER_CUES = ["돕겠", "도와주겠", "도와 주겠", "거들겠", "거들어 주겠"]
CHOOSER = """당신은 한국어 TRPG의 입력 분류기입니다. 플레이어 문장이 하려는 첫 행동을 선택지에서 번호 하나로 고릅니다.
- 사람에게 말하거나 인사하거나 묻거나 부탁하는 문장은 그 사람과 '이야기한다'입니다.
- 어느 장소로 가는 문장은 그 장소로 '간다'입니다.
- 무엇을 보거나 살피거나 읽는 문장은 그것을 '살핀다'입니다.
- 물건을 집거나 챙기는 문장은 '집는다', 사람에게 물건을 주는 문장은 '건넨다'입니다.
- 밀기, 부수기, 훔치기, 숨기, 몰래 다가가기, 속이기 같은 직접 시도나, 맞는 선택지가 없는 문장은 '위 목록에 없는 행동'입니다.
번호만 답합니다."""
CHOOSER_PROMPT = "플레이어 문장: {text}\n선택지:\n{options}\n번호:"
PRESS_QUESTION = "플레이어는 {name}에게 한 말로 다음 장애물을 풀려고 합니까?"
PRESS_NONE = "장애물과 관계없는 말"
TOPIC_QUESTION = "플레이어는 {name}에게 무엇에 대해 말합니까?"
ATTITUDE_QUESTION = "플레이어는 {name}에게 어떤 태도로 말합니까?"
MEANING = {
    "overcome": "극복함: 더는 앞을 막지 않습니다",
    "partial": "한 걸음 나아감: 아직 {left}칸 남아 완전히 풀리지 않았습니다. 상대가 끝내 승낙하거나 결과물을 내주는 장면은 쓰지 않습니다",
    "danger": "시간이 흐르거나 경계가 높아짐: 장면의 배경으로만 드러냅니다",
    "gain": "이번 장면에서 당신 손에 들어옵니다. 당신이 내미는 것이 아니라 건네받거나 손에 넣는 것입니다",
    "learn": "이제 당신이 압니다",
}
CLAIM_QUESTION = "플레이어가 자신의 신분, 자격, 경력을 주장합니까?"
CLAIM_YES = "자신에 대해 주장함"
CLAIM_NO = "주장하지 않음"
TOUCH_QUESTION = "플레이어의 말이 {name}의 바람이나 두려움을 건드립니까?"
STANCE_QUESTION = "사실: {fact}\n플레이어의 말은 이 사실에 대해 어떻습니까?"
STANCES = {"agree": "사실과 같은 말을 함", "deny": "사실을 부정하거나 반대로 말함", "none": "이 사실과 관계없음"}

NARRATOR = """당신은 한국어 TRPG의 서술자입니다.
- 플레이어를 '당신'이라 부르고 합니다체로 씁니다.
- 3~6문장으로 씁니다. 마지막 문장은 지금 상황입니다. 선택지를 나열하지 않고, 인물의 대사로도 '이것 아니면 저것'을 묻지 않습니다.
- 플레이어의 감정이나 생각을 정하지 않습니다. 플레이어가 한 말과 행동에만 반응합니다.
- 동행 중인 인물은 늘 당신 곁에 있습니다.
- '당신'은 [플레이어 입력]과 [바뀐 것]에 있는 행동만 합니다. 손잡이를 돌리거나 물건을 꺼내는 등 다른 행동을 덧붙이지 않습니다.
- [바뀐 것]이 이번 장면의 중심입니다. 모두 장면 안에서 보여 주고, 바뀌지 않은 것을 바뀐 것처럼 쓰지 않습니다.
- 성공이면 플레이어가 원한 쪽으로 일이 나아가는 모습을, 실패면 일이 틀어지는 모습을 분명히 씁니다. 장애물은 '극복함'일 때만 완전히 풀린 모습으로 씁니다. [사실]의 장애물은 아직 앞을 막고 있으니 문이 열리거나 사람이 풀려나는 장면을 쓰지 않습니다. 아직 남은 장애물에서 상대가 약속하거나 명령하거나 물건을 내주는 장면은 쓰지 않습니다.
- [사실]에 없는 인물, 장소, 물건, 단서를 새로 만들지 않습니다.
- 실패는 단서 차단이 아니라 장면의 변화로 씁니다: 오해, 경계, 끼어듦, 말 끊김.
- 숫자, 규칙 용어, 주사위는 쓰지 않습니다.
- 인물이 장면 끝에 짧은 질문 하나를 던질 수 있습니다.
- [직전 장면의 끝]은 이미 보여 준 글입니다. 되풀이하지 않고, [플레이어 입력]에 반응하는 다음 순간부터 씁니다."""
PREVIOUS = "[직전 장면의 끝] (이미 보여 줌, 되풀이 금지)"
NAMING = ("이번 장면에서 새 상황 하나가 생겼습니다({kind}, {id}). 서술 끝에 따로 한 줄로 '@{id} 이름'을 적으십시오. "
          "이름은 그 곤란을 부르는 2~4단어이며, 장소나 인물 이름만 적지 않습니다.")
HINT = "동료나 장면이 '{name}'을(를) {approach}(으)로 풀 수 있다는 실마리를 한 문장으로 짚게 하십시오."
RECAP = "장이 끝났습니다. 서술 뒤에 다음 순간들을 되짚는 짧은 문단을 덧붙이십시오."
ENDING_SCENE = "이번 장면으로 이야기가 끝납니다. 아래 결말로 이어지도록 마무리하고, 인물이 질문하거나 다음 행동을 묻지 않습니다."
CHAPTER_OPENING = "새 장이 시작됩니다. 당신은 아직 아무것도 하지 않았습니다. 새 장소와 그곳의 인물, 앞을 막는 것만 보여 주십시오."
OPENING = "게임의 첫 장면입니다. 다음 전제로 장면을 여십시오."
FEEDBACK = {
    "contradicts": "앞 서술이 사실과 어긋났습니다. 사실에 맞게 다시 쓰십시오.",
    "invents": "앞 서술이 사실에 없는 인물이나 물건을 만들었습니다. 사실 안에서 다시 쓰십시오.",
    "missing": "앞 서술에 이번에 손에 들어오거나 잃은 물건이 보이지 않습니다: {names}. 그 이름을 그대로 써서 보여 주십시오.",
    "handed": "앞 서술에서 당신이 아직 지닌 물건을 건넸습니다: {names}. 당신은 이번에 그 물건을 건네지 않았습니다. 그 문장을 빼고 다시 쓰십시오.",
    "doubled": "앞 서술이 같은 문장을 두 번 썼습니다: {sentences}. 한 번만 쓰십시오.",
    "rules": "앞 서술에 숫자나 규칙 용어(3/8, 주사위, 판정, '성공입니다')가 나왔습니다. 장면 속 모습으로만 쓰십시오.",
    "you": "앞 서술이 플레이어를 '너', '나', '우리'로 불렀습니다. 대사 밖에서는 늘 '당신'(함께라면 '당신과 동행'처럼 이름)으로 쓰십시오.",
    "broken": "앞 서술에 깨진 글자가 있습니다. 다시 쓰십시오.",
    "pronoun": "앞 서술이 '그녀'라고 불렀습니다. 이 장면의 인물은 모두 '그'라고 부르십시오.",
    "alone": "앞 서술에 동행이 나왔지만 당신과 함께 다니는 인물은 없습니다. 동행을 빼고 다시 쓰십시오.",
    "meddled": "앞 서술에서 당신이 하지 않은 일을 했습니다: {names}을(를) 다룸. 당신은 플레이어 입력에 있는 행동만 합니다.",
    "early": "앞 서술이 아직 얻지 못한 것을 내주거나 약속했습니다: {names}. 장애물이 아직 남았으니 상대가 마음이 흔들리는 모습까지만 쓰십시오.",
    "foreign": "앞 서술에 한자나 외국 글자가 섞였습니다. 한국어로만 쓰십시오.",
    "plain": "앞 서술이 '-다'체로 쓰였습니다. 인물의 대사 밖 문장은 모두 '-습니다/-ㅂ니다'로 끝내십시오.",
    "long": "앞 서술이 너무 깁니다. 3~6문장으로 줄이십시오.",
    "repeats": "앞 서술이 직전 서술의 문장을 되풀이했습니다: {sentences}. 이 문장들을 쓰지 말고 플레이어 입력 뒤의 새 순간만 쓰십시오.",
}
CHECK_CONTRADICTS = "서술이 사실 목록과 어긋나는 내용을 담고 있습니까?"
CHECK_INVENTS = "서술이 사실 목록에 없는 인물, 장소, 물건, 단서를 새로 등장시킵니까?"
YES = "그렇다"
NO = "아니다"


def _has_final(word: str) -> tuple[bool, bool]:
    """(has final consonant, final is ㄹ) for the last Hangul syllable."""
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
    final, rieul = _has_final(word)
    if form == "으로":
        return "로" if not final or rieul else "으로"
    pairs = {"을": ("을", "를"), "이": ("이", "가"), "은": ("은", "는"), "와": ("과", "와")}
    with_final, without = pairs[form]
    return with_final if final else without


_HANGUL, _FINAL_N, _FINAL_B, _FINAL_BS, _FINAL_SS = 0xAC00, 4, 17, 18, 20
_PLAIN_END = re.compile(r"([가-힣])다(?=[.!]?(?:\s|$))")


def _polite_end(match: re.Match) -> str:
    """'내민다' -> '내밉니다', '잡는다' -> '잡습니다', '했다' -> '했습니다'; other endings stay as they are."""
    syllable = match[1]
    code = ord(syllable) - _HANGUL
    final = code % 28
    if syllable == "는":
        return "습니다"
    if final == _FINAL_N:
        return chr(ord(syllable) - _FINAL_N + _FINAL_B) + "니다"
    if final in (_FINAL_SS, _FINAL_BS):
        return syllable + "습니다"
    return match[0]


def polite(text: str, quoted: re.Pattern) -> str:
    """Turn sentence-final plain verbs outside quotes into 합니다체. Qwen sometimes writes a whole scene in
    -ㄴ다 form even after feedback; the common endings convert by rule."""
    out, last = [], 0
    for m in quoted.finditer(text):
        out += [_PLAIN_END.sub(_polite_end, text[last : m.start()]), m[0]]
        last = m.end()
    out.append(_PLAIN_END.sub(_polite_end, text[last:]))
    return "".join(out)


def fill(template: str, **values) -> str:
    """Format a template whose {을}/{이}/{은}/{와}/{으로} follow the preceding value."""
    out, i = "", 0
    while i < len(template):
        if template[i] == "{":
            end = template.index("}", i)
            key = template[i + 1 : end]
            if key in ("을", "이", "은", "와", "으로"):
                prev = out.rstrip()
                out += josa(prev, key)
            else:
                name, _, spec = key.partition(":")
                out += format(values[name], spec)
            i = end + 1
        else:
            out += template[i]
            i += 1
    return out
