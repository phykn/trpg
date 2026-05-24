import json

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import ExchangePair, GMLogEntry, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.llm.context.classify_view import (
    ClassifyContextLimits,
    build_classify_context_view,
    classify_context_to_grounding_view,
)


def _character(
    character_id: str, *, name: str | None = None, xp_reward: int = 0
) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": name or character_id,
            "description": f"{character_id} full description must not leak",
            "hp": 30,
            "max_hp": 30,
            "mp": 10,
            "max_mp": 10,
            "alive": True,
            "xp_reward": xp_reward,
            "stats": {"body": 10, "agility": 10, "mind": 10, "presence": 10},
            "status": [],
        },
    )


def _runtime(
    *,
    visible_character_count: int = 1,
    inventory_count: int = 1,
    skill_count: int = 1,
    active_quest: bool = False,
    gm_log_text: str = "GM 원문이 여기 들어가면 실패합니다.",
    dialogue_count: int = 1,
) -> GameRuntimeState:
    nodes: dict[str, GraphNode] = {
        "town": GraphNode(
            id="town",
            type="location",
            properties={
                "name": "마을",
                "description": "장소 설명이 classify에 들어가면 실패합니다.",
            },
        ),
        "forest": GraphNode(id="forest", type="location", properties={"name": "숲"}),
        "player_01": _character("player_01", name="당신"),
    }
    if active_quest:
        nodes["quest_01"] = GraphNode(
            id="quest_01",
            type="quest",
            properties={
                "name": "통행 의뢰",
                "description": "숨겨야 할 퀘스트 설명",
                "choices": {
                    "record": {"label": "기록으로 남깁니다"},
                    "release": {"label": "흘려보냅니다"},
                },
            },
        )
    edges: dict[str, GraphEdge] = {
        "located_at:player_01:town": GraphEdge(
            id="located_at:player_01:town",
            type="located_at",
            from_node_id="player_01",
            to_node_id="town",
        ),
        "connects_to:town:forest": GraphEdge(
            id="connects_to:town:forest",
            type="connects_to",
            from_node_id="town",
            to_node_id="forest",
        ),
    }
    for index in range(visible_character_count):
        node_id = f"npc_{index}"
        nodes[node_id] = _character(node_id, name=f"상인 {index}", xp_reward=0)
        edges[f"located_at:{node_id}:town"] = GraphEdge(
            id=f"located_at:{node_id}:town",
            type="located_at",
            from_node_id=node_id,
            to_node_id="town",
        )
    for index in range(inventory_count):
        node_id = f"item_{index}"
        nodes[node_id] = GraphNode(
            id=node_id,
            type="item",
            properties={
                "name": f"물건 {index}",
                "kind": "tool",
                "description": "숨겨야 할 물건 설명",
            },
        )
        edges[f"carries:player_01:{node_id}"] = GraphEdge(
            id=f"carries:player_01:{node_id}",
            type="carries",
            from_node_id="player_01",
            to_node_id=node_id,
        )
    for index in range(skill_count):
        node_id = f"skill_{index}"
        nodes[node_id] = GraphNode(
            id=node_id,
            type="skill",
            properties={
                "name": f"기술 {index}",
                "description": "숨겨야 할 기술 설명",
                "action": "attack",
            },
        )
        edges[f"knows_skill:player_01:{node_id}"] = GraphEdge(
            id=f"knows_skill:player_01:{node_id}",
            type="knows_skill",
            from_node_id="player_01",
            to_node_id=node_id,
        )

    return GameRuntimeState(
        graph=Graph(nodes=nodes, edges=edges),
        progress=GameProgress(
            game_id="game-1",
            player_id="player_01",
            active_quest_id="quest_01" if active_quest else None,
        ),
        log_entries=[GMLogEntry(id=1, kind="gm", text=gm_log_text)],
        recent_exchanges=[
            ExchangePair(turn=turn, player=f"질문 {turn}", narrator=f"요약 {turn}")
            for turn in range(1, dialogue_count + 1)
        ],
        turn_log=[
            TurnLogEntry(
                turn=1,
                target="npc_0",
                summary="상인이 숲 방향을 가리켰습니다.",
                importance=1,
            )
        ],
    )


def test_classify_context_excludes_gm_narration_and_descriptions():
    runtime = _runtime()

    context = build_classify_context_view(runtime, "상인에게 말을 겁니다")
    payload = json.dumps(context, ensure_ascii=False)

    assert "GM 원문이 여기 들어가면 실패합니다." not in payload
    assert "description" not in payload
    assert "장소 설명이 classify에 들어가면 실패합니다." not in payload
    assert "player_input" not in context


def test_classify_context_orders_json_from_global_to_specific_context():
    runtime = _runtime(active_quest=True)

    context = build_classify_context_view(runtime, "상인에게 말을 겁니다")

    assert list(context) == ["mode", "identity", "affordances", "references"]
    assert list(context["identity"]) == [
        "player",
        "location",
        "active_quest",
        "available_quests",
        "visible_targets",
        "exits",
        "inventory",
        "equipment",
        "skills",
        "location_items",
        "merchants",
        "corpses",
    ]
    assert list(context["references"]) == [
        "recent_scene",
        "recent_exchanges",
        "last_npc",
        "last_target",
        "last_item",
    ]


def test_classify_context_includes_minimal_recent_scene_summary():
    runtime = _runtime(gm_log_text="GM 원문 전체는 classify에 들어가면 안 됩니다.")

    context = build_classify_context_view(runtime, "그쪽으로 갑니다")
    payload = json.dumps(context, ensure_ascii=False)

    assert context["references"]["recent_scene"] == []
    assert "GM 원문 전체" not in payload


def test_classify_context_keeps_all_graph_related_candidates():
    runtime = _runtime(visible_character_count=10, inventory_count=12, skill_count=9)

    context = build_classify_context_view(runtime, "주변을 살핍니다")

    assert len(context["identity"]["visible_targets"]) == 10
    assert len(context["identity"]["inventory"]) == 12
    assert len(context["identity"]["skills"]) == 9
    assert "budget" not in context


def test_classify_context_limits_only_recent_context():
    runtime = _runtime(
        visible_character_count=5,
        inventory_count=4,
        skill_count=3,
        dialogue_count=4,
    )

    context = build_classify_context_view(
        runtime,
        "주변을 살핍니다",
        limits=ClassifyContextLimits(
            recent_exchanges=2,
        ),
    )

    assert len(context["identity"]["visible_targets"]) == 5
    assert len(context["identity"]["inventory"]) == 4
    assert len(context["identity"]["skills"]) == 3
    assert context["references"]["recent_exchanges"] == [
        {"turn": 3, "player": "질문 3", "narrator": "요약 3"},
        {"turn": 4, "player": "질문 4", "narrator": "요약 4"},
    ]


def test_classify_context_keeps_last_three_recent_exchanges_by_default():
    runtime = _runtime(dialogue_count=7)

    context = build_classify_context_view(runtime, "그 말을 이어갑니다")

    assert context["references"]["recent_exchanges"] == [
        {"turn": turn, "player": f"질문 {turn}", "narrator": f"요약 {turn}"}
        for turn in range(5, 8)
    ]


def test_classify_context_uses_raw_recent_then_previous_scene_summaries():
    runtime = _runtime(dialogue_count=6)
    runtime.turn_log = [
        TurnLogEntry(
            turn=turn,
            target=f"npc_{turn}",
            summary=f"장면 요약 {turn}",
            importance=1,
        )
        for turn in range(1, 7)
    ]

    context = build_classify_context_view(runtime, "그 다음 행동을 한다")

    assert context["references"]["recent_exchanges"] == [
        {"turn": turn, "player": f"질문 {turn}", "narrator": f"요약 {turn}"}
        for turn in range(4, 7)
    ]
    assert context["references"]["recent_scene"] == [
        {"turn": turn, "summary": f"장면 요약 {turn}", "target": f"npc_{turn}"}
        for turn in range(1, 4)
    ]


def test_classify_context_to_grounding_view_preserves_grounding_ids():
    context = build_classify_context_view(_runtime(), "숲으로 갑니다")

    grounding = classify_context_to_grounding_view(context)

    assert grounding["location"] == {"id": "town", "name": "마을"}
    assert grounding["entities"][0] == {
        "id": "player_01",
        "name": "당신",
        "type": "player",
    }
    assert {"id": "npc_0", "name": "상인 0", "type": "npc"} in grounding["entities"]
    assert {"id": "forest", "name": "숲", "type": "connection"} in grounding["entities"]
    assert grounding["inventory"] == [
        {"id": "item_0", "name": "물건 0", "kind": "tool"}
    ]
    assert grounding["skills"] == [
        {
            "id": "skill_0",
            "name": "기술 0",
            "action": "attack",
        }
    ]


def test_classify_context_to_grounding_view_preserves_active_quest_id():
    context = build_classify_context_view(
        _runtime(active_quest=True), "의뢰를 수락한다"
    )

    grounding = classify_context_to_grounding_view(context)

    assert grounding["quests"] == [
        {
            "id": "quest_01",
            "name": "통행 의뢰",
            "choices": [
                {"id": "record", "label": "기록으로 남깁니다"},
                {"id": "release", "label": "흘려보냅니다"},
            ],
        }
    ]
    assert context["affordances"]["can_decide"] == ["record", "release"]


def test_classify_context_exposes_active_quest_location_targets():
    runtime = _runtime(active_quest=True)
    runtime.graph.nodes["quest_01"].properties["triggers"] = [
        {"type": "location_enter", "target": "forest"}
    ]

    context = build_classify_context_view(runtime, "숲으로 떠난다")
    grounding = classify_context_to_grounding_view(context)

    assert grounding["quests"] == [
        {
            "id": "quest_01",
            "name": "통행 의뢰",
            "location_targets": ["forest"],
        }
    ]


def test_classify_context_exposes_visible_pending_quest_for_acceptance():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"] = GraphNode(
        id="quest_01",
        type="quest",
        properties={
            "name": "통행 의뢰",
            "status": "pending",
            "giver": "npc_0",
        },
    )

    context = build_classify_context_view(runtime, "상인 0의 의뢰를 수락한다")
    grounding = classify_context_to_grounding_view(context)

    assert context["identity"]["available_quests"] == [
        {
            "id": "quest_01",
            "name": "통행 의뢰",
            "status": "pending",
            "giver": "npc_0",
            "giver_name": "상인 0",
        }
    ]
    assert context["affordances"]["can_accept_or_abandon_quest"] == ["quest_01"]
    assert grounding["quests"] == context["identity"]["available_quests"]


def test_classify_context_hides_pending_quest_without_visible_giver():
    runtime = _runtime()
    runtime.graph.nodes["quest_01"] = GraphNode(
        id="quest_01",
        type="quest",
        properties={
            "name": "통행 의뢰",
            "status": "pending",
            "giver": "missing_npc",
        },
    )

    context = build_classify_context_view(runtime, "의뢰를 수락한다")

    assert context["identity"]["available_quests"] == []
    assert context["affordances"]["can_accept_or_abandon_quest"] == []


def test_classify_context_hides_quest_choices_until_goals_are_met():
    runtime = _runtime(active_quest=True)
    runtime.graph.nodes["quest_01"].properties.update(
        {
            "triggers": [
                {
                    "id": "convince_guard",
                    "type": "social_check",
                    "target": "npc_0",
                }
            ],
            "triggers_met": [False],
        }
    )

    context = build_classify_context_view(runtime, "기록으로 남깁니다")
    grounding = classify_context_to_grounding_view(context)

    assert grounding["quests"] == [{"id": "quest_01", "name": "통행 의뢰"}]
    assert context["affordances"]["can_decide"] == []

    runtime.graph.nodes["quest_01"].properties["triggers_met"] = [True]

    context = build_classify_context_view(runtime, "기록으로 남깁니다")
    assert context["affordances"]["can_decide"] == ["record", "release"]


def test_classify_context_to_grounding_view_preserves_optional_trade_candidates():
    context = {
        "mode": "exploration",
        "identity": {
            "location": {"id": "town", "name": "마을"},
            "visible_targets": [{"id": "merchant_01", "name": "상인", "type": "npc"}],
            "exits": [],
            "inventory": [],
            "equipment": {},
            "skills": [],
            "merchants": [
                {
                    "id": "merchant_01",
                    "name": "상인",
                    "stock": [{"id": "potion_01", "name": "물약", "price": 5}],
                }
            ],
            "corpses": [],
        },
        "references": {},
    }

    grounding = classify_context_to_grounding_view(context)

    assert grounding["merchants"] == [
        {
            "id": "merchant_01",
            "name": "상인",
            "stock": [{"id": "potion_01", "name": "물약", "price": 5}],
        }
    ]


def test_classify_context_exposes_items_at_current_location():
    runtime = _runtime()
    runtime.graph.nodes["ground_item"] = GraphNode(
        id="ground_item",
        type="item",
        properties={"name": "바닥 표식", "kind": "token"},
    )
    runtime.graph.edges["located_at:ground_item:town"] = GraphEdge(
        id="located_at:ground_item:town",
        type="located_at",
        from_node_id="ground_item",
        to_node_id="town",
    )

    context = build_classify_context_view(runtime, "바닥 표식을 줍는다")
    grounding = classify_context_to_grounding_view(context)

    assert context["identity"]["location_items"] == [
        {"id": "ground_item", "name": "바닥 표식", "kind": "token"}
    ]
    assert context["affordances"]["can_pick_up"] == ["ground_item"]
    assert grounding["location_items"] == context["identity"]["location_items"]


def test_classify_context_exposes_transfer_and_protected_candidates():
    nodes = {
        "town": GraphNode(id="town", type="location", properties={"name": "마을"}),
        "player_01": _character("player_01", name="당신"),
        "merchant_01": _character("merchant_01", name="상인"),
        "bystander_01": _character("bystander_01", name="구경꾼"),
        "guard_01": _character("guard_01", name="경비병", xp_reward=1),
        "corpse_01": _character("corpse_01", name="쓰러진 산적"),
        "potion_01": GraphNode(
            id="potion_01",
            type="item",
            properties={"name": "물약", "kind": "consumable", "price": 5},
        ),
        "coin_pouch_01": GraphNode(
            id="coin_pouch_01",
            type="item",
            properties={"name": "동전 주머니"},
        ),
        "ring_01": GraphNode(
            id="ring_01",
            type="item",
            properties={"name": "반지"},
        ),
    }
    nodes["merchant_01"].properties["gold"] = 20
    nodes["bystander_01"].properties["gold"] = 0
    nodes["guard_01"].properties["protected"] = True
    nodes["corpse_01"].properties["alive"] = False
    nodes["corpse_01"].properties["hp"] = 0
    edges = {
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
        "located_at:guard_01:town": GraphEdge(
            id="located_at:guard_01:town",
            type="located_at",
            from_node_id="guard_01",
            to_node_id="town",
        ),
        "located_at:bystander_01:town": GraphEdge(
            id="located_at:bystander_01:town",
            type="located_at",
            from_node_id="bystander_01",
            to_node_id="town",
        ),
        "located_at:corpse_01:town": GraphEdge(
            id="located_at:corpse_01:town",
            type="located_at",
            from_node_id="corpse_01",
            to_node_id="town",
        ),
        "carries:merchant_01:potion_01": GraphEdge(
            id="carries:merchant_01:potion_01",
            type="carries",
            from_node_id="merchant_01",
            to_node_id="potion_01",
        ),
        "carries:merchant_01:coin_pouch_01": GraphEdge(
            id="carries:merchant_01:coin_pouch_01",
            type="carries",
            from_node_id="merchant_01",
            to_node_id="coin_pouch_01",
        ),
        "carries:corpse_01:ring_01": GraphEdge(
            id="carries:corpse_01:ring_01",
            type="carries",
            from_node_id="corpse_01",
            to_node_id="ring_01",
        ),
    }
    runtime = GameRuntimeState(
        graph=Graph(nodes=nodes, edges=edges),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )

    context = build_classify_context_view(
        runtime, "상인에게 물약을 사고 경비병을 공격한다"
    )
    grounding = classify_context_to_grounding_view(context)

    assert {
        "id": "merchant_01",
        "name": "상인",
        "type": "npc",
    } in context["identity"]["visible_targets"]
    assert {
        "id": "guard_01",
        "name": "경비병",
        "type": "npc",
        "protected": True,
    } in context["identity"]["visible_targets"]
    assert context["affordances"]["can_attack"] == ["merchant_01", "bystander_01"]
    assert context["identity"]["merchants"] == [
        {
            "id": "merchant_01",
            "name": "상인",
            "stock": [
                {"id": "potion_01", "name": "물약", "kind": "consumable", "price": 5},
                {"id": "coin_pouch_01", "name": "동전 주머니", "kind": "item"},
            ],
        }
    ]
    assert context["identity"]["corpses"] == [
        {
            "id": "corpse_01",
            "name": "쓰러진 산적",
            "inventory": [{"id": "ring_01", "name": "반지", "kind": "item"}],
        }
    ]
    assert grounding["merchants"] == context["identity"]["merchants"]
    assert grounding["corpses"] == context["identity"]["corpses"]


def test_classify_context_keeps_all_merchant_and_corpse_inventory():
    nodes: dict[str, GraphNode] = {
        "town": GraphNode(id="town", type="location", properties={"name": "마을"}),
        "player_01": _character("player_01", name="당신"),
        "merchant_01": _character("merchant_01", name="상인"),
        "corpse_01": _character("corpse_01", name="쓰러진 산적"),
    }
    nodes["merchant_01"].properties["gold"] = 20
    nodes["corpse_01"].properties["alive"] = False
    nodes["corpse_01"].properties["hp"] = 0
    edges: dict[str, GraphEdge] = {
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
        "located_at:corpse_01:town": GraphEdge(
            id="located_at:corpse_01:town",
            type="located_at",
            from_node_id="corpse_01",
            to_node_id="town",
        ),
    }
    for index in range(9):
        item_id = f"stock_{index}"
        nodes[item_id] = GraphNode(
            id=item_id,
            type="item",
            properties={"name": f"상품 {index}"},
        )
        edges[f"carries:merchant_01:{item_id}"] = GraphEdge(
            id=f"carries:merchant_01:{item_id}",
            type="carries",
            from_node_id="merchant_01",
            to_node_id=item_id,
        )
    for index in range(5):
        item_id = f"loot_{index}"
        nodes[item_id] = GraphNode(
            id=item_id,
            type="item",
            properties={"name": f"전리품 {index}"},
        )
        edges[f"carries:corpse_01:{item_id}"] = GraphEdge(
            id=f"carries:corpse_01:{item_id}",
            type="carries",
            from_node_id="corpse_01",
            to_node_id=item_id,
        )
    runtime = GameRuntimeState(
        graph=Graph(nodes=nodes, edges=edges),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )

    context = build_classify_context_view(runtime, "상인과 시체를 확인한다")

    assert len(context["identity"]["merchants"][0]["stock"]) == 9
    assert len(context["identity"]["corpses"][0]["inventory"]) == 5
