import asyncio
import json

import httpx
import pytest
from src.models import ModelUnavailable
from src.models.decision import DecisionClient


def make_client(run, answers=None):
    def handle(request):
        if request.url.path == "/v1/info":
            return httpx.Response(200, json={"run": run})
        questions = json.loads(request.content)["questions"]
        every = {q: {"type": "noul", "noul": 0.9} for q in questions}
        return httpx.Response(200, json={"answers": every if answers is None else answers})
    return DecisionClient("http://kanana", "kanana", httpx.MockTransport(handle))


def test_check_accepts_only_kanana_answering_every_question():
    asyncio.run(make_client("kakaocorp/kanana-2-v-decide-3b-2611@1489062d").check())
    for client in (make_client("dhtocks/malkuth-2b"), make_client("kakaocorp/kanana-2-v-decide-3b-2611", {})):
        with pytest.raises(ModelUnavailable):
            asyncio.run(client.check())
    with pytest.raises(ValueError, match="malkuth"):
        DecisionClient("http://kanana", "malkuth")
