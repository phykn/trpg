import json
from pathlib import Path

from src.game.domain.action import Action
from src.game.runtime import GameRuntimeState
from src.game.runtime.action.dispatch import dispatch_graph_action
from src.game.runtime.narration.context import build_input_narration_payload
from src.game.seed.graph_seed import build_seed_graph
from src.game.seed.player import PlayerInput


ROOT = Path(__file__).resolve().parents[4]
SCENARIO = ROOT / "scenarios" / "dev_test"


def _records(name: str) -> dict:
    path = SCENARIO / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _dev_runtime() -> GameRuntimeState:
    bundle = build_seed_graph(
        profile_name="dev_test",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races=_records("races"),
        locations=_records("locations"),
        items=_records("items"),
        skills=_records("skills"),
        effects=_records("effects"),
        statuses=_records("statuses"),
        slots=_records("slots"),
        factions=_records("factions"),
        actions=_records("actions"),
        knowledge=_records("knowledge"),
        dialogue_styles=_records("dialogue_styles"),
        mbti=_records("mbti"),
        npcs=_records("characters"),
        quests=_records("quests"),
        chapters=_records("chapters"),
        start=_records("start"),
        template=_records("player"),
        game_id="game-1",
        locale="ko",
    )
    return GameRuntimeState(
        graph=bundle.graph,
        content=bundle.content,
        progress=bundle.progress,
    )


def test_dev_test_luka_has_public_route_clue_for_followup_questions():
    runtime = _dev_runtime()

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="이동 경로 기록에서 특이점을 알려 달라고 루카에게 묻습니다",
        action=Action(verb="speak", to="companion_probe_npc", how="ask"),
        dialogue_target=runtime.graph.nodes["companion_probe_npc"],
    )

    assert payload["scene_state"]["target_view"]["public_knowledge"] == [
        {
            "id": "movement_route_public_clue",
            "title": "동선 기록의 공개 단서",
            "summary": (
                "테스트 허브에서 기록 보관실로 이어지는 이동 기록만 시간 순서가 "
                "어긋나며, 기록 보관실의 봉인 표식 날짜 확인으로 이어집니다"
            ),
        }
    ]


def test_dev_test_first_aid_quest_completes_by_using_treatment_bandage():
    runtime = _dev_runtime()

    accepted = dispatch_graph_action(
        runtime,
        Action(verb="transfer", what="q_first_aid", how="accept"),
    )
    result = dispatch_graph_action(
        accepted.runtime,
        Action(verb="use", what="treatment_bandage", to="injured_tester_npc"),
    )

    graph = result.runtime.graph
    assert result.kind == "use"
    assert "hp" not in graph.nodes["injured_tester_npc"].properties
    assert graph.nodes["q_first_aid"].properties["status"] == "completed"
    assert graph.nodes["q_first_aid"].properties["triggers_met"] == [True]
    assert "carries:player_01:treatment_bandage" not in graph.edges
    assert "carries:player_01:first_aid_badge" in graph.edges
    assert result.runtime.progress.active_quest_id is None
