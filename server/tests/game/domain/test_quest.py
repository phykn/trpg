from src.game.domain.graph import GraphNode
from src.game.domain.quest import (
    quest_choices,
    quest_progress,
    quest_ready_to_decide,
    quest_triggers,
    quest_triggers_met,
)


def test_quest_helpers_normalize_trigger_progress_and_choices():
    quest = GraphNode(
        id="quest_1",
        type="quest",
        properties={
            "triggers": [
                {"type": "location_enter", "target": "town"},
                "bad",
                {"type": "social_check", "target": "npc"},
            ],
            "triggers_met": [True, "bad"],
            "choices": {
                "record": {"label": "Record"},
                "": {"label": "Skip"},
                "bad": "shape",
            },
        },
    )

    assert quest_triggers(quest) == [
        {"type": "location_enter", "target": "town"},
        {"type": "social_check", "target": "npc"},
    ]
    assert quest_triggers_met(quest) == [True, False]
    assert quest_progress(quest) == (1, 2)
    assert quest_ready_to_decide(quest) is False
    assert quest_choices(quest) == {"record": {"label": "Record"}}


def test_quest_without_triggers_is_ready_to_decide():
    quest = GraphNode(id="quest_1", type="quest", properties={})

    assert quest_progress(quest) == (0, 0)
    assert quest_ready_to_decide(quest) is True
