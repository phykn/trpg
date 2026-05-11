# dev_test Social Quest Branching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small `dev_test` social quest slice where NPC relationship changes alter quest resolution.

**Architecture:** Add a focused social quest planner under `server/src/game/engines/` that returns graph changes for the `q_missing_supplies` QA quest. Call it from the existing `speak` narrative path before generic narration persistence, so LLM classification still identifies `speak` but the engine owns quest and relation state.

**Tech Stack:** Python 3.12, Pydantic v2 graph models, pytest, existing LocalFs graph repo tests, JSON scenario seed files.

---

## File Structure

- Create `server/src/game/engines/graph_social_quest.py`
  - Owns rule-based planning for the `q_missing_supplies` QA quest.
  - Exposes one function: `plan_social_quest_speak(graph, player_id, target_id, how, player_input)`.
  - Returns changed graph facts only; no LLM calls, persistence, or front-state conversion.

- Modify `server/src/game/runtime/input.py`
  - Calls the social quest planner inside `_run_graph_narrative_input` and `_run_graph_narrative_input_stream`.
  - Persists returned graph changes before appending the GM narration log.
  - Keeps ordinary `speak` behavior unchanged when the planner returns no changes.

- Modify `server/src/locale/catalog/runtime.toml`
  - Adds fallback narration strings for report, mediation prerequisite, mediation completion, and quiet return.

- Add `server/tests/game/engines/test_graph_social_quest.py`
  - Unit-tests planner behavior without LLM or persistence.

- Modify `server/tests/game/runtime/test_graph_input.py`
  - Adds integration tests proving `speak` input persists relation and quest changes.

- Modify `server/tests/game/seed/test_graph_seed.py`
  - Adds seed-level coverage for relation edges and missing supplies quest edges.

- Create `scenarios/dev_test/items/missing_supply_bundle.json`
  - New quest item for the social slice.

- Create `scenarios/dev_test/quests/q_missing_supplies.json`
  - New QA quest.

- Modify `scenarios/dev_test/characters/guide_npc.json`
  - Adds hint text for observing relationship outcomes.

- Modify `scenarios/dev_test/characters/quartermaster_npc.json`
  - Adds hint text and relation seed values for the supply dispute.

- Modify `scenarios/dev_test/characters/village_resident.json`
  - Adds hint text and relation seed values for the resident route.

- Modify `scenarios/dev_test/chapters/ch_dev_test.json`
  - Adds `q_missing_supplies`.

- Modify `tester.md`
  - Adds manual QA route checks.

---

### Task 1: Add the Social Quest Planner Tests

**Files:**
- Create: `server/tests/game/engines/test_graph_social_quest.py`
- Create: `server/src/game/engines/graph_social_quest.py`

- [ ] **Step 1: Write the failing planner tests**

Create `server/tests/game/engines/test_graph_social_quest.py` with:

```python
from src.game.domain.graph import Graph, GraphEdge, GraphNode, apply_graph_changes
from src.game.engines.graph_social_quest import plan_social_quest_speak


def _character(character_id: str) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={"hp": 5, "max_hp": 5, "alive": True},
    )


def _quest(status: str = "pending", **properties) -> GraphNode:
    return GraphNode(
        id="q_missing_supplies",
        type="quest",
        properties={
            "status": status,
            "triggers": [],
            "triggers_met": [],
            "rewards": {"gold": 1, "exp": 0},
            **properties,
        },
    )


def _graph(*, quest_status: str = "pending", quest_props=None, edges=None) -> Graph:
    base_edges = {
        "relation:quartermaster_npc:player_01": GraphEdge(
            id="relation:quartermaster_npc:player_01",
            type="relation",
            from_node_id="quartermaster_npc",
            to_node_id="player_01",
            properties={"affinity": 20},
        ),
        "relation:village_resident:player_01": GraphEdge(
            id="relation:village_resident:player_01",
            type="relation",
            from_node_id="village_resident",
            to_node_id="player_01",
            properties={"affinity": 0},
        ),
        "relation:guide_npc:player_01": GraphEdge(
            id="relation:guide_npc:player_01",
            type="relation",
            from_node_id="guide_npc",
            to_node_id="player_01",
            properties={"affinity": 0},
        ),
    }
    if edges:
        base_edges.update(edges)
    return Graph(
        nodes={
            "player_01": _character("player_01"),
            "quartermaster_npc": _character("quartermaster_npc"),
            "village_resident": _character("village_resident"),
            "guide_npc": _character("guide_npc"),
            "q_missing_supplies": _quest(quest_status, **(quest_props or {})),
        },
        edges=base_edges,
    )


def _apply(graph: Graph, target_id: str, how: str, text: str) -> Graph:
    result = plan_social_quest_speak(
        graph,
        player_id="player_01",
        target_id=target_id,
        how=how,
        player_input=text,
    )
    assert result is not None
    return apply_graph_changes(graph, result.changes)


def test_report_route_completes_quest_and_changes_affinity():
    graph = _apply(
        _graph(),
        "village_resident",
        "hostile",
        "보급 담당자에게 주민을 고발합니다",
    )

    assert graph.nodes["q_missing_supplies"].properties["status"] == "completed"
    assert graph.nodes["q_missing_supplies"].properties["resolution_route"] == "report"
    assert graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 25
    assert graph.edges["relation:village_resident:player_01"].properties["affinity"] == -5
    assert graph.edges["relation:guide_npc:player_01"].properties["affinity"] == 0


def test_mediation_first_records_resident_reason_without_completing():
    graph = _apply(
        _graph(),
        "village_resident",
        "friendly",
        "누락된 보급품을 가져간 이유를 묻습니다",
    )

    quest = graph.nodes["q_missing_supplies"].properties
    assert quest["status"] == "pending"
    assert quest["resident_reason_known"] is True
    assert "resolution_route" not in quest


def test_mediation_route_requires_reason_flag():
    result = plan_social_quest_speak(
        _graph(),
        player_id="player_01",
        target_id="quartermaster_npc",
        how="friendly",
        player_input="주민의 사정을 봐 달라고 설득합니다",
    )

    assert result is not None
    assert result.kind == "blocked"
    assert result.changes == []
    assert result.message_key == "runtime.social.missing_supplies.need_reason"


def test_mediation_route_completes_after_reason_flag():
    graph = _apply(
        _graph(quest_props={"resident_reason_known": True}),
        "quartermaster_npc",
        "friendly",
        "주민의 사정을 봐 달라고 설득합니다",
    )

    assert graph.nodes["q_missing_supplies"].properties["status"] == "completed"
    assert graph.nodes["q_missing_supplies"].properties["resolution_route"] == "mediate"
    assert graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 23
    assert graph.edges["relation:village_resident:player_01"].properties["affinity"] == 8
    assert graph.edges["relation:guide_npc:player_01"].properties["affinity"] == 5


def test_quiet_return_route_records_help_flag():
    graph = _apply(
        _graph(),
        "quartermaster_npc",
        "deceptive",
        "보급품을 조용히 돌려놓습니다",
    )

    assert graph.nodes["q_missing_supplies"].properties["status"] == "completed"
    assert graph.nodes["q_missing_supplies"].properties["resolution_route"] == "quiet_return"
    assert graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 20
    resident_relation = graph.edges["relation:village_resident:player_01"].properties
    assert resident_relation["affinity"] == 6
    assert resident_relation["flags"] == ["helped_quietly"]


def test_completed_quest_does_not_apply_again():
    result = plan_social_quest_speak(
        _graph(quest_status="completed", quest_props={"resolution_route": "report"}),
        player_id="player_01",
        target_id="village_resident",
        how="hostile",
        player_input="다시 고발합니다",
    )

    assert result is None
```

- [ ] **Step 2: Run the new test file and verify import failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/engines/test_graph_social_quest.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.game.engines.graph_social_quest'`.

---

### Task 2: Implement the Pure Social Quest Planner

**Files:**
- Create: `server/src/game/engines/graph_social_quest.py`
- Test: `server/tests/game/engines/test_graph_social_quest.py`

- [ ] **Step 1: Add the planner implementation**

Create `server/src/game/engines/graph_social_quest.py` with:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import (
    AddEdgeChange,
    Graph,
    GraphChange,
    GraphEdge,
    SetEdgePropertyChange,
    SetNodePropertyChange,
)


SocialQuestKind = Literal["reason_known", "resolved", "blocked"]

QUEST_ID = "q_missing_supplies"
PLAYER_ID = "player_01"
QUARTERMASTER_ID = "quartermaster_npc"
RESIDENT_ID = "village_resident"
GUIDE_ID = "guide_npc"


class SocialQuestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SocialQuestKind
    changes: list[GraphChange]
    message_key: str
    route: str | None = None


def plan_social_quest_speak(
    graph: Graph,
    *,
    player_id: str,
    target_id: str | None,
    how: str | None,
    player_input: str,
) -> SocialQuestResult | None:
    if player_id != PLAYER_ID:
        return None
    quest = graph.nodes.get(QUEST_ID)
    if quest is None or quest.type != "quest":
        return None
    status = quest.properties.get("status")
    if status in {"completed", "failed", "abandoned"}:
        return None
    if status not in {"locked", "pending", "active"}:
        return None
    if target_id == RESIDENT_ID and how == "friendly" and _mentions_reason(player_input):
        if quest.properties.get("resident_reason_known") is True:
            return None
        return SocialQuestResult(
            kind="reason_known",
            changes=[
                _quest_prop("resident_reason_known", True),
                *_affinity_changes(graph, RESIDENT_ID, player_id, 2),
            ],
            message_key="runtime.social.missing_supplies.reason_known",
        )
    if target_id == RESIDENT_ID and how == "hostile" and _mentions_report(player_input):
        return _resolve(
            graph,
            route="report",
            message_key="runtime.social.missing_supplies.report",
            affinity={
                QUARTERMASTER_ID: 5,
                RESIDENT_ID: -5,
                GUIDE_ID: 0,
            },
            flags={},
            player_id=player_id,
        )
    if target_id == QUARTERMASTER_ID and how == "friendly" and _mentions_mediate(player_input):
        if quest.properties.get("resident_reason_known") is not True:
            return SocialQuestResult(
                kind="blocked",
                changes=[],
                message_key="runtime.social.missing_supplies.need_reason",
            )
        return _resolve(
            graph,
            route="mediate",
            message_key="runtime.social.missing_supplies.mediate",
            affinity={
                QUARTERMASTER_ID: 3,
                RESIDENT_ID: 8,
                GUIDE_ID: 5,
            },
            flags={},
            player_id=player_id,
        )
    if how == "deceptive" and _mentions_quiet_return(player_input):
        return _resolve(
            graph,
            route="quiet_return",
            message_key="runtime.social.missing_supplies.quiet_return",
            affinity={
                RESIDENT_ID: 6,
            },
            flags={RESIDENT_ID: "helped_quietly"},
            player_id=player_id,
        )
    return None


def _resolve(
    graph: Graph,
    *,
    route: str,
    message_key: str,
    affinity: dict[str, int],
    flags: dict[str, str],
    player_id: str,
) -> SocialQuestResult:
    changes: list[GraphChange] = [
        _quest_prop("status", "completed"),
        _quest_prop("resolution_route", route),
    ]
    for actor_id, delta in affinity.items():
        changes.extend(_affinity_changes(graph, actor_id, player_id, delta))
    for actor_id, flag in flags.items():
        changes.extend(_flag_changes(graph, actor_id, player_id, flag))
    return SocialQuestResult(
        kind="resolved",
        changes=changes,
        message_key=message_key,
        route=route,
    )


def _quest_prop(path: str, value: object) -> SetNodePropertyChange:
    return SetNodePropertyChange(
        type="set_node_property",
        node_id=QUEST_ID,
        path=path,
        value=value,
    )


def _affinity_changes(
    graph: Graph,
    actor_id: str,
    player_id: str,
    delta: int,
) -> list[GraphChange]:
    if delta == 0:
        return []
    edge_id = _relation_edge_id(actor_id, player_id)
    edge = graph.edges.get(edge_id)
    if edge is None:
        return [
            AddEdgeChange(
                type="add_edge",
                edge=GraphEdge(
                    id=edge_id,
                    type="relation",
                    from_node_id=actor_id,
                    to_node_id=player_id,
                    properties={"affinity": delta},
                ),
            )
        ]
    affinity = edge.properties.get("affinity")
    current = affinity if isinstance(affinity, int) else 0
    return [
        SetEdgePropertyChange(
            type="set_edge_property",
            edge_id=edge_id,
            path="affinity",
            value=current + delta,
        )
    ]


def _flag_changes(
    graph: Graph,
    actor_id: str,
    player_id: str,
    flag: str,
) -> list[GraphChange]:
    edge_id = _relation_edge_id(actor_id, player_id)
    edge = graph.edges.get(edge_id)
    if edge is None:
        return [
            AddEdgeChange(
                type="add_edge",
                edge=GraphEdge(
                    id=edge_id,
                    type="relation",
                    from_node_id=actor_id,
                    to_node_id=player_id,
                    properties={"affinity": 0, "flags": [flag]},
                ),
            )
        ]
    raw_flags = edge.properties.get("flags")
    flags = [item for item in raw_flags if isinstance(item, str)] if isinstance(raw_flags, list) else []
    if flag not in flags:
        flags.append(flag)
    return [
        SetEdgePropertyChange(
            type="set_edge_property",
            edge_id=edge_id,
            path="flags",
            value=flags,
        )
    ]


def _relation_edge_id(actor_id: str, player_id: str) -> str:
    return f"relation:{actor_id}:{player_id}"


def _mentions_reason(text: str) -> bool:
    return _has_any(text, ("이유", "사정", "왜", "무슨 일", "보급품"))


def _mentions_report(text: str) -> bool:
    return _has_any(text, ("고발", "보고", "알립니다", "알린다", "훔쳤"))


def _mentions_mediate(text: str) -> bool:
    return _has_any(text, ("설득", "봐 달", "용서", "중재", "사정"))


def _mentions_quiet_return(text: str) -> bool:
    return _has_any(text, ("조용히", "몰래", "돌려놓", "반납"))


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)
```

- [ ] **Step 2: Run planner tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/engines/test_graph_social_quest.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit planner**

Run:

```powershell
git add server/src/game/engines/graph_social_quest.py server/tests/game/engines/test_graph_social_quest.py
git commit -m "feat: add social quest planner"
```

Expected: commit succeeds.

---

### Task 3: Connect Social Quest Results to Speak Input

**Files:**
- Modify: `server/src/game/runtime/input.py`
- Modify: `server/src/locale/catalog/runtime.toml`
- Test: `server/tests/game/runtime/test_graph_input.py`

- [ ] **Step 1: Add failing runtime tests**

Append these tests to `server/tests/game/runtime/test_graph_input.py`:

```python
def _social_graph() -> Graph:
    graph = _graph()
    graph.nodes.update(
        {
            "quartermaster_npc": _character("quartermaster_npc"),
            "village_resident": _character("village_resident"),
            "guide_npc": _character("guide_npc"),
            "q_missing_supplies": GraphNode(
                id="q_missing_supplies",
                type="quest",
                properties={
                    "status": "pending",
                    "triggers": [],
                    "triggers_met": [],
                    "rewards": {"gold": 1, "exp": 0},
                },
            ),
        }
    )
    graph.edges.update(
        {
            "located_at:quartermaster_npc:town": GraphEdge(
                id="located_at:quartermaster_npc:town",
                type="located_at",
                from_node_id="quartermaster_npc",
                to_node_id="town",
            ),
            "located_at:village_resident:town": GraphEdge(
                id="located_at:village_resident:town",
                type="located_at",
                from_node_id="village_resident",
                to_node_id="town",
            ),
            "located_at:guide_npc:town": GraphEdge(
                id="located_at:guide_npc:town",
                type="located_at",
                from_node_id="guide_npc",
                to_node_id="town",
            ),
            "relation:quartermaster_npc:player_01": GraphEdge(
                id="relation:quartermaster_npc:player_01",
                type="relation",
                from_node_id="quartermaster_npc",
                to_node_id="player_01",
                properties={"affinity": 20},
            ),
            "relation:village_resident:player_01": GraphEdge(
                id="relation:village_resident:player_01",
                type="relation",
                from_node_id="village_resident",
                to_node_id="player_01",
                properties={"affinity": 0},
            ),
            "relation:guide_npc:player_01": GraphEdge(
                id="relation:guide_npc:player_01",
                type="relation",
                from_node_id="guide_npc",
                to_node_id="player_01",
                properties={"affinity": 0},
            ),
        }
    )
    return graph


async def _social_repo(tmp_path) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph("game-1", _social_graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


async def test_graph_input_social_report_route_persists_quest_and_relations(tmp_path):
    repo = await _social_repo(tmp_path)
    llm = _FakeLLM(
        {
            "actions": [
                {
                    "verb": "speak",
                    "what": "village_resident",
                    "how": "hostile",
                    "note": "report missing supplies",
                }
            ]
        },
        narration="주민은 시선을 떨구고 보급 담당자는 기록판을 고쳐 쥡니다.",
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "보급 담당자에게 주민을 고발합니다")
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert graph.nodes["q_missing_supplies"].properties["status"] == "completed"
    assert graph.nodes["q_missing_supplies"].properties["resolution_route"] == "report"
    assert graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 25
    assert graph.edges["relation:village_resident:player_01"].properties["affinity"] == -5
    assert logs[-1].kind == "gm"
    assert logs[-1].text == "주민은 시선을 떨구고 보급 담당자는 기록판을 고쳐 쥡니다."


async def test_graph_input_social_mediation_requires_resident_reason(tmp_path):
    repo = await _social_repo(tmp_path)
    llm = _FakeLLM(
        {
            "actions": [
                {
                    "verb": "speak",
                    "what": "quartermaster_npc",
                    "how": "friendly",
                    "note": "mediate missing supplies",
                }
            ]
        },
        narration="이 문장은 쓰이지 않습니다.",
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "주민의 사정을 봐 달라고 설득합니다")
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert graph.nodes["q_missing_supplies"].properties["status"] == "pending"
    assert "resolution_route" not in graph.nodes["q_missing_supplies"].properties
    assert logs[-1].text == "보급 담당자는 판단을 미룹니다. 먼저 주민에게 사정을 확인해야 합니다."


async def test_graph_input_social_mediation_route_after_reason(tmp_path):
    repo = await _social_repo(tmp_path)
    ask_llm = _FakeLLM(
        {
            "actions": [
                {
                    "verb": "speak",
                    "what": "village_resident",
                    "how": "friendly",
                    "note": "ask missing supplies reason",
                }
            ]
        },
        narration="주민은 보급품을 가져간 이유를 조심스럽게 털어놓습니다.",
    )
    await run_graph_input_turn(ask_llm, repo, "game-1", "누락된 보급품을 가져간 이유를 묻습니다")

    mediate_llm = _FakeLLM(
        {
            "actions": [
                {
                    "verb": "speak",
                    "what": "quartermaster_npc",
                    "how": "friendly",
                    "note": "mediate missing supplies",
                }
            ]
        },
        narration="보급 담당자는 짧게 숨을 고르고 기록을 접습니다.",
    )
    await run_graph_input_turn(mediate_llm, repo, "game-1", "주민의 사정을 봐 달라고 설득합니다")
    graph = await repo.load_graph("game-1")

    assert graph.nodes["q_missing_supplies"].properties["status"] == "completed"
    assert graph.nodes["q_missing_supplies"].properties["resolution_route"] == "mediate"
    assert graph.edges["relation:village_resident:player_01"].properties["affinity"] == 10
    assert graph.edges["relation:guide_npc:player_01"].properties["affinity"] == 5


async def test_graph_input_social_quiet_return_is_idempotent(tmp_path):
    repo = await _social_repo(tmp_path)
    llm = _FakeLLM(
        {
            "actions": [
                {
                    "verb": "speak",
                    "what": "quartermaster_npc",
                    "how": "deceptive",
                    "note": "quietly return missing supplies",
                }
            ]
        },
        narration="보급품은 선반 한쪽에 조용히 돌아옵니다.",
    )

    await run_graph_input_turn(llm, repo, "game-1", "보급품을 조용히 돌려놓습니다")
    await run_graph_input_turn(llm, repo, "game-1", "보급품을 조용히 돌려놓습니다")
    graph = await repo.load_graph("game-1")

    assert graph.nodes["q_missing_supplies"].properties["resolution_route"] == "quiet_return"
    relation = graph.edges["relation:village_resident:player_01"].properties
    assert relation["affinity"] == 6
    assert relation["flags"] == ["helped_quietly"]
```

- [ ] **Step 2: Run the new runtime tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_graph_input.py::test_graph_input_social_report_route_persists_quest_and_relations server/tests/game/runtime/test_graph_input.py::test_graph_input_social_mediation_requires_resident_reason server/tests/game/runtime/test_graph_input.py::test_graph_input_social_mediation_route_after_reason server/tests/game/runtime/test_graph_input.py::test_graph_input_social_quiet_return_is_idempotent -q
```

Expected: FAIL because `input.py` does not apply social quest graph changes yet.

- [ ] **Step 3: Add locale strings**

Append these entries to `server/src/locale/catalog/runtime.toml` near the existing `runtime.input.*` entries:

```toml
[runtime."social.missing_supplies.reason_known"]
ko = "주민은 누락된 보급품을 가져간 이유를 조심스럽게 털어놓습니다."
en = "The resident cautiously explains why the missing supplies were taken."

[runtime."social.missing_supplies.need_reason"]
ko = "보급 담당자는 판단을 미룹니다. 먼저 주민에게 사정을 확인해야 합니다."
en = "The quartermaster withholds judgment. You need to hear the resident's reason first."

[runtime."social.missing_supplies.report"]
ko = "당신은 주민의 일을 보급 담당자에게 보고합니다."
en = "You report the resident's action to the quartermaster."

[runtime."social.missing_supplies.mediate"]
ko = "당신은 주민의 사정을 전하고 보급 담당자를 설득합니다."
en = "You explain the resident's reason and persuade the quartermaster."

[runtime."social.missing_supplies.quiet_return"]
ko = "당신은 보급품을 조용히 제자리로 돌려놓습니다."
en = "You quietly return the supplies to their place."
```

- [ ] **Step 4: Update `input.py` imports**

Add these imports near existing imports in `server/src/game/runtime/input.py`:

```python
from src.game.engines.graph_social_quest import (
    SocialQuestResult,
    plan_social_quest_speak,
)

from .apply import apply_runtime_graph_changes
```

- [ ] **Step 5: Add social planner helper functions in `input.py`**

Add these helpers near `_run_graph_narrative_input`:

```python
def _plan_social_quest_input(
    runtime: GameRuntimeState,
    action,
    subject_id: str | None,
    player_input: str,
) -> SocialQuestResult | None:
    if action.verb != "speak":
        return None
    return plan_social_quest_speak(
        runtime.graph,
        player_id=runtime.progress.player_id,
        target_id=subject_id,
        how=action.how,
        player_input=player_input,
    )


def _social_fallback_text(
    runtime: GameRuntimeState,
    result: SocialQuestResult | None,
) -> str | None:
    if result is None:
        return None
    return render(result.message_key, runtime.progress.locale)
```

- [ ] **Step 6: Apply social changes in non-streaming speak path**

In `_run_graph_narrative_input`, replace the opening block:

```python
    subject_id = _resolve_narrative_subject(runtime, action)
    narration_result = await _generate_graph_input_narration(
        client,
        runtime,
        player_input,
        action,
        subject_id,
    )
```

with:

```python
    subject_id = _resolve_narrative_subject(runtime, action)
    social_result = _plan_social_quest_input(runtime, action, subject_id, player_input)
    if social_result is not None and social_result.changes:
        applied = apply_runtime_graph_changes(runtime, social_result.changes)
        runtime = applied.runtime
    if social_result is not None and social_result.kind == "blocked":
        narration_result = GraphNarrationResult(
            narration=_social_fallback_text(runtime, social_result) or ""
        )
    else:
        narration_result = await _generate_graph_input_narration(
            client,
            runtime,
            player_input,
            action,
            subject_id,
        )
```

Then after `next_runtime` is built and before `repo.append_log_entries(...)`, add:

```python
    if social_result is not None and social_result.changes:
        await repo.save_graph_changes(
            runtime.progress.game_id,
            next_runtime.graph,
            changed_node_ids=applied.changed_node_ids,
            changed_edge_ids=applied.changed_edge_ids,
            removed_edge_ids=applied.removed_edge_ids,
        )
```

- [ ] **Step 7: Apply social changes in streaming speak path**

In `_run_graph_narrative_input_stream`, add the same `social_result` and `applied` handling before streaming narration. For blocked results, skip `_stream_graph_input_narration` and use the social fallback text:

```python
    subject_id = _resolve_narrative_subject(runtime, action)
    social_result = _plan_social_quest_input(runtime, action, subject_id, player_input)
    if social_result is not None and social_result.changes:
        applied = apply_runtime_graph_changes(runtime, social_result.changes)
        runtime = applied.runtime
    stream = VisibleNarrationStream()
    if social_result is not None and social_result.kind == "blocked":
        fallback = _social_fallback_text(runtime, social_result) or ""
        if fallback:
            for visible in stream.push(fallback):
                yield {"type": "delta", "text": visible}
    else:
        async for chunk in _stream_graph_input_narration(
            client,
            runtime,
            player_input,
            action,
            subject_id,
        ):
            for visible in stream.push(chunk):
                yield {"type": "delta", "text": visible}
```

Then persist graph changes before appending logs:

```python
    if social_result is not None and social_result.changes:
        await repo.save_graph_changes(
            runtime.progress.game_id,
            next_runtime.graph,
            changed_node_ids=applied.changed_node_ids,
            changed_edge_ids=applied.changed_edge_ids,
            removed_edge_ids=applied.removed_edge_ids,
        )
```

- [ ] **Step 8: Run runtime tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_graph_input.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit runtime integration**

Run:

```powershell
git add server/src/game/runtime/input.py server/src/locale/catalog/runtime.toml server/tests/game/runtime/test_graph_input.py
git commit -m "feat: resolve missing supplies through speak input"
```

Expected: commit succeeds.

---

### Task 4: Add dev_test Scenario Content

**Files:**
- Create: `scenarios/dev_test/items/missing_supply_bundle.json`
- Create: `scenarios/dev_test/quests/q_missing_supplies.json`
- Modify: `scenarios/dev_test/characters/guide_npc.json`
- Modify: `scenarios/dev_test/characters/quartermaster_npc.json`
- Modify: `scenarios/dev_test/characters/village_resident.json`
- Modify: `scenarios/dev_test/chapters/ch_dev_test.json`
- Test: `server/tests/game/seed/test_graph_seed.py`

- [ ] **Step 1: Add seed converter test**

Append this test to `server/tests/game/seed/test_graph_seed.py`:

```python
def test_build_seed_graph_links_missing_supplies_social_quest():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="none"),
        races={"human": {"id": "human", "name": "인간", "description": ""}},
        locations={"hub": {"id": "hub", "name": "허브"}},
        items={
            "missing_supply_bundle": {
                "id": "missing_supply_bundle",
                "name": "누락된 보급품",
            }
        },
        skills={},
        npcs={
            "quartermaster_npc": {
                "id": "quartermaster_npc",
                "name": "보급 담당자",
                "race_id": "human",
                "location_id": "hub",
                "level": 1,
                "relations": {"player_01": 20},
            },
            "village_resident": {
                "id": "village_resident",
                "name": "마을 주민",
                "race_id": "human",
                "location_id": "hub",
                "level": 1,
                "relations": {"player_01": 0},
            },
            "guide_npc": {
                "id": "guide_npc",
                "name": "테스트 가이드",
                "race_id": "human",
                "location_id": "hub",
                "level": 1,
                "relations": {"player_01": 0},
            },
        },
        quests={
            "q_missing_supplies": {
                "id": "q_missing_supplies",
                "title": "보급품 누락",
                "summary": "보급품 누락을 관계 선택으로 해결합니다.",
                "giver_id": "quartermaster_npc",
                "difficulty": "easy",
                "status": "pending",
                "triggers": [
                    {
                        "id": "resolve_missing_supplies",
                        "name": "보급품 누락 해결",
                        "type": "item_obtained",
                        "target_id": "missing_supply_bundle",
                    }
                ],
                "rewards": {"gold": 1, "exp": 0},
            }
        },
        chapters={
            "ch_dev_test": {
                "id": "ch_dev_test",
                "title": "개발 테스트",
                "quest_ids": ["q_missing_supplies"],
            }
        },
        start={
            "start_location_id": "hub",
            "active_subject_id": None,
            "active_quest_id": None,
        },
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph
    assert graph.edges["gives_quest:quartermaster_npc:q_missing_supplies"].type == "gives_quest"
    assert graph.edges["target_of:resolve_missing_supplies:missing_supply_bundle:q_missing_supplies"].type == "target_of"
    assert graph.edges["part_of_chapter:q_missing_supplies:ch_dev_test"].type == "part_of_chapter"
    assert graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 20
    assert graph.edges["relation:village_resident:player_01"].properties["affinity"] == 0
    assert graph.edges["relation:guide_npc:player_01"].properties["affinity"] == 0
```

- [ ] **Step 2: Run the seed test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/seed/test_graph_seed.py::test_build_seed_graph_links_missing_supplies_social_quest -q
```

Expected: PASS because this test uses inline seed data and confirms the existing seed converter supports the needed graph shape.

- [ ] **Step 3: Create missing supply item**

Create `scenarios/dev_test/items/missing_supply_bundle.json`:

```json
{
  "id": "missing_supply_bundle",
  "name": "누락된 보급품",
  "description": "보급품 누락 관계 분기 퀘스트에 쓰는 작은 꾸러미입니다.",
  "kind": "quest",
  "effects": null,
  "price": 0,
  "weight": 1,
  "tags": ["quest", "social_test"]
}
```

- [ ] **Step 4: Create missing supplies quest**

Create `scenarios/dev_test/quests/q_missing_supplies.json`:

```json
{
  "id": "q_missing_supplies",
  "title": "보급품 누락",
  "summary": "보급품 누락을 고발, 중재, 조용한 반납 중 하나로 해결해 관계 변화를 확인합니다.",
  "description": "보급 담당자는 누락된 보급품을 찾고 있고, 마을 주민은 사정이 있어 그것을 가져갔습니다.",
  "giver_id": "quartermaster_npc",
  "difficulty": "easy",
  "status": "pending",
  "scope": "dev_test",
  "triggers": [
    {
      "id": "resolve_missing_supplies",
      "name": "보급품 누락 해결",
      "type": "item_obtained",
      "target_id": "missing_supply_bundle"
    }
  ],
  "fail_triggers": [],
  "rewards": {
    "gold": 1,
    "exp": 0
  },
  "triggers_met": [
    false
  ],
  "fail_triggers_met": []
}
```

- [ ] **Step 5: Update character seed hints and relations**

Update `scenarios/dev_test/characters/quartermaster_npc.json`:

- Keep existing fields.
- Ensure `"relations": { "player_01": 20 }` remains.
- Add this string to `hints`:

```json
"보급품 누락을 물으면 관계 분기 퀘스트를 시작할 수 있다."
```

Update `scenarios/dev_test/characters/village_resident.json`:

- Set `"relations": { "player_01": 0 }`.
- Add this string to `hints`:

```json
"누락된 보급품에는 주민의 사정이 연결되어 있다."
```

Update `scenarios/dev_test/characters/guide_npc.json`:

- Set `"relations": { "player_01": 0 }`.
- Add this string to `hints`:

```json
"보급품 누락 퀘스트는 고발, 중재, 조용한 반납으로 관계 변화가 달라진다."
```

- [ ] **Step 6: Add quest to chapter**

Modify `scenarios/dev_test/chapters/ch_dev_test.json` so `quest_ids` includes:

```json
"q_missing_supplies"
```

- [ ] **Step 7: Run seed validation**

Run:

```powershell
.\.venv\Scripts\python.exe server\scripts\check_seed.py scenarios\dev_test
```

Expected: `OK: scenarios\dev_test`.

- [ ] **Step 8: Commit scenario additions**

Run:

```powershell
git add scenarios/dev_test server/tests/game/seed/test_graph_seed.py
git commit -m "feat: add dev_test missing supplies quest"
```

Expected: commit succeeds.

---

### Task 5: Add Manual QA Instructions and Full Verification

**Files:**
- Modify: `tester.md`

- [ ] **Step 1: Add manual QA section**

In `tester.md`, add this section after the existing “퀘스트 확인” section:

```markdown
### 보급품 누락 관계 분기

각 루트는 새 게임에서 시작한다.

고발 루트:

1. `보급 구역으로 이동한다`
2. `보급 담당자에게 누락된 보급품을 묻는다`
3. `마을 주민을 보급 담당자에게 고발한다`

기대값: `보급품 누락` 퀘스트가 완료되고, 보급 담당자와의 관계는 좋아지며 주민과의 관계는 나빠진다. 로그는 고발로 해결했다는 장면 반응을 보여야 한다.

중재 루트:

1. `마을 주민에게 누락된 보급품을 가져간 이유를 묻는다`
2. `보급 구역으로 이동한다`
3. `보급 담당자에게 주민의 사정을 봐 달라고 설득한다`

기대값: 먼저 주민의 사정이 확인되고, 이후 설득으로 퀘스트가 완료된다. 주민과 가이드 관계가 좋아지고 보급 담당자 관계도 조금 좋아진다.

조용한 반납 루트:

1. `보급 구역으로 이동한다`
2. `보급품을 조용히 돌려놓는다`

기대값: 퀘스트가 조용한 반납으로 완료된다. 주민과의 관계가 좋아지고 `helped_quietly` 성격의 플래그가 저장된다.
```

- [ ] **Step 2: Run targeted server tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/engines/test_graph_social_quest.py server/tests/game/runtime/test_graph_input.py server/tests/game/seed/test_graph_seed.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full server tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS.

- [ ] **Step 4: Run lint and graph SSOT guard**

Run:

```powershell
.\.venv\Scripts\ruff.exe check server agency
bash server/scripts/check_relational_ssot.sh
```

Expected:

```text
All checks passed!
✅ relational SSOT guard: clean.
```

- [ ] **Step 5: Commit QA docs**

Run:

```powershell
git add tester.md
git commit -m "docs: add social quest qa checklist"
```

Expected: commit succeeds.

---

## Self-Review

Spec coverage:

- Scenario additions are covered by Task 4.
- Relation and quest route planning are covered by Tasks 1 and 2.
- Runtime `speak` integration is covered by Task 3.
- UI scope stays unchanged; verification uses logs, quest state, and save inspection as covered by Tasks 3 and 5.
- Error handling and idempotence are covered by Tasks 1 and 3.
- Manual QA is covered by Task 5.

Type consistency:

- The planner uses existing `GraphChange` models.
- The planner uses existing `speak.how` values: `friendly`, `hostile`, and `deceptive`.
- Relation edge ids match seed graph convention: `relation:<actor_id>:<player_id>`.
- Quest marker property is consistently named `resolution_route`.
