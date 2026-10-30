from types import SimpleNamespace

from conftest import REPO
from src.interpret import Interpreter, lack, mentions, rules, squeeze, title_words
from src.locale import ko
from src.models.decision import ModelUnavailable
from src.onto.log import Log
from src.onto.universe import initial
from src.onto.view import observe
from src.rules.acts import parse
from src.service import GameService
from src.story.validate import load_all

STORIES = load_all(REPO / "scenarios")
CREATION = {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]}


class FakeDecision:

    def __init__(self, answers=None, fail=False):
        # a line is an act unless a test says otherwise, so the kind needs no narration-model reading
        self.answers, self.fail, self.asked = {"k": {"act": 1.0}, **(answers or {})}, fail, []

    async def decide(self, state, questions):
        self.asked.append((state, questions))
        if self.fail:
            raise ModelUnavailable("down")
        return {q: SimpleNamespace(probabilities=self.answers.get(q, {})) for q in questions}


class FakeLLM:
    def __init__(self, *replies):
        self.replies, self.prompts = replies, []       # one per call, the last one again after that

    async def pick(self, messages):
        self.prompts.append(messages)
        return self.replies[min(len(self.prompts), len(self.replies)) - 1]


async def game(tmp_path, decision, llm=None, moves=()):
    svc = GameService(STORIES, tmp_path, Interpreter(decision, llm), seeds=lambda: 7)
    out = await svc.create("r", "lighthouse", CREATION)
    gid, view = out["game_id"], out["view"]
    for i, a in enumerate(moves):
        view = (await svc.command(gid, {"request_id": f"m{i}", "revision": view["revision"], "action": a}))["view"]
    return svc, gid, view


async def say(svc, gid, view, text, rid="t1"):
    out = await svc.command(gid, {"request_id": rid, "revision": view["revision"], "text": text})
    card = out["view"]["card"]
    if card and card["kind"] == "move":     # leave for the way the sentence chose (engine.md 4.4)
        go = await svc.command(gid, {"request_id": f"{rid}.go", "revision": out["view"]["revision"],
                                     "card": card["id"], "pick": card["selected"]})
        return {**go, "steps": out["steps"] + go["steps"]}
    return out


def test_layer0_text_helpers():
    assert squeeze("마을로 간다.") == "마을로간다"
    assert mentions("문", "문을 연다") == 0 and mentions("문", "문서를 본다") == -1
    assert mentions("윤슬", "윤슬아 가자") == 0 and mentions("누렁이", "누렁아~ 이리온") == 0     # called by name
    assert mentions("누렁이", "누렁아지") == -1
    assert title_words("폐허로 가는 길") == ["폐허", "가는", "길"] and title_words("등대 뒤 담장") == ["등대", "담장"]
    assert mentions("윤슬", "윤슬에게 묻는다") == 0


async def test_impossible_and_meta_are_refused_without_a_model(tmp_path):
    decision = FakeDecision()
    svc, gid, view = await game(tmp_path, decision)
    out = await say(svc, gid, view, "휴대전화로 구조를 부른다")
    assert out["kind"] == "refused" and out["reason"] == "이 이야기에는 그런 것이 없습니다."
    out = await say(svc, gid, view, "게임 저장해 줘", "t2")
    assert out["kind"] == "refused" and not decision.asked


def test_story_words_that_contain_a_meta_word_stay_in_the_story():
    u = STORIES["lighthouse"]
    s = initial(u, CREATION)
    o, p = observe(u, s, Log()), {}
    for text in ("마을 저장고로 간다", "처음부터 차근차근 문을 살핀다", "규칙적으로 숨을 고른다"):
        assert rules(u, o, p, text) is None, text
    for text in ("저장해 줘", "처음부터 다시 할래", "게임 규칙 알려줘"):
        assert rules(u, o, p, text) == {"refused": ko.META_REPLY}, text


def test_typed_growth_points_to_its_card_only_when_there_is_growth():
    from src.onto.atoms import PLAYER, State
    u = STORIES["lighthouse"]
    s = initial(u, CREATION)
    assert rules(u, observe(u, s, Log()), {}, "성장? 재치 올릴래") is None
    grown = State.of([*(a for a in s.atoms() if a[:3] != ("stat", PLAYER, "growth")), ("stat", PLAYER, "growth", 1)])
    assert rules(u, observe(u, grown, Log()), {}, "성장? 재치 올릴래") == {"refused": ko.GROWTH_REPLY}


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
    assert set(decision.asked[0][1]) == {"k", "s1", "n"} and "예:" in decision.asked[0][1]["s1"]["criteria"]["go"]


async def test_a_line_to_the_person_here_is_small_talk_that_spends_no_time(tmp_path):
    # Kev would take a part, and every topic would roll: only an action may (engine.md 3.2, rule.md 4.1)
    decision = FakeDecision({"k": {"say": 0.8}, "s1": {"try": 0.9}, "n": {"1": 0.9}, "tone": {"threaten": 0.9}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"))
    out = await say(svc, gid, view, "먹을거 어디에 있어?")
    assert [s["action"] for s in out["steps"]] == ["talk:yunseul:chat"]       # a threat needs an act, so no tone
    assert len(decision.asked) == 1                                         # nothing left to ask
    assert out["view"]["player"]["beats"] == view["player"]["beats"]


async def test_a_line_to_no_one_or_to_oneself_is_only_narrated(tmp_path):
    for kind, moves, text in (("muse", (), "와 바람 개쎄네"), ("say", ("go:yard",), "아무도 없어요?")):
        decision = FakeDecision({"k": {kind: 0.9}, "s1": {"look": 0.9}, "n": {"1": 0.9}})
        svc, gid, view = await game(tmp_path / kind, decision, FakeLLM("1"), moves)
        out = await say(svc, gid, view, text)
        assert out["steps"][0]["action"] == "try:player:wits" and out["steps"][0]["result"] == "none"
        assert out["view"]["player"]["beats"] == view["player"]["beats"]


async def test_an_unsure_kind_is_the_narration_models_reading(tmp_path):
    decision = FakeDecision({"k": {"say": 0.6}, "s1": {"look": 0.9}, "n": {"1": 0.9}})
    llm = FakeLLM("3")                                           # muse
    svc, gid, view = await game(tmp_path, decision, llm)
    out = await say(svc, gid, view, "날씨 진짜 별로다")
    assert out["steps"][0]["action"] == "try:player:wits" and "어떤 말입니까" in llm.prompts[0][1]["content"]


async def test_words_to_an_animal_are_an_attempt_on_it(tmp_path):
    decision = FakeDecision({"k": {"say": 0.9}, "s1": {"try": 0.9}, "n": {"1": 0.9}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("4"), ("go:village", "talk:dohae:chat"))
    out = await say(svc, gid, view, "누렁아~ 이리온 쭈쭈")
    assert out["view"]["card"]["kind"] == "roll" and out["view"]["card"]["options"][0]["id"].startswith("try:hound:")


async def test_a_topic_is_offered_only_when_the_sentence_names_it(tmp_path):
    decision = FakeDecision({"k": {"act": 0.9}, "s1": {"talk": 0.9}, "n": {"1": 0.9}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("2"))
    view = (await say(svc, gid, view, "윤슬에게 먹을거 어디 있는지 묻는다"))["view"]
    assert "yunseul:t_wall" not in decision.asked[1][1]["intent"]["criteria"]
    decision.asked.clear()
    await say(svc, gid, view, "윤슬에게 담장 얘기 좀 해 달라고 한다", "t2")
    assert "yunseul:t_wall" in decision.asked[1][1]["intent"]["criteria"]


async def test_a_sentence_that_hands_a_thing_over_asks_first(tmp_path):
    decision = FakeDecision({"s1": {"give": 0.9}, "n": {"1": 0.9}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"))
    out = await say(svc, gid, view, "윤슬에게 아들의 편지를 건넨다")
    card = out["view"]["card"]
    assert card["kind"] == "confirm" and not out["steps"]
    assert [(x["id"], x["effects"]) for x in card["options"]] == \
        [("give:letter:yunseul", ["아들의 편지가 윤슬에게 감"]), ("show:letter:yunseul", [])]
    out = await svc.command(gid, {"request_id": "ok", "revision": out["view"]["revision"], "card": card["id"],
                                  "pick": "show:letter:yunseul"})
    assert [s["action"] for s in out["steps"]] == ["show:letter:yunseul"]
    assert out["view"]["card"] is None
    from src.jobs import turn_job
    assert turn_job(*svc.games[gid], out["turn"]).shown == ("아들의 편지",)       # the sentence said 건넨다


async def test_a_sentence_that_goes_with_someone_asks_them_first(tmp_path):
    decision = FakeDecision({"s1": {"go": 0.9}, "n": {"1": 0.9}, "intent": {"village": 0.9}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"))
    out = await svc.command(gid, {"request_id": "t1", "revision": view["revision"], "text": "윤슬과 같이 마을로 간다"})
    card = out["view"]["card"]
    assert card["kind"] == "move" and not out["steps"]                # it went alone, the second half dropped
    assert [(o["id"], o.get("with")) for o in card["options"]][:2] == \
        [("go:village", None), ("talk:yunseul:come+go:village", "윤슬")]
    assert card["selected"] == "talk:yunseul:come+go:village"
    out = await svc.command(gid, {"request_id": "w", "revision": out["view"]["revision"], "card": card["id"],
                                  "pick": card["selected"]})
    card = out["view"]["card"]
    assert card["kind"] == "roll" and card["plan"]["rest"] == ["바닷가 마을로 간다"]


async def test_a_sentence_that_skips_the_scene_asks_first(tmp_path):
    decision = FakeDecision({"s1": {"cut": 0.9}, "n": {"1": 0.9}, "intent": {"pass": 0.9}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"))
    out = await say(svc, gid, view, "날이 저물 때까지 그냥 기다린다")
    card = out["view"]["card"]
    assert card["kind"] == "confirm" and not out["steps"] and card["options"][0]["id"] == "cut:pass"
    assert card["options"][0]["effects"] == ["장면이 끝남", "다가오는 일들이 한 칸씩 다가옴"]


async def test_a_sentence_that_shows_a_thing_keeps_it(tmp_path):
    svc, gid, view = await game(tmp_path, FakeDecision({}), FakeLLM("1"))
    out = await say(svc, gid, view, "윤슬에게 아들의 편지를 보여준다")      # read as giving (play-4-talker 7)
    assert [s["action"] for s in out["steps"]] == ["show:letter:yunseul"] and out["view"]["card"] is None


async def test_several_actions_are_the_narration_models_list(tmp_path):
    decision = FakeDecision({"s1": {"go": 0.9}, "n": {"2": 0.8}, "tone": {"polite": 0.8},
                             "intent": {"dohae:chat": 0.9}})
    llm = FakeLLM("1, 1, 4")              # go, go (one action in two clauses), talk
    svc, gid, view = await game(tmp_path, decision, llm)
    out = await say(svc, gid, view, "마을로 가서 도해에게 말을 건다")
    assert [s["action"] for s in out["steps"]] == ["go:village", "talk:dohae:chat"]
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
    decision = FakeDecision({"s1": {"look": 0.6, "go": 0.3}, "n": {"1": 0.9}})     # under 0.7 is not sure
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"))
    out = await say(svc, gid, view, "음")
    assert out["steps"][0]["action"].startswith("go:")  # the narration model decides even against Kev's top answer
    # an unreadable reading leaves the player idle; one whose first step cannot happen here is refused
    for i, (reply, kind) in enumerate((("?", "turn"), ("9", "refused"))):
        decision = FakeDecision({"s1": {"look": 0.4, "go": 0.3}})
        svc, gid, view = await game(tmp_path / str(i), decision, FakeLLM(reply))
        out = await say(svc, gid, view, "음")
        assert out["kind"] == kind and len(decision.asked) == 1
    assert out["reason"] == "지금은 고를 갈림길이 없습니다." and out["view"]["revision"] == view["revision"]   # "9" is choose


async def test_every_schema_is_offered_and_an_impossible_one_needs_both_readings(tmp_path):
    # at the dock nothing lies to take, no fork waits and no tie can be recalled yet
    decision = FakeDecision({"s1": {"take": 0.8}, "n": {"1": 0.9}})
    llm = FakeLLM("7")
    svc, gid, view = await game(tmp_path, decision, llm)
    out = await say(svc, gid, view, "바닥의 돌멩이를 줍는다")
    say_opts = list(decision.asked[0][1]["s1"]["criteria"])
    assert sorted(say_opts) == sorted(("go", "look", "take", "give", "talk", "try", "declare", "cut", "choose"))
    assert say_opts.index("take") > say_opts.index("cut")      # what can happen here comes first
    assert len(llm.prompts) == 1                               # Kev sure of an impossible step is not enough
    assert out["kind"] == "refused" and out["reason"] == "여기에는 집을 수 있는 것이 없습니다."
    decision = FakeDecision({"s1": {"take": 0.8}, "n": {"1": 0.9}})
    svc, gid, view = await game(tmp_path / "b", decision, FakeLLM("2"))
    out = await say(svc, gid, view, "바닥을 살핀다")
    assert out["steps"][0]["action"].startswith("look:")       # the reading names a step that can happen


async def test_a_give_with_no_one_here_says_so_and_one_with_empty_hands_says_that(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeDecision(), moves=("go:yard",))
    u, g = await svc.load(gid)
    assert lack(u, observe(u, g.state, g.log), "give") == "여기에는 무언가를 건넬 사람이 없습니다."
    svc, gid, _ = await game(tmp_path / "b", FakeDecision(), moves=("give:letter:yunseul",))
    u, g = await svc.load(gid)
    assert g.state.where("letter") == "yunseul"
    assert lack(u, observe(u, g.state, g.log), "give") == "건넬 수 있는 것을 지니고 있지 않습니다."


async def test_going_where_the_player_is_moves_nowhere(tmp_path):
    # naming the dock, where the player stands, leaves the choice to both models: "to the dock" stays, "leaving it" goes
    for i, (text, pick, first) in enumerate((("부두로 간다", "3", None), ("선착장을 떠난다", "1", "go:village"))):
        decision = FakeDecision({"s1": {"go": 0.9}, "n": {"1": 0.9}, "intent": {"dock": 0.9}})
        svc, gid, view = await game(tmp_path / str(i), decision, FakeLLM(pick))
        out = await say(svc, gid, view, text)
        assert list(decision.asked[1][1]["intent"]["criteria"]) == ["village", "yard", "dock"]
        assert [s["action"] for s in out["steps"]][:1] == ([first] if first else [])
        if not first:
            assert out["kind"] == "refused" and out["reason"] == "이미 선착장에 있습니다."
    # a walk about the place names no place, so the answer is where one can go (play-3-explorer 9)
    decision = FakeDecision({"s1": {"go": 0.9}, "n": {"1": 0.9}, "intent": {"dock": 0.9}})
    svc, gid, view = await game(tmp_path / "about", decision, FakeLLM("3"))
    out = await say(svc, gid, view, "창고 뒤쪽으로 돌아가 본다")
    assert out["kind"] == "refused" and out["reason"] == "여기서 갈 수 있는 곳은 바닷가 마을, 등대 앞입니다."
    decision = FakeDecision({"s1": {"go": 0.9}, "n": {"1": 0.9}})
    svc, gid, view = await game(tmp_path / "exit", decision)
    out = await say(svc, gid, view, "선착장에서 마을로 간다")
    assert [s["action"] for s in out["steps"]] == ["go:village"] and len(decision.asked) == 1


async def test_the_place_the_player_is_in_is_a_destination_both_models_must_choose(tmp_path):
    # Kev is sure of the dock, where the player stands; the narration model's pick (third option: dock) decides
    for i, (pick, first) in enumerate((("3", "look:dock"), ("1", "go:village"))):
        decision = FakeDecision({"s1": {"go": 0.9}, "n": {"2": 0.9}, "intent": {"dock": 0.8}})
        llm = FakeLLM("1, 2", pick)
        svc, gid, view = await game(tmp_path / str(i), decision, llm)
        out = await say(svc, gid, view, "이 바닷가 앞마당으로 가서 둘러본다")
        assert list(decision.asked[1][1]["intent"]["criteria"]) == ["village", "yard", "dock"]
        assert len(llm.prompts) == 2 and out["steps"][0]["action"] == first   # staying runs the look at once


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
    assert card is not None and card["kind"] == "confirm", "a lie is high risk and waits for a confirm card"
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
                             "approach": {"finesse": 0.9}, "rely": {"r0": 0.05, "r1": 0.8, "none": 0.15}})
    svc, gid, view = await game(tmp_path, decision, moves=["go:village", "go:yard"])
    out = await say(svc, gid, view, "기계공 솜씨로 문을 비집어 연다")
    card = out["view"]["card"]
    # The named trait is kept without asking; the model kept the letter and dropped 뱃사람.
    assert [o["label"] for o in card["options"] if not o["forced"]] == ["기계공", "아들의 편지", "기대지 않음"]
    assert card["selected"] == "try:door:finesse;rely=trait:tinker"
    state, qs = decision.asked[-1]
    assert "기계공 솜씨로" in state and list(qs["rely"]["criteria"]) == ["r0", "r1", "none"]
    # The same attempt in other words keeps what was offered and asks only about 뱃사람 again.
    out = await say(svc, gid, out["view"], "문을 살살 비집어 연다", "s2")
    assert [o["label"] for o in out["view"]["card"]["options"] if not o["forced"]] == ["기계공", "아들의 편지", "기대지 않음"]
    state, qs = decision.asked[-1]
    assert "살살" in state and list(qs["rely"]["criteria"]) == ["r0", "none"]


async def test_story_links_and_edges_skip_the_question_and_a_silent_model_hides_nothing(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeDecision())
    u, g = await svc.load(gid)
    o, p, a = observe(u, g.state, g.log), g.presentation, parse("try:lamp:wits")
    values = ["trait:sailor", "thing:letter", "thing:oil", "tag:lamp:1", "tag:player:2"]
    sure = FakeDecision({"rely": {"none": 1.0}})
    # an edge is offered wherever in reach it lies
    assert await Interpreter(sure).relevant(u, o, p, a, values, None, None) == ["thing:oil", "tag:lamp:1", "tag:player:2"]
    assert list(sure.asked[0][1]["rely"]["criteria"]) == ["r0", "r1", "none"]
    assert await Interpreter(FakeDecision(fail=True)).relevant(u, o, p, a, values, None, None) == values


async def test_a_fork_in_the_scene_lends_its_choices_as_the_examples_of_choose():
    from src.story.evals import interpret, replay
    u = STORIES["lighthouse"]
    decision = FakeDecision({"s1": {"choose": 0.9}, "n": {"1": 0.9}})
    await interpret(Interpreter(decision), u, replay(u, {"path": 0, "step": 4, "then": [{"do": "try:lens:finesse", "roll": [6, 6, 0]}]}),
                    "등불에 기름을 붓는다")
    choose = decision.asked[0][1]["s1"]["criteria"]["choose"]
    assert "기름을 모두 등불에 붓는다" in choose and "절반을 마을 봉화에 남긴다" in choose
    decision = FakeDecision({"s1": {"look": 0.9}, "n": {"1": 0.9}})
    await interpret(Interpreter(decision), u, replay(u, {"path": 0, "step": 0}), "둘러본다")
    assert "기름" not in decision.asked[0][1]["s1"]["criteria"]["choose"]


async def test_a_guarded_target_offers_the_ways_around_the_guard(tmp_path):
    """engine.md 4.1 detour: five refusals in a row left the player talking to a guarded man (qa_test/runs/loop-1)."""
    decision = FakeDecision({"s1": {"try": 0.9}, "n": {"1": 0.9}, "strain": {"natural": 0.9}})
    # talking to 도해 runs into the hidden dog, which is then in sight
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"), moves=["go:village", "talk:dohae:chat"])
    assert "hound" in [x["id"] for x in view["scene"]["obstacles"]]
    out = await say(svc, gid, view, "ㅋㅋㅋ 도해의 아구창을 날린다")
    # not a try on another target (the letter) but the guard and the ways around it
    card = out["view"]["card"]
    assert out["kind"] == "card" and card["kind"] == "clarify" and not out["steps"]
    assert card["question"] == "사나운 누렁이가 도해를 막고 있습니다. 어떻게 할까요?"
    # the bait needs the dried fish in hand, so only the soothing holds
    assert [o["label"] for o in card["options"]] == ["낮은 목소리로 달래며 다가간다"]
    out = await svc.command(gid, {"request_id": "pick", "revision": out["view"]["revision"], "card": card["id"],
                                  "pick": card["options"][0]["id"]})
    assert out["view"]["card"]["kind"] == "roll" and out["view"]["card"]["selected"] == "try:hound:charm"
    decision.answers["s1"] = {"talk": 0.9}
    out = await say(svc, gid, out["view"], "도해에게 이야기", "t2")
    assert out["view"]["card"]["question"].startswith("사나운 누렁이가 도해를 막고 있습니다.")
    # someone met elsewhere: the reader may well walk there, but a talk step says where they are not
    u, g = svc.games[gid]
    st = await svc.interpreter.fill(u, g, {"schema": "talk", "text": "윤슬에게 등대에 대해 묻는다", "fixed": {}})
    assert st == {"refused": "윤슬은 여기 없습니다."}
    st = await svc.interpreter.fill(u, g, {"schema": "talk", "text": "왜 못하지?", "fixed": {}})
    assert st["clarify"]["slot"] == "detour" and set(st["clarify"]["resume"]) == {"try:hound:charm"}
    # the guard keeps things from being handed over too
    out = await svc.command(gid, {"request_id": "g", "revision": out["view"]["revision"], "action": "give:letter:dohae"})
    assert out["kind"] == "refused"
    decision.answers["s1"] = {"try": 0.9}
    out = await say(svc, gid, out["view"], "도해 앞의 누렁이를 낮은 목소리로 달랜다", "t4")
    assert out["kind"] != "refused"


async def test_a_blocked_way_offers_only_the_ways_around_that_hold(tmp_path):
    decision = FakeDecision({"s1": {"go": 0.9}, "n": {"1": 0.9}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"), moves=["go:yard"])
    for i, text in enumerate(["등불 방으로 올라간다", "날아서 꼭대기 등불실로"]):
        view = (await say(svc, gid, view, text, f"t{i}"))["view"]
        card = view["card"]
        assert card["question"] == "녹슨 등대 문이 등불실로 가는 길을 막고 있습니다. 어떻게 할까요?"
        # no key and no word of the wall yet: only the shoulder
        assert [o["label"] for o in card["options"]] == ["어깨로 문을 들이받는다"]


async def test_giving_what_the_player_does_not_hold_says_so(tmp_path):
    svc, gid, _ = await game(tmp_path, FakeDecision(), moves=["give:letter:yunseul"])
    u, g = svc.games[gid]
    st = await svc.interpreter.fill(u, g, {"schema": "give", "text": "윤슬에게 편지를 다시 건넨다", "fixed": {}})
    assert st == {"refused": "아들의 편지를 지니고 있지 않습니다."}


async def test_the_decision_models_context_names_only_who_is_in_sight(tmp_path):
    decision = FakeDecision({"s1": {"talk": 0.9}, "n": {"1": 0.9}})
    svc, gid, view = await game(tmp_path, decision, FakeLLM("1"), moves=["go:village"])
    await say(svc, gid, view, "도해에게 인사한다")
    state = decision.asked[1][0]
    # 윤슬 stayed at the dock and 백 is not brought in yet, yet both regard the player (decision-2/parity-context.txt).
    assert "도해는 당신을" in state and "윤슬" not in state and "백은" not in state
