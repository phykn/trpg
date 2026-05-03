import pytest
from pathlib import Path

from src.domain.memory import PendingGrowth
from src.domain.state import GameState
from src.persistence.store import save_meta, load_game


@pytest.mark.asyncio
async def test_pending_growth_meta_round_trip(tmp_path: Path):
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
        pending_growth=PendingGrowth(stage="asking_stat"),
    )
    saves_dir = str(tmp_path)
    Path(saves_dir, "games", state.game_id).mkdir(parents=True, exist_ok=True)
    await save_meta(state, saves_dir)
    loaded = load_game(saves_dir, state.game_id)
    assert loaded.pending_growth is not None
    assert loaded.pending_growth.stage == "asking_stat"


@pytest.mark.asyncio
async def test_pending_growth_default_none_round_trip(tmp_path: Path):
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
    )
    saves_dir = str(tmp_path)
    Path(saves_dir, "games", state.game_id).mkdir(parents=True, exist_ok=True)
    await save_meta(state, saves_dir)
    loaded = load_game(saves_dir, state.game_id)
    assert loaded.pending_growth is None


@pytest.mark.asyncio
async def test_legacy_meta_without_pending_growth_loads_gracefully(tmp_path: Path):
    saves_dir = str(tmp_path)
    game_id = "g_legacy"
    meta_dir = Path(saves_dir, "games", game_id)
    meta_dir.mkdir(parents=True, exist_ok=True)
    legacy_meta = """{
  "game_id": "g_legacy",
  "profile": "p_test",
  "player_id": "player_01",
  "active_subject_id": null,
  "active_quest_id": null,
  "turn_count": 0,
  "pending_check": null,
  "pending_skill_candidates": [],
  "combat_state": null,
  "previous_phase_signal": null,
  "next_log_id": 1
}"""
    (meta_dir / "meta.json").write_text(legacy_meta)
    loaded = load_game(saves_dir, game_id)
    assert loaded.pending_growth is None
