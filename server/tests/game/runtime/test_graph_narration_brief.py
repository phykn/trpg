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


def test_narration_brief_includes_subject_memories_and_discoveries():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "레아에게 밧줄을 묻습니다"},
            "engine_event": {"kind": "dialogue"},
            "scene_state": {
                "scene_anchor": {"location": {"name": "푸른 비 거리"}},
                "target_view": {"name": "레아"},
            },
            "reference_context": {
                "subject_memories": [
                    {
                        "content": "레아는 당신이 빈방 열쇠를 돌려준 일을 기억합니다.",
                    }
                ],
                "discoveries": {
                    "clues": [
                        {
                            "title": "젖은 밧줄",
                            "summary": "밧줄은 아직 물기를 머금고 있습니다.",
                        }
                    ],
                    "memories": [
                        {
                            "title": "찢어진 표",
                            "summary": "당신은 표 반쪽을 남겼습니다.",
                        }
                    ],
                },
            },
        }
    )

    assert "대상 기억:" in brief
    assert "- 레아는 당신이 빈방 열쇠를 돌려준 일을 기억합니다." in brief
    assert "저장된 단서와 기억:" in brief
    assert "- 젖은 밧줄: 밧줄은 아직 물기를 머금고 있습니다." in brief
    assert "- 찢어진 표: 당신은 표 반쪽을 남겼습니다." in brief
    assert brief.find("대상 기억:") < brief.find("저장된 단서와 기억:")
    assert brief.find("저장된 단서와 기억:") < brief.find("장면 유형:")


def test_combat_brief_includes_subject_memories_and_discoveries():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "허수아비를 공격합니다"},
            "engine_event": {"kind": "combat", "action": {"verb": "attack"}},
            "scene_state": {
                "scene_anchor": {"location": {"name": "훈련장"}},
                "target_view": {"name": "훈련용 허수아비"},
            },
            "combat_view": {
                "exchange_result": "success",
                "events": [
                    {"target": {"name": "훈련용 허수아비"}, "result_label": "성공"}
                ],
            },
            "reference_context": {
                "subject_memories": [
                    {"content": "허수아비의 왼쪽 받침대가 느슨합니다."}
                ],
                "discoveries": {
                    "clues": [
                        {
                            "title": "금 간 받침대",
                            "summary": "왼쪽 받침대가 흔들립니다.",
                        }
                    ]
                },
            },
        }
    )

    assert "대상 기억:" in brief
    assert "허수아비의 왼쪽 받침대가 느슨합니다." in brief
    assert "저장된 단서와 기억:" in brief
    assert "금 간 받침대: 왼쪽 받침대가 흔들립니다." in brief
    assert "장면 유형: 전투" in brief


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


def test_narration_brief_includes_chapter_guidance():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "루카에게 영수증을 보여 달라고 묻습니다"},
            "engine_event": {"kind": "dialogue"},
            "scene_state": {"scene_anchor": {"location": {"name": "붉은섬 광장"}}},
            "reference_context": {
                "current_story": {
                    "chapter": {
                        "name": "붉은섬",
                        "description": "분노 거래와 환불 요구를 다룹니다.",
                        "guidance": [
                            "루카의 붉은 영수증은 처음부터 끝까지 루카의 젖은 손끝에 접힌 채 보인다.",
                            "보여 달라는 말을 들으면 루카가 손에 든 영수증을 들어 보인다.",
                        ],
                    },
                },
            },
        }
    )

    assert "- 챕터 운영: 루카의 붉은 영수증은 처음부터 끝까지 루카의 젖은 손끝에 접힌 채 보인다." in brief
    assert "- 챕터 운영: 보여 달라는 말을 들으면 루카가 손에 든 영수증을 들어 보인다." in brief


def test_story_transition_brief_omits_recent_context():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "출항 허가 받기"},
            "engine_event": {
                "kind": "action",
                "story_transition": {
                    "completed_quests": [{"id": "q_green", "name": "출항 허가서"}],
                    "choice_result": {
                        "choice": {"id": "extend", "label": "체류권 남기기"},
                        "gained_items": [{"id": "itm_green_permit", "name": "연두 체류권"}],
                    },
                    "next_quest": {"id": "q_purple", "name": "사랑 증명 비용 사건"},
                    "handoff": "보라섬 선착장 너머 예식장 견적서가 바람에 흔들립니다.",
                },
            },
            "scene_state": {"scene_anchor": {"location": {"name": "출항 허가소"}}},
            "reference_context": {
                "previous_scene": [{"summary": "루카의 붉은 영수증이 비어 있습니다."}],
                "recent_exchanges": [
                    {
                        "player": "영수증을 확인합니다.",
                        "narrator": "엘리가 붉은 영수증을 봅니다.",
                    }
                ],
            },
        }
    )

    assert "장면 유형: 사건 전환" in brief
    assert "선택 결과: 선택: 체류권 남기기 / 획득: 연두 체류권" in brief
    assert "전환 단서: 보라섬 선착장 너머 예식장 견적서가 바람에 흔들립니다." in brief
    assert "이전 장면 요약:" not in brief
    assert "최근 대화:" not in brief
    assert "붉은 영수증" not in brief


def test_move_brief_omits_previous_dialogue_context():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "서쪽 문 앞으로 이동합니다."},
            "engine_event": {
                "kind": "move",
                "resolved_results": ["서쪽 문 앞으로 이동"],
            },
            "scene_state": {
                "current_place": {
                    "name": "서쪽 문 앞",
                    "description": "닫힌 문과 낡은 표식이 보입니다.",
                    "traits": ["문지기와 닫힌 문만 기다립니다."],
                },
                "scene_anchor": {"location": {"name": "서쪽 문 앞"}},
            },
            "reference_context": {
                "previous_scene": [
                    {"summary": "안내인은 출입 규칙을 설명했습니다."},
                ],
                "recent_exchanges": [
                    {
                        "player": "안내인에게 묻습니다.",
                        "narrator": "안내인은 열쇠를 확인합니다.",
                    }
                ],
            },
        }
    )

    assert "이전 장면 요약:" not in brief
    assert "최근 대화:" not in brief
    assert "안내인" not in brief
    assert "장면 유형: move" in brief
    assert "장소: 서쪽 문 앞" in brief
    assert "현재 장소:" in brief
    assert "닫힌 문과 낡은 표식이 보입니다." in brief
    assert "문지기와 닫힌 문만 기다립니다." in brief
    assert "직전 대화 요약" not in brief
    assert "금지:" not in brief
    assert "목표:" not in brief
    assert brief.splitlines()[-1] == "플레이어 입력: 서쪽 문 앞으로 이동합니다."


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
            "user_request": {"player_input": "관리인에게 출입 규칙을 묻습니다"},
            "engine_event": {"kind": "dialogue"},
            "scene_state": {
                "scene_anchor": {"location": {"name": "기록실 입구"}},
                "target_view": {
                    "name": "관리인",
                    "public_knowledge": [
                        {
                            "title": "기록실 출입 규칙",
                            "summary": "기록실은 담당자 확인과 방문 목적이 함께 필요합니다.",
                        }
                    ],
                },
            },
        }
    )

    assert "대상 정보:" in brief
    assert "응답 대상: 관리인" in brief
    assert "질문을 반복하지 말고" not in brief
    assert "목표:" not in brief
    assert "질문 문장을 NPC 대사로 복사하지 않습니다." not in brief
    assert "- 기록실 출입 규칙: 기록실은 담당자 확인과 방문 목적이 함께 필요합니다." in brief
    assert brief.rfind("플레이어 입력:") > brief.find("대상 정보:")
    assert brief.splitlines()[-1] == "플레이어 입력: 관리인에게 출입 규칙을 묻습니다"


def test_dialogue_brief_prioritizes_answer_over_decorative_gestures():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "관리인에게 여기가 어디인지 묻습니다"},
            "engine_event": {"kind": "dialogue"},
            "scene_state": {
                "scene_anchor": {"location": {"name": "기록실 입구"}},
                "target_view": {"name": "관리인"},
            },
        }
    )

    assert "입술, 시선, 미소 같은 장식보다 답변 내용을 먼저 씁니다." not in brief
    assert "응답 대상: 관리인" in brief
    assert "직접 발화로 답변 필요" in brief


def test_dialogue_brief_requires_possibility_question_condition():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "관리인에게 나갈 수 있는지 묻습니다"},
            "engine_event": {"kind": "dialogue"},
            "scene_state": {
                "scene_anchor": {"location": {"name": "기록실 입구"}},
                "target_view": {
                    "name": "관리인",
                    "public_knowledge": [
                        {
                            "title": "출입 조건",
                            "summary": "담당자 확인을 받아야 문을 열 수 있습니다.",
                        }
                    ],
                },
            },
        }
    )

    assert "가능 여부를 물으면 가능/불가능과 조건을 함께 말합니다." not in brief
    assert "출입 조건: 담당자 확인을 받아야 문을 열 수 있습니다." in brief


def test_dialogue_brief_includes_current_place_details_and_future_place_forbid():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "문지기에게 여기가 어디인지 묻습니다"},
            "engine_event": {"kind": "dialogue"},
            "scene_state": {
                "current_place": {
                    "name": "서쪽 문 앞",
                    "description": "문지기가 닫힌 문 앞을 지키는 복도",
                    "traits": ["문 너머 기록실 불빛이 새어 나온다"],
                },
                "scene_anchor": {"location": {"name": "서쪽 문 앞"}},
                "target_view": {"name": "문지기"},
            },
        }
    )

    assert "장소: 서쪽 문 앞" in brief
    assert "현재 장소:" in brief
    assert "문지기가 닫힌 문 앞을 지키는 복도" in brief
    assert "문 너머 기록실 불빛이 새어 나온다" in brief
    assert "금지:" not in brief
    assert brief.splitlines()[-1] == "플레이어 입력: 문지기에게 여기가 어디인지 묻습니다"


def test_action_brief_includes_responder_for_dialogue_like_input():
    brief = build_narration_brief(
        {
            "user_request": {"player_input": "관리인에게 기록을 보여 달라고 말합니다"},
            "engine_event": {"kind": "action"},
            "scene_state": {
                "scene_anchor": {"location": {"name": "기록실 입구"}},
                "target_view": {"name": "관리인"},
            },
        }
    )

    assert "응답 대상: 관리인" in brief
    assert "질문을 반복하지 말고" not in brief
    assert "목표:" not in brief


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
