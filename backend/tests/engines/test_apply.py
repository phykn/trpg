import pytest

from src.domain.entities import (
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    QuestTrigger,
    Stats,
)
from src.engines.apply import apply_changes


@pytest.fixture
def state(fresh_state):
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01", name="광장", item_ids=["stone_01"]
    )
    fresh_state.locations["gate_01"] = Location(id="gate_01", name="성문")
    fresh_state.items["stone_01"] = Item(id="stone_01", name="돌")
    fresh_state.items["key_01"] = Item(id="key_01", name="열쇠")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        inventory_ids=["key_01"],
    )
    fresh_state.characters["guard_01"] = Character(
        id="guard_01",
        name="경비",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    fresh_state.chapters["ch1"] = Chapter(id="ch1", title="t", status="active")
    fresh_state.quests["q1"] = Quest(
        id="q1",
        title="t",
        giver_id="guard_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="x", name="n", type="character_death", target_id="goblin_01"
            )
        ],
        status="active",
    )
    return fresh_state


def test_set_scalar_and_dotted(state):
    r = apply_changes(
        state,
        [
            {
                "type": "set",
                "entity": "characters",
                "id": "guard_01",
                "field": "tone_hint",
                "value": "격식",
            },
            {
                "type": "set",
                "entity": "characters",
                "id": "guard_01",
                "field": "disposition.aggressive",
                "value": 80,
            },
        ],
    )
    assert r["applied"] == 2 and r["rejected"] == []
    assert state.characters["guard_01"].tone_hint == "격식"
    assert state.characters["guard_01"].disposition.aggressive == 80


def test_set_rejects_wrong_type_before_persist(state):
    # Regression: judge produced `Character.status = 'muddy_foot'` (str instead
    # of list[str]) and the bad value survived setattr only to blow up at the
    # next persistence read as PersistenceFailed. Now the type is validated up
    # front and the change is rejected without touching the entity.
    r = apply_changes(
        state,
        [
            {
                "type": "set",
                "entity": "characters",
                "id": "guard_01",
                "field": "status",
                "value": "muddy_foot",
            },
            {
                "type": "set",
                "entity": "locations",
                "id": "plaza_01",
                "field": "description",
                "value": None,
            },
        ],
    )
    assert r["applied"] == 0 and len(r["rejected"]) == 2
    assert state.characters["guard_01"].status == []
    assert state.locations["plaza_01"].description == ""


def test_set_engine_owned_field_rejected(state):
    r = apply_changes(
        state,
        [
            {
                "type": "set",
                "entity": "characters",
                "id": "guard_01",
                "field": "hp",
                "value": 0,
            },
            {
                "type": "set",
                "entity": "characters",
                "id": "guard_01",
                "field": "level",
                "value": 99,
            },
            {
                "type": "set",
                "entity": "characters",
                "id": "guard_01",
                "field": "memories",
                "value": [],
            },
        ],
    )
    assert r["applied"] == 0 and len(r["rejected"]) == 3


def test_set_chapter_quest_only_summary_or_status(state):
    r = apply_changes(
        state,
        [
            {
                "type": "set",
                "entity": "quests",
                "id": "q1",
                "field": "summary",
                "value": "x",
            },
            {
                "type": "set",
                "entity": "chapters",
                "id": "ch1",
                "field": "status",
                "value": "completed",
            },
            {
                "type": "set",
                "entity": "quests",
                "id": "q1",
                "field": "difficulty",
                "value": "신화",
            },
            {
                "type": "set",
                "entity": "chapters",
                "id": "ch1",
                "field": "title",
                "value": "X",
            },
        ],
    )
    assert r["applied"] == 2 and len(r["rejected"]) == 2


def test_set_time_forward_and_reject_backward(state):
    r = apply_changes(state, [{"type": "set_time", "value": "0812-04-29T06:00:00"}])
    assert r["applied"] == 1 and state.world_time == "0812-04-29T06:00:00"
    r = apply_changes(state, [{"type": "set_time", "value": "0812-04-28T00:00:00"}])
    assert r["applied"] == 0
    assert "no time travel" in r["rejected"][0]["reason"]


def test_move_valid_and_unknown(state):
    r = apply_changes(
        state, [{"type": "move", "target": "player_01", "destination": "gate_01"}]
    )
    assert r["applied"] == 1 and state.characters["player_01"].location_id == "gate_01"
    r = apply_changes(
        state, [{"type": "move", "target": "player_01", "destination": "nowhere"}]
    )
    assert r["applied"] == 0


def test_move_item_between_containers(state):
    r = apply_changes(
        state,
        [
            {
                "type": "move_item",
                "item": "key_01",
                "from": "player_01",
                "to": "plaza_01",
            }
        ],
    )
    assert r["applied"] == 1
    assert "key_01" not in state.characters["player_01"].inventory_ids
    assert "key_01" in state.locations["plaza_01"].item_ids


def test_affinity_grade_intent_matrix(state):
    apply_changes(
        state,
        [
            {
                "type": "affinity",
                "actor": "player_01",
                "target": "guard_01",
                "grade": "success",
                "intent": "friendly",
            }
        ],
    )
    assert state.characters["player_01"].relations["guard_01"] == 5

    state.characters["player_01"].relations["guard_01"] = 0
    apply_changes(
        state,
        [
            {
                "type": "affinity",
                "actor": "player_01",
                "target": "guard_01",
                "grade": "success",
                "intent": "hostile",
            }
        ],
    )
    assert state.characters["player_01"].relations["guard_01"] == -5

    state.characters["player_01"].relations["guard_01"] = 0
    apply_changes(
        state,
        [
            {
                "type": "affinity",
                "actor": "player_01",
                "target": "guard_01",
                "grade": "success",
                "intent": "deceptive",
            }
        ],
    )
    assert (
        state.characters["player_01"].relations["guard_01"] == 0
    )  # successful deception = 0

    state.characters["player_01"].relations["guard_01"] = 0
    apply_changes(
        state,
        [
            {
                "type": "affinity",
                "actor": "player_01",
                "target": "guard_01",
                "grade": "failure",
                "intent": "deceptive",
            }
        ],
    )
    assert state.characters["player_01"].relations["guard_01"] == -6  # delta * 2

    # clamp 100
    state.characters["player_01"].relations["guard_01"] = 95
    apply_changes(
        state,
        [
            {
                "type": "affinity",
                "actor": "player_01",
                "target": "guard_01",
                "grade": "critical_success",
                "intent": "friendly",
            }
        ],
    )
    assert state.characters["player_01"].relations["guard_01"] == 100


def test_partial_success_keeps_valid_changes(state):
    r = apply_changes(
        state,
        [
            {
                "type": "set",
                "entity": "characters",
                "id": "guard_01",
                "field": "tone_hint",
                "value": "x",
            },
            {
                "type": "set",
                "entity": "characters",
                "id": "guard_01",
                "field": "hp",
                "value": 0,
            },
            {"type": "set_time", "value": "0812-04-29T00:00:00"},
        ],
    )
    assert r["applied"] == 2 and len(r["rejected"]) == 1
    assert state.characters["guard_01"].tone_hint == "x"


def test_unknown_change_type_rejected(state):
    r = apply_changes(state, [{"type": "exotic_thing"}])
    assert r["applied"] == 0 and len(r["rejected"]) == 1


def test_set_unknown_field_on_character_rejected(state):
    """Pydantic v2 raises ValueError for unknown fields. _apply_set must
    catch it and route to rejected[] like any other set failure."""
    r = apply_changes(
        state,
        [
            {
                "type": "set",
                "entity": "characters",
                "id": "guard_01",
                "field": "is_resting",  # not a Character field
                "value": True,
            }
        ],
    )
    assert r["applied"] == 0
    assert len(r["rejected"]) == 1
    assert "is_resting" in r["rejected"][0]["reason"]
