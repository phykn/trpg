"""enemies_end and player_start/end carry only the closing-tone fields."""

from src.llm.calls.combat_narrate.schema import (
    EnemyEndSnapshot,
    EnemyStartSnapshot,
    PlayerNarrateSnapshot,
)


def test_enemy_end_only_name_and_alive():
    schema = EnemyEndSnapshot.model_json_schema()
    assert set(schema["properties"].keys()) == {"name", "alive"}


def test_enemy_start_keeps_identity_fields():
    props = set(EnemyStartSnapshot.model_json_schema()["properties"].keys())
    assert {"name", "alive", "race", "appearance", "description", "gender"} <= props


def test_player_snapshot_only_alive():
    schema = PlayerNarrateSnapshot.model_json_schema()
    assert set(schema["properties"].keys()) == {"alive"}
