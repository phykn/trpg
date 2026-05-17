from src.db.graph.supabase import SupabaseGraphRepo
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import DialoguePair, GMLogEntry, TurnLogEntry
from src.game.domain.progress import GameProgress
from tests._fakes import FakePostgREST


def _repo(
    db: FakePostgREST | None = None,
) -> tuple[SupabaseGraphRepo, FakePostgREST]:
    repo = SupabaseGraphRepo.__new__(SupabaseGraphRepo)
    db = db or FakePostgREST()
    repo._db = db  # type: ignore[attr-defined]
    return repo, db


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


async def test_supabase_graph_repo_round_trips_graph_and_progress():
    repo, db = _repo()
    graph = _graph()
    progress = GameProgress(game_id="game-1", player_id="player", turn_count=4)

    await repo.save_graph("game-1", graph)
    await repo.save_progress(progress)

    assert await repo.load_graph("game-1") == graph
    assert await repo.load_progress("game-1") == progress

    assert "graph_nodes" in db.rows
    assert "graph_edges" in db.rows
    assert "game_progress" in db.rows


async def test_supabase_graph_repo_replace_save_removes_stale_rows():
    repo, db = _repo()
    await repo.save_graph("game-1", _graph())

    smaller = Graph(nodes={"town": GraphNode(id="town", type="location")})
    await repo.save_graph("game-1", smaller)

    assert await repo.load_graph("game-1") == smaller
    assert any(call[0] == "delete" and call[1] == "graph_edges" for call in db.calls)
    assert any(call[0] == "delete" and call[1] == "graph_nodes" for call in db.calls)


async def test_supabase_graph_repo_upserts_before_deleting_stale_rows():
    repo, db = _repo()
    await repo.save_graph("game-1", _graph())
    db.calls.clear()

    smaller = Graph(nodes={"town": GraphNode(id="town", type="location")})
    await repo.save_graph("game-1", smaller)

    first_upsert = next(
        index for index, call in enumerate(db.calls) if call[0] == "upsert"
    )
    first_delete = next(
        index for index, call in enumerate(db.calls) if call[0] == "delete"
    )
    assert first_upsert < first_delete


async def test_supabase_graph_repo_saves_partial_graph_changes_only():
    repo, db = _repo()
    await repo.save_graph("game-1", _graph())
    db.calls.clear()

    graph = Graph(
        nodes={
            "player": GraphNode(
                id="player",
                type="character",
                properties={"name": "Player", "hp": 12},
            ),
            "town": GraphNode(id="town", type="location", properties={"name": "Town"}),
            "forest": GraphNode(id="forest", type="location"),
        },
        edges={
            "connects_to:town:forest": GraphEdge(
                id="connects_to:town:forest",
                type="connects_to",
                from_node_id="town",
                to_node_id="forest",
            )
        },
    )

    await repo.save_graph_changes(
        "game-1",
        graph,
        changed_node_ids=["player", "forest"],
        changed_edge_ids=["connects_to:town:forest"],
        removed_edge_ids=["located_at:player:town"],
    )

    upserts = [call for call in db.calls if call[0] == "upsert"]
    deletes = [call for call in db.calls if call[0] == "delete"]

    assert [call[1] for call in upserts] == ["graph_nodes", "graph_edges"]
    assert [row["node_id"] for row in upserts[0][2]] == ["player", "forest"]
    assert [row["edge_id"] for row in upserts[1][2]] == ["connects_to:town:forest"]
    assert deletes == [
        (
            "delete",
            "graph_edges",
            {
                "game_id": "eq.game-1",
                "edge_id": "in.(located_at:player:town)",
            },
        )
    ]
    assert await repo.load_graph("game-1") == graph


async def test_supabase_graph_repo_missing_rows_raise_filenotfound():
    repo, _ = _repo()

    try:
        await repo.load_graph("missing")
    except FileNotFoundError as e:
        assert str(e)
    else:
        raise AssertionError("expected FileNotFoundError")


async def test_supabase_graph_repo_loads_log_tails_in_chronological_order():
    repo, _ = _repo()

    await repo.append_log_entries(
        "game-1",
        [
            GMLogEntry(id=1, kind="gm", text="첫번째"),
            GMLogEntry(id=2, kind="gm", text="두번째"),
        ],
    )
    await repo.append_history_entries(
        "game-1",
        [
            TurnLogEntry(turn=1, summary="요약 1"),
            TurnLogEntry(turn=2, summary="요약 2"),
        ],
    )
    await repo.append_dialogue_entries(
        "game-1",
        [
            DialoguePair(turn=1, player="p1", narrator="n1"),
            DialoguePair(turn=2, player="p2", narrator="n2"),
        ],
    )

    log_entries = await repo.load_log_entries("game-1")
    history_entries = await repo.load_history_entries("game-1")
    dialogue_entries = await repo.load_dialogue_entries("game-1")

    assert [entry.id for entry in log_entries] == [1, 2]
    assert [entry.summary for entry in history_entries] == ["요약 1", "요약 2"]
    assert [entry.player for entry in dialogue_entries] == ["p1", "p2"]
