import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _clear_save_locks():
    """Clear the global save locks dict between tests to avoid event loop binding issues."""
    from src.db import store

    store._save_locks.clear()
    yield
    store._save_locks.clear()


@pytest.fixture
def fresh_state():
    from src.game.domain.state import GameState

    return GameState(
        game_id="t",
        profile="default",
        player_id="player_01",
    )


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def collect():
    async def _c(it):
        return [ev async for ev in it]

    return _c
