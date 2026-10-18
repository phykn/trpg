from conftest import FakeKev, choice, noul
from src.interpret import Clarify, Rejected, Steps, assemble, interpret, questions
from src.rules import dsl
from src.rules.candidates import candidates
from src.scene.build import build
from src.world.state import ActionStep, ImproviseStep, TalkStep


def ask(story, state):
    return questions(story, state, build(story, state), candidates(story, state))


def test_questions_offer_only_kev_candidates_and_skip_single_options(story, state):
    q = ask(story, state)
    options = q["s1"]["criteria"]
    assert "move:base" in options and "improvise" in options and "none" in options
    assert not any(k.startswith(("solve:", "use_tag:", "topic:")) for k in options)
    assert "s1.uses.tag" not in q, "no edge tags, so the question has only 'none'"
    assert "s1.approach" in q and "s1.check" in q
    assert set(q["talk.topic"]["criteria"]) == {"topic_key_mira", "topic_lamp_mira", "topic_key_doha", "chat"}


def test_target_options_include_obstacles_and_snags(story, state):
    out = []
    dsl.move(state, "player", "base", out)
    snag = dsl.add_tag(state, "snag", "door", out)
    targets = ask(story, state)["s1.target"]["criteria"]
    assert {"door", snag.id, "none"} == set(targets)


def test_candidate_answer_becomes_action_step(story, state):
    answers = {"s1": choice("move:base"), "s2": choice("none")}
    result = assemble(story, state, candidates(story, state), answers, 0.6)
    assert result == Steps(steps=[ActionStep(action_id="move:base")])


def test_none_is_rejected_without_a_turn(story, state):
    result = assemble(story, state, candidates(story, state), {"s1": choice("none")}, 0.6)
    assert isinstance(result, Rejected)


def test_low_confidence_target_asks_back(story, state):
    probs = {"talk:mira": 0.4, "talk:doha": 0.35, "improvise": 0.25}
    answers = {"s1": choice("talk:mira", 0.4, probs)}
    result = assemble(story, state, candidates(story, state), answers, 0.6)
    assert isinstance(result, Clarify)
    assert [k for k, _ in result.options] == ["talk:mira", "talk:doha"]


def test_vague_action_goes_improvise(story, state):
    probs = {"talk:mira": 0.3, "move:base": 0.3, "improvise": 0.4}
    answers = {"s1": choice("improvise", 0.4, probs), "s1.approach": choice("wits"), "s1.check": noul(True)}
    result = assemble(story, state, candidates(story, state), answers, 0.6)
    assert isinstance(result.steps[0], ImproviseStep) and result.steps[0].approach == "wits"


def test_impossible_first_step_is_rejected_with_reason(story, state):
    answers = {"s1": choice("improvise"), "s1.plausible": choice("impossible"), "why_not": choice("rule")}
    result = assemble(story, state, candidates(story, state), answers, 0.6)
    assert result == Rejected(reason="이 세계에서는 그렇게 되지 않습니다.")


def test_chain_drops_unsure_later_steps(story, state):
    answers = {"s1": choice("take:bread"), "s2": choice("give:mira:bread", 0.3), "s3": choice("move:base")}
    result = assemble(story, state, candidates(story, state), answers, 0.6)
    assert result.steps == [ActionStep(action_id="take:bread")]


def test_talk_step_keeps_only_the_partners_topics_and_known_lies(story, state):
    answers = {
        "s1": choice("talk:doha"), "talk.topic": choice("topic_key_mira"), "talk.attitude": choice("deceive"),
        "talk.claim": noul(True), "talk.contradicts": choice("kn_lamp_trick"), "talk.touch": choice("fear"),
    }
    step = assemble(story, state, candidates(story, state), answers, 0.6).steps[0]
    assert isinstance(step, TalkStep)
    assert step.topic == "chat", "topic_key_mira belongs to mira"
    assert step.contradicts is None, "doha does not know the lamp trick"
    assert step.claim and step.attitude == "deceive" and step.touch == "fear"


async def test_interpret_sends_one_call_with_state_text(story, state):
    kev = FakeKev({"s1": choice("move:base")})
    result = await interpret(kev, story, state, "등대로 간다", 0.6)
    assert result.steps == [ActionStep(action_id="move:base")]
    assert len(kev.calls) == 1
    assert kev.calls[0][0].endswith("플레이어 입력: 등대로 간다")
