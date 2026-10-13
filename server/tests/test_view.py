from pathlib import Path

import pytest
from src.content import load_story
from src.game.engine import choose, new_game
from src.view import game_view


@pytest.mark.parametrize(
    "actions",
    [
        [],
        ["move:prison", "guard.fight"],
        ["move:prison", "guard.fight", "combat.skill:brace"],
        ["move:prison", "guard.bribe", "sailor.rescue", "move:square", "escape"],
    ],
)
def test_reading_the_view_does_not_spend_resources_roll_dice_or_advance_time(actions):
    story = load_story(
        Path(__file__).resolve().parents[2] / "scenarios/harbor/adventure.json"
    )
    state = new_game(story, "Tester", "listener", seed=7)
    for action in actions:
        state = choose(story, state, action)
    before = state.model_dump_json()

    first = game_view(story, state)
    second = game_view(story, state)

    assert first == second
    assert state.model_dump_json() == before
