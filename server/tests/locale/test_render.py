import pytest
from src.locale.render import render


def test_hit_ko():
    assert (
        render("error.llm_unavailable", "ko")
        == "이야기꾼이 잠시 길을 잃었습니다. 다시 시도해 주세요."
    )


def test_hit_en():
    assert (
        render("error.llm_unavailable", "en")
        == "The storyteller is briefly lost. Please try again."
    )


def test_key_miss_raises():
    with pytest.raises(KeyError):
        render("error.does_not_exist", "ko")


def test_locale_miss_raises():
    with pytest.raises(KeyError):
        render("error.llm_unavailable", "ja")


def test_no_vars_no_kwargs_call():
    assert (
        render("error.runtime_generic", "ko")
        == "지금은 응답할 수 없습니다. 잠시 후 다시 시도해 주세요."
    )


def test_render_reloads_catalog_when_file_changes(tmp_path, monkeypatch):
    import os
    import sys

    render_mod = sys.modules["src.locale.render"]
    fixture = tmp_path / "fix.toml"
    fixture.write_text('[fix.message]\nko = "처음"\nen = "first"\n', encoding="utf-8")
    os.utime(fixture, ns=(1_000_000_000, 1_000_000_000))
    monkeypatch.setattr(render_mod, "_CATALOG_DIR", tmp_path)
    monkeypatch.setattr(render_mod, "_CACHE", {})
    monkeypatch.setattr(render_mod, "_CACHE_MTIME", {})

    assert render("fix.message", "ko") == "처음"

    fixture.write_text('[fix.message]\nko = "변경"\nen = "changed"\n', encoding="utf-8")
    os.utime(fixture, ns=(2_000_000_000, 2_000_000_000))

    assert render("fix.message", "ko") == "변경"
