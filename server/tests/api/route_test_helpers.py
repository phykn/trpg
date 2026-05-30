import asyncio
import json

import httpx
from httpx import ASGITransport, AsyncClient
from openai import RateLimitError

from run_api import build_app
from src.db.graph.local_fs import LocalFsGraphRepo
from tests._fakes import make_default_storage, make_scenario_repo


class _MockLLM:
    def __init__(
        self,
        payload: dict | None = None,
        *,
        intro_answer: str = "당신은 광장에 처음 발을 들입니다.",
        intro_delay: float = 0.0,
        intro_error: Exception | None = None,
        narration_meta: dict | None = None,
    ) -> None:
        self.payload = payload or {"actions": [{"verb": "pass"}]}
        self.intro_answer = intro_answer
        self.intro_delay = intro_delay
        self.intro_error = intro_error
        self.narration_meta = narration_meta
        self.calls: list[dict] = []

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.calls.append({"agent": agent, "messages": messages})
        if agent == "graph_intro":
            if self.intro_error is not None:
                raise self.intro_error
            if self.intro_delay:
                await asyncio.sleep(self.intro_delay)
            return {"answer": self.intro_answer, "think": ""}
        if agent in {"graph_narrate", "combat_narrate"}:
            return {"answer": self._narration_answer(), "think": ""}
        return {"answer": json.dumps(self.payload, ensure_ascii=False), "think": ""}

    async def chat_stream(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.calls.append({"agent": agent, "messages": messages})
        if agent == "graph_intro":
            if self.intro_error is not None:
                raise self.intro_error
            if self.intro_delay:
                await asyncio.sleep(self.intro_delay)
            midpoint = max(1, len(self.intro_answer) // 2)
            for chunk in (self.intro_answer[:midpoint], self.intro_answer[midpoint:]):
                yield {"answer": chunk, "think": None}
            return
        if agent in {"graph_narrate", "combat_narrate"}:
            answer = self._narration_answer()
            midpoint = max(1, len(answer) // 2)
            for chunk in (answer[:midpoint], answer[midpoint:]):
                yield {"answer": chunk, "think": None}
            return
        yield {
            "answer": json.dumps(self.payload, ensure_ascii=False),
            "think": None,
        }

    def _narration_answer(self) -> str:
        narration = "장면의 긴장이 짧게 가라앉습니다."
        if self.narration_meta is None:
            return narration
        return "\n".join(
            [
                narration,
                "---TRPG_META---",
                json.dumps(self.narration_meta, ensure_ascii=False),
            ]
        )


def _extend_default_storage_for_movement(storage) -> None:
    storage.objects["default/locations/loc_01.json"] = json.dumps(
        {
            "id": "loc_01",
            "name": "광장",
            "description": "테스트 광장",
            "connections": [{"target": "loc_02"}],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    storage.objects["default/locations/loc_02.json"] = json.dumps(
        {
            "id": "loc_02",
            "name": "숲길",
            "description": "테스트 숲길",
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _build_app(
    tmp_path,
    *,
    llm_payload: dict | None = None,
    intro_answer: str = "당신은 광장에 처음 발을 들입니다.",
    start_intro_text: str | None = None,
    intro_delay: float = 0.0,
    intro_error: Exception | None = None,
    narration_meta: dict | None = None,
    generated_contract: bool = False,
):
    storage = make_default_storage()
    if generated_contract:
        storage.objects["default/contract.json"] = json.dumps(
            {
                "id": "default",
                "world": {"title": "생성형 테스트", "locale": "ko"},
                "fixed": [],
                "forbid": ["금지된 결말"],
                "tone": {"register": "합니다체", "person": "second"},
                "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
                "allowed_ops": ["add_memory", "add_clue", "add_location"],
                "stability_defaults": {
                    "add_memory": "campaign",
                    "add_clue": "scene",
                    "add_location": "scene",
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
    if start_intro_text is not None:
        start = json.loads(storage.objects["default/start.json"].decode("utf-8"))
        start["intro_text"] = start_intro_text
        storage.objects["default/start.json"] = json.dumps(
            start, ensure_ascii=False
        ).encode("utf-8")
    _extend_default_storage_for_movement(storage)
    scenario_repo, _ = make_scenario_repo(storage)
    return build_app(
        llm=_MockLLM(
            llm_payload,
            intro_answer=intro_answer,
            intro_delay=intro_delay,
            intro_error=intro_error,
            narration_meta=narration_meta,
        ),
        basic_auth_user="t",
        basic_auth_pass="t",
        scenario_repo=scenario_repo,
        graph_repo=LocalFsGraphRepo(str(tmp_path / "graph")),
        cors_origins=[],
    )


def _client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        auth=("t", "t"),
        timeout=30.0,
    )


def _rate_limit_error(message: str = "quota exceeded") -> RateLimitError:
    response = httpx.Response(
        status_code=429, request=httpx.Request("POST", "http://x")
    )
    return RateLimitError(message, response=response, body=None)


async def _init_graph_session(client) -> str:
    response = await client.post(
        "/session/graph/init",
        json={
            "profile": "default",
            "player": {"name": "테스터", "race_id": "human", "gender": "female"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["game_id"]


