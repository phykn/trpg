from src.flow.format import (
    format_recruit_success_log,
    format_recruit_failure_log,
    format_recruit_critical_failure_log,
    format_dismiss_log,
    format_dismiss_turn_log,
)


def test_recruit_success_log():
    assert format_recruit_success_log("에드릭") == "에드릭이 동료가 되었습니다."


def test_recruit_success_log_with_vowel_ending():
    assert format_recruit_success_log("리나") == "리나가 동료가 되었습니다."


def test_recruit_failure_log():
    assert format_recruit_failure_log("에드릭") == "에드릭이 제안을 거절합니다."


def test_recruit_failure_log_with_vowel_ending():
    assert format_recruit_failure_log("리나") == "리나가 제안을 거절합니다."


def test_recruit_critical_failure_log():
    assert format_recruit_critical_failure_log("에드릭") == "에드릭이 노골적으로 거절합니다."


def test_recruit_critical_failure_log_with_vowel_ending():
    assert format_recruit_critical_failure_log("리나") == "리나가 노골적으로 거절합니다."


def test_dismiss_log():
    assert format_dismiss_log("에드릭") == "에드릭이 일행에서 빠집니다."


def test_dismiss_log_with_vowel_ending():
    assert format_dismiss_log("리나") == "리나가 일행에서 빠집니다."


def test_dismiss_turn_log():
    assert format_dismiss_turn_log("에드릭") == "에드릭 동행 이탈"
