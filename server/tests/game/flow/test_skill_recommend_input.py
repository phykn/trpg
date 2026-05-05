"""existing_skills[*] carries target + primary_stat; special_effect dropped."""

from src.game.domain.entities import Character, Skill, Stats
from src.game.domain.state import GameState
from src.game.flow.skill_recommend import _build_input  # type: ignore[attr-defined]


def _state_with_player_skill() -> GameState:
    state = GameState(game_id="g", profile="p", player_id="player_01")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        stats=Stats(),
        learned_skill_ids=["s_heal"],
    )
    state.skills["s_heal"] = Skill(
        id="s_heal",
        name="치유",
        type="heal",
        target="self",
        primary_stat="WIS",
        description="자가 치유",
        special_effect="warm glow",
    )
    return state


def test_existing_skills_have_dedup_keys():
    state = _state_with_player_skill()
    inp = _build_input(state)
    skill = inp.existing_skills[0]
    assert skill["name"] == "치유"
    assert skill["type"] == "heal"
    assert skill["target"] == "self"
    assert skill["primary_stat"] == "WIS"
    assert skill["description"] == "자가 치유"
    assert "special_effect" not in skill
