import os
import random
import tempfile
from pathlib import Path

import pytest

from src.domain.entities import Character, Location, Race, Stats
from src.errors import PendingCheckActive, PendingCheckExpected
from src.llm_client.client import LLMClient
from src.pipeline.turn import run_roll, run_turn
from src.state.models import GameState

pytestmark = pytest.mark.live


@pytest.fixture
def client():
    base_url = os.environ.get("BASE_URL", "http://localhost:8000/v1")
    return LLMClient(base_url=base_url, model="local")


@pytest.fixture
def env():
    with tempfile.TemporaryDirectory() as tmp:
        profile_dir = Path(tmp) / "profiles"
        saves_dir = Path(tmp) / "saves"
        pdir = profile_dir / "default"
        pdir.mkdir(parents=True)
        (pdir / "world.md").write_text("중세 판타지", encoding="utf-8")
        gs = GameState(
            game_id="t",
            profile="default",
            player_id="player_01",
            world_time="0812-04-28T14:00:00",
        )
        gs.races["human"] = Race(id="human", name="인간", description="x")
        gs.locations["plaza_01"] = Location(id="plaza_01", name="광장")
        gs.characters["player_01"] = Character(
            id="player_01",
            name="주",
            race_id="human",
            stats=Stats(),
            location_id="plaza_01",
            hp=20,
            max_hp=20,
            mp=15,
            max_mp=15,
        )
        gs.characters["guard_01"] = Character(
            id="guard_01",
            name="경비병",
            race_id="human",
            stats=Stats(),
            location_id="plaza_01",
            appearance="갑옷",
            tone_hint="격식체",
        )
        yield gs, str(profile_dir), str(saves_dir)


async def _collect_events(gen):
    return [e async for e in gen]


async def test_pass_branch_full_flow(client, env):
    gs, profile_dir, saves_dir = env
    events = await _collect_events(
        run_turn(
            client,
            gs,
            profile_dir,
            saves_dir,
            "주변을 둘러본다.",
        )
    )
    types = [e["type"] for e in events]
    assert types[0] == "log_entry"  # player input
    assert "judge" in types
    assert "narrative_delta" in types
    assert types[-1] == "done"
    assert gs.turn_count == 1
    assert gs.pending_check is None


async def test_roll_branch_pauses_then_resumes(client, env):
    gs, profile_dir, saves_dir = env
    events = await _collect_events(
        run_turn(
            client,
            gs,
            profile_dir,
            saves_dir,
            "경비병에게 동전을 쥐여주며 통과시켜달라고 한다.",
        )
    )
    assert events[-1]["type"] == "pending_check"
    assert gs.pending_check is not None

    # /turn is blocked while a pending_check is active.
    with pytest.raises(PendingCheckActive):
        async for _ in run_turn(client, gs, profile_dir, saves_dir, "..."):
            pass

    # Resolve via /roll.
    roll_events = await _collect_events(
        run_roll(
            client,
            gs,
            profile_dir,
            saves_dir,
            rng=random.Random(7),
        )
    )
    assert roll_events[0]["type"] == "log_entry"  # roll log
    assert roll_events[-1]["type"] == "done"
    assert gs.pending_check is None
    # turn_count bumps in /roll, not /turn (roll branch leaves it untouched).
    assert gs.turn_count == 1


async def test_roll_without_pending_blocked(client, env):
    gs, profile_dir, saves_dir = env
    with pytest.raises(PendingCheckExpected):
        async for _ in run_roll(client, gs, profile_dir, saves_dir):
            pass
