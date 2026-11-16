import json
from pathlib import Path

from src.narrate import make_messages
from src.rules.act import act
from src.rules.guide import make_guide
from src.rules.state import start_state
from src.slots import is_here, make_jobs
from src.story.load import load_story
from src.view import make_feed

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
DAWN = load_story(SCENARIOS / "dawn")
SKELETON = load_story(SCENARIOS / "skeleton")
STATS = ({"do": "stats", "plus2": "wit", "plus1": "charm"}, None)
JOB_KINDS = {"text": ("answer", "scene"), "ending": ("ending",), "omen": ("scene",), "event": ("scene",),
             "guide": ("dm",)}


def play(story, actions, seed=7):
    state, turns, past = start_state(story, seed), [], []
    for action, heard in actions:
        result = act(story, state, action, heard)
        turn = {"action": action, **{k: result[k] for k in ("dice", "changes", "happened", "talk")}}
        turn["guide"] = make_guide(story, state, result["state"], turn, past)
        past += [{**turn["guide"], "turn": result["state"]["turn"]}] if turn["guide"] else []
        turns.append((state, result["state"], turn))
        state = result["state"]
    return turns


def ask(*topics):
    return {"do": "ask", "text": "x"}, {"kind": "topics", "topics": list(topics)}


def do(name, **fields):
    return {"do": name, **fields}, None


DAWN_GAME = [STATS, ask("징수관"), do("move", place="숲길"), do("look"),
             *[do("move", place=p) for p in ["마을 사당", "숲길"] * 8 + ["마을 사당"]],
             do("conclude", who=None, how=None, why=None)]
CREW = "말 오토.밤.참말"
SKELETON_GAME = [STATS, do("look"), ask("밤"), do("move", place="곡물 창고"), do("look"), ask("그날 밤"),
                 do("present", line="볼 것 쇠 지렛대", target="한스"), do("present", line=CREW, target="한스"),
                 do("present", line="볼 것 쇠 지렛대", target="잠김 잠긴 뒷문"), do("move", place="방앗간"),
                 ask("새벽"), do("present", line=CREW, target="리사"), ({"do": "ask"}, {"kind": "none"}),
                 do("face", person=None), do("read", lines=["곳 광장"]),
                 do("conclude", who="한스", how="볼 것 수레 자국", why=None)]


def test_every_text_slot_of_a_whole_game_gets_one_job_of_its_kind_and_no_job_names_a_branch_address():
    for story, game in ((DAWN, DAWN_GAME), (SKELETON, SKELETON_GAME)):
        kinds = set()
        for before, after, turn in play(story, game):
            jobs = make_jobs(story, before, after, turn)
            ids = {a: i for i, a in enumerate(after["notebook"], 1)}
            slots = [f for f in make_feed(story, turn, ids) if "slot" in f]
            assert [f["slot"] for f in slots] == list(range(len(jobs)))
            assert all(job["kind"] in JOB_KINDS[f["kind"]] for f, job in zip(slots, jobs))
            assert not [w for w in (".거짓말", ".깨진 뒤", ".풀린 뒤", ".참말") if w in json.dumps(jobs, ensure_ascii=False)]
            kinds |= {f["kind"] for f in slots}
        assert {"text", "ending", "guide"} <= kinds


def test_jobs_tell_what_is_new_and_the_ending_tells_the_time_the_cells_ran_out():
    turns = play(DAWN, DAWN_GAME)
    opening, answer, first, looked, back, again = (make_jobs(DAWN, *t)[0] for t in turns[:6])
    assert opening["intro"] and opening["desc"] and opening["time"] == "밤 8시"
    assert answer["says"] == [DAWN.lines["말 고드릭.징수관.거짓말"].text]
    assert not opening["written"] and first["desc"] and not first["written"] and first["people"] == ["토빈"]
    assert "입술이 검푸르게" in " ".join(looked["written"]) and not looked["again"] and looked["happening"]
    assert back["again"] and again["again"] and not first["again"]
    assert len([j for t in turns for j in make_jobs(DAWN, *t) if j.get("happening")]) >= 2
    assert "목소리다" in make_messages(answer)[0]["content"] and "서술자다" in make_messages(first)[0]["content"]
    ending = make_jobs(DAWN, *turns[-1])[0]
    assert ending["kind"] == "ending" and ending["time"] == "새벽 4시"
    assert ending["happening"] == [DAWN.endings.unsolved, *(e.happened for e in DAWN.events if e.at <= 19),
                                   DAWN.endings.explain] and len(ending["happening"]) == 4


def test_the_dm_is_the_last_slot_and_judges_a_person_only_by_bio_and_attitude():
    (before, after, turn), = play(DAWN, [STATS])
    assert turn["guide"] == {"key": "open", "name": "고드릭"}
    jobs = make_jobs(DAWN, before, after, turn)
    feed = [f for f in make_feed(DAWN, turn, {}) if "slot" in f]
    assert [f["kind"] for f in feed] == ["text", "guide"] and jobs[-1]["kind"] == "dm"
    given = make_messages(jobs[-1])[0]["content"].split("지킬 것:")[0]
    assert DAWN.people["고드릭"].bio in given and "믿음 보통" in given and "거짓말" not in given


def test_an_event_is_news_only_where_the_player_is_not():
    state, event = start_state(SKELETON, 1), SKELETON.events[0]   # 한스 moves, 빚 문서 at 방앗간 vanishes, 리사 leaves
    assert is_here(SKELETON, state, {**state, "place": "방앗간"}, event)
    assert is_here(SKELETON, state, {**state, "place": "곡물 창고"}, event)   # 한스 leaves from here
    assert not is_here(SKELETON, state, state, event)
