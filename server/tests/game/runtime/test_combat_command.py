import pytest
from pydantic import ValidationError

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphNode
from src.api.schema import GraphCombatCommandRequest
from src.game.domain.progress import GameProgress
from src.game.runtime.action.combat_command import (
    CombatCommandError,
    build_combat_command_action,
)
from src.game.runtime.state import GameRuntimeState


def _runtime() -> GameRuntimeState:
    progress = GameProgress(
        game_id="game-1",
        player_id="player_01",
        locale="ko",
        graph_combat_state=GraphCombatState(
            player_id="player_01",
            location_id="loc_01",
            active_enemy_id="enemy_01",
            enemy_ids=["enemy_01"],
            participant_ids=["player_01", "enemy_01"],
            sides={"player_01": "player", "enemy_01": "enemy"},
            player_hearts=3,
            enemy_hearts=2,
            round=1,
            outcome="ongoing",
            trace=[],
        ),
    )
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(id="player_01", type="character"),
                "basic_strike": GraphNode(id="basic_strike", type="skill"),
                "enemy_01": GraphNode(id="enemy_01", type="character"),
            }
        ),
        progress=progress,
    )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"command": "precise", "target": "enemy_01"},
            Action(verb="attack", what="enemy_01", how="precise"),
        ),
        (
            {
                "command": "precise",
                "target": "enemy_01",
                "support_id": "basic_strike",
                "support_kind": "skill",
            },
            Action(verb="attack", what="enemy_01", how="precise", with_="basic_strike"),
        ),
        (
            {"command": "reckless", "target": "enemy_01"},
            Action(verb="attack", what="enemy_01", how="reckless"),
        ),
        ({"command": "defend"}, Action(verb="pass", how="defend")),
        ({"command": "guarded"}, Action(verb="pass", how="guarded")),
        ({"command": "create_distance"}, Action(verb="move", how="create_distance")),
        (
            {"command": "talk", "target": "enemy_01"},
            Action(verb="speak", to="enemy_01"),
        ),
    ],
)
def test_build_combat_command_action(payload, expected):
    assert build_combat_command_action(_runtime(), payload) == expected


def test_rejects_when_not_in_combat():
    runtime = _runtime()
    runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(update={"graph_combat_state": None})
        }
    )

    with pytest.raises(CombatCommandError, match="combat is not active"):
        build_combat_command_action(runtime, {"command": "guarded"})


def test_rejects_wrong_target():
    with pytest.raises(CombatCommandError, match="target is not active enemy"):
        build_combat_command_action(
            _runtime(),
            {"command": "precise", "target": "enemy_02"},
        )


@pytest.mark.parametrize("command", ["attack", "skill", "flee"])
def test_graph_combat_command_request_rejects_legacy_commands(command):
    with pytest.raises(ValidationError):
        GraphCombatCommandRequest.model_validate({"command": command})


def test_graph_combat_command_request_requires_support_pair():
    with pytest.raises(ValidationError):
        GraphCombatCommandRequest.model_validate(
            {
                "command": "precise",
                "target": "enemy_01",
                "support_id": "basic_strike",
            }
        )
