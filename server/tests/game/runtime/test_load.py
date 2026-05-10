from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import DialoguePair, GMLogEntry, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime import load_runtime_state


class FakeScenarioRepo:
    def __init__(self) -> None:
        self.records = {
            "locations": {"town": {"id": "town", "name": "마을"}},
            "characters": {"guide": {"id": "guide", "name": "가이드"}},
            "items": {},
            "skills": {},
            "races": {},
            "quests": {},
            "chapters": {},
        }

    async def load_seed_records(self, profile: str, kind: str) -> dict[str, dict]:
        assert profile == "default"
        return self.records[kind]


def _graph() -> Graph:
    return Graph(
        nodes={
            "player": GraphNode(id="player", type="character", properties={}),
            "town": GraphNode(id="town", type="location", properties={}),
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


async def test_load_runtime_state_reads_graph_progress_and_tails(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))
    graph = _graph()
    progress = GameProgress(
        game_id="game-1",
        player_id="player",
        pending_confirmation={
            "id": "confirm-1",
            "kind": "quest_accept",
            "target_id": "quest-1",
        },
        next_log_id=1,
    )

    await repo.save_graph("game-1", graph)
    await repo.save_progress(progress)
    await repo.append_log_entries(
        "game-1",
        [GMLogEntry(id=5, kind="gm", text="도착했습니다.")],
    )
    await repo.append_history_entries(
        "game-1",
        [TurnLogEntry(turn=1, target="town", summary="마을 도착")],
    )
    await repo.append_dialogue_entries(
        "game-1",
        [DialoguePair(turn=1, player="간다", narrator="당신은 이동합니다.")],
    )

    runtime = await load_runtime_state(repo, "game-1")

    assert runtime.graph == graph
    assert runtime.progress.pending_confirmation["kind"] == "quest_accept"
    assert runtime.progress.next_log_id == 6
    assert runtime.log_entries[0].text == "도착했습니다."
    assert runtime.turn_log[0].summary == "마을 도착"
    assert runtime.recent_dialogue[0].player == "간다"


async def test_load_runtime_state_preserves_graph_combat_state(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))
    graph = Graph(
        nodes={
            "player": GraphNode(
                id="player",
                type="character",
                properties={"hp": 10, "max_hp": 10},
            ),
            "rat": GraphNode(
                id="rat",
                type="character",
                properties={"hp": 4, "max_hp": 4},
            ),
            "town": GraphNode(id="town", type="location", properties={}),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
            ),
            "located_at:rat:town": GraphEdge(
                id="located_at:rat:town",
                type="located_at",
                from_node_id="rat",
                to_node_id="town",
            ),
        },
    )
    graph_combat_state = GraphCombatState(
        location_id="town",
        player_id="player",
        enemy_ids=["rat"],
        participant_ids=["player", "rat"],
        sides={"player": "player", "rat": "enemy"},
        round=2,
    )

    await repo.save_graph("game-1", graph)
    await repo.save_progress(
        GameProgress(
            game_id="game-1",
            player_id="player",
            graph_combat_state=graph_combat_state,
        )
    )

    runtime = await load_runtime_state(repo, "game-1")

    assert runtime.progress.graph_combat_state == graph_combat_state


async def test_load_runtime_state_loads_scenario_content_when_profile_is_saved(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))
    graph = Graph(
        nodes={
            "player": GraphNode(
                id="player",
                type="character",
                properties={"source": "runtime", "source_id": "player"},
            ),
            "town": GraphNode(
                id="town",
                type="location",
                properties={"source": "scenario", "source_id": "town"},
            ),
            "guide": GraphNode(
                id="guide",
                type="character",
                properties={"source": "scenario", "source_id": "guide"},
            ),
        },
        edges={},
    )
    await repo.save_graph("game-1", graph)
    await repo.save_progress(
        GameProgress(game_id="game-1", player_id="player", profile_id="default")
    )

    runtime = await load_runtime_state(repo, "game-1", FakeScenarioRepo())

    assert runtime.content.locations["town"]["name"] == "마을"
    assert runtime.content.characters["guide"]["name"] == "가이드"
