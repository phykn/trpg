from pathlib import Path

import pytest
import yaml
from src.rules.act import does_fit
from src.story.load import StoryError, StoryFile, find_missing, load_story, read_story

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
SKELETON = SCENARIOS / "skeleton"


def skeleton_data():
    return yaml.safe_load((SKELETON / "story.yaml").read_text(encoding="utf-8"))


def write_story(folder, data):
    folder.mkdir(exist_ok=True)
    (folder / "story.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return folder


def test_skeleton_compiles_addresses_and_reverse_indexes():
    story = load_story(SKELETON)
    assert story.links["방앗간"] == ["광장"]
    assert story.shows["노름빚"] == ["볼 것 빚 문서", "말 한스.그날 밤.깨진 뒤"]
    assert story.holders["납작하고 단단하다"] == ["볼 것 쇠 지렛대"]
    tracks = story.lines["볼 것 수레 자국"]
    assert (tracks.place, tracks.lock) == ("곡물 창고", "잠김 잠긴 뒷문")
    assert story.lines["말 오토.밤.참말"].tells == ["사람 한스", "곳 방앗간"]
    assert story.blocks["거짓말 한스.그날 밤"].opens == ["말 한스.그날 밤.깨진 뒤"]
    assert story.head.clock.start == 4 * 60


def test_the_mark_changes_with_one_letter(tmp_path):
    data = skeleton_data()
    data["머리"]["제목"] += "!"
    assert load_story(write_story(tmp_path / "copy", data)).mark != load_story(SKELETON).mark


def test_each_pointer_to_nothing_is_named():
    data = skeleton_data()
    data["볼 것"]["꺼진 등잔"]["보여 주는 사실"] = "없는 사실"
    data["사람"]["리사"]["화제"]["새벽"]["바라는 것"] = "없는 성질"
    data["곳"]["방앗간"]["나오는 조건"] = "말 한스.그날 밤.거짓말"
    data["번진 일"][0]["막는 조건"] = "꺼림 한스.그날 밤"
    del data["볼 것"]["빈 자루 더미"]
    assert find_missing(StoryFile.model_validate(data)) == [
        "곳 방앗간의 나오는 조건: 말 한스.그날 밤.거짓말 (거짓말 갈래)",
        "볼 것 꺼진 등잔의 보여 주는 사실: 없는 사실",
        "볼 것 빚 문서의 나오는 조건: 볼 것 빈 자루 더미",
        "화제 리사.새벽의 바라는 것: 없는 성질",
        "번진 일 5칸째의 막는 조건: 꺼림 한스.그날 밤",
    ]


@pytest.mark.parametrize("edit, error", [
    (lambda d: d["사람"]["리사"]["화제"]["새벽"].pop("실마리"), "takes exactly 바라는 것, 실마리, 풀린 뒤"),
    (lambda d: d["사람"]["한스"]["화제"]["그날 밤"].update({"거짓말": {"말": "x", "보여 주는 사실": "노름빚"}}),
     "거짓말 shows no fact"),
    (lambda d: d["사실"].update({"광장": "x"}), "광장 names both 사실 and 곳"),
    (lambda d: d["번진 일"][0].pop("조짐"), "조짐 is required"),
    (lambda d: d["볼 것"]["꺼진 등잔"].update({"물건인가": "yes"}), "write 예 or 아니오"),
    (lambda d: d["사람"]["리사"].update({"하는 일": {1: "x"}}), "리사의 하는 일: .* must start at 0"),
    (lambda d: d["사람"]["리사"].update({"하는 일": {0: "x", 9: "y"}}), "리사의 하는 일: .* end by 8"),
])
def test_shape_errors_stop_reading(tmp_path, edit, error):
    data = skeleton_data()
    edit(data)
    with pytest.raises(StoryError, match=error):
        read_story(write_story(tmp_path / "copy", data))


def test_a_key_written_twice_stops_reading(tmp_path):
    text = (SKELETON / "story.yaml").read_text(encoding="utf-8").replace("  방앗간:\n", "  광장:\n", 1)
    (tmp_path / "story.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(StoryError, match="appears twice"):
        read_story(tmp_path)


def test_a_lie_can_fall_to_any_of_several_facts():
    dawn = load_story(SCENARIOS / "dawn")
    block = dawn.blocks["거짓말 고드릭.그 뒤의 일"]
    assert block.wants == ("밤에 나간 수레", "옮겨진 시신")
    assert does_fit(dawn, "볼 것 마른 장화", block) and not does_fit(dawn, "볼 것 제단의 초", block)


def test_a_story_without_소개_still_reads_for_old_saves_but_fails_the_check():
    from src.story.check import check_story
    data = skeleton_data()
    for section in ("사람", "볼 것"):
        for entry in data[section].values():
            entry.pop("소개", None)
    results, _ = check_story(StoryFile.model_validate(data))
    assert ("떨어짐", "소개", "사람 오토; 사람 한스; 사람 리사; 볼 것 쇠 지렛대") in results


def test_close_people_go_both_ways_and_blocks_carry_their_unlocking_impression():
    story = load_story(SKELETON)
    assert story.close == {"오토": ["한스"], "한스": ["오토"], "리사": []}
    assert (story.blocks["꺼림 리사.새벽"].unlock, story.blocks["꺼림 리사.새벽"].unlock_count) == ("위로", 1)
    assert story.blocks["거짓말 한스.그날 밤"].unlock_count == 2


def test_impression_names_are_checked():
    from src.story.check import check_story
    data = skeleton_data()
    data["사람"]["리사"]["인상"] = {"다정": "겹친다"}
    data["사람"]["리사"]["화제"]["새벽"]["풀리는 인상"] = "없는 인상"
    failed = [d for v, n, d in check_story(StoryFile.model_validate(data))[0] if n == "인상의 이름"]
    assert failed == ["사람 리사의 인상: 다정; 꺼림 리사.새벽의 풀리는 인상: 없는 인상"]
    data["사람"]["오토"]["화제"]["밤"]["풀리는 인상"] = "위로"
    with pytest.raises(ValueError, match="풀리는 인상 is for"):
        StoryFile.model_validate(data)
