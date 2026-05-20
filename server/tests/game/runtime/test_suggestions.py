from unittest.mock import patch

from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.narration.suggestions import (
    GraphSuggestion,
    filter_grounded_suggestions,
)
from src.game.runtime.narration.result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    gm_log_entry_from_narration,
    parse_graph_narration_answer,
)


def _runtime_for_suggestions(*, in_combat: bool = False) -> GameRuntimeState:
    progress = GameProgress(game_id="game-1", player_id="player_01")
    if in_combat:
        progress = progress.model_copy(
            update={
                "graph_combat_state": GraphCombatState(
                    location_id="town",
                    player_id="player_01",
                    active_enemy_id="goblin_01",
                    enemy_ids=["goblin_01"],
                    participant_ids=["player_01", "goblin_01"],
                    sides={"player_01": "player", "goblin_01": "enemy"},
                    player_hearts=3,
                    enemy_hearts=3,
                )
            }
        )
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "town": GraphNode(id="town", type="location", properties={"name": "마을"}),
                "forest": GraphNode(id="forest", type="location", properties={"name": "숲"}),
                "player_01": GraphNode(id="player_01", type="character"),
                "merchant_01": GraphNode(
                    id="merchant_01",
                    type="character",
                    properties={"name": "상인", "alive": True},
                ),
                "goblin_01": GraphNode(
                    id="goblin_01",
                    type="character",
                    properties={"name": "고블린", "alive": True},
                ),
                "healing_herb": GraphNode(
                    id="healing_herb",
                    type="item",
                    properties={"name": "회복 약초"},
                ),
            },
            edges={
                "located_at:player_01:town": GraphEdge(
                    id="located_at:player_01:town",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="town",
                ),
                "located_at:merchant_01:town": GraphEdge(
                    id="located_at:merchant_01:town",
                    type="located_at",
                    from_node_id="merchant_01",
                    to_node_id="town",
                ),
                "located_at:goblin_01:town": GraphEdge(
                    id="located_at:goblin_01:town",
                    type="located_at",
                    from_node_id="goblin_01",
                    to_node_id="town",
                ),
                "connects_to:town:forest": GraphEdge(
                    id="connects_to:town:forest",
                    type="connects_to",
                    from_node_id="town",
                    to_node_id="forest",
                ),
                "carries:player_01:healing_herb": GraphEdge(
                    id="carries:player_01:healing_herb",
                    type="carries",
                    from_node_id="player_01",
                    to_node_id="healing_herb",
                ),
            },
        ),
        progress=progress,
    )


def test_filter_grounded_suggestions_drops_unavailable_move_talk_and_use_targets():
    runtime = _runtime_for_suggestions()

    result = filter_grounded_suggestions(
        runtime,
        [
            GraphSuggestion(label="숲으로", input_text="숲으로 이동합니다", intent="move"),
            GraphSuggestion(label="북문으로", input_text="북문으로 이동합니다", intent="move"),
            GraphSuggestion(label="상인에게", input_text="상인에게 말을 겁니다", intent="talk"),
            GraphSuggestion(label="용에게", input_text="용에게 말을 겁니다", intent="talk"),
            GraphSuggestion(label="약초 사용", input_text="회복 약초를 사용합니다", intent="use"),
            GraphSuggestion(label="열쇠 사용", input_text="은열쇠를 사용합니다", intent="use"),
        ],
    )

    assert [suggestion.input_text for suggestion in result] == [
        "숲으로 이동합니다",
        "상인에게 말을 겁니다",
        "회복 약초를 사용합니다",
    ]


def test_filter_grounded_suggestions_drops_combat_when_not_in_combat():
    runtime = _runtime_for_suggestions()

    result = filter_grounded_suggestions(
        runtime,
        [
            GraphSuggestion(label="공격", input_text="고블린을 공격합니다", intent="combat"),
            GraphSuggestion(label="확인", input_text="주변을 살핍니다", intent="inspect"),
        ],
    )

    assert [suggestion.input_text for suggestion in result] == ["주변을 살핍니다"]


def test_filter_grounded_suggestions_keeps_combat_when_in_combat():
    runtime = _runtime_for_suggestions(in_combat=True)

    result = filter_grounded_suggestions(
        runtime,
        [GraphSuggestion(label="공격", input_text="고블린을 공격합니다", intent="combat")],
    )

    assert [suggestion.input_text for suggestion in result] == ["고블린을 공격합니다"]


def test_parse_graph_narration_answer_accepts_structured_suggestions():
    answer = "\n".join(
        [
            "당신은 북문 쪽으로 시선을 돌립니다.",
            "---TRPG_META---",
            """
            {
              "turn_summary": "북문을 살필 준비를 합니다.",
              "importance": 2,
              "suggestions": [
                {
                  "label": "북문으로",
                  "input_text": "북문으로 이동합니다",
                  "intent": "move",
                  "action": null
                }
              ]
            }
            """,
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.suggestions[0].model_dump() == {
        "label": "북문으로",
        "input_text": "북문으로 이동합니다",
        "intent": "move",
        "action": None,
    }


def test_parse_graph_narration_answer_accepts_ui_cues():
    answer = "\n".join(
        [
            "당신은 경비병의 움직임을 살핍니다.",
            "---TRPG_META---",
            """
            {
              "ui_cues": [
                {
                  "kind": "change",
                  "label": "변화",
                  "text": "경비병이 문 앞에서 멈춤",
                  "scope": "delta"
                },
                {
                  "kind": "opportunity",
                  "label": "기회",
                  "text": "짧게 말을 걸 수 있음",
                  "scope": "temporary"
                }
              ]
            }
            """,
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.narration == "당신은 경비병의 움직임을 살핍니다."
    assert [cue.model_dump() for cue in result.ui_cues] == [
        {
            "kind": "change",
            "label": "변화",
            "text": "경비병이 문 앞에서 멈춤",
            "scope": "delta",
        },
        {
            "kind": "opportunity",
            "label": "기회",
            "text": "짧게 말을 걸 수 있음",
            "scope": "temporary",
        },
    ]


def test_parse_graph_narration_answer_ignores_invalid_ui_cues():
    answer = "\n".join(
        [
            "당신은 잠시 숨을 고릅니다.",
            "---TRPG_META---",
            """
            {
              "ui_cues": [
                {
                  "kind": "change",
                  "label": "변화",
                  "text": "복도 끝의 불빛이 약해짐",
                  "scope": "delta"
                },
                "not a cue",
                {
                  "kind": "mood",
                  "label": "분위기",
                  "text": "긴장감이 감돎",
                  "scope": "delta"
                },
                {
                  "kind": "warning",
                  "label": "",
                  "text": "문 너머에서 발소리가 들림",
                  "scope": "temporary"
                },
                {
                  "kind": "warning",
                  "label": "경고",
                  "text": "문 너머에서 발소리가 들림",
                  "scope": "temporary"
                }
              ]
            }
            """,
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert [cue.model_dump() for cue in result.ui_cues] == [
        {
            "kind": "change",
            "label": "변화",
            "text": "복도 끝의 불빛이 약해짐",
            "scope": "delta",
        },
        {
            "kind": "warning",
            "label": "경고",
            "text": "문 너머에서 발소리가 들림",
            "scope": "temporary",
        },
    ]


def test_parse_graph_narration_answer_respects_zero_ui_cue_limit(monkeypatch):
    monkeypatch.setenv("GRAPH_NARRATION_MAX_UI_CUES", "0")
    answer = "\n".join(
        [
            "당신은 경비병의 움직임을 살핍니다.",
            "---TRPG_META---",
            """
            {
              "ui_cues": [
                {
                  "kind": "change",
                  "label": "변화",
                  "text": "경비병이 문 앞에서 멈춤",
                  "scope": "delta"
                }
              ]
            }
            """,
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.ui_cues == []


def test_gm_log_entry_from_narration_serializes_non_empty_ui_cues():
    result = GraphNarrationResult(
        narration="당신은 북문 앞에 섭니다.",
        ui_cues=[
            {
                "kind": "opportunity",
                "label": "기회",
                "text": "경비 교대가 곧 시작됨",
                "scope": "temporary",
            }
        ],
    )

    entry = gm_log_entry_from_narration(7, result, outcome="neutral")

    assert entry.model_dump() == {
        "id": 7,
        "kind": "gm",
        "text": "당신은 북문 앞에 섭니다.",
        "outcome": "neutral",
        "cues": [
            {
                "kind": "opportunity",
                "label": "기회",
                "text": "경비 교대가 곧 시작됨",
                "scope": "temporary",
            }
        ],
    }


def test_gm_log_entry_from_narration_omits_empty_ui_cues():
    result = GraphNarrationResult(narration="당신은 잠시 기다립니다.")

    entry = gm_log_entry_from_narration(8, result)

    assert entry.model_dump() == {
        "id": 8,
        "kind": "gm",
        "text": "당신은 잠시 기다립니다.",
    }


def test_parse_graph_narration_answer_normalizes_legacy_string_suggestions():
    answer = "\n".join(
        [
            "상대가 당신의 말을 기다립니다.",
            "---TRPG_META---",
            """
            {
              "suggestions": [
                "상인에게 다시 묻습니다",
                {"label": "대답 기다리기", "input_text": "상인의 대답을 기다립니다"}
              ]
            }
            """,
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.suggestions[0].model_dump() == {
        "label": "상인에게 다시 묻습니다",
        "input_text": "상인에게 다시 묻습니다",
        "intent": None,
        "action": None,
    }
    assert result.suggestions[1].model_dump() == {
        "label": "대답 기다리기",
        "input_text": "상인의 대답을 기다립니다",
        "intent": None,
        "action": None,
    }


def test_parse_graph_narration_answer_drops_json_fragment_suggestions():
    answer = "\n".join(
        [
            "루카가 짧게 고개를 끄덕입니다.",
            "---TRPG_META---",
            """
            {
              "suggestions": [
                "{\\"label\\":\\"루카에게 말을 겁니다\\",\\"input_te",
                {"label": "다시 묻기", "input_text": "루카에게 다시 묻습니다"}
              ]
            }
            """,
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert [suggestion.input_text for suggestion in result.suggestions] == [
        "루카에게 다시 묻습니다"
    ]


def test_parse_graph_narration_answer_removes_empty_direct_speech_lines():
    answer = "\n".join(
        [
            "루카가 체크리스트를 접습니다.",
            "「」",
            "「   」",
            '""',
            "그는 문가로 한 걸음 물러섭니다.",
            "---TRPG_META---",
            '{"suggestions": []}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.narration == (
        "루카가 체크리스트를 접습니다.\n그는 문가로 한 걸음 물러섭니다."
    )


def test_parse_graph_narration_answer_strips_trailing_ascii_quote_junk():
    answer = "\n".join(
        [
            '선장이 낮게 말합니다. 「돌아갈 배라... 조건이 까다롭지.\\"\\"\\"',
            "---TRPG_META---",
            '{"suggestions": []}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.narration == "선장이 낮게 말합니다. 「돌아갈 배라... 조건이 까다롭지."


def test_parse_graph_narration_answer_uses_env_marker(monkeypatch):
    monkeypatch.setenv("GRAPH_NARRATION_META_MARKER", "---META---")
    answer = "\n".join(
        [
            "상대가 고개를 끄덕입니다.",
            "---META---",
            '{"suggestions": ["다시 묻습니다"]}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.suggestions[0].input_text == "다시 묻습니다"


def test_parse_graph_narration_answer_uses_env_suggestion_limits(monkeypatch):
    monkeypatch.setenv("GRAPH_NARRATION_MAX_SUGGESTIONS", "1")
    monkeypatch.setenv("GRAPH_NARRATION_MAX_SUGGESTION_CHARS", "4")
    answer = "\n".join(
        [
            "상대가 길을 가리킵니다.",
            "---TRPG_META---",
            '{"suggestions": ["북문으로 이동합니다", "광장으로 돌아갑니다"]}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert len(result.suggestions) == 1
    assert result.suggestions[0].input_text == "북문으로"


def test_parse_graph_narration_answer_logs_missing_meta_marker():
    with patch("src.game.runtime.narration.result.llm_diag") as diag:
        result = parse_graph_narration_answer("당신은 잠시 기다립니다.")

    assert result.narration == "당신은 잠시 기다립니다."
    diag.assert_called_once_with("llm:graph_narrate_meta_missing", answer_len=13)


def test_parse_graph_narration_answer_logs_invalid_meta_json():
    answer = "당신은 잠시 기다립니다.\n---TRPG_META---\n{"

    with patch("src.game.runtime.narration.result.llm_diag") as diag:
        result = parse_graph_narration_answer(answer)

    assert result.narration == "당신은 잠시 기다립니다."
    diag.assert_called_once_with(
        "llm:graph_narrate_meta_invalid",
        err="JSONDecodeError",
        meta_len=1,
    )


def test_parse_graph_narration_answer_drops_private_patch_blocks():
    answer = "\n".join(
        [
            "경비가 창고 쪽으로 다가옵니다.",
            "<STATE_PATCH>",
            '{"guard_alert": 3}',
            "</STATE_PATCH>",
            "---TRPG_META---",
            '{"suggestions": []}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.narration == "경비가 창고 쪽으로 다가옵니다."


def test_visible_narration_stream_stops_before_split_private_marker():
    stream = VisibleNarrationStream()

    visible = [
        *stream.push("경비가 다가옵니다.\n<STA"),
        *stream.push("TE_PATCH>{}"),
        *stream.finish(),
    ]

    assert "".join(visible) == "경비가 다가옵니다."
