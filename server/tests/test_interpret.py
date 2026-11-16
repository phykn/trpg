import asyncio
from pathlib import Path

import pytest
from src.interpret import Interpreter
from src.models import ModelUnavailable
from src.story.evals import make_state
from src.story.load import load_story

DAWN = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "dawn")


class FakeDecision:
    def __init__(self, kind, topics=None, two=0.1, place="숲길"):
        self.answers = {"kind": {"choice": kind, "probabilities": {kind: 0.9}},
                        "two": {"noul": two}, "place": {"choice": place, "probabilities": {}}}
        if topics:
            self.answers["topic"] = {"choice": max(topics, key=topics.get), "probabilities": topics}

    async def decide(self, state, questions):
        self.questions = questions
        return {key: self.answers[key] for key in questions}


def read(decision, where="사람 브람", text="x"):
    return asyncio.run(Interpreter(decision).read(DAWN, make_state(DAWN, where), text))


def test_the_questions_offer_shown_topics_with_their_asks_and_reachable_places():
    decision = FakeDecision("chat", {"징수관": 0.1, "독미나리": 0.1, "_none": 0.8})
    assert read(decision)["kind"] == "chat"
    topic = decision.questions["topic"]["criteria"]
    assert set(topic) == {"징수관", "독미나리", "_none"} and "여관에 들렀습니까" in topic["징수관"]
    assert set(decision.questions["place"]["criteria"]) == set(DAWN.places) - {"여관 물레방아"}
    alone = FakeDecision("look", place="마을 사당")
    assert read(alone, "곳 숲길")["kind"] == "look" and "topic" not in alone.questions


@pytest.mark.parametrize(("decision", "heard"), [
    (FakeDecision("move", {"징수관": 0.9, "_none": 0.1}, place="촌장 집"), {"kind": "move", "place": "촌장 집"}),
    (FakeDecision("look", {"징수관": 0.9, "_none": 0.1}), {"kind": "look"}),
    (FakeDecision("chat", {"징수관": 0.8, "독미나리": 0.1, "_none": 0.1}), {"kind": "topics", "topics": ["징수관"]}),
    (FakeDecision("topic", {"징수관": 0.6, "독미나리": 0.3, "_none": 0.1}, two=0.9),
     {"kind": "topics", "topics": ["징수관", "독미나리"]}),
    (FakeDecision("topic", {"징수관": 0.9, "독미나리": 0.0, "_none": 0.1}, two=0.9), {"kind": "topics", "topics": ["징수관"]}),
    (FakeDecision("topic", {"징수관": 0.4, "독미나리": 0.1, "_none": 0.5}), {"kind": "none"}),
    (FakeDecision("topic", {"징수관": 0.5, "독미나리": 0.3, "_none": 0.2}), {"kind": "unsure", "topics": ["징수관", "독미나리"]}),
])
def test_the_answers_become_one_reading(decision, heard):
    got = read(decision)
    assert {k: v for k, v in got.items() if k != "probs"} == heard and "topic" in got["probs"]


def test_an_answer_outside_the_options_is_no_answer():
    with pytest.raises(ModelUnavailable):
        read(FakeDecision("move", {"징수관": 1.0}, place="달나라"))
