from src.rules.act import act
from src.rules.guide import is_ready, make_guide
from src.rules.state import start_state
from tests.test_act import CREW, LOOK, PASS, STATS, STORY, ask, go, present, said


def guides(steps, seed=1):
    state, said, past = start_state(STORY, seed), [], []
    for step in steps:
        action, heard = step if isinstance(step, tuple) else (step, None)
        result = act(STORY, state, action, heard)
        turn = {"action": action, "changes": result["changes"], "happened": result["happened"], "talk": result["talk"]}
        guide = make_guide(STORY, state, result["state"], turn, past)
        said.append(guide and guide["key"] + (f" {guide['name']}" if guide.get("name") else ""))
        past += [{**guide, "turn": result["state"]["turn"]}] if guide else []
        state = result["state"]
    return said


def test_the_opener_speaks_first_so_the_dm_waits_before_speaking():
    assert guides([STATS, ask("밤"), go("곡물 창고"), ask("그날 밤"), present(CREW, "한스"), go("광장"),
                   go("곡물 창고")]) == [None, None, None, None, None, "around 광장", None]


def test_the_dm_remarks_on_someone_not_yet_talked_to_on_arrival():
    assert guides([STATS, ask("밤"), ask("씨앗"), PASS, go("곡물 창고")])[-1] == "meet 한스"


def test_the_dm_nudges_after_four_idle_turns_and_helps_from_the_eighth():
    assert guides([STATS, ask("밤"), *[PASS] * 12]) == [
        None, None, None, None, None, "around 광장", None, None, None, "hint_topic 오토", None, None, None, "hint_line"]


def test_a_held_topic_gets_a_gesture():
    assert guides([STATS, ask("밤"), go("곡물 창고"), LOOK, go("방앗간"), LOOK, LOOK, LOOK, ask("새벽")])[-1] == "held 리사"


def test_someone_who_held_back_is_not_met_again():
    keys = guides([STATS, ask("밤"), go("곡물 창고"), LOOK, go("방앗간"), ask("새벽"), PASS, PASS, PASS, PASS, PASS,
                   go("광장"), go("방앗간")])
    assert keys.count("meet 리사") == 1


def test_a_roll_that_shows_a_lie_gets_a_remark():
    bet = {"do": "bet", "target": "말 한스.그날 밤.거짓말", "method": "press"}   # seed 2 wins it
    assert guides([STATS, ask("밤"), go("곡물 창고"), ask("그날 밤"), bet], seed=2)[-1] == "doubt 한스"


def test_a_stuck_nudge_is_not_said_twice_running():
    # Each help once and in order, then the nudges again; no more than that.
    assert [k for k in guides([STATS, ask("밤"), *[PASS] * 30]) if k] == [
        "around 광장", "hint_topic 오토", "hint_line", "hint_place 곡물 창고", "unvisited 곡물 창고", "unvisited 방앗간",
        "ask 오토"]


def test_help_takes_the_place_of_nudges_while_long_stuck():
    back = [PASS, PASS, PASS]
    assert guides([STATS, ask("밤"), PASS, PASS, go("곡물 창고"), go("광장"), *back, PASS, go("곡물 창고"), *back,
                   go("광장"), *back, go("곡물 창고")]) == [
        None, None, None, None, "meet 한스", None, None, None, None, "hint_topic 오토", None, None, None, "hint_line",
        None, None, None, "hint_place 방앗간", None]


def test_the_dm_shows_an_attitude_that_impressions_turned():
    assert guides([STATS, PASS, PASS, PASS, said("무례"), said("의심")])[-1] == "cold 오토"


def test_the_dm_says_once_that_the_pieces_are_in_when_who_how_and_why_are_in_the_notebook():
    state = start_state(STORY, 1)
    truth = STORY.head.truth
    found = [f"사람 {truth.who}", STORY.shows[truth.how][0], STORY.shows[truth.why][0]]
    assert not is_ready(STORY, {**state, "notebook": {a: 1 for a in found[:2]}})
    full = {**state, "notebook": {a: 1 for a in found}, "turn": 5}
    turn = {"action": PASS[0], "changes": [], "happened": [], "talk": []}
    assert make_guide(STORY, full, full, turn, [])["key"] == "ready"
    assert make_guide(STORY, full, {**full, "turn": 9}, turn, [{"key": "ready", "turn": 5}])["key"] != "ready"
