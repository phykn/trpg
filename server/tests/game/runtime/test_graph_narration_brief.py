from src.game.runtime.narration.brief import build_narration_brief


def test_narration_brief_includes_ordered_recent_context():
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
                "previous_scene": [
                    {"summary": "레아는 닫힌 방문 앞에서 열쇠를 쥐고 있습니다."},
                    {"summary": "비가 문패 위로 가늘게 흘러내립니다."},
                ],
                "recent_exchanges": [
                    {
                        "player": "그 방은 누구의 자리였나요?",
                        "narrator": "레아는 방 안쪽을 보지 않고 대답합니다.",
                    }
                ],
            },
        }
    )

    assert brief.startswith("이전 장면 요약:")
    assert "- 레아는 닫힌 방문 앞에서 열쇠를 쥐고 있습니다." in brief
    assert "- 비가 문패 위로 가늘게 흘러내립니다." in brief
    assert "- 플레이어: 그 방은 누구의 자리였나요?" in brief
    assert "- GM: 레아는 방 안쪽을 보지 않고 대답합니다." in brief
    assert brief.find("최근 대화:") > brief.find("이전 장면 요약:")
    assert brief.rfind("플레이어 입력:") > brief.find("최근 대화:")
    assert brief.splitlines()[-1] == "플레이어 입력: 레아에게 빈방을 다시 열자고 말합니다"


def test_narration_brief_includes_world_guidance_first():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "레아에게 말을 겁니다"},
            "engine_event": {"kind": "dialogue"},
            "scene_state": {"scene_anchor": {"location": {"name": "푸른 비 거리"}}},
            "reference_context": {
                "world_guidance": "비밀을 단정하지 말고 관찰 가능한 반응으로 씁니다.",
                "recent_exchanges": [
                    {
                        "player": "방 안을 봅니다.",
                        "narrator": "문틈은 어둡습니다.",
                    }
                ],
            },
        }
    )

    assert brief.startswith("세계 가이드:")
    assert "- 비밀을 단정하지 말고 관찰 가능한 반응으로 씁니다." in brief
    assert brief.find("최근 대화:") > brief.find("세계 가이드:")


def test_narration_brief_orders_global_story_before_recent_dialogue():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "레아에게 말을 겁니다"},
            "engine_event": {"kind": "dialogue"},
            "scene_state": {"scene_anchor": {"location": {"name": "푸른 비 거리"}}},
            "reference_context": {
                "world_guidance": "비밀을 단정하지 말고 관찰 가능한 반응으로 씁니다.",
                "current_story": {
                    "chapter": {
                        "name": "푸른섬",
                        "description": "애도와 산 사람의 자리 사이에서 빈방의 의미를 판단합니다.",
                    },
                    "active_quest": {
                        "name": "빈방 사건",
                        "description": "레아의 빈방을 계속 닫아 둘지 정합니다.",
                    },
                },
                "previous_scene": [
                    {"summary": "레아는 닫힌 방문 앞에서 열쇠를 쥐고 있습니다."},
                ],
                "recent_exchanges": [
                    {
                        "player": "그 방은 누구의 자리였나요?",
                        "narrator": "레아는 방 안쪽을 보지 않고 대답합니다.",
                    }
                ],
            },
        }
    )

    assert "현재 이야기:" in brief
    assert "- 챕터: 푸른섬 - 애도와 산 사람의 자리 사이에서 빈방의 의미를 판단합니다." in brief
    assert "- 진행 중 퀘스트: 빈방 사건 - 레아의 빈방을 계속 닫아 둘지 정합니다." in brief
    assert brief.find("세계 가이드:") < brief.find("현재 이야기:")
    assert brief.find("현재 이야기:") < brief.find("이전 장면 요약:")
    assert brief.find("이전 장면 요약:") < brief.find("최근 대화:")
    assert brief.find("최근 대화:") < brief.find("장면 유형:")
    assert brief.splitlines()[-1] == "플레이어 입력: 레아에게 말을 겁니다"


def test_move_brief_omits_previous_dialogue_context():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "안개 항구 선착장으로 이동합니다."},
            "engine_event": {
                "kind": "move",
                "resolved_results": ["안개 항구 선착장으로 이동"],
            },
            "scene_state": {
                "current_place": {
                    "name": "안개 항구 선착장",
                    "description": "밧줄에 묶인 배와 짧은 노 두 개가 보입니다.",
                    "traits": ["엘리와 묶인 배만 기다립니다."],
                },
                "scene_anchor": {"location": {"name": "안개 항구 선착장"}},
            },
            "reference_context": {
                "previous_scene": [
                    {"summary": "올든은 출항 규칙을 설명했습니다."},
                ],
                "recent_exchanges": [
                    {
                        "player": "올든에게 묻습니다.",
                        "narrator": "올든은 노를 잡습니다.",
                    }
                ],
            },
        }
    )

    assert "이전 장면 요약:" not in brief
    assert "최근 대화:" not in brief
    assert "올든" not in brief
    assert "장면 유형: move" in brief
    assert "장소: 안개 항구 선착장" in brief
    assert "현재 장소:" in brief
    assert "밧줄에 묶인 배와 짧은 노 두 개가 보입니다." in brief
    assert "엘리와 묶인 배만 기다립니다." in brief
    assert "직전 대화 요약" in brief
    assert brief.splitlines()[-1] == "플레이어 입력: 안개 항구 선착장으로 이동합니다."


def test_narration_brief_includes_visible_cues_on_recent_exchanges():
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
                "recent_exchanges": [
                    {
                        "player": "레아에게 방 열쇠를 묻습니다.",
                        "narrator": "레아는 열쇠를 손바닥 안에서 굴립니다.",
                        "cues": [
                            {
                                "kind": "opportunity",
                                "label": "기회",
                                "text": "열쇠 이야기를 이어갈 수 있음",
                            }
                        ],
                    },
                ],
            },
        }
    )

    assert "- 플레이어: 레아에게 방 열쇠를 묻습니다." in brief
    assert "- GM: 레아는 열쇠를 손바닥 안에서 굴립니다." in brief
    assert "열쇠 이야기를 이어갈 수 있음" in brief
    assert brief.rfind("플레이어 입력:") > brief.find("최근 대화:")
    assert brief.splitlines()[-1] == "플레이어 입력: 레아를 설득합니다"


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
    assert brief.splitlines()[-1] == "플레이어 입력: 레아에게 방을 열어야 하는 이유를 묻습니다"


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
    assert "응답 대상: 항구장. 직접 답하거나 답을 피합니다. 플레이어 질문으로 끝내지 않습니다." in brief
    assert "목표: 대상이 플레이어 질문에 직접 답합니다." in brief
    assert "- 안개 바다의 규칙: 안개 바다는 키를 잡는 사람과 물살을 확인하는 사람이 함께 필요합니다." in brief
    assert brief.rfind("플레이어 입력:") > brief.find("대상 정보:")
    assert brief.splitlines()[-1] == "플레이어 입력: 항구장에게 출항 규칙을 묻습니다"


def test_action_brief_includes_responder_for_dialogue_like_input():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "루카에게 영수증을 보여 달라고 말합니다"},
            "engine_event": {"kind": "action"},
            "scene_state": {
                "scene_anchor": {"location": {"name": "붉은섬 광장"}},
                "target_view": {"name": "루카"},
            },
        }
    )

    assert "응답 대상: 루카. 직접 답하거나 답을 피합니다. 플레이어 질문으로 끝내지 않습니다." in brief
    assert "목표: 대상이 플레이어 질문에 직접 답합니다." in brief


def test_narration_brief_includes_all_payload_recent_context():
    brief = build_narration_brief(
        {
            "engine_event": {"kind": "dialogue"},
            "scene_state": {"scene_anchor": {"location": {"name": "거리"}}},
            "reference_context": {
                "previous_scene": [
                    {"summary": "첫번째 장면 요약"},
                    {"summary": "두번째 장면 요약"},
                    {"summary": "세번째 장면 요약"},
                ],
                "recent_exchanges": [
                    {"player": "첫번째 질문", "narrator": "첫번째 답"},
                    {"player": "두번째 질문", "narrator": "두번째 답"},
                    {"player": "세번째 질문", "narrator": "세번째 답"},
                ],
            },
        }
    )

    assert "- 첫번째 장면 요약" in brief
    assert "- 플레이어: 첫번째 질문" in brief
    assert "- 두번째 장면 요약" in brief
    assert "- 플레이어: 두번째 질문" in brief
    assert "- 세번째 장면 요약" in brief
    assert "- 플레이어: 세번째 질문" in brief


def test_narration_brief_does_not_clip_payload_lines():
    long_summary = "가" * 140

    brief = build_narration_brief(
        {
            "engine_event": {"kind": "dialogue"},
            "scene_state": {"scene_anchor": {"location": {"name": "거리"}}},
            "reference_context": {
                "previous_scene": [{"summary": long_summary}],
            },
        }
    )

    assert long_summary in brief


def test_combat_brief_orders_scene_place_target_before_action_result():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "허수아비를 공격합니다"},
            "engine_event": {
                "kind": "combat",
                "outcome": "ongoing",
                "action": {"verb": "attack"},
                "resolved_results": ["공격이 닿습니다."],
            },
            "scene_state": {
                "current_place": {"name": "훈련장"},
                "target_view": {"name": "허수아비"},
            },
            "combat_view": {
                "player_action": "공격",
                "exchange_result_label": "성공",
                "outcome": "ongoing",
            },
            "reference_context": {
                "current_story": {
                    "chapter": {"name": "개발용 원턴 테스트"},
                    "active_quest": {"name": "훈련 확인"},
                },
                "recent_exchanges": [
                    {"player": "자세를 낮춥니다.", "narrator": "허수아비가 흔들립니다."}
                ],
            },
        }
    )

    assert brief.find("현재 이야기:") < brief.find("최근 대화:")
    assert brief.find("최근 대화:") < brief.find("장면 유형: 전투")
    assert brief.find("장소: 훈련장") < brief.find("대상: 허수아비")
    assert brief.find("대상: 허수아비") < brief.find("행동: 공격")
    assert brief.find("행동: 공격") < brief.find("결과: 성공")
    assert brief.splitlines()[-1] == "플레이어 입력: 허수아비를 공격합니다"
