import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import httpx
from conftest import REPO
from run_api import build_app
from src.lang.polite import polite
from src.locale import ko
from src.models.decision import ModelUnavailable
from src.narrate import (
    Narrator,
    change_line,
    change_lines,
    messages,
    sentences_of,
    split,
)
from src.onto.atoms import PLAYER, State
from src.service import GameService
from src.story.validate import load_all

STORIES = load_all(REPO / "scenarios")
CREATION = {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]}
GOOD = "젖은 길을 따라 마을로 내려갑니다. 낮은 지붕들 위로 회색 구름이 깔려 있습니다."


class FakeLLM:
    """The last draft repeats; an exception draft raises."""

    def __init__(self, *drafts, delay=0.0):
        self.drafts, self.calls, self.delay = list(drafts), [], delay

    async def stream(self, messages, max_tokens=500, seed=None):
        self.calls.append(messages)
        draft = self.drafts[min(len(self.calls), len(self.drafts)) - 1]
        await asyncio.sleep(self.delay)
        if isinstance(draft, Exception):
            raise draft
        for i in range(0, len(draft), 7):
            yield draft[i:i + 7]


class FakeDecision:
    def __init__(self, bad=0.0):
        self.bad, self.asked = bad, []

    async def decide(self, state, questions):
        self.asked.append((state, questions))
        return {q: SimpleNamespace(probabilities={"fine": 1 - self.bad, "contradicts": self.bad, "invents": 0.0})
                for q in questions}


async def game(tmp_path, llm, decision=None, moves=("go:village",)):
    svc = GameService(STORIES, tmp_path, narrator=Narrator(llm, decision or FakeDecision()), seeds=lambda: 7)
    out = await svc.create("r", "lighthouse", CREATION)
    gid, view = out["game_id"], out["view"]
    for i, a in enumerate(moves):
        view = (await svc.command(gid, {"request_id": f"m{i}", "revision": view["revision"], "action": a}))["view"]
    return svc, gid, view


async def events(svc, gid, n=1):
    return [e async for e in await svc.narration(gid, n)]


def test_text_helpers():
    assert sentences_of("하나입니다. 둘입니다! \"셋.\" 넷입니다") == ["하나입니다.", "둘입니다!", "\"셋.\" 넷입니다"]
    assert sentences_of("그가 웃습니다. \"돌아와. 꼭!\" 그가 말합니다.") == ["그가 웃습니다.", "\"돌아와. 꼭!\" 그가 말합니다."]
    assert sentences_of("바람이 붑니다. 그가 대답합니다. \"그래. 가.\"") == ["바람이 붑니다.", "그가 대답합니다. \"그래. 가.\""]
    assert split("문이 열린다.\n태그: 젖은 발\n[문맥]\n- 사실") == ("문이 열립니다.", ["젖은 발"])
    assert split("등대 앞에 섰습니다. 태그: 흩날리는 물보라") == ("등대 앞에 섰습니다.", ["흩날리는 물보라"])
    assert polite("그가 \"간다\"고 말했다.") == "그가 \"간다\"고 말했습니다."
    assert split("\"다 썼네. \\*컥\\*, 없네.\" **도해**가 말한다.") == ("\"다 썼네. 컥, 없네.\" 도해가 말합니다.", [])


async def test_stages_then_text_and_done(tmp_path):
    llm = FakeLLM(GOOD)
    svc, gid, _ = await game(tmp_path, llm)
    got = await events(svc, gid)
    assert [e.get("stage", e["type"]) for e in got] == ["writing", "checking", "text", "done"]
    assert got[2]["text"] == GOOD
    assert (await svc.view(gid))["last"]["narrated"] is True
    again = await events(svc, gid)
    assert [e["type"] for e in again] == ["text", "done"] and len(llm.calls) == 1


async def test_a_failed_rule_is_rewritten_with_feedback(tmp_path):
    llm = FakeLLM("마을로 3걸음 내려갑니다. 구름이 낮습니다.", GOOD)
    svc, gid, _ = await game(tmp_path, llm)
    got = await events(svc, gid)
    assert {"type": "stage", "stage": "rewriting", "attempt": 2} in got and got[-2]["text"] == GOOD
    feedback = llm.calls[1][1]["content"]
    assert "[고칠 점]" in feedback and "마을로 3걸음 내려갑니다." in feedback


async def test_unearned_possession_is_rejected(tmp_path):
    llm = FakeLLM("당신은 등대 열쇠를 손에 넣었습니다. 바람이 붑니다.", GOOD)
    svc, gid, _ = await game(tmp_path, llm)
    got = await events(svc, gid)
    assert got[-2]["text"] == GOOD and "등대 열쇠" in llm.calls[1][1]["content"]


async def test_three_failures_drop_the_sentences_and_keep_delta(tmp_path):
    decision = FakeDecision(bad=0.9)                       # the check rejects every sentence
    llm = FakeLLM(GOOD)
    svc, gid, _ = await game(tmp_path, llm, decision)
    got = await events(svc, gid)
    assert len(llm.calls) == 3 and got[-2]["type"] == "text" and got[-2]["text"]
    feedback = llm.calls[1][1]["content"]
    assert ko.FEEDBACK["contradicts"] in feedback and ko.FEEDBACK["invents"] not in feedback
    entry = svc.games[gid][1].presentation["narration"]["1"]
    assert entry["attempts"] == 3 and entry["dropped"] == 2


async def test_a_silent_model_ends_in_error_and_is_not_cached(tmp_path):
    llm = FakeLLM(ModelUnavailable("down"))
    svc, gid, _ = await game(tmp_path, llm)
    got = await events(svc, gid)
    assert got[-1]["type"] == "error" and len(llm.calls) == 3
    assert "1" not in svc.games[gid][1].presentation["narration"]
    llm.drafts = [GOOD]
    assert (await events(svc, gid))[-2]["text"] == GOOD


async def test_overlapping_requests_share_one_narration(tmp_path):
    llm = FakeLLM(GOOD, delay=0.05)
    svc, gid, _ = await game(tmp_path, llm)
    a, b = await asyncio.gather(events(svc, gid), events(svc, gid))
    assert a == b and len(llm.calls) == 1


async def test_check_reads_only_the_view(tmp_path):
    decision = FakeDecision()
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD), decision)
    await events(svc, gid)
    state, qs = decision.asked[0]
    assert "누렁이" not in state and "누렁이" not in json.dumps(qs, ensure_ascii=False)
    assert set(qs) == {"0", "1"} and all(set(q["criteria"]) == {"fine", "contradicts", "invents"} for q in qs.values())


async def test_routes_stream_ndjson(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))
    app = build_app(service=svc, basic_auth_user="u", basic_auth_pass="p", cors_origins=[])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", auth=("u", "p")) as c:
        r = await c.get(f"/games/{gid}/turns/1/narration")
        lines = [json.loads(x) for x in r.text.splitlines()]
        assert r.headers["content-type"].startswith("application/x-ndjson") and lines[-1]["type"] == "done"
        assert (await c.get(f"/games/{gid}/turns/9/narration")).status_code == 404
        assert (await c.get(f"/games/{gid}/chapters/1/recap")).status_code == 404


async def test_tag_names_come_from_the_narration_when_they_pass(tmp_path):
    llm = FakeLLM("등대 앞에 닿자 물보라가 얼굴을 때립니다. 발밑이 미끄럽습니다.\n태그: 젖은 발")
    svc, gid, _ = await game(tmp_path, llm, moves=("go:village", "go:yard"))
    got = await events(svc, gid, 2)
    assert got[-1]["tags"] and got[-1]["tags"][0]["name"] == "젖은 발"
    assert any(t[2] == "젖은 발" for t in svc.games[gid][1].presentation["tags"])
    llm.drafts = ["물보라가 칩니다.\n태그: 이 이름은 열두 글자를 훌쩍 넘습니다"]
    svc2, gid2, _ = await game(tmp_path / "b", llm, moves=("go:village", "go:yard"))
    assert (await events(svc2, gid2, 2))[-1]["tags"][0]["name"] != "이 이름은 열두 글자를 훌쩍 넘습니다"


async def test_a_finished_chapter_has_a_recap(tmp_path):
    llm = FakeLLM("문이 열리고 당신은 꼭대기에 섭니다. 바람이 거셉니다.")
    svc, gid, view = await game(tmp_path, llm, moves=("go:village", "go:yard"))
    for i in range(8):
        out = await svc.command(gid, {"request_id": f"t{i}", "revision": view["revision"], "action": "try:door:finesse"})
        card = out["view"]["card"]
        view = (await svc.command(gid, {"request_id": f"p{i}", "revision": out["view"]["revision"],
                                        "card": card["id"], "pick": "try:door:finesse"}))["view"]
        if (ob := view["scene"]["obstacles"][0])["fill"] == ob["boxes"]:
            break
    out = await svc.command(gid, {"request_id": "up", "revision": view["revision"], "action": "go:lamp_room"})
    n = out["turn"]
    assert svc._turn_job(*svc.games[gid], n - 1).progress == {"door": True}     # the roll that opened the door
    narr = await events(svc, gid, n)
    assert narr[-2]["type"] == "text"
    assert "160자" in llm.calls[-1][0]["content"]
    got = [e async for e in await svc.recap(gid, 1)]
    assert got[-2]["type"] == "text" and "되짚는" in llm.calls[-1][1]["content"]
    # the move that closed the chapter is not notable on its own, yet the recap must end on it (play-3-bold 21)
    # the door overcome and the move that closed the chapter, though neither is a +2 improvisation (play-3-bold 6, 21)
    notable = llm.calls[-1][1]["content"].split(ko.HEAD["notable"])[1].split(ko.STYLE)[0]
    assert "녹슨 등대 문이 마침내 당신 뜻대로 되었습니다" in notable
    assert notable.rstrip().endswith("- 새 장이 시작됩니다: 불을 켜다") and "'등대에 오르다' 장이 끝났습니다" in notable
    assert (await svc.view(gid))["recaps"] == [1]


async def test_an_obstacle_said_open_before_it_is_full_is_rejected(tmp_path):
    llm = FakeLLM("녹슨 등대 문이 활짝 열렸습니다. 바람이 붑니다.", "등대 앞에 바람이 붑니다. 물보라가 칩니다.")
    svc, gid, _ = await game(tmp_path, llm, moves=("go:village", "go:yard"))
    got = await events(svc, gid, 2)
    assert {"type": "stage", "stage": "rewriting", "attempt": 2} in got


async def test_an_absent_person_acting_is_rewritten(tmp_path):
    llm = FakeLLM("윤슬이 당신의 젖은 소매를 가볍게 스칩니다. 바람이 붑니다.", GOOD)
    svc, gid, _ = await game(tmp_path, llm)        # the village; 윤슬 waits at the dock
    got = await events(svc, gid)
    assert {"type": "stage", "stage": "rewriting", "attempt": 2} in got and got[-2]["text"] == GOOD
    assert "없는 사람" in llm.calls[1][1]["content"] and "윤슬" in llm.calls[1][1]["content"]


async def test_a_change_naming_someone_elsewhere_does_not_bring_them_here(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))
    u, g = svc.games[gid]
    job = replace(svc._turn_job(u, g, 1), delta=["윤슬이 기름통을 얻었습니다"])
    said = ["윤슬이 당신의 젖은 소매를 가볍게 스칩니다.", "도해가 낮게 기침합니다.", "\"윤슬이 온다\"고 누가 외칩니다."]
    per, _ = svc.narrator.rules(job, said, [])
    assert list(per) == [0]


async def test_a_companion_left_behind_appears_only_parting(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))     # the village; 윤슬 is at the dock
    u, g = svc.games[gid]
    job = replace(svc._turn_job(u, g, 1), left={"yunseul": "dock"})
    said = ["윤슬은 선착장에 남아 손을 흔듭니다.", "윤슬이 당신의 젖은 소매를 가볍게 스칩니다."]
    per, _ = svc.narrator.rules(job, said, [])
    assert list(per) == [1]
    prompt = messages(job)[1]["content"]
    assert "윤슬은 선착장에 남았습니다" in prompt and u.agents["yunseul"].fear.rstrip(".") in prompt


async def test_obstacle_progress_is_steered_short_of_done(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))
    job = svc._turn_job(*svc.games[gid], 1)
    now = messages(replace(job, progress={"lamp": False, "door": True}))[1]["content"].split(ko.HEAD["now"])[1]
    assert "꺼진 등불은 조금 진척이 있었을 뿐 아직 다 되지 않았습니다" in now and "녹슨 등대 문은 마침내 다 되었습니다" in now
    assert "진척" not in messages(job)[1]["content"].split(ko.HEAD["now"])[1]


async def test_a_blocked_step_and_what_a_roll_leaned_on_are_steered(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))
    job = svc._turn_job(*svc.games[gid], 1)
    now = messages(replace(job, blocked=("도해와 이야기한다",), relied=("기름통",)))[1]["content"].split(ko.HEAD["now"])[1]
    assert "'도해와 이야기한다'는 무언가에 가로막혀" in now and "기름통을 밑천으로 삼았습니다" in now
    assert "가로막혀" not in messages(job)[1]["content"]


async def test_what_came_to_pass_is_steered_to_be_told(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))
    job = svc._turn_job(*svc.games[gid], 1)
    now = messages(replace(job, struck=("무너지는 다리",), missed=("해가 진다",)))[1]["content"].split(ko.HEAD["now"])[1]
    assert "이번에 닥친 일: 무너지는 다리." in now and "때가 다 된 일: 해가 진다." in now
    assert "닥친 일" not in messages(job)[1]["content"]
    u, g = svc.games[gid]
    g.presentation["turns"][0]["steps"][0]["changes"] += [
        {"kind": "arrival", "id": "deadline.1", "name": "해가 진다"},
        {"kind": "crisis", "id": "storm", "name": "몰려오는 폭풍", "from": 3, "to": 0}]
    job = svc._turn_job(u, g, 1)
    assert job.struck == ("몰려오는 폭풍",) and job.missed == ("해가 진다",)


async def test_a_growth_turn_is_steered_to_the_change_alone(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))
    job = replace(svc._turn_job(*svc.games[gid], 1), grown=True)
    now = messages(job)[1]["content"].split(ko.HEAD["now"])[1]
    assert ko.NOW["grown"] in now and "새로 그릴 감각" not in now and ko.NOW["close"] not in now


async def test_a_turn_that_stops_before_the_rest_of_the_sentence_says_so(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))
    u, g = svc.games[gid]
    job = svc._turn_job(u, g, 1)
    assert "아직 하지 않았습니다" not in messages(job)[1]["content"]
    now = messages(replace(job, unfinished="녹슨 등대 문을 완력으로 다룬다"))[1]["content"].split(ko.HEAD["now"])[1]
    assert "'녹슨 등대 문을 완력으로 다룬다'부터는 아직 하지 않았습니다" in now
    assert ko.NOW["waits_rest"] in messages(replace(job, unfinished=""))[1]["content"]


async def test_an_ending_picks_up_what_the_player_left_behind(tmp_path):
    from src.onto.log import Delta
    from src.onto.view import Seen
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))     # met 윤슬 at the dock, now in the village with 도해
    u, g = svc.games[gid]
    job = svc._turn_job(u, g, 1)
    atoms = [a for a in job.o.facts.atoms() if a[:2] != ("regards", "yunseul")]
    trust = [("regards", "yunseul", PLAYER, "trust", 2), ("regards", "yunseul", PLAYER, "fear", 0)]
    gave = Seen(9, "give", None, "none", ("dohae", PLAYER), Delta(frozenset({("at", "letter", "dohae")}), frozenset()), ())
    o = replace(job.o, facts=State.of([*atoms, *trust]), memory=(*job.o.memory, gave))
    job = replace(job, o=o, ending="불이 다시 켜집니다")
    now = messages(job)[1]["content"].split(ko.HEAD["now"])[1]
    assert "윤슬은 당신을 신뢰합니다" in now and "도해가 아들의 편지를 지니고 있습니다" in now
    assert now.rstrip().endswith("불이 다시 켜집니다") and "아직 멀었습니다" not in now
    said = ["멀리 선착장에서 윤슬이 불빛을 올려다봅니다.", "윤슬이 당신 곁에서 웃습니다."]
    assert list(svc.narrator.rules(job, said, [])[0]) == [1]
    assert list(svc.narrator.rules(replace(job, ending=None), said, [])[0]) == [0, 1]


def test_a_lowered_threat_recedes_instead_of_approaching(u):
    up = {"kind": "clock", "id": "hound", "name": "사냥개", "from": 0, "to": 1}
    assert change_line(u, up).endswith("다가왔습니다")
    assert change_line(u, {**up, "from": 1, "to": 0}).endswith("물러났습니다")
    # a full clock strikes and starts over; read as a fall, it said the storm receded (play-2-bold 23, play-2-odd 50)
    assert change_line(u, {**up, "kind": "crisis", "from": 3, "to": 0}).endswith("끝내 닥쳤습니다")
    lamp = {"kind": "fill", "id": "lamp", "name": "꺼진 등불", "from": 3, "to": 2}
    assert change_line(u, lamp) == "꺼진 등불이 다시 뜻대로 되지 않습니다"
    # a deadline's name is often a clause ("해가 진다"), so no particle follows it, and its arrival says the goal was missed
    assert change_line(u, {"kind": "arrival", "id": "deadline.1", "name": "해가 진다"}) == \
        "해가 진다: 목표를 이루지 못한 채 시간이 다 되었습니다"


def test_a_way_cut_both_ways_is_one_line(u):
    cut = [{"kind": "link", "from": "yard", "to": "village", "name": "바닷가 마을", "open": False},
           {"kind": "link", "from": "village", "to": "yard", "name": "등대 앞", "open": False}]
    assert change_lines(u, cut) == ["바닷가 마을과 등대 앞 사이의 길이 끊겼습니다"]
    assert change_lines(u, cut[:1]) == ["바닷가 마을로 가는 길이 끊겼습니다"]


def test_event_verbs_in_a_quote_are_not_claims():
    from src.lang.claims import claims
    u = STORIES["lighthouse"]
    assert any(a[0] == "fill" for _, a in claims(u, "녹슨 등대 문이 열렸습니다."))
    assert not any(a[0] == "fill" for _, a in claims(u, "\"녹슨 등대 문은 예전에 열렸지.\" 그가 말합니다."))


def test_arriving_somewhere_is_a_claim_on_where_you_are():
    from src.lang.claims import claims
    u = STORIES["lighthouse"]
    assert (True, ("at", "player", "yard")) in claims(u, "당신은 선착장을 지나 등대 앞마당으로 발을 내디뎠습니다.")
    assert not any(a[1] == "player" for _, a in claims(u, "윤슬이 등대 앞에 도착했습니다."))


def test_the_narrators_context_has_only_the_scene_and_no_numbers():
    from src.lang.context import render, scene
    from src.onto.log import Log
    from src.onto.universe import initial
    from src.onto.view import observe
    u = STORIES["lighthouse"]
    o = observe(u, initial(u, CREATION), Log())
    text = render(scene(u, o, {"player", "dock", "yunseul"}, {}))
    assert "도해" not in text and not any(c.isdigit() for c in text)
    assert "바닷가 마을에서 선착장으로" not in text and "선착장에서 바닷가 마을로" in text
    assert f"{u.name('deadline.1')}: 아직 멀었습니다" in text
    from src.onto.atoms import State
    s0 = initial(u, CREATION)
    yard = render(scene(u, observe(u, s0, Log()), {"player", "yard", "door"}, {}))
    assert u.name("door") + ":" not in yard and not any(c.isdigit() for c in yard)
    moved = {a for a in s0.atoms() if a[:2] not in (("fill", "door"), ("at", "player"))}
    s1 = State.of(moved | {("fill", "door", u.boxes("door")), ("at", "player", "yard")})
    assert f"{u.name('door')}: 뜻대로 되었습니다" in render(scene(u, observe(u, s1, Log()), {"player", "yard", "door"}, {}))


async def test_a_companion_who_will_not_go_everywhere_says_so_when_joining(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))
    u, g = svc.games[gid]
    come = {"kind": "follow", "id": "dohae", "name": "도해", "state": "start"}
    assert change_line(u, come) == "도해가 당신과 함께 다니기로 했지만 등대 앞, 등불실에는 가지 않습니다"
    assert change_line(u, {**come, "state": "stop"}) == "도해는 이제 당신을 따라다니지 않습니다"
    now = messages(replace(svc._turn_job(u, g, 1), joined=("dohae",)))[1]["content"].split(ko.HEAD["now"])[1]
    assert "도해는 등대 앞, 등불실에는 따라가지 않습니다" in now and u.agents["dohae"].fear.rstrip(".") in now


def test_a_tag_on_someone_takes_ege(u):
    spray = {"kind": "tag_add", "owner": "player", "name": "흩날리는 물보라"}
    assert change_line(u, spray) == "당신에게 흩날리는 물보라가 생겼습니다"
    assert change_line(u, {**spray, "owner": "dohae", "name": "굳은 입"}) == "도해에게 굳은 입이 생겼습니다"
    assert change_line(u, {**spray, "owner": "village", "name": "마을 봉화"}) == "바닷가 마을에 마을 봉화가 생겼습니다"


def test_repetition_cues_and_address():
    from src.narrate import ADDRESS, fresh_cue, repeated
    before = ["거친 파도가 절벽을 때리며 차가운 물보라를 뿌립니다."]
    assert repeated("거친 파도가 절벽을 때리며 흩어집니다.", before) == "거친파도가절벽을때리며"
    assert repeated("파도가 높습니다.", before) is None
    senses = ["젖은 밧줄 냄새", "말뚝에 부딪는 파도", "낮게 깔린 회색 구름"]
    assert fresh_cue(senses, ["젖은 밧줄의 비릿한 냄새가 납니다."]) == "말뚝에 부딪는 파도"
    assert fresh_cue(senses, []) == "젖은 밧줄 냄새"
    assert fresh_cue(senses, ["젖은 밧줄의 냄새. 말뚝에 부딪히는 파도. 낮게 깔린 회색 구름."]) is None
    assert ADDRESS.search("\"어머, 아저씨! 바다요?\"") and not ADDRESS.search("\"저 아저씨는 누구야?\"")


def test_worn_phrases_are_those_in_two_recent_narrations_aside_from_names_and_senses(u):
    from src.narrate import worn
    previous = ["파도가 등대를 집어삼킬 듯 몰아칩니다. 윤슬이 웃습니다.",
                "어둠이 바다를 집어삼킬 듯한 기세입니다. 윤슬이 웃습니다.",
                "젖은 밧줄 냄새가 납니다."]
    assert worn(u, previous) == ["집어삼킬 듯한"]
