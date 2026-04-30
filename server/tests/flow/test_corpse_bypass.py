"""When `pass.targets` includes a dead character, narrate is bypassed
entirely and a deterministic single-line body is emitted. No LLM call =
no chance the model resurrects the dead NPC's voice in any phrasing the
post-hoc redactor might miss (indirect speech, pronoun-only attribution,
quote-after-attribution, etc.).
"""
import tempfile

import pytest

from src.agents.dc_judge.schema import (
    ChainAction,
    PassAction,
    UseAction,
)
from src.domain.entities import Character, Location, Stats
from src.flow import turn as turn_mod
from src.flow.turn import _CORPSE_BYPASS_BODY, run_turn


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def state_with_corpse(fresh_state):
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01", name="주인공", race_id="human", is_player=True,
        location_id="plaza_01", stats=Stats(),
    )
    fresh_state.characters["edrik"] = Character(
        id="edrik", name="에드릭", race_id="human",
        location_id="plaza_01", stats=Stats(),
        alive=False,
    )
    return fresh_state


async def _collect(it):
    return [ev async for ev in it]


async def test_pass_with_dead_target_bypasses_narrate(
    state_with_corpse, tmp_saves, monkeypatch,
):
    """The bypass path must:
    - never call run_narrate
    - emit `narrative_delta` with exactly the fixed body
    - persist that body to log_entries / recent_dialogue
    """
    narrate_called = False

    async def fake_run_narrate(*a, **kw):
        nonlocal narrate_called
        narrate_called = True
        if False:
            yield None  # pragma: no cover — make it an async generator
    monkeypatch.setattr(turn_mod, "run_narrate", fake_run_narrate)

    async def fake_judge(*a, **kw):
        return PassAction(action="pass", targets=["edrik"])
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    events = await _collect(
        run_turn(
            client=None,
            state=state_with_corpse,
            profile_dir="<unused>",
            saves_dir=tmp_saves,
            player_input="에드릭에게 묻는다",
        )
    )

    assert not narrate_called, "narrate must be skipped for dead target"

    deltas = [e for e in events if e["type"] == "narrative_delta"]
    assert len(deltas) == 1
    assert deltas[0]["data"]["text"] == _CORPSE_BYPASS_BODY

    suggestions = [e for e in events if e["type"] == "suggestions"]
    assert suggestions and suggestions[0]["data"]["items"] == []

    gm_logs = [e for e in state_with_corpse.log_entries if e.kind == "gm"]
    assert gm_logs and gm_logs[-1].text == _CORPSE_BYPASS_BODY

    assert state_with_corpse.recent_dialogue
    last_dlg = state_with_corpse.recent_dialogue[-1]
    assert last_dlg.player == "에드릭에게 묻는다"
    assert last_dlg.narrator == _CORPSE_BYPASS_BODY


async def test_pass_with_alive_target_still_runs_narrate(
    state_with_corpse, tmp_saves, monkeypatch,
):
    """A live target shouldn't trigger the bypass — narrate runs as usual.
    Add a live merchant NPC alongside the dead Edrik so the action targets
    the live one."""
    state_with_corpse.characters["merchant"] = Character(
        id="merchant", name="상인", race_id="human",
        location_id="plaza_01", stats=Stats(),
    )
    narrate_called = False

    async def fake_run_narrate(*a, **kw):
        nonlocal narrate_called
        narrate_called = True
        # minimal stream: no body, no final → consume_narrate falls back to
        # "잠시 정적이 흐릅니다." This is enough to confirm narrate was reached.
        if False:
            yield None  # pragma: no cover
    monkeypatch.setattr(turn_mod, "run_narrate", fake_run_narrate)

    async def fake_judge(*a, **kw):
        return PassAction(action="pass", targets=["merchant"])
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    await _collect(
        run_turn(
            client=None,
            state=state_with_corpse,
            profile_dir="<unused>",
            saves_dir=tmp_saves,
            player_input="상인에게 인사한다",
        )
    )

    assert narrate_called, "narrate must run when target is alive"


async def test_chain_with_dead_target_in_last_pass_bypasses(
    state_with_corpse, tmp_saves, monkeypatch,
):
    """ChainAction.last_pass with a dead target funnels through the same
    `_stream_narrate_tail`, so the bypass also fires there."""
    narrate_called = False

    async def fake_run_narrate(*a, **kw):
        nonlocal narrate_called
        narrate_called = True
        if False:
            yield None  # pragma: no cover
    monkeypatch.setattr(turn_mod, "run_narrate", fake_run_narrate)

    # chain = [use missing item (engine logs failure), pass with dead target]
    # — only the pass carries the narrate path. The use part's failure log
    # doesn't matter; we just need a non-pass first part to confirm the
    # last_pass branch routes through `_stream_narrate_tail`.
    state_with_corpse.characters["player_01"].inventory_ids = []

    async def fake_judge(*a, **kw):
        return ChainAction(
            action="chain",
            parts=[
                UseAction(action="use", item_id="dagger"),
                PassAction(action="pass", targets=["edrik"]),
            ],
        )
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    events = await _collect(
        run_turn(
            client=None,
            state=state_with_corpse,
            profile_dir="<unused>",
            saves_dir=tmp_saves,
            player_input="단검을 챙기고 에드릭에게 묻는다",
        )
    )

    assert not narrate_called, "narrate must be skipped on chain last_pass to dead"
    deltas = [e for e in events if e["type"] == "narrative_delta"]
    assert deltas and deltas[0]["data"]["text"] == _CORPSE_BYPASS_BODY


async def test_corpse_bypass_pushes_turn_log_with_dead_id(
    state_with_corpse, tmp_saves, monkeypatch,
):
    """`turn_log` entry's `target` field must point at the dead character —
    that's what surfaces them as off-screen corpses on subsequent turns
    (`_corpses_payload` reads `turn_log.target`)."""
    async def fake_run_narrate(*a, **kw):
        if False:
            yield None  # pragma: no cover
    monkeypatch.setattr(turn_mod, "run_narrate", fake_run_narrate)

    async def fake_judge(*a, **kw):
        return PassAction(action="pass", targets=["edrik"])
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    await _collect(
        run_turn(
            client=None,
            state=state_with_corpse,
            profile_dir="<unused>",
            saves_dir=tmp_saves,
            player_input="에드릭에게 사과한다",
        )
    )

    assert state_with_corpse.turn_log
    last = state_with_corpse.turn_log[-1]
    assert last.target == "edrik"
    assert "에드릭" in last.summary
