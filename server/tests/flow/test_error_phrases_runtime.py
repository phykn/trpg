import json

from src.flow.error_phrases import humanize_runtime_error


def test_jsondecodeerror_mapped_to_korean_phrase():
    err = json.JSONDecodeError("empty answer", "", 0)
    assert humanize_runtime_error(err) == "행동을 해석하지 못했습니다. 다시 시도해 주세요."


def test_unknown_exception_falls_back_to_generic():
    class _Custom(Exception):
        pass

    assert humanize_runtime_error(_Custom("x")) == (
        "지금은 응답할 수 없습니다. 잠시 후 다시 시도해 주세요."
    )


def test_judgemalformed_still_mapped():
    from src.domain.errors import JudgeMalformed

    assert humanize_runtime_error(JudgeMalformed("x")) == (
        "행동을 해석하지 못했습니다. 다시 시도해 주세요."
    )
