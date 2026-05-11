from src.game.domain.combat import GraphCombatState, GraphCombatTraceEvent
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.combat_narration_view import combat_narration_view


def test_combat_narration_view_marks_korean_training_dummy_nonlethal():
    runtime = GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(id="player_01", type="character", properties={"name": "당신"}),
                "training_dummy": GraphNode(
                    id="training_dummy",
                    type="character",
                    properties={
                        "name": "훈련용 허수아비",
                        "role": "전투 테스트 대상",
                        "raceJob": "훈련 대상",
                    },
                ),
            },
            edges={},
        ),
        progress=GameProgress(
            game_id="game-1",
            player_id="player_01",
            graph_combat_state=GraphCombatState(
                location_id="test_hub",
                player_id="player_01",
                enemy_ids=["training_dummy"],
                participant_ids=["player_01", "training_dummy"],
                sides={"player_01": "player", "training_dummy": "enemy"},
                trace=[
                    GraphCombatTraceEvent(
                        kind="player_attacked",
                        actor_id="player_01",
                        target_id="training_dummy",
                        state="critical",
                    )
                ],
            ),
        ),
    )

    payload = combat_narration_view(runtime)

    assert payload is not None
    assert payload["tone"] == {"lethality": "nonlethal", "style": "training"}
