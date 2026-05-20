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
    assert get_prompt("classify", "ko")
    assert get_prompt("recommend", "ko")
    assert get_prompt("recommend", "en")


def test_graph_narration_prompts_encode_style_without_source_title():
    intro_prompt = get_prompt("graph_intro", "ko")
    narrate_prompt = get_prompt("graph_narrate", "ko")
    combat_prompt = get_prompt("combat_narrate", "ko")
    classify_prompt = get_prompt("classify", "ko")
    recommend_prompt = get_prompt("recommend", "ko")
    recommend_en_prompt = get_prompt("recommend", "en")
    combined = f"{intro_prompt}\n{narrate_prompt}\n{combat_prompt}"

    assert "문체 목표" in intro_prompt
    assert "본문 문체" in narrate_prompt
    assert "감각" in combined
    assert "선택" in combined
    assert "장면을 쓰는 에이전트는 같은 기본 리듬을 따릅니다" in combined
    assert "첫 장소 소개는 같은 리듬으로 씁니다" in intro_prompt
    assert "가장 압력이 큰 대상이나 물건 하나" in intro_prompt
    assert "일반 행동은 같은 리듬으로 씁니다" in narrate_prompt
    assert "플레이어의 선택이나 시도가 보입니다" in narrate_prompt
    assert "확정된 결과가 보입니다" in narrate_prompt
    assert "남은 거리, 물건 상태, NPC 반응, 다음 목표" in narrate_prompt
    assert "## 처리 라우터" in narrate_prompt
    assert "출력 전에 이번 턴의 주 처리 유형을 하나만 고릅니다" in narrate_prompt
    assert "`payload.current_event.outcome`이 `action_rejected`이면 행동 거부" in narrate_prompt
    assert "`payload.combat_view`가 있으면 전투" in narrate_prompt
    assert "`payload.current_event.kind`가 `roll_prompt`이면 판정 전" in narrate_prompt
    assert "선택한 처리 유형의 규칙을 가장 우선합니다" in narrate_prompt
    assert "다른 섹션의 규칙은 사실 범위, 문체, 반복 회피에만 참고합니다" in narrate_prompt
    assert "전투 모드에서는 대화, 조사, 퀘스트 규칙보다" in narrate_prompt
    assert "`combat_view.exchange_result`, `combat_view.player_action`, `combat_view.outcome`" in narrate_prompt
    assert "전투 결과를 일반 행동 성공/실패처럼 해석하지 않습니다" in narrate_prompt
    assert "전투에서 `defend`/`guarded`의 success는 공격 성공이 아니라 방어 성공입니다" in narrate_prompt
    assert "전투에서 `flee`/`create_distance`의 success는 피해가 아니라 거리 확보나 이탈 성공입니다" in narrate_prompt
    assert "전투에서 `talk`의 success는 설득 확정이 아니라 압박 완화나 흐름 흔들림입니다" in narrate_prompt
    assert "`ui_cues`와 `suggestions`의 기본값은 빈 배열입니다" in narrate_prompt
    assert "suggestions는 새 행동을 창작하는 기능이 아닙니다" in narrate_prompt
    assert "payload에 이미 드러난 대상, 장소, 물건, 목표를 플레이어 입력문으로 바꾸는 기능입니다" in narrate_prompt
    assert "payload.scene_anchor.visible_names에 명시된 대상과 장소는 제안할 수 있습니다" in narrate_prompt
    assert "현재 목표가 바로 보이면 목표를 수행하는 입력문을 제안할 수 있습니다" in narrate_prompt
    assert "`대화 시도하기`, `상황 파악하기`처럼 대상이나 목적이 없는 label은 쓰지 않습니다" in narrate_prompt
    assert "손맛" in narrate_prompt
    assert "손끝에 먼지만 묻어납니다" in narrate_prompt
    assert "플레이어의 팬인 GM" in combined
    assert "플레이어를 우습게 만들지" in combined
    assert "결과 라벨" in combat_prompt
    assert "payload.combat_view.player_action" in combat_prompt
    assert "판정을 다시 해석하지 않고" in combat_prompt
    assert "조금 과장해서 씁니다" in combat_prompt
    assert "결과는 즉시 이해되고" in combat_prompt
    assert "모든 전투 행동은 같은 리듬으로 씁니다" in combat_prompt
    assert "선택한 행동이 보입니다" in combat_prompt
    assert "같은 의미의 물리적 장면으로 바꿔도 됩니다" in combat_prompt
    assert "성공이면 먹힘, 뚫림, 밀어냄" in combat_prompt
    assert "중립이면 대치, 거리, 자세" in combat_prompt
    assert "사용할 수 있는 감각" in combat_prompt
    assert "## 대사" in combat_prompt
    assert "필요할 때만 짧은 직접 발화 하나를 섞습니다" in combat_prompt
    assert "직접 발화는 `「」`로 감쌉니다" in combat_prompt
    assert "대사는 감탄사가 아니라 반응, 각오, 경고, 숨 고르기" in combat_prompt
    assert "대사가 장면의 속도를 떨어뜨리면 넣지 않습니다" in combat_prompt
    assert "「지금 밀어붙입니다.」" in combat_prompt
    assert "「다시 잡겠습니다.」" in combat_prompt
    assert "「여기서 받아냅니다.」" in combat_prompt
    assert "「거리를 벌립니다.」" in combat_prompt
    assert "「그 정도론 안 밀립니다.」" in combat_prompt
    assert "「큭, 막혔습니다.」" not in combat_prompt
    assert "말할 수 없는 대상은 대사하지 않습니다" in combat_prompt
    assert "대사로 새 정보, 속마음, 항복, 승리, 패배, 약속을 만들지 않습니다" in combat_prompt
    assert "exchange_result별 작성 기준" in combat_prompt
    assert "failure:" in combat_prompt
    assert "neutral:" in combat_prompt
    assert "player_action별 초점" in combat_prompt
    assert "attack, precise, reckless" in combat_prompt
    assert "defend, guarded" in combat_prompt
    assert "success는 공격 성공이 아니라 방어 성공입니다" in combat_prompt
    assert "flee, create_distance" in combat_prompt
    assert "success는 피해를 주는 것이 아니라 거리를 벌리거나 전투 흐름에서 빠져나오는 것입니다" in combat_prompt
    assert "talk:" in combat_prompt
    assert "success는 설득 성공이 아니라 전투 압박을 늦추거나 흐름을 흔든 것입니다" in combat_prompt
    assert "전투를 더 이어가지 않고" in combat_prompt
    assert (
        "victory, defeat, fled, escaped, surrendered, combat_stopped, ongoing"
        in combat_prompt
    )
    assert "victory, defeat, flee, stop" not in combat_prompt
    assert "직전 GM 나레이션" in combat_prompt
    assert "직전과 다른 초점을 고릅니다" in combat_prompt
    assert "직전과 같은 직접 발화나 같은 감탄사를 반복하지 않습니다" in combat_prompt
    assert "허수아비" not in combat_prompt
    assert "결과 라벨 대신 맞음, 막힘, 빗나감" in combat_prompt
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
    assert "critical_success" in narrate_prompt
    assert "다음 행동 가능성" in narrate_prompt
    assert "본문을 두 번 쓰지 않습니다" in narrate_prompt
    assert "조사 실패" in narrate_prompt
    assert "대화 실패" in narrate_prompt
    assert "실패이면 LLM이 장면을 씁니다" in narrate_prompt
    assert "성공처럼 읽히는 단서 획득" in narrate_prompt
    assert "payload.current_event.kind`가 `roll_prompt`" in narrate_prompt
    assert "발견해냈습니다" in narrate_prompt
    assert "포착해냅니다" in narrate_prompt
    assert "개인적인 내용을 캐면" in narrate_prompt
    assert "최근에 같은 NPC가 이미 말한 직접 발화를 그대로 다시 쓰지 않습니다" in narrate_prompt
    assert "자연스러운 한국어 구어" in narrate_prompt
    assert "빈 직접 발화" in narrate_prompt
    assert "플레이어 원문이 단순히 말을 건다는 뜻이면" in narrate_prompt
    assert "무슨 일이신가요" in narrate_prompt
    assert "현재 장소의 visible targets" in narrate_prompt
    assert "이전 기억에 있어도 현재 주변에 있다고 쓰지 않습니다" in narrate_prompt
    assert "현재 목표와 다음 행동" in narrate_prompt
    assert "새로운 여정" in narrate_prompt
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
    assert "`label`은 칩에 보이는 짧은 목적입니다" in narrate_prompt
    assert "`input_text`는 그대로 전송해도 자연스러운 플레이어 입력문입니다" in narrate_prompt
    assert "UI 라벨, 명사구, 시스템 명령이 아니라" in narrate_prompt
    assert "기록 보관실로 이동합니다." in narrate_prompt
    assert "봉인 표식을 자세히 살펴봅니다." in narrate_prompt
    assert "낡은 열쇠로 잠긴 서랍을 열어 봅니다." in narrate_prompt
    assert "거리를 벌리며 방어 자세를 잡습니다." in narrate_prompt
    assert "루카에게 기록 보관실 조사를 맡겠다고 말합니다." in narrate_prompt
    assert "`intent`가 `talk`이면" in narrate_prompt
    assert "말의 목적을 짧게 씁니다" in narrate_prompt
    assert "보이는 대상 이름과 실제로 꺼낼 말을 함께 씁니다" in narrate_prompt
    assert "루카에게 「이상하다는 동선 기록이 어느 구간이었나요?」라고 묻습니다." in narrate_prompt
    assert "말할 내용이 떠오르지 않으면 `talk` 제안을 만들지 않습니다" in narrate_prompt
    assert "STATE_PATCH" in intro_prompt
    assert "제공된 성격" in intro_prompt
    assert "훈련, 점검, 안내" not in intro_prompt
    assert "추상적인 분위기만 쓰지 말고" in intro_prompt
    assert "출력은 플레이어가 읽는 나레이션" in combat_prompt
    assert "훈련 충격" in combat_prompt
    assert "recent_narration" in combat_prompt
    assert "행동 요약" in combat_prompt
    assert "새 문장으로 장면화합니다" in combat_prompt
    assert "전투가 끝났으면" in combat_prompt
    assert "마무리 장면으로 닫습니다" in combat_prompt
    assert "전투 시작" in combat_prompt
    assert "전투 시작은 대치 진입입니다" in combat_prompt
    assert "전투 종료, 도주, 쓰러짐, 큰 전세 변화가 있을 때만 씁니다" in combat_prompt
    assert "일반 교환이면 `turn_summary`는 빈 문자열입니다" in combat_prompt
    assert "`suggestions`는 항상 빈 배열입니다" in combat_prompt
    assert "다음 행동 제안은 만들지 않습니다" in combat_prompt
    assert '"label":"","input_text":"","intent":"combat","action":null' not in combat_prompt
    assert "`tactic`이 아니라 `flee` intent" in classify_prompt
    assert "`tactic`이 아니라 `talk` intent" in classify_prompt
    assert "`tactic`: 전투 중 공격 전술" in classify_prompt
    assert "공격 또는 이탈 전술" not in classify_prompt
    assert "`create_distance`: 거리 벌리기" not in classify_prompt
    assert "후보는 같은 리듬으로 만듭니다" in recommend_prompt
    assert "최근에 실제로 반복한 행동" in recommend_prompt
    assert "Candidate rhythm" in recommend_en_prompt
    assert "Do not add setting lore" in recommend_en_prompt
    assert "Skills support a roll/check" in recommend_en_prompt
    assert "Skills support a combat roll" not in recommend_en_prompt
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
    assert "secrets" not in payload["target_view"]
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
