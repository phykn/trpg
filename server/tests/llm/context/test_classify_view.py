import json

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import DialoguePair, GMLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.llm.context.classify_view import (
    build_classify_context_view,
    classify_context_to_grounding_view,
)


def _character(character_id: str, *, name: str | None = None, xp_reward: int = 0) -> GraphNode:
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
            properties={"name": f"물건 {index}", "kind": "tool", "description": "숨겨야 할 물건 설명"},
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
            properties={"name": f"기술 {index}", "description": "숨겨야 할 기술 설명"},
        )
        edges[f"knows_skill:player_01:{node_id}"] = GraphEdge(
            id=f"knows_skill:player_01:{node_id}",
            type="knows_skill",
            from_node_id="player_01",
            to_node_id=node_id,
        )

    return GameRuntimeState(
        graph=Graph(nodes=nodes, edges=edges),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
        log_entries=[GMLogEntry(id=1, kind="gm", text=gm_log_text)],
        recent_dialogue=[
            DialoguePair(turn=turn, player=f"질문 {turn}", narrator=f"요약 {turn}")
            for turn in range(1, dialogue_count + 1)
        ],
    )


def test_classify_context_excludes_gm_narration_and_descriptions():
    runtime = _runtime()

    context = build_classify_context_view(runtime, "상인에게 말을 겁니다")
    payload = json.dumps(context, ensure_ascii=False)

    assert "GM 원문이 여기 들어가면 실패합니다." not in payload
    assert "description" not in payload
    assert "장소 설명이 classify에 들어가면 실패합니다." not in payload
    assert context["player_input"] == "상인에게 말을 겁니다"


def test_classify_context_tracks_omitted_candidates():
    runtime = _runtime(visible_character_count=10, inventory_count=12, skill_count=9)

    context = build_classify_context_view(runtime, "주변을 살핍니다")

    assert len(context["identity"]["visible_targets"]) == 8
    assert len(context["identity"]["inventory"]) == 10
    assert len(context["identity"]["skills"]) == 8
    assert context["budget"]["visible_targets_omitted"] == 2
    assert context["budget"]["inventory_omitted"] == 2
    assert context["budget"]["skills_omitted"] == 1


def test_classify_context_to_grounding_view_preserves_grounding_ids():
    context = build_classify_context_view(_runtime(), "숲으로 갑니다")

    grounding = classify_context_to_grounding_view(context)

    assert grounding["location"] == {"id": "town", "name": "마을"}
    assert {"id": "npc_0", "name": "상인 0", "type": "npc"} in grounding["entities"]
    assert {"id": "forest", "name": "숲", "type": "connection"} in grounding["entities"]
    assert grounding["inventory"] == [{"id": "item_0", "name": "물건 0", "kind": "tool"}]
    assert grounding["skills"] == [{"id": "skill_0", "name": "기술 0"}]


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
