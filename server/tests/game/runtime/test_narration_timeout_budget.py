from src.game.runtime.flow import input as input_runtime
from src.game.runtime.flow import turn as turn_runtime


def test_graph_narration_timeout_allows_structured_metadata_tail():
    assert input_runtime._input_narration_timeout_s() >= 30.0
    assert turn_runtime._action_narration_timeout_s() >= 30.0
