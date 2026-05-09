from src.game.flow.format import (
    format_dismiss_log,
    format_dismiss_turn_log,
    format_recruit_log,
    format_recruit_turn_log,
)


def test_recruit_success_log():
    assert format_recruit_log("에드릭", "success") == "에드릭이 동료가 되었습니다."


def test_recruit_success_log_with_vowel_ending():
    assert format_recruit_log("리나", "success") == "리나가 동료가 되었습니다."


def test_recruit_failure_log():
    assert format_recruit_log("에드릭", "failure") == "에드릭이 제안을 거절합니다."


def test_recruit_failure_log_with_vowel_ending():
    assert format_recruit_log("리나", "failure") == "리나가 제안을 거절합니다."


def test_recruit_critical_failure_log():
    assert (
        format_recruit_log("에드릭", "critical_failure")
        == "에드릭이 노골적으로 거절합니다."
    )


def test_recruit_critical_failure_log_with_vowel_ending():
    assert (
        format_recruit_log("리나", "critical_failure")
        == "리나가 노골적으로 거절합니다."
    )


def test_dismiss_log():
    assert format_dismiss_log("에드릭") == "에드릭이 일행에서 빠집니다."


def test_dismiss_log_with_vowel_ending():
    assert format_dismiss_log("리나") == "리나가 일행에서 빠집니다."


def test_dismiss_turn_log():
    assert format_dismiss_turn_log("에드릭") == "에드릭 동행 이탈"


def test_recruit_success_turn_log():
    assert format_recruit_turn_log("에드릭", "success") == "에드릭 동료 합류"


def test_recruit_failure_turn_log():
    assert format_recruit_turn_log("에드릭", "failure") == "에드릭 동료 영입 실패"


def test_recruit_critical_failure_turn_log_collapses_to_failure():
    assert (
        format_recruit_turn_log("에드릭", "critical_failure")
        == "에드릭 동료 영입 실패"
    )
