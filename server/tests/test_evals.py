import asyncio
from pathlib import Path

import pytest
import yaml
from src.story.evals import grade, read_cases, run_evals, summarize
from src.story.load import StoryError, load_story

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"


class Echo:
    async def read(self, story, state, text):
        return {"kind": "topics", "topics": ["밤"]} if state["partner"] == "오토" else {"kind": "chat"}


def test_every_story_has_cases_and_the_report_grades_them():
    for folder in ("dawn", "skeleton"):
        assert len(read_cases(SCENARIOS / folder, load_story(SCENARIOS / folder))) >= 10
    report, passed = summarize(asyncio.run(run_evals(SCENARIOS / "skeleton", Echo())))
    assert not passed and "틀린 화제 4" in report
    assert grade("밤 + 씨앗", {"kind": "topics", "topics": ["씨앗"]}) == "모자람"
    assert grade("넘김", {"kind": "unsure", "topics": ["밤", "씨앗"]}) == "되물음"


def test_an_unknown_expectation_is_refused(tmp_path):
    (tmp_path / "story.yaml").write_text((SCENARIOS / "skeleton" / "story.yaml").read_text(encoding="utf-8"),
                                         encoding="utf-8")
    (tmp_path / "evals.yaml").write_text(yaml.safe_dump({"사람 오토": {"달": ["달이 밝습니까?"]}}, allow_unicode=True),
                                         encoding="utf-8")
    with pytest.raises(StoryError, match="달"):
        read_cases(tmp_path, load_story(tmp_path))
