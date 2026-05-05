# continue — 라운드 1·2 진행 인계

이 문서는 본 세션의 합의 결과 + 작업 내역을 새 세션이 그대로 이어받기 위한 정리입니다. 결정 굳은 항목은 흔들지 말고, 굳지 않은 미정 항목은 새 세션에서 정합니다.

원본 큰 그림: `0505.md` (서버 4분할 — locale / llm / game system / 통역기)

---

## 0. 봐야할 문서 (새 세션 시작 시)

### 필수 읽기 (이 순서대로)

| # | 경로 | 왜 |
|---|---|---|
| 1 | `continue.md` (이 파일) | 본 세션 인계 — 어디까지 왔고 다음 뭘 할지 |
| 2 | `0505.md` | 큰 그림 4분할 plan. §1 통증 분리, §4 첫 케이스 결, §5 두 갈래 진행, §9 합의 굳음 |
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

#### 패턴 참조 코드

| 무엇 | 어디 |
|---|---|
| catalog 파일 형식 (단일/다중 segment 키, 조사 토큰) | `server/src/locale/catalog/*.toml` (7개: error/tier/phase/stat/log/ui/prompt) |
| render() 구현 + 조사 토큰 walker | `server/src/locale/render.py` |
| 조사 함수 (`i_ga`, `eun_neun` 등) | `server/src/locale/particles.py` |
| Wire 모델 패턴 | `server/src/wire/models/error.py`, `server/src/wire/models/pending_check.py` |
| Wire 빌더 패턴 (emit_error / emit_pending_check / _build_*) | `server/src/wire/emit.py` |
| Codegen export + `_flatten` 헬퍼 ($defs hoist) | `server/src/wire/export.py` |
| Wire `__init__` public API | `server/src/wire/__init__.py` |
| 클라 wire alias re-export 패턴 | `client/types/wire.ts` |
| 단위 테스트 패턴 (wire) | `server/tests/wire/test_emit_error.py`, `server/tests/wire/test_pending_check.py` |
| Catalog 무결성 테스트 | `server/tests/locale/test_catalog_integrity.py` |
| Render token-walker 단위 테스트 | `server/tests/locale/test_render_particles.py` |

#### 도메인 / 게임 컨텍스트 (디자인 의도)

| 경로 | 무엇 |
|---|---|
| `docs/01-overview.md` ~ `docs/05-codemap.md` | gitignored 디자인 노트 (rationale, per-turn flow). 새 세션에서 큰 디자인 결정 필요할 때 참조 |
| `server/src/domain/errors.py` | DomainError 계층 (session lifecycle vs action validation 분리 — CLAUDE.md "Error hierarchy" 참조) |
| `server/src/domain/memory.py` | `PendingCheck` 등 게임 상태 도메인 모델 |
| `server/src/domain/state.py` | `GameState` (게임 진행 SSOT) |
| `server/src/ontology/graph.py` | 관계 SSOT (CLAUDE.md "Relational SSOT" 참조) |

### 문서 읽기 우선순위

- **새 세션 첫 답변 전**: 1+2 (continue.md + 0505.md). 나머지는 task에 따라 ad-hoc.
- **첫 sub-round 진행 시작 전**: 6 (가장 가까운 패턴의 sub-round plan)
- **첫 wire 페이로드 작업 시 (2.2)**: `2026-05-05-wire-sub-round-2-1-pending-check-payload.md` 가 직접 템플릿
- **catalog 늘릴 때**: 기존 catalog 파일 형식 grep 으로 확인

---

## 1. 어디까지 왔는가

### 라운드 1 (locale, 통증 B) — 5/6 sub-round 완료, 1.6 남음

| sub-round | 상태 | PR | 산물 |
|---|---|---|---|
| 1.1 | ✅ main | (squash) | Tier/Phase ASCII enum 전환, `tier.toml`/`phase.toml` 신설 |
| 1.2 | ✅ main | #4 | `stat.toml` (6 stat 라벨), `mapping/labels.py:stat_label` catalog-backed |
| 1.3 | ✅ main | #5 | `render()` 조사 토큰 처리, `log.toml`(80+) + `ui.toml`(22) 본진. `flow/format.py` 30+ 함수 + `flow/error_phrases.py` 28 phrases + `mapping/labels.py` 잔여 모두 catalog |
| 1.4 | ✅ main | #6 | flow 산재 13줄 + engines/quest+perspective 8줄 + format 아이템 fallback. `eun_neun` import 제거. perspective marker invariant 명시 |
| 1.5 | ✅ main | #7 | `prompt.toml` 신설 (12 entries: history.* + judge.*). `context/layers.py` history headers + `flow/judge.py:judge_quest_progress` prompt 카탈로그 |
| **1.6** | ⏳ 미루기 | — | LLM 프롬프트 `.md` 파일 (kernel + 5 agents) — 본 세션에서 라운드 2로 점프 결정 |

### 라운드 2 (wire, 통증 A) — 2/N sub-round 완료, 첫 큰 페이로드 통과

| sub-round | 상태 | PR | 산물 |
|---|---|---|---|
| 2.0 | ✅ main | #8 | `emit_error` 시그니처 확장 (옵션 A: `code_or_exc: str \| Exception` + `message=` + `**vars`). 새 catalog 2개 (`error.pending_check_active`, `error.level_up_invalid_stat`). 5 raw dict 사이트 마이그레이션 (level_up × 4 + narrate × 1) |
| 2.1 | ✅ main | #9 | `PendingCheckPayload` + `TierBadge` 모델, `emit_pending_check` 빌더, `_build_pending_check_payload` 헬퍼 (SSOT). 2 호출자 마이그레이션. **codegen 파이프라인 버그 수정** — Pydantic v2 `$defs` → draft-07 `definitions` hoist (`_flatten` in `wire/export.py`). 클라 `wire.ts` alias re-export |

`server/src/`에 raw `"type": "error"` dict는 이제 `wire/emit.py` 본문 단 1곳.

main HEAD: `45e7f95` (PR #9 머지 후).

---

## 2. 굳은 결정 — 흔들지 말 것

### 큰 그림

- **서버 4분할** (locale / llm / game system / 통역기). 0505.md §9 합의 굳음.
- **통역기 위치**: 서버 안 (옵션 A). 별도 패키지(B)는 형태 잡힌 후.
- **다국어 모델**: W (풀 i18n + 한 곳 관리).
- **첫 케이스**: 에러 메시지 한 종류 (이미 1.1 시점에 통과).

### 라운드 단위 (사용자 요청 패턴)

- **PR per sub-round, squash merge** — 각 sub-round 끝나면 main에 squash 머지 후 다음 sub-round 새 branch.
- **Branch 명명**: `refactor/<round>-<sub>-<topic>` (예: `refactor/locale-1.4-residue`, `refactor/wire-2.1-pending-check-payload`).
- **각 task당 spec + quality 두 리뷰** — implement → spec compliance review (subagent) → code quality review (subagent) → next task.

### Catalog 패턴 (라운드 1에서 굳음)

- 위치: `server/src/locale/catalog/<domain>.toml` (5 카탈로그: error / tier / phase / stat / log / ui / prompt — 7개)
- 키 형태:
  - 단일 segment: `[domain.name]` plain (예: `[error.llm_unavailable]`, `[log.equip]`)
  - 2+ segment: `[domain."seg1.seg2"]` 인용 (예: `[log."error.hp_full"]`, `[log."combat.defeat"]`, `[ui."story.edge.current"]`)
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

- 모델: `wire/models/<event>.py`에 Pydantic `<Event>Payload` + 필요시 sub-model (예: `TierBadge`)
- 빌더: `wire/emit.py`에 `emit_<event>(state, ...)` — `{"type": "<event>", "data": payload.model_dump()}` 반환
- 헬퍼: `_build_<event>_payload(state, ...) -> <Event>Payload` — SSE wrap과 state-embedding이 SSOT 공유
- `emit_error` 시그니처: `code_or_exc: str | Exception, *, locale="ko", message=None, **vars` (옵션 A 옵션)

### 자동 생성 파이프라인

- `wire/export.py:_MODELS` list에 모델 추가
- `_flatten` 헬퍼가 Pydantic v2의 `$defs`를 draft-07 `definitions`로 hoist + ref 재작성 (sub-model TS 타입화 보장)
- `npm run gen` (cd client) → `client/types/wire.gen.d.ts` 갱신
- 클라 `wire.ts`는 `import type { ... } from './wire.gen'` 후 alias re-export로 caller churn 0

### 명명 규칙 (라운드 2에서 굳음)

- Wire 모델: `<EventName>Payload` (예: `ErrorPayload`, `PendingCheckPayload`)
- Sub-model: 짧은 이름 + 의미 (예: `TierBadge` — 재사용 가능)
- 클라 alias: `export type <ShortName> = <EventName>Payload` (예: `PendingCheck = PendingCheckPayload`)

### 잠금된 invariants

- **`engines/perspective.py`의 marker invariant**: `log.death.killed_marker`(`살해당했다`)는 `log.death.killed`(`{killer}에게 살해당했다.`)의 substring이어야 함. dedupe-by-substring 검사가 깨지지 않게 docstring 명시.
- **catalog `error.narrate_malformed` / `error.narrate_unavailable`**: NarrateMalformed / NarrateUnavailable 도메인 클래스가 raise되면 자동 라우팅. 첫 세션 사용자 정정 결.

---

## 3. 굳은 작업 패턴 — 새 세션도 따를 것

### 새 라운드/sub-round 시작 시

1. main에 다른 작업 없는지 확인 (`git log --oneline -3`)
2. Brainstorm — 큰 결정 있으면 옵션 다중 선택 1~3개 제시 → 사용자 confirm
3. `git checkout -b refactor/<round>-<sub>-<topic>` (⚠ 본 세션에서 한 번 누락 — main에 직접 commit 들어감 → 복구함)
4. plan 문서 `docs/superpowers/plans/2026-MM-DD-<round>-<sub>-<topic>.md` 작성 — task 분할 명시
5. TaskCreate × N (sub-round 안 task 개수만큼)

### Task dispatch 사이클

1. TaskUpdate → in_progress
2. Implementer agent dispatch (sonnet for non-trivial, haiku for mechanical)
3. spec compliance reviewer (sonnet)
4. code quality reviewer (haiku — lightweight 설명)
5. fix-up이 필요하면 직접 Edit/Bash로 빠른 commit (subagent 거치지 않음)
6. TaskUpdate → completed
7. 다음 task

### 검증 task (마지막) — 항상 같은 구성

- 한국어 잔재 grep (영역별)
- pytest + ruff + ssot (server)
- jest + tsc (client)
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

### A. 1.6 (라운드 1 마무리) — LLM 프롬프트 .md 파일 카탈로그

- 대상: `llm_calls/_kernel.md` + `classify/prompt.md` + `combat_narrate/prompt.md` + `narrate/body/prompt.md` + `narrate/extract/prompt.md` + `recommend/prompt.md` + `summon/prompt.md`
- 가장 큰 단위. 프롬프트 본문이 통째로 한국어. `prompt.toml` (1.5에서 신설된 카탈로그)에 흡수.
- 결정 필요: 프롬프트 한 파일을 하나의 catalog entry로 둘지 (`prompt.kernel` `prompt.classify` 등), 아니면 prompt를 더 잘게 쪼갤지 (e.g., 시스템 명령 / 어휘 / 출력 형식 등 섹션 단위)?
- 위험: 프롬프트 변경은 LLM 출력 영향 가장 큼. `smoke_judge.py` 같은 스모크 테스트 + 수동 LLM 호출 검증 필요.
- 선택지: (a) 1.6 진행, (b) 라운드 2 마무리 (2.2~2.6) 후 1.6, (c) 1.6은 수동 작업 (코드 변경이 적고 LLM 출력 회귀 위험이 커서 자동화 가치 낮음).

### B. 라운드 2 — 큰 페이로드 4종 (sub-round 2.2~2.5)

각각 2.1과 동일 패턴:
- Pydantic 모델 + sub-model 정의
- emit_<event> 빌더 + _build_<event>_payload 헬퍼
- 호출자 마이그레이션
- 클라 wire.ts alias

| sub | 페이로드 | 호출자 | 비고 |
|---|---|---|---|
| 2.2 | `hero` | `mapping/to_front.py:to_hero` | 주인공 캐릭터 정보 (체력 / 마나 / 능력치 / 장비 등) |
| 2.3 | `subject` | `mapping/to_front.py:to_subject` | 현재 주시 대상 (NPC / 아이템 등) |
| 2.4 | `quest` | `mapping/to_front.py:to_quest` | 활성 퀘스트 정보 |
| 2.5 | `place` | `mapping/to_front.py:to_place` | 현재 장소 + 연결 |

각 sub-round는 4 task (model+test, caller migration, codegen+wire.ts, verify+PR) — 2.1과 동일.

`mapping/to_front.py:to_front_state` 의 `state` SSE 이벤트 자체도 페이로드. 위 4종이 끝나면 `FrontStatePayload` (`hero` + `subject` + `quest` + `place` + ... 모두 결합)도 자연스럽게 들어옴.

### C. 라운드 2 — SSE 이벤트들 (sub-round 2.6+)

| sub | 이벤트 | 빌더 |
|---|---|---|
| 2.6 | `judge` | discriminated union (4 judge_kind) — 0505.md §4의 "discriminated union 자동 생성" 검증 자리 |
| 2.7 | `narrative_delta` | 단순 (text only) |
| 2.8 | `log_entry` | discriminated union (4 kind: gm/player/act/roll) |
| 2.9 | `combat_start` / `combat_turn` / `combat_end` | (클라 무시 — 옵저버빌리티만) |
| 2.10 | `suggestions` | items list |
| 2.11 | `done` | empty payload |

`narrative_delta` `done` 같은 단순 이벤트는 모델 만드는 비용이 크지 않고 자동 생성 파이프라인 검증 외 가치 적음. `judge` `log_entry`의 discriminated union은 진짜 검증 자리.

### D. 라운드 1·2 끝나면 — 폴더 4분할 정리

`server/src/` 13 폴더를 4분할로 묶기. 0505.md §5의 "두 갈래 진행의 부산물로 자연스럽게 따라옴". 이 시점에 `flow/` `mapping/` 책임이 빠져 슬림해져 있어 폴더 이동만 남음.

| 4분할 | 흡수 |
|---|---|
| **locale/** | `locale/` |
| **llm/** | `llm/`, `llm_calls/`, `context/` |
| **game/** | `domain/`, `rules/`, `engines/`, `ontology/`, `persistence/`, `flow/` (orchestration만 남은 후) |
| **wire/** | `wire/`, `api/`, `mapping/` (잔여) |

### E. 별개 cleanup

- `flow/judge.py:19-23` PendingCheckTrigger Korean docstring → 영문화 (locale 영역 외, comment cleanup)
- `flow/judge.py:_call_judge_llm` 스텁 wiring (현재 NotImplementedError)
- `wire/export.py:_flatten`의 sub-model name collision 가드 (현재 dormant — 다른 페이로드가 같은 이름 sub-model 쓰면 silent clobber. assertion 추가 가능)

---

## 5. 새 세션 시작 가이드

1. `continue.md` (이 파일) 읽기 — §0 봐야할 문서 + §1 어디까지 + §4 다음 할 일
2. `0505.md` 읽기 — 큰 그림 합의 굳음 항목 internalize
3. `git log --oneline -10` 최근 진행 확인 (`374ba6e` 기준 — continue.md 커밋 직후)
4. 메모리 인덱스 자동 로드 확인 (`~/.claude/projects/-home-kn-code-trpg/memory/MEMORY.md`)
5. 사용자에게 다음 sub-round 결정 받기 (§4의 A/B/C/D/E 우선순위 중)
6. Brainstorm (필요시) → plan 문서 (직전 sub-round plan을 템플릿으로) → branch → dispatch

### 첫 결정 brainstorm 후보 (사용자에게 물을 내용)

**Q1**: 1.6 (LLM prompts) vs 라운드 2 큰 페이로드 (2.2 hero) — 어느쪽 먼저?

추천: **2.2 hero** — 라운드 2 큰 페이로드 패턴이 2.1에서 굳었으니 그대로 반복하면 빠름. 1.6은 LLM 출력 회귀 위험 커서 별도 시점에. 0505.md §4의 "1.5 끝나는 시점에 wire 갈래로 점프할지 다시 결정"은 본 세션에서 이미 결정 (wire 갈래 선택). 2.2~2.5 끝나면 다시 1.6 검토.

---

## 6. 굳지 않은 — 새 세션에서 정함

- 1.6 진행 시 prompt 카탈로그 입자 (파일 단위 vs 섹션 단위)
- 2.2~2.5 hero / subject / quest / place의 sub-model 명명 (TierBadge 결로 재사용 가능 sub-model 발굴 — 예: `StatBlock`, `EquipmentSlot`, `LocationLink`?)
- 라운드 3+ (game system / llm 분할) — 라운드 1·2 끝나는 시점에 다시 보기

---

## 7. 본 세션 마지막 상태

- main HEAD: `45e7f95 refactor(wire): sub-round 2.1 — PendingCheckPayload model + builder (#9)`
- 작업 트리: clean
- 진행 중인 branch: 없음 (2.1 squash 머지 후 자동 정리됨)
- 미푸시: 없음

새 세션에서 `git pull origin main` 후 시작.
