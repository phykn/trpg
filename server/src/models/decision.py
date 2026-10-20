from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field


class ModelUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Decision:
    run: str                      # the prefix of the `run` the server reports for this model
    min_confidence: float


# local-models kev.toml: every model serves the same API under the name kev-latest.
# malkuth-2b with its own prompt settings reaches about 80% of kev-4b in 7GB instead of 16GB, which leaves room for a
# larger narration model (qa_test/runs/decision-1/REPORT.md).
DECISION_MODELS = {
    "malkuth": Decision(run="dhtocks/malkuth-2b", min_confidence=0.5),
}


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    answer: str | bool
    confidence: float
    probabilities: dict[str, float] = Field(default_factory=dict)
    low: bool = False


def normalize(raw: dict[str, Any], min_confidence: float) -> Answer:
    """Same shape as local-models `kev.backends.normalize`, so one threshold fits every question type."""
    if raw["type"] == "noul":
        p = float(raw["noul"])
        answer = Answer(type="noul", answer=p >= 0.5, confidence=round(abs(p - 0.5) * 2, 4),
                        probabilities={"true": p, "false": 1 - p})
    else:
        answer = Answer(type="choice", answer=raw["choice"], confidence=float(raw["confidence"]),
                        probabilities=dict(raw.get("probabilities", {})))
    answer.low = answer.confidence < min_confidence
    return answer


class DecisionClient:
    def __init__(self, base_url: str, *, model: str = "kev", min_confidence: float | None = None,
                 timeout_s: float = 30.0, api_key: str = "", transport: httpx.AsyncBaseTransport | None = None):
        if model not in DECISION_MODELS:
            raise ValueError(f"unknown decision model {model!r}; one of {sorted(DECISION_MODELS)}")
        self.base_url = base_url.rstrip("/")
        self.headers = {"authorization": f"Bearer {api_key}"} if api_key else {}
        self.name = model
        self.model = "kev-latest"
        self.min_confidence = DECISION_MODELS[model].min_confidence if min_confidence is None else min_confidence
        self.timeout_s = timeout_s
        self.transport = transport

    async def decide(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, Answer]:
        body = {"state": state, "model": self.model, "questions": questions}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, transport=self.transport) as client:
                response = await client.post(f"{self.base_url}/v1/systemone", json=body, headers=self.headers)
            response.raise_for_status()
            answers = {qid: normalize(raw, self.min_confidence) for qid, raw in response.json()["answers"].items()}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ModelUnavailable(f"decision: {type(exc).__name__}: {exc}") from exc
        missing = set(questions) - set(answers)
        if missing:
            raise ModelUnavailable(f"decision: no answer for {sorted(missing)}")
        return answers

    async def check(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, transport=self.transport) as client:
                response = await client.get(f"{self.base_url}/v1/models", headers=self.headers)
            response.raise_for_status()
            runs = [m.get("run", "") for m in response.json()["models"] if m.get("name") == self.model]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ModelUnavailable(f"decision: {type(exc).__name__}: {exc}") from exc
        want = DECISION_MODELS[self.name].run
        if not any(r.startswith(want) for r in runs):
            raise ModelUnavailable(f"decision: {self.name} is configured but the server runs {runs or 'nothing'}")
        await self.decide("ping", {"ok": {"type": "noul", "instructions": "ok?", "criteria": {"true": "yes", "false": "no"}}})
