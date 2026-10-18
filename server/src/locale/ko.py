"""Engine-owned Korean text. Story text lives in the scenario, never here."""

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
RISKS = {"low": "낮음: 실패해도 크게 다치지 않음", "normal": "보통", "high": "높음: 실패하면 크게 잃음"}
RISK_NAMES = {"low": "낮음", "normal": "보통", "high": "높음"}
PLAUSIBLE = {
    "natural": "이 장면에서 자연스럽게 할 수 있음",
    "stretch": "할 수는 있지만 무리가 큼",
    "impossible": "이 장면에서 할 수 없음",
}
PURPOSES = {
    "overcome": "장애물을 직접 넘거나 해결하려 함",
    "setup": "나중에 쓸 유리한 상황을 만들려 함",
    "clear": "불리한 상황을 없애려 함",
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
    "grow_approach": "{name} +1",
    "grow_trait": "특성 바꾸기: {old} → {name}",
}

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

STEP_QUESTION = "플레이어 입력에 담긴 {n}번째 행동은 무엇입니까? 행동이 {n}개보다 적으면 none을 고르십시오."
IMPROVISE = "목록에 맞는 행동이 없고 플레이어가 새로운 방법을 시도함"
NONE_STEP = "행동이 없음"
TARGET_QUESTION = "{n}번째 행동이 노리는 장애물이나 없애려는 불리한 상황은 무엇입니까?"
PURPOSE_QUESTION = "{n}번째 행동의 목적은 무엇입니까?"
APPROACH_QUESTION = "{n}번째 행동은 어떤 방식에 가장 가깝습니까?"
RISK_QUESTION = "{n}번째 행동이 실패하면 얼마나 위험합니까?"
PLAUSIBLE_QUESTION = "{n}번째 행동이 이 장면에서 말이 됩니까?"
CHECK_QUESTION = "{n}번째 행동은 실패할 수 있고 그 결과가 중요합니까?"
CHECK_YES = "실패할 수 있고 결과가 중요함"
CHECK_NO = "그냥 하면 되는 사소한 행동"
USES_TAG_QUESTION = "{n}번째 행동이 장면의 유리한 상황 중 하나를 이용합니까?"
USES_THING_QUESTION = "{n}번째 행동이 지닌 물건, 아는 사실, 기술 중 하나를 이용합니까?"
USES_TRAIT_QUESTION = "{n}번째 행동이 플레이어의 특성을 살립니까?"
TOPIC_QUESTION = "플레이어는 {name}에게 무엇에 대해 말합니까?"
ATTITUDE_QUESTION = "플레이어는 {name}에게 어떤 태도로 말합니까?"
CLAIM_QUESTION = "플레이어가 자신의 신분, 자격, 경력을 주장합니까?"
CLAIM_YES = "자신에 대해 주장함"
CLAIM_NO = "주장하지 않음"
TOUCH_QUESTION = "플레이어의 말이 {name}의 바람이나 두려움을 건드립니까?"
CONTRADICTS_QUESTION = "플레이어의 말이 {name}이(가) 아는 다음 사실 중 하나와 어긋납니까?"
WHY_NOT_QUESTION = "이 행동을 할 수 없다면 이유는 무엇입니까?"
WHY_NOT_OPTIONS = {
    "absent": "장면에 그런 대상이 없음",
    "beyond": "플레이어의 능력 밖임",
    "rule": "세계의 규칙에 어긋남",
}

NARRATOR = """당신은 한국어 TRPG의 서술자입니다.
- 플레이어를 '당신'이라 부르고 합니다체로 씁니다.
- 3~6문장으로 씁니다. 마지막 문장은 지금 상황입니다. 선택지를 나열하지 않습니다.
- 플레이어의 감정이나 생각을 정하지 않습니다. 플레이어가 한 말과 행동에만 반응합니다.
- [바뀐 것]은 모두 장면 안에서 보여 주고, 바뀌지 않은 것을 바뀐 것처럼 쓰지 않습니다.
- [사실]에 없는 인물, 장소, 물건, 단서를 새로 만들지 않습니다.
- 실패는 단서 차단이 아니라 장면의 변화로 씁니다: 오해, 경계, 끼어듦, 말 끊김.
- 숫자, 규칙 용어, 주사위는 쓰지 않습니다.
- 인물이 장면 끝에 짧은 질문 하나를 던질 수 있습니다."""
NAMING = "새 상황 {id}({kind}, 대상: {target})의 짧은 이름을 서술 끝에 '@{id} 이름' 한 줄로 적으십시오."
HINT = "동료나 장면이 '{name}'을(를) {approach}(으)로 풀 수 있다는 실마리를 한 문장으로 짚게 하십시오."
RECAP = "장이 끝났습니다. 서술 뒤에 다음 순간들을 되짚는 짧은 문단을 덧붙이십시오."
OPENING = "게임의 첫 장면입니다. 다음 전제로 장면을 여십시오."
FEEDBACK = {
    "contradicts": "앞 서술이 사실과 어긋났습니다. 사실에 맞게 다시 쓰십시오.",
    "invents": "앞 서술이 사실에 없는 인물이나 물건을 만들었습니다. 사실 안에서 다시 쓰십시오.",
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
