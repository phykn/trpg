"""Korean particle (조사) selection: 이/가, 은/는, 을/를, 와/과, 으로/로 by 받침 of trailing syllable."""


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


def eu_ro(name: str) -> str:
    """Picks 으로/로: 으로 when 받침 (except ㄹ); 로 otherwise (no 받침 or ㄹ 받침)."""
    if not name:
        return "로"
    last = name[-1]
    if not ("가" <= last <= "힣"):
        return "로"
    jong = (ord(last) - 0xAC00) % 28
    # 0 = no jongseong, 8 = ㄹ — both take 로 instead of 으로.
    return "로" if jong in (0, 8) else "으로"
