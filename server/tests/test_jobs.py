import json
from pathlib import Path

from src.ai.jobs import (
    NARRATED,
    find_doing,
    find_last_said,
    is_here,
    list_narrated,
    list_slots,
    make_dm,
    make_job,
    make_jobs,
)
from src.ai.narrate import make_messages
from src.game.view import make_feed
from src.rules.act import act
from src.rules.guide import make_guide
from src.rules.state import start_state
from src.story.load import load_story
from tests.test_act import LOCK, STORY, doing, said

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
DAWN = load_story(SCENARIOS / "dawn")
SKELETON = load_story(SCENARIOS / "skeleton")


def unopened(story):
    """The story as an old save's copy keeps it, from before stories had an opening: the model writes turn 1."""
    copy = object.__new__(type(story))
    copy.__dict__.update(story.__dict__, head=story.head.model_copy(update={"opening": None}))
    return copy


OLD_DAWN = unopened(DAWN)
STATS = ({"do": "stats", "plus2": "wit", "plus1": "charm"}, None)
JOB_KINDS = {"text": ("answer", "scene", "written"), "ending": ("ending",), "omen": ("scene",), "event": ("scene",),
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
    opening = make_jobs(OLD_DAWN, *turns[0])[0]
    answer, first, looked, back, again = (make_jobs(DAWN, *t)[0] for t in turns[1:6])
    assert "intro" not in opening and opening["desc"] and opening["time"] == "밤 8시"
    # The first talk with the opener tells the case, says the line asked for, then names one more topic.
    assert answer["says"][1] == DAWN.lines["말 고드릭.징수관.거짓말"].text and answer["case"] == DAWN.head.intro
    assert len(answer["says"]) == 3 and answer["leads"] and answer["leads"][0] in answer["says"][2]
    assert not opening["written"] and first["desc"] and not first["written"] and first["people"] == ["토빈"]
    assert first["doing"] == [f"토빈은 {DAWN.people['토빈'].doing[0]}"] and "(" not in make_messages(first)[0]["content"]
    assert "입술이 검푸르게" in " ".join(looked["written"]) and not looked["again"] and looked["happening"]
    assert back["again"] and again["again"] and not first["again"]
    assert len([j for t in turns for j in make_jobs(DAWN, *t) if j.get("happening")]) >= 2
    assert "목소리다" in make_messages(answer)[0]["content"] and "서술자다" in make_messages(first)[0]["content"]
    ending = make_jobs(DAWN, *turns[-1])[0]
    assert ending["kind"] == "ending" and ending["time"] == "새벽 4시"
    assert ending["happening"] == [DAWN.endings.unsolved, *(e.happened for e in DAWN.events if e.at <= 19),
                                   DAWN.endings.explain] and len(ending["happening"]) == 4


def test_the_game_opens_with_the_scene_then_the_opener_calling_out_without_naming_topics():
    (before, after, turn), = play(DAWN, [STATS])
    assert turn["guide"] is None
    jobs = make_jobs(DAWN, before, after, turn)
    feed = [f for f in make_feed(DAWN, turn, {}, after=after) if "slot" in f]
    assert [(f["kind"], f["who"]) for f in feed] == [("text", None), ("text", "고드릭")]
    opening = DAWN.head.opening
    assert jobs == [{"kind": "written", "text": opening.scene}, {"kind": "written", "text": opening.first}]
    hook = make_jobs(OLD_DAWN, before, after, turn)[1]   # an old save's turn 1 still unwritten
    assert hook["kind"] == "answer" and hook["hook"] and hook["case"] == DAWN.head.intro and not hook["leads"]
    assert "방금 당신 앞에 왔다" in make_messages(hook)[-1]["content"]


def test_the_dm_judges_a_person_only_by_bio_mbti_doing_and_attitude():
    (_, after, _), = play(DAWN, [STATS])
    given = make_messages(make_dm(DAWN, after, {"key": "meet", "name": "고드릭"}))[0]["content"].split("지킬 것:")[0]
    assert DAWN.people["고드릭"].mbti in given
    assert DAWN.people["고드릭"].bio in given and "믿음 보통" in given and "거짓말" not in given
    assert DAWN.people["고드릭"].doing[0] in given


def test_people_are_seen_doing_what_they_do_by_now():
    state, hans = start_state(SKELETON, 0), SKELETON.people["한스"].doing
    assert [find_doing(SKELETON, {**state, "spent": s}, "한스") for s in (0, 4, 5, 8)] == [hans[0], hans[0], hans[5], hans[5]]


def test_the_story_mood_reaches_the_narrator_and_the_dm_but_never_a_person():
    turns = play(DAWN, [STATS, ask("징수관")])
    scene = make_jobs(OLD_DAWN, *turns[0])[0]
    dm = make_job(DAWN, *turns[0], {"kind": "guide", "guide": {"key": "meet", "name": "고드릭"}}, ())
    answer = make_jobs(DAWN, *turns[1])[0]
    assert scene["mood"] == dm["mood"] == DAWN.head.mood and "mood" not in answer
    # Given, so the sounds and smells the mood names pass the check.
    assert f"분위기: {DAWN.head.mood}" in make_messages(scene)[0]["content"].split("지킬 것:")[0]
    assert answer["doing"] == DAWN.people["고드릭"].doing[0] and f"지금 하는 일: {answer['doing']}" in make_messages(answer)[0]["content"]


def test_only_a_bet_answer_is_told_its_line_next_to_the_player_line():
    answer = make_jobs(DAWN, *play(DAWN, [STATS, ask("징수관")])[1])[0]
    note = f"(이번에 할 말: {' / '.join(answer['says'])})"
    assert not answer["bet"] and note not in make_messages(answer)[-1]["content"]
    assert make_messages({**answer, "bet": True})[-1]["content"].endswith(note)


def test_an_event_is_news_only_where_the_player_is_not():
    state, event = start_state(SKELETON, 1), SKELETON.events[0]   # 한스 moves, 빚 문서 at 방앗간 vanishes, 리사 leaves
    assert is_here(SKELETON, state, {**state, "place": "방앗간"}, event)
    assert is_here(SKELETON, state, {**state, "place": "곡물 창고"}, event)   # 한스 leaves from here
    assert not is_here(SKELETON, state, state, event)


def test_an_answer_knows_the_talk_so_far_what_the_person_said_and_what_they_watched():
    turns = play(DAWN, [STATS, ask("징수관"), do("look"), ({"do": "ask", "text": "한 잔 하시겠소?"}, {"kind": "chat"})])
    past = [({**turn, "text": [{"text": f"글 {i}"}]}, after) for i, (_, after, turn) in enumerate(turns[:-1])]
    before, after, turn = turns[-1]
    job = make_jobs(DAWN, before, after, turn, past)[0]
    assert job["recent"] == [{"said": "x", "answer": "글 1"}]
    assert job["told"] == [DAWN.lines["말 고드릭.징수관.거짓말"].text]
    assert job["saw"] == ["이곳을 둘러봤다"] and job["lines"] == [] and job["where"].startswith("마을 사당")
    assert "앞서 나눈 말" in make_messages(job)[0]["content"]


def test_an_answer_knows_its_impressions_and_the_rumors_it_heard():
    turns = play(STORY, [STATS, said("무례"), said("무례"), do("move", place="곡물 창고"), do("move", place="광장"),
                         do("move", place="곡물 창고"), ({"do": "ask", "text": "x"}, {"kind": "chat"})])
    oto, hans = (make_jobs(STORY, *turns[i])[0] for i in (2, 6))
    assert oto["impressions"] == ["무례(깔보거나 하인처럼 부리거나 욕한다): 여러 번"]
    assert hans["rumors"] == ["오토에게 무례(전해 들음)"] and not hans["impressions"]
    assert "플레이어에 관한 소문" in make_messages(hans)[0]["content"]


def test_a_typed_action_is_answered_by_the_person_or_told_as_a_scene_at_a_lock():
    pressed = play(STORY, [STATS, ({"do": "ask", "text": "x"}, {"kind": "chat"}), doing("press")])[-1]
    job = make_jobs(STORY, *pressed)[0]
    assert job["kind"] == "answer" and job["says"] == ["플레이어가 거칠게 몰아붙이려 든다. 그 행동에 반응하되, 결과는 아직 모르므로 털어놓거나 굴복하지 않는다"] and job["quiet"]
    forced = play(STORY, [STATS, do("move", place="곡물 창고"), do("look"), doing("force", LOCK)])[-1]
    assert make_jobs(STORY, *forced)[0]["happening"] == ["당신이 잠긴 뒷문을 힘으로 비틀어 열어 보려 손을 댄다. 아직 열리지 않았고 잠긴 그대로다"]


def test_the_last_line_a_person_said_is_found_even_in_the_opening_call():
    turns = [{**turn, "text": None} for _, _, turn in play(DAWN, [STATS, do("look")])]
    assert find_last_said(DAWN, "고드릭", turns) is None   # not written yet
    turns[0] = {**turns[0], "text": [{"text": "사당입니다."}, {"text": "자네, 큰일 났소!"}]}
    turns[1] = {**turns[1], "text": [{"text": "둘러봅니다."}]}
    assert find_last_said(DAWN, "고드릭", turns) == "자네, 큰일 났소!"


def test_the_narrator_gets_its_own_last_texts_and_not_what_people_said():
    turns = play(DAWN, [STATS, ask("징수관"), do("look"), do("look"), do("look"), do("look"), do("look")])
    past = [({**turn, "text": [{"text": f"글 {i}.{k}"} for k in range(len(list_slots(DAWN, turn)))]}, after)
            for i, (_, after, turn) in enumerate(turns[:-1])]
    before, after, turn = turns[-1]
    scene = make_jobs(DAWN, before, after, turn, past)[0]
    assert scene["kind"] == "scene" and len(scene["narrated"]) == NARRATED
    assert scene["narrated"] == ["글 2.0", "글 3.0", "글 4.0", "글 5.0"]   # 1 is 징수관's answer
    assert "글 1.0" not in list_narrated(DAWN, past[:3]) and "앞서 들려준 글" in make_messages(scene)[0]["content"]


def test_a_bet_on_a_line_shows_in_the_answer_whether_the_person_gave_way():
    from tests.test_act import CREW, ask, bet, find_seed
    # wit +2, charm +1: soothing 오토 adds 1 (game/05 3절)
    for win, say, outcome in [(True, "다독임에 마음이 누그러져 이 말이 참이라고 흔들림 없이 힘주어 다시 말한다: ", "밀려서"),
                              (False, "다독여도 마음을 열지 않고 차갑게 선을 긋는다. 새로 털어놓는 것은 없고", "넘어가지 않고")]:
        turns = play(STORY, [STATS, ask("밤"), (bet(CREW, "soothe"), None)], seed=find_seed(3, 1, win))
        job = make_jobs(STORY, *turns[-1])[0]
        assert job["says"][0].startswith(say) and job["outcome"].startswith(outcome)
        assert bool(job["lines"]) == win and job["quiet"] != win


def test_a_person_carries_what_the_ontology_says_they_hide_but_no_topic_or_fact():
    from src.ai.jobs import INNER, list_inner, list_unknown
    from src.rules.state import start_state
    from tests.test_act import STORY
    state = start_state(STORY, 0)
    liar = next(b.name for b in STORY.blocks.values() if b.kind == "거짓말")
    inner = list_inner(STORY, state, liar)
    assert INNER["거짓말", False] in inner
    assert not any(t in line for line in inner for t in STORY.people[liar].topics)
    assert ("들키면" in " ".join(list_inner(STORY, state, STORY.head.truth.who)))
    unknown = list_unknown(STORY, state)
    assert all(f"사람 {p}" not in state["notebook"] for p in STORY.people if p in unknown)
