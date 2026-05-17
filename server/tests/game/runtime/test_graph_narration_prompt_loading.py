import pytest

from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.flow.input import run_graph_input_turn
from src.game.runtime.flow.intro import run_graph_initial_narration
from src.game.runtime.narration.context import (
    build_input_narration_payload,
    build_intro_narration_payload,
)
from src.game.runtime.state import GameRuntimeState
from src.game.runtime.flow.turn import run_graph_action_turn
from src.llm.calls.runner import get_prompt


class _PromptCaptureLLM:
    def __init__(self, payload=None) -> None:
        self.payload = payload or {
            "actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]
        }
        self.calls: list[dict] = []

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.calls.append(
            {"agent": agent, "messages": messages, "temperature": temperature}
        )
        if agent == "classify":
            import json

            return {"answer": json.dumps(self.payload), "think": ""}
        return {"answer": "짧은 나레이션입니다.", "think": ""}


def _character(node_id: str, *, hp: int = 30) -> GraphNode:
    return GraphNode(
        id=node_id,
        type="character",
        properties={
            "name": node_id,
            "hp": hp,
            "max_hp": 30,
            "mp": 10,
            "max_mp": 10,
            "stats": {"body": 10, "agility": 10, "mind": 10, "presence": 10},
            "status": [],
        },
    )


def _graph() -> Graph:
    return Graph(
        nodes={
            "town": GraphNode(
                id="town",
                type="location",
                properties={
                    "name": "Town",
                    "description": "A quiet place.",
                    "mood": "quiet but procedural",
                    "traits": ["safe", "orderly"],
                },
            ),
            "player_01": _character("player_01"),
            "goblin_01": GraphNode(
                id="goblin_01",
                type="character",
                properties={
                    **_character("goblin_01", hp=8).properties,
                    "personality": ["dry", "watchful"],
                    "personal_boundary": "deflects personal questions politely",
                    "secrets": ["secretly enjoys practical jokes"],
                    "traits": ["can speak", "does not rush"],
                },
            ),
            "dry_report_style": GraphNode(
                id="dry_report_style",
                type="dialogue_style",
                properties={
                    "name": "Dry report style",
                    "speech_style": "short report-like replies",
                    "humor_style": "treats jokes as report categories",
                    "traits": ["dry delivery"],
                },
            ),
            "marker_01": GraphNode(
                id="marker_01",
                type="item",
                properties={
                    "name": "Marker",
                    "description": "A small floor marker.",
                    "traits": ["flat", "interactive"],
                },
            ),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
            "located_at:goblin_01:town": GraphEdge(
                id="located_at:goblin_01:town",
                type="located_at",
                from_node_id="goblin_01",
                to_node_id="town",
            ),
            "uses_dialogue_style:goblin_01:dry_report_style": GraphEdge(
                id="uses_dialogue_style:goblin_01:dry_report_style",
                type="uses_dialogue_style",
                from_node_id="goblin_01",
                to_node_id="dry_report_style",
            ),
            "located_at:marker_01:town": GraphEdge(
                id="located_at:marker_01:town",
                type="located_at",
                from_node_id="marker_01",
                to_node_id="town",
            ),
        },
    )


async def _repo(tmp_path) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph("game-1", _graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


def test_graph_narration_prompt_files_are_packaged():
    assert get_prompt("graph_intro", "ko")
    assert get_prompt("graph_narrate", "ko")
    assert get_prompt("combat_narrate", "ko")


def test_graph_narration_prompts_encode_style_without_source_title():
    intro_prompt = get_prompt("graph_intro", "ko")
    narrate_prompt = get_prompt("graph_narrate", "ko")
    combat_prompt = get_prompt("combat_narrate", "ko")
    combined = f"{intro_prompt}\n{narrate_prompt}\n{combat_prompt}"

    assert "문체 목표" in intro_prompt
    assert "본문 문체" in narrate_prompt
    assert "감각" in combined
    assert "선택" in combined
    assert "플레이어의 팬인 GM" in combined
    assert "플레이어를 우습게 만들지" in combined
    assert "결과 라벨" in combat_prompt
    assert "이번 교환은 성공적으로 이루어졌습니다" in combat_prompt
    assert "선택하지 않은 행동" in intro_prompt
    assert "금지 예" in intro_prompt
    assert "좋은 예" in combined
    assert "한자" in combined
    assert "문장 수와 길이를 엄격히 고정하지 않지만" in intro_prompt
    assert "장황하게 설명하지 않습니다" in narrate_prompt
    assert "「」" in narrate_prompt
    assert "직접 발화" in narrate_prompt
    assert "NPC 직접 발화" in narrate_prompt
    assert "짧은 반응으로만" not in narrate_prompt
    assert "짧은 말" not in narrate_prompt
    assert "당신의 새 대사" not in narrate_prompt
    assert "payload.combat_view" in narrate_prompt
    assert "tone.lethality" in narrate_prompt
    assert "STATE_PATCH" in narrate_prompt
    assert "GraphChange" in narrate_prompt
    assert "USER_STREAM" in narrate_prompt
    assert "판정 결과 장면화" in narrate_prompt
    assert "payload에 없는 단서" in narrate_prompt
    assert "실패여도 장면은 멈추지 않습니다" in narrate_prompt
    assert "기척이 선명해집니다" in narrate_prompt
    assert "물건의 상태" in narrate_prompt
    assert "mbti" in narrate_prompt
    assert "boundary_style" in narrate_prompt
    assert "speech_style" in narrate_prompt
    assert "traits" in narrate_prompt
    assert "판정 후 나레이션" in narrate_prompt
    assert "preroll_narration" in narrate_prompt
    assert "판정 전 문장을 반복하지 않습니다" in narrate_prompt
    assert "본문을 두 번 쓰지 않습니다" in narrate_prompt
    assert "조사 실패" in narrate_prompt
    assert "대화 실패" in narrate_prompt
    assert "실패이면 LLM이 장면을 씁니다" in narrate_prompt
    assert "성공처럼 읽히는 단서 획득" in narrate_prompt
    assert "payload.current_event.kind`가 `roll_prompt`" in narrate_prompt
    assert "발견해냈습니다" in narrate_prompt
    assert "포착해냅니다" in narrate_prompt
    assert "secrets" in narrate_prompt
    assert "여러 개일 수 있으므로" in narrate_prompt
    assert "개인적인 내용을 캐면" in narrate_prompt
    assert "faction" in narrate_prompt
    assert "새로운 소속, 명령, 관계 변화는 만들지 않습니다" in narrate_prompt
    assert "dialogue_style" not in narrate_prompt
    assert "character-specific" not in narrate_prompt
    assert "게임 밖 요청" in narrate_prompt
    assert "그대로 출력하지 않습니다" in narrate_prompt
    assert "combat_view.effect" in narrate_prompt
    assert "지원 효과 이름, 원리, 추가 효과를 지어내지 않습니다" in narrate_prompt
    assert "combat_view.statuses" in narrate_prompt
    assert "상태 효과 이름, 원리, 추가 효과를 지어내지 않습니다" in narrate_prompt
    assert "STATE_PATCH" in intro_prompt
    assert "제공된 성격" in intro_prompt
    assert "훈련, 점검, 안내" not in intro_prompt
    assert "추상적인 분위기만 쓰지 말고" in intro_prompt
    assert "STATE_PATCH" in combat_prompt
    assert "훈련 충격" in combat_prompt
    assert "recent_narration" in combat_prompt
    assert "행동 요약" in combat_prompt
    assert "결과 카드와 같은 문장으로 시작하지 않습니다" in combat_prompt
    assert "전투가 끝났으면" in combat_prompt
    assert "다음 공격이나 다음 틈을 유도하지 않습니다" in combat_prompt
    assert "전투 시작" in combat_prompt
    assert "아직 명중하지 않았습니다" in combat_prompt
    assert "1~2문장" not in combined
    assert "2~3문장" not in combined
    assert "한 문장" not in intro_prompt
    assert "Baldur" not in combined
    assert "발더" not in combined
    assert "발게" not in combined


@pytest.mark.asyncio
async def test_graph_intro_payload_exposes_scene_and_actor_traits(tmp_path):
    repo = await _repo(tmp_path)
    runtime = GameRuntimeState(
        graph=await repo.load_graph("game-1"),
        progress=await repo.load_progress("game-1"),
    )

    payload = build_intro_narration_payload(runtime)

    assert payload["place"]["mood"] == "quiet but procedural"
    assert payload["place"]["traits"] == ["safe", "orderly"]
    assert "speech_style" not in payload["visible_targets"][0]
    assert payload["visible_targets"][0]["dialogue_style"]["speech_style"] == (
        "short report-like replies"
    )
    assert payload["visible_targets"][0]["personality"] == ["dry", "watchful"]
    assert payload["visible_items"][0]["traits"] == ["flat", "interactive"]


@pytest.mark.asyncio
async def test_graph_input_payload_exposes_target_traits(tmp_path):
    repo = await _repo(tmp_path)
    runtime = GameRuntimeState(
        graph=await repo.load_graph("game-1"),
        progress=await repo.load_progress("game-1"),
    )
    target = runtime.graph.nodes["goblin_01"]

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="고블린에게 농담을 건넨다",
        action=Action(verb="speak", what="goblin_01"),
        dialogue_target=target,
    )

    assert payload["target_view"]["personality"] == ["dry", "watchful"]
    assert "speech_style" not in payload["target_view"]
    assert "humor_style" not in payload["target_view"]
    assert payload["target_view"]["dialogue_style"]["speech_style"] == (
        "short report-like replies"
    )
    assert payload["target_view"]["dialogue_style"]["humor_style"] == (
        "treats jokes as report categories"
    )
    assert payload["target_view"]["personal_boundary"] == (
        "deflects personal questions politely"
    )
    assert payload["target_view"]["secrets"] == ["secretly enjoys practical jokes"]
    assert payload["target_view"]["traits"] == ["can speak", "does not rush"]


def test_graph_narration_runtime_preserves_llm_text():
    from src.game.runtime.flow.intro import _clean_intro_text

    long_text = "  긴 문장입니다.\n\n" + ("가" * 450)

    assert _clean_intro_text(long_text) == long_text


@pytest.mark.asyncio
async def test_graph_intro_uses_packaged_prompt(monkeypatch, tmp_path):
    import src.game.runtime.flow.intro as intro_module

    monkeypatch.setattr(
        intro_module, "get_prompt", lambda agent, locale: f"{agent}:{locale}"
    )
    repo = await _repo(tmp_path)
    runtime = GameRuntimeState(
        graph=await repo.load_graph("game-1"),
        progress=await repo.load_progress("game-1"),
    )
    llm = _PromptCaptureLLM()

    await run_graph_initial_narration(llm, repo, runtime)  # type: ignore[arg-type]

    assert llm.calls[-1]["messages"][0]["content"] == "graph_intro:ko"


@pytest.mark.asyncio
async def test_graph_intro_sends_rich_first_scene_payload(tmp_path):
    import json
    import src.game.runtime.flow.intro as intro_module

    repo = await _repo(tmp_path)
    runtime = GameRuntimeState(
        graph=await repo.load_graph("game-1"),
        progress=await repo.load_progress("game-1"),
    )
    llm = _PromptCaptureLLM()

    await intro_module.run_graph_initial_narration(llm, repo, runtime)  # type: ignore[arg-type]

    payload = json.loads(llm.calls[-1]["messages"][1]["content"])
    assert "player" in payload
    assert "place" in payload
    assert "visible_targets" in payload
    assert "exits" in payload
    assert "inventory" in payload


@pytest.mark.asyncio
async def test_graph_turn_narration_uses_packaged_prompt(monkeypatch, tmp_path):
    import src.game.runtime.narration.action as action_narration

    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 20)
    monkeypatch.setattr(
        action_narration, "get_prompt", lambda agent, locale: f"{agent}:{locale}"
    )
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "graph_combat_state": GraphCombatState(
                    location_id="town",
                    player_id="player_01",
                    enemy_ids=["goblin_01"],
                    participant_ids=["player_01", "goblin_01"],
                    sides={"player_01": "player", "goblin_01": "enemy"},
                    round=3,
                )
            }
        )
    )
    llm = _PromptCaptureLLM()

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
        llm=llm,  # type: ignore[arg-type]
    )

    call = [call for call in llm.calls if call["agent"] == "combat_narrate"][0]

    assert call["messages"][0]["content"] == "combat_narrate:ko"
    assert call["temperature"] == 1.0


@pytest.mark.asyncio
async def test_graph_input_narration_uses_packaged_prompt(monkeypatch, tmp_path):
    import src.game.runtime.narration.input as input_narration

    monkeypatch.setattr(
        input_narration, "get_prompt", lambda agent, locale: f"{agent}:{locale}"
    )
    repo = await _repo(tmp_path)
    llm = _PromptCaptureLLM()

    await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")  # type: ignore[arg-type]

    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    assert narrate_call["messages"][0]["content"] == "graph_narrate:ko"
    assert narrate_call["temperature"] == 1.0
