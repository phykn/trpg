from types import SimpleNamespace

from conftest import REPO
from src.interpret import Interpreter
from src.story.evals import gate, interpret, near, replay, report, score
from src.story.validate import load_all

STORIES = load_all(REPO / "scenarios")


def row(n, ok, known=None, lost=0, fragile=()):
    return {"n": n, "text": f"문장 {n}", "expect": "look", "got": [], "kind": "plan", "ok": ok, "known": known,
            "lost": lost, "fragile": list(fragile)}


def test_a_failure_without_known_fails_the_run_and_a_known_one_does_not(capsys):
    g = gate([row(1, True), row(2, False, known="1층이 읽지 못함")])
    assert not g["regressions"] and not g["fixes"] and report(g) == 0
    g = gate([row(1, False), row(2, False, known="1층이 읽지 못함")])
    assert [r["n"] for r in g["regressions"]] == [1] and report(g) == 1
    assert "regression  1 문장 1" in capsys.readouterr().out


def test_a_known_case_that_passes_is_a_fix_that_asks_to_drop_the_mark(capsys):
    g = gate([row(1, True, known="2층이 편지를 고름")])
    assert [r["n"] for r in g["fixes"]] == [1] and report(g) == 0
    assert "drop its known (2층이 편지를 고름)" in capsys.readouterr().out


def test_a_swap_that_keeps_the_count_still_fails():
    # one known miss now passes and another case now fails: the same accuracy, but a regression
    before = [row(1, True), row(2, False, known="x")]
    after = [row(1, False), row(2, True, known="x")]
    assert sum(r["ok"] for r in before) == sum(r["ok"] for r in after)
    g = gate(after)
    assert [r["n"] for r in g["regressions"]] == [1] and [r["n"] for r in g["fixes"]] == [2] and report(g) == 1


def test_a_case_a_model_left_unanswered_fails_the_run_even_when_it_passes():
    g = gate([row(1, True, lost=1), row(2, False, known="x", lost=2)])
    assert [r["n"] for r in g["unanswered"]] == [1, 2] and not g["regressions"] and report(g) == 1


def test_scores():
    got = {"kind": "plan", "steps": ["try:player:wits (idle)"]}
    assert score("idle", got) and not score("try", got) and not score("try:player:wits", got)
    got = {"kind": "plan", "steps": ["go:village", "talk:dohae:chat"]}
    assert score("go", got) and score("go:village", got) and score(["go:village", "talk:dohae:chat"], got)
    assert not score(["go:village", "talk:dohae:t_oil"], got) and not score("idle", got)
    assert score("clarify", {"kind": "clarify", "steps": []}) and score("refused", {"kind": "refused", "steps": []})


def call(**answers):
    questions = {k: {"type": "noul" if k.startswith("c_") else "choice",
                     "criteria": {"r0": "특성 '기계공'", "r1": "지닌 물건 '편지'"} if k == "rely" else {}}
                 for k in answers}
    return {"questions": questions, "answers": answers}


def test_fragile_answers_lie_within_005_of_the_threshold_that_decides_them():
    calls = [
        call(s1={"go": 0.72, "look": 0.28}, n={"1": 0.51, "2": 0.49}),
        call(intent={"yard": 0.501, "dock": 0.499}, tone={"polite": 0.52, "threaten": 0.48},
             strain={"forced": 0.46, "natural": 0.54}, target={"door": 0.5}, approach={"wits": 0.5}),
        call(c_keeper={"true": 0.53, "false": 0.47}, c_other={"true": 0.2, "false": 0.8}),
        call(rely={"r0": 0.12, "r1": 0.3, "none": 0.58}),
    ]
    got = [(m["q"], m["option"], m["theta"]) for m in near(calls, 0.5, 0.7)]
    # the count has no threshold, a neutral tone or strain is ν₀ either way, and the narration model decides the
    # target and approach
    assert got == [("s1", "go", 0.7), ("intent", "yard", 0.5), ("c_keeper", "true", 0.5), ("rely", "특성 '기계공'", 0.1)]
    assert near([call(s1={"go": 0.9}), call(strain={"forced": 0.62}), call(s1={})], 0.5, 0.7) == []


class Fake:
    def __init__(self, answers):
        self.answers = answers

    async def decide(self, state, questions):
        return {q: SimpleNamespace(probabilities=self.answers.get(q, {})) for q in questions}


async def test_a_case_with_relies_asks_what_the_first_roll_card_offers():
    u = STORIES["lighthouse"]
    # at the door: the traits sailor and tinker and the letter are asked, in that order
    it = Interpreter(Fake({"s1": {"try": 0.9}, "n": {"1": 0.9}, "target": {"door": 0.9}, "strain": {"natural": 0.9},
                           "rely": {"r0": 0.01, "r1": 0.7, "r2": 0.05, "none": 0.24}}))
    got = await interpret(it, u, replay(u, {"path": 0, "step": 2}), "녹슨 자물쇠를 살살 따 본다", card=True)
    assert got["steps"] == ["try:door:finesse"] and got["relies"] == ["trait:tinker"]
    assert "rely" in got["calls"][-1]["questions"]
    got = await interpret(it, u, replay(u, {"path": 0, "step": 2}), "녹슨 자물쇠를 살살 따 본다")
    assert got["relies"] is None and all("rely" not in c["questions"] for c in got["calls"])
    # no step rolls
    it = Interpreter(Fake({"s1": {"look": 0.9}, "n": {"1": 0.9}, "intent": {"door": 0.9}}))
    got = await interpret(it, u, replay(u, {"path": 0, "step": 2}), "문을 살펴본다", card=True)
    assert got["steps"] == ["look:door"] and got["relies"] is None


def test_a_step_that_rolls_nothing_replays_without_dice(u):
    """A witness step {do} without roll is valid where the action rolls nothing (V5), so a replay takes it too."""
    run = replay(u, {"path": 0, "step": 0, "then": [{"do": "go:village"}]})
    assert run.s.where("player") == "village"


class Planned:
    """An interpreter that reads every sentence as the given plan."""

    def __init__(self, plan):
        self.plan_, self.calls = plan, []

    async def plan(self, u, g, text):
        return {"plan": self.plan_}


async def test_a_rolled_step_runs_with_the_reliance_its_card_would_open_with(u):
    """The service's roll card selects the hinted reliance, so the step that runs spends it (engine.md 4.2)."""
    run = replay(u, {"path": 0, "step": 2})
    got = await interpret(Planned([{"action": "try:door:finesse", "rely": "trait:tinker"}]), u, run, "자물쇠를 딴다")
    assert got["steps"] == ["try:door:finesse;rely=trait:tinker"]
    assert run.s.has("spent", "player", "tinker")

