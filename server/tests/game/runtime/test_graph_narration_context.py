import json

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState, GraphCombatTraceEvent
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import (
    ExchangePair,
    GMLogEntry,
    NarrationCue,
    RollLogEntry,
    TurnLogEntry,
)
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.action.dispatch import GraphActionDispatchResult
from src.game.runtime.narration.context import (
    build_action_narration_payload,
    build_input_narration_payload,
    build_roll_narration_payload,
)


def _character(node_id: str, *, name: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        type="character",
        properties={
            "name": name,
            "hp": 10,
            "max_hp": 10,
            "mp": 5,
            "max_mp": 5,
            "alive": True,
            "background": "경비병은 북문 앞에서 교대 기록을 관리합니다.",
            "desire": "북문 기록을 자기 손으로 정리하고 싶다.",
            "fear": "기록이 비면 책임이 자신에게 돌아올까 두렵다.",
            "contradiction": "규칙을 앞세우지만 빈 기록은 조용히 덮고 싶어 한다.",
            "secrets": ["숨은 단서가 있습니다."],
            "stats": {"body": 3, "agility": 2, "mind": 2, "presence": 2},
            "status": [],
        },
    )


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "square": GraphNode(
                    id="square",
                    type="location",
                    properties={
                        "name": "광장",
                        "description": "차가운 돌바닥이 이어집니다.",
                    },
                ),
                "north_gate": GraphNode(
                    id="north_gate",
                    type="location",
                    properties={"name": "북문"},
                ),
                "player_01": _character("player_01", name="당신"),
                "guard_01": _character("guard_01", name="경비병"),
                "city_watch": GraphNode(
                    id="city_watch",
                    type="faction",
                    properties={
                        "name": "도시 경비대",
                        "description": "북문을 지키는 경비 조직입니다.",
                    },
                ),
                "public_clue": GraphNode(
                    id="public_clue",
                    type="knowledge",
                    properties={
                        "title": "북문 단서",
                        "summary": "북문 교대 기록이 비어 있습니다.",
                        "visibility": "public",
                    },
                ),
                "private_clue": GraphNode(
                    id="private_clue",
                    type="knowledge",
                    properties={
                        "title": "숨은 단서",
                        "summary": "payload에 나오면 안 됩니다.",
                        "visibility": "private",
                    },
                ),
                "procedural_style": GraphNode(
                    id="procedural_style",
                    type="dialogue_style",
                    properties={
                        "name": "절차형 말투",
                        "speech_style": "짧고 기록문 같은 말투",
                        "humor_style": "농담을 보고서 항목처럼 분류함",
                        "traits": ["업무적", "간결함"],
                    },
                ),
                "ENFP": GraphNode(
                    id="ENFP",
                    type="mbti",
                    properties={
                        "attitude": "밝고 즉흥적으로 반응합니다.",
                        "speech_style": "말이 빠르고 감탄이 많습니다.",
                        "personality": "솔직하고 호기심이 많습니다.",
                        "boundary_style": "개인 질문에도 장난스럽게 받아칩니다.",
                        "humor_style": "어색함을 바로 짚어 웃음으로 바꿉니다.",
                        "decision_style": "감정에 먼저 반응한 뒤 이유를 붙입니다.",
                        "stress_response": "갑자기 말이 빨라집니다.",
                        "trust_response": "신뢰하면 자기 이야기를 길게 합니다.",
                        "conflict_style": "정면충돌 대신 농담으로 비켜갑니다.",
                        "roleplay_cues": ["상대 말에 바로 반응합니다"],
                        "avoid": ["차갑게 반복하지 않습니다"],
                    },
                ),
                "shop_herb": GraphNode(
                    id="shop_herb",
                    type="item",
                    properties={
                        "name": "상점 회복 약초",
                        "price": 3,
                        "kind": "consumable",
                    },
                ),
                "sword_01": GraphNode(
                    id="sword_01",
                    type="item",
                    properties={"name": "검", "kind": "weapon"},
                ),
            },
            edges={
                "located_at:player_01:square": GraphEdge(
                    id="located_at:player_01:square",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="square",
                ),
                "located_at:guard_01:square": GraphEdge(
                    id="located_at:guard_01:square",
                    type="located_at",
                    from_node_id="guard_01",
                    to_node_id="square",
                ),
                "carries:guard_01:shop_herb": GraphEdge(
                    id="carries:guard_01:shop_herb",
                    type="carries",
                    from_node_id="guard_01",
                    to_node_id="shop_herb",
                ),
                "member_of_faction:guard_01:city_watch": GraphEdge(
                    id="member_of_faction:guard_01:city_watch",
                    type="member_of_faction",
                    from_node_id="guard_01",
                    to_node_id="city_watch",
                ),
                "has_knowledge:guard_01:public_clue": GraphEdge(
                    id="has_knowledge:guard_01:public_clue",
                    type="has_knowledge",
                    from_node_id="guard_01",
                    to_node_id="public_clue",
                ),
                "has_knowledge:guard_01:private_clue": GraphEdge(
                    id="has_knowledge:guard_01:private_clue",
                    type="has_knowledge",
                    from_node_id="guard_01",
                    to_node_id="private_clue",
                ),
                "uses_dialogue_style:guard_01:procedural_style": GraphEdge(
                    id="uses_dialogue_style:guard_01:procedural_style",
                    type="uses_dialogue_style",
                    from_node_id="guard_01",
                    to_node_id="procedural_style",
                ),
                "has_mbti:guard_01:ENFP": GraphEdge(
                    id="has_mbti:guard_01:ENFP",
                    type="has_mbti",
                    from_node_id="guard_01",
                    to_node_id="ENFP",
                ),
                "connects_to:square:north_gate": GraphEdge(
                    id="connects_to:square:north_gate",
                    type="connects_to",
                    from_node_id="square",
                    to_node_id="north_gate",
                ),
                "carries:player_01:sword_01": GraphEdge(
                    id="carries:player_01:sword_01",
                    type="carries",
                    from_node_id="player_01",
                    to_node_id="sword_01",
                ),
            },
        ),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
        log_entries=[GMLogEntry(id=1, kind="gm", text="경비병이 북문을 지킵니다.")],
        turn_log=[
            TurnLogEntry(
                turn=1,
                target="guard_01",
                summary="경비병은 북문을 신경 씁니다.",
                importance=2,
            )
        ],
        recent_exchanges=[
            ExchangePair(
                turn=1,
                player="북문에 대해 묻습니다.",
                narrator="경비병은 북문 쪽을 봅니다.",
                target="guard_01",
            )
        ],
    )


def test_input_payload_includes_recent_context_and_keeps_player_input():
    runtime = _runtime()

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="경비병에게 북문을 묻습니다",
        action=Action(verb="speak", to="guard_01", how="friendly"),
        dialogue_target=runtime.graph.nodes["guard_01"],
    )
    encoded = json.dumps(payload, ensure_ascii=False)

    assert list(payload)[-1] == "user_request"
    assert payload["user_request"] == {"player_input": "경비병에게 북문을 묻습니다"}
    assert payload["engine_event"]["kind"] == "dialogue"
    assert payload["scene_state"]["target_view"]["id"] == "guard_01"
    assert payload["scene_state"]["target_view"]["desire"] == (
        "북문 기록을 자기 손으로 정리하고 싶다."
    )
    assert payload["scene_state"]["target_view"]["fear"] == (
        "기록이 비면 책임이 자신에게 돌아올까 두렵다."
    )
    assert payload["scene_state"]["target_view"]["contradiction"] == (
        "규칙을 앞세우지만 빈 기록은 조용히 덮고 싶어 한다."
    )
    assert "recent_log" not in payload
    assert "recent_narration" not in payload["reference_context"]
    assert payload["reference_context"]["recent_exchanges"] == [
        {
            "turn": 1,
            "player": "북문에 대해 묻습니다.",
            "narrator": "경비병은 북문 쪽을 봅니다.",
            "target": "guard_01",
        }
    ]
    assert "screen_log" not in payload["reference_context"]
    assert "previous_scene" not in payload["reference_context"]
    assert payload["scene_state"]["scene_anchor"]["location"]["id"] == "square"
    assert "recent_log" not in encoded
    assert "숨은 단서가 있습니다." not in encoded
    assert "player_input" not in payload
    assert "current_event" not in payload
    assert "recent_narration" not in payload


def test_input_payload_includes_current_story_context():
    runtime = _runtime()
    runtime.graph.nodes["chapter_01"] = GraphNode(
        id="chapter_01",
        type="chapter",
        properties={
            "title": "푸른섬",
            "description": "애도와 산 사람의 자리 사이에서 빈방의 의미를 판단합니다.",
            "guidance": "빈방의 물건과 산 사람의 자리만 근거로 씁니다.",
            "status": "active",
        },
    )
    runtime.graph.nodes["quest_01"] = GraphNode(
        id="quest_01",
        type="quest",
        properties={
            "title": "빈방 사건",
            "description": "레아의 빈방을 계속 닫아 둘지 정합니다.",
            "status": "active",
        },
    )
    runtime.progress = runtime.progress.model_copy(
        update={"active_quest_id": "quest_01"}
    )

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="레아에게 말을 겁니다",
        action=Action(verb="speak", to="guard_01"),
        dialogue_target=runtime.graph.nodes["guard_01"],
    )

    assert payload["reference_context"]["current_story"] == {
        "chapter": {
            "id": "chapter_01",
            "name": "푸른섬",
            "status": "active",
            "description": "애도와 산 사람의 자리 사이에서 빈방의 의미를 판단합니다.",
            "guidance": "빈방의 물건과 산 사람의 자리만 근거로 씁니다.",
        },
        "active_quest": {
            "id": "quest_01",
            "name": "빈방 사건",
            "status": "active",
            "description": "레아의 빈방을 계속 닫아 둘지 정합니다.",
        },
    }


def test_input_payload_keeps_chapter_guidance_list():
    runtime = _runtime()
    runtime.graph.nodes["chapter_01"] = GraphNode(
        id="chapter_01",
        type="chapter",
        properties={
            "title": "안개섬",
            "description": "출항 규칙을 확인합니다.",
            "guidance": [
                "튜토리얼 장이다.",
                "질문에는 항구 규칙과 안개 바다만 짧게 답한다.",
                "확인서나 허가를 새 조건으로 만들지 않는다.",
            ],
            "status": "active",
        },
    )

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="올든에게 왜 못 떠나는지 묻습니다",
        action=Action(verb="speak", to="guard_01"),
        dialogue_target=runtime.graph.nodes["guard_01"],
    )

    assert payload["reference_context"]["current_story"]["chapter"]["guidance"] == [
        "튜토리얼 장이다.",
        "질문에는 항구 규칙과 안개 바다만 짧게 답한다.",
        "확인서나 허가를 새 조건으로 만들지 않는다.",
    ]


def test_recent_exchanges_include_visible_ui_cues():
    runtime = _runtime()
    runtime.recent_exchanges[0] = ExchangePair(
        turn=1,
        player="북문에 대해 묻습니다.",
        narrator="경비병은 북문 쪽을 봅니다.",
        target="guard_01",
        cues=[
            NarrationCue(
                kind="warning",
                label="경계",
                text="경비병의 의심이 커집니다.",
            )
        ],
    )

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="경비병에게 북문을 묻습니다",
        action=Action(verb="speak", to="guard_01", how="friendly"),
        dialogue_target=runtime.graph.nodes["guard_01"],
    )

    assert payload["reference_context"]["recent_exchanges"] == [
        {
            "turn": 1,
            "player": "북문에 대해 묻습니다.",
            "narrator": "경비병은 북문 쪽을 봅니다.",
            "target": "guard_01",
            "cues": [
                {
                    "kind": "warning",
                    "label": "경계",
                    "text": "경비병의 의심이 커집니다.",
                    "scope": "delta",
                }
            ],
        }
    ]


def test_narration_references_use_recent_raw_then_previous_summaries():
    runtime = _runtime()
    runtime.recent_exchanges = [
        ExchangePair(turn=turn, player=f"질문 {turn}", narrator=f"응답 {turn}")
        for turn in range(1, 7)
    ]
    runtime.turn_log = [
        TurnLogEntry(turn=turn, summary=f"장면 요약 {turn}", target=f"npc_{turn}")
        for turn in range(1, 7)
    ]

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="경비병에게 북문을 묻습니다",
        action=Action(verb="speak", to="guard_01", how="friendly"),
        dialogue_target=runtime.graph.nodes["guard_01"],
    )

    assert payload["reference_context"]["previous_scene"] == [
        {"turn": turn, "target": f"npc_{turn}", "summary": f"장면 요약 {turn}"}
        for turn in range(1, 4)
    ]
    assert payload["reference_context"]["recent_exchanges"] == [
        {"turn": turn, "player": f"질문 {turn}", "narrator": f"응답 {turn}"}
        for turn in range(4, 7)
    ]
    assert "related_memory" not in payload["reference_context"]
    assert "recent_narration" not in payload["reference_context"]
    assert "screen_log" not in payload["reference_context"]


def test_action_payload_adds_arrival_branch_when_inventory_property_matches():
    before = _runtime()
    after = _runtime()
    after.graph.nodes["arrival_dock"] = GraphNode(
        id="arrival_dock",
        type="location",
        properties={
            "name": "도착 선착장",
            "arrival_branches": [
                {
                    "inventory_item_property": "route_marker",
                    "text": "표식이 있는 도착 결과가 적용됩니다.",
                    "else_text": "표식이 없는 도착 결과가 적용됩니다.",
                }
            ],
        },
    )
    after.graph.nodes["marked_item"] = GraphNode(
        id="marked_item",
        type="item",
        properties={"name": "표식 물건", "route_marker": True},
    )
    after.graph.edges.pop("located_at:player_01:square")
    after.graph.edges["located_at:player_01:arrival_dock"] = GraphEdge(
        id="located_at:player_01:arrival_dock",
        type="located_at",
        from_node_id="player_01",
        to_node_id="arrival_dock",
    )
    after.graph.edges["carries:player_01:marked_item"] = GraphEdge(
        id="carries:player_01:marked_item",
        type="carries",
        from_node_id="player_01",
        to_node_id="marked_item",
    )

    payload = build_action_narration_payload(
        before=before,
        after=after,
        action=Action(verb="move", to="arrival_dock"),
        dispatch=GraphActionDispatchResult(
            runtime=after,
            kind="move",
            applied=1,
            changed_node_ids=[],
            changed_edge_ids=[],
            removed_edge_ids=[],
            outcome="moved",
        ),
        card_texts=["도착 선착장으로 이동합니다."],
    )

    assert (
        "표식이 있는 도착 결과가 적용됩니다."
        in payload["engine_event"]["resolved_results"]
    )


def test_action_payload_adds_connection_travel_text_on_location_change():
    before = _runtime()
    after = _runtime()
    after.graph.nodes["arrival_dock"] = GraphNode(
        id="arrival_dock",
        type="location",
        properties={"name": "도착 선착장"},
    )
    before.graph.edges["connects_to:square:arrival_dock"] = GraphEdge(
        id="connects_to:square:arrival_dock",
        type="connects_to",
        from_node_id="square",
        to_node_id="arrival_dock",
        properties={
            "travel_text": "배는 광장을 떠나 물길을 건너 도착 선착장에 닿습니다."
        },
    )
    after.graph.edges["connects_to:square:arrival_dock"] = before.graph.edges[
        "connects_to:square:arrival_dock"
    ]
    after.graph.edges.pop("located_at:player_01:square")
    after.graph.edges["located_at:player_01:arrival_dock"] = GraphEdge(
        id="located_at:player_01:arrival_dock",
        type="located_at",
        from_node_id="player_01",
        to_node_id="arrival_dock",
    )

    payload = build_action_narration_payload(
        before=before,
        after=after,
        action=Action(verb="move", to="arrival_dock"),
        dispatch=GraphActionDispatchResult(
            runtime=after,
            kind="move",
            applied=1,
            changed_node_ids=[],
            changed_edge_ids=[],
            removed_edge_ids=[],
            outcome="moved",
        ),
        card_texts=["도착 선착장으로 이동합니다."],
    )

    assert (
        "배는 광장을 떠나 물길을 건너 도착 선착장에 닿습니다."
        in payload["engine_event"]["resolved_results"]
    )


def test_action_payload_adds_arrival_branch_else_text_without_matching_item():
    before = _runtime()
    after = _runtime()
    after.graph.nodes["arrival_dock"] = GraphNode(
        id="arrival_dock",
        type="location",
        properties={
            "name": "도착 선착장",
            "arrival_branches": [
                {
                    "inventory_item_property": "route_marker",
                    "text": "표식이 있는 도착 결과가 적용됩니다.",
                    "else_text": "표식이 없는 도착 결과가 적용됩니다.",
                }
            ],
        },
    )
    after.graph.edges.pop("located_at:player_01:square")
    after.graph.edges["located_at:player_01:arrival_dock"] = GraphEdge(
        id="located_at:player_01:arrival_dock",
        type="located_at",
        from_node_id="player_01",
        to_node_id="arrival_dock",
    )

    payload = build_action_narration_payload(
        before=before,
        after=after,
        action=Action(verb="move", to="arrival_dock"),
        dispatch=GraphActionDispatchResult(
            runtime=after,
            kind="move",
            applied=1,
            changed_node_ids=[],
            changed_edge_ids=[],
            removed_edge_ids=[],
            outcome="moved",
        ),
        card_texts=["도착 선착장으로 이동합니다."],
    )

    assert (
        "표식이 없는 도착 결과가 적용됩니다."
        in payload["engine_event"]["resolved_results"]
    )


def test_roll_payload_keeps_original_player_input_and_marks_preroll_text():
    runtime = _runtime()
    runtime.log_entries.append(
        GMLogEntry(
            id=2,
            kind="gm",
            text="경비병의 표정을 읽으려 합니다.",
        )
    )
    pending = {
        "body": "경비병의 표정을 읽으려 합니다.",
        "player_input": "경비병에게 취미가 뭐냐고 묻습니다",
    }

    payload = build_roll_narration_payload(
        runtime=runtime,
        action=Action(verb="speak", to="guard_01", how="friendly"),
        pending=pending,
        roll_entry=RollLogEntry(
            id=3,
            kind="roll",
            check="매력",
            roll=18,
            margin=5,
            result="success",
        ),
        outcome="success",
    )

    assert payload["user_request"]["player_input"] == (
        "경비병에게 취미가 뭐냐고 묻습니다"
    )
    assert "check_reason" not in payload["engine_event"]
    assert "preroll_narration" not in payload["engine_event"]
    target_view = payload["scene_state"]["target_view"]
    assert target_view["id"] == "guard_01"
    assert target_view["faction"] == {
        "id": "city_watch",
        "name": "도시 경비대",
        "description": "북문을 지키는 경비 조직입니다.",
    }
    assert target_view["public_knowledge"] == [
        {
            "id": "public_clue",
            "title": "북문 단서",
            "summary": "북문 교대 기록이 비어 있습니다.",
        }
    ]
    assert target_view["dialogue_style"] == {
        "id": "procedural_style",
        "name": "절차형 말투",
        "speech_style": "짧고 기록문 같은 말투",
        "humor_style": "농담을 보고서 항목처럼 분류함",
        "traits": ["업무적", "간결함"],
    }
    assert "숨은 단서" not in json.dumps(payload, ensure_ascii=False)


def test_success_roll_payload_exposes_reveal_on_success_private_knowledge():
    runtime = _runtime()
    runtime.graph.nodes["success_clue"] = GraphNode(
        id="success_clue",
        type="knowledge",
        properties={
            "title": "잠긴 장부",
            "summary": "장부의 빈 줄은 교대자가 일부러 지운 흔적입니다.",
            "visibility": "private",
            "reveal_on_success": True,
        },
    )
    runtime.graph.edges["has_knowledge:guard_01:success_clue"] = GraphEdge(
        id="has_knowledge:guard_01:success_clue",
        type="has_knowledge",
        from_node_id="guard_01",
        to_node_id="success_clue",
    )
    runtime = runtime.model_copy(update={"graph": runtime.graph})

    payload = build_roll_narration_payload(
        runtime=runtime,
        action=Action(verb="perceive", what="guard_01"),
        pending={"player_input": "경비병의 장부를 자세히 살핍니다"},
        roll_entry=RollLogEntry(
            id=3,
            kind="roll",
            check="지력",
            roll=18,
            margin=5,
            result="success",
        ),
        outcome="success",
    )

    assert payload["engine_event"]["revealed_facts"] == [
        {
            "id": "public_clue",
            "title": "북문 단서",
            "summary": "북문 교대 기록이 비어 있습니다.",
        },
        {
            "id": "success_clue",
            "title": "잠긴 장부",
            "summary": "장부의 빈 줄은 교대자가 일부러 지운 흔적입니다.",
        },
    ]
    target_view = payload["scene_state"]["target_view"]
    assert "success_clue" not in json.dumps(target_view, ensure_ascii=False)


def test_failed_roll_payload_does_not_expose_reveal_on_success_private_knowledge():
    runtime = _runtime()
    runtime.graph.nodes["success_clue"] = GraphNode(
        id="success_clue",
        type="knowledge",
        properties={
            "title": "잠긴 장부",
            "summary": "장부의 빈 줄은 교대자가 일부러 지운 흔적입니다.",
            "visibility": "private",
            "reveal_on_success": True,
        },
    )
    runtime.graph.edges["has_knowledge:guard_01:success_clue"] = GraphEdge(
        id="has_knowledge:guard_01:success_clue",
        type="has_knowledge",
        from_node_id="guard_01",
        to_node_id="success_clue",
    )
    runtime = runtime.model_copy(update={"graph": runtime.graph})

    payload = build_roll_narration_payload(
        runtime=runtime,
        action=Action(verb="perceive", what="guard_01"),
        pending={"player_input": "경비병의 장부를 자세히 살핍니다"},
        roll_entry=RollLogEntry(
            id=3,
            kind="roll",
            check="지력",
            roll=8,
            margin=-5,
            result="fail",
        ),
        outcome="failure",
    )

    assert "revealed_facts" not in payload["engine_event"]
    assert "잠긴 장부" not in json.dumps(payload, ensure_ascii=False)


def test_roll_payload_keeps_check_reason_without_preroll_narration():
    runtime = _runtime()
    pending = {
        "check_reason": "경비병을 설득하려면 믿을 만한 말을 해야 합니다.",
        "body": "경비병은 답하기 전에 주변의 시선을 먼저 살핍니다.",
        "player_input": "경비병에게 북문 기록을 보여 달라고 설득합니다",
    }

    payload = build_roll_narration_payload(
        runtime=runtime,
        action=Action(verb="speak", to="guard_01", how="friendly"),
        pending=pending,
        roll_entry=RollLogEntry(
            id=3,
            kind="roll",
            check="매력",
            roll=12,
            margin=-1,
            result="fail",
        ),
        outcome="failure",
    )

    assert (
        payload["user_request"]["player_input"]
        == "경비병에게 북문 기록을 보여 달라고 설득합니다"
    )
    assert (
        payload["engine_event"]["check_reason"]
        == "경비병을 설득하려면 믿을 만한 말을 해야 합니다."
    )
    assert "preroll_narration" not in payload["engine_event"]


def test_roll_payload_does_not_use_recent_narration_context():
    runtime = _runtime()
    runtime.log_entries.append(
        GMLogEntry(
            id=2,
            kind="gm",
            text="경비병은 답하기 전에 주변의 시선을 먼저 살핍니다.",
        )
    )
    pending = {
        "check_reason": "경비병을 설득하려면 믿을 만한 말을 해야 합니다.",
        "body": "경비병은 답하기 전에 주변의 시선을 먼저 살핍니다.",
        "player_input": "경비병에게 북문 기록을 보여 달라고 설득합니다",
    }

    payload = build_roll_narration_payload(
        runtime=runtime,
        action=Action(verb="speak", to="guard_01", how="friendly"),
        pending=pending,
        roll_entry=RollLogEntry(
            id=3,
            kind="roll",
            check="매력",
            roll=18,
            margin=5,
            result="success",
        ),
        outcome="success",
    )

    encoded = json.dumps(payload, ensure_ascii=False)

    assert "recent_narration" not in payload["reference_context"]
    assert "경비병은 답하기 전에 주변의 시선을 먼저 살핍니다." not in encoded


def test_roll_payload_does_not_use_extended_recent_narration_context():
    runtime = _runtime()
    runtime.log_entries.append(
        GMLogEntry(
            id=2,
            kind="gm",
            text=(
                "경비병은 답하기 전에 주변의 시선을 먼저 살핍니다. "
                "손끝이 문서 위에서 멈춥니다."
            ),
        )
    )
    pending = {
        "check_reason": "경비병을 설득하려면 믿을 만한 말을 해야 합니다.",
        "body": "경비병은 답하기 전에 주변의 시선을 먼저 살핍니다.",
        "player_input": "경비병에게 북문 기록을 보여 달라고 설득합니다",
    }

    payload = build_roll_narration_payload(
        runtime=runtime,
        action=Action(verb="speak", to="guard_01", how="friendly"),
        pending=pending,
        roll_entry=RollLogEntry(
            id=3,
            kind="roll",
            check="매력",
            roll=18,
            margin=5,
            result="success",
        ),
        outcome="success",
    )

    encoded = json.dumps(payload, ensure_ascii=False)

    assert "recent_narration" not in payload["reference_context"]
    assert "경비병은 답하기 전에 주변의 시선을 먼저 살핍니다." not in encoded


def test_roll_payload_can_include_completed_quest_result_cards():
    runtime = _runtime()
    pending = {
        "check_reason": "경비병에게 북문 규칙을 묻습니다.",
        "body": "경비병은 답하기 전에 주변의 시선을 먼저 살핍니다.",
        "player_input": "경비병에게 북문 규칙을 묻습니다",
    }

    payload = build_roll_narration_payload(
        runtime=runtime,
        action=Action(verb="speak", to="guard_01", how="friendly"),
        pending=pending,
        roll_entry=RollLogEntry(
            id=3,
            kind="roll",
            check="매력",
            roll=18,
            margin=5,
            result="success",
        ),
        outcome="success",
        result_texts=["성공  매력", "북문은 밤마다 닫힙니다."],
    )

    assert payload["engine_event"]["resolved_results"] == [
        "성공  매력",
        "북문은 밤마다 닫힙니다.",
    ]
    assert payload["result_cards"] == [
        {"text": "성공  매력"},
        {"text": "북문은 밤마다 닫힙니다."},
    ]


def test_input_payload_compacts_target_mbti_for_narration_tokens():
    runtime = _runtime()

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="경비병에게 북문 기록을 보여 달라고 말합니다",
        action=Action(verb="speak", to="guard_01", how="friendly"),
        dialogue_target=runtime.graph.nodes["guard_01"],
    )

    mbti = payload["scene_state"]["target_view"]["mbti"]
    assert mbti == {
        "attitude": "밝고 즉흥적으로 반응합니다.",
        "speech_style": "말이 빠르고 감탄이 많습니다.",
        "boundary_style": "개인 질문에도 장난스럽게 받아칩니다.",
        "humor_style": "어색함을 바로 짚어 웃음으로 바꿉니다.",
        "roleplay_cues": ["상대 말에 바로 반응합니다"],
        "avoid": ["차갑게 반복하지 않습니다"],
    }


def test_action_payload_omits_internal_action_ids_from_narration():
    runtime = _runtime()
    dispatch = GraphActionDispatchResult(
        runtime=runtime,
        kind="quest",
        applied=1,
        changed_node_ids=[],
        changed_edge_ids=[],
        removed_edge_ids=[],
        outcome="accepted",
    )

    payload = build_action_narration_payload(
        before=runtime,
        after=runtime,
        action=Action(
            verb="transfer",
            what="q_red_refund",
            from_="quest_giver_red",
            to="player_01",
            how="accept",
        ),
        dispatch=dispatch,
        card_texts=["의뢰 「분노 환불 사건」을 시작합니다."],
    )
    encoded = json.dumps(payload, ensure_ascii=False)

    assert payload["engine_event"]["action"] == {
        "verb": "transfer",
        "how": "accept",
    }
    assert "q_red_refund" not in encoded
    assert "quest_giver_red" not in encoded
    assert "player_01" not in encoded


def test_input_payload_includes_target_public_knowledge_and_mentioned_inventory():
    runtime = _runtime()
    guard = runtime.graph.nodes["guard_01"].model_copy(
        update={
            "properties": {
                **runtime.graph.nodes["guard_01"].properties,
                "tone_hint": "짧게 가격과 이용 조건만 말한다.",
            }
        }
    )
    runtime.graph.nodes["guard_01"] = guard

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="경비병에게 회복 약초 가격을 묻습니다",
        action=Action(verb="speak", to="guard_01", how="friendly"),
        dialogue_target=runtime.graph.nodes["guard_01"],
    )

    target_view = payload["scene_state"]["target_view"]
    assert target_view["tone_hint"] == "짧게 가격과 이용 조건만 말한다."
    assert target_view["public_knowledge"] == [
        {
            "id": "public_clue",
            "title": "북문 단서",
            "summary": "북문 교대 기록이 비어 있습니다.",
        }
    ]
    assert target_view["available_items"] == [
        {
            "id": "shop_herb",
            "name": "상점 회복 약초",
            "kind": "consumable",
            "price": 3,
        }
    ]


def test_input_payload_keeps_full_world_guidance():
    runtime = _runtime().model_copy(
        update={
            "content": _runtime().content.model_copy(
                update={"world_guidance": "가" * 1700}
            )
        }
    )

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="경비병에게 말을 겁니다",
        action=Action(verb="speak", to="guard_01", how="friendly"),
        dialogue_target=runtime.graph.nodes["guard_01"],
    )

    assert payload["reference_context"]["world_guidance"] == "가" * 1700


def test_action_payload_contains_safe_current_event_and_combat_view():
    runtime = _runtime()
    runtime.log_entries.append(
        GMLogEntry(
            id=2,
            kind="gm",
            text="당신의 공격이 허수아비에게 닿습니다. 교전은 이어집니다.",
            outcome="success",
        )
    )
    dispatch = GraphActionDispatchResult(
        runtime=runtime,
        kind="combat",
        applied=1,
        changed_node_ids=["guard_01"],
        changed_edge_ids=[],
        removed_edge_ids=[],
        outcome="ongoing",
        combat_trace=[
            GraphCombatTraceEvent(
                kind="player_attack_success",
                actor_id="player_01",
                target="guard_01",
                state="hurt",
            )
        ],
    )

    payload = build_action_narration_payload(
        before=runtime,
        after=runtime,
        action=Action(verb="attack", what="guard_01"),
        dispatch=dispatch,
        card_texts=["전투가 이어집니다."],
    )

    encoded = json.dumps(payload, ensure_ascii=False)

    assert "user_request" not in payload
    assert payload["engine_event"]["kind"] == "combat"
    assert payload["engine_event"]["outcome"] == "ongoing"
    assert payload["result_cards"] == [{"text": "전투가 이어집니다."}]
    assert "recent_narration" not in payload["reference_context"]
    assert "recent_log" not in payload
    assert payload["combat_view"]["kind"] == "combat_exchange"
    assert payload["combat_view"]["player_can_act"] is True
    assert payload["combat_view"]["exchange_result"] == "success"
    assert payload["combat_view"]["events"]
    assert "player_attack_success" not in encoded
    assert "hurt" not in encoded
    assert "damage" not in encoded
    assert "hp" not in encoded.lower()


def test_action_payload_marks_location_enter_quest_trigger():
    runtime = _runtime()
    dispatch = GraphActionDispatchResult(
        runtime=runtime,
        kind="move",
        applied=1,
        changed_node_ids=["player_01"],
        changed_edge_ids=[],
        removed_edge_ids=[],
    )

    payload = build_action_narration_payload(
        before=runtime,
        after=runtime,
        action=Action(verb="move", to="north_gate"),
        dispatch=dispatch,
        card_texts=["북문으로 이동합니다.", "퀘스트가 완료됩니다."],
    )

    assert payload["engine_event"]["quest_trigger"] == {"type": "location_enter"}


def test_action_payload_includes_story_transition_without_forcing_solution():
    before = _runtime()
    before.graph.nodes["chapter_01"] = GraphNode(
        id="chapter_01",
        type="chapter",
        properties={"title": "붉은섬", "status": "active"},
    )
    before.graph.nodes["chapter_02"] = GraphNode(
        id="chapter_02",
        type="chapter",
        properties={"title": "푸른섬", "status": "locked"},
    )
    before.graph.nodes["quest_done"] = GraphNode(
        id="quest_done",
        type="quest",
        properties={
            "title": "분노 환불 사건",
            "status": "active",
            "handoff": "엘리는 빈방 이야기는 레아에게서 시작될 것 같다고 말합니다.",
        },
    )
    before.graph.nodes["quest_next"] = GraphNode(
        id="quest_next",
        type="quest",
        properties={"title": "빈방 사건", "status": "locked"},
    )
    after = before.model_copy(deep=True)
    after.graph.nodes["chapter_01"].properties["status"] = "completed"
    after.graph.nodes["chapter_02"].properties["status"] = "active"
    after.graph.nodes["quest_done"].properties["status"] = "completed"
    after.graph.nodes["quest_next"].properties["status"] = "pending"
    dispatch = GraphActionDispatchResult(
        runtime=after,
        kind="decide",
        applied=3,
        changed_node_ids=["quest_done", "chapter_01", "chapter_02", "quest_next"],
        changed_edge_ids=[],
        removed_edge_ids=[],
    )

    payload = build_action_narration_payload(
        before=before,
        after=after,
        action=Action(verb="decide", what="quest_done", how="release"),
        dispatch=dispatch,
        card_texts=["당신은 분노 환불 사건에서 「분노를 흘려보냅니다」를 선택합니다."],
    )

    assert payload["engine_event"]["story_transition"] == {
        "completed_quests": [{"id": "quest_done", "name": "분노 환불 사건"}],
        "opened_chapter": {"id": "chapter_02", "name": "푸른섬"},
        "next_quest": {"id": "quest_next", "name": "빈방 사건"},
        "handoff": "엘리는 빈방 이야기는 레아에게서 시작될 것 같다고 말합니다.",
        "style": "lead_not_solution",
    }


def test_action_payload_keeps_terminal_combat_trace_after_state_clears():
    before = _runtime().model_copy(
        update={
            "progress": _runtime().progress.model_copy(
                update={
                    "graph_combat_state": GraphCombatState(
                        location_id="square",
                        player_id="player_01",
                        active_enemy_id="guard_01",
                        enemy_ids=["guard_01"],
                        participant_ids=["player_01", "guard_01"],
                        sides={"player_01": "player", "guard_01": "enemy"},
                        round=2,
                    )
                }
            )
        }
    )
    after = before.model_copy(
        update={
            "progress": before.progress.model_copy(update={"graph_combat_state": None})
        }
    )
    dispatch = GraphActionDispatchResult(
        runtime=after,
        kind="combat",
        applied=1,
        changed_node_ids=["guard_01"],
        changed_edge_ids=[],
        removed_edge_ids=[],
        outcome="victory",
        combat_trace=[
            GraphCombatTraceEvent(
                kind="enemy_defeated",
                actor_id="player_01",
                target="guard_01",
                state="critical",
            )
        ],
    )

    payload = build_action_narration_payload(
        before=before,
        after=after,
        action=Action(verb="attack", what="guard_01"),
        dispatch=dispatch,
        card_texts=["전투가 끝납니다."],
    )
    encoded = json.dumps(payload["combat_view"], ensure_ascii=False)

    assert payload["combat_view"]["outcome"] == "victory"
    assert payload["combat_view"]["exchange_result"] == "success"
    assert payload["combat_view"]["events"]
    assert "enemy_defeated" not in encoded
    assert "critical" not in encoded
