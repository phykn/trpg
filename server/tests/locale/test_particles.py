from src.locale.particles import (
    eu_ro,
    eul_reul,
    eun_neun,
    gwa_wa,
    has_jongseong,
    i_ga,
)


def test_has_jongseong():
    assert has_jongseong("말") is True
    assert has_jongseong("나") is False
    assert has_jongseong("") is False
    assert has_jongseong("a") is False


def test_i_ga():
    assert i_ga("말") == "이"
    assert i_ga("나") == "가"


def test_eun_neun():
    assert eun_neun("말") == "은"
    assert eun_neun("나") == "는"


def test_eul_reul():
    assert eul_reul("말") == "을"
    assert eul_reul("나") == "를"


def test_gwa_wa():
    assert gwa_wa("말") == "과"
    assert gwa_wa("나") == "와"


def test_eu_ro():
    assert eu_ro("학교") == "로"
    assert eu_ro("말") == "로"
    assert eu_ro("집") == "으로"
    assert eu_ro("") == "로"
    assert eu_ro("abc") == "로"
