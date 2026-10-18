import json

import httpx
import pytest
from src.models.kev import KevClient, ModelUnavailable
from src.models.qwen import QwenClient


async def test_kev_normalizes_and_flags_low_confidence():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/systemone" and body["model"] == "kev-latest"
        assert request.headers["authorization"] == "Bearer k"
        return httpx.Response(200, json={"answers": {
            "a": {"type": "choice", "choice": "x", "confidence": 0.3, "probabilities": {"x": 0.6, "y": 0.4}},
            "b": {"type": "noul", "noul": 0.9},
        }})

    kev = KevClient("http://kev/", api_key="k", transport=httpx.MockTransport(handler))
    answers = await kev.decide("state", {"a": {}, "b": {}})
    assert answers["a"].answer == "x" and answers["a"].low
    assert answers["b"].answer is True and answers["b"].confidence == 0.8 and not answers["b"].low


@pytest.mark.parametrize("response", [
    httpx.Response(422, text="bad"),
    httpx.Response(200, json={"answers": {}}),
    httpx.Response(200, text="not json"),
])
async def test_kev_failures_are_unavailable(response):
    kev = KevClient("http://kev", transport=httpx.MockTransport(lambda r: response))
    with pytest.raises(ModelUnavailable):
        await kev.decide("state", {"a": {}})


def sse(*chunks: str) -> str:
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}" for c in chunks]
    return "\n\n".join([*lines, "data: [DONE]"]) + "\n\n"


async def test_qwen_resolves_auto_and_streams_without_thinking():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "other"}, {"id": "/snap/qwen", "loaded": True}]})
        seen.update(json.loads(request.content))
        return httpx.Response(200, text=sse("안녕", "하세요"))

    qwen = QwenClient("http://qwen/v1", transport=httpx.MockTransport(handler))
    text = "".join([c async for c in qwen.stream([{"role": "user", "content": "hi"}])])
    assert text == "안녕하세요"
    assert seen["model"] == "/snap/qwen"
    assert seen["enable_thinking"] is False and seen["chat_template_kwargs"] == {"enable_thinking": False}
    assert seen["top_k"] == 20 and seen["stream"] is True


async def test_qwen_without_loaded_model_is_unavailable():
    qwen = QwenClient("http://qwen/v1", transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})))
    with pytest.raises(ModelUnavailable):
        await qwen.resolve_model()


async def test_qwen_http_error_is_unavailable():
    qwen = QwenClient("http://qwen/v1", model="m", transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(ModelUnavailable):
        _ = [c async for c in qwen.stream([])]
