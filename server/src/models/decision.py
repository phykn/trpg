import httpx

from . import ModelUnavailable

DECISION_MODELS = {"kanana": "kakaocorp/kanana-2-v-decide-3b-2611"}


class DecisionClient:
    def __init__(self, base_url, model, transport=None):
        if model not in DECISION_MODELS:
            raise ValueError(f"unknown decision model {model!r}; one of {sorted(DECISION_MODELS)}")
        self.base_url = base_url.rstrip("/")
        self.name = model
        self.transport = transport

    async def request(self, method, path, body=None):
        try:
            async with httpx.AsyncClient(timeout=30.0, transport=self.transport) as client:
                response = await client.request(method, f"{self.base_url}{path}", json=body)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise TypeError("not an object")
            return data
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ModelUnavailable(f"decision: {type(exc).__name__}: {exc}") from None

    async def decide(self, state, questions):
        answers = (await self.request("POST", "/v1/systemone", {"state": state, "questions": questions})).get("answers")
        if not isinstance(answers, dict) or set(questions) - set(answers):
            raise ModelUnavailable("decision: an answer is missing")
        return answers

    async def check(self):
        run = str((await self.request("GET", "/v1/info")).get("run", ""))
        if not run.startswith(DECISION_MODELS[self.name]):
            raise ModelUnavailable(f"decision: {self.name} is configured but the server runs {run or 'nothing'}")
        await self.decide("확인", {"ok": {"type": "noul", "instructions": "확인", "criteria": {"true": "예", "false": "아니오"}}})
