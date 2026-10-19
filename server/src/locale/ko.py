"""Engine-owned Korean text (engine.md 1). Story text lives in the scenario, never here."""

from __future__ import annotations

APPROACHES = {"force": "힘", "finesse": "솜씨", "wits": "꾀", "charm": "매력"}
APPROACH_HINT = {
    "force": "힘으로 밀어붙이거나 버팁니다",
    "finesse": "손재주, 몸놀림, 몰래 움직임",
    "wits": "관찰, 계획, 꾀와 속임수",
    "charm": "말로 설득하거나 마음을 움직입니다",
}
TONES = {"polite": "정중하게", "friendly": "친근하게", "plead": "간청하며", "threaten": "위협하며", "deceive": "속여서"}
STRAINS = {"natural": "자연스럽게", "forced": "무리해서"}
RISKS = {"low": "낮음", "normal": "보통", "high": "높음"}
WEIGHTS = {"light": "가벼운 대가", "heavy": "무거운 대가"}
RESULTS = {"success": "성공", "mixed": "대가 있는 성공", "fail": "실패", "none": "", "blocked": "막힘"}
SHEET = {"beats": "박자", "wounds": "상처", "growth": "성장"}

# The engine's complications (rule.md 3.3).
COMPLICATIONS = {"engine.snag": "꼬임", "engine.beat": "지체", "engine.wound": "다침", "engine.end": "끊긴 장면"}
# Default tag names: by kind, and the "@" keys the rules give to the tags they place.
TAG_DEFAULT = {"edge": "유리함", "snag": "불리함"}
TAG_KEYS = {"@suspicion": "의심", "@broken_promise": "약속을 어김", "@scar": "흉터"}

# How a person regards the player, by trust; fear above this shows instead.
TRUST_WORDS = {-3: "적대", -2: "불신", -1: "경계", 0: "무덤덤", 1: "호의", 2: "신뢰", 3: "유대"}
FEARFUL, FEAR_WORD = 2, "두려움"

# Action names λ (engine.md 1). {을}/{이}/{은}/{와}/{으로} follow the value before them.
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
    "pay": "{name}",
    "grow": "{approach} {before}→{after}",
    "grow_trait": "특성 바꾸기: {old} → {new}",
    "grow_scar": "흉터 지우기: {name}",
}
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
    "due": "먼저 대가를 고르세요.",
    "text": "아직 문장을 읽을 수 없습니다. 버튼을 눌러 주세요.",
}
ERRORS = {
    "missing": "저장된 게임을 찾을 수 없습니다.",
    "incompatible": "incompatible",
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
