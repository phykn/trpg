import asyncio
from pathlib import Path

import pytest
from src.interpret import Interpreter
from src.models import ModelUnavailable
from src.story.evals import make_state
from src.story.load import load_story

DAWN = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "dawn")


class FakeDecision:
    def __init__(self, kind, topics=None, two=0.1, place="숲길", second="_none", impression=None, method="press", deed=0.1):
        impression = impression or {"_none": 0.9}
        self.answers = {"kind": {"choice": kind, "probabilities": {kind: 0.9}}, "two": {"noul": two}, "deed": {"noul": deed},
                        "place": {"choice": place, "probabilities": {}}, "second": {"choice": second, "probabilities": {}},
                        "method": {"choice": method, "probabilities": {method: 0.9}},
                        "impression": {"choice": max(impression, key=impression.get), "probabilities": impression}}
        self.asked = []
        if topics:
            self.answers["topic"] = {"choice": max(topics, key=topics.get), "probabilities": topics}

    async def decide(self, state, questions):
        self.asked.append(questions)
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
    (FakeDecision("topic", {"징수관": 0.9, "독미나리": 0.0, "_none": 0.1}, two=0.9, second="독미나리"),
     {"kind": "topics", "topics": ["징수관", "독미나리"]}),
    (FakeDecision("topic", {"징수관": 0.6, "독미나리": 0.3, "_none": 0.1}, two=0.9), {"kind": "topics", "topics": ["징수관"]}),
    (FakeDecision("topic", {"징수관": 0.4, "독미나리": 0.1, "_none": 0.5}), {"kind": "none"}),
    (FakeDecision("topic", {"징수관": 0.5, "독미나리": 0.3, "_none": 0.2}), {"kind": "unsure", "topics": ["징수관", "독미나리"]}),
    (FakeDecision("topic", {"징수관": 0.6, "독미나리": 0.1, "_none": 0.3}), {"kind": "topics", "topics": ["징수관"]}),   # 0.3 ahead
])
def test_the_answers_become_one_reading(decision, heard):
    got = read(decision)
    assert {k: v for k, v in got.items() if k not in ("probs", "impression")} == heard and "topic" in got["probs"]


def test_a_second_topic_is_asked_apart_only_when_two_things_are_asked():
    once = FakeDecision("topic", {"징수관": 0.9, "독미나리": 0.1, "_none": 0.0})
    read(once)
    twice = FakeDecision("topic", {"징수관": 0.9, "독미나리": 0.1, "_none": 0.0}, two=0.9)
    read(twice)
    assert len(once.asked) == 1 and list(twice.asked[1]) == ["second"]
    assert set(twice.asked[1]["second"]["criteria"]) == {"독미나리", "_none"}


def test_the_kinds_name_the_other_people_in_the_notebook():
    decision = FakeDecision("chat", {"징수관": 0.1, "독미나리": 0.1, "_none": 0.8})
    read(decision)
    assert decision.questions["kind"]["criteria"]["topic"] == "브람에게 사건이나 고드릭, 마렌, 넬, 토빈에 관해 묻는다"


def test_an_answer_outside_the_options_is_no_answer():
    with pytest.raises(ModelUnavailable):
        read(FakeDecision("move", {"징수관": 1.0}, place="달나라"))


def test_an_impression_is_taken_from_the_common_ones_and_the_persons_own_above_its_threshold():
    rude = FakeDecision("chat", {"징수관": 0.1, "_none": 0.9}, impression={"무례": 0.7, "_none": 0.3})
    assert read(rude)["impression"] == "무례"
    assert {"다정", "위협", "눈감기", "_none"} <= set(rude.questions["impression"]["criteria"])
    assert "들킴" not in rude.questions["impression"]["criteria"]
    unsure = FakeDecision("chat", {"징수관": 0.1, "_none": 0.9}, impression={"무례": 0.4, "다정": 0.3, "_none": 0.3})
    assert read(unsure)["impression"] is None
    alone = FakeDecision("look", place="마을 사당")
    assert read(alone, "곳 숲길")["impression"] is None and "impression" not in alone.questions
    given = FakeDecision("chat", impression={"눈감기": 0.8, "_none": 0.2})
    assert asyncio.run(Interpreter(given).read_impression(DAWN, "브람", "밀주 건은 못 본 걸로 하지"))["impression"] == "눈감기"


def test_an_action_is_asked_apart_which_method_it_is_and_a_lock_here_can_be_opened():
    pressed = FakeDecision("action", {"징수관": 0.1, "_none": 0.9})
    assert {k: read(pressed)[k] for k in ("kind", "method", "target")} == {"kind": "action", "method": "press", "target": None}
    assert set(pressed.asked[1]["method"]["criteria"]) == {"press", "soothe", "trick"}
    forced = FakeDecision("action", {"_none": 0.9}, method="force")
    assert {k: read(forced, "사람 마렌")[k] for k in ("kind", "method", "target")} == {
        "kind": "action", "method": "force", "target": "잠김 장부 궤짝"}
    assert set(forced.asked[1]["method"]["criteria"]) == {"press", "soothe", "trick", "force", "sneak"}
    chat = FakeDecision("chat", {"징수관": 0.1, "_none": 0.9})
    read(chat)
    assert len(chat.asked) == 1
    told = FakeDecision("topic", {"징수관": 0.1, "_none": 0.9}, method="soothe", deed=0.9)
    assert {k: read(told)[k] for k in ("kind", "method")} == {"kind": "action", "method": "soothe"}
    asked = FakeDecision("topic", {"징수관": 0.9, "_none": 0.1}, deed=0.9)
    assert read(asked)["kind"] == "topics"   # a told deed that asks a topic still asks it
