# CLAUDE.md

`frontend/` 에서 Claude Code 가 일할 때 참고. 사용자용 셋업·테스트는 [README.md](./README.md), 백엔드 경계 정의는 `../docs/04-boundary.md`.

## Layout

`frontend/` 가 Expo 앱. backend 는 peer 디렉터리 (`../backend/`). 모든 frontend 명령은 여기서 실행.

## Commands

[README.md](./README.md) 의 전체 표 참고. 메모:

- `tailwind.config.js`, `babel.config.js`, `metro.config.js`, `design/tokens.js` 수정 후엔 `-c` 로 Metro 재시작.
- 테스트 러너 없음. 타입 체크는 `node_modules/.bin/tsc --noEmit` 또는 에디터 / Metro 로 implicit (`strict` TS, extends `expo/tsconfig.base`).
- `--host=tunnel` 을 `--tunnel` 보다 선호 (`@expo/ngrok@4.x` 버그).

## Stack constraints

- **Expo SDK 54 / RN 0.81 / React 19**, `app.json` 에 `newArchEnabled` + `experiments.reactCompiler` — 수동 memoization 보통 불필요. class component / legacy native module 은 New Arch 에서 동작해야 함.
- **expo-router** with `typedRoutes`. 화면 추가는 `app/` 아래 파일 만들기, 네비게이션 수동 배선 금지.
- **NativeWind v4**: `className="bg-canvas-subtle p-3 rounded-md"`, StyleSheet 객체 아님. `@tailwind` directive 는 `global.css`, `app/_layout.tsx` 에서 import.
- Path alias `@/*` → 이 디렉터리. 상대 경로보다 `@/components/...` 선호.
- **백엔드 통신은 expo/fetch**. 표준 `fetch` 가 RN 에서 SSE body streaming 을 지원 안 함.

## Architecture

한국어 TRPG 단일 화면. tab bar 숨김, `app/(tabs)/index.tsx` 가 `<Shell />` 마운트. 모든 UX 는 `components/Shell.tsx` 아래.

**Layers (top → bottom):**

1. `app/` — 라우트 셸. `_layout.tsx` 가 Google Fonts (Inter / Source Serif 4 / Geist Mono) 로드, ready 될 때까지 렌더 게이팅. `(tabs)/index.tsx` 가 `<Shell />` 마운트.
2. `components/Shell.tsx` — composition root. `useGame()` 의 `status` 로 `loading / no-game / error / ready` 분기만 한다. 게임 화면은 `Playing` 으로 위임.
3. `components/Playing.tsx` — `status === 'ready'` 일 때 마운트되는 게임 화면. `activeId / heroOpen / typing` 로컬 UI state 소유, 패널은 `buildPanelSlots(...)` 로 구성.
4. `components/new-game/` — `status === 'no-game'` 일 때 노출. `NewGame.tsx` 가 `GET /profiles` 받아 시나리오·종족 카드 + 이름·외모 입력 → `useGame().startNewGame(body)` 호출. 내부 헬퍼 (`Section`, `SelectCard`, `Input`, `CenterMessage`) 는 같은 폴더 안.
5. `components/{header,log,hero,composer,combat,ui}/` — 기능별 폴더, 각자 `index.ts` barrel. 폴더 단위 import, 개별 파일 직접 import 안 함. `ui/` 는 공유 primitive (`Bar`, `Row`, `StatRow`, `InlineParts`, `InlineNodes`, `LabeledRow`, `ExpandGroup`).
6. `hooks/useGame.ts` — game state + 액션 (`onSend / onRoll / onStop / startNewGame / refresh`) 의 단일 진실. mount 시 `getCurrentSession()` 으로 마지막 게임 자동 복원, unmount 시 모든 abort controller 일괄 cancel. SSE 이벤트 → state setter 매핑은 `hooks/handleStreamEvent.ts` 의 pure dispatcher 가 처리.
7. `services/` — **데이터 경계**. `services/index.ts` 가 `services/api.ts` 를 re-export. `listProfiles / getCurrentSession / initSession / streamTurn / streamRoll / streamIntro` 가 그 표면. 백엔드 base URL / basic auth 는 여기서만 처리, 다른 layer 가 fetch 직접 호출 금지.
8. `presenters/` — **domain → UI presenter**. `panels.ts` 가 `domain` 타입 (`Subject / Quest / Place`) 을 `PanelSlot` 렌더 계약으로 변환 (`buildPanelSlots`). `format.ts` 는 공유 표시 헬퍼 (`joinList`, `joinOrDash`, `formatInventoryItem`, `joinInventory`). 순수 매핑, state 없음, IO 없음.
9. `types/` — `domain.ts` (백엔드 게임 모델: `Hero`, `Subject`, `Quest`, `Place`, `Stats`, `RollResult`, `FrontState`), `ui.ts` (프론트 렌더 계약: `LogEntry`, `Panel`, `PanelSlot`, `Tone`, ...), `wire.ts` (백엔드 wire 포맷: `ProfileCard`, `RaceCard`, `InitRequest`, `SessionPayload`, `TurnRequest`, `PendingCheck`, `JudgeAction`, `StreamEvent`). SSE `log_entry` payload 는 `ui.LogEntry` 를 그대로 재사용. `LogEntry` 는 `kind: 'gm' | 'player' | 'act' | 'roll'` discriminated union — union 확장 시 `components/log/LogItem.tsx` 에 case 추가.
10. `design/tokens.js` (+ `tokens.d.ts`) — **디자인 토큰의 단일 진실**: `colors`, `spacing`, `radius`, `fontFamily`, `fontSize`, `toneColor`. `tailwind.config.js` (className utility) 와 raw 값이 필요한 TS 코드 양쪽이 consume. **컴포넌트에 색상·간격 하드코딩 금지** — className 또는 `@/design/tokens` import. CJS (`.js`) 인 이유는 Tailwind config 가 Node 에서 돌기 때문, 타입은 `.d.ts` sibling.

## Conventions

- 프론트 타입은 UI 가 렌더하는 필드만 포함. 백엔드 전용 필드는 백엔드 작업 시 추가.
- UI 구조는 고정. 데이터 변형은 같은 슬롯 안 조건 분기가 아니라 다른 패널 슬롯으로 옮김.
- UI 일관성 수정은 holistic — 지적된 인스턴스만 패치하지 말고 해당 atom 전체를 한 규칙으로 통일.
- env 변수는 fail-fast. `services/api.ts` 가 `EXPO_PUBLIC_API_URL` / `EXPO_PUBLIC_API_USER` / `EXPO_PUBLIC_API_PASS` 누락 시 import 단계에서 throw.
- 한국어 단일. 백엔드가 모든 표시 문자열을 한국어로 만들어 보냄 (날짜·기간·합성 문자열 포함). 프론트는 그대로 표시.
