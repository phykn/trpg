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
