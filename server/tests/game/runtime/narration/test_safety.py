from types import SimpleNamespace

from src.game.domain.action import Action
from src.game.domain.graph import GraphNode
from src.game.runtime.narration.result import GraphNarrationResult
from src.game.runtime.narration.safety import guard_speak_narration_player_quote


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(
        graph=SimpleNamespace(
            nodes={
                "npc_noah": GraphNode(
                    id="npc_noah",
                    type="character",
                    properties={"name": "노아"},
                )
            }
        ),
        content={},
        progress=SimpleNamespace(locale="ko"),
    )


def test_speak_guard_replaces_npc_echoing_player_question():
    result = guard_speak_narration_player_quote(
        _runtime(),
        Action(verb="speak", to="npc_noah"),
        "npc_noah",
        GraphNarrationResult(
            narration="노아가 「환불할 물건도 증명할 분노도 없는데, 왜 빈손으로 서 계신 겁니까?」라고 묻습니다."
        ),
        "노아에게 환불할 물건도 증명할 분노도 없는데 왜 빈손인지 묻습니다.",
    )

    assert result.narration == "노아에게 말을 겁니다."
