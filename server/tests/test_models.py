import httpx
import pytest
from src.models.decision import DecisionClient, ModelUnavailable
from src.models.llm import LLMClient

SNAP = "/w/hub/models--{}/snapshots/abc"


def decision_server(run: str) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"models": [{"name": "kev-latest", "run": run},
                                                        {"name": "jev-latest", "run": "x"}]})
        return httpx.Response(200, json={"answers": {"ok": {"type": "noul", "noul": 0.9}}})
    return httpx.MockTransport(handle)


def llm_server(loaded: str | None) -> httpx.MockTransport:
    ids = ["empero-ai--Qwen3.8-2B-Distill", "mlx-community--gemma-4-26B-A4B-it-qat-4bit",
           "mlx-community--Qwen3.8-27B-mxfp4", "mlx-community--MiniCPM-V-4.7-35B-A3B-mxfp4"]
    data = [{"id": SNAP.format(i), "loaded": i == loaded} for i in ids]
    return httpx.MockTransport(lambda request: httpx.Response(200, json={"data": data}))


async def test_decision_check_accepts_the_configured_model_only():
    await DecisionClient("http://d", model="malkuth", transport=decision_server("dhtocks/malkuth-2b@37ae")).check()
    with pytest.raises(ModelUnavailable, match="malkuth is configured"):
        await DecisionClient("http://d", model="malkuth", transport=decision_server("jaredpalmer/kev-4b@v1.0")).check()


def test_unknown_model_names_fail_at_construction():
    with pytest.raises(ValueError):
        DecisionClient("http://d", model="jev")
    with pytest.raises(ValueError):
        LLMClient("http://l", model="llama")


async def test_llm_finds_its_loaded_id_and_uses_its_sampling():
    llm = LLMClient("http://l/v1", model="gemma4", transport=llm_server("mlx-community--gemma-4-26B-A4B-it-qat-4bit"))
    assert "gemma-4-26B" in await llm.resolve_model()
    assert llm.sampling["top_k"] == 64


async def test_llm_that_is_not_loaded_is_an_error_and_a_distill_is_not_qwen():
    with pytest.raises(ModelUnavailable, match="qwen is configured but not loaded"):
        await LLMClient("http://l/v1", model="qwen", transport=llm_server("empero-ai--Qwen3.8-2B-Distill")).resolve_model()


def test_a_greedy_pick_leaves_the_shared_sampling_alone():
    llm = LLMClient("http://l/v1", model="gemma4")
    assert llm.body([], 6, 1, {"temperature": 0.0})["temperature"] == 0.0
    assert llm.sampling["top_k"] == 64 and llm.body([], 6)["top_k"] == 64
