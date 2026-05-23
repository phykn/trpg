from src.game.runtime.narration.brief import build_narration_brief


def test_narration_brief_includes_recent_log_context():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "레아에게 빈방을 다시 열자고 말합니다"},
            "engine_event": {
                "kind": "roll",
                "outcome": "failure",
                "resolved_results": ["매력 판정 실패"],
            },
            "scene_state": {
                "scene_anchor": {"location": {"name": "푸른 비 거리"}},
                "target_view": {"name": "레아"},
            },
            "reference_context": {
                "recent_narration": [
                    {"text": "레아는 닫힌 방문 앞에서 열쇠를 쥐고 있습니다."},
                    {"text": "비가 문패 위로 가늘게 흘러내립니다."},
                ],
                "recent_dialogue": [
                    {
                        "player": "그 방은 누구의 자리였나요?",
                        "narrator": "레아는 방 안쪽을 보지 않고 대답합니다.",
                    }
                ],
            },
        }
    )

    assert brief.startswith("최근 로그:")
    assert "- 레아는 닫힌 방문 앞에서 열쇠를 쥐고 있습니다." in brief
    assert "- 비가 문패 위로 가늘게 흘러내립니다." in brief
    assert "- 플레이어: 그 방은 누구의 자리였나요?" in brief
    assert "- GM: 레아는 방 안쪽을 보지 않고 대답합니다." in brief
    assert brief.rfind("플레이어 입력:") > brief.find("최근 로그:")


def test_narration_brief_shows_player_visible_screen_log():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "레아를 설득합니다"},
            "engine_event": {
                "kind": "roll",
                "outcome": "success",
                "resolved_results": ["레아가 한 걸음 물러섭니다."],
            },
            "scene_state": {
                "scene_anchor": {"location": {"name": "푸른 비 거리"}},
                "target_view": {"name": "레아"},
            },
            "reference_context": {
                "screen_log": [
                    {"id": 1, "kind": "act", "text": "당신은 푸른 비 거리에 있습니다."},
                    {"id": 2, "kind": "player", "text": "레아에게 방 열쇠를 묻습니다."},
                    {
                        "id": 3,
                        "kind": "roll",
                        "check": "매력",
                        "roll": 15,
                        "margin": 2,
                        "result": "success",
                        "bonus_breakdown": [
                            {"label": "d20", "value": 15},
                            {"label": "매력", "value": 3},
                        ],
                    },
                    {
                        "id": 4,
                        "kind": "gm",
                        "text": "레아는 열쇠를 손바닥 안에서 굴립니다.",
                        "outcome": "neutral",
                    },
                ],
            },
        }
    )

    assert brief.startswith("화면 로그:")
    assert "- 행동: 당신은 푸른 비 거리에 있습니다." in brief
    assert "- 플레이어: 레아에게 방 열쇠를 묻습니다." in brief
    assert "- 판정: 성공 매력 d20 15 (+3) +2 초과" in brief
    assert "- GM: 레아는 열쇠를 손바닥 안에서 굴립니다." in brief
    assert brief.rfind("플레이어 입력:") > brief.find("화면 로그:")


def test_roll_brief_includes_target_public_knowledge_as_scene_facts():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "레아에게 방을 열어야 하는 이유를 묻습니다"},
            "engine_event": {
                "kind": "roll",
                "outcome": "success",
                "resolved_results": ["매력 판정 성공"],
            },
            "scene_state": {
                "scene_anchor": {"location": {"name": "푸른 비 거리"}},
                "target_view": {
                    "name": "레아",
                    "public_knowledge": [
                        {
                            "title": "비워 둔 방",
                            "summary": "레아의 빈방은 애도의 장소이지만, 방 밖에는 지금 머물 곳이 필요한 사람이 있습니다.",
                        }
                    ],
                },
            },
        }
    )

    assert "대상 정보:" in brief
    assert "- 비워 둔 방: 레아의 빈방은 애도의 장소이지만, 방 밖에는 지금 머물 곳이 필요한 사람이 있습니다." in brief
    assert brief.rfind("플레이어 입력:") > brief.find("대상 정보:")


def test_roll_brief_uses_revealed_facts_before_target_public_knowledge():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "장부의 빈 줄을 확인합니다"},
            "engine_event": {
                "kind": "roll",
                "outcome": "success",
                "revealed_facts": [
                    {
                        "title": "잠긴 장부",
                        "summary": "장부의 빈 줄은 교대자가 일부러 지운 흔적입니다.",
                    }
                ],
                "resolved_results": ["지력 판정 성공"],
            },
            "scene_state": {
                "scene_anchor": {"location": {"name": "광장"}},
                "target_view": {
                    "name": "경비병",
                    "public_knowledge": [
                        {
                            "title": "북문 단서",
                            "summary": "북문 교대 기록이 비어 있습니다.",
                        }
                    ],
                },
            },
        }
    )

    assert "공개된 사실:" in brief
    assert "- 잠긴 장부: 장부의 빈 줄은 교대자가 일부러 지운 흔적입니다." in brief
    assert "북문 교대 기록이 비어 있습니다." not in brief


def test_failed_roll_brief_omits_target_public_knowledge():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "레아의 표정을 살핍니다"},
            "engine_event": {
                "kind": "roll",
                "outcome": "failure",
                "resolved_results": ["지력 판정 실패"],
            },
            "scene_state": {
                "scene_anchor": {"location": {"name": "푸른 비 거리"}},
                "target_view": {
                    "name": "레아",
                    "public_knowledge": [
                        {
                            "title": "비워 둔 방",
                            "summary": "방 밖에는 지금 머물 곳이 필요한 사람이 있습니다.",
                        }
                    ],
                },
            },
        }
    )

    assert "대상 정보:" not in brief
    assert "방 밖에는 지금 머물 곳이 필요한 사람이 있습니다." not in brief


def test_dialogue_brief_includes_target_public_knowledge_before_player_input():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "항구장에게 출항 규칙을 묻습니다"},
            "engine_event": {"kind": "dialogue"},
            "scene_state": {
                "scene_anchor": {"location": {"name": "안개 항구"}},
                "target_view": {
                    "name": "항구장",
                    "public_knowledge": [
                        {
                            "title": "안개 바다의 규칙",
                            "summary": "안개 바다는 키를 잡는 사람과 물살을 확인하는 사람이 함께 필요합니다.",
                        }
                    ],
                },
            },
        }
    )

    assert "대상 정보:" in brief
    assert "- 안개 바다의 규칙: 안개 바다는 키를 잡는 사람과 물살을 확인하는 사람이 함께 필요합니다." in brief
    assert brief.rfind("플레이어 입력:") > brief.find("대상 정보:")


def test_narration_brief_respects_screen_log_env_limits(monkeypatch):
    monkeypatch.setenv("GRAPH_NARRATION_SCREEN_LOG_ENTRIES", "1")
    monkeypatch.setenv("GRAPH_NARRATION_BRIEF_LINE_CHARS", "12")

    brief = build_narration_brief(
        {
            "engine_event": {"kind": "dialogue"},
            "scene_state": {"scene_anchor": {"location": {"name": "거리"}}},
            "reference_context": {
                "screen_log": [
                    {"kind": "player", "text": "첫번째 말은 잘려야 합니다."},
                    {"kind": "gm", "text": "두번째 긴 나레이션만 남습니다."},
                ],
            },
        }
    )

    assert "첫번째 말" not in brief
    assert "- GM: 두번째 긴 나레이션만…" in brief


def test_narration_brief_respects_recent_context_env_limit(monkeypatch):
    monkeypatch.setenv("GRAPH_NARRATION_BRIEF_RECENT_ENTRIES", "1")

    brief = build_narration_brief(
        {
            "engine_event": {"kind": "dialogue"},
            "scene_state": {"scene_anchor": {"location": {"name": "거리"}}},
            "reference_context": {
                "recent_narration": [
                    {"text": "첫번째 최근 로그"},
                    {"text": "두번째 최근 로그"},
                ],
                "recent_dialogue": [
                    {"player": "첫번째 질문", "narrator": "첫번째 답"},
                    {"player": "두번째 질문", "narrator": "두번째 답"},
                ],
            },
        }
    )

    assert "첫번째 최근 로그" not in brief
    assert "첫번째 질문" not in brief
    assert "- 두번째 최근 로그" in brief
    assert "- 플레이어: 두번째 질문" in brief
