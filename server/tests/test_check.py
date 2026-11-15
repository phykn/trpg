from pathlib import Path

import pytest
import yaml
from src.story.check import check_story, load_stories, report_checks
from src.story.load import StoryError, StoryFile

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"


def story_data(folder):
    return yaml.safe_load((SCENARIOS / folder / "story.yaml").read_text(encoding="utf-8"))


def test_both_stories_pass_and_the_first_takes_three_cells(capsys):
    assert report_checks(SCENARIOS / "skeleton") == 0
    assert "알림  크기  막힘 3, 사람 3, 곳 3" in capsys.readouterr().out
    assert report_checks(SCENARIOS / "dawn") == 0
    out = capsys.readouterr().out
    assert "통과  시간 안에 닿는다  3칸 / 24칸\n" in out and "떨어짐" not in out and "알림" not in out


def drop_event_and_shrink(d):
    d["번진 일"] = []
    d["머리"]["칸 수"] = 4


@pytest.mark.parametrize("folder, edit, name, detail", [
    ("dawn", lambda d: d["볼 것"]["여관 나무패"].pop("보여 주는 사실"), "거짓말의 길",
     "거짓말 브람.징수관: 곳이 하나뿐이다 (약초꾼 오두막)"),
    ("dawn", lambda d: [d["볼 것"][t].update({"성질": []}) for t in ("쇠꼬챙이", "약초 칼")], "꺼림과 잠김의 길",
     "잠김 장부 궤짝"),
    ("dawn", lambda d: d["볼 것"]["가방의 쪽지"].pop("보여 주는 사실"), "진실의 길",
     "왜 빼돌린 세금: 단서가 하나뿐이다 (볼 것 장부 두 벌)"),
    ("dawn", lambda d: [d["볼 것"]["검푸른 입술"].pop("보여 주는 사실"),
                        d["사람"]["넬"]["화제"]["시신"]["풀린 뒤"].pop("보여 주는 사실"),
                        d["사람"]["넬"]["화제"]["독미나리"]["참말"].pop("보여 주는 사실")], "주사위 없이 닿는다", "어떻게"),
    ("dawn", drop_event_and_shrink, "시간 안에 닿는다", "3칸 / 4칸"),
    ("dawn", lambda d: d["번진 일"][0]["일"].append({"없어진다": "가방의 쪽지"}), "번진 뒤에도 닿는다",
     "번진 일 10칸째: 왜"),
    ("skeleton", lambda d: d["사람"]["오토"].update({"있는 곳": "곡물 창고"}), "첫걸음", "1"),
    ("skeleton", lambda d: d["곳"].update({"외딴 집": {"모습": "아무도 살지 않는 집이다."}}), "닿지 않는 것", "곳 외딴 집"),
])
def test_each_broken_copy_fails_its_check(folder, edit, name, detail):
    data = story_data(folder)
    edit(data)
    results = {n: (v, d) for v, n, d in check_story(StoryFile.model_validate(data))}
    assert results[name][0] == "떨어짐" and detail in results[name][1]


def test_alerts_name_long_lines_and_necks():
    data = story_data("skeleton")
    data["사람"]["오토"]["화제"]["씨앗"]["참말"] = "하나다. 둘이다. 셋이다."
    data["볼 것"]["빚 문서"].pop("보여 주는 사실")
    alerts = [(n, d) for v, n, d in check_story(StoryFile.model_validate(data)) if v == "알림"]
    assert ("긴 할 말", "말 오토.씨앗.참말") in alerts and ("한 막힘의 목", "거짓말 한스.그날 밤") in alerts


def test_loading_stops_at_a_broken_story(tmp_path):
    assert sorted(load_stories(SCENARIOS)) == ["arena", "dawn", "skeleton"]
    data = story_data("skeleton")
    data["곳"]["외딴 집"] = {"모습": "x"}
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "story.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(StoryError, match="닿지 않는 것  곳 외딴 집"):
        load_stories(tmp_path)
