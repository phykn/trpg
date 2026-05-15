from unittest.mock import patch

from src.game.runtime.narration.result import parse_graph_narration_answer


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
