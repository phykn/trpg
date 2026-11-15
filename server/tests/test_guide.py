from src.guide import make_guide
from src.rules.act import act
from src.rules.state import start_state
from tests.test_act import CREW, PASS, STATS, STORY, ask, go, present


def guides(steps):
    state, said = start_state(STORY, 1), []
    for step in steps:
        action, heard = step if isinstance(step, tuple) else (step, None)
        result = act(STORY, state, action, heard)
        turn = {"action": action, "changes": result["changes"], "happened": result["happened"]}
        guide = make_guide(STORY, state, result["state"], turn)
        said.append(guide and guide["key"])
        state = result["state"]
    return said


def test_the_dm_shows_each_part_once_as_it_first_comes_up():
    assert guides([STATS, ask("밤"), ask("씨앗"), go("곡물 창고"), ask("그날 밤"), present(CREW, "한스"),
                   ask("그날 밤")]) == ["talk", "notebook", None, "lock", "present", "broke", None]


def test_the_dm_nudges_every_third_turn_without_a_new_line():
    assert guides([STATS, ask("밤"), PASS, PASS, PASS, PASS, PASS, PASS]) == [
        "talk", "notebook", None, None, "unvisited", None, None, "unvisited"]


def test_a_held_topic_is_named_once():
    keys = guides([STATS, ask("밤"), go("곡물 창고"), go("방앗간"), ask("새벽")])
    assert keys[-1] == "held"
