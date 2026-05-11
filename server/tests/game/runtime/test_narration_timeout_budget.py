from src.game.runtime import input as input_runtime
from src.game.runtime import turn as turn_runtime


def test_graph_narration_timeout_allows_structured_metadata_tail():
    assert input_runtime._GRAPH_INPUT_NARRATION_TIMEOUT_SECONDS >= 30.0
    assert turn_runtime._GRAPH_ACTION_NARRATION_TIMEOUT_SECONDS >= 30.0
