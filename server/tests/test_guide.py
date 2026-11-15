from src.guide import make_guide
from src.rules.act import act
from src.rules.state import start_state
from tests.test_act import CREW, PASS, STATS, STORY, ask, go, present


def guides(steps):
    state, said, past = start_state(STORY, 1), [], []
    for step in steps:
        action, heard = step if isinstance(step, tuple) else (step, None)
        result = act(STORY, state, action, heard)
        turn = {"action": action, "changes": result["changes"], "happened": result["happened"]}
        guide = make_guide(STORY, state, result["state"], turn, past)
        said.append(guide and guide["key"] + (f" {guide['name']}" if guide.get("name") else ""))
        past += [{**guide, "turn": result["state"]["turn"]}] if guide else []
        state = result["state"]
    return said


def test_the_dm_opens_and_then_waits_before_speaking_again():
    assert guides([STATS, ask("밤"), go("곡물 창고"), ask("그날 밤"), present(CREW, "한스"), go("광장"),
                   go("곡물 창고")]) == ["open 오토", None, None, None, None, None, None]


def test_the_dm_remarks_on_someone_not_yet_talked_to_on_arrival():
    assert guides([STATS, ask("밤"), ask("씨앗"), PASS, go("곡물 창고")])[-1] == "meet 한스"


def test_the_dm_nudges_after_a_while_without_a_new_line():
    assert guides([STATS, ask("밤"), PASS, PASS, PASS, PASS, PASS, PASS, PASS, PASS, PASS]) == [
        "open 오토", None, None, None, None, "unvisited 곡물 창고", None, None, None, "unvisited 방앗간", None]


def test_the_first_held_topic_gets_a_remark():
    assert guides([STATS, ask("밤"), go("곡물 창고"), go("방앗간"), PASS, ask("새벽")])[-1] == "held 리사"


def test_someone_who_held_back_is_not_met_again():
    keys = guides([STATS, ask("밤"), go("곡물 창고"), go("방앗간"), ask("새벽"), PASS, PASS, PASS, PASS, PASS,
                   go("광장"), go("방앗간")])
    assert "meet 리사" not in keys
