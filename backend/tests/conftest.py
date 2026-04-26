import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def fresh_state():
    from src.domain.state import GameState

    return GameState(
        game_id="t",
        profile="default",
        player_id="player_01",
        world_time="0812-04-28T12:00:00",
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LIVE") == "1":
        return
    skip_live = pytest.mark.skip(reason="live LLM test (set RUN_LIVE=1 to run)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
