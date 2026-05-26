import json

from src.db.graph.local_fs import LocalFsGraphRepo
from src.db.scenario.local_fs import LocalFsScenarioRepo
from src.game.runtime.flow.session import initialize_graph_session
from src.game.runtime.load import load_runtime_state


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


async def test_generated_session_init_saves_profile_and_reload_contract(tmp_path):
    scenario_root = tmp_path / "scenarios"
    profile = scenario_root / "white_isle_llm"
    profile.mkdir(parents=True)
    _write_json(
        profile / "contract.json",
        {
            "id": "white_isle_llm",
            "world": {"title": "흰섬", "locale": "ko"},
            "fixed": [],
            "forbid": [],
            "tone": {"register": "합니다체", "person": "second"},
            "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
            "allowed_ops": ["add_memory", "add_clue"],
            "stability_defaults": {
                "add_memory": "campaign",
                "add_clue": "scene",
            },
        },
    )
    _write_json(
        profile / "profile.json",
        {
            "id": "white_isle_llm",
            "name": "흰섬 LLM",
            "description": "실험 시나리오입니다.",
        },
    )
    _write_json(
        profile / "races.json",
        [
            {
                "id": "traveler",
                "name": "여행자",
                "description": "안개 바다를 건너는 사람입니다.",
                "playable": True,
            }
        ],
    )
    graph_repo = LocalFsGraphRepo(str(tmp_path / "graph"))
    scenario_repo = LocalFsScenarioRepo(str(scenario_root))

    result = await initialize_graph_session(
        "white_isle_llm",
        {"name": "테스터", "race_id": "traveler", "gender": "female"},
        graph_repo,
        scenario_repo,
        locale="ko",
    )

    assert result.front_state.hero.id == "player_01"
    assert result.front_state.place is not None
    assert result.front_state.place.id == "loc_fog_harbor"
    saved_progress = await graph_repo.load_progress(result.game_id)
    assert saved_progress.profile_id == "white_isle_llm"

    reloaded = await load_runtime_state(
        graph_repo,
        result.game_id,
        scenario_repo,
    )

    assert reloaded.story_contract is not None
    assert reloaded.story_contract.id == "white_isle_llm"
