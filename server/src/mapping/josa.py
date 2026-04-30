"""Korean particle (조사) selection helpers.

Picks 이/가, 은/는, 을/를, 와/과 based on the trailing syllable's final
consonant (받침). Non-Hangul tails (digits, ASCII, punctuation) default to
"no final consonant", which is good enough for our names — they're either
pure Hangul or single-loanword strings that read as having no final.
"""


def has_jongseong(name: str) -> bool:
    if not name:
        return False
    last = name[-1]
    if not ("가" <= last <= "힣"):
        return False
    return (ord(last) - 0xAC00) % 28 != 0


def i_ga(name: str) -> str:
    return "이" if has_jongseong(name) else "가"


def eun_neun(name: str) -> str:
    return "은" if has_jongseong(name) else "는"


def eul_reul(name: str) -> str:
    return "을" if has_jongseong(name) else "를"


def gwa_wa(name: str) -> str:
    return "과" if has_jongseong(name) else "와"
