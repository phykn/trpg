import json
from pathlib import Path

from src.narrate import (
    count_sentences,
    is_here,
    judge,
    make_checks,
    make_jobs,
    make_messages,
)
from src.rules.act import act
from src.rules.state import start_state
from src.story.load import load_story
from src.view import make_feed

DAWN = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "dawn")
SKELETON = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "skeleton")


def play(actions):
    state, turns = start_state(DAWN, 7), []
    for action, heard in actions:
        result = act(DAWN, state, action, heard)
        turn = {"action": action, **{k: result[k] for k in ("dice", "changes", "happened", "talk")}}
        turns.append((state, result["state"], turn))
        state = result["state"]
    return turns


def test_each_text_slot_gets_one_job_and_no_job_says_which_line_is_a_lie():
    moves = [({"do": "move", "place": p}, None) for p in ["마을 사당", "숲길"] * 8 + ["마을 사당"]]
    turns = play([({"do": "stats", "plus2": "wit", "plus1": "charm"}, None),
                  ({"do": "ask", "text": "징수관은?"}, {"kind": "topics", "topics": ["징수관"]}),
                  ({"do": "move", "place": "숲길"}, None), ({"do": "look"}, None), *moves,
                  ({"do": "conclude", "who": None, "how": None, "why": None}, None)])
    every = []
    for before, after, turn in turns:
        jobs = make_jobs(DAWN, before, after, turn)
        ids = {a: i for i, a in enumerate(after["notebook"], 1)}
        assert len(jobs) == len([f for f in make_feed(DAWN, turn, ids) if "slot" in f])
        assert not [w for w in ("거짓말", "깨진 뒤", "풀린 뒤", "참말") if w in json.dumps(jobs, ensure_ascii=False)]
        every += jobs
    opening, answer, first, looked, back, again = (make_jobs(DAWN, *t)[0] for t in turns[:6])
    assert opening["intro"] and opening["desc"] and opening["time"] == "밤 8시" and answer["says"] == [DAWN.lines["말 고드릭.징수관.거짓말"].text]
    assert not opening["written"] and first["desc"] and not first["written"] and first["people"] == ["토빈"]
    assert "입술이 검푸르게" in " ".join(looked["written"]) and not looked["again"] and looked["happening"]
    assert back["again"] and again["again"] and not first["again"]
    assert len([j for j in every if j.get("happening")]) >= 2
    assert "목소리다" in make_messages(answer)[0]["content"] and "서술자다" in make_messages(first)[0]["content"]
    ending = make_jobs(DAWN, *turns[-1])[0]
    assert ending["kind"] == "ending" and ending["time"] == "새벽 4시"   # when the cells run out, not when concluded
    assert ending["happening"] == [DAWN.endings.unsolved, *(e.happened for e in DAWN.events if e.at <= 19),
                                   DAWN.endings.explain] and len(ending["happening"]) == 4


def test_a_text_fails_on_low_checks_and_on_length():
    job = {"kind": "answer", "person": "브람", "bio": "", "attitude": "", "said": None, "says": ["말"], "quiet": False}
    assert set(make_checks(job)) == {"added", "meaning"}
    assert judge(job, {"added": {"noul": 0.2}, "meaning": {"noul": 0.8}}, "한 말.") == (
        [], {"added": 0.2, "meaning": 0.8})
    assert judge(job, {"added": {"noul": 0.9}, "meaning": {"noul": 0.4}}, "하나. 둘! 셋? 넷.")[0] == [
        "added", "meaning", "length"]
    assert count_sentences("……알았소, 그렇다면 말하리다. 해 지기 전에 떠났소") == 2
    assert judge(job, {"added": {"noul": 0.2}, "meaning": {"noul": 0.8}}, "말 모르겠어요.")[0] == []   # a person keeps their own speech
    says = {**job, "says": ["징수관 나리가 집에 오셨었다.", "내가 잔 둘을 내갔다."]}
    passing = {"added": {"noul": 0.1}, "meaning": {"noul": 0.9}}
    assert judge(says, passing, "그건... 제가 잘 모르겠어요...")[0] == ["meaning"]   # qa-5 turn 46
    assert judge(says, passing, "사실 징수관 나리가 집에 오셨었어요.")[0] == ["meaning"]   # the second line dropped
    assert judge(says, passing, "사실 징수관 나리가 집에 오셨었어요... 제가 잔을 둘이나 내갔는걸요.")[0] == []
    dm, low = {"kind": "dm", "key": "unvisited"}, {"added": {"noul": 0.1}}
    assert judge(dm, low, "그에게 물어보도록 하세요.")[0] == ["style"]
    assert judge(dm, low, "점잖은 얼굴이군요. 그에게 물어보십시오.")[0] == ["style", "push"]
    assert judge(dm, low, "그가 \"모르겠어요\" 하고 고개를 젓습니다.")[0] == ["speech"]   # the DM puts no words in a mouth
    assert judge(dm, low, "아직 가 보지 않은 경기장으로 가 보길 권합니다.")[0] == ["push"]
    assert judge(dm, low, "경기장 쪽에서 함성이 한 차례 터져 나옵니다.")[0] == []
    assert judge({"kind": "dm", "key": "conclude"}, low, "공이 울립니다. 당신의 결론을 들려주십시오.")[0] == []


def test_the_dm_is_the_last_slot_and_judges_a_person_only_by_bio_and_attitude():
    (before, after, turn), = play([({"do": "stats", "plus2": "wit", "plus1": "charm"}, None)])
    turn = {**turn, "guide": {"key": "open", "name": "고드릭"}}
    jobs = make_jobs(DAWN, before, after, turn)
    feed = [f for f in make_feed(DAWN, turn, {}) if "slot" in f]
    assert [f["kind"] for f in feed] == ["text", "guide"] and jobs[-1]["kind"] == "dm"
    system = make_messages(jobs[-1])[0]["content"]
    assert DAWN.people["고드릭"].bio in system and "믿음 보통" in system
    assert "거짓말" not in "\n".join(make_messages(jobs[-1])[0]["content"].split("지킬 것:")[0].splitlines())


def test_an_event_is_news_only_where_the_player_is_not():
    state, event = start_state(SKELETON, 1), SKELETON.events[0]   # 한스 moves, 빚 문서 at 방앗간 vanishes, 리사 leaves
    assert is_here(SKELETON, state, {**state, "place": "방앗간"}, event)
    assert is_here(SKELETON, state, {**state, "place": "곡물 창고"}, event)   # 한스 leaves from here
    assert not is_here(SKELETON, state, state, event)
