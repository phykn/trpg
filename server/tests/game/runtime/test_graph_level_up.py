import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.engines.growth import xp_for_next_level
from src.game.runtime.level_up import GraphLevelUpError, run_graph_level_up
from src.game.runtime.level_up_choices import build_level_up_choices
from src.game.runtime.load import load_runtime_state


class _SkillCandidateLLM:
    def pick_fallback(self, agent):
        return None

    async def chat(self, messages, **kw):
        return {
            "answer": (
                '{"skills":[{"name":"그림자 찌르기","description":"공격 DC를 낮춘다.",'
                '"action":"attack","effect_template":"dc_down","support_bonus":2,'
                '"mp_cost":2,"tags":["stealth","attack"]}]}'
            ),
            "think": None,
        }


def _player(*, xp_pool: int | None = None) -> GraphNode:
    level = 1
    stats = {"body": 10, "agility": 10, "mind": 10, "presence": 10}
    return GraphNode(
        id="player_01",
        type="character",
        properties={
            "name": "테스터",
            "level": level,
            "xp_pool": xp_for_next_level(level) if xp_pool is None else xp_pool,
            "gold": 0,
            "hp": 5,
            "max_hp": 5,
            "mp": 5,
            "max_mp": 5,
            "alive": True,
            "stats": stats,
            "status": [],
        },
    )


async def _repo(
    tmp_path,
    *,
    xp_pool: int | None = None,
    known_skill: bool = False,
) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    edges = {}
    if known_skill:
        edges["knows_skill:learned:player_01:fireball"] = GraphEdge(
            id="knows_skill:learned:player_01:fireball",
            type="knows_skill",
            from_node_id="player_01",
            to_node_id="fireball",
            properties={"source": "learned", "tier": 1},
        )
    await repo.save_graph(
        "game-1",
        Graph(
            nodes={
                "player_01": _player(xp_pool=xp_pool),
                "fireball": GraphNode(
                    id="fireball",
                    type="skill",
                    properties={"name": "화염구", "action": "attack"},
                ),
            },
            edges=edges,
        ),
    )
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


async def test_run_graph_level_up_consumes_current_level_xp_and_raises_hp(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_level_up(repo, "game-1", growth={"kind": "max_hp"})
    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    saved_logs = await repo.load_log_entries("game-1")
    player = saved_graph.nodes["player_01"].properties

    assert player["level"] == 2
    assert player["xp_pool"] == 0
    assert player["max_hp"] == 6
    assert player["hp"] == 6
    assert saved_progress.next_log_id == 2
    assert len(saved_logs) == 1
    assert saved_logs[0].kind == "act"
    assert (
        saved_logs[0].text
        == "테스터의 레벨이 올랐습니다 (레벨 2, 최대 HP +1, HP 6 / MP 5)."
    )
    assert result.front_state.hero.level == 2
    assert result.front_state.hero.exp == 0
    assert result.front_state.log == saved_logs


async def test_run_graph_level_up_can_learn_selected_skill(tmp_path):
    repo = await _repo(tmp_path)

    await run_graph_level_up(
        repo,
        "game-1",
        growth={"kind": "learn_skill", "skill_id": "fireball"},
    )
    saved_graph = await repo.load_graph("game-1")
    saved_logs = await repo.load_log_entries("game-1")

    edge = saved_graph.edges["knows_skill:learned:player_01:fireball"]
    assert edge == GraphEdge(
        id="knows_skill:learned:player_01:fireball",
        type="knows_skill",
        from_node_id="player_01",
        to_node_id="fireball",
        properties={"source": "learned", "tier": 1},
    )
    assert saved_logs[0].kind == "act"
    assert "화염구 습득" in saved_logs[0].text


async def test_run_graph_level_up_can_upgrade_known_skill(tmp_path):
    repo = await _repo(tmp_path, known_skill=True)

    await run_graph_level_up(
        repo,
        "game-1",
        growth={"kind": "upgrade_skill", "skill_id": "fireball"},
    )
    saved_graph = await repo.load_graph("game-1")
    saved_logs = await repo.load_log_entries("game-1")

    edge = saved_graph.edges["knows_skill:learned:player_01:fireball"]
    assert edge.properties["tier"] == 2
    assert "화염구 강화" in saved_logs[0].text


async def test_level_up_options_include_llm_skill_candidate(tmp_path):
    repo = await _repo(tmp_path)
    runtime = await load_runtime_state(repo, "game-1")

    choices = await build_level_up_choices(runtime, llm=_SkillCandidateLLM())

    learn = next(choice for choice in choices if choice["id"].startswith("learn_skill:"))
    assert learn["label"] == "그림자 찌르기 습득"
    assert learn["growth"]["kind"] == "learn_skill"
    assert learn["growth"]["skill"]["effect_template"] == "dc_down"
    assert learn["growth"]["skill"]["mp_cost"] == 2


async def test_run_graph_level_up_can_learn_generated_skill(tmp_path):
    repo = await _repo(tmp_path)
    runtime = await load_runtime_state(repo, "game-1")
    choices = await build_level_up_choices(runtime, llm=_SkillCandidateLLM())
    growth = next(
        choice["growth"]
        for choice in choices
        if choice["id"].startswith("learn_skill:")
    )

    await run_graph_level_up(repo, "game-1", growth=growth)
    saved_graph = await repo.load_graph("game-1")
    skill_id = growth["skill_id"]

    assert saved_graph.nodes[skill_id].type == "skill"
    assert saved_graph.nodes[skill_id].properties["name"] == "그림자 찌르기"
    assert saved_graph.edges[f"knows_skill:learned:player_01:{skill_id}"].properties[
        "tier"
    ] == 1


async def test_run_graph_level_up_rejects_insufficient_xp_without_saving(tmp_path):
    repo = await _repo(tmp_path, xp_pool=0)

    with pytest.raises(GraphLevelUpError, match="not enough xp"):
        await run_graph_level_up(repo, "game-1", growth={"kind": "max_hp"})

    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    saved_logs = await repo.load_log_entries("game-1")
    assert saved_graph.nodes["player_01"].properties["level"] == 1
    assert saved_progress.next_log_id == 1
    assert saved_logs == []
