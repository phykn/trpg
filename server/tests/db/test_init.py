import json
from pathlib import Path

from src.db.init import PlayerInput, init_game
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


def _write_minimal_seed(profile_dir: Path) -> None:
    pdir = profile_dir / "default"
    pdir.mkdir(parents=True)
    (pdir / "world.md").write_text("world", encoding="utf-8")
    (pdir / "start.json").write_text(
        json.dumps({"start_location_id": "plaza_01"}),
        encoding="utf-8",
    )
    (pdir / "player_template.json").write_text(
        json.dumps({"id": "player_01"}), encoding="utf-8"
    )
    (pdir / "races").mkdir()
    (pdir / "races" / "human.json").write_text(
        json.dumps(
            {
                "id": "human",
                "name": "인간",
                "description": "x",
                "racial_skills": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pdir / "locations").mkdir()
    (pdir / "locations" / "plaza.json").write_text(
        json.dumps({"id": "plaza_01", "name": "광장"}, ensure_ascii=False),
        encoding="utf-8",
    )


async def test_init_marks_start_location_visited(tmp_data):
    # Re-visit logic (cards-only, no narrate body) keys off visited_location_ids.
    # Without this, the player returning to spawn would trip first-visit narrate
    # and the LLM would hallucinate that NPCs colocated since the start are absent.
    profile_dir = Path(tmp_data) / "profiles"
    saves_dir = str(Path(tmp_data) / "saves")
    _write_minimal_seed(profile_dir)
    state = await init_game(
        "default",
        PlayerInput(name="테스터", race_id="human", gender="female"),
        LocalFsSaveRepo(saves_dir=saves_dir),
        LocalFsScenarioRepo(profile_dir=str(profile_dir)),
    )
    p = state.characters["player_01"]
    assert p.location_id == "plaza_01"
    assert "plaza_01" in p.visited_location_ids
