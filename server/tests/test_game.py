from pathlib import Path

import pytest
from src.content import load_story
from src.game.engine import choose, new_game
from src.view import game_view


@pytest.fixture
def story():
    return load_story(
        Path(__file__).resolve().parents[2] / "scenarios/harbor/adventure.json"
    )


def play(story, actions, *, role="listener", seed=7):
    state = new_game(story, "Tester", role, seed=seed)
    for action in actions:
        state = choose(story, state, action)
    return state


def test_debt_route_rescues_sailor_and_reaches_ending_without_combat(story):
    state = play(
        story,
        [
            "move:tavern",
            "keeper.debt",
            "keeper.promise",
            "move:prison",
            "guard.promise",
            "sailor.rescue",
            "move:warehouse",
            "ledger.take",
            "move:tavern",
            "keeper.ledger",
            "move:square",
            "escape",
        ],
    )
    view = game_view(story, state)
    assert view.ending is not None
    assert view.ending.id == "bargain"
    assert not view.actions
    assert state.graph.nodes["chapter"].properties["violence"] == 0


def test_evidence_route_is_a_distinct_peaceful_ending(story):
    state = play(
        story,
        [
            "move:warehouse",
            "manifest.read",
            "ledger.take",
            "move:square",
            "inspector.evidence",
            "move:prison",
            "guard.order",
            "sailor.rescue",
            "move:square",
            "inspector.ledger",
            "escape",
        ],
    )
    assert game_view(story, state).ending.id == "public"


def test_battle_can_end_through_understanding_and_mercy(story):
    state = play(
        story,
        [
            "move:prison",
            "guard.fight",
            "combat.listen",
            "combat.reassure",
            "combat.mercy",
        ],
    )
    assert state.combat is None
    assert state.graph.nodes["guard"].properties["alive"] is True
    assert state.graph.nodes["chapter"].properties["gate_open"] is True
    assert state.graph.nodes["chapter"].properties["violence"] == 0
    assert "sailor.rescue" in [a.id for a in game_view(story, state).actions]


def test_skill_cost_is_visible_beside_time_and_chance(story):
    state = play(story, ["move:prison", "guard.fight"])
    action = next(
        action
        for action in game_view(story, state).actions
        if action.id == "combat.skill:brace"
    )
    assert "기술 자원 1" in action.cost


def test_hidden_information_is_not_in_initial_public_view(story):
    state = new_game(story, "Tester", "listener", seed=7)
    payload = game_view(story, state).model_dump_json()
    assert "guard_debt" not in payload
    assert "forgery" not in payload
    assert "rng_seed" not in payload
    assert "graph" not in game_view(story, state).model_dump()
    assert game_view(story, state).knowledge == []


@pytest.mark.parametrize("resource, cost", [("gold", 12), ("mp", 4)])
def test_paid_check_uses_the_threshold_before_spending(
    story, monkeypatch, resource, cost
):
    from src.game.models import Check, Choice, Result

    story.choices.append(
        Choice(
            id="paid.check",
            target="player",
            label="Try",
            description="Spend the last resource on a check.",
            check=Check(stat="presence", dc=12),
            success=Result(text="Success"),
            failure=Result(text="Failure"),
            **{resource: cost},
        )
    )
    state = new_game(story, "Tester", "listener", seed=7)
    monkeypatch.setattr("src.game.engine._roll", lambda _: 10)

    next_state = choose(story, state, "paid.check")

    assert next_state.graph.nodes["player"].properties[resource] == 0
    assert state.graph.nodes["player"].properties[resource] == cost
    assert next_state.journal[-2].values["required"] == 10
    assert next_state.journal[-1].text == "Success"


def test_unknown_and_repeated_choices_cannot_grant_rewards(story):
    state = play(story, ["move:warehouse", "ledger.take"])
    before = state.model_dump_json()
    with pytest.raises(ValueError):
        choose(story, state, "ledger.take")
    with pytest.raises(ValueError):
        choose(story, state, "guard.promise")
    assert state.model_dump_json() == before


def test_same_seed_and_commands_reproduce_roll_and_state(story):
    actions = ["move:warehouse", "shift.read", "tunnel.sneak"]
    first = play(story, actions, seed=25)
    second = play(story, actions, seed=25)
    assert first.graph == second.graph
    assert first.journal == second.journal
    assert first.rng_step == second.rng_step == 1


def test_failed_sneak_keeps_another_route_and_cannot_be_spammed(story):
    state = next(
        state
        for seed in range(100)
        if not (
            state := play(
                story, ["move:warehouse", "shift.read", "tunnel.sneak"], seed=seed
            )
        )
        .graph.nodes["chapter"]
        .properties["gate_open"]
    )
    assert state.graph.nodes["chapter"].properties["alert"] > 0
    assert "tunnel.sneak" not in [a.id for a in game_view(story, state).actions]
    for action in [
        "move:tavern",
        "keeper.debt",
        "keeper.promise",
        "move:prison",
        "guard.promise",
        "sailor.rescue",
        "move:square",
        "escape",
    ]:
        state = choose(story, state, action)
    assert game_view(story, state).ending is not None


def test_deadline_produces_an_ending_instead_of_a_dead_end(story):
    state = new_game(story, "Tester", "listener", seed=7)
    for _ in range(story.deadline // 2):
        state = choose(story, state, "move:tavern")
        state = choose(story, state, "move:square")
    assert game_view(story, state).ending.id == "departed"
    assert not game_view(story, state).actions


def test_attacking_has_a_persistent_consequence(story):
    state = play(story, ["move:prison", "guard.fight"], role="warden", seed=7)
    for _ in range(15):
        if state.combat is None:
            break
        state = choose(story, state, "combat.attack")
    assert state.combat is None
    if state.graph.nodes["chapter"].properties["gate_open"]:
        assert state.graph.nodes["chapter"].properties["violence"] == 1
        assert state.graph.nodes["guard"].properties["alive"] is False
    else:
        assert state.graph.nodes["player"].properties["hp"] > 0
        assert "move:tavern" in [a.id for a in game_view(story, state).actions]


def test_lethal_victory_changes_scene_and_epilogue(story, monkeypatch):
    monkeypatch.setattr("src.game.engine._roll", lambda _: 20)
    state = play(story, ["move:prison", "guard.fight", *["combat.attack"] * 3])
    assert state.graph.nodes["guard"].properties["alive"] is False
    assert game_view(story, state).scene.text != story.descriptions["prison"].text
    for action in ["sailor.rescue", "move:square", "escape"]:
        state = choose(story, state, action)
    view = game_view(story, state)
    assert view.ending.id == "quiet"
    assert len(view.ending.epilogue) == 1


def test_defeat_is_a_costly_retreat_with_a_peaceful_recovery_route(story, monkeypatch):
    monkeypatch.setattr("src.game.engine._roll", lambda _: 1)
    state = play(story, ["move:prison", "guard.fight", *["combat.attack"] * 3])
    view = game_view(story, state)
    assert view.scene.id == "square"
    assert view.hp == 5
    assert view.gold == 9
    for action in [
        "move:warehouse",
        "manifest.read",
        "move:square",
        "inspector.evidence",
        "move:prison",
        "guard.order",
        "sailor.rescue",
        "move:square",
        "escape",
    ]:
        state = choose(story, state, action)
    assert game_view(story, state).ending.id == "quiet"


def test_exhausted_skill_is_visible_but_cannot_be_used_and_bandage_consumes_once(
    story, monkeypatch
):
    monkeypatch.setattr("src.game.engine._roll", lambda _: 20)
    state = play(story, ["move:prison", "guard.fight", *["combat.skill:brace"] * 4])
    skill = next(
        a for a in game_view(story, state).actions if a.id == "combat.skill:brace"
    )
    assert skill.enabled is False
    with pytest.raises(ValueError):
        choose(story, state, skill.id)
    monkeypatch.setattr("src.game.engine._roll", lambda _: 1)
    state = choose(story, state, "combat.attack")
    assert state.combat.player_hearts == 2
    state = choose(story, state, "item:bandage")
    assert state.combat.player_hearts == 3
    assert "bandage" not in [item.id for item in game_view(story, state).inventory]
    with pytest.raises(ValueError):
        choose(story, state, "item:bandage")


def test_rescue_grants_exactly_one_growth_choice_and_companion_follows(story):
    state = play(
        story,
        ["move:prison", "guard.bribe", "sailor.rescue", "growth:steady", "move:square"],
    )
    view = game_view(story, state)
    assert "sailor" in [person.id for person in view.characters]
    assert {skill.id for skill in view.skills} == {"brace", "steady"}
    assert not any(action.group == "growth" for action in view.actions)


@pytest.mark.parametrize(
    "case",
    [
        "unknown_reference",
        "duplicate_id",
        "system_command",
        "invalid_role_skill",
        "missing_blocked",
        "wrong_effect_type",
    ],
)
def test_invalid_authored_content_fails_before_play(story, tmp_path, case):
    data = story.model_dump(mode="json", by_alias=True)
    if case == "unknown_reference":
        data["choices"][0]["show"][0]["target"] = "missing"
    elif case == "duplicate_id":
        data["choices"].append(data["choices"][0])
    elif case == "system_command":
        data["choices"][0]["system"] = True
    elif case == "invalid_role_skill":
        data["roles"]["listener"]["skill"] = "guard"
    elif case == "missing_blocked":
        next(c for c in data["choices"] if c["id"] == "guard.order")["blocked"] = ""
    else:
        data["choices"][0]["success"]["effects"] = [
            {"kind": "learn", "target": "guard"}
        ]
    import json

    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_story(path)
