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
    profile = scenario_root / "white_isle"
    profile.mkdir(parents=True)
    _write_json(
        profile / "contract.json",
        {
            "id": "white_isle",
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
            "id": "white_isle",
            "name": "흰섬",
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
        "white_isle",
        {"name": "테스터", "race_id": "traveler", "gender": "female"},
        graph_repo,
        scenario_repo,
        locale="ko",
    )

    assert result.front_state.hero.id == "player_01"
    assert result.front_state.place is not None
    assert result.front_state.place.id == "loc_fog_harbor"
    saved_progress = await graph_repo.load_progress(result.game_id)
    assert saved_progress.profile_id == "white_isle"

    reloaded = await load_runtime_state(
        graph_repo,
        result.game_id,
        scenario_repo,
    )

    assert reloaded.story_contract is not None
    assert reloaded.story_contract.id == "white_isle"


async def test_contract_profile_with_seed_starts_from_seed_graph(tmp_path):
    scenario_root = tmp_path / "scenarios"
    profile = scenario_root / "white_isle"
    profile.mkdir(parents=True)
    _write_json(
        profile / "profile.json",
        {
            "id": "white_isle",
            "name": "흰섬",
            "description": "흰섬 독립 생성형 시나리오",
            "mode": "generated",
        },
    )
    _write_json(
        profile / "contract.json",
        {
            "id": "white_isle",
            "world": {"title": "흰섬", "locale": "ko"},
            "fixed": ["마지막 도착지는 흰섬입니다."],
            "forbid": ["흰섬의 결말을 조기 공개하지 않습니다."],
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
        profile / "races.json",
        {
            "human": {
                "id": "human",
                "name": "인간",
                "description": "안개 바다를 건너는 사람입니다.",
                "racial_skills": [],
            }
        },
    )
    _write_json(
        profile / "locations.json",
        {
            "loc_fog_harbor": {
                "id": "loc_fog_harbor",
                "name": "안개 항구",
                "description": "젖은 명부가 놓인 선착장입니다.",
                "connections": [],
            }
        },
    )
    _write_json(
        profile / "characters.json",
        {
            "npc_olden": {
                "id": "npc_olden",
                "race": "human",
                "gender": "male",
                "name": "올든",
                "role": "출항 명부를 지키는 항구 관리인",
                "level": 1,
                "alive": True,
                "location": "loc_fog_harbor",
                "inventory": [],
                "equipment": {},
                "gold": 0,
                "learned_skills": [],
                "relations": {"player_01": 0},
                "xp_reward": 0,
                "active_buffs": [],
                "memories": [],
            }
        },
    )
    _write_json(
        profile / "quests.json",
        {
            "q_fog_ready": {
                "id": "q_fog_ready",
                "title": "출항 준비",
                "description": "흰섬으로 향할 준비를 확인합니다.",
                "giver": "npc_olden",
                "triggers": [
                    {
                        "id": "enter_fog_harbor",
                        "type": "location_enter",
                        "target": "loc_fog_harbor",
                    }
                ],
                "fail_triggers": [],
                "prerequisites": [],
                "status": "active",
                "required": True,
                "rewards": {"gold": 0, "exp": 0, "items": []},
            }
        },
    )
    _write_json(
        profile / "chapters.json",
        {
            "chapter_fog_harbor": {
                "id": "chapter_fog_harbor",
                "title": "안개 항구",
                "description": "흰섬으로 떠나기 전 항구의 조건을 확인합니다.",
                "quests": ["q_fog_ready"],
                "prerequisites": [],
                "status": "active",
            }
        },
    )
    _write_json(
        profile / "start.json",
        {
            "start_location": "loc_fog_harbor",
            "active_subject": "npc_olden",
            "active_quest": "q_fog_ready",
            "intro_text": "젖은 출항 명부가 선착장 난간에 눌려 있습니다.",
        },
    )
    _write_json(
        profile / "player.json",
        {"id": "player_01", "equipment": {}, "inventory": [], "gold": 0, "xp_pool": 0},
    )
    (profile / "world.md").write_text("흰섬 고정 메인 스토리", encoding="utf-8")
    graph_repo = LocalFsGraphRepo(str(tmp_path / "graph"))
    scenario_repo = LocalFsScenarioRepo(str(scenario_root))

    result = await initialize_graph_session(
        "white_isle",
        {"name": "테스터", "race_id": "human", "gender": "female"},
        graph_repo,
        scenario_repo,
        locale="ko",
    )

    graph = await graph_repo.load_graph(result.game_id)
    progress = await graph_repo.load_progress(result.game_id)
    reloaded = await load_runtime_state(graph_repo, result.game_id, scenario_repo)

    assert "npc_olden" in graph.nodes
    assert "q_fog_ready" in graph.nodes
    assert result.front_state.place is not None
    assert result.front_state.place.id == "loc_fog_harbor"
    assert progress.active_subject_id == "npc_olden"
    assert progress.active_quest_id == "q_fog_ready"
    assert reloaded.story_contract is not None
    assert reloaded.story_contract.id == "white_isle"
