from src.game.runtime.flow import input as input_runtime
from src.game.runtime.flow import roll as roll_runtime
from src.game.runtime.flow import turn as turn_runtime


def test_graph_narration_timeouts_use_shared_llm_timeout(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_S", "12.5")

    assert input_runtime._input_narration_timeout_s() == 12.5
    assert turn_runtime._action_narration_timeout_s() == 12.5
    assert roll_runtime._roll_narration_timeout_s() == 12.5
