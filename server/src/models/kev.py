"""Kev decision model: calibrated answers to closed questions over one state text."""

import time
from typing import Any

import httpx
from pydantic import Field

from src.content.schema import Model


class ModelUnavailable(RuntimeError):
    pass


class Answer(Model):
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


class KevClient:
    def __init__(self, base_url: str, *, model: str = "kev-latest", min_confidence: float = 0.5,
                 timeout_s: float = 30.0, api_key: str = "", transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"authorization": f"Bearer {api_key}"} if api_key else {}
        self.model = model
        self.min_confidence = min_confidence
        self.timeout_s = timeout_s
        self.transport = transport
        self.last_ms = 0

    async def decide(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, Answer]:
        body = {"state": state, "model": self.model, "questions": questions}
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, transport=self.transport) as client:
                response = await client.post(f"{self.base_url}/v1/systemone", json=body, headers=self.headers)
            response.raise_for_status()
            answers = {qid: normalize(raw, self.min_confidence) for qid, raw in response.json()["answers"].items()}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ModelUnavailable(f"kev: {type(exc).__name__}: {exc}") from exc
        self.last_ms = round((time.perf_counter() - started) * 1000)
        missing = set(questions) - set(answers)
        if missing:
            raise ModelUnavailable(f"kev: no answer for {sorted(missing)}")
        return answers

    async def ping(self) -> None:
        await self.decide("ping", {"ok": {"type": "noul", "instructions": "ok?", "criteria": {"true": "yes", "false": "no"}}})
