# continue — 라운드 1·2 완료, 라운드 3 폴더 분할 인계

이 문서는 본 세션의 합의 결과 + 작업 내역을 새 세션이 그대로 이어받기 위한 정리입니다. 결정 굳은 항목은 흔들지 말고, 굳지 않은 미정 항목은 새 세션에서 정합니다.

원본 큰 그림: `0505.md` (서버 6분할 — locale / llm / game / wire(통역기) / api / persistence. 라운드 2 finale 후 4 → 6 갱신; 자세한 결정 근거는 0505 §2 참조)

---

## 0. 봐야할 문서 (새 세션 시작 시)

### 필수 읽기 (이 순서대로)

| # | 경로 | 왜 |
|---|---|---|
| 1 | `continue.md` (이 파일) | 본 세션 인계 — 어디까지 왔고 다음 뭘 할지 |
| 2 | `0505.md` | 큰 그림 6분할 plan. §1 통증 분리, §2 6분할 (4 → 6 갱신 근거 포함), §4 첫 케이스 결, §5 두 갈래 진행, §9 합의 굳음 |
| 3 | `CLAUDE.md` (repo root) | 한국어 정책, env 정책, save isolation, 스택 |
| 4 | `server/CLAUDE.md` | 레이어 룰, 관계 SSOT, 에러 hierarchy, 명명 규칙 (Tier ASCII enum 등 1.1 결과 반영됨) |
| 5 | `client/CLAUDE.md` | 클라 폴더 룰, wire 타입 위치 (`types/wire.ts`), 디자인 토큰 |

자동 로드 (별도 명시 안 해도 들어옴):
- `~/.claude/projects/-home-kn-code-trpg/memory/MEMORY.md` 인덱스 + 그 안 7개 메모리 파일 (§3 "메모리 / 피드백" 참조)

### 참조용 (필요할 때 보면 됨)

#### sub-round 진행 plan (작업 패턴 참조)

| 경로 | 무엇 |
|---|---|
| `docs/superpowers/plans/2026-05-05-locale-sub-round-1-2-stat-labels.md` | 작은 sub-round 패턴 (3 task, mechanical) |
| `docs/superpowers/plans/2026-05-05-locale-sub-round-1-3-system-messages.md` | 큰 sub-round 패턴 (8 task, 패턴 굳히기) |
| `docs/superpowers/plans/2026-05-05-locale-sub-round-1-4-residue.md` | 잔재 정리 패턴 (3 task) |
| `docs/superpowers/plans/2026-05-05-locale-sub-round-1-5-llm-input-labels.md` | prompt.toml 도입 + multi-line template |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-0-emit-error-extension.md` | emit_error 시그니처 확장 |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-1-pending-check-payload.md` | **첫 큰 페이로드 패턴 — 2.2~2.5의 템플릿** |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-2-hero-payload.md` | hero 페이로드 (camelCase `_CamelModel` 도입, 4 sub-model atom) |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-3-subject-payload.md` | subject 페이로드 + dead helper cleanup |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-4-quest-payload.md` | quest + 신규 sub-model 첫 도입 (DifficultyBadge, QuestRewards, Literal 좁힘) |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-5-place-payload.md` | place + 3 신규 sub-model |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-6-judge-event.md` | **첫 SSE 이벤트 (RootModel + discriminated union 검증 자리)** |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-7-log-entry-event.md` | log_entry (RootModel + 도메인 모델 재사용) |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-8-simple-events.md` | narrative_delta + suggestions + done 묶음 |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-9-combat-events.md` | combat_start/turn/end (라운드 2 SSE finale) |
| `docs/superpowers/plans/2026-05-05-wire-sub-round-2-10-combat-badge.md` | mapping last mile — to_combat 위임 |

#### 패턴 참조 코드

| 무엇 | 어디 |
|---|---|
| catalog 파일 형식 (단일/다중 segment 키, 조사 토큰) | `server/src/locale/catalog/*.toml` (7개: error/tier/phase/stat/log/ui/prompt) |
| render() 구현 + 조사 토큰 walker | `server/src/locale/render.py` |
| 조사 함수 (`i_ga`, `eun_neun` 등) | `server/src/locale/particles.py` |
| Wire 모델 패턴 (단순 BaseModel) | `server/src/wire/models/error.py`, `wire/models/pending_check.py`, `wire/models/done.py` |
| Wire 모델 패턴 (camelCase) | `server/src/wire/models/hero.py` (`_CamelModel` base 정의) |
| Wire 모델 패턴 (RootModel discriminated union) | `server/src/wire/models/judge.py`, `wire/models/log_entry.py` |
| Wire 빌더 패턴 (kwargs / payload-or-dict) | `server/src/wire/emit.py` (16 빌더 + 6 헬퍼) |
| Codegen export + `_flatten` 헬퍼 ($defs hoist + nested ref rewrite) | `server/src/wire/export.py` (15 _MODELS) |
| Wire `__init__` public API | `server/src/wire/__init__.py` |
| 클라 wire alias re-export 패턴 | `client/types/wire.ts`, `client/features/<x>/types.ts` (모두 wire.gen alias) |
| 단위 테스트 패턴 (wire) | `server/tests/wire/test_*.py` (101 tests) |
| Catalog 무결성 테스트 | `server/tests/locale/test_catalog_integrity.py` |
| Render token-walker 단위 테스트 | `server/tests/locale/test_render_particles.py` |

#### 도메인 / 게임 컨텍스트 (디자인 의도)

| 경로 | 무엇 |
|---|---|
| `docs/01-overview.md` ~ `docs/05-codemap.md` | gitignored 디자인 노트 (rationale, per-turn flow). 새 세션에서 큰 디자인 결정 필요할 때 참조 |
| `server/src/domain/errors.py` | DomainError 계층 (session lifecycle vs action validation 분리 — CLAUDE.md "Error hierarchy" 참조) |
| `server/src/domain/memory.py` | `PendingCheck` + `LogEntry` discriminated union (4 sub-class) 등 게임 상태 도메인 모델 |
| `server/src/domain/state.py` | `GameState` (게임 진행 SSOT), `CombatState` |
| `server/src/domain/verb.py` | `Verb` / `RefuseReason` / `VerbName` Literal — judge SSE에서 wire 측이 재사용 |
| `server/src/ontology/graph.py` | 관계 SSOT (CLAUDE.md "Relational SSOT" 참조) |

### 문서 읽기 우선순위

- **새 세션 첫 답변 전**: 1+2 (continue.md + 0505.md). 나머지는 task에 따라 ad-hoc.
- **첫 폴더 분할 sub-round 시작 전**: 라운드 3은 mechanical migration, 별도 plan 패턴 없음. 영향 범위 grep 후 atomic file move + import 갱신.
- **catalog 늘릴 때**: 기존 catalog 파일 형식 grep 으로 확인

---

## 1. 어디까지 왔는가

### 라운드 1 (locale, 통증 B) — 5/6 sub-round 완료, 1.6 미루기 유지

| sub-round | 상태 | PR | 산물 |
|---|---|---|---|
| 1.1 | ✅ main | (squash) | Tier/Phase ASCII enum 전환, `tier.toml`/`phase.toml` 신설 |
| 1.2 | ✅ main | #4 | `stat.toml` (6 stat 라벨), `mapping/labels.py:stat_label` catalog-backed |
| 1.3 | ✅ main | #5 | `render()` 조사 토큰 처리, `log.toml`(80+) + `ui.toml`(22) 본진. `flow/format.py` 30+ 함수 + `flow/error_phrases.py` 28 phrases + `mapping/labels.py` 잔여 모두 catalog |
| 1.4 | ✅ main | #6 | flow 산재 13줄 + engines/quest+perspective 8줄 + format 아이템 fallback. `eun_neun` import 제거. perspective marker invariant 명시 |
| 1.5 | ✅ main | #7 | `prompt.toml` 신설 (12 entries: history.* + judge.*). `context/layers.py` history headers + `flow/judge.py:judge_quest_progress` prompt 카탈로그 |
| **1.6** | ⏳ 미루기 | — | LLM 프롬프트 `.md` 파일 (kernel + 5 agents). 라운드 3 (폴더 분할) 후 검토 |

### 라운드 2 (wire, 통증 A) — **모든 sub-round 완료** ✅

| sub-round | 상태 | PR | 산물 |
|---|---|---|---|
| 2.0 | ✅ main | #8 | `emit_error` 시그니처 확장 (옵션 A: `code_or_exc: str \| Exception` + `message=` + `**vars`). 새 catalog 2개. 5 raw dict 사이트 마이그레이션 |
| 2.1 | ✅ main | #9 | `PendingCheckPayload` + `TierBadge` 모델, `emit_pending_check` 빌더, `_build_pending_check_payload` SSOT 헬퍼. **codegen 파이프라인 첫 통과** — `_flatten` ($defs → definitions hoist) |
| 2.2 | ✅ main | #10 | `HeroPayload` (21 필드) + 4 atom sub-model (`StatEntry`/`EquipItem`/`Equipment`/`InventoryItem`). **`_CamelModel` base 도입** (camelCase alias). codegen 버그 수정 — hoisted sub-schema 안 `$defs` ref도 재작성 |
| 2.3 | ✅ main | #11 | `SubjectPayload` (14 필드, mp 의도적 부재). 4 sub-model 재사용. **dead helper cleanup** — `_equipment`/`_inventory`/`_skill_names`/`_companion_label` 4 helper 삭제 |
| 2.4 | ✅ main | #12 | `QuestPayload` (11 필드) + 신규 sub-model 2 (`DifficultyBadge` 5-literal tone, `QuestRewards` items 미노출). status/actions Literal 좁힘 |
| 2.5 | ✅ main | #13 | `PlacePayload` (8 필드) + 신규 sub-model 3 (`RiskBadge` 3-literal, `PlaceSurrounding`, `PlaceTarget`). 5 큰 페이로드 모두 완료 |
| 2.6 | ✅ main | #14 | `JudgePayload` **RootModel + discriminated union** (4 judge_kind). 4 emit 빌더. domain `Verb`/`RefuseReason` 재사용. 0505.md §4의 "discriminated union 자동 생성" 검증 통과 |
| 2.7 | ✅ main | #15 | `LogEntryPayload` RootModel union. domain `GMLogEntry`/`PlayerLogEntry`/`ActLogEntry`/`RollLogEntry` 재사용 (이미 domain.memory에 정의됨). 단일 `emit_log_entry` 빌더 |
| 2.8 | ✅ main | #16 | `narrative_delta` + `suggestions` + `done` 3 단순 SSE 이벤트 묶음 (각 BaseModel + emit 빌더). `DonePayload` 빈 BaseModel |
| 2.9 | ✅ main | #17 | `combat_start` / `combat_turn` / `combat_end` 3 SSE 이벤트. `CombatTurnPayload` 통합 schema (`item_id` 추가로 두 emit 사이트 shape 통합) |
| 2.10 | ✅ main | #18 | `CombatBadgePayload` (3 필드) + `CombatEnemy` (4 필드, camelCase). **mapping/to_front.py 5 함수 모두 wire 위임 완료** — mapping/은 거의 빈 폴더 |

### 라운드 2 결과 정량

- **wire 모델 33+ 개** (top-level 15 + sub-model 18+). `wire/export.py:_MODELS`에 15 entries.
- **emit 빌더 16개** (`emit_error`, `emit_pending_check`, 4 emit_judge_*, `emit_log_entry`, `emit_narrative_delta`, `emit_suggestions`, `emit_done`, `emit_combat_start/turn/end`)
- **상태 슬롯 헬퍼 6개** (`_build_*_payload`: pending_check / hero / subject / quest / place / combat_badge)
- **wire 단위 테스트 101 PASS** (10 emit_error + 2 export + 4 pending_check + 6 hero + 10 subject + 14 quest + 10 place + 9 judge + 8 log_entry + 9 simple + 12 combat + 7 combat_badge)
- **클라 손작성 wire 타입 거의 모두 wire.gen alias로 교체** — `features/<x>/types.ts` 파일 모두 alias re-export. caller churn 0.
- **mapping/to_front.py 5 main 함수 + pending_check_to_front** 모두 wire 위임. `to_front_state`만 orchestrator로 남음.
- **server raw `"type": "..."` dict 발사 잔재 0** — 모든 SSE는 emit 빌더 통과.

### docs 커밋

| 커밋 | 내용 |
|---|---|
| `374ba6e` | docs: continue.md — 라운드 1·2 진행 인계 (초기) |
| `9f41ca8` | docs: continue.md — 봐야할 문서 섹션 추가 |
| `20b5451` | docs: 4 → 6분할 갱신 (api/persistence 1급 분리, 라운드 2 finale 후) |

main HEAD: `590efc5` (PR #18 머지 후, 라운드 2 finale).

---

## 2. 굳은 결정 — 흔들지 말 것

### 큰 그림

- **서버 6분할** (locale / llm / game / wire(통역기) / api / persistence). 0505.md §2·§9 합의 굳음 (라운드 2 finale 후 4 → 6 갱신).
- **통역기 위치**: 서버 안 (옵션 A). 별도 패키지(B)는 형태 잡힌 후.
- **다국어 모델**: W (풀 i18n + 한 곳 관리).
- **첫 케이스**: 에러 메시지 한 종류 (이미 1.1 시점에 통과).
- **인간 가독성도 통증** — 0505.md §1 갱신. 위계 정리는 분할의 부산물 + 그 자체 가치.

### 라운드 단위 (사용자 요청 패턴)

- **PR per sub-round, squash merge** — 각 sub-round 끝나면 main에 squash 머지 후 다음 sub-round 새 branch.
- **Branch 명명**: `refactor/<round>-<sub>-<topic>` (예: `refactor/locale-1.4-residue`, `refactor/wire-2.10-combat-badge`).
- **각 task당 spec + quality 두 리뷰** — implement → spec compliance review (subagent) → code quality review (subagent) → next task.
- **mechanical task는 직접 검증** (subagent 거치지 않음) — 본 세션 후반에 시간 절약 위해 도입. 기준: 단일-파일 mechanical migration + JSON parity 명확.

### Catalog 패턴 (라운드 1에서 굳음)

- 위치: `server/src/locale/catalog/<domain>.toml` (7 카탈로그: error / tier / phase / stat / log / ui / prompt)
- 키 형태:
  - 단일 segment: `[domain.name]` plain (예: `[error.llm_unavailable]`, `[log.equip]`)
  - 2+ segment: `[domain."seg1.seg2"]` 인용 (예: `[log."error.hp_full"]`, `[ui."story.edge.current"]`)
  - 이유: render의 `partition(".")`이 첫 dot에서만 분할 → 그 뒤가 단일 dict key
- 변수 보간: `{varname}` placeholder
- 조사 토큰: `{이/가}` `{은/는}` `{을/를}` `{과/와}` `{으로/로}` — 직전 변수 받침 보고 자동 선택
- TOML triple-quoted `"""..."""` for multi-line templates (`prompt.judge.quest_evaluator` 사례)

### Render API

```python
from ..locale import render

render(key, locale, **vars) -> str
```

- `key = "domain.name"` (한 dot)
- `key = "domain.seg1.seg2"` (여러 dot — TOML quoted-key 형식과 정합)
- `**vars` for variable substitution + 조사 token resolution
- KeyError on missing variable (no silent fallback)
- 모듈 import-time에 호출해 상수 만드는 패턴 OK (catalog cached)

### Wire 빌더 패턴 (라운드 2에서 굳음)

- **단순 BaseModel** (대부분): `wire/models/<event>.py`에 Pydantic `<Event>Payload` + 필요시 sub-model
- **`_CamelModel` base** (camelCase alias 필요 시): `wire/models/hero.py`에 정의. `serialize_by_alias=True`로 `model_dump()` 자동 camel
- **RootModel discriminated union** (judge / log_entry): `Annotated[A | B | C, Field(discriminator="kind")]`로 wrap. `model_dump()` unwrap 자동.
- 빌더: `wire/emit.py`에 `emit_<event>(...)` — `{"type": "<event>", "data": payload.model_dump()}` 반환
- 헬퍼: `_build_<event>_payload(state, ...) -> <Event>Payload | None` — state slot용. None gating은 mapping의 기존 결정 그대로 mirror.
- `emit_error` 시그니처: `code_or_exc: str | Exception, *, locale="ko", message=None, **vars` (옵션 A 옵션)

### 자동 생성 파이프라인

- `wire/export.py:_MODELS` list에 모델 추가 (15 entries 현재)
- `_flatten` 헬퍼가 Pydantic v2의 `$defs`를 draft-07 `definitions`로 hoist + ref 재작성. **2.1 → 2.2에서 두 단계 강화**:
  1. 2.1: main schema 안 ref `#/$defs/X` → `#/definitions/X` 재작성
  2. 2.2: hoisted sub-schema 안 ref도 같은 재작성 (Equipment → EquipItem 같은 nested ref)
- `npm run gen` (cd client) → `client/types/wire.gen.d.ts` + `client/types/wire.schema.json` 갱신
- 클라 `wire.ts` + `features/<x>/types.ts`는 `import type { ... } from '@/types/wire.gen'` 후 alias re-export로 caller churn 0
- **RootModel discriminated union 출력**: Form A union alias (`export type JudgePayload = JudgeA | JudgeB | ...`). codegen이 sub-interface 4개 + union alias 모두 emit.

### 명명 규칙 (라운드 2에서 굳음)

- Wire 모델: `<EventName>Payload` (예: `ErrorPayload`, `PendingCheckPayload`, `JudgePayload`)
- Sub-model: 짧은 이름 + 의미 (예: `TierBadge`, `RiskBadge`, `DifficultyBadge` — 재사용 가능 atom)
- 클라 alias: `export type <ShortName> = <EventName>Payload` (예: `PendingCheck = PendingCheckPayload`, `JudgeData = JudgePayload`)
- camelCase vs snake_case: payload 결정. Hero/Subject/Place/CombatBadge는 camelCase (UI 카드). Judge/LogEntry/Combat events는 snake (관찰성 위주).

### 잠금된 invariants

- **`engines/perspective.py`의 marker invariant**: `log.death.killed_marker`(`살해당했다`)는 `log.death.killed`(`{killer}에게 살해당했다.`)의 substring이어야 함. dedupe-by-substring 검사가 깨지지 않게 docstring 명시.
- **catalog `error.narrate_malformed` / `error.narrate_unavailable`**: NarrateMalformed / NarrateUnavailable 도메인 클래스가 raise되면 자동 라우팅. 첫 세션 사용자 정정 결.
- **client `Subject` mp 부재**: NPC 마력은 player에 미공개. `SubjectPayload`도 mp 미정의 (서버 wire와 클라 alias 양쪽에서 보존).

---

## 3. 굳은 작업 패턴 — 새 세션도 따를 것

### 새 라운드/sub-round 시작 시

1. main에 다른 작업 없는지 확인 (`git log --oneline -3`)
2. Brainstorm — 큰 결정 있으면 옵션 다중 선택 1~3개 제시 → 사용자 confirm
3. `git checkout -b refactor/<round>-<sub>-<topic>`
4. plan 문서 `docs/superpowers/plans/2026-MM-DD-<round>-<sub>-<topic>.md` 작성 — task 분할 명시
5. TaskCreate × N (sub-round 안 task 개수만큼)

### Task dispatch 사이클

1. TaskUpdate → in_progress
2. Implementer agent dispatch (sonnet for non-trivial / 신규 모델 정의, haiku for mechanical / 단순 마이그레이션)
3. spec compliance reviewer (sonnet)
4. code quality reviewer (haiku — lightweight 설명)
5. fix-up이 필요하면 직접 Edit/Bash로 빠른 commit (subagent 거치지 않음)
6. TaskUpdate → completed
7. 다음 task

**예외 — mechanical task 직접 검증**: 단일-파일 migration + JSON parity 명확하면 subagent dispatch 생략하고 controller가 직접 grep + pytest로 검증 (라운드 2.10 후반에 도입한 시간 절약 패턴).

### 검증 task (마지막) — 항상 같은 구성

- 한국어 잔재 grep (영역별)
- pytest + ruff + ssot (server)
- jest + tsc (client)
- raw dict 잔재 grep (해당 SSE 이벤트 / 페이로드)
- branch state 확인
- `gh pr create` (squash merge 가정)
- 본 세션에서 사용자 결정 후 머지

### 메모리 / 피드백

이미 박힌 user memory (`~/.claude/projects/-home-kn-code-trpg/memory/MEMORY.md`):

- `feedback_plain_korean.md` — 평이한 한국어 + 구체적 영향 명시
- `feedback_plain_always.md` — 답변 전마다 defog:plain 호출
- `feedback_minimal_claude_md.md` — CLAUDE.md 최소화
- `project_classify_consolidation.md` — classify 카탈로그 비대화 인지
- `feedback_narrate_prose_only.md` — narrate는 묘사 전용
- `feedback_read_scope_tables_first.md` — plan 문서 scope 표 먼저 읽기
- `feedback_conservative_means_small_steps.md` — "보수적" = 라운드 작게 + 퀄리티 양보 X

이 결들은 새 세션도 그대로 따릅니다.

---

## 4. 다음 할 일 — 우선순위 순

### A. 라운드 3 — 폴더 6분할 정리 (다음 세션 진입 자리)

`server/src/` 13 폴더 → 6분할로 묶기. 라운드 1·2 결과 wire/ 자기 자리, mapping/ 거의 비어있음, persistence/도 단단한 1급. 폴더 이동 + import 경로 갱신 위주.

| 6분할 | 흡수 폴더 | 위험 |
|---|---|---|
| **locale/** | `locale/` (그대로) | 0 |
| **llm/** | `llm/`, `llm_calls/`, `context/` | 중 (3 폴더 흡수, llm_calls는 5 agent 디렉토리) |
| **game/** | `domain/`, `rules/`, `engines/`, `ontology/`, `flow/` | **고** (5 폴더 흡수, import 경로 수백 곳) |
| **wire/** | `wire/`, `mapping/` (3 파일 잔여) | 저 (mapping은 거의 비어있음) |
| **api/** | `api/` (그대로) | 0 |
| **persistence/** | `persistence/` (그대로) | 0 |

#### 추천 sub-round 입자

1. **3.1 wire 묶음** (가장 작은 위험) — `mapping/` → `wire/` 통합. 4 task 또는 3 task.
2. **3.2 llm 묶음** (중간) — `llm/`, `llm_calls/`, `context/` → `llm/` 통합.
3. **3.3 game 묶음** (가장 큰 위험) — 5 폴더 → `game/` 통합.

각 sub-round는 atomic — 한 sub-round 안에서 파일 이동 + 모든 import 갱신 + ssot script 갱신 + tests 이동을 한 commit/PR에 묶음 (중간 상태에서 broken되지 않게). Implementer task는 step별 명시.

#### 3.1 입자 — 새 세션 첫 작업 자리

`mapping/` 3 파일을 `wire/`로 통합:
- `src/mapping/labels.py` → `src/wire/labels.py`
- `src/mapping/story_graph.py` → `src/wire/story_graph.py`
- `src/mapping/to_front.py` → `src/wire/to_front.py`
- `src/mapping/__init__.py` 삭제, 폴더 삭제

영향 범위 (이미 grep 완료, 새 세션도 동일 grep 가능):
- src callers (5곳): `api/routes/session.py:22`, `flow/judge.py:15`, `flow/format.py:11`, `flow/roll.py:16`, `wire/emit.py` 5 local imports
- tests (6 파일): `tests/mapping/*.py` 5개 + `tests/flow/test_finalize_chip_branches.py:17`
- `server/scripts/check_relational_ssot.sh:32` — `$ROOT/server/src/mapping` → `$ROOT/server/src/wire`
- `locale/catalog/ui.toml:1` — comment `from mapping/labels.py` → `from wire/labels.py` (doc only)

note: `mapping/labels.py`에는 locale-related catalog wrappers (stat_label, gender_label 등)와 wire-side combiners (race_job_label, risk_payload, difficulty_badge)가 mixed. 본 sub-round는 wire/로 통째 이동만; locale 분리는 후속 sub-round (예: 3.4 locale wrapper 분리 — optional).

#### 3.2 입자

`llm/` (LLMClient + 4 provider) + `llm_calls/` (5 agent 디렉토리: classify, narrate, combat_narrate, summon, recommend) + `context/` (history/judge surroundings 빌더) → `llm/` 통합:
- `src/llm/` 그대로 두고 다른 두 폴더를 sub-package로 흡수: `src/llm/calls/`, `src/llm/context/`. 또는 평면 통합 — 결정 자리.
- import 갱신 광범 (수십 ~ 백곳). flow/turn.py, flow/narrate.py, flow/judge.py 등 LLM 호출자.

#### 3.3 입자 — 가장 큰

`domain/`, `rules/`, `engines/`, `ontology/`, `flow/` → `game/` 통합:
- 가장 큰 import path migration. 수백 곳.
- step별 분할: 한 폴더씩 `game/` 안으로 이동 (5 step). 각 step atomic.
- `engines/`는 sub-package 깊이 있음 (apply.py + 여러 sub-module). 평면 vs 계층 결정.
- ssot script 패턴 (현 `flow|context|mapping`) → `game/flow|game/context|wire`로 갱신 — 이건 3.1에서 mapping→wire 갱신 시 함께.

### B. 1.6 (라운드 1 마무리) — LLM 프롬프트 .md 파일 카탈로그

라운드 3 (폴더 분할) 후 검토. 폴더 이동 끝나면 `llm/calls/` 안 5 agent의 prompt.md 위치가 명확해져 카탈로그 작업이 clean.

- 대상: `llm_calls/_kernel.md` + `classify/prompt.md` + `combat_narrate/prompt.md` + `narrate/body/prompt.md` + `narrate/extract/prompt.md` + `recommend/prompt.md` + `summon/prompt.md`
- 결정 필요: 프롬프트 한 파일을 하나의 catalog entry로 둘지 (`prompt.kernel` `prompt.classify` 등), 아니면 prompt를 더 잘게 쪼갤지 (e.g., 시스템 명령 / 어휘 / 출력 형식 등 섹션 단위)?
- 위험: 프롬프트 변경은 LLM 출력 영향 가장 큼. `smoke_judge.py` 같은 스모크 테스트 + 수동 LLM 호출 검증 필요.
- 옵션: (a) 1.6 진행, (b) 수동 작업 (코드 변경 적고 LLM 출력 회귀 위험이 커서 자동화 가치 낮음 — 현재 가장 가능성 높음).

### C. 별개 cleanup (작은 자리)

- `flow/judge.py:19-23` PendingCheckTrigger Korean docstring → 영문화 (locale 영역 외, comment cleanup)
- `flow/judge.py:_call_judge_llm` 스텁 wiring (현재 NotImplementedError)
- `wire/export.py:_flatten`의 sub-model name collision 가드 (현재 dormant — 다른 페이로드가 같은 이름 sub-model 쓰면 silent clobber. assertion 추가 가능)
- `mapping/labels.py`의 mixed locale wrappers vs wire combiners — 라운드 3 후 분리 검토 (3.4 sub-round optional)

---

## 5. 새 세션 시작 가이드

1. `continue.md` (이 파일) 읽기 — §0 봐야할 문서 + §1 어디까지 + §4 다음 할 일
2. `0505.md` 읽기 — §2 6분할 결정 근거 internalize
3. `git pull origin main` 후 `git log --oneline -10` 최근 진행 확인 (`590efc5` 기준 — 라운드 2 finale)
4. 메모리 인덱스 자동 로드 확인 (`~/.claude/projects/-home-kn-code-trpg/memory/MEMORY.md`)
5. 사용자에게 다음 sub-round 결정 받기 (§4의 A.3.1 → A.3.2 → A.3.3 추천)
6. Brainstorm (필요시 — 폴더 입자 결정에) → plan 문서 → branch → dispatch

### 첫 결정 brainstorm 후보 (사용자에게 물을 내용)

**Q1**: 라운드 3 진행 방식 — (a) 3.1 wire 묶음부터 (가장 작은 위험으로 패턴 굳히기), (b) 3.3 game 묶음부터 (가장 큰 작업 끝내고 나머지 mechanical), (c) 3 sub-round를 한 PR로 (atomic) — 어느쪽?

추천: **(a) 3.1부터** — mapping/→wire/ 통합이 가장 단순, atomic 변경 범위 명확. 패턴 굳힌 후 3.2 llm, 3.3 game 순. 보수적 = 단계 잘게.

**Q2** (3.1 안에서): `mapping/labels.py`의 locale-wrapper 함수들 (stat_label, gender_label, story_summary_*, state_tag_*, ROLL_REASON_DEFAULT, STORY_EDGE_LABEL_*)을 `locale/labels.py`로 분리할지, 일단 `wire/labels.py`에 통째 두고 후속 sub-round에서 분리할지?

추천: **통째 wire/로** — atomic 이동 우선, locale 분리는 의미 결 분리 작업이라 별도 sub-round (3.4 optional)에서. churn 분산.

---

## 6. 굳지 않은 — 새 세션에서 정함

- **3.1 wire 묶음 입자**: labels.py mixed split 시점 (본 sub-round vs 후속).
- **3.2 llm 묶음 입자**: 평면 통합 vs sub-package 계층 (`llm/calls/`, `llm/context/`).
- **3.3 game 묶음 입자**: 한 sub-round로 묶을지 5 sub-step (per 폴더) 분할할지.
- **engines/ 계층**: `engines/apply.py` + sub-module들. 평면 vs 계층 — 큰 폴더라 결정 자리.
- **1.6 진행 시점**: 라운드 3 끝난 뒤 vs 별개 (수동 작업).

---

## 7. 본 세션 마지막 상태

- main HEAD: `590efc5 refactor(wire): sub-round 2.10 — CombatBadgePayload (mapping last mile) (#18)`
- 직전 docs commit: `20b5451 docs: 4 → 6분할 갱신 (api/persistence 1급 분리)`
- 작업 트리: clean (3.1 plan 작성 직전에 세션 종료)
- 진행 중인 branch: 없음 (2.10 squash 머지 후 자동 정리됨)
- 미푸시: 없음

새 세션에서 `git pull origin main` 후 시작.

### 본 세션의 핵심 산출물

1. **라운드 2 (wire 통역기) 완료** — 11 sub-round (2.0 → 2.10), 11 PR, 모든 SSE 이벤트 + 5 큰 페이로드 + mapping last mile 통과.
2. **6분할 결정 갱신** (4 → 6) — `0505.md` §2 결정 근거에 명시. api/persistence 1급 분리.
3. **mapping/to_front.py 5 main 함수 모두 wire 위임** — 폴더 분할 시 wire/로 흡수 자연스러움.
4. **wire 단위 테스트 101 PASS** + 클라 손작성 wire 타입 거의 모두 wire.gen alias로 교체.
