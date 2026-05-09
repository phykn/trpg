from src.game.domain.memory import PendingCheck
from src.llm.calls.classify.schema import Verb


def test_pending_check_default_no_triggering_verb():
    p = PendingCheck(
        player_input="x",
        tier="normal",
        stat="CHA",
        target="n_01",
        targets=["n_01"],
        dc=12,
        mod=0,
        required_roll=12,
        reason="x",
        created_at="2026-05-04T00:00:00Z",
    )
    assert p.triggering_verb is None
    assert p.pending_verbs == []
    assert p.kind == "stat"


def test_pending_check_with_verb_fields():
    v = Verb(name="speak", modifiers={"intent": "recruit", "target": "n_01"})
    p = PendingCheck(
        player_input="x",
        tier="normal",
        stat="CHA",
        target="n_01",
        targets=["n_01"],
        dc=12,
        mod=0,
        required_roll=12,
        reason="x",
        created_at="2026-05-04T00:00:00Z",
        triggering_verb=v,
        pending_verbs=[Verb(name="wait")],
    )
    assert p.triggering_verb.name == "speak"
    assert len(p.pending_verbs) == 1


def test_pending_check_round_trip():
    v = Verb(name="speak", modifiers={"intent": "recruit", "target": "n_01"})
    p = PendingCheck(
        player_input="x",
        tier="normal",
        stat="CHA",
        target="n_01",
        targets=["n_01"],
        dc=12,
        mod=0,
        required_roll=12,
        reason="x",
        created_at="2026-05-04T00:00:00Z",
        triggering_verb=v,
    )
    j = p.model_dump_json()
    restored = PendingCheck.model_validate_json(j)
    assert restored.triggering_verb.modifiers["intent"] == "recruit"
