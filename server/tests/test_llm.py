import asyncio
import json

import httpx
import pytest
from src.ai import ModelUnavailable
from src.ai.llm import LLMClient

SNAPSHOT = "/w/hub/models--mlx-community--gemma-4-26B-A4B-it-qat-4bit/snapshots/0e3c"


def make_client(models, chunks):
    sent = []

    def handle(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": models})
        sent.append(json.loads(request.content))
        lines = [f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}" for c in chunks]
        return httpx.Response(200, text="\n\n".join([*lines, "data: [DONE]"]))
    return LLMClient("http://gemma/v1", "gemma4", httpx.MockTransport(handle)), sent


async def collect(client):
    return [chunk async for chunk in client.stream([{"role": "user", "content": "x"}], 10)]


def test_check_finds_the_loaded_snapshot_and_writes_without_thinking():
    client, sent = make_client([{"id": "/w/qwen", "loaded": True}, {"id": SNAPSHOT, "loaded": True}], ["안", "녕"])
    asyncio.run(client.check())
    assert client.model == SNAPSHOT and sent[0]["model"] == SNAPSHOT and sent[0]["enable_thinking"] is False
    assert asyncio.run(collect(client)) == ["안", "녕"]
    unloaded, _ = make_client([{"id": SNAPSHOT, "loaded": False}], [])
    with pytest.raises(ModelUnavailable, match="not loaded"):
        asyncio.run(unloaded.check())


def test_a_model_server_that_is_down_or_breaks_mid_stream_is_unavailable():
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)
    down = LLMClient("http://gemma/v1", "gemma4", httpx.MockTransport(refuse))
    with pytest.raises(ModelUnavailable, match="llm"):
        asyncio.run(down.check())
    broken = LLMClient("http://gemma/v1", "gemma4", httpx.MockTransport(lambda _: httpx.Response(200, text="data: {oops\n\n")))
    with pytest.raises(ModelUnavailable, match="llm"):
        asyncio.run(collect(broken))

