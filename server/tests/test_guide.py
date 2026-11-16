from src.guide import make_guide
from src.rules.act import act
from src.rules.state import start_state
from tests.test_act import CREW, LOOK, PASS, STATS, STORY, ask, go, present


def guides(steps, seed=1):
    state, said, past = start_state(STORY, seed), [], []
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
                   go("곡물 창고")]) == ["open 오토", None, None, None, None, "around 광장", None]


def test_the_dm_remarks_on_someone_not_yet_talked_to_on_arrival():
    assert guides([STATS, ask("밤"), ask("씨앗"), PASS, go("곡물 창고")])[-1] == "meet 한스"


def test_the_dm_nudges_after_a_while_without_a_new_line():
    assert guides([STATS, ask("밤"), *[PASS] * 12]) == [
        "open 오토", None, None, None, None, "around 광장", None, None, None, "unvisited 곡물 창고", None, None, None,
        "unvisited 방앗간"]


def test_the_first_held_topic_gets_a_remark():
    chat = ({"do": "ask"}, {"kind": "chat"})
    assert guides([STATS, ask("밤"), go("곡물 창고"), LOOK, go("방앗간"), chat, chat, chat, ask("새벽")])[-1] == "held 리사"


def test_someone_who_held_back_is_not_met_again():
    keys = guides([STATS, ask("밤"), go("곡물 창고"), LOOK, go("방앗간"), ask("새벽"), PASS, PASS, PASS, PASS, PASS,
                   go("광장"), go("방앗간")])
    assert keys.count("meet 리사") == 1


def test_a_roll_that_shows_a_lie_gets_a_remark():
    bet = {"do": "bet", "target": "말 한스.그날 밤.거짓말", "method": "press"}   # seed 2 wins it
    assert guides([STATS, ask("밤"), go("곡물 창고"), ask("그날 밤"), bet], seed=2)[-1] == "doubt 한스"


def test_a_stuck_nudge_is_not_said_twice_running():
    assert [k for k in guides([STATS, ask("밤"), *[PASS] * 30]) if k] == [
        "open 오토", "around 광장", "unvisited 곡물 창고", "unvisited 방앗간", "ask 오토", "look"]


def test_arriving_somewhere_not_looked_around_gets_a_remark_once():
    back = [PASS, PASS, PASS]
    assert guides([STATS, ask("밤"), PASS, PASS, go("곡물 창고"), go("광장"), *back, PASS, go("곡물 창고"), *back,
                   go("광장"), *back, go("곡물 창고")]) == [
        "open 오토", None, None, None, "meet 한스", None, None, None, None, "around 광장", None, None, None,
        "around 곡물 창고", None, None, None, "unvisited 방앗간", None]
