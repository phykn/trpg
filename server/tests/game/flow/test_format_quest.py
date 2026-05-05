"""Quest end-state log line builders: success card with rewards, fail card with reason."""

from src.game.flow.format import format_quest_fail_log, format_quest_success_log


def test_success_with_all_rewards():
    text = format_quest_success_log(
        "촌장의 부탁", exp=80, gold=40, items=["회복약", "철검"]
    )
    assert text == "퀘스트 성공: 촌장의 부탁 — +EXP 80 · +GOLD 40 · 회복약 / 철검"


def test_success_with_items_only():
    text = format_quest_success_log("유물 회수", exp=0, gold=0, items=["고대 두루마리"])
    assert text == "퀘스트 성공: 유물 회수 — 고대 두루마리"


def test_success_with_no_rewards():
    text = format_quest_success_log("전언 전달", exp=0, gold=0, items=[])
    assert text == "퀘스트 성공: 전언 전달"


def test_fail_giver_dead():
    text = format_quest_fail_log("촌장의 부탁", "의뢰자 사망")
    assert text == "퀘스트 실패: 촌장의 부탁 — 의뢰자 사망"


def test_fail_abandoned():
    text = format_quest_fail_log("도적 토벌", "의뢰 포기")
    assert text == "퀘스트 실패: 도적 토벌 — 의뢰 포기"
