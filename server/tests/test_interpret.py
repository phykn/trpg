from types import SimpleNamespace

from conftest import REPO
from src.interpret import Interpreter, mentions, squeeze
from src.models.decision import ModelUnavailable
from src.onto.view import observe
from src.rules.acts import parse
from src.service import GameService
from src.story.validate import load_all

STORIES = load_all(REPO / "scenarios")
CREATION = {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]}


class FakeDecision:

    def __init__(self, answers=None, fail=False):
        self.answers, self.fail, self.asked = answers or {}, fail, []

    async def decide(self, state, questions):
        self.asked.append((state, questions))
        if self.fail:
            raise ModelUnavailable("down")
        return {q: SimpleNamespace(probabilities=self.answers.get(q, {})) for q in questions}


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    async def pick(self, messages):
        self.prompts.append(messages)
        return self.reply


async def game(tmp_path, decision, llm=None, moves=()):
    svc = GameService(STORIES, tmp_path, Interpreter(decision, llm), seeds=lambda: 7)
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
    decision = FakeDecision()
    svc, gid, view = await game(tmp_path, decision)
    out = await say(svc, gid, view, "휴대전화로 구조를 부른다")
    assert out["kind"] == "refused" and out["reason"] == "이 세계에는 없는 것입니다."
    out = await say(svc, gid, view, "게임 저장해 줘", "t2")
    assert out["kind"] == "refused" and not decision.asked


async def test_exact_label_is_a_plan_without_a_model(tmp_path):
    decision = FakeDecision()
    svc, gid, view = await game(tmp_path, decision)
    out = await say(svc, gid, view, "바닷가 마을로 간다")
    assert out["steps"][0]["action"] == "go:village" and not decision.asked


async def test_sure_schema_and_named_place(tmp_path):
    decision = FakeDecision({"s1": {"go": 0.9}, "n": {"1": 0.7}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1, 5"))
    out = await say(svc, gid, view, "마을 쪽으로 걸어가 봐야겠다")
    assert [s["action"] for s in out["steps"]] == ["go:village"]    # one sure action needs no reading
    assert len(decision.asked) == 1                    # the named place fills the slot; no layer-2 call
    assert set(decision.asked[0][1]) == {"s1", "n"} and "예:" in decision.asked[0][1]["s1"]["criteria"]["go"]


async def test_several_actions_are_the_narration_models_list(tmp_path):
    decision = FakeDecision({"s1": {"go": 0.9}, "n": {"2": 0.8}, "tone": {"friendly": 0.8},
                             "intent": {"dohae:chat": 0.9}})
    llm = FakeLLM("1, 1, 4")              # go, go (one action in two clauses), talk
    svc, gid, view = await game(tmp_path, decision, llm)
    out = await say(svc, gid, view, "마을로 가서 도해에게 말을 건다")
    assert [s["action"] for s in out["steps"]] == ["go:village", "talk:dohae:chat;tone=friendly"]
    state, qs = decision.asked[-1]                     # the second step's slots are asked after the first runs
    assert set(qs) == {"intent", "tone"} and "도해의 말투" in state
    assert all(k.startswith("dohae:") for k in qs["intent"]["criteria"])
    assert llm.prompts[0][1]["content"].startswith("플레이어 문장: 마을로 가서")


async def test_a_list_of_one_keeps_kevs_sure_step(tmp_path):
    decision = FakeDecision({"s1": {"go": 0.9}, "n": {"2": 0.8}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("2"))
    out = await say(svc, gid, view, "마을 쪽으로 서둘러 걸어 내려간다")
    assert [s["action"] for s in out["steps"]] == ["go:village"]


async def test_unsure_first_step_is_the_narration_models(tmp_path):
    decision = FakeDecision({"s1": {"look": 0.4, "go": 0.3}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"))
    out = await say(svc, gid, view, "음")
    assert out["steps"][0]["action"].startswith("go:")  # the narration model decides even against Kev's top answer
    # an unreadable reading, or one whose first step cannot happen here, leaves the player idle
    for i, reply in enumerate(("?", "9")):
        decision = FakeDecision({"s1": {"look": 0.4, "go": 0.3}})
        svc, gid, view = await game(tmp_path / str(i), decision, FakeLLM(reply))
        out = await say(svc, gid, view, "음")
        assert [s["action"] for s in out["steps"]] == ["try:player:wits"] and len(decision.asked) == 1


async def test_model_failure_is_all_zero_and_changes_nothing(tmp_path):
    svc, gid, view = await game(tmp_path, FakeDecision(fail=True))
    out = await say(svc, gid, view, "어딘가로 간다")
    assert [s["action"] for s in out["steps"]] == ["try:player:wits"]
    assert out["steps"][0]["changes"] == []


async def test_unsure_intent_makes_a_clarify_card_and_a_pick_resumes(tmp_path):
    decision = FakeDecision({"s1": {"look": 0.9}, "intent": {"dock": 0.3, "yunseul": 0.25, "letter": 0.2}})
    svc, gid, view = await game(tmp_path, decision)
    out = await say(svc, gid, view, "저걸 자세히 본다")
    card = out["view"]["card"]
    assert out["kind"] == "card" and card["kind"] == "clarify"
    assert [o["id"] for o in card["options"]] == ["dock", "yunseul", "letter"]
    done = await svc.command(gid, {"request_id": "p", "revision": out["view"]["revision"], "card": card["id"],
                                   "pick": "yunseul"})
    assert [s["action"] for s in done["steps"]] == ["look:yunseul"] and done["view"]["card"] is None


async def test_the_narration_model_picks_an_unsure_intent_before_the_player_is_asked(tmp_path):
    decision = FakeDecision({"s1": {"look": 0.9}, "intent": {"dock": 0.3, "yunseul": 0.25, "letter": 0.2}})
    llm = FakeLLM("1")
    svc, gid, view = await game(tmp_path, decision, llm)
    out = await say(svc, gid, view, "저걸 자세히 본다")
    assert out["steps"][0]["action"].startswith("look:") and out["view"]["card"] is None
    state, qs = decision.asked[-1]
    prompt = llm.prompts[0][1]["content"]
    assert prompt.startswith(state) and qs["intent"]["instructions"] in prompt


async def test_try_reads_cues_and_refuses_the_impossible(tmp_path):
    decision = FakeDecision({"s1": {"try": 0.9}, "strain": {"natural": 0.9}})
    svc, gid, view = await game(tmp_path, decision, moves=["go:village", "go:yard"])
    out = await say(svc, gid, view, "기계공의 손으로 문의 자물쇠를 살살 따 본다")
    card = out["view"]["card"]
    assert card["kind"] == "roll" and card["selected"] == "try:door:finesse;rely=trait:tinker"
    assert [s["label"] for s in card["echo"]["slots"]] == ["녹슨 등대 문", "솜씨"]
    assert "approach" not in decision.asked[-1][1]
    decision.answers["strain"] = {"impossible": 0.8}
    out = await say(svc, gid, out["view"], "문을 단숨에 날려 버린다", "t2")
    assert out["kind"] == "refused" and out["reason"] == "이 장면에서는 할 수 없는 일입니다."


async def test_unsure_judgment_falls_back_to_neutral(tmp_path):
    decision = FakeDecision({"s1": {"talk": 0.9}, "intent": {"yunseul:chat": 0.9},
                   "tone": {"threaten": 0.4}})
    svc, gid, view = await game(tmp_path, decision)
    out = await say(svc, gid, view, "윤슬에게 말을 건다")
    assert out["steps"][0]["action"] == "talk:yunseul:chat"


async def test_a_claim_is_asked_only_after_a_deceiving_tone(tmp_path):
    decision = FakeDecision({"s1": {"talk": 0.9}, "intent": {"dohae:chat": 0.9},
                   "tone": {"deceive": 0.8}, "c_keeper": {"true": 0.7, "false": 0.3}})
    svc, gid, view = await game(tmp_path, decision, moves=["go:village"])
    out = await say(svc, gid, view, "도해에게 내가 새 등대지기라고 둘러댄다")
    assert [set(q) for _, q in decision.asked[1:]] == [{"intent", "tone"}, {"c_keeper"}]
    assert decision.asked[-1][1]["c_keeper"]["type"] == "noul"
    card = out["view"]["card"]
    assert card["plan"]["step"]["action"] == "talk:dohae:chat;claim=c_keeper;tone=deceive"


async def test_an_unclear_approach_is_picked_or_takes_the_strongest_stat(tmp_path):
    decision = FakeDecision({"s1": {"try": 0.9}, "strain": {"natural": 0.9},
                             "approach": {"force": 0.3, "wits": 0.3}})
    svc, gid, view = await game(tmp_path, decision, moves=["go:village", "go:yard"])
    out = await say(svc, gid, view, "문을 열어 본다")
    card = out["view"]["card"]
    assert card["kind"] == "roll" and card["plan"]["step"]["action"] == "try:door:finesse"
    # with a narration model, its pick: force, finesse, wits, charm
    svc, gid, view = await game(tmp_path / "b", decision, FakeLLM("3"), moves=["go:village", "go:yard"])
    out = await say(svc, gid, view, "문을 열어 본다")
    assert out["view"]["card"]["plan"]["step"]["action"] == "try:door:wits"


async def test_the_narration_model_picks_target_and_approach_over_a_sure_kev(tmp_path):
    decision = FakeDecision({"s1": {"try": 0.9}, "strain": {"natural": 0.9}, "target": {"player": 0.9},
                             "approach": {"charm": 0.9}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"), moves=["go:village", "go:yard"])
    out = await say(svc, gid, view, "문을 밀어 본다")
    assert out["view"]["card"]["plan"]["step"]["action"] == "try:door:force"


async def test_the_roll_card_keeps_only_the_reliances_the_model_sees_helping(tmp_path):
    decision = FakeDecision({"s1": {"try": 0.9}, "strain": {"natural": 0.9},
                             "approach": {"finesse": 0.9}, "rely": {"r1": 0.8, "r2": 0.05, "none": 0.15}})
    svc, gid, view = await game(tmp_path, decision, moves=["go:village", "go:yard"])
    out = await say(svc, gid, view, "기계공 솜씨로 문을 비집어 연다")
    card = out["view"]["card"]
    assert [o["label"] for o in card["options"]] == ["기계공", "기대지 않음"]
    assert card["selected"] == "try:door:finesse;rely=trait:tinker"
    state, qs = decision.asked[-1]
    assert "기계공 솜씨로" in state and list(qs["rely"]["criteria"]) == ["r0", "r1", "r2", "none"]


async def test_story_links_skip_the_question_and_a_silent_model_hides_nothing(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeDecision())
    u, g = await svc.load(gid)
    o, p, a = observe(u, g.state, g.log), g.presentation, parse("try:lamp:wits")
    values = ["trait:sailor", "thing:letter", "thing:oil", "tag:lamp:1"]
    sure = FakeDecision({"rely": {"none": 1.0}})
    assert await Interpreter(sure).relevant(u, o, p, a, values, None) == ["thing:oil", "tag:lamp:1"]
    assert list(sure.asked[0][1]["rely"]["criteria"]) == ["r0", "r1", "none"]
    assert await Interpreter(FakeDecision(fail=True)).relevant(u, o, p, a, values, None) == values
