from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph.apply import apply_graph_changes
from src.game.domain.graph.models import AddEdgeChange, AddNodeChange
from src.game.domain.progress import GameProgress
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteResponse
from src.game.runtime.flow import turn as turn_flow
from src.game.runtime.flow.generated_input import (
    apply_generated_story_after_action,
    derive_story_write_intent,
    story_write_intent_for_contract,
)
from src.game.runtime.flow.turn import run_graph_action_turn_from_runtime
from src.game.runtime.narration.result import GraphNarrationResult
from src.game.runtime.request_result import GraphActionRequestResult, rejected_result
from src.game.runtime.state import GameRuntimeState
from src.wire.graph.to_front import graph_to_front_state


class FakeGraphRepo:
    def __init__(self) -> None:
        self.saved = False
        self.progress = None
        self.logs = []
        self.story_patch_entries = []

    async def save_graph_changes(self, *args, **kwargs) -> None:
        self.saved = True

    async def append_log_entries(self, game_id, entries) -> None:
        self.logs.extend(entries)

    async def append_story_patch_entries(self, game_id, entries) -> None:
        self.story_patch_entries.extend(entries)

    async def save_progress(self, progress) -> None:
        self.progress = progress


def _story_contract() -> StoryContract:
    return StoryContract.model_validate(
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
        }
    )


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01",
                    type="character",
                    properties={
                        "name": "당신",
                        "is_player": True,
                        "level": 1,
                        "gold": 0,
                        "xp_pool": 0,
                        "hp": 5,
                        "max_hp": 5,
                        "mp": 5,
                        "max_mp": 5,
                        "stats": {
                            "body": 1,
                            "agility": 1,
                            "mind": 1,
                            "presence": 1,
                        },
                    },
                ),
                "loc_fog_harbor": GraphNode(
                    id="loc_fog_harbor",
                    type="location",
                    properties={"name": "안개 항구", "description": "항구입니다."},
                ),
                "loc_white_pier": GraphNode(
                    id="loc_white_pier",
                    type="location",
                    properties={"name": "하얀 부두", "description": "부두입니다."},
                ),
            },
            edges={
                "located_at:player_01:loc_fog_harbor": GraphEdge(
                    id="located_at:player_01:loc_fog_harbor",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="loc_fog_harbor",
                ),
                "connects_to:loc_fog_harbor:loc_white_pier": GraphEdge(
                    id="connects_to:loc_fog_harbor:loc_white_pier",
                    type="connects_to",
                    from_node_id="loc_fog_harbor",
                    to_node_id="loc_white_pier",
                )
            },
        ),
        progress=GameProgress(
            game_id="game-1",
            player_id="player_01",
            profile_id="white_isle",
        ),
        story_contract=_story_contract(),
    )


async def test_generated_story_skips_non_executed_results() -> None:
    calls = 0

    async def fake_writer(**kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("writer should not be called")

    runtime = _runtime()
    repo = FakeGraphRepo()
    result = rejected_result(
        runtime,
        graph_to_front_state(runtime),
        message="rejected",
    )

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=_story_contract(),
        player_input="표를 봅니다.",
        action=Action(verb="perceive", what="ticket"),
        writer=fake_writer,
    )

    assert next_result is result
    assert calls == 0
    assert repo.saved is False


async def test_generated_story_applies_valid_clue_to_graph_and_front_state() -> None:
    async def fake_writer(**kwargs) -> StoryWriteResponse:
        return StoryWriteResponse.model_validate(
            {
                "reason": "found",
                "patches": [
                    {
                        "op": "add_clue",
                        "id": "clue_wet_ticket_001",
                        "title": "젖은 승선표",
                        "summary": "표가 젖어 있습니다.",
                        "anchor_id": "loc_fog_harbor",
                    }
                ],
            }
        )

    runtime = _runtime()
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=FakeGraphRepo(),
        result=result,
        contract=_story_contract(),
        player_input="표를 봅니다.",
        action=Action(verb="perceive", what="ticket"),
        writer=fake_writer,
    )

    assert "clue_wet_ticket_001" in next_result.runtime.graph.nodes
    assert [entry.id for entry in next_result.front_state.discoveries.clues] == [
        "clue_wet_ticket_001"
    ]


async def test_generated_story_accepts_clue_patch_for_actionable_advice_without_retry() -> None:
    calls = 0

    async def fake_writer(**kwargs) -> StoryWriteResponse:
        nonlocal calls
        calls += 1
        return StoryWriteResponse.model_validate(
            {
                "reason": "advice becomes a clue",
                "patches": [
                    {
                        "op": "add_clue",
                        "id": "clue_fog_balance_check",
                        "title": "배 균형 확인",
                        "summary": "안개 항구에서는 혼자 탄 배의 균형을 먼저 확인해야 합니다.",
                        "anchor_id": "loc_fog_harbor",
                    }
                ],
            }
        )

    contract = _story_contract().model_copy(
        update={
            "allowed_ops": [
                "add_memory",
                "add_clue",
                "add_location",
                "add_character",
                "add_item",
                "add_quest_beat",
            ]
        }
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="올든에게 안개 항구에서 무엇을 먼저 확인해야 하는지 묻습니다.",
        action=Action(verb="speak", what="npc_olden", how="ask"),
        accepted_narration=(
            "올든이 혼자 탄 배의 균형을 먼저 확인해야 한다며 "
            "출항 명부를 가리킵니다."
        ),
        writer=fake_writer,
    )

    assert calls == 1
    assert "clue_fog_balance_check" in next_result.runtime.graph.nodes
    assert [entry.status for entry in repo.story_patch_entries] == ["accepted"]
    assert repo.story_patch_entries[0].changed_node_ids == ["clue_fog_balance_check"]


async def test_generated_story_records_accepted_patch_entry() -> None:
    async def fake_writer(**kwargs) -> StoryWriteResponse:
        return StoryWriteResponse.model_validate(
            {
                "reason": "found",
                "patches": [
                    {
                        "op": "add_clue",
                        "id": "clue_wet_ticket_001",
                        "title": "젖은 승선표",
                        "summary": "표가 젖어 있습니다.",
                        "anchor_id": "loc_fog_harbor",
                    }
                ],
            }
        )

    runtime = _runtime()
    repo = FakeGraphRepo()
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )

    await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=_story_contract(),
        player_input="표를 봅니다.",
        action=Action(verb="perceive", what="ticket"),
        writer=fake_writer,
    )

    assert len(repo.story_patch_entries) == 1
    entry = repo.story_patch_entries[0]
    assert entry.status == "accepted"
    assert entry.intent_kind == "clue_candidate"
    assert entry.patches[0]["id"] == "clue_wet_ticket_001"
    assert entry.changed_node_ids == ["clue_wet_ticket_001"]


async def test_generated_story_applies_first_patch_when_writer_exceeds_budget() -> None:
    async def fake_writer(**kwargs) -> StoryWriteResponse:
        return StoryWriteResponse.model_validate(
            {
                "reason": "too much but useful",
                "patches": [
                    {
                        "op": "add_memory",
                        "id": "mem_ellie_advice",
                        "summary": "흰섬에 가려면 선장에게 이야기해야 합니다.",
                    },
                    {
                        "op": "add_memory",
                        "id": "mem_extra",
                        "summary": "추가 정보입니다.",
                    },
                ],
                "new_terms": ["선장", "추가"],
            }
        )

    runtime = _runtime()
    repo = FakeGraphRepo()
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=_story_contract(),
        player_input="엘리에게 흰섬으로 가는 방법을 묻습니다.",
        action=Action(verb="speak", what="npc_ellie", how="friendly"),
        writer=fake_writer,
    )

    assert "mem_ellie_advice" in next_result.runtime.graph.nodes
    assert "mem_extra" not in next_result.runtime.graph.nodes
    entry = repo.story_patch_entries[0]
    assert entry.status == "accepted"
    assert [patch["id"] for patch in entry.patches] == ["mem_ellie_advice"]
    assert entry.changed_node_ids == ["mem_ellie_advice"]


async def test_generated_story_records_empty_patch_as_skipped() -> None:
    async def fake_writer(**kwargs) -> StoryWriteResponse:
        return StoryWriteResponse.model_validate(
            {"reason": "nothing durable changed", "patches": []}
        )

    runtime = _runtime()
    repo = FakeGraphRepo()
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )

    await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=_story_contract(),
        player_input="표를 봅니다.",
        action=Action(verb="perceive", what="ticket"),
        writer=fake_writer,
    )

    assert len(repo.story_patch_entries) == 1
    entry = repo.story_patch_entries[0]
    assert entry.status == "skipped"
    assert entry.reason == "nothing durable changed"
    assert entry.changed_node_ids == []
    assert entry.changed_edge_ids == []


async def test_generated_story_retries_empty_patch_for_actionable_narration() -> None:
    calls = []

    async def fake_writer(**kwargs) -> StoryWriteResponse:
        calls.append(kwargs["input_"].model_dump(mode="json"))
        if len(calls) == 1:
            return StoryWriteResponse.model_validate(
                {"reason": "prose only", "patches": []}
            )
        return StoryWriteResponse.model_validate(
            {
                "reason": "lead promoted",
                "patches": [
                    {
                        "op": "add_character",
                        "id": "char_harbor_manager",
                        "name": "항구 관리인",
                        "role": "quest_giver",
                        "location_id": "loc_fog_harbor",
                    }
                ],
            }
        )

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_character"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="엘리에게 흰섬으로 가는 방법을 묻습니다.",
        action=Action(verb="speak", what="npc_ellie", how="friendly"),
        accepted_narration=(
            "엘리가 말합니다. 「흰섬에 가려면 먼저 항구 관리인에게 "
            "이야기를 꺼내야 해요.」"
        ),
        writer=fake_writer,
    )

    assert len(calls) == 2
    assert calls[0]["visible_context"]["patch_requirement"]["required"] is True
    assert calls[1]["intent"]["reason"] == (
        "retry: accepted narration requires a graph patch"
    )
    assert "char_harbor_manager" in next_result.runtime.graph.nodes
    assert [entry.status for entry in repo.story_patch_entries] == ["accepted"]
    assert repo.story_patch_entries[0].changed_node_ids == ["char_harbor_manager"]


async def test_generated_story_allows_empty_patch_for_atmosphere_narration() -> None:
    calls = []

    async def fake_writer(**kwargs) -> StoryWriteResponse:
        calls.append(kwargs["input_"].model_dump(mode="json"))
        return StoryWriteResponse.model_validate(
            {"reason": "atmosphere only", "patches": []}
        )

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_location"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )

    await apply_generated_story_after_action(
        client=object(),
        repo=FakeGraphRepo(),
        result=result,
        contract=contract,
        player_input="여기가 어디인지 둘러봅니다.",
        action=Action(verb="perceive", what="loc_fog_harbor"),
        accepted_narration="안개 낀 부두에 습기 찬 바닷바람이 붑니다.",
        writer=fake_writer,
    )

    assert len(calls) == 1
    assert "patch_requirement" not in calls[0]["visible_context"]


async def test_generated_story_does_not_require_patch_for_existing_pier_mention() -> None:
    calls = []

    async def fake_writer(**kwargs) -> StoryWriteResponse:
        calls.append(kwargs["input_"].model_dump(mode="json"))
        return StoryWriteResponse.model_validate(
            {"reason": "existing scene detail", "patches": []}
        )

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_character", "add_location", "add_quest_beat"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="올든에게 말을 겁니다.",
        action=Action(verb="speak", what="npc_olden"),
        accepted_narration=(
            "선착장 끝에서는 작은 배 하나가 밧줄에 묶여 흔들리고 있습니다."
        ),
        writer=fake_writer,
    )

    assert len(calls) == 1
    assert "patch_requirement" not in calls[0]["visible_context"]
    assert [entry.status for entry in repo.story_patch_entries] == ["skipped"]


async def test_generated_story_skips_writer_error_without_synthesizing_patch() -> None:
    async def broken_writer(**kwargs) -> StoryWriteResponse:
        raise ValueError("patches.0 needs op")

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_character"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="엘리에게 흰섬으로 가는 방법을 묻습니다.",
        action=Action(verb="speak", what="npc_ellie", how="friendly"),
        accepted_narration=(
            "엘리가 말합니다. 「흰섬에 가려면 먼저 항구 관리인에게 "
            "이야기를 꺼내야 합니다.」"
        ),
        writer=broken_writer,
    )

    assert next_result is result
    assert repo.saved is False
    assert "char_manager" not in next_result.runtime.graph.nodes
    assert [entry.status for entry in repo.story_patch_entries] == ["skipped"]
    assert repo.story_patch_entries[0].reason == "story_write skipped after ValueError"
    assert repo.story_patch_entries[0].patches == []


async def test_generated_story_skips_writer_error_even_when_goal_is_actionable() -> None:
    async def broken_writer(**kwargs) -> StoryWriteResponse:
        raise ValueError("patches.0 needs op")

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_quest_beat"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="흰섬으로 가려면 무엇을 해야 하는지 묻습니다.",
        action=Action(verb="speak", what="npc_ellie", how="friendly"),
        accepted_narration="엘리가 잠시 생각하다가 길을 알아봐야 한다고 말합니다.",
        writer=broken_writer,
    )

    assert next_result is result
    assert "quest_clue" not in next_result.runtime.graph.nodes
    assert [entry.status for entry in repo.story_patch_entries] == ["skipped"]
    assert repo.story_patch_entries[0].patches == []


async def test_generated_story_rejects_empty_actionable_retry_without_synthesizing_patch() -> None:
    calls = 0

    async def empty_writer(**kwargs) -> StoryWriteResponse:
        nonlocal calls
        calls += 1
        return StoryWriteResponse.model_validate(
            {"reason": "nothing durable changed", "patches": []}
        )

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_quest_beat"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="엘리에게 구체적으로 어디로 가야 하는지 묻습니다.",
        action=Action(verb="speak", what="npc_ellie", how="friendly"),
        accepted_narration="엘리가 북쪽 길목으로 가셔야 한다고 말합니다.",
        writer=empty_writer,
    )

    assert calls == 2
    assert next_result is result
    assert repo.saved is False
    assert "quest_road" not in next_result.runtime.graph.nodes
    assert [entry.status for entry in repo.story_patch_entries] == ["rejected"]
    assert repo.story_patch_entries[0].reason == "nothing durable changed"
    assert repo.story_patch_entries[0].rejected_reasons == [
        "required_actionable_patch_missing"
    ]


async def test_generated_story_rejects_empty_open_move_without_synthesizing_location() -> None:
    calls = 0

    async def empty_writer(**kwargs) -> StoryWriteResponse:
        nonlocal calls
        calls += 1
        return StoryWriteResponse.model_validate(
            {"reason": "nothing durable changed", "patches": []}
        )

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_location"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="표지판이 가리키는 북쪽 길목으로 이동합니다.",
        action=Action(verb="move"),
        accepted_narration="당신은 북쪽 길목을 향해 걸음을 옮깁니다.",
        writer=empty_writer,
    )

    assert calls == 2
    assert next_result is result
    assert repo.saved is False
    assert "loc_road" not in next_result.runtime.graph.nodes
    assert [entry.status for entry in repo.story_patch_entries] == ["rejected"]
    assert repo.story_patch_entries[0].rejected_reasons == [
        "required_actionable_patch_missing"
    ]


async def test_generated_story_rejects_memory_only_patch_for_actionable_move() -> None:
    calls = 0

    async def memory_writer(**kwargs) -> StoryWriteResponse:
        nonlocal calls
        calls += 1
        return StoryWriteResponse.model_validate(
            {
                "reason": "remembered the move",
                "patches": [
                    {
                        "op": "add_memory",
                        "id": "mem_north_path_taken",
                        "summary": "당신은 북쪽 길목으로 진입했습니다.",
                    }
                ],
            }
        )

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_memory", "add_location"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="표지판이 가리키는 북쪽 길목으로 이동합니다.",
        action=Action(verb="move"),
        accepted_narration="당신은 북쪽 길목을 향해 걸음을 옮깁니다.",
        writer=memory_writer,
    )

    assert calls == 2
    assert next_result is result
    assert repo.saved is False
    assert "loc_road" not in next_result.runtime.graph.nodes
    assert "mem_north_path_taken" not in next_result.runtime.graph.nodes
    assert [entry.status for entry in repo.story_patch_entries] == ["rejected"]
    assert repo.story_patch_entries[0].patches[0]["id"] == "mem_north_path_taken"
    assert repo.story_patch_entries[0].rejected_reasons == [
        "required_actionable_patch_missing"
    ]


async def test_generated_story_skips_writer_error_when_no_fallback_matches() -> None:
    async def broken_writer(**kwargs) -> StoryWriteResponse:
        raise ValueError("patches.0 needs op")

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_memory", "add_clue"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="엘리에게 접근합니다.",
        action=Action(verb="speak", what="npc_ellie", how="approach"),
        accepted_narration="엘리가 부둣가를 가리킵니다.",
        writer=broken_writer,
    )

    assert next_result is result
    assert repo.saved is False
    assert [entry.status for entry in repo.story_patch_entries] == ["skipped"]
    assert repo.story_patch_entries[0].reason == "story_write skipped after ValueError"
    assert repo.story_patch_entries[0].patches == []


async def test_generated_story_does_not_retry_after_writer_error_skip() -> None:
    calls = 0

    async def broken_writer(**kwargs) -> StoryWriteResponse:
        nonlocal calls
        calls += 1
        raise ValueError("patches.0 needs op")

    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_location"]}
    )
    runtime = _runtime().model_copy(update={"story_contract": contract})
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )
    repo = FakeGraphRepo()

    await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=contract,
        player_input="엘리에게 접근합니다.",
        action=Action(verb="speak", what="npc_ellie", how="approach"),
        accepted_narration="엘리가 부둣가를 가리킵니다.",
        writer=broken_writer,
    )

    assert calls == 1
    assert repo.story_patch_entries[0].status == "skipped"
    assert repo.story_patch_entries[0].reason == "story_write skipped after ValueError"


async def test_generated_story_records_rejected_patch_entry() -> None:
    async def fake_writer(**kwargs) -> StoryWriteResponse:
        return StoryWriteResponse.model_validate(
            {
                "reason": "duplicate",
                "patches": [
                    {
                        "op": "add_clue",
                        "id": "clue_existing",
                        "title": "이미 본 단서",
                        "summary": "이미 있습니다.",
                        "anchor_id": "loc_fog_harbor",
                    }
                ],
            }
        )

    runtime = _runtime()
    runtime.graph.nodes["clue_existing"] = GraphNode(
        id="clue_existing",
        type="knowledge",
        properties={"kind": "clue"},
    )
    repo = FakeGraphRepo()
    result = GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=graph_to_front_state(runtime),
    )

    next_result = await apply_generated_story_after_action(
        client=object(),
        repo=repo,
        result=result,
        contract=_story_contract(),
        player_input="표를 봅니다.",
        action=Action(verb="perceive", what="ticket"),
        writer=fake_writer,
    )

    assert next_result is result
    assert repo.saved is False
    assert len(repo.story_patch_entries) == 1
    entry = repo.story_patch_entries[0]
    assert entry.status == "rejected"
    assert entry.patches[0]["id"] == "clue_existing"
    assert entry.rejected_reasons


def test_derive_story_write_intent_marks_perception_as_clue_candidate() -> None:
    intent = derive_story_write_intent(Action(verb="perceive", what="ticket"))

    assert intent.kind == "clue_candidate"


def test_story_write_intent_for_contract_expands_when_world_ops_are_allowed() -> None:
    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_memory", "add_clue", "add_location"]}
    )

    intent = story_write_intent_for_contract(
        Action(verb="perceive", what="창고 뒤"),
        contract,
    )

    assert intent.kind == "both"
    assert intent.reason == "world write allowed"


def test_story_write_intent_expands_when_recent_discovery_is_only_memory() -> None:
    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_memory", "add_clue", "add_location"]}
    )
    runtime = _runtime()
    runtime.progress.turn_count = 5
    runtime.graph.nodes["mem_recent"] = GraphNode(
        id="mem_recent",
        type="knowledge",
        properties={
            "kind": "memory",
            "title": "최근 기억",
            "summary": "최근에 기억했습니다.",
            "stability": "campaign",
            "turn_id": 4,
        },
    )

    intent = story_write_intent_for_contract(
        Action(verb="move", to="loc_white_pier"),
        contract,
        runtime=runtime,
    )

    assert intent.kind == "both"


def test_story_write_intent_keeps_base_when_recent_world_node_exists() -> None:
    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_memory", "add_clue", "add_location"]}
    )
    runtime = _runtime()
    runtime.progress.turn_count = 5
    runtime.graph.nodes["loc_recent"] = GraphNode(
        id="loc_recent",
        type="location",
        properties={
            "name": "최근 장소",
            "description": "최근에 생성했습니다.",
            "turn_id": 4,
        },
    )

    intent = story_write_intent_for_contract(
        Action(verb="move", to="loc_white_pier"),
        contract,
        runtime=runtime,
    )

    assert intent.kind == "memory_candidate"


def test_story_write_intent_expands_when_recent_discoveries_are_stale() -> None:
    contract = _story_contract().model_copy(
        update={"allowed_ops": ["add_memory", "add_clue", "add_location"]}
    )
    runtime = _runtime()
    runtime.progress.turn_count = 5
    runtime.graph.nodes["clue_old"] = GraphNode(
        id="clue_old",
        type="knowledge",
        properties={
            "kind": "clue",
            "title": "오래된 단서",
            "summary": "한참 전에 발견했습니다.",
            "stability": "scene",
            "turn_id": 1,
        },
    )

    intent = story_write_intent_for_contract(
        Action(verb="move", to="loc_white_pier"),
        contract,
        runtime=runtime,
    )

    assert intent.kind == "both"
    assert intent.reason == "no recent generated discoveries"


async def test_action_turn_narrates_after_generated_story_is_applied(
    monkeypatch,
) -> None:
    repo = FakeGraphRepo()
    seen_after_has_clue = False

    async def fake_apply_generated_story_after_action(**kwargs):
        result = kwargs["result"]
        changes = [
            AddNodeChange(
                type="add_node",
                node=GraphNode(
                    id="clue_wet_ticket_001",
                    type="knowledge",
                    properties={
                        "kind": "clue",
                        "title": "젖은 승선표",
                        "summary": "표가 젖어 있습니다.",
                        "visibility": "player",
                        "stability": "scene",
                    },
                ),
            ),
            AddEdgeChange(
                type="add_edge",
                edge=GraphEdge(
                    id="has_knowledge:loc_white_pier:clue_wet_ticket_001",
                    type="has_knowledge",
                    from_node_id="loc_white_pier",
                    to_node_id="clue_wet_ticket_001",
                ),
            ),
        ]
        graph = apply_graph_changes(result.runtime.graph, changes)
        runtime = result.runtime.model_copy(update={"graph": graph})
        return result.model_copy(
            update={
                "runtime": runtime,
                "front_state": graph_to_front_state(runtime),
            }
        )

    async def fake_build_graph_action_narration(*args, **kwargs):
        nonlocal seen_after_has_clue
        seen_after_has_clue = "clue_wet_ticket_001" in kwargs["after"].graph.nodes
        return GraphNarrationResult(narration="부두에 도착합니다.")

    monkeypatch.setattr(
        turn_flow,
        "apply_generated_story_after_action",
        fake_apply_generated_story_after_action,
    )
    monkeypatch.setattr(
        turn_flow,
        "build_graph_action_narration",
        fake_build_graph_action_narration,
    )

    result = await run_graph_action_turn_from_runtime(
        repo,
        "game-1",
        _runtime(),
        Action(verb="move", to="loc_white_pier"),
        player_input="부두로 갑니다.",
    )

    assert seen_after_has_clue is True
    assert [entry.id for entry in result.front_state.discoveries.clues] == [
        "clue_wet_ticket_001"
    ]
