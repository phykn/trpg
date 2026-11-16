from pathlib import Path

import pytest
from src.rules.state import RuleError, apply_change, apply_turn, start_state
from src.story.load import load_story

STORY = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "skeleton")
LIE = "말 한스.그날 밤.거짓말"
BROKEN = "말 한스.그날 밤.깨진 뒤"
CREW = "말 오토.밤.참말"


def start():
    return start_state(STORY, 7)


def test_start_writes_what_the_start_shows():
    state = start()
    assert state["notebook"] == {"사람 오토": 0, "곳 광장": 0, "곳 곡물 창고": 0}   # what lies here waits for a look
    assert (state["partner"], state["place"], state["visited"]) == ("오토", "광장", ["광장"])
    assert state["attitudes"]["한스"] == {"trust": -1, "fear": 0}


@pytest.mark.parametrize("changes, key, value", [
    ([{"op": "set_stats", "stats": {"charm": 2, "might": 1, "wit": 0, "skill": 0}}], "stats",
     {"charm": 2, "might": 1, "wit": 0, "skill": 0}),
    ([{"op": "spend"}, {"op": "spend"}], "spent", 2),
    ([{"op": "move", "place": "곡물 창고"}], "visited", ["광장", "곡물 창고"]),
    ([{"op": "write", "line": CREW}], "notebook", {"사람 오토": 0, "곳 광장": 0, "곳 곡물 창고": 0, CREW: 1}),
    ([{"op": "look", "place": "광장"}], "looked", ["광장"]),
    ([{"op": "strike", "line": LIE}], "struck", [LIE]),
    ([{"op": "withhold", "block": "꺼림 리사.새벽"}], "withheld", ["꺼림 리사.새벽"]),
    ([{"op": "withhold", "block": "꺼림 리사.새벽"}, {"op": "unwithhold", "block": "꺼림 리사.새벽"}], "withheld", []),
    ([{"op": "hint", "block": "잠김 잠긴 뒷문"}], "hints", ["잠김 잠긴 뒷문"]),
    ([{"op": "judge", "line": LIE, "verdict": "lying"}], "judged", {LIE: "lying"}),
    ([{"op": "open", "block": "거짓말 한스.그날 밤"}], "opened", ["거짓말 한스.그날 밤"]),
    ([{"op": "close", "target": "잠김 잠긴 뒷문", "method": "force"}], "closed", [["잠김 잠긴 뒷문", "force"]]),
    ([{"op": "shift", "person": "한스", "axis": "trust", "by": -1},
      {"op": "shift", "person": "한스", "axis": "fear", "by": 1}], "attitudes",
     {"오토": {"trust": 0, "fear": 0}, "한스": {"trust": -1, "fear": 1}, "리사": {"trust": 0, "fear": 0}}),
    ([{"op": "settle", "event": 0, "result": "prevented"}], "events", {"0": "prevented"}),
    ([{"op": "leave", "person": "리사"}], "gone", ["리사"]),
    ([{"op": "relocate", "person": "한스", "place": "방앗간"}], "where", {"오토": "광장", "한스": "방앗간", "리사": "방앗간"}),
    ([{"op": "vanish", "thing": "빚 문서"}], "lost", ["빚 문서"]),
    ([{"op": "count", "person": "오토", "topic": "밤", "value": 2},
      {"op": "count", "person": "오토", "topic": None, "value": 1}, {"op": "done", "person": "오토"}], "talks",
     {"오토": {"topics": {"밤": 2}, "passes": 1, "done": True}, "한스": {"topics": {}, "passes": 0, "done": False},
      "리사": {"topics": {}, "passes": 0, "done": False}}),
    ([{"op": "face", "person": None}], "partner", None),
    ([{"op": "read", "lines": ["사람 오토", "곳 광장"]}, {"op": "read", "lines": ["곳 광장"]}], "read",
     ["사람 오토", "곳 광장"]),
    ([{"op": "conclude", "who": "한스", "how": None, "why": CREW}], "conclusion",
     {"who": "한스", "how": None, "why": CREW}),
])
def test_each_change_writes_its_part_of_the_state(changes, key, value):
    state = start()
    for change in changes:
        state = apply_change(state, change, 1)
    assert state[key] == value


def spends(n):
    return [{"op": "spend"} for _ in range(n)]


@pytest.mark.parametrize("before, changes, broken", [
    ([], [{"op": "write", "line": "볼 것 없는 것"}], "notebook"),
    ([], [{"op": "write", "line": "사람 오토"}], "notebook"),
    ([], [{"op": "write", "line": "볼 것 수레 자국"}], "shown"),
    ([], [{"op": "strike", "line": LIE}], "struck"),
    ([[{"op": "write", "line": LIE}]], [{"op": "open", "block": "거짓말 한스.그날 밤"}, {"op": "write", "line": BROKEN}],
     "struck"),
    ([], [{"op": "write", "line": BROKEN}], "after"),
    ([[{"op": "leave", "person": "리사"}]], [{"op": "open", "block": "꺼림 리사.새벽"}], "gone"),
    ([], [{"op": "withhold", "block": "꺼림 리사.새벽"}, {"op": "open", "block": "꺼림 리사.새벽"}], "withheld"),
    ([], [{"op": "hint", "block": "잠김 잠긴 뒷문"}], "hint"),
    ([], [{"op": "judge", "line": CREW, "verdict": "true"}], "judged"),
    ([], [{"op": "close", "target": "잠김 잠긴 뒷문", "method": "sneak"}] * 2, "closed"),
    ([], [{"op": "set_stats", "stats": {"charm": 2, "might": 2, "wit": 0, "skill": 0}}], "stats"),
    ([], [{"op": "move", "place": "방앗간"}], "place"),
    ([], [{"op": "face", "person": "한스"}], "partner"),
    ([], spends(9), "spent"),
    ([], [{"op": "settle", "event": 0, "result": "happened"}], "events"),
    ([spends(5) + [{"op": "settle", "event": 0, "result": "happened"}]],
     [{"op": "settle", "event": 0, "result": "prevented"}], "events"),
    ([spends(8)], [{"op": "move", "place": "곡물 창고"}], "ended"),
    ([], [{"op": "conclude", "who": "한스", "how": None, "why": None}], "conclusion"),
    ([[{"op": "conclude", "who": None, "how": None, "why": None}]], [{"op": "read", "lines": ["곳 광장"]}], "final"),
])
def test_a_turn_that_breaks_an_invariant_is_refused(before, changes, broken):
    state = start()
    for turn in before:
        state = apply_turn(STORY, state, turn)
    with pytest.raises(RuleError, match=f"breaks {broken}$"):
        apply_turn(STORY, state, changes)


def test_breaking_a_heard_lie_strikes_it_in_the_same_turn():
    state = apply_turn(STORY, start(), [{"op": "write", "line": LIE}])
    state = apply_turn(STORY, state, [{"op": "open", "block": "거짓말 한스.그날 밤"}, {"op": "strike", "line": LIE},
                                      {"op": "write", "line": BROKEN}])
    assert (state["turn"], state["struck"], state["notebook"][BROKEN]) == (2, [LIE], 2)
