"""finalize emits state + suggestions BEFORE flush, then done."""

import pytest

from src.domain.state import GameState
from src.flow.dirty import Dirty, finalize


class _FlushTracker:
    """Capture order: tracker.events records yields and flush operations."""

    def __init__(self, sequence: list[str]) -> None:
        self.sequence = sequence

    async def save_entity(self, state, kind, eid):  # SaveRepo protocol
        self.sequence.append(f"flush:save_entity:{kind}:{eid}")

    async def append_log_entries(self, gid, entries):
        self.sequence.append("flush:append_log")

    async def append_history_entries(self, gid, entries):
        self.sequence.append("flush:append_history")

    async def append_dialogue_entries(self, gid, entries):
        self.sequence.append("flush:append_dialogue")

    async def save_meta(self, state):
        self.sequence.append("flush:save_meta")


@pytest.mark.asyncio
async def test_state_and_suggestions_fire_before_flush():
    state = GameState(game_id="g", profile="p", player_id="player_01")
    dirty = Dirty()
    sequence: list[str] = []
    repo = _FlushTracker(sequence)

    def to_front(s):
        return {"hp": 1}

    async for ev in finalize(state, repo, dirty, to_front):  # type: ignore[arg-type]
        sequence.append(f"yield:{ev['type']}")

    state_idx = sequence.index("yield:state")
    suggestions_idx = sequence.index("yield:suggestions")
    first_flush_idx = next(i for i, s in enumerate(sequence) if s.startswith("flush:"))
    done_idx = sequence.index("yield:done")

    assert state_idx < first_flush_idx, f"state should fire before flush. sequence: {sequence}"
    assert suggestions_idx < first_flush_idx, f"suggestions should fire before flush. sequence: {sequence}"
    assert first_flush_idx < done_idx, f"flush should complete before done. sequence: {sequence}"
