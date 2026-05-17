from src.game.domain.combat import GraphCombatState, GraphCombatTraceEvent
from src.game.domain.content import RuntimeContent
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.narration.combat_view import combat_narration_view


def test_combat_narration_view_marks_korean_training_dummy_nonlethal():
    runtime = GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01", type="character", properties={"name": "당신"}
                ),
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


def test_combat_narration_view_exposes_latest_exchange_result():
    runtime = GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01", type="character", properties={"name": "당신"}
                ),
                "training_dummy": GraphNode(
                    id="training_dummy",
                    type="character",
                    properties={"name": "훈련용 허수아비"},
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
                        kind="combat_started",
                        actor_id="player_01",
                        target_id="training_dummy",
                    ),
                    GraphCombatTraceEvent(
                        kind="player_precise_failure",
                        actor_id="player_01",
                        target_id="training_dummy",
                        state="healthy",
                    ),
                ],
            ),
        ),
    )

    payload = combat_narration_view(runtime)

    assert payload is not None
    assert payload["exchange_result"] == "failure"
    assert payload["exchange_result_label"] == "이번 교환은 실패입니다"
    assert payload["events"][-1]["result"] == "failure"
    assert payload["events"][-1]["result_label"] == "이번 교환은 실패입니다"


def test_combat_narration_view_exposes_effect_context():
    runtime = GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01", type="character", properties={"name": "당신"}
                ),
                "training_dummy": GraphNode(
                    id="training_dummy",
                    type="character",
                    properties={"name": "훈련용 허수아비"},
                ),
                "training_strike": GraphNode(
                    id="training_strike",
                    type="skill",
                    properties={"effect": "dc_down"},
                ),
                "dc_down": GraphNode(
                    id="dc_down",
                    type="effect",
                    properties={},
                ),
            },
            edges={},
        ),
        content=RuntimeContent(
            skills={"training_strike": {"id": "training_strike", "name": "훈련 일격"}},
            effects={
                "dc_down": {
                    "id": "dc_down",
                    "name": "판정 난이도 감소",
                    "description": "판정 난이도를 낮춥니다.",
                    "traits": ["성공 가능성을 높입니다"],
                }
            },
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
                last_support_id="training_strike",
                last_support_kind="skill",
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
    assert payload["effect"] == {
        "id": "dc_down",
        "name": "판정 난이도 감소",
        "description": "판정 난이도를 낮춥니다.",
        "traits": ["성공 가능성을 높입니다"],
    }


def test_combat_narration_view_exposes_status_context_from_last_support():
    runtime = GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01", type="character", properties={"name": "당신"}
                ),
                "training_dummy": GraphNode(
                    id="training_dummy",
                    type="character",
                    properties={"name": "훈련용 허수아비"},
                ),
                "focus_charm": GraphNode(
                    id="focus_charm",
                    type="item",
                    properties={"status_ids": ["focused"]},
                ),
                "focused": GraphNode(id="focused", type="status", properties={}),
            },
            edges={},
        ),
        content=RuntimeContent(
            items={"focus_charm": {"id": "focus_charm", "name": "집중 부적"}},
            statuses={
                "focused": {
                    "id": "focused",
                    "name": "집중",
                    "description": "주의가 흐트러지지 않은 상태입니다.",
                    "traits": ["다음 행동을 차분하게 이어갑니다"],
                }
            },
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
                last_support_id="focus_charm",
                last_support_kind="item",
                trace=[
                    GraphCombatTraceEvent(
                        kind="player_defended",
                        actor_id="player_01",
                        target_id="training_dummy",
                        state="healthy",
                    )
                ],
            ),
        ),
    )

    payload = combat_narration_view(runtime)

    assert payload is not None
    assert payload["statuses"] == [
        {
            "id": "focused",
            "name": "집중",
            "description": "주의가 흐트러지지 않은 상태입니다.",
            "traits": ["다음 행동을 차분하게 이어갑니다"],
        }
    ]
