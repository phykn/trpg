from src.game.runtime.narration_result import parse_graph_narration_answer


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


def test_parse_graph_narration_answer_keeps_legacy_string_suggestions():
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

    assert result.suggestions[0] == "상인에게 다시 묻습니다"
    assert result.suggestions[1].model_dump() == {
        "label": "대답 기다리기",
        "input_text": "상인의 대답을 기다립니다",
        "intent": None,
        "action": None,
    }
