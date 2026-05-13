# Runtime Result Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 런타임 request 결과 구조를 한 곳으로 분리해서 `executed / rejected / answered / roll_required / confirmation_required / cancelled` 흐름을 읽기 쉽게 만든다.

**Architecture:** 새 `server/src/game/runtime/request_result.py`가 request status 타입, `GraphActionRequestResult`, 작은 factory helper를 맡는다. 기존 `confirmation.py`, `roll.py`, `input.py`는 이 타입과 helper를 가져다 쓰며 기존 API 응답과 동작은 바꾸지 않는다.

**Tech Stack:** Python 3.12, Pydantic v2, pytest.

---

## File Structure

- Create `server/src/game/runtime/request_result.py`: request status 타입, result model, helper 함수.
- Modify `server/src/game/runtime/confirmation.py`: result model 정의를 제거하고 새 module import로 교체.
- Modify `server/src/game/runtime/roll.py`: `GraphActionRequestResult` import 위치 변경, roll helper 사용.
- Modify `server/src/game/runtime/input.py`: `GraphActionRequestResult` import 위치 변경, 필요한 곳만 helper 사용.
- Modify `server/src/game/runtime/__init__.py`: 기존 외부 import surface가 깨지지 않도록 필요 시 re-export 조정.
- Test `server/tests/game/runtime/test_request_result.py`: 새 result helper의 status와 payload 보장.
- Existing tests: `server/tests/game/runtime/test_graph_confirmation.py`, `server/tests/game/runtime/test_graph_roll.py`, `server/tests/game/runtime/test_graph_input.py`.

---

### Task 1: Add Request Result Module

**Files:**
- Create: `server/src/game/runtime/request_result.py`
- Test: `server/tests/game/runtime/test_request_result.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/game/runtime/test_request_result.py`:

```python
from src.game.domain.progress import GameProgress
from src.game.domain.graph import Graph, GraphNode
from src.game.runtime.request_result import (
    GraphActionRequestResult,
    GraphRequestStatus,
    answered_result,
    cancelled_result,
    confirmation_required_result,
    executed_result,
    rejected_result,
    roll_required_result,
)
from src.game.runtime.state import GameRuntimeState
from src.wire.graph_to_front import graph_to_front_state


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01",
                    type="character",
                    properties={
                        "name": "테스터",
                        "hp": 10,
                        "max_hp": 10,
                        "mp": 5,
                        "max_mp": 5,
                        "alive": True,
                        "stats": {
                            "body": 10,
                            "agility": 10,
                            "mind": 10,
                            "presence": 10,
                        },
                    },
                )
            }
        ),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )


def test_request_status_literals_are_the_api_status_set():
    statuses: set[GraphRequestStatus] = {
        "executed",
        "rejected",
        "answered",
        "roll_required",
        "confirmation_required",
        "cancelled",
    }

    assert statuses == {
        "executed",
        "rejected",
        "answered",
        "roll_required",
        "confirmation_required",
        "cancelled",
    }


def test_result_helpers_set_only_the_relevant_pending_payload():
    runtime = _runtime()
    front_state = graph_to_front_state(runtime)

    confirmation = confirmation_required_result(
        runtime,
        front_state,
        {"id": "confirm_1", "kind": "quest_accept"},
    )
    roll = roll_required_result(
        runtime,
        front_state,
        {"id": "roll_1", "kind": "perceive"},
    )

    assert confirmation.status == "confirmation_required"
    assert confirmation.pending_confirmation == {"id": "confirm_1", "kind": "quest_accept"}
    assert confirmation.pending_roll is None
    assert roll.status == "roll_required"
    assert roll.pending_roll == {"id": "roll_1", "kind": "perceive"}
    assert roll.pending_confirmation is None


def test_terminal_result_helpers_keep_existing_response_shape():
    runtime = _runtime()
    front_state = graph_to_front_state(runtime)

    results = [
        executed_result(runtime, front_state),
        answered_result(runtime, front_state, "주변은 조용합니다."),
        rejected_result(runtime, front_state, "지금은 할 수 없습니다."),
        cancelled_result(runtime, front_state),
    ]

    assert [result.status for result in results] == [
        "executed",
        "answered",
        "rejected",
        "cancelled",
    ]
    assert results[1].message == "주변은 조용합니다."
    assert results[2].message == "지금은 할 수 없습니다."
    assert all(isinstance(result, GraphActionRequestResult) for result in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_request_result.py -q
```

Expected: FAIL because `src.game.runtime.request_result` does not exist.

- [ ] **Step 3: Add request result module**

Create `server/src/game/runtime/request_result.py`:

```python
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.wire.graph_to_front import GraphFrontStatePayload

from .dispatch import GraphActionDispatchResult
from .state import GameRuntimeState
from .suggestions import GraphSuggestionValue


GraphRequestStatus = Literal[
    "executed",
    "confirmation_required",
    "roll_required",
    "cancelled",
    "answered",
    "rejected",
]


class GraphActionRequestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    status: GraphRequestStatus
    front_state: GraphFrontStatePayload
    pending_confirmation: dict[str, Any] | None = None
    pending_roll: dict[str, Any] | None = None
    dispatch: GraphActionDispatchResult | None = None
    message: str | None = None
    suggestions: list[GraphSuggestionValue] = Field(default_factory=list)


def executed_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    *,
    dispatch: GraphActionDispatchResult | None = None,
    suggestions: list[GraphSuggestionValue] | None = None,
) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        front_state=front_state,
        dispatch=dispatch,
        suggestions=suggestions or [],
    )


def rejected_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    message: str | None = None,
    *,
    suggestions: list[GraphSuggestionValue] | None = None,
) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status="rejected",
        front_state=front_state,
        message=message,
        suggestions=suggestions or [],
    )


def answered_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    message: str,
) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status="answered",
        front_state=front_state,
        message=message,
    )


def roll_required_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    pending_roll: dict[str, Any],
) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status="roll_required",
        front_state=front_state,
        pending_roll=pending_roll,
    )


def confirmation_required_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    pending_confirmation: dict[str, Any],
) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status="confirmation_required",
        front_state=front_state,
        pending_confirmation=pending_confirmation,
    )


def cancelled_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status="cancelled",
        front_state=front_state,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_request_result.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/src/game/runtime/request_result.py server/tests/game/runtime/test_request_result.py
git commit -m "refactor(server): define graph request results"
```

---

### Task 2: Move Existing Request Result Imports

**Files:**
- Modify: `server/src/game/runtime/confirmation.py`
- Modify: `server/src/game/runtime/roll.py`
- Modify: `server/src/game/runtime/input.py`
- Modify: `server/src/game/runtime/__init__.py`

- [ ] **Step 1: Add compatibility import test**

Add this test to `server/tests/game/runtime/test_request_result.py`:

```python
def test_runtime_package_reexports_request_result():
    from src.game.runtime import GraphActionRequestResult
    from src.game.runtime.request_result import GraphActionRequestResult as Direct

    assert GraphActionRequestResult is Direct
```

- [ ] **Step 2: Run test to verify it fails if re-export is missing**

Run:

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_request_result.py::test_runtime_package_reexports_request_result -q
```

Expected: FAIL if `src.game.runtime` still re-exports from the old location or does not expose the name.

- [ ] **Step 3: Update `confirmation.py` imports and remove moved definitions**

In `server/src/game/runtime/confirmation.py`, remove:

```python
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
```

Replace it with:

```python
from typing import Any
```

Remove the `GraphRequestStatus` and `GraphActionRequestResult` definitions from this file.

Add imports from the new module:

```python
from .request_result import (
    GraphActionRequestResult,
    answered_result,
    cancelled_result,
    confirmation_required_result,
    executed_result,
)
```

Replace direct `GraphActionRequestResult(...)` calls in `confirmation.py`:

```python
return GraphActionRequestResult(
    runtime=runtime,
    status="answered",
    front_state=graph_to_front_state(runtime),
    message=answer_graph_query(runtime, action),
)
```

with:

```python
return answered_result(
    runtime,
    graph_to_front_state(runtime),
    answer_graph_query(runtime, action),
)
```

Replace executed returns with:

```python
return executed_result(
    result.runtime,
    result.front_state,
    dispatch=result.dispatch,
    suggestions=result.suggestions,
)
```

Replace confirmation returns with:

```python
return confirmation_required_result(
    next_runtime,
    graph_to_front_state(next_runtime),
    pending,
)
```

Replace cancel returns with:

```python
return cancelled_result(
    cleared_runtime,
    graph_to_front_state(cleared_runtime),
)
```

For stream final events, keep the surrounding `yield {"type": "final", "result": ...}` shape and only replace the result object construction.

- [ ] **Step 4: Update `roll.py` imports and helper use**

In `server/src/game/runtime/roll.py`, replace:

```python
from .confirmation import GraphActionRequestResult
```

with:

```python
from .request_result import (
    GraphActionRequestResult,
    executed_result,
    roll_required_result,
)
```

Replace the roll pending return:

```python
return GraphActionRequestResult(
    runtime=next_runtime,
    status="roll_required",
    front_state=graph_to_front_state(next_runtime),
    pending_roll=pending,
)
```

with:

```python
return roll_required_result(
    next_runtime,
    graph_to_front_state(next_runtime),
    pending,
)
```

Replace the roll resolved return:

```python
return GraphActionRequestResult(
    runtime=next_runtime,
    status="executed",
    front_state=graph_to_front_state(next_runtime),
)
```

with:

```python
return executed_result(
    next_runtime,
    graph_to_front_state(next_runtime),
)
```

- [ ] **Step 5: Update `input.py` imports**

In `server/src/game/runtime/input.py`, replace:

```python
from .confirmation import GraphActionRequestResult, run_graph_action_request
```

with:

```python
from .confirmation import run_graph_action_request
from .request_result import GraphActionRequestResult, rejected_result
```

Where `input.py` currently returns a rejected `GraphActionRequestResult(...)`, replace only that rejected construction with:

```python
return rejected_result(
    next_runtime,
    graph_to_front_state(next_runtime),
    suggestions=narration_result.suggestions,
)
```

This keeps the existing response shape: rejected narrative input currently carries suggestions but no `message`.

- [ ] **Step 6: Update package re-export**

In `server/src/game/runtime/__init__.py`, make sure `GraphActionRequestResult` is imported from `request_result`, not from `confirmation`.

Use:

```python
from .request_result import GraphActionRequestResult
```

Keep the existing public name unchanged.

- [ ] **Step 7: Run focused tests**

Run:

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_request_result.py server/tests/game/runtime/test_graph_confirmation.py server/tests/game/runtime/test_graph_roll.py server/tests/game/runtime/test_graph_input.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add server/src/game/runtime/confirmation.py server/src/game/runtime/roll.py server/src/game/runtime/input.py server/src/game/runtime/__init__.py server/tests/game/runtime/test_request_result.py
git commit -m "refactor(server): centralize graph request results"
```

---

### Task 3: Full Verification

**Files:**
- No production changes expected.

- [ ] **Step 1: Run full server tests**

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run client checks**

```powershell
cd D:\code\trpg\client
npm test -- --runInBand
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 3: Confirm old import location is gone**

Run:

```powershell
cd D:\code\trpg
rg -n "from \\.confirmation import GraphActionRequestResult|class GraphActionRequestResult|GraphRequestStatus" server/src/game/runtime
```

Expected:

```text
server/src/game/runtime/request_result.py:<line>:GraphRequestStatus = Literal[
server/src/game/runtime/request_result.py:<line>:class GraphActionRequestResult(BaseModel):
```

- [ ] **Step 4: Commit only if verification required small fixes**

If Task 3 required no code changes, skip this commit.

If fixes were needed:

```powershell
git add server/src/game/runtime/request_result.py server/src/game/runtime/confirmation.py server/src/game/runtime/roll.py server/src/game/runtime/input.py server/src/game/runtime/__init__.py server/tests/game/runtime/test_request_result.py
git commit -m "test: verify graph request result structure"
```
