import json
import os
from pathlib import Path

from src.db.scenario.local_fs import LocalFsScenarioRepo


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _touch_forward(path: Path) -> None:
    next_mtime = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(next_mtime, next_mtime))


async def test_local_seed_records_reuse_cached_files(tmp_path, monkeypatch):
    item_file = tmp_path / "default" / "items" / "sword.json"
    _write_json(item_file, {"id": "sword", "name": "검"})
    repo = LocalFsScenarioRepo(str(tmp_path))

    read_count = 0
    original_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        nonlocal read_count
        read_count += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    first = await repo.load_seed_records("default", "items")
    second = await repo.load_seed_records("default", "items")

    assert first == second == {"sword": {"id": "sword", "name": "검"}}
    assert read_count == 1


async def test_local_seed_records_can_read_aggregate_kind_file(tmp_path):
    items_file = tmp_path / "default" / "items.json"
    _write_json(
        items_file,
        {
            "sword": {"id": "sword", "name": "검"},
            "shield": {"id": "shield", "name": "방패"},
        },
    )
    repo = LocalFsScenarioRepo(str(tmp_path))

    items = await repo.load_seed_records("default", "items")

    assert set(items) == {"sword", "shield"}
    assert items["shield"]["name"] == "방패"


async def test_local_seed_records_reload_when_file_changes(tmp_path):
    item_file = tmp_path / "default" / "items" / "sword.json"
    _write_json(item_file, {"id": "sword", "name": "검"})
    repo = LocalFsScenarioRepo(str(tmp_path))

    first = await repo.load_seed_records("default", "items")
    _write_json(item_file, {"id": "sword", "name": "긴 훈련용 검"})
    _touch_forward(item_file)
    second = await repo.load_seed_records("default", "items")

    assert first["sword"]["name"] == "검"
    assert second["sword"]["name"] == "긴 훈련용 검"


async def test_list_profiles_reads_races_from_aggregate_file(tmp_path):
    _write_json(
        tmp_path / "default" / "profile.json",
        {"id": "default", "name": "기본", "description": ""},
    )
    _write_json(
        tmp_path / "default" / "races.json",
        {"human": {"id": "human", "name": "인간", "description": "다재다능"}},
    )
    repo = LocalFsScenarioRepo(str(tmp_path))

    profiles = await repo.list_profiles()

    assert profiles[0]["races"] == [
        {"id": "human", "name": "인간", "description": "다재다능"}
    ]


async def test_local_json_content_cache_reloads_when_file_changes(tmp_path):
    start_file = tmp_path / "default" / "start.json"
    _write_json(start_file, {"start_location_id": "room_a"})
    repo = LocalFsScenarioRepo(str(tmp_path))

    first = await repo.read_start_json("default")
    _write_json(start_file, {"start_location_id": "room_b"})
    _touch_forward(start_file)
    second = await repo.read_start_json("default")

    assert first["start_location_id"] == "room_a"
    assert second["start_location_id"] == "room_b"


async def test_local_fs_reads_contract_json_when_present(tmp_path):
    _write_json(tmp_path / "white_isle_llm" / "contract.json", {"id": "white_isle_llm"})
    repo = LocalFsScenarioRepo(str(tmp_path))

    assert await repo.read_contract_json("white_isle_llm", missing_ok=True) == {
        "id": "white_isle_llm"
    }


async def test_local_fs_contract_missing_ok_returns_none(tmp_path):
    (tmp_path / "legacy").mkdir()
    repo = LocalFsScenarioRepo(str(tmp_path))

    assert await repo.read_contract_json("legacy", missing_ok=True) is None
