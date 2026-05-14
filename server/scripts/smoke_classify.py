"""One-shot smoke check: call the classify LLM against the env-routed LLM to
verify the production prompt path (kernel + agent rules + substitutions) works.

Run from repo root:
  .venv/bin/python server/scripts/smoke_classify.py

Loads .env.dev to mirror run_api.py.
Exits 0 if every case parses to a valid action; non-zero otherwise.
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

load_dotenv(SERVER_DIR / ".env.dev")

from src.game.domain.graph import Graph, GraphEdge, GraphNode  # noqa: E402
from src.game.domain.progress import GameProgress  # noqa: E402
from src.game.runtime.state import GameRuntimeState  # noqa: E402
from src.llm.context.classify_view import build_classify_context_view  # noqa: E402
from src.llm.calls.classify import classify  # noqa: E402
from src.llm.calls.classify.schema import ClassifyInput  # noqa: E402
from src.llm.client import LLMClient  # noqa: E402

SAMPLE_SURROUNDINGS = {
    "location": {"id": "isnar_square", "name": "이스나르 광장"},
    "entities": [
        {"id": "player_01", "name": "주인공", "type": "player"},
        {"id": "guard_01", "name": "경비병", "type": "npc"},
        {"id": "merchant_01", "name": "광장 상인", "type": "npc"},
    ],
    "corpses": [],
    "skills": [],
    "inventory": [],
    "equipment": {},
    "in_combat": False,
    "growth": {"can_level_up": False},
    "merchants": [
        {
            "id": "merchant_01",
            "name": "광장 상인",
            "stock": [{"id": "healing_potion_01", "name": "회복약", "price": 5}],
        }
    ],
    "recent_npc": "guard_01",
}

CASES: list[tuple[str, str]] = [
    ("경비병에게 인사한다", "speak(to=guard_01, how=friendly)"),
    (
        "회복약을 산다",
        "transfer(from=merchant_01, to=player_01, how=trade, what=healing_potion_01)",
    ),
    ("경비병을 설득해 통과시켜달라", "speak(to=guard_01, how=friendly|deceptive)"),
    ("뭔가 해봐", "pass (vague)"),
]


def _classify_context(player_input: str, scene: dict) -> dict:
    return build_classify_context_view(_runtime_from_scene(scene), player_input)


def _runtime_from_scene(scene: dict) -> GameRuntimeState:
    graph = _graph_from_scene(scene)
    player_id = _player_id(scene)
    progress = GameProgress(
        game_id="smoke",
        player_id=player_id,
        locale="ko",
        active_subject_id=scene.get("recent_npc"),
    )
    return GameRuntimeState(graph=graph, progress=progress)


def _graph_from_scene(scene: dict) -> Graph:
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    location = scene["location"]
    location_id = location["id"]
    nodes[location_id] = GraphNode(
        id=location_id,
        type="location",
        properties=_properties(location),
    )
    player_id = _player_id(scene)

    for entity in scene.get("entities", []):
        entity_id = entity["id"]
        if entity["type"] == "connection":
            nodes[entity_id] = GraphNode(
                id=entity_id,
                type="location",
                properties=_properties(entity),
            )
            _edge(edges, "connects_to", location_id, entity_id)
        elif entity["type"] == "item":
            nodes[entity_id] = GraphNode(
                id=entity_id,
                type="item",
                properties=_properties(entity),
            )
            _edge(edges, "located_at", entity_id, location_id)
        else:
            nodes[entity_id] = GraphNode(
                id=entity_id,
                type="character",
                properties=_character_properties(entity),
            )
            _edge(edges, "located_at", entity_id, location_id)

    for item in scene.get("inventory", []):
        _add_item(nodes, item)
        _edge(edges, "carries", player_id, item["id"])
    for skill in scene.get("skills", []):
        nodes[skill["id"]] = GraphNode(
            id=skill["id"],
            type="skill",
            properties=_properties(skill),
        )
        _edge(edges, "knows_skill", player_id, skill["id"])
    for merchant in scene.get("merchants", []):
        if merchant["id"] in nodes:
            nodes[merchant["id"]].properties["gold"] = 999
        for item in merchant.get("stock", []):
            _add_item(nodes, item)
            _edge(edges, "carries", merchant["id"], item["id"])
    return Graph(nodes=nodes, edges=edges)


def _player_id(scene: dict) -> str:
    for entity in scene.get("entities", []):
        if entity.get("type") == "player":
            return entity["id"]
    return "player_01"


def _add_item(nodes: dict[str, GraphNode], item: dict) -> None:
    nodes[item["id"]] = GraphNode(
        id=item["id"],
        type="item",
        properties=_properties(item),
    )


def _edge(
    edges: dict[str, GraphEdge], edge_type: str, source: str, target: str
) -> None:
    edge_id = f"{edge_type}:{source}:{target}"
    edges[edge_id] = GraphEdge(
        id=edge_id,
        type=edge_type,
        from_node_id=source,
        to_node_id=target,
    )


def _character_properties(entity: dict) -> dict:
    props = {
        **_properties(entity),
        "alive": True,
        "status": [],
        "hp": 10,
        "max_hp": 10,
        "mp": 5,
        "max_mp": 5,
        "stats": {"body": 3, "agility": 3, "mind": 3, "presence": 3},
    }
    if entity.get("type") == "enemy":
        props["xp_reward"] = 1
    if "merchant" in entity.get("roles", []):
        props["gold"] = 999
    return props


def _properties(data: dict) -> dict:
    return {key: value for key, value in data.items() if key != "id"}


async def main() -> int:
    print("Loading LLMClient from env routing...")
    client = LLMClient.from_env()
    providers = client._providers
    default_route = providers["default"].model
    classify_route = providers.get("classify", providers["default"]).model
    print(f"  default route: {default_route}")
    print(f"  classify route: {classify_route}")
    print()

    failed = 0
    for player_input, hint in CASES:
        print(f"--- INPUT: {player_input!r}  (expect: {hint})")
        try:
            result = await classify(
                client,
                ClassifyInput(
                    player_input=player_input,
                    context=_classify_context(player_input, SAMPLE_SURROUNDINGS),
                ),
                locale="ko",
                retries=2,
            )
            print(f"    OK  {result.model_dump_json()}")
        except Exception as e:
            failed += 1
            print(f"    FAIL  {type(e).__name__}: {e}")
        print()

    print(f"Result: {len(CASES) - failed}/{len(CASES)} cases passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
