import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

from src.content.load import load_story, new_game
from src.models.kev import Answer

REPO = SERVER.parent
TEMPLATE = REPO / "scenarios" / "_template"
GAME_ID = "g_" + "0" * 32


def choice(answer: str, confidence: float = 0.9, probabilities: dict[str, float] | None = None) -> Answer:
    return Answer(type="choice", answer=answer, confidence=confidence,
                  probabilities=probabilities or {answer: confidence}, low=confidence < 0.5)


def noul(answer: bool, confidence: float = 0.9) -> Answer:
    return Answer(type="noul", answer=answer, confidence=confidence, low=confidence < 0.5)


class FakeKev:
    """Answers from a table; unanswered choice questions pick 'none' or their last option, noul says no."""

    def __init__(self, answers: dict | None = None, error: Exception | None = None):
        self.answers = answers or {}
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    async def decide(self, state: str, questions: dict) -> dict[str, Answer]:
        self.calls.append((state, questions))
        if self.error is not None:
            raise self.error
        out = {}
        for qid, q in questions.items():
            if qid in self.answers:
                out[qid] = self.answers[qid]
            elif q["type"] == "noul":
                out[qid] = noul(False)
            else:
                keys = list(q["criteria"])
                out[qid] = choice("none" if "none" in keys else keys[-1])
        return out

    async def ping(self) -> None:
        if self.error is not None:
            raise self.error


class FakeQwen:
    """Streams one scripted text per attempt, split into small chunks."""

    def __init__(self, texts: list[str] | None = None, error: Exception | None = None):
        self.texts = list(texts or ["당신은 광장에 서 있습니다. 바람이 붑니다. 이제 무엇을 할지 정할 때입니다."])
        self.error = error
        self.calls: list[list[dict]] = []
        self.seeds: list[int | None] = []

    async def resolve_model(self) -> str:
        if self.error is not None:
            raise self.error
        return "fake"

    async def pick(self, messages, max_tokens: int = 6) -> str:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return self.texts[0]

    async def stream(self, messages, max_tokens: int = 500, seed: int | None = None):
        self.calls.append(messages)
        self.seeds.append(seed)
        if self.error is not None:
            raise self.error
        text = self.texts[min(len(self.calls) - 1, len(self.texts) - 1)]
        for i in range(0, len(text), 7):
            yield text[i : i + 7]


@pytest.fixture
def loaded():
    return load_story(TEMPLATE)


@pytest.fixture
def story(loaded):
    return loaded.story


@pytest.fixture
def state(story):
    return new_game(story, game_id=GAME_ID, seed=1)
