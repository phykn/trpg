"""Interpretation layers and δ_θ with stand-in models (engine.md 3, 4.1)."""

from types import SimpleNamespace

from conftest import REPO
from src.interpret import Interpreter, mentions, squeeze
from src.models.kev import ModelUnavailable
from src.service import GameService
from src.story.validate import load_all

STORIES = load_all(REPO / "scenarios")
CREATION = {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]}


class FakeKev:
    """Answers each question id with fixed probabilities; records the questions it was asked."""

    def __init__(self, answers=None, fail=False):
        self.answers, self.fail, self.asked = answers or {}, fail, []

    async def decide(self, state, questions):
        self.asked.append((state, questions))
        if self.fail:
            raise ModelUnavailable("down")
        return {q: SimpleNamespace(probabilities=self.answers.get(q, {})) for q in questions}


class FakeQwen:
    def __init__(self, reply):
        self.reply = reply

    async def pick(self, messages):
        return self.reply


async def game(tmp_path, kev, qwen=None, moves=()):
    svc = GameService(STORIES, tmp_path, Interpreter(kev, qwen), seeds=lambda: 7)
    out = await svc.create("r", "lighthouse", CREATION)
    gid, view = out["game_id"], out["view"]
    for i, a in enumerate(moves):
        view = (await svc.command(gid, {"request_id": f"m{i}", "revision": view["revision"], "action": a}))["view"]
    return svc, gid, view


async def say(svc, gid, view, text, rid="t1"):
    return await svc.command(gid, {"request_id": rid, "revision": view["revision"], "text": text})


def test_layer0_text_helpers():
    assert squeeze("마을로 간다.") == "마을로간다"
    assert mentions("문", "문을 연다") == 0 and mentions("문", "문서를 본다") == -1
    assert mentions("윤슬", "윤슬에게 묻는다") == 0


async def test_impossible_and_meta_are_refused_without_a_model(tmp_path):
    kev = FakeKev()
    svc, gid, view = await game(tmp_path, kev)
    out = await say(svc, gid, view, "휴대전화로 구조를 부른다")
    assert out["kind"] == "refused" and out["reason"] == "이 세계에는 없는 것입니다."
    out = await say(svc, gid, view, "게임 저장해 줘", "t2")
    assert out["kind"] == "refused" and not kev.asked


async def test_exact_label_is_a_plan_without_a_model(tmp_path):
    kev = FakeKev()
    svc, gid, view = await game(tmp_path, kev)
    out = await say(svc, gid, view, "바닷가 마을로 간다")
    assert out["steps"][0]["action"] == "go:village" and not kev.asked


async def test_sure_schema_and_named_place(tmp_path):
    kev = FakeKev({"s1": {"go": 0.9}, "s2": {"end": 0.8}})
    svc, gid, view = await game(tmp_path, kev)
    out = await say(svc, gid, view, "마을 쪽으로 걸어가 봐야겠다")
    assert [s["action"] for s in out["steps"]] == ["go:village"]
    assert len(kev.asked) == 1                    # the named place fills the slot; no layer-2 call


async def test_two_steps_ask_the_second_slot_after_the_first_runs(tmp_path):
    kev = FakeKev({"s1": {"go": 0.9}, "s2": {"talk": 0.7}, "s3": {"end": 0.9}, "tone": {"friendly": 0.8},
                   "intent": {"dohae:chat": 0.9}})
    svc, gid, view = await game(tmp_path, kev)
    out = await say(svc, gid, view, "마을로 가서 도해에게 말을 건다")
    assert [s["action"] for s in out["steps"]] == ["go:village", "talk:dohae:chat;tone=friendly"]
    state, qs = kev.asked[-1]
    assert set(qs) == {"intent", "tone"} and "도해의 말투" in state
    assert all(k.startswith("dohae:") for k in qs["intent"]["criteria"])


async def test_unsure_first_step_takes_a_second_opinion(tmp_path):
    kev = FakeKev({"s1": {"look": 0.4, "go": 0.3}})
    svc, gid, view = await game(tmp_path, kev, FakeQwen("2"))
    out = await say(svc, gid, view, "주위를 둘러본다")
    first = out["steps"][0]["action"] if out["steps"] else out["view"]["card"]
    assert first != "try:player:wits"
    kev2 = FakeKev({"s1": {"look": 0.4, "go": 0.3}})
    svc, gid, view = await game(tmp_path / "b", kev2, FakeQwen("1"))
    out = await say(svc, gid, view, "음")
    assert [s["action"] for s in out["steps"]] == ["try:player:wits"] and len(kev2.asked) == 1


async def test_model_failure_is_all_zero_and_changes_nothing(tmp_path):
    svc, gid, view = await game(tmp_path, FakeKev(fail=True))
    out = await say(svc, gid, view, "어딘가로 간다")
    assert [s["action"] for s in out["steps"]] == ["try:player:wits"]
    assert out["steps"][0]["changes"] == []


async def test_unsure_intent_makes_a_clarify_card_and_a_pick_resumes(tmp_path):
    kev = FakeKev({"s1": {"look": 0.9}, "s2": {"end": 0.9}, "intent": {"dock": 0.3, "yunseul": 0.25, "letter": 0.2}})
    svc, gid, view = await game(tmp_path, kev)
    out = await say(svc, gid, view, "저걸 자세히 본다")
    card = out["view"]["card"]
    assert out["kind"] == "card" and card["kind"] == "clarify"
    assert [o["id"] for o in card["options"]] == ["dock", "yunseul", "letter"]
    done = await svc.command(gid, {"request_id": "p", "revision": out["view"]["revision"], "card": card["id"],
                                   "pick": "yunseul"})
    assert [s["action"] for s in done["steps"]] == ["look:yunseul"] and done["view"]["card"] is None


async def test_try_reads_cues_and_refuses_the_impossible(tmp_path):
    kev = FakeKev({"s1": {"try": 0.9}, "s2": {"end": 0.9}, "strain": {"natural": 0.9}})
    svc, gid, view = await game(tmp_path, kev, moves=["go:village", "go:yard"])
    out = await say(svc, gid, view, "손재주로 문의 자물쇠를 살살 따 본다")
    card = out["view"]["card"]
    assert card["kind"] == "roll" and card["selected"] == "try:door:finesse;rely=trait:tinker"
    assert [s["label"] for s in card["echo"]["slots"]] == ["녹슨 등대 문", "솜씨"]
    assert "approach" not in kev.asked[-1][1]
    kev.answers["strain"] = {"impossible": 0.8}
    out = await say(svc, gid, out["view"], "문을 단숨에 날려 버린다", "t2")
    assert out["kind"] == "refused" and out["reason"] == "이 장면에서는 할 수 없는 일입니다."


async def test_unsure_judgment_falls_back_to_neutral(tmp_path):
    kev = FakeKev({"s1": {"talk": 0.9}, "s2": {"end": 0.9}, "intent": {"yunseul:chat": 0.9},
                   "tone": {"threaten": 0.4}})
    svc, gid, view = await game(tmp_path, kev)
    out = await say(svc, gid, view, "윤슬에게 말을 건다")
    assert out["steps"][0]["action"] == "talk:yunseul:chat"


async def test_a_claim_is_asked_only_after_a_deceiving_tone(tmp_path):
    kev = FakeKev({"s1": {"talk": 0.9}, "s2": {"end": 0.9}, "intent": {"dohae:chat": 0.9},
                   "tone": {"deceive": 0.8}, "claim": {"c_keeper": 0.7}})
    svc, gid, view = await game(tmp_path, kev, moves=["go:village"])
    out = await say(svc, gid, view, "도해에게 내가 새 등대지기라고 둘러댄다")
    assert [set(q) for _, q in kev.asked[1:]] == [{"intent", "tone"}, {"claim"}]
    card = out["view"]["card"]
    assert card["plan"]["step"]["action"] == "talk:dohae:chat;claim=c_keeper;tone=deceive"
