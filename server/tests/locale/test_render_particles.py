"""render() 조사 토큰 처리 + 변수 치환 단위 테스트."""

from src.locale.particles import has_jongseong
from src.locale.render import render


def test_no_tokens_returns_template_verbatim() -> None:
    """변수도 조사 토큰도 없으면 템플릿 그대로."""
    # error.runtime_generic = "지금은 응답할 수 없습니다. 잠시 후 다시 시도해 주세요."
    assert (
        render("error.runtime_generic", "ko")
        == "지금은 응답할 수 없습니다. 잠시 후 다시 시도해 주세요."
    )


def test_tier_lookup_unchanged() -> None:
    """1.1에서 동작하던 단순 lookup이 그대로."""
    assert render("tier.hard", "ko") == "어려움"


def test_has_jongseong_basic() -> None:
    """particles.has_jongseong 기본 회로."""
    assert has_jongseong("검") is True   # ㅁ 받침
    assert has_jongseong("칼") is True   # ㄹ 받침
    assert has_jongseong("나") is False  # 받침 없음
    assert has_jongseong("") is False    # 빈 문자열
    assert has_jongseong("Sword") is False  # 한글 아님


def test_token_walker_via_fixture(tmp_path, monkeypatch) -> None:
    """render의 token walker를 fixture catalog로 검증."""
    import sys
    render_mod = sys.modules["src.locale.render"]

    fixture = tmp_path / "fix.toml"
    fixture.write_text(
        '[fix.equip]\n'
        'ko = "{actor}{이/가} 「{item}」{을/를} 장비"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(render_mod, "_CATALOG_DIR", tmp_path)
    monkeypatch.setattr(render_mod, "_CACHE", {})

    # 받침 있는 actor + 받침 없는 item ("칼" — ㄹ 받침이라 을, "활" — ㄹ 받침이라 을)
    assert render("fix.equip", "ko", actor="검사", item="칼") == "검사가 「칼」을 장비"
    assert render("fix.equip", "ko", actor="레오", item="검") == "레오가 「검」을 장비"
    assert render("fix.equip", "ko", actor="검사", item="활") == "검사가 「활」을 장비"


def test_all_five_particles(tmp_path, monkeypatch) -> None:
    """이/가, 은/는, 을/를, 과/와, 으로/로 모두 받침 회로."""
    import sys
    render_mod = sys.modules["src.locale.render"]

    fixture = tmp_path / "fix.toml"
    fixture.write_text(
        '[fix.iga]\nko = "{x}{이/가} 갑니다"\n\n'
        '[fix.eunneun]\nko = "{x}{은/는} 떠납니다"\n\n'
        '[fix.eulreul]\nko = "{x}{을/를} 잡습니다"\n\n'
        '[fix.gwawa]\nko = "{x}{과/와} 만납니다"\n\n'
        '[fix.euro]\nko = "{x}{으로/로} 향합니다"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(render_mod, "_CATALOG_DIR", tmp_path)
    monkeypatch.setattr(render_mod, "_CACHE", {})

    # 받침 있음 (책 — ㄱ 받침)
    assert render("fix.iga", "ko", x="책") == "책이 갑니다"
    assert render("fix.eunneun", "ko", x="책") == "책은 떠납니다"
    assert render("fix.eulreul", "ko", x="책") == "책을 잡습니다"
    assert render("fix.gwawa", "ko", x="책") == "책과 만납니다"
    assert render("fix.euro", "ko", x="책") == "책으로 향합니다"
    # 받침 없음 (나무)
    assert render("fix.iga", "ko", x="나무") == "나무가 갑니다"
    assert render("fix.eunneun", "ko", x="나무") == "나무는 떠납니다"
    assert render("fix.eulreul", "ko", x="나무") == "나무를 잡습니다"
    assert render("fix.gwawa", "ko", x="나무") == "나무와 만납니다"
    assert render("fix.euro", "ko", x="나무") == "나무로 향합니다"
    # ㄹ 받침 — 으로/로 특수 (칼 → 칼로, not 칼으로)
    assert render("fix.euro", "ko", x="칼") == "칼로 향합니다"
