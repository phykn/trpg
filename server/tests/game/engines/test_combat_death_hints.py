from server.src.game.engines.combat import (
    _append_death_to_hints as append_death_to_hints,
)


def test_dead_character_hints_includes_death_fact():
    """Death adds the killer-aware fact to hints."""
    entity = type(
        "Entity",
        (),
        {
            "id": "edric",
            "name": "에드릭",
            "hints": ["이스나르 촌장이다."],
        },
    )()
    append_death_to_hints(entity, killer_name="주인공")
    assert any("살해" in h for h in entity.hints)


def test_already_dead_entity_no_double_append():
    """Idempotent: already-recorded death is not duplicated."""
    entity = type(
        "Entity",
        (),
        {
            "id": "edric",
            "name": "에드릭",
            "hints": ["이스나르 촌장이다.", "주인공에게 살해당했다."],
        },
    )()
    before = len(entity.hints)
    append_death_to_hints(entity, killer_name="주인공")
    assert len(entity.hints) == before


def test_unknown_killer_falls_back_to_plain_death():
    """No killer name → simple 사망 marker."""
    entity = type(
        "Entity",
        (),
        {
            "id": "x",
            "name": "x",
            "hints": [],
        },
    )()
    append_death_to_hints(entity, killer_name=None)
    assert any("사망" in h for h in entity.hints)
