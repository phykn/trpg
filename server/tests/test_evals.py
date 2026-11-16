import asyncio
from pathlib import Path

import pytest
import yaml
from src.story.evals import grade, read_cases, run_evals, summarize
from src.story.load import StoryError, load_story

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"


class Echo:
    async def read(self, story, state, text, last=None):
        if last:   # a case paired with what the person said just before reaches the interpreter with it
            return {"kind": "topics", "topics": ["씨앗"]} if "씨앗" in last else {"kind": "chat"}
        return {"kind": "topics", "topics": ["밤"]} if state["partner"] == "오토" else {"kind": "chat"}


def test_every_story_has_cases_and_the_report_grades_them():
    for folder in ("dawn", "skeleton"):
        assert len(read_cases(SCENARIOS / folder, load_story(SCENARIOS / folder))) >= 10
    report, passed = summarize(asyncio.run(run_evals(SCENARIOS / "skeleton", Echo())))
    assert not passed and "틀린 화제 4" in report
    assert grade("밤 + 씨앗", {"kind": "topics", "topics": ["씨앗"]}) == "모자람"
    assert grade("넘김", {"kind": "unsure", "topics": ["밤", "씨앗"]}) == "되물음"
    pressed = {"kind": "action", "method": "press", "target": None}
    assert grade("행동 몰아세운다", pressed) == "맞힘" and grade("행동 달랜다", pressed) == "틀린 행동"
    assert grade("행동 잠김", {"kind": "action", "method": "sneak", "target": "잠김 잠긴 뒷문"}) == "맞힘"
    assert grade("행동 속인다", {"kind": "chat"}) == "놓침" and grade("밤", pressed) == "행동으로 읽음"
    assert grade("행동 속인다", {"kind": "chat", "guess": {"method": "trick", "target": None}}) == "맞힘"


def test_an_unknown_expectation_is_refused(tmp_path):
    (tmp_path / "story.yaml").write_text((SCENARIOS / "skeleton" / "story.yaml").read_text(encoding="utf-8"),
                                         encoding="utf-8")
    (tmp_path / "evals.yaml").write_text(yaml.safe_dump({"사람 오토": {"달": ["달이 밝습니까?"]}}, allow_unicode=True),
                                         encoding="utf-8")
    with pytest.raises(StoryError, match="달"):
        read_cases(tmp_path, load_story(tmp_path))
