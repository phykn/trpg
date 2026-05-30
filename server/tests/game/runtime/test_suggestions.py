from unittest.mock import patch

from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import PlayerLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.narration.suggestions import (
    GraphSuggestion,
    build_intro_suggestions,
    filter_grounded_suggestions,
    next_turn_suggestions,
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
                "quest_01": GraphNode(
                    id="quest_01",
                    type="quest",
                    properties={"title": "숲으로", "status": "active"},
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


def test_filter_grounded_suggestions_drops_recent_repeated_player_input():
    runtime = _runtime_for_suggestions()
    runtime.log_entries.append(
        PlayerLogEntry(id=1, kind="player", text="상인에게 말을 겁니다")
    )

    result = filter_grounded_suggestions(
        runtime,
        [
            GraphSuggestion(label="대화", input_text="상인에게 말을 겁니다", intent="talk"),
            GraphSuggestion(label="숲으로", input_text="숲으로 이동합니다", intent="move"),
        ],
    )

    assert [suggestion.input_text for suggestion in result] == ["숲으로 이동합니다"]


def test_next_turn_suggestions_falls_back_to_visible_actions_without_repeating_recent():
    runtime = _runtime_for_suggestions()
    runtime.log_entries.append(
        PlayerLogEntry(id=1, kind="player", text="상인에게 말을 겁니다")
    )

    result = next_turn_suggestions(runtime, [])

    assert [suggestion.input_text for suggestion in result] == [
        "숲으로 이동합니다",
        "주변을 살핍니다",
    ]


def test_next_turn_suggestions_repeats_visible_actions_when_all_are_recent():
    runtime = _runtime_for_suggestions()
    runtime.log_entries.extend(
        [
            PlayerLogEntry(id=1, kind="player", text="상인에게 말을 겁니다"),
            PlayerLogEntry(id=2, kind="player", text="숲으로 이동합니다"),
            PlayerLogEntry(id=3, kind="player", text="주변을 살핍니다"),
        ]
    )

    result = next_turn_suggestions(runtime, [])

    assert [suggestion.input_text for suggestion in result] == [
        "상인에게 말을 겁니다",
        "숲으로 이동합니다",
        "주변을 살핍니다",
    ]


def test_next_turn_suggestions_uses_visible_generated_clue_when_generic_inspect_is_recent():
    runtime = _runtime_for_suggestions()
    runtime.graph.nodes["clue_signpost"] = GraphNode(
        id="clue_signpost",
        type="knowledge",
        properties={
            "kind": "clue",
            "title": "북쪽 길목의 표지판",
            "summary": "북쪽을 가리킵니다.",
            "visibility": "player",
        },
    )
    runtime.log_entries.append(
        PlayerLogEntry(id=1, kind="player", text="주변을 살핍니다")
    )

    result = next_turn_suggestions(runtime, [])

    assert "북쪽 길목의 표지판을 살핍니다" in [
        suggestion.input_text for suggestion in result
    ]


def test_build_intro_suggestions_uses_visible_graph_state():
    runtime = _runtime_for_suggestions()

    result = build_intro_suggestions(runtime)

    assert [suggestion.model_dump() for suggestion in result] == [
        {
            "label": "talk",
            "input_text": "상인에게 말을 겁니다",
            "intent": "talk",
            "action": None,
        },
        {
            "label": "move",
            "input_text": "숲으로 이동합니다",
            "intent": "move",
            "action": None,
        },
        {
            "label": "inspect",
            "input_text": "주변을 살핍니다",
            "intent": "inspect",
            "action": None,
        },
    ]


def test_build_intro_suggestions_hides_locked_exits():
    runtime = _runtime_for_suggestions()
    runtime.graph.edges["connects_to:town:forest"].properties["requires_quest"] = "quest_01"

    result = build_intro_suggestions(runtime)

    assert [suggestion.input_text for suggestion in result] == [
        "상인에게 말을 겁니다",
        "주변을 살핍니다",
    ]


def test_build_intro_suggestions_includes_visible_generated_clue():
    runtime = _runtime_for_suggestions()
    runtime.graph.edges.pop("connects_to:town:forest")
    runtime.graph.nodes["clue_signpost"] = GraphNode(
        id="clue_signpost",
        type="knowledge",
        properties={
            "kind": "clue",
            "title": "북쪽 길목의 표지판",
            "summary": "북쪽을 가리킵니다.",
            "visibility": "player",
        },
    )

    result = build_intro_suggestions(runtime)

    assert [suggestion.model_dump() for suggestion in result] == [
        {
            "label": "talk",
            "input_text": "상인에게 말을 겁니다",
            "intent": "talk",
            "action": None,
        },
        {
            "label": "북쪽 길목의 표지판",
            "input_text": "북쪽 길목의 표지판을 살핍니다",
            "intent": "inspect",
            "action": None,
        },
        {
            "label": "inspect",
            "input_text": "주변을 살핍니다",
            "intent": "inspect",
            "action": None,
        },
    ]


def test_build_intro_suggestions_uses_object_particle_for_vowel_ending_clue():
    runtime = _runtime_for_suggestions()
    runtime.graph.edges.pop("connects_to:town:forest")
    runtime.graph.nodes["clue_fog"] = GraphNode(
        id="clue_fog",
        type="knowledge",
        properties={
            "kind": "clue",
            "title": "짙은 안개",
            "summary": "시야를 방해합니다.",
            "visibility": "player",
        },
    )

    result = build_intro_suggestions(runtime)

    assert "짙은 안개를 살핍니다" in [
        suggestion.input_text for suggestion in result
    ]


def test_filter_grounded_suggestions_drops_locked_move_targets():
    runtime = _runtime_for_suggestions()
    runtime.graph.edges["connects_to:town:forest"].properties["requires_quest"] = "quest_01"

    result = filter_grounded_suggestions(
        runtime,
        [GraphSuggestion(label="숲으로", input_text="숲으로 이동합니다", intent="move")],
    )

    assert result == []


def test_filter_grounded_suggestions_drops_combat_when_not_in_combat():
    runtime = _runtime_for_suggestions()

    result = filter_grounded_suggestions(
        runtime,
        [
            GraphSuggestion(label="공격", input_text="고블린을 공격합니다", intent="combat"),
            GraphSuggestion(label="확인", input_text="주변을 살핍니다", intent="inspect"),
            GraphSuggestion(label="용 확인", input_text="용을 살핍니다", intent="inspect"),
        ],
    )

    assert [suggestion.input_text for suggestion in result] == ["주변을 살핍니다"]


def test_filter_grounded_suggestions_drops_missing_intent():
    runtime = _runtime_for_suggestions()

    result = filter_grounded_suggestions(
        runtime,
        [
            GraphSuggestion(label="대답 기다리기", input_text="상인의 대답을 기다립니다"),
            GraphSuggestion(label="상인에게", input_text="상인에게 말을 겁니다", intent="talk"),
        ],
    )

    assert [suggestion.input_text for suggestion in result] == ["상인에게 말을 겁니다"]


def test_filter_grounded_suggestions_keeps_inspect_for_visible_scene_refs():
    runtime = _runtime_for_suggestions()

    result = filter_grounded_suggestions(
        runtime,
        [
            GraphSuggestion(label="마을 살피기", input_text="마을을 살핍니다", intent="inspect"),
            GraphSuggestion(label="상인 살피기", input_text="상인을 살핍니다", intent="inspect"),
            GraphSuggestion(label="숲 살피기", input_text="숲을 살핍니다", intent="inspect"),
            GraphSuggestion(label="약초 살피기", input_text="회복 약초를 살핍니다", intent="inspect"),
            GraphSuggestion(label="용 살피기", input_text="마을의 용을 살핍니다", intent="inspect"),
            GraphSuggestion(label="마을", input_text="용을 살핍니다", intent="inspect"),
        ],
    )

    assert [suggestion.input_text for suggestion in result] == [
        "마을을 살핍니다",
        "상인을 살핍니다",
        "숲을 살핍니다",
    ]


def test_filter_grounded_suggestions_keeps_inspect_for_visible_generated_clue():
    runtime = _runtime_for_suggestions()
    runtime.graph.nodes["clue_signpost"] = GraphNode(
        id="clue_signpost",
        type="knowledge",
        properties={
            "kind": "clue",
            "title": "북쪽 길목의 표지판",
            "summary": "북쪽을 가리킵니다.",
            "visibility": "player",
        },
    )

    result = filter_grounded_suggestions(
        runtime,
        [
            GraphSuggestion(
                label="표지판 확인",
                input_text="북쪽 길목의 표지판을 살핍니다",
                intent="inspect",
            ),
            GraphSuggestion(
                label="숨겨진 단서",
                input_text="숨겨진 단서를 살핍니다",
                intent="inspect",
            ),
        ],
    )

    assert [suggestion.input_text for suggestion in result] == [
        "북쪽 길목의 표지판을 살핍니다"
    ]


def test_scene_clue_suggestion_stays_at_current_anchor():
    runtime = _runtime_for_suggestions()
    runtime.graph.nodes["harbor"] = GraphNode(
        id="harbor",
        type="location",
        properties={"name": "안개 항구"},
    )
    runtime.graph.nodes["clue_fog"] = GraphNode(
        id="clue_fog",
        type="knowledge",
        properties={
            "kind": "clue",
            "title": "짙은 안개",
            "summary": "항구 주변에만 짙게 깔려 있습니다.",
            "visibility": "player",
            "stability": "scene",
            "anchor_id": "harbor",
        },
    )

    result = next_turn_suggestions(runtime, [])

    assert "짙은 안개를 살핍니다" not in [
        suggestion.input_text for suggestion in result
    ]


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


def test_parse_graph_narration_answer_keeps_all_valid_ui_cues_without_limit():
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
                  "kind": "warning",
                  "label": "긴 경고 라벨",
                  "text": "문장 중간에서 잘리면 안 되는 긴 표시 정보입니다.",
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
            "text": "경비병이 문 앞에서 멈춤",
            "scope": "delta",
        },
        {
            "kind": "warning",
            "label": "긴 경고 라벨",
            "text": "문장 중간에서 잘리면 안 되는 긴 표시 정보입니다.",
            "scope": "temporary",
        },
    ]


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


def test_parse_graph_narration_answer_drops_string_suggestions():
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

    assert len(result.suggestions) == 1
    assert result.suggestions[0].model_dump() == {
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


def test_parse_graph_narration_answer_drops_targetless_generic_suggestions():
    answer = "\n".join(
        [
            "흰 머리 여인이 아직 말을 아낍니다.",
            "---TRPG_META---",
            """
            {
              "suggestions": [
                {"label": "대화 시작하기", "input_text": "대화 시작하기"},
                {"label": "상황 파악하기", "input_text": "상황 파악하기"},
                {"label": "흰 머리 여인에게 묻기", "input_text": "흰 머리 여인에게 섬의 규칙을 묻습니다"}
              ]
            }
            """,
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert [suggestion.input_text for suggestion in result.suggestions] == [
        "흰 머리 여인에게 섬의 규칙을 묻습니다"
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


def test_parse_graph_narration_answer_normalizes_ascii_direct_speech():
    answer = "\n".join(
        [
            r'루카가 기침합니다. \"크흠.\" 그는 모자를 고쳐 씁니다. \"도와주시겠습니까?\"',
            "---TRPG_META---",
            '{"suggestions": []}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.narration == (
        "루카가 기침합니다. 「크흠.」 그는 모자를 고쳐 씁니다. 「도와주시겠습니까?」"
    )


def test_parse_graph_narration_answer_removes_runtime_status_text():
    answer = "\n".join(
        [
            "당신의 행동이 처리됩니다.",
            "방 안에 다시 숨이 돕니다. 「당신의 행동이 처리됩니다.」라는 짧은 확인과 함께, "
            "당신의 선택(열기)이 자리를 잡습니다. 공기가 감돌며، 빛이 흔들립니다.",
            "---TRPG_META---",
            '{"suggestions": []}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.narration == (
        "방 안에 다시 숨이 돕니다. 당신의 선택이 자리를 잡습니다. "
        "공기가 감돌며, 빛이 흔들립니다."
    )


def test_parse_graph_narration_answer_normalizes_player_honorific():
    answer = "\n".join(
        [
            "플레이어님이 먼저 말을 걸자, 상대가 대답합니다.",
            "---TRPG_META---",
            '{"suggestions": []}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.narration == "당신이 먼저 말을 걸자, 상대가 대답합니다."


def test_parse_graph_narration_answer_closes_unmatched_ascii_direct_speech():
    answer = "\n".join(
        [
            '"아이고! 드디어 오셨네요! 뭘 도와드릴까요?',
            "",
            "당신에게 시선을 고정시킨 채 미소를 짓습니다.",
            "---TRPG_META---",
            '{"suggestions": []}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.narration == (
        "「아이고! 드디어 오셨네요! 뭘 도와드릴까요?」\n"
        "당신에게 시선을 고정시킨 채 미소를 짓습니다."
    )


def test_parse_graph_narration_answer_uses_env_marker(monkeypatch):
    monkeypatch.setenv("GRAPH_NARRATION_META_MARKER", "---META---")
    answer = "\n".join(
        [
            "상대가 고개를 끄덕입니다.",
            "---META---",
            '{"suggestions": [{"label": "다시 묻기", "input_text": "다시 묻습니다"}]}',
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert result.suggestions[0].input_text == "다시 묻습니다"


def test_parse_graph_narration_answer_keeps_all_valid_suggestions_without_truncation():
    answer = "\n".join(
        [
            "상대가 길을 가리킵니다.",
            "---TRPG_META---",
            '{"suggestions": ['
            '{"label": "북문", "input_text": "북문으로 이동합니다"}, '
            '{"label": "광장", "input_text": "광장으로 돌아갑니다"}'
            "]}",
        ]
    )

    result = parse_graph_narration_answer(answer)

    assert [suggestion.input_text for suggestion in result.suggestions] == [
        "북문으로 이동합니다",
        "광장으로 돌아갑니다",
    ]


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
