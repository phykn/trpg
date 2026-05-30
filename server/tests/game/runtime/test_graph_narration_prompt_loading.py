from pathlib import Path

import pytest

from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.content import RuntimeContent
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.flow.input import run_graph_input_turn
from src.game.runtime.flow.intro import run_graph_initial_narration
from src.game.runtime.narration.context import (
    build_input_narration_payload,
)
from src.game.runtime.state import GameRuntimeState
from src.game.runtime.flow.turn import run_graph_action_turn
from src.llm.calls.runner import get_prompt


PROMPT_ROOT = Path(__file__).resolve().parents[3] / "src" / "locale" / "prompts"


def _assert_contains_all(text: str, needles: list[str]) -> None:
    missing = [needle for needle in needles if needle not in text]
    assert not missing, f"missing prompt contract terms: {missing}"


def _assert_contains_none(text: str, needles: list[str]) -> None:
    found = [needle for needle in needles if needle in text]
    assert not found, f"forbidden prompt terms found: {found}"


def _assert_ordered(text: str, needles: list[str]) -> None:
    positions = [text.index(needle) for needle in needles]
    assert positions == sorted(positions), f"prompt sections out of order: {needles}"


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
    assert get_prompt("graph_narrate", "ko")
    assert get_prompt("combat_narrate", "ko")
    assert get_prompt("classify", "ko")
    assert get_prompt("recommend", "ko")


def test_packaged_prompts_stay_within_size_budget():
    budgets = {
        "graph_narrate": 28000,
        "classify": 18000,
        "combat_narrate": 7000,
        "recommend": 6000,
    }

    for agent, max_chars in budgets.items():
        assert len(get_prompt(agent, "ko")) <= max_chars


def test_graph_narrate_prompt_orders_contract_before_mode_details():
    prompt = get_prompt("graph_narrate", "ko")

    _assert_ordered(
        prompt,
        [
            "## 본문 문체",
            "## 사용 정보",
            "## 처리 라우터",
            "## 판정 결과 장면화",
            "## 판정 전 나레이션",
            "## player_input",
            "## 대화",
            "## 메타 JSON",
        ],
    )


def test_graph_narration_prompts_encode_core_contracts():
    narrate_prompt = get_prompt("graph_narrate", "ko")
    combat_prompt = get_prompt("combat_narrate", "ko")
    classify_prompt = get_prompt("classify", "ko")
    recommend_prompt = get_prompt("recommend", "ko")
    combined_narration = f"{narrate_prompt}\n{combat_prompt}"

    _assert_contains_all(
        combined_narration,
        [
            "담백한 플레이 로그체",
            "한 문장에는 하나의 동작만 넣습니다",
            "멋 부리지 말고, 보이는 일만 짧게 씁니다",
            "플레이어의 행동을 분명하게 씁니다",
            "플레이어를 우습게 만들지",
            "좋은 예",
            "한자",
        ],
    )
    _assert_contains_none(
        combined_narration,
        ["조금 과장해서 씁니다", "1~2문장", "2~3문장", "Baldur", "발더", "발게"],
    )

    _assert_contains_all(
        narrate_prompt,
        [
            "본문 문체",
            "일반 행동은 같은 리듬으로 씁니다",
            "플레이어의 선택이나 시도가 보입니다",
            "확정된 결과가 보입니다",
            "남은 거리, 물건 상태, NPC 반응, 다음 목표",
            "## 처리 라우터",
            "전투 브리핑이면 전투",
            "`장면 유형`이 `roll_prompt`이면 판정 전",
            "`ui_cues`와 `suggestions`의 기본값은 빈 배열입니다",
            "선택 라벨이나 퀘스트 제목",
            "임의로 성공 상태",
            "완료된 목표",
            "연두 체류권 획득",
            "위치 이동, 동행자 이탈, 소유 변화",
            "`혹은`, `아마`, `시야에서 약간`",
            "suggestions는 새 행동을 창작하는 기능이 아닙니다",
            "브리핑에 이미 드러난 대상, 장소, 물건, 목표를 플레이어 입력문으로 바꾸는 기능입니다",
            "NPC가 직접 반응하는 것을 기본값으로 씁니다",
            "설명문만 쓰지 말고 직접 발화 한 문장을 반드시 넣습니다",
            "`앞에 선니다`처럼 잘못 합성한 표현",
            "`앞에 섭니다`처럼 자연스러운 현재형",
            "직접 발화 `「」` 앞뒤는 문장과 붙이지 말고",
            "`플레이어님`",
            "`당신의 행동이 처리됩니다`",
            "`당신의 선택(열기)`",
            "`하나`, `한 장`, `한 척`, `한 상점`, `한 진열대`, `둘`, `네 개`, `다섯 개`",
            "`듯한`, `듯 보입니다`, `느껴집니다`",
            "런타임이 고쳐 주지 않습니다",
            "`대상 정보`는 그 대상과 이번 상호작용에 붙은 공개 정보입니다",
            "전투 모드에서는 대화, 조사, 퀘스트 규칙보다",
            "전투의 `행동`, `결과`, `전투 상태`, `확정`",
            "STATE_PATCH",
            "GraphChange",
            "USER_STREAM",
        ],
    )
    _assert_contains_none(
        narrate_prompt,
        [
            "사용자 메시지는 이미 확정된 사실을 담은 JSON입니다",
            "preroll_narration",
            "dialogue_style",
            "character-specific",
            '"label":"","input_text":"","intent":"combat","action":null',
        ],
    )

    _assert_contains_all(
        combat_prompt,
        [
            "사용자 메시지는 engine이 확정한 전투 결과 브리핑입니다",
            "판정을 다시 해석하지 않고",
            "결과 라벨 대신 맞음, 막힘, 빗나감",
            "exchange_result별 작성 기준",
            "player_action별 초점",
            "success는 공격 성공이 아니라 방어 성공입니다",
            "success는 피해를 주는 것이 아니라 거리를 벌리거나 전투에서 빠져나오는 것입니다",
            "success는 설득 성공이 아니라 상대의 거리, 자세, 공격 타이밍이 흔들린 것입니다",
            "victory, defeat, escaped, combat_stopped, ongoing",
            "훈련 충격",
            "`suggestions`는 항상 빈 배열입니다",
            "다음 행동 제안은 만들지 않습니다",
        ],
    )
    _assert_contains_none(
        combat_prompt,
        ["전투 JSON", "손맛", "「큭, 막혔습니다.」", "victory, defeat, flee, stop"],
    )

    _assert_contains_all(
        classify_prompt,
        [
            "전투 중 도망 의도",
            "`flee` intent",
            "전투 중 대화 의도",
            "`talk` intent",
            "`flee`",
            "전투 중 도망 또는 거리 확보",
        ],
    )
    _assert_contains_none(classify_prompt, ["`tactic`: 전투 중 공격 전술", "공격 또는 이탈 전술"])

    _assert_contains_all(
        recommend_prompt,
        [
            "후보는 같은 리듬으로 만듭니다",
            "입력 JSON은 큰 정보에서 세부 정보 순서로 읽습니다",
            "`current_story`로 현재 챕터/퀘스트 맥락을 잡고",
            "마지막 `recent_log`를 가장 중요한 최근 플레이 경향으로 판단합니다",
            "최근에 실제로 반복한 행동",
            "`flee` 후보",
            "`talk` 후보",
        ],
    )
    _assert_contains_none(recommend_prompt, ["`social` 후보"])


def test_graph_narrate_prompt_prefers_grounded_natural_prose_over_hype():
    prompt = get_prompt("graph_narrate", "ko")

    _assert_contains_all(prompt, ["관찰 가능한 변화", "번역투", "결과", "장면이 반응"])
    _assert_contains_none(prompt, ["조금 과장해서 씁니다", "플레이어의 팬인 GM"])


def test_combat_narrate_prompt_prefers_plain_play_log_style():
    prompt = get_prompt("combat_narrate", "ko")

    _assert_contains_all(
        prompt,
        ["담백한 플레이 로그체", "한 문장에는 하나의 동작", "비명을 삼킵니다", "검이 대상의 어깨에 닿습니다"],
    )
    _assert_contains_none(prompt, ["조금 과장해서 씁니다"])


def test_graph_narrate_prompt_treats_rhythm_as_order_not_template():
    prompt = (PROMPT_ROOT / "graph_narrate" / "prompt.ko.md").read_text(
        encoding="utf-8"
    )

    _assert_contains_all(
        prompt,
        ["같은 리듬", "고정 문장틀", "문장 시작", "서술어", "닫는 초점", "반응한 대상 하나"],
    )


def test_graph_narrate_prompt_encodes_theory_pressure_and_completion_limits():
    prompt = (PROMPT_ROOT / "graph_narrate" / "prompt.ko.md").read_text(
        encoding="utf-8"
    )

    _assert_contains_all(
        prompt,
        [
            "가장 강한 근거",
            "`플레이어 입력`",
            "`장면 유형`",
            "`결과`",
            "`확정`",
            "`선택 결과`",
            "`대상 정보`",
            "`공개된 사실`",
            "배경 문맥",
            "마지막",
            "연속성과 반복 회피",
            "UI 라벨",
            "추천 칩",
            "강한 근거가 아닙니다",
            "막힘을 남기는 것은 필수가 아닙니다",
            "대화 대상",
            "다른 인물",
            "엘리에게 대화 시도하기",
            "출항 가능 여부 묻기",
            "챕터 제목은 물리적 위치가 아닙니다",
            "현재 연두섬의 별점 게시판",
            "글, 영수증, 표지판, 계약서",
            "실제 문구, 이름, 금액, 조건",
            "새 갈고리 없이 닫습니다",
            "장소 진입 퀘스트 트리거",
            "갈등을 해결한 것처럼 과장하지 않습니다",
            "소유자와 위치",
            "보관 동작",
            "체류권 남기기",
            "연두 체류권",
            "출항 허가서가 발급",
            "축하식이 이미 끝났다고",
            "새 출발의 박자 사건",
            "축하식의 흔적",
            "이미 연주 중인 상태",
            "기대감 가득한 정적",
            "흰섬의 빈 의자 쪽",
            "과거 장소명인 `안개 항구`",
            "선택의 잔향",
            "마지막 사물",
        ],
    )


def test_graph_narrate_prompt_requires_clear_roll_consequences():
    prompt = (PROMPT_ROOT / "graph_narrate" / "prompt.ko.md").read_text(
        encoding="utf-8"
    )

    _assert_contains_all(
        prompt,
        [
            "성공/실패",
            "귀결",
            "되묻기",
            "추상 묘사",
            "`공개된 사실`",
            "확정 정보",
            "`대상 정보`",
            "선명한 사실 후보",
            "질문을 되묻기만 하면 실패",
            "원하는 답, 단서, 양보",
        ],
    )


def test_graph_narrate_prompt_rejects_silent_info_dialogue():
    prompt = (PROMPT_ROOT / "graph_narrate" / "prompt.ko.md").read_text(
        encoding="utf-8"
    )

    _assert_contains_all(
        prompt,
        [
            "정보형 질문은 직접 발화 없이 시선 묘사만으로 끝내면 실패입니다",
            "장소 질문이면 장소 이름이나 보이는 방의 쓰임을 먼저 말합니다",
        ],
    )


def test_graph_narrate_prompt_uses_story_transition_as_lead_not_solution():
    prompt = (PROMPT_ROOT / "graph_narrate" / "prompt.ko.md").read_text(
        encoding="utf-8"
    )

    _assert_contains_all(
        prompt,
        [
            "사건 전환",
            "동행자의 짧은 관찰",
            "정답이나 명령",
            "다음 사건의 쟁점",
            "handoff에 없는 이전 퀘스트의 물건",
            "플레이어 손",
            "인벤토리",
            "여러 선택지 뒤에 공통",
            "한쪽 선택 결과",
            "남은 흔적",
            "서로 다른 사물을 섞어 새 복합 사물",
            "`별 모양 서명란`",
            "매듭이 물길과 연결",
            "방금 선택한 결과",
            "`선택 결과`와 `획득`",
            "점수표 떼어내기",
            "`별점 복구`처럼",
            "작은 시작으로 줄이기",
            "플레이어 손",
        ],
    )
    _assert_contains_none(prompt, ["엘리나 동행자"])


@pytest.mark.asyncio
async def test_graph_input_payload_exposes_target_traits(tmp_path):
    repo = await _repo(tmp_path)
    runtime = GameRuntimeState(
        graph=await repo.load_graph("game-1"),
        progress=await repo.load_progress("game-1"),
        content=RuntimeContent(world_guidance="짧고 차분하게 씁니다."),
    )
    target = runtime.graph.nodes["goblin_01"]

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="고블린에게 농담을 건넨다",
        action=Action(verb="speak", what="goblin_01"),
        dialogue_target=target,
    )

    target_view = payload["scene_state"]["target_view"]
    assert target_view["personality"] == ["dry", "watchful"]
    assert "speech_style" not in target_view
    assert "humor_style" not in target_view
    assert target_view["dialogue_style"]["speech_style"] == (
        "short report-like replies"
    )
    assert target_view["dialogue_style"]["humor_style"] == (
        "treats jokes as report categories"
    )
    assert target_view["personal_boundary"] == (
        "deflects personal questions politely"
    )
    assert "secrets" not in target_view
    assert target_view["traits"] == ["can speak", "does not rush"]
    assert payload["reference_context"]["world_guidance"] == "짧고 차분하게 씁니다."
    assert payload["engine_event"]["dialogue_expectation"] == {
        "npc_reply": "expected",
        "direct_speech": "prefer_one_short_utterance",
    }


def test_graph_narration_runtime_preserves_llm_text():
    from src.game.runtime.flow.intro import _clean_intro_text

    long_text = "  긴 문장입니다.\n\n" + ("가" * 450)

    assert _clean_intro_text(long_text) == long_text


@pytest.mark.asyncio
async def test_graph_intro_uses_fixed_progress_text_without_llm(tmp_path):
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(update={"intro_text": "고정된 첫 장면입니다."})
    )
    runtime = GameRuntimeState(
        graph=await repo.load_graph("game-1"),
        progress=await repo.load_progress("game-1"),
    )

    next_runtime = await run_graph_initial_narration(repo, runtime)

    assert next_runtime.log_entries[-1].text == "고정된 첫 장면입니다."


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
                    active_enemy_id="goblin_01",
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
    assert call["temperature"] is None


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
    assert narrate_call["temperature"] is None
