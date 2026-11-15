import json
from pathlib import Path

from src.narrate import count_sentences, judge, make_checks, make_jobs, make_messages
from src.rules.act import act
from src.rules.state import start_state
from src.story.load import load_story
from src.view import make_feed

DAWN = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "dawn")


def play(actions):
    state, turns = start_state(DAWN, 7), []
    for action, heard in actions:
        result = act(DAWN, state, action, heard)
        turn = {"action": action, **{k: result[k] for k in ("dice", "changes", "happened", "talk")}}
        turns.append((state, result["state"], turn))
        state = result["state"]
    return turns


def test_each_text_slot_gets_one_job_and_no_job_says_which_line_is_a_lie():
    moves = [({"do": "move", "place": p}, None) for p in ["숲길", "마을 사당"] * 9]
    turns = play([({"do": "stats", "plus2": "wit", "plus1": "charm"}, None),
                  ({"do": "ask", "text": "징수관은?"}, {"kind": "topics", "topics": ["징수관"]}), *moves])
    every = []
    for before, after, turn in turns:
        jobs = make_jobs(DAWN, before, after, turn)
        ids = {a: i for i, a in enumerate(after["notebook"], 1)}
        assert len(jobs) == len([f for f in make_feed(DAWN, turn, ids) if "slot" in f])
        assert not [w for w in ("거짓말", "깨진 뒤", "풀린 뒤", "참말") if w in json.dumps(jobs, ensure_ascii=False)]
        every += jobs
    opening, answer, first, back, again = (make_jobs(DAWN, *t)[0] for t in turns[:5])
    assert opening["intro"] and opening["desc"] and answer["says"] == [DAWN.lines["말 고드릭.징수관.거짓말"].text]
    assert first["desc"] and "입술이 검푸르게" in " ".join(first["written"]) and first["people"] == ["토빈"]
    assert back["desc"] is None and again["desc"] is None
    assert len([j for j in every if j.get("happening")]) >= 2
    assert "목소리다" in make_messages(answer)[0]["content"] and "서술자다" in make_messages(first)[0]["content"]


def test_a_text_fails_on_low_checks_and_on_length():
    job = {"kind": "answer", "person": "브람", "bio": "", "attitude": "", "said": None, "says": ["말"], "quiet": False}
    assert set(make_checks(job)) == {"added", "meaning"}
    assert judge(job, {"added": {"noul": 0.2}, "meaning": {"noul": 0.8}}, "한 문장.") == (
        [], {"added": 0.2, "meaning": 0.8})
    assert judge(job, {"added": {"noul": 0.9}, "meaning": {"noul": 0.4}}, "하나. 둘! 셋? 넷.")[0] == [
        "added", "meaning", "length"]
    assert count_sentences("……알았소, 그렇다면 말하리다. 해 지기 전에 떠났소") == 2
