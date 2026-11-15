from pathlib import Path

import pytest
from src.rules.act import Refused, act, roll_dice
from src.rules.state import start_state
from src.story.load import load_story

STORY = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "skeleton")
STATS = {"do": "stats", "plus2": "skill", "plus1": "charm"}
CREW = "말 오토.밤.참말"
LOCK = "잠김 잠긴 뒷문"
PASS = ({"do": "ask"}, {"kind": "none"})


def ask(*topics):
    return {"do": "ask"}, {"kind": "topics", "topics": list(topics)}


def go(place):
    return {"do": "move", "place": place}


def present(line, target):
    return {"do": "present", "line": line, "target": target}


def bet(target, method):
    return {"do": "bet", "target": target, "method": method}


def play(seed, steps):
    state = start_state(STORY, seed)
    results = []
    for step in steps:
        action, heard = step if isinstance(step, tuple) else (step, None)
        result = act(STORY, state, action, heard)
        state = result["state"]
        results.append(result)
    return state, results


def ops(result):
    return [c["op"] for c in result["changes"]]


def find_seed(turn, bonus, win):
    return next(s for s in range(500) if (sum(roll_dice(s, turn)) + bonus >= 8) == win)


def test_stats_come_first():
    with pytest.raises(Refused):
        play(1, [ask("밤")])


def test_asking_writes_once_then_leads_and_passes_lead_to_done():
    state, rs = play(1, [STATS, ask("밤"), ask("밤"), ask("밤")])
    assert [r["talk"] for r in rs[1:]] == [[{"say": CREW}], [{"say": CREW}], [{"say": CREW}, {"lead": "오토.씨앗"}]]
    assert ops(rs[2]) == ["count", "count"]
    state, rs = play(1, [STATS, ask("밤", "씨앗"), PASS, PASS, PASS])
    assert rs[4]["talk"] == [{"pass": "오토"}, {"done": "오토"}]
    assert state["talks"]["오토"] == {"topics": {"밤": 1, "씨앗": 1}, "passes": 3, "done": True}


def test_a_held_topic_that_appears_after_done_is_marked_the_next_time_you_talk():
    chat = ({"do": "ask"}, {"kind": "chat"})
    _, rs = play(1, [STATS, ask("밤"), go("방앗간"), PASS, PASS, PASS, go("곡물 창고"),
                         present("볼 것 꺼진 등잔", "한스"), go("방앗간"), chat])
    assert rs[5]["talk"] == [{"pass": "리사"}, {"done": "리사"}] and ops(rs[5]) == ["count", "done"]
    assert "꺼림 리사.새벽" not in rs[8]["state"]["withheld"]   # the topic appeared after she was done
    assert rs[9]["changes"] == [{"op": "withhold", "block": "꺼림 리사.새벽"}] and rs[9]["talk"] == [{"chat": "리사"}]


def test_a_held_back_topic_is_withheld_then_opened_by_what_it_wants():
    state, rs = play(1, [STATS, ask("밤"), go("곡물 창고"), go("방앗간"), ask("새벽"), present(CREW, "리사")])
    assert rs[4]["changes"][0] == {"op": "withhold", "block": "꺼림 리사.새벽"}
    assert ops(rs[5]) == ["unwithhold", "open", "write", "shift"]
    assert (state["spent"], state["attitudes"]["리사"]["trust"], state["withheld"]) == (3, 1, [])


def test_presenting_right_is_free_and_wrong_costs_a_cell_and_a_pass():
    state, rs = play(1, [STATS, ask("밤"), go("곡물 창고"), ask("그날 밤"), present("볼 것 쇠 지렛대", "한스"),
                         present(CREW, "한스"), present("볼 것 쇠 지렛대", LOCK)])
    assert ops(rs[4]) == ["count", "spend"] and rs[4]["talk"] == [{"pass": "한스"}]
    assert ops(rs[5]) == ["open", "strike", "write", "shift"]
    assert ops(rs[6]) == ["open", "write"] and rs[6]["changes"][1]["line"] == "볼 것 수레 자국"
    assert (state["spent"], state["struck"], state["attitudes"]["한스"]["fear"]) == (2, ["말 한스.그날 밤.거짓말"], 1)


def test_a_lock_takes_only_an_item():
    state, _ = play(1, [STATS, go("곡물 창고")])
    with pytest.raises(Refused):
        act(STORY, state, present("볼 것 꺼진 등잔", LOCK))


@pytest.mark.parametrize("win", [True, False])
def test_betting_on_a_line_marks_it_or_costs_trust(win):
    seed = find_seed(3, 1, win)
    state, rs = play(seed, [STATS, ask("밤"), bet(CREW, "soothe")])
    assert rs[2]["dice"] == {"method": "soothe", "eyes": roll_dice(seed, 3), "total": sum(roll_dice(seed, 3)) + 1,
                           "won": win} and state["spent"] == 1
    assert state["judged"] == ({CREW: "true"} if win else {})
    assert state["closed"] == ([] if win else [[CREW, "soothe"]]) and state["hints"] == []
    assert state["attitudes"]["오토"]["trust"] == (1 if win else -1)


def test_a_failed_bet_on_a_lock_hints_and_closes_that_way_only():
    seed = find_seed(3, 1, False)
    state, _ = play(seed, [STATS, go("곡물 창고"), bet(LOCK, "sneak")])
    assert (state["closed"], state["hints"]) == ([[LOCK, "sneak"]], [LOCK])
    with pytest.raises(Refused):
        act(STORY, state, bet(LOCK, "sneak"))
    assert act(STORY, state, bet(LOCK, "force"))["state"]["spent"] == 3
    won, _ = play(find_seed(3, 1, True), [STATS, go("곡물 창고"), bet(LOCK, "sneak")])
    assert LOCK in won["opened"] and "볼 것 수레 자국" in won["notebook"]


def test_the_event_happens_after_its_omen_unless_its_block_is_open():
    walk = [go("곡물 창고"), go("광장"), go("곡물 창고"), go("광장"), go("곡물 창고")]
    state, rs = play(1, [STATS] + walk)
    assert rs[2]["happened"] == [{"omen": 0}] and rs[5]["happened"] == [{"event": 0, "result": "happened"}]
    assert (state["where"]["한스"], state["lost"], state["gone"], state["partner"]) == ("방앗간", ["빚 문서"], ["리사"], None)
    state, rs = play(1, [STATS, ask("밤"), go("곡물 창고"), present(CREW, "한스")] + walk[1:])
    assert all(r["happened"] == [] for r in rs[:-1]) and rs[-1]["happened"] == [{"event": 0, "result": "prevented"}]
    assert (state["events"], state["where"]["한스"], state["gone"]) == ({"0": "prevented"}, "곡물 창고", [])


def test_when_the_cells_run_out_only_reading_and_concluding_remain():
    state, _ = play(1, [STATS] + [go("곡물 창고"), go("광장")] * 4)
    assert state["spent"] == 8
    with pytest.raises(Refused):
        act(STORY, state, go("곡물 창고"))
    state = act(STORY, state, {"do": "read", "lines": ["사람 한스"]})["state"]
    with pytest.raises(Refused):
        act(STORY, state, {"do": "conclude", "who": "리사", "how": None, "why": None})
    state = act(STORY, state, {"do": "conclude", "who": "한스", "how": "볼 것 꺼진 등잔", "why": None})["state"]
    assert state["conclusion"] == {"who": "한스", "how": "볼 것 꺼진 등잔", "why": None}
    with pytest.raises(Refused):
        act(STORY, state, {"do": "read", "lines": ["곳 광장"]})


def test_the_same_actions_make_the_same_game():
    steps = [STATS, ask("밤"), go("곡물 창고"), bet(LOCK, "force"), present(CREW, "한스"), go("방앗간")]
    assert play(5, steps) == play(5, steps)


def test_arriving_as_an_event_takes_a_thing_away_writes_only_what_is_left():
    state, _ = play(1, [STATS, ask("밤"), go("곡물 창고"), go("광장"), go("곡물 창고"), go("광장"), go("방앗간")])
    assert state["spent"] == 5 and "빚 문서" in state["lost"] and "볼 것 빚 문서" not in state["notebook"]
