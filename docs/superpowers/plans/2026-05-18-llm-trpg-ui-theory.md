# LLM TRPG UI Theory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply `docs/research/THEORY_UI.md` to the actual play UI by treating LLM narration as scene UI, fixed components as decision-state UI, and short-lived changes as temporary affordances.

**Architecture:** The server remains authoritative for game state and LLM-derived narration cues. The client renders server-composed narration verbatim, displays cue anchors under GM narration, and adds a compact decision strip derived from structured state. No client layer invents new game facts.

**Tech Stack:** FastAPI/Pydantic v2 server, Expo React Native client, NativeWind, Jest, pytest.

---

## File Structure

- Modify `server/src/game/domain/memory.py`
  - Add a small `NarrationCue` model and attach cues to GM log entries.
- Modify `server/src/game/runtime/narration/result.py`
  - Parse `ui_cues` from graph narration metadata.
  - Add a helper for creating GM log entries from narration results.
- Modify `server/src/game/runtime/flow/input.py`
  - Persist `ui_cues` on rejected-input and input narration GM logs.
- Modify `server/src/game/runtime/flow/roll.py`
  - Persist `ui_cues` on preroll and postroll narration GM logs.
- Modify `server/src/game/runtime/flow/turn.py`
  - Persist `ui_cues` on graph action narration GM logs.
- Modify `server/src/locale/prompts/graph_narrate/prompt.ko.md`
  - Teach the LLM to emit short cue anchors in metadata, not in prose.
- Modify `client/logic/log/types.ts`
  - Mirror the server cue shape in the GM log entry type.
- Modify `client/components/log/LogItem.tsx`
  - Render cue anchors under GM narration.
- Create `client/logic/decision-state/types.ts`
  - Define a compact state summary model.
- Create `client/logic/decision-state/buildDecisionState.ts`
  - Build fixed decision-state rows from `hero`, `quest`, `place`, `combat`, and latest GM cues.
- Create `client/logic/decision-state/index.ts`
  - Export builder, types, and view component.
- Create `client/components/decision-state/DecisionStateStrip.tsx`
  - Render fixed decision-state rows above the composer.
- Modify `client/screens/play/Playing.tsx`
  - Insert `DecisionStateStrip` between log/error area and input controls.
- Modify `client/locale/ko.ts`
  - Add client-owned labels for decision-state rows and cue accessibility labels.
- Add or modify tests:
  - `server/tests/game/runtime/test_suggestions.py`
  - `server/tests/game/runtime/test_graph_input.py`
  - `server/tests/wire/test_graph_to_front.py`
  - `client/components/log/__tests__/LogItem.test.ts`
  - `client/logic/decision-state/__tests__/buildDecisionState.test.ts`

---

### Task 1: Add Server Cue Contract

**Files:**
- Modify: `server/src/game/domain/memory.py`
- Modify: `server/src/game/runtime/narration/result.py`
- Test: `server/tests/game/runtime/test_suggestions.py`

- [ ] **Step 1: Write parser test for metadata cues**

Add this test to `server/tests/game/runtime/test_suggestions.py`:

```python
def test_parse_graph_narration_answer_accepts_ui_cues():
    answer = (
        "당신은 경비병의 발이 문턱에서 멈추는 것을 봅니다."
        "\n---TRPG_META---\n"
        '{"turn_summary":"","importance":1,'
        '"ui_cues":['
        '{"kind":"change","label":"변화","text":"경비병이 문 앞에서 멈춤","scope":"delta"},'
        '{"kind":"opportunity","label":"기회","text":"짧게 말을 걸 수 있음","scope":"temporary"}'
        '],'
        '"suggestions":[]}'
    )

    result = parse_graph_narration_answer(answer)

    assert result.narration == "당신은 경비병의 발이 문턱에서 멈추는 것을 봅니다."
    assert [cue.model_dump() for cue in result.ui_cues] == [
        {
            "kind": "change",
            "label": "변화",
            "text": "경비병이 문 앞에서 멈춤",
            "scope": "delta",
        },
        {
            "kind": "opportunity",
            "label": "기회",
            "text": "짧게 말을 걸 수 있음",
            "scope": "temporary",
        },
    ]
```

- [ ] **Step 2: Run test and confirm it fails**

Run from repo root:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_suggestions.py::test_parse_graph_narration_answer_accepts_ui_cues -q
```

Expected: fail because `GraphNarrationResult` has no `ui_cues`.

- [ ] **Step 3: Add cue models**

In `server/src/game/domain/memory.py`, add before `GMLogEntry`:

```python
class NarrationCue(BaseModel):
    kind: Literal["change", "constraint", "opportunity", "warning"]
    label: str
    text: str
    scope: Literal["delta", "temporary"] = "delta"
```

Then change `GMLogEntry`:

```python
class GMLogEntry(BaseModel):
    id: int
    kind: Literal["gm"]
    text: str
    outcome: Literal["success", "failure", "neutral"] | None = None
    cues: list[NarrationCue] = []

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        if data.get("outcome") is None:
            data.pop("outcome", None)
        if not data.get("cues"):
            data.pop("cues", None)
        return data
```

- [ ] **Step 4: Parse cues in narration result**

In `server/src/game/runtime/narration/result.py`, import `GMLogEntry` and `NarrationCue`:

```python
from src.game.domain.memory import DialoguePair, GMLogEntry, NarrationCue, TurnLogEntry
```

Extend `GraphNarrationResult`:

```python
class GraphNarrationResult(BaseModel):
    narration: str = ""
    turn_summary: str = ""
    importance: int = Field(default=1, ge=1, le=3)
    suggestions: list[GraphSuggestion] = Field(default_factory=list)
    ui_cues: list[NarrationCue] = Field(default_factory=list)
```

Add helpers near `_clean_suggestions`:

```python
def _max_ui_cues(default: int = 3) -> int:
    return _env_int("GRAPH_NARRATION_MAX_UI_CUES", default)


def _max_ui_cue_chars(default: int = 48) -> int:
    return _env_int("GRAPH_NARRATION_MAX_UI_CUE_CHARS", default)


def _clean_ui_cues(values: object) -> list[NarrationCue]:
    if not isinstance(values, list):
        return []
    out: list[NarrationCue] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        try:
            cue = NarrationCue.model_validate(value)
        except ValidationError:
            continue
        label = cue.label.strip()[:12]
        text = cue.text.strip()[: _max_ui_cue_chars()]
        if not label or not text:
            continue
        key = (cue.kind, text)
        if key in seen:
            continue
        seen.add(key)
        out.append(cue.model_copy(update={"label": label, "text": text}))
        if len(out) == _max_ui_cues():
            break
    return out
```

In `parse_graph_narration_answer`, pull `ui_cues` like suggestions:

```python
suggestions = raw.pop("suggestions", [])
ui_cues = raw.pop("ui_cues", [])
parsed = GraphNarrationResult.model_validate(
    {
        "narration": narration,
        **raw,
        "suggestions": _clean_suggestions(suggestions),
        "ui_cues": _clean_ui_cues(ui_cues),
    }
)
```

Add a creation helper:

```python
def gm_log_entry_from_narration(
    log_id: int,
    result: GraphNarrationResult,
    *,
    outcome: str | None = None,
) -> GMLogEntry:
    return GMLogEntry(
        id=log_id,
        kind="gm",
        text=result.narration,
        outcome=outcome,
        cues=result.ui_cues,
    )
```

- [ ] **Step 5: Run parser test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_suggestions.py::test_parse_graph_narration_answer_accepts_ui_cues -q
```

Expected: pass.

---

### Task 2: Persist Cues on GM Log Entries

**Files:**
- Modify: `server/src/game/runtime/flow/input.py`
- Modify: `server/src/game/runtime/flow/roll.py`
- Modify: `server/src/game/runtime/flow/turn.py`
- Test: `server/tests/game/runtime/test_graph_input.py`
- Test: `server/tests/wire/test_graph_to_front.py`

- [ ] **Step 1: Write runtime persistence test**

In `server/tests/game/runtime/test_graph_input.py`, update an existing fake-LLM narration test or add a narrow one using the existing `_FakeLLM` helper:

```python
async def test_graph_input_persists_narration_ui_cues(tmp_path):
    repo, runtime = await _ready_runtime(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "perceive"}]},
        narration=(
            "문틈 아래로 빛이 흔들립니다."
            "\n---TRPG_META---\n"
            '{"turn_summary":"","importance":1,'
            '"ui_cues":[{"kind":"opportunity","label":"기회","text":"문틈을 살필 수 있음","scope":"temporary"}],'
            '"suggestions":[]}'
        ),
    )

    events = [event async for event in stream_graph_input(repo, llm, runtime, "문틈을 살핀다")]
    logs = await repo.load_log_entries(runtime.progress.game_id)

    assert events[-1]["type"] == "final"
    assert logs[-1].kind == "gm"
    assert logs[-1].cues[0].text == "문틈을 살필 수 있음"
```

If `_ready_runtime` is not the local helper name in that file, reuse the existing fixture helper used by nearby graph input tests.

- [ ] **Step 2: Write wire serialization test**

In `server/tests/wire/test_graph_to_front.py`, extend the existing log serialization test to include a GM log with cues:

```python
GMLogEntry(
    id=2,
    kind="gm",
    text="나레이션입니다.",
    outcome="success",
    cues=[
        NarrationCue(
            kind="change",
            label="변화",
            text="북쪽 문이 잠김",
            scope="delta",
        )
    ],
)
```

Assert:

```python
assert payload.log[1].cues[0].text == "북쪽 문이 잠김"
```

- [ ] **Step 3: Run tests and confirm failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_input.py::test_graph_input_persists_narration_ui_cues server\tests\wire\test_graph_to_front.py -q
```

Expected: runtime test fails until GM log constructors use `gm_log_entry_from_narration`.

- [ ] **Step 4: Use helper in runtime flows**

In `server/src/game/runtime/flow/input.py`, import:

```python
from src.game.runtime.narration.result import gm_log_entry_from_narration
```

Replace GM log construction that uses `narration_result.narration` with:

```python
entry = gm_log_entry_from_narration(
    runtime.progress.next_log_id,
    narration_result,
)
```

In `server/src/game/runtime/flow/roll.py`, replace narration-result GM entries with:

```python
entry = gm_log_entry_from_narration(
    runtime.progress.next_log_id,
    narration_result,
)
```

In `server/src/game/runtime/flow/turn.py`, replace graph action narration entry creation with:

```python
entry = gm_log_entry_from_narration(
    next_runtime.progress.next_log_id,
    narration_result,
    outcome=narration_outcome or outcome_from_dispatch(prepared.dispatch),
)
```

Do not change deterministic non-LLM fallback entries unless they already pass through `GraphNarrationResult`.

- [ ] **Step 5: Run focused server tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_suggestions.py server\tests\game\runtime\test_graph_input.py::test_graph_input_persists_narration_ui_cues server\tests\wire\test_graph_to_front.py -q
```

Expected: pass.

---

### Task 3: Update Graph Narration Prompt Contract

**Files:**
- Modify: `server/src/locale/prompts/graph_narrate/prompt.ko.md`
- Test: `server/tests/game/runtime/test_suggestions.py`

- [ ] **Step 1: Update the required metadata shape**

Change the required output example near the top from:

```text
{"turn_summary":"","importance":1,"suggestions":[]}
```

to:

```text
{"turn_summary":"","importance":1,"ui_cues":[],"suggestions":[]}
```

- [ ] **Step 2: Add cue rules under metadata**

Add this after `importance` and before `suggestions`:

```markdown
`ui_cues`:
- 0개에서 3개까지입니다.
- 나레이션 본문에서 놓치면 다음 선택이 흔들리는 변화, 제약, 기회, 위험만 씁니다.
- 전체 상태표가 아닙니다.
- 숨은 정보, 내부 수치, 확정되지 않은 미래 결과를 쓰지 않습니다.
- 모든 행동 가능성을 나열하지 않습니다.
- 각 항목은 반드시 이 형태입니다.

{"kind":"change","label":"변화","text":"은신 해제","scope":"delta"}

허용 `kind`:
`change`, `constraint`, `opportunity`, `warning`

허용 `scope`:
`delta`, `temporary`

`temporary`는 다음 입력 동안만 선택을 바꾸는 짧은 기회나 위험에 씁니다.
```

- [ ] **Step 3: Run parser tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_suggestions.py -q
```

Expected: pass.

---

### Task 4: Render Narration Cues in Log

**Files:**
- Modify: `client/logic/log/types.ts`
- Modify: `client/components/log/LogItem.tsx`
- Modify: `client/components/log/__tests__/LogItem.test.ts`
- Modify: `client/locale/ko.ts`

- [ ] **Step 1: Update client log types**

In `client/logic/log/types.ts`, add:

```ts
export type NarrationCue = {
  kind: 'change' | 'constraint' | 'opportunity' | 'warning';
  label: string;
  text: string;
  scope?: 'delta' | 'temporary';
};
```

Change the GM log entry to:

```ts
| {
    id: number;
    kind: 'gm';
    text: string;
    outcome?: LogOutcome | null;
    cues?: NarrationCue[];
  }
```

- [ ] **Step 2: Add cue locale labels**

In `client/locale/ko.ts`, add:

```ts
cue: {
  groupLabel: '장면 변화',
},
```

- [ ] **Step 3: Write log rendering test**

Add to `client/components/log/__tests__/LogItem.test.ts`:

```ts
test('renders GM narration cues as compact anchors below narration', () => {
  expect(source).toContain('function NarrationCues');
  expect(source).toContain('entry.cues');
  expect(source).toContain('ko.cue.groupLabel');
  expect(source).toContain('cue.label');
  expect(source).toContain('cue.text');
});
```

- [ ] **Step 4: Render cues under GM narration**

In `client/components/log/LogItem.tsx`, import `ko`:

```ts
import { ko } from '@/locale/ko';
```

Add:

```tsx
function cueToneClass(kind: NonNullable<Extract<LogEntry, { kind: 'gm' }>['cues']>[number]['kind']): string {
  if (kind === 'warning') return 'border-danger-fg bg-danger-muted text-danger-fg';
  if (kind === 'opportunity') return 'border-success-fg bg-success-muted text-success-fg';
  if (kind === 'constraint') return 'border-attention-fg bg-attention-muted text-attention-fg';
  return 'border-border-default bg-canvas-inset text-fg-muted';
}

function NarrationCues({ cues }: { cues: NonNullable<Extract<LogEntry, { kind: 'gm' }>['cues']> }) {
  if (cues.length === 0) return null;
  return (
    <View
      className="mt-2 flex-row flex-wrap gap-1.5"
      accessibilityLabel={ko.cue.groupLabel}
    >
      {cues.map((cue, index) => (
        <View
          key={`${cue.kind}:${cue.text}:${index}`}
          className={`rounded-sm border px-2 py-1 ${cueToneClass(cue.kind)}`}
        >
          <Text className="font-sans-semibold text-caption">
            {cue.label}
          </Text>
          <Text className="font-sans text-caption">
            {cue.text}
          </Text>
        </View>
      ))}
    </View>
  );
}
```

Then render it at the end of `GMNarration`:

```tsx
{entry.cues && entry.cues.length > 0 ? <NarrationCues cues={entry.cues} /> : null}
```

If any token class such as `bg-danger-muted` does not exist, use existing token-backed classes from `tailwind.config.js`; do not hardcode colors.

- [ ] **Step 5: Run focused client test**

Run from `client/`:

```powershell
npm test -- components/log/__tests__/LogItem.test.ts --runInBand
```

Expected: pass.

---

### Task 5: Add Fixed Decision State Strip

**Files:**
- Create: `client/logic/decision-state/types.ts`
- Create: `client/logic/decision-state/buildDecisionState.ts`
- Create: `client/logic/decision-state/index.ts`
- Create: `client/components/decision-state/DecisionStateStrip.tsx`
- Create: `client/logic/decision-state/__tests__/buildDecisionState.test.ts`
- Modify: `client/screens/play/Playing.tsx`
- Modify: `client/locale/ko.ts`

- [ ] **Step 1: Add locale labels**

In `client/locale/ko.ts`, add:

```ts
decision: {
  title: '현재 판단 기준',
  place: '장소',
  goal: '목표',
  risk: '위험',
  status: '상태',
  temporary: '이번 선택',
},
```

- [ ] **Step 2: Define decision-state types**

Create `client/logic/decision-state/types.ts`:

```ts
export type DecisionStateTone = 'neutral' | 'accent' | 'warning' | 'danger';

export type DecisionStateItem = {
  id: string;
  label: string;
  text: string;
  tone: DecisionStateTone;
  temporary?: boolean;
};
```

- [ ] **Step 3: Write builder tests**

Create `client/logic/decision-state/__tests__/buildDecisionState.test.ts`:

```ts
import { buildDecisionState } from '../buildDecisionState';

describe('buildDecisionState', () => {
  test('keeps current place and first active quest goal visible', () => {
    const items = buildDecisionState({
      place: { id: 'town', name: '마을', description: '', exits: [], items: [], targets: [] },
      quest: {
        id: 'q1',
        title: '북문 조사',
        summary: '북문을 확인합니다.',
        giver: '경비대장',
        difficulty: { label: '보통' },
        goals: ['북문 흔적 확인'],
        progressLabel: '',
        rewards: { gold: 0, exp: 0 },
        status: 'active',
        actions: [],
      },
      combat: null,
      heroStatus: [],
      latestCues: [],
    });

    expect(items.map((item) => item.text)).toEqual(['마을', '북문 흔적 확인']);
  });

  test('promotes temporary cue for the next input only', () => {
    const items = buildDecisionState({
      place: null,
      quest: null,
      combat: null,
      heroStatus: [],
      latestCues: [
        { kind: 'opportunity', label: '기회', text: '문틈을 살필 수 있음', scope: 'temporary' },
      ],
    });

    expect(items).toEqual([
      {
        id: 'cue:0',
        label: '이번 선택',
        text: '문틈을 살필 수 있음',
        tone: 'accent',
        temporary: true,
      },
    ]);
  });
});
```

- [ ] **Step 4: Implement builder**

Create `client/logic/decision-state/buildDecisionState.ts`:

```ts
import { ko } from '@/locale/ko';
import type { CombatBadge } from '@/logic/combat';
import type { Quest } from '@/logic/quest';
import type { Place } from '@/logic/story-graph';
import type { NarrationCue } from '@/logic/log';
import type { DecisionStateItem } from './types';

type Input = {
  place: Place | null;
  quest: Quest | null;
  combat: CombatBadge | null;
  heroStatus: string[];
  latestCues: NarrationCue[];
};

export function buildDecisionState(input: Input): DecisionStateItem[] {
  const items: DecisionStateItem[] = [];

  if (input.place) {
    items.push({ id: 'place', label: ko.decision.place, text: input.place.name, tone: 'neutral' });
  }

  const firstGoal = input.quest?.goals[0]?.trim();
  if (firstGoal) {
    items.push({ id: 'goal', label: ko.decision.goal, text: firstGoal, tone: 'accent' });
  }

  if (input.combat) {
    items.push({
      id: 'combat',
      label: ko.decision.risk,
      text: input.combat.turnLabel,
      tone: input.combat.enemyPressure > 0 ? 'danger' : 'warning',
    });
  }

  for (const status of input.heroStatus.slice(0, 2)) {
    items.push({ id: `status:${status}`, label: ko.decision.status, text: status, tone: 'warning' });
  }

  input.latestCues.forEach((cue, index) => {
    if (cue.scope !== 'temporary') return;
    items.push({
      id: `cue:${index}`,
      label: ko.decision.temporary,
      text: cue.text,
      tone: cue.kind === 'warning' ? 'danger' : 'accent',
      temporary: true,
    });
  });

  return items.slice(0, 5);
}
```

- [ ] **Step 5: Export decision-state module**

Create `client/logic/decision-state/index.ts`:

```ts
export { DecisionStateStrip } from '@/components/decision-state/DecisionStateStrip';
export { buildDecisionState } from './buildDecisionState';
export type { DecisionStateItem, DecisionStateTone } from './types';
```

- [ ] **Step 6: Implement strip component**

Create `client/components/decision-state/DecisionStateStrip.tsx`:

```tsx
import { ScrollView, Text, View } from 'react-native';
import { ko } from '@/locale/ko';
import type { DecisionStateItem, DecisionStateTone } from '@/logic/decision-state/types';

function toneClass(tone: DecisionStateTone): string {
  if (tone === 'danger') return 'border-danger-fg bg-danger-muted text-danger-fg';
  if (tone === 'warning') return 'border-attention-fg bg-attention-muted text-attention-fg';
  if (tone === 'accent') return 'border-accent-fg bg-accent-muted text-accent-fg';
  return 'border-border-default bg-canvas-inset text-fg-muted';
}

export function DecisionStateStrip({ items }: { items: DecisionStateItem[] }) {
  if (items.length === 0) return null;
  return (
    <View className="border-t border-border-default bg-canvas-default px-5 py-2">
      <Text className="mb-1 font-sans-semibold text-caption text-fg-muted">
        {ko.decision.title}
      </Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ gap: 6, paddingRight: 16 }}
      >
        {items.map((item) => (
          <View
            key={item.id}
            className={`max-w-56 rounded-sm border px-2 py-1 ${toneClass(item.tone)}`}
          >
            <Text className="font-sans-semibold text-caption" numberOfLines={1}>
              {item.label}
            </Text>
            <Text className="font-sans text-caption" numberOfLines={1}>
              {item.text}
            </Text>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}
```

If a tone class does not exist in Tailwind tokens, replace it with existing token-backed classes before running tests.

- [ ] **Step 7: Wire into `Playing`**

In `client/screens/play/Playing.tsx`, import:

```ts
import { buildDecisionState, DecisionStateStrip } from '@/logic/decision-state';
```

Add before `return`:

```ts
const latestGm = [...log].reverse().find((entry) => entry.kind === 'gm');
const decisionItems = buildDecisionState({
  place,
  quest,
  combat,
  heroStatus: hero.status,
  latestCues: latestGm?.cues ?? [],
});
```

Render after the error message block and before `KeyboardAvoidingView`:

```tsx
<DecisionStateStrip items={decisionItems} />
```

- [ ] **Step 8: Run focused client tests**

Run from `client/`:

```powershell
npm test -- logic/decision-state/__tests__/buildDecisionState.test.ts components/log/__tests__/LogItem.test.ts --runInBand
```

Expected: pass.

---

### Task 6: Verification Pass

**Files:**
- No new files unless tests reveal a narrow defect.

- [ ] **Step 1: Run server focused tests**

Run from repo root:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_suggestions.py server\tests\game\runtime\test_graph_input.py::test_graph_input_persists_narration_ui_cues server\tests\wire\test_graph_to_front.py -q
```

Expected: pass.

- [ ] **Step 2: Run client tests**

Run from `client/`:

```powershell
npm test -- --runInBand
```

Expected: pass.

- [ ] **Step 3: Type-check client**

Run from `client/`:

```powershell
npx tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 4: Lint client**

Run from `client/`:

```powershell
npm run lint
```

Expected: no lint errors.

- [ ] **Step 5: Run server focused lint**

Run from repo root:

```powershell
.\.venv\Scripts\ruff.exe check server
```

Expected: no lint errors.

---

## Self-Review

Spec coverage:
- Narration as scene UI: Tasks 1, 3, 4.
- Fixed UI as decision state: Task 5.
- Structured state authority: Tasks 1, 2, 5.
- Highlighted deltas and temporary affordances: Tasks 1, 3, 4, 5.
- No hidden-info leakage: Task 3 prompt rules and Task 1 parser allowlist.

Known tradeoff:
- This plan adds one compact decision strip rather than redesigning the whole play screen. Existing `HeroStrip`, `ContextCard`, `CombatStrip`, and `Composer` remain intact.
- The first implementation depends on LLM metadata for cue quality. If cues are missing, the UI remains playable because fixed state is still built from structured state.

Implementation order:
1. Server cue contract and persistence.
2. Prompt metadata contract.
3. Client cue rendering.
4. Client decision strip.
5. Focused tests, then broad client checks.
