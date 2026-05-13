import pytest

from src.game.domain.action import Action
from src.game.runtime.pending_action import (
    build_pending_action_payload,
    load_pending_action,
)


def test_build_pending_action_payload_round_trips_action():
    payload = build_pending_action_payload(Action(verb="attack", what=["goblin_01"]))

    assert payload == {
        "kind": "graph_action",
        "action": {
            "verb": "attack",
            "what": ["goblin_01"],
            "from": None,
            "to": None,
            "with": None,
            "how": None,
            "note": None,
        },
    }
    assert load_pending_action({"payload": payload}).verb == "attack"


def test_load_pending_action_raises_requested_error_type():
    class PendingExpected(ValueError):
        pass

    with pytest.raises(PendingExpected, match="pending graph action missing"):
        load_pending_action({}, error_type=PendingExpected)
