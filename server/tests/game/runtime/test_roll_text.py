from types import SimpleNamespace

from src.game.domain.action import Action
from src.game.runtime.roll.text import prepare_roll_narration_text


def test_successful_perceive_roll_removes_no_clue_contradiction():
    resolved = SimpleNamespace(
        action=Action(verb="perceive"),
        outcome="success",
        runtime=SimpleNamespace(
            progress=SimpleNamespace(locale="ko"),
            graph=SimpleNamespace(nodes={}),
            content={},
        ),
        roll_entry=SimpleNamespace(check="지력 판정"),
        completed_quest_ids=[],
        pending={},
    )

    text = prepare_roll_narration_text(
        resolved,
        "특별한 의미 있는 흔적은 보이지 않습니다. 엘리가 고개를 갸웃합니다.",
        ensure_resolution=True,
    )

    assert "의미 있는 단서를 확인합니다" in text
    assert "특별한 의미 있는 흔적은 보이지 않습니다" not in text
    assert "엘리가 고개를 갸웃합니다." in text
