"""Tests for SupabaseStorageScenarioRepo using in-memory Storage fakes.

Fakes themselves live in `tests/_fakes.py` so other test modules can reuse
them (e.g. the API integration tests).
"""

import json

import pytest

from tests._fakes import make_scenario_repo


# ---------------------------------------------------------------------------
# ScenarioRepo tests


async def test_profile_exists_true_when_profile_json_present():
    repo, fs = make_scenario_repo()
    fs.objects["default/profile.json"] = b'{"id":"default","name":"X"}'
    assert await repo.profile_exists("default") is True
    assert await repo.profile_exists("missing") is False


async def test_read_world_md_caches_second_call():
    repo, fs = make_scenario_repo()
    fs.objects["default/world.md"] = "# 세계\n원본".encode("utf-8")
    a = await repo.read_world_md("default")
    # Mutate underlying storage; cached read should still return the original.
    fs.objects["default/world.md"] = "변경됨".encode("utf-8")
    b = await repo.read_world_md("default")
    assert a == b == "# 세계\n원본"


async def test_read_world_md_missing_ok_returns_empty():
    repo, _ = make_scenario_repo()
    assert await repo.read_world_md("absent", missing_ok=True) == ""
    with pytest.raises(FileNotFoundError):
        await repo.read_world_md("absent")


async def test_read_start_and_player():
    repo, fs = make_scenario_repo()
    fs.objects["default/start.json"] = json.dumps(
        {"start_location_id": "loc_01"}
    ).encode("utf-8")
    fs.objects["default/player.json"] = json.dumps(
        {"id": "player_01", "gold": 5}
    ).encode("utf-8")
    start = await repo.read_start_json("default")
    template = await repo.read_player("default")
    assert start["start_location_id"] == "loc_01"
    assert template["gold"] == 5


async def test_load_seed_records_reads_each_file():
    repo, fs = make_scenario_repo()
    fs.objects["default/items/sword.json"] = json.dumps(
        {"id": "sword", "name": "검", "description": "강철", "weight": 1.0}
    ).encode("utf-8")
    fs.objects["default/items/shield.json"] = json.dumps(
        {"id": "shield", "name": "방패", "description": "원형", "weight": 2.0}
    ).encode("utf-8")
    items = await repo.load_seed_records("default", "items")
    assert set(items) == {"sword", "shield"}
    assert items["sword"]["name"] == "검"


async def test_load_seed_records_reads_aggregate_kind_file():
    repo, fs = make_scenario_repo()
    fs.objects["default/items.json"] = json.dumps(
        {
            "sword": {"id": "sword", "name": "검"},
            "shield": {"id": "shield", "name": "방패"},
        },
        ensure_ascii=False,
    ).encode("utf-8")

    items = await repo.load_seed_records("default", "items")

    assert set(items) == {"sword", "shield"}
    assert items["shield"]["name"] == "방패"


async def test_list_profiles_walks_top_level_dirs():
    repo, fs = make_scenario_repo()
    fs.objects["default/profile.json"] = json.dumps(
        {"id": "default", "name": "기본", "description": "d1"}
    ).encode("utf-8")
    fs.objects["default/races/human.json"] = json.dumps(
        {"id": "human", "name": "인간", "description": "d2"}
    ).encode("utf-8")
    fs.objects["other/profile.json"] = json.dumps(
        {"id": "other", "name": "다른", "description": ""}
    ).encode("utf-8")

    profiles = await repo.list_profiles()
    ids = sorted(p["id"] for p in profiles)
    assert ids == ["default", "other"]
    default = next(p for p in profiles if p["id"] == "default")
    assert default["name"] == "기본"
    assert [r["id"] for r in default["races"]] == ["human"]


async def test_list_profiles_reads_races_from_aggregate_file():
    repo, fs = make_scenario_repo()
    fs.objects["default/profile.json"] = json.dumps(
        {"id": "default", "name": "기본", "description": ""}
    ).encode("utf-8")
    fs.objects["default/races.json"] = json.dumps(
        {"human": {"id": "human", "name": "인간", "description": "다재다능"}},
        ensure_ascii=False,
    ).encode("utf-8")

    profiles = await repo.list_profiles()

    assert profiles == [
        {
            "id": "default",
            "name": "기본",
            "description": "",
            "races": [{"id": "human", "name": "인간", "description": "다재다능"}],
        }
    ]
