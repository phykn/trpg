"""End-to-end: '단검을 교환한다' swaps daggers between player and an NPC."""

import pytest

# Skipped by default — requires a live LLM. Locks the slot for the spec's
# §5 testing requirement; concrete fixtures filled in during a live debug pass.

pytestmark = pytest.mark.skip(reason="LLM-dependent e2e; run manually with RUN_LIVE=1")


def test_swap_daggers_via_run_turn():
    """Stub. When run live: setup state with player+NPC each holding a
    dagger, run run_turn with '단검을 교환한다', assert both inventories swapped."""
    pass
