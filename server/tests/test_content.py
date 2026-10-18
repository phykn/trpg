import json

import pytest
from conftest import REPO, TEMPLATE
from pydantic import ValidationError
from src.content.load import check_creation, load_story, new_game, story_folders
from src.content.schema import Story
from src.content.validate import validate


def raw():
    return json.loads((TEMPLATE / "scenario.json").read_text(encoding="utf-8"))


def errors_for(data) -> list[str]:
    return validate(Story.model_validate(data))


def test_every_story_folder_is_valid():
    folders = story_folders(REPO / "scenarios")
    assert TEMPLATE in folders
    for folder in folders:
        assert validate(load_story(folder).story) == [], folder.name


def test_unknown_field_is_rejected():
    data = raw()
    data["places"]["square"]["colour"] = "red"
    with pytest.raises(ValidationError):
        Story.model_validate(data)


def test_obstacle_needs_two_solutions():
    data = raw()
    data["obstacles"]["lamp"]["solutions"] = data["obstacles"]["lamp"]["solutions"][:1]
    assert "obstacle lamp: needs 2 or more solutions" in errors_for(data)


def test_unknown_reference_is_reported():
    data = raw()
    data["characters"]["mira"]["knows"].append("kn_missing")
    assert any("kn_missing" in e for e in errors_for(data))


def test_topic_needs_two_free_paths():
    data = raw()
    data["topics"][0]["free_when"] = data["topics"][0]["free_when"][:1]
    assert any("free_when" in e for e in errors_for(data))


def test_unreachable_ending_is_reported():
    data = raw()
    data["endings"][0]["when"] = [{"kind": "flag", "target": "never_set", "value": True}]
    assert "ending calm: cannot be reached" in errors_for(data)


def test_ending_behind_closed_exit_is_unreachable():
    data = raw()
    data["obstacles"]["door"]["on_full"] = [{"kind": "flag", "target": "door_open", "value": True}]
    errors = errors_for(data)
    assert "ending calm: cannot be reached" in errors


def test_invalid_ids_and_senses():
    data = raw()
    data["places"]["Square"] = data["places"].pop("square")
    data["places"]["base"]["senses"] = ["하나"]
    errors = errors_for(data)
    assert "invalid node id: Square" in errors
    assert "place base: needs 3 to 5 senses" in errors


def test_creation_spread_and_traits(story):
    check_creation(story, {"force": 2, "finesse": 1, "wits": 1, "charm": 0}, ["trait_fearless", "trait_in_debt"])
    with pytest.raises(ValueError):
        check_creation(story, {"force": 3, "finesse": 1, "wits": 0, "charm": 0}, ["trait_fearless", "trait_in_debt"])
    with pytest.raises(ValueError):
        check_creation(story, {"force": 2, "finesse": 1, "wits": 1, "charm": 0}, ["trait_fearless"])


def test_new_game_uses_choices_only_when_story_allows(story):
    chosen = new_game(story, game_id="g", seed=1, approaches={"force": 2, "finesse": 1, "wits": 1, "charm": 0},
                      traits=["trait_fearless", "trait_in_debt"])
    assert chosen.player.approaches["force"] == 2
    fixed_story = story.model_copy(deep=True)
    fixed_story.creation.choose = False
    fixed = new_game(fixed_story, game_id="g", seed=1, approaches={"force": 2, "finesse": 1, "wits": 1, "charm": 0},
                     traits=["trait_fearless", "trait_in_debt"])
    assert fixed.player.approaches == story.creation.approaches


def test_initial_graph_places_everyone(state):
    g = state.graph
    assert g.edge("at", "player", "square")
    assert g.edge("at", "mira", "square")
    assert g.edge("connects", "base", "top").props["open"] is False
    assert not g.into("spare_key")
