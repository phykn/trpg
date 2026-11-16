from pathlib import Path

import pytest
from src.rules.act import Refused, act, roll_dice, was_tried
from src.rules.state import list_rumors, start_state
from src.story.load import load_story

STORY = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "skeleton")
STATS = {"do": "stats", "plus2": "skill", "plus1": "charm"}
CREW = "말 오토.밤.참말"
LOCK = "잠김 잠긴 뒷문"
PASS = ({"do": "ask"}, {"kind": "none"})
LOOK = {"do": "look"}


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
    _, rs = play(1, [STATS, ask("밤"), go("방앗간"), PASS, PASS, PASS, go("곡물 창고"), LOOK,
                         present("볼 것 꺼진 등잔", "한스"), go("방앗간"), chat])
    assert rs[5]["talk"] == [{"pass": "리사"}, {"done": "리사"}] and ops(rs[5]) == ["count", "done"]
    assert "꺼림 리사.새벽" not in rs[9]["state"]["withheld"]   # the topic appeared after she was done
    assert rs[10]["changes"] == [{"op": "withhold", "block": "꺼림 리사.새벽"}] and rs[10]["talk"] == [{"chat": "리사"}]


def test_a_held_back_topic_is_withheld_then_opened_by_what_it_wants():
    state, rs = play(1, [STATS, ask("밤"), go("곡물 창고"), LOOK, go("방앗간"), ask("새벽"), present(CREW, "리사")])
    assert rs[5]["changes"][0] == {"op": "withhold", "block": "꺼림 리사.새벽"}
    assert ops(rs[6]) == ["unwithhold", "open", "write", "shift"]
    assert (state["spent"], state["attitudes"]["리사"]["trust"], state["withheld"]) == (3, 1, [])


def test_presenting_right_is_free_and_wrong_costs_a_cell_and_a_pass():
    state, rs = play(1, [STATS, LOOK, ask("밤"), go("곡물 창고"), LOOK, ask("그날 밤"), present("볼 것 쇠 지렛대", "한스"),
                         present(CREW, "한스"), present("볼 것 쇠 지렛대", LOCK)])
    assert ops(rs[6]) == ["try", "count", "spend"] and rs[6]["talk"] == [{"pass": "한스"}]
    assert ops(rs[7]) == ["open", "strike", "write", "shift"]
    assert ops(rs[8]) == ["open", "write"] and rs[8]["changes"][1]["line"] == "볼 것 수레 자국"
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
    seed = find_seed(4, 1, False)
    state, _ = play(seed, [STATS, go("곡물 창고"), LOOK, bet(LOCK, "sneak")])
    assert (state["closed"], state["hints"]) == ([[LOCK, "sneak"]], [LOCK])
    with pytest.raises(Refused):
        act(STORY, state, bet(LOCK, "sneak"))
    assert act(STORY, state, bet(LOCK, "force"))["state"]["spent"] == 3
    won, _ = play(find_seed(4, 1, True), [STATS, go("곡물 창고"), LOOK, bet(LOCK, "sneak")])
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
    state, _ = play(1, [STATS, go("곡물 창고"), LOOK, go("광장")] + [go("곡물 창고"), go("광장")] * 3)
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
    steps = [STATS, ask("밤"), go("곡물 창고"), LOOK, bet(LOCK, "force"), present(CREW, "한스"), go("방앗간")]
    assert play(5, steps) == play(5, steps)


def test_arriving_as_an_event_takes_a_thing_away_writes_only_what_is_left():
    state, _ = play(1, [STATS, ask("밤"), go("곡물 창고"), go("광장"), go("곡물 창고"), go("광장"), go("방앗간"), LOOK])
    assert state["spent"] == 5 and "빚 문서" in state["lost"] and "볼 것 빚 문서" not in state["notebook"]


def test_a_failed_present_is_known_until_the_person_holds_something_new():
    lever = "볼 것 쇠 지렛대"
    state, _ = play(1, [STATS, LOOK, ask("밤"), go("곡물 창고"), present(lever, "한스")])
    assert state["spent"] == 2 and was_tried(STORY, state, lever, "한스")
    tried = {**start_state(STORY, 1), "place": "방앗간", "tried": [{"line": CREW, "target": "리사", "blocks": []}]}
    assert was_tried(STORY, tried, CREW, "리사")
    lamp = {**tried, "notebook": {"볼 것 꺼진 등잔": 1}}   # her held topic is out now; the line may yet answer it
    assert not was_tried(STORY, lamp, CREW, "리사")


def test_arriving_writes_who_is_there_and_looking_writes_what_lies_there():
    lamp = "볼 것 꺼진 등잔"
    state, rs = play(1, [STATS, go("곡물 창고")])
    assert "사람 한스" in state["notebook"] and lamp not in state["notebook"] and "볼 것 쇠 지렛대" not in state["notebook"]
    state, rs = play(1, [STATS, go("곡물 창고"), LOOK, LOOK])
    assert ops(rs[2])[0] == "look" and lamp in state["notebook"] and state["spent"] == 1
    assert ops(rs[3]) == [] and rs[3]["talk"] == [{"look": "곡물 창고"}]   # a second look only tells the scene again


def said(impression, *topics):
    heard = {"kind": "topics", "topics": list(topics)} if topics else {"kind": "chat"}
    return {"do": "ask", "text": "x"}, {**heard, "impression": impression}


def test_two_impressions_of_one_lean_move_the_attitude_and_close_people_hear_later():
    state, rs = play(0, [STATS, said("다정"), said("칭찬")])
    assert ops(rs[1]) == ["impress", "rumor"] and ops(rs[2]) == ["impress", "shift", "rumor"]
    assert state["impressions"]["오토"] == {"다정": 1, "칭찬": 1} and state["attitudes"]["오토"]["trust"] == 1
    assert [(r["to"], r["impression"], r["at"], r["seen"]) for r in state["rumors"]] == [
        ("한스", "다정", 2, False), ("한스", "칭찬", 2, False)]
    later, _ = play(0, [STATS, said("다정"), go("곡물 창고"), go("광장")])
    assert [r["impression"] for r in list_rumors(later, "한스")] == ["다정"]


def test_the_right_impression_opens_a_held_topic_as_a_fitting_clue_would():
    state, rs = play(1, [STATS, ask("밤"), go("곡물 창고"), LOOK, go("방앗간"), said("위로", "새벽")])
    assert ops(rs[5])[:5] == ["impress", "open", "write", "shift", "count"]
    assert "꺼림 리사.새벽" in state["opened"] and "말 리사.새벽.풀린 뒤" in state["notebook"]
    assert rs[5]["talk"][0] == {"say": "말 리사.새벽.풀린 뒤"}
    held, _ = play(1, [STATS, ask("밤"), go("곡물 창고"), LOOK, go("방앗간"), said("다정", "새벽")])
    assert "꺼림 리사.새벽" not in held["opened"]


def test_a_deed_impresses_the_owner_who_watched_and_an_unknown_impression_is_refused():
    state, _ = play(find_seed(4, 1, True), [STATS, go("곡물 창고"), LOOK, bet(LOCK, "sneak")])
    assert state["impressions"]["한스"] == {"무례": 1}
    with pytest.raises(Refused):
        play(0, [STATS, said("사탕")])   # 리사's own impression, not 오토's


def doing(method, target=None):
    return {"do": "ask", "text": "x"}, {"kind": "action", "method": method, "target": target}


def test_a_typed_action_costs_no_cell_and_pressing_leaves_a_threat():
    state, rs = play(0, [STATS, doing("press")])
    assert state["spent"] == 0 and state["impressions"]["오토"] == {"위협": 1}
    assert rs[1]["talk"] == [{"try": "오토", "method": "press"}]
    soft, _ = play(0, [STATS, doing("soothe")])
    assert soft["impressions"]["오토"] == {}
    with pytest.raises(Refused):
        play(0, [STATS, doing("force", LOCK)])   # the lock is not here
    _, rs = play(0, [STATS, go("곡물 창고"), LOOK, doing("force", LOCK)])
    assert rs[3]["talk"] == [{"try": LOCK, "method": "force"}] and not rs[3]["changes"]
