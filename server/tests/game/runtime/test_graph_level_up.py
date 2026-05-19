import json

import pytest

from src.game.domain.content import RuntimeContent
from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.engines.growth import xp_for_next_level
from src.game.runtime.flow.level_up import GraphLevelUpError, run_graph_level_up
from src.game.runtime.flow.level_up_choices import build_level_up_choices
from src.game.runtime.load import load_runtime_state


class _SkillCandidateLLM:
    def __init__(self):
        self.calls = []

    def pick_fallback(self, agent):
        return None

    async def chat(self, messages, **kw):
        self.calls.append({"messages": messages, **kw})
        return {
            "answer": (
                '{"skills":[{"name":"그림자 찌르기",'
                '"description":"공격 흐름을 잡을 때 판정을 보조합니다."}]}'
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
        == "당신의 레벨이 올랐습니다 (레벨 2, 최대 HP +1, HP 6 / MP 5)."
    )
    assert result.front_state.hero.level == 2
    assert result.front_state.hero.exp == 0
    assert result.front_state.log == saved_logs


async def test_run_graph_level_up_can_raise_stat(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_level_up(
        repo,
        "game-1",
        growth={"kind": "stat", "stat": "presence"},
    )
    saved_graph = await repo.load_graph("game-1")
    saved_logs = await repo.load_log_entries("game-1")
    player = saved_graph.nodes["player_01"].properties

    assert player["level"] == 2
    assert player["xp_pool"] == 0
    assert player["stats"]["presence"] == 11
    assert "매력 +1" in saved_logs[0].text
    assert result.front_state.hero.stats["presence"] == 11


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


async def test_level_up_upgrade_uses_runtime_content_skill_name(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph(
        "game-1",
        Graph(
            nodes={
                "player_01": _player(),
                "training_strike": GraphNode(
                    id="training_strike",
                    type="skill",
                    properties={
                        "source": "scenario",
                        "source_id": "training_strike",
                        "action": "attack",
                    },
                ),
            },
            edges={
                "knows_skill:learned:player_01:training_strike": GraphEdge(
                    id="knows_skill:learned:player_01:training_strike",
                    type="knows_skill",
                    from_node_id="player_01",
                    to_node_id="training_strike",
                    properties={"source": "learned", "tier": 1},
                )
            },
        ),
    )
    await repo.save_progress(
        GameProgress(
            game_id="game-1",
            player_id="player_01",
            runtime_content=RuntimeContent(
                skills={
                    "training_strike": {
                        "id": "training_strike",
                        "name": "훈련 일격",
                    }
                }
            ),
        )
    )
    runtime = await load_runtime_state(repo, "game-1")

    choices = await build_level_up_choices(runtime, llm=None)
    upgrade = next(choice for choice in choices if choice["id"].startswith("upgrade_skill:"))

    assert upgrade["label"] == "훈련 일격 강화"

    await run_graph_level_up(
        repo,
        "game-1",
        growth={"kind": "upgrade_skill", "skill_id": "training_strike"},
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert "훈련 일격 강화" in saved_logs[0].text


async def test_level_up_options_include_llm_skill_candidate(tmp_path):
    repo = await _repo(tmp_path)
    runtime = await load_runtime_state(repo, "game-1")
    llm = _SkillCandidateLLM()

    choices = await build_level_up_choices(runtime, llm=llm)

    learn = next(
        choice for choice in choices if choice["id"].startswith("learn_skill:")
    )
    assert learn["label"] == "그림자 찌르기 습득"
    assert learn["growth"]["kind"] == "learn_skill"
    assert learn["growth"]["skill"]["bonus"] == 2
    assert learn["growth"]["skill"]["mp_cost"] == 2
    assert (
        json.loads(llm.calls[0]["messages"][1]["content"])["skills"][0][
            "action"
        ]
        == "attack"
    )
    assert "bonus" not in json.loads(llm.calls[0]["messages"][1]["content"])["skills"][0]
    assert llm.calls[0]["agent"] == "recommend"


async def test_level_up_options_include_all_growth_choices(tmp_path):
    repo = await _repo(tmp_path, known_skill=True)
    runtime = await load_runtime_state(repo, "game-1")

    choices = await build_level_up_choices(runtime, llm=_SkillCandidateLLM())

    assert {choice["id"] for choice in choices} >= {
        "max_hp",
        "max_mp",
        "stat:body",
        "stat:agility",
        "stat:mind",
        "stat:presence",
    }
    assert any(
        choice["id"].startswith(("upgrade_skill:", "learn_skill:"))
        for choice in choices
    )


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
    assert (
        saved_graph.edges[f"knows_skill:learned:player_01:{skill_id}"].properties[
            "tier"
        ]
        == 1
    )


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
