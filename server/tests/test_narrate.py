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
from src.narrate import Narrator, change_line, sentences_of, split
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
    assert sentences_of("하나입니다. 둘입니다! \"셋.\" 넷입니다") == ["하나입니다.", "둘입니다!", "\"셋.\"", "넷입니다"]
    assert split("문이 열린다.\n태그: 젖은 발\n[문맥]\n- 사실") == ("문이 열립니다.", ["젖은 발"])
    assert split("등대 앞에 섰습니다. 태그: 흩날리는 물보라") == ("등대 앞에 섰습니다.", ["흩날리는 물보라"])
    assert polite("그가 \"간다\"고 말했다.") == "그가 \"간다\"고 말했습니다."


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
    narr = await events(svc, gid, n)
    assert narr[-2]["type"] == "text"
    assert "160자" in llm.calls[-1][0]["content"]
    got = [e async for e in await svc.recap(gid, 1)]
    assert got[-2]["type"] == "text" and "되짚는" in llm.calls[-1][1]["content"]
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


async def test_a_person_named_in_delta_or_here_may_act(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeLLM(GOOD))
    u, g = svc.games[gid]
    job = replace(svc._turn_job(u, g, 1), delta=["윤슬이 기름통을 얻었습니다"])
    said = ["윤슬이 당신의 젖은 소매를 가볍게 스칩니다.", "도해가 낮게 기침합니다.", "\"윤슬이 온다\"고 누가 외칩니다."]
    per, _ = svc.narrator.rules(job, said, [])
    assert per == {}
    per, _ = svc.narrator.rules(replace(job, delta=[]), said, [])
    assert list(per) == [0]


def test_a_lowered_threat_recedes_instead_of_approaching(u):
    up = {"kind": "clock", "id": "hound", "name": "사냥개", "from": 0, "to": 1}
    assert change_line(u, up).endswith("다가왔습니다")
    assert change_line(u, {**up, "from": 1, "to": 0}).endswith("물러났습니다")
