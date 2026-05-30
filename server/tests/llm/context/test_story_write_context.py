from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import ExchangePair, Memory
from src.game.domain.progress import GameProgress
from src.game.domain.story_contract import (
    StoryBudgetContract,
    StoryContract,
    StoryStabilityDefaults,
    StoryToneContract,
    StoryWorldContract,
)
from src.game.domain.story_patch import StoryWriteIntent
from src.game.runtime.state import GameRuntimeState
from src.llm.context.story_write_context import build_story_write_input


def _contract() -> StoryContract:
    return StoryContract(
        id="test",
        world=StoryWorldContract(title="테스트"),
        tone=StoryToneContract(register="합니다체", person="second"),
        budgets=StoryBudgetContract(patches_per_turn=2, new_terms_per_turn=1),
        allowed_ops=["add_memory", "add_clue", "add_location"],
        stability_defaults=StoryStabilityDefaults(),
    )


def test_story_write_context_includes_dynamic_knowledge_details_and_memories():
    runtime = GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01",
                    type="character",
                    properties={"name": "당신"},
                ),
                "loc_harbor": GraphNode(
                    id="loc_harbor",
                    type="location",
                    properties={"name": "항구", "description": "젖은 밧줄이 보입니다."},
                ),
                "clue_wet_rope_001": GraphNode(
                    id="clue_wet_rope_001",
                    type="knowledge",
                    properties={
                        "kind": "clue",
                        "title": "젖은 밧줄",
                        "summary": "밧줄은 아직 물기를 머금고 있습니다.",
                        "visibility": "player",
                        "anchor_id": "loc_harbor",
                        "turn_id": 6,
                    },
                ),
            },
            edges={
                "located_at:player_01:loc_harbor": GraphEdge(
                    id="located_at:player_01:loc_harbor",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="loc_harbor",
                ),
                "has_knowledge:loc_harbor:clue_wet_rope_001": GraphEdge(
                    id="has_knowledge:loc_harbor:clue_wet_rope_001",
                    type="has_knowledge",
                    from_node_id="loc_harbor",
                    to_node_id="clue_wet_rope_001",
                ),
            },
        ),
        progress=GameProgress(game_id="game-1", player_id="player_01", turn_count=7),
        memories=[
            Memory(
                turn=6,
                target="npc_guard",
                content="경비병은 당신이 밧줄을 확인했다고 기억합니다.",
                importance=2,
            )
        ],
        recent_exchanges=[
            ExchangePair(
                turn=6,
                target="npc_guard",
                player="밧줄을 묻습니다.",
                narrator="경비병은 밧줄이 방금 젖었다고 말합니다.",
            )
        ],
    )

    input_ = build_story_write_input(
        runtime,
        contract=_contract(),
        intent=StoryWriteIntent(kind="clue_candidate", reason="follow clue"),
        player_input="젖은 밧줄을 다시 살핀다",
        action=Action(verb="perceive", what="clue_wet_rope_001"),
    )

    context = input_.visible_context
    clue = next(node for node in context["nodes"] if node["id"] == "clue_wet_rope_001")
    assert clue == {
        "id": "clue_wet_rope_001",
        "type": "knowledge",
        "name": "젖은 밧줄",
        "summary": "밧줄은 아직 물기를 머금고 있습니다.",
        "kind": "clue",
        "visibility": "player",
        "anchor_id": "loc_harbor",
        "turn_id": 6,
    }
    assert context["memories"] == [
        {
            "turn": 6,
            "target": "npc_guard",
            "content": "경비병은 당신이 밧줄을 확인했다고 기억합니다.",
            "importance": 2,
        }
    ]
    assert context["recent_exchanges"] == [
        {
            "turn": 6,
            "target": "npc_guard",
            "player": "밧줄을 묻습니다.",
            "narrator": "경비병은 밧줄이 방금 젖었다고 말합니다.",
        }
    ]
