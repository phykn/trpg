import json
from pathlib import Path

import pytest

from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.errors import PersistenceFailed
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import Memory
from src.game.domain.progress import GameProgress
from src.game.domain.story_patch_ledger import StoryPatchLedgerEntry


def _graph() -> Graph:
    return Graph(
        nodes={
            "player": GraphNode(
                id="player",
                type="character",
                properties={"name": "Player"},
            ),
            "town": GraphNode(
                id="town",
                type="location",
                properties={"name": "Town"},
            ),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
            )
        },
    )


async def test_local_fs_graph_repo_round_trips_graph_and_progress(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))
    graph = _graph()
    progress = GameProgress(game_id="game-1", player_id="player", turn_count=2)

    await repo.save_graph("game-1", graph)
    await repo.save_progress(progress)

    assert await repo.load_graph("game-1") == graph
    assert await repo.load_progress("game-1") == progress


async def test_local_fs_graph_repo_raises_for_missing_game(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))

    with pytest.raises(FileNotFoundError):
        await repo.load_graph("missing")

    with pytest.raises(FileNotFoundError):
        await repo.load_progress("missing")


async def test_local_fs_graph_repo_wraps_invalid_graph(tmp_path):
    graph_dir = Path(tmp_path) / "games" / "game-1" / "graph"
    graph_dir.mkdir(parents=True)
    (graph_dir / "nodes.json").write_text(
        json.dumps(
            [
                {
                    "game_id": "game-1",
                    "node_id": "player",
                    "node_type": "character",
                    "properties": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    (graph_dir / "edges.json").write_text(
        json.dumps(
            [
                {
                    "game_id": "game-1",
                    "edge_id": "located_at:player:void",
                    "edge_type": "located_at",
                    "from_node_id": "player",
                    "to_node_id": "void",
                    "properties": {},
                }
            ]
        ),
        encoding="utf-8",
    )

    repo = LocalFsGraphRepo(str(tmp_path))

    with pytest.raises(PersistenceFailed, match="missing node"):
        await repo.load_graph("game-1")


async def test_local_fs_graph_repo_round_trips_story_patch_entries(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))

    await repo.append_story_patch_entries(
        "game-1",
        [
            StoryPatchLedgerEntry(
                turn=1,
                status="rejected",
                intent_kind="clue_candidate",
                reason="found",
                patches=[],
                rejected_reasons=["duplicate patch id: clue_seen"],
                changed_node_ids=[],
                changed_edge_ids=[],
            ),
            StoryPatchLedgerEntry(
                turn=2,
                status="accepted",
                intent_kind="memory_candidate",
                reason="remembered",
                patches=[
                    {
                        "op": "add_memory",
                        "id": "mem_seen_ticket",
                        "summary": "표를 봤습니다.",
                    }
                ],
                rejected_reasons=[],
                changed_node_ids=["mem_seen_ticket"],
                changed_edge_ids=["has_knowledge:player:mem_seen_ticket"],
            ),
        ],
    )

    entries = await repo.load_story_patch_entries("game-1")

    assert [entry.status for entry in entries] == ["rejected", "accepted"]
    assert entries[0].rejected_reasons == ["duplicate patch id: clue_seen"]
    assert entries[1].changed_node_ids == ["mem_seen_ticket"]


async def test_local_fs_graph_repo_round_trips_target_memory_entries(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))

    await repo.append_memory_entries(
        "game-1",
        [
            Memory(
                turn=1,
                target="npc_olden",
                content="올든은 당신이 동행자를 찾는 중임을 기억합니다.",
                importance=2,
            ),
            Memory(
                turn=2,
                target="npc_other",
                content="다른 인물의 기억입니다.",
                importance=3,
            ),
        ],
    )

    entries = await repo.load_memory_entries("game-1", target="npc_olden")

    assert entries == [
        Memory(
            turn=1,
            target="npc_olden",
            content="올든은 당신이 동행자를 찾는 중임을 기억합니다.",
            importance=2,
        )
    ]
