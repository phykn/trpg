from unittest.mock import patch

from src.game.runtime.narration.result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    gm_log_entry_from_narration,
    parse_graph_narration_answer,
)


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
