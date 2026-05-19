# Browser QA Patch Notes

작성일: 2026-05-19

이 문서는 `http://localhost:8081/`에서 새 게임을 시작해 실제 플레이하며 확인한 추가 개선 사항을 정리한다. 이미 반영한 UI 개선 이후 남은 문제와 새로 발견한 문제를 패치 대상으로 기록한다.

## 확인 환경

- 클라이언트: Expo web, 로컬 `localhost:8081`
- 시나리오: `개발용 원턴 테스트`
- 플레이어: 기본 생성 캐릭터 `주인공`
- 주요 진행 흐름:
  1. 새 이야기 시작
  2. 루카와 대화
  3. 엘리엇과 대화
  4. 노트에서 `동행 이동 확인` 퀘스트 수락
  5. `준비실`로 이동
  6. 준비실 대상 목록 확인
  7. `보급 표식` 줍기
  8. 시트 확인
  9. 루카와 다시 대화

## 이미 개선된 부분

다음 항목은 이전 패치에서 반영했고, 브라우저에서 정상 동작을 확인했다.

- 새 이야기 화면에서 `시작` 버튼을 이름, 성별, 세계, 종족, 언어 선택 아래로 이동했다.
- 영어 UI 카탈로그가 없는 상태에서 `English` 선택지를 숨기고 `한국어`만 노출했다.
- 지도, 노트, 시트 패널이 로그 위를 덮지 않고 정상 레이아웃 흐름 안에서 열리도록 했다.
- 주변 대상 목록은 스크롤 동작은 유지하되 시각적 스크롤바는 숨겼다.
- 주변 대상 목록이 열린 상태에서 추천 행동을 보내면 대상 목록이 닫히도록 했다.
- 로그는 짧은 내용일 때 위 정렬되고, 긴 내용/새 로그 추가 시 최신 로그 쪽으로 이동한다.
- 레벨업 선택지는 `HP/MP`, `스탯 4개`, `기술 2개`의 `2 / 4 / 2` 배열로 정상 노출된다.

## 우선 수정 대상

### 1. 추천 칩이 JSON 문자열 일부로 깨짐

우선순위: 높음

재현 흐름:

1. 새 게임 시작
2. 루카와 대화
3. 엘리엇과 대화
4. `동행 이동 확인` 퀘스트 수락
5. 준비실로 이동
6. 보급 표식 줍기
7. 루카에게 다시 말하기

관찰된 화면:

- 하단 추천 칩이 정상 라벨 대신 JSON 문자열 일부로 보였다.
- 예시:
  - `{"label":"루카에게 말을 겁니다","input_te`

문제:

- 사용자가 클릭 가능한 행동 제안을 자연어 칩으로 이해할 수 없다.
- LLM이 반환한 `---TRPG_META---` 이후 JSON이 정상 파싱되지 않았거나, 파싱 실패 시 원문 조각이 suggestion label로 흘러 들어간 것으로 보인다.
- 서버가 suggestion을 검증할 때 stringified JSON 조각을 그대로 통과시키는 방어가 부족할 수 있다.

의심 영역:

- `server/src/game/runtime/narration/result.py`
- `server/src/game/runtime/narration/input.py`
- `server/src/locale/prompts/graph_narrate/prompt.ko.md`
- `client/services/graphAdapter.ts`
- `client/components/composer/Composer.tsx`
- `client/logic/game/useGame.ts`

검증 방향:

- LLM 응답에서 `suggestions` 배열이 객체 배열이 아닐 때 폐기하는 서버 테스트를 추가한다.
- `label`, `input_text`, `intent`, `action` 필드 타입을 엄격히 검증한다.
- label 또는 input text가 `{`, `"label"`, `"input_text"` 같은 JSON 구조 조각을 포함하면 suggestion을 버리는 방어를 고려한다.
- 클라이언트는 서버 payload를 신뢰하더라도 최소한 비정상적으로 긴/구조화 문자열 라벨을 그대로 칩에 보여주지 않는 방어가 필요할 수 있다.

### 2. 빈 직접 발화 `「」`가 로그에 출력됨

우선순위: 높음

재현 흐름:

1. 준비실 이동 후 루카에게 다시 말하기

관찰된 로그:

```text
「」
```

문제:

- 대사가 비어 있는데 직접 발화 구분자인 `「」`만 출력된다.
- 플레이어 입장에서는 NPC가 아무 말도 하지 않았는지, 시스템 출력이 깨진 것인지 알 수 없다.
- 나레이션 품질 문제를 넘어서 출력 후처리 방어가 필요하다.

의심 영역:

- `server/src/game/runtime/narration/result.py`
- `server/src/locale/prompts/graph_narrate/prompt.ko.md`
- LLM 출력 정리 함수 또는 메타 분리 함수

검증 방향:

- 나레이션 본문 정리 단계에서 빈 직접 발화만 있는 문장을 제거한다.
- `「」`, `「 」`, `""` 같은 빈 발화 패턴을 방어하는 테스트를 추가한다.
- 프롬프트에도 “빈 직접 발화를 출력하지 않는다”는 규칙을 추가한다.

### 3. 현재 장소에 없는 NPC를 나레이션이 계속 언급함

우선순위: 높음

재현 흐름:

1. `동행 이동 확인` 퀘스트 수락
2. `준비실`로 이동
3. 준비실 도착 나레이션 확인
4. 준비실 대상 목록 확인

관찰된 상태:

- 현재 장소 칩: `준비실`
- 대상 요약: `인물 1 · 장소 1 · 물품 1 · 할 일 5`
- 준비실 대상 목록의 인물: `루카` 1명

관찰된 나레이션:

```text
준비실의 공기는 정돈된 상태 그대로 당신을 맞이합니다. 이곳은 돌아가는 길만 열려 있는 테스트 허브입니다. 루카와 엘리엇은 여전히 주변에 서 있고, 노라는 팔의 붕대를 만지작거립니다.
```

문제:

- 실제 현재 장소에는 루카만 있는데 엘리엇과 노라가 주변에 있는 것처럼 서술한다.
- `준비실`을 `돌아가는 길만 열려 있는 테스트 허브`라고 표현해 장소 정체성도 흐려진다.
- 이론 기준으로는 `FictionContinuity` 위반이다. UI의 현재 대상 목록과 나레이션의 가시 대상이 불일치한다.

의심 원인:

- `recent_narration` 또는 이전 `scene_anchor.visible_names`가 현재 장소의 visible targets보다 강하게 작용하는 것으로 보인다.
- LLM이 이전 장소의 등장인물 목록을 현재 장면에 계속 재사용한다.
- prompt는 “입력에 없는 인물은 만들지 않는다”고 되어 있지만, 이전 맥락에 있던 인물을 현재 장소에 다시 투사하는 것을 충분히 막지 못한다.

의심 영역:

- `server/src/game/runtime/narration/context.py`
- `server/src/game/runtime/narration/memory_context.py`
- `server/src/locale/prompts/graph_narrate/prompt.ko.md`

검증 방향:

- 이동 후 narration payload의 `scene_anchor.visible_names`, `target_view`, `recent_narration`, `related_memory`를 확인한다.
- 현재 장소의 visible targets에 없는 NPC 이름이 나레이션 본문에 나오지 않도록 테스트한다.
- prompt에 “현재 장소의 visible targets에 없는 이름은 이전 기억에 있어도 현재 주변에 있다고 쓰지 않는다”는 규칙을 추가한다.
- 가능하면 payload에 `current_visible_names` 같은 명확한 필드를 두고 LLM이 현재 가시 대상과 과거 맥락을 구분하게 한다.

### 4. 보급 표식 줍기 후 상태 변화가 일치하지 않음

우선순위: 높음

재현 흐름:

1. 테스트 허브에서 퀘스트 수락
2. 준비실로 이동
3. 준비실 대상 목록 열기
4. `보급 표식 줍기` 클릭
5. 시트 확인
6. 대상 목록 다시 확인

관찰된 로그:

```text
보급 표식을 줍습니다
보급 표식이 바닥에 놓여 있자 당신은 그것을 집어 올립니다. 작은 표시물이 손안에서 무게를 가지며 익숙한 느낌을 전달합니다.
```

관찰된 상태:

- 시트의 `소지` 항목에는 `보급 표식`이 추가되지 않았다.
- 대상 요약은 계속 `물품 1`로 남았다.
- 대상 목록에도 `보급 표식`이 계속 보이고, `줍기` 액션도 계속 노출됐다.

문제:

- 나레이션은 줍기 성공을 확정하지만, 게임 상태는 변하지 않는다.
- `ExposedTransitionValidity` 위반이다. UI에 노출된 상태 전이와 실제 결과가 맞지 않는다.
- 같은 아이템을 반복해서 줍는 루프가 가능할 수 있다.

의심 원인:

- `보급 표식`이 실제 inventory transfer 대상이 아니라 환경 마커/quest marker로 처리되고 있을 수 있다.
- action label은 `줍기`인데 graph action이 실제 item pickup change를 만들지 못할 수 있다.
- location item과 inventory item의 edge 업데이트가 누락됐거나, client front-state 변환에서 업데이트가 반영되지 않았을 수 있다.

의심 영역:

- `client/logic/story-graph/_nodeActions.ts`
- `server/src/game/runtime/flow/input.py`
- `server/src/game/runtime/flow/confirmation.py`
- `server/src/game/runtime/action/apply.py`
- `server/src/game/engines/graph/*pickup*`, `inventory`, `transfer` 관련 코드
- `server/src/wire/graph/to_front.py`
- `scenarios/dev_test/items.json`
- `scenarios/dev_test/locations.json`

검증 방향:

- `보급 표식 줍기` graph action이 어떤 `Action` 또는 `GraphChange`로 변환되는지 테스트한다.
- 줍기 후 `located_at:item:place` edge가 제거되고 `carries:player:item` edge가 생기는지 확인한다.
- 줍기 후 front payload의 nearby items에서 해당 물품이 사라지는지 확인한다.
- 보급 표식이 실제 획득 불가 마커라면 `줍기` 액션을 노출하지 않아야 한다.

## 중간 우선순위 개선 사항

### 5. 퀘스트 수락 나레이션이 추상적이고 과장됨

우선순위: 중간

관찰된 나레이션:

```text
퀘스트를 수락하자 당신은 동행 이동 확인이라는 새로운 여정을 시작합니다. 테스트 허브의 공기는 이전과 크게 다르지 않으나, 이제 그곳에 부여된 역할이 달라진 듯한 미묘한 긴장감이 감돕니다.
```

문제:

- 개발용 테스트 허브의 “동행 이동 확인” 퀘스트에 비해 `새로운 여정`, `미묘한 긴장감`이 과장되어 있다.
- 현재 목표는 `준비실로 이동`이므로, 더 구체적으로 “루카가 체크리스트를 들고 따라올 준비를 한다”처럼 쓰는 편이 낫다.
- 이론 기준으로는 `FictionContinuity`와 `AgencyContinuity`를 더 잘 살리려면 현재 목표와 다음 행동 가능성을 구체적으로 보여줘야 한다.

개선 방향:

- prompt에서 추상 표현 회피 규칙을 더 강화한다.
- 퀘스트 수락 이벤트에는 `current objective`, `giver`, `next step`을 우선 장면화하도록 한다.
- “여정”, “긴장감”, “기운”, “역할이 달라짐” 같은 표현은 구체 상태가 없으면 피한다.

### 6. 지도 탭 접근성 active 상태 불일치

우선순위: 중간 또는 낮음

재현 흐름:

1. 지도 탭 열기
2. 지도 탭 다시 눌러 닫기
3. 화면상 지도 패널은 닫혔지만 DOM snapshot에서 `button "지도" [active]`가 남는 경우 확인

문제:

- 시각적으로는 큰 문제가 없어 보인다.
- 접근성 상태와 실제 화면 상태가 어긋나면 스크린리더나 자동 테스트에서 잘못된 상태로 인식할 수 있다.

의심 영역:

- `client/components/ui/Chip.tsx`
- `client/components/info-panel/ContextCard.tsx`
- `client/screens/play/Playing.tsx`

검증 방향:

- `Chip`의 `accessibilityState.selected` 또는 active 스타일이 실제 `activeId`와 정확히 동기화되는지 확인한다.
- React Native web의 active/focus pseudo state가 DOM snapshot에 `[active]`로 남는 것인지, 실제 accessibility state인지 구분한다.

### 7. 노트/시트 DOM 텍스트 중복

우선순위: 낮음

관찰:

- 노트 패널 DOM에서 `노트`, `루카 · 동행 점검자`, `동행 이동 확인`, `준비실로 이동...` 등이 중복으로 잡힌다.
- 시트 패널 DOM에서도 `주인공`, `Lv 1`, 장비/소지품 텍스트가 중복으로 잡힌다.

문제:

- 화면상으로는 큰 시각 문제는 없다.
- 접근성 트리에서 같은 정보가 두 번 읽힐 가능성이 있다.

의심 영역:

- `Expandable`, `ExpandableTitle`, `InlineParts`, `InlineNodes` 같은 측정용/숨김 텍스트 컴포넌트
- `client/components/ui/Expandable*.tsx`
- `client/components/info-panel/PanelBody.tsx`

검증 방향:

- 측정용 텍스트가 `aria-hidden` 또는 접근성 숨김 처리가 되어 있는지 확인한다.
- DOM snapshot 중복이 실제 스크린리더 중복인지, 테스트 snapshot의 구현 디테일인지 구분한다.

## 현재 정상으로 보인 부분

- 새 게임 생성 화면의 순서:
  - 이름
  - 성별
  - 세계
  - 종족
  - 언어
  - 시작
- `English` 선택지 미노출
- 지도/노트/시트 패널이 로그를 덮지 않는 구조
- 주변 대상 목록의 스크롤 동작
- 시각적 스크롤바 제거
- 퀘스트 수락 확인 모달
- 목표 칩 `목표 준비실로 이동`
- 레벨업 선택지의 `2 / 4 / 2` 배열
- 브라우저 콘솔:
  - 새 에러 없음
  - 기존 개발 경고만 있음
    - Reanimated reduced motion
    - `props.pointerEvents is deprecated`
    - Animated `useNativeDriver` fallback

## 권장 패치 순서

1. LLM 메타 JSON 파싱/검증 방어
   - JSON 조각 추천 칩 방지
   - 빈 직접 발화 제거
   - 서버 테스트 우선

2. 현재 장소 가시 대상과 나레이션 일치 강화
   - 이동 후 현재 visible targets만 현재 주변 인물로 서술
   - 이전 장소 인물은 “이전에는 보였다” 이상의 현재성 표현 금지
   - prompt와 context payload 테스트 추가

3. 보급 표식 줍기 상태 전이 수정
   - 실제 획득 가능 물품이면 inventory로 이동
   - 획득 불가 마커면 `줍기` 액션 노출 금지
   - nearby summary와 sheet inventory 동시 검증

4. 퀘스트 수락 나레이션 구체화
   - 목표/다음 행동/동행자 상태 중심
   - 추상 표현 축소

5. 접근성/DOM 상태 정리
   - active 상태 불일치 확인
   - 측정용 텍스트 접근성 숨김 처리 검토

## 패치 성공 기준

- 루카에게 반복 대화해도 빈 `「」`가 출력되지 않는다.
- 추천 칩에는 사람이 읽는 짧은 라벨만 나온다.
- 이동 후 현재 장소에 없는 NPC가 “주변에 있다”고 서술되지 않는다.
- 준비실 대상 목록의 인물 수와 나레이션의 현재 인물 언급이 일치한다.
- `보급 표식 줍기` 후 다음 둘 중 하나가 일관되게 성립한다.
  - 실제 획득형: 대상 목록에서 사라지고 시트 소지품에 추가된다.
  - 비획득형: 애초에 `줍기` 액션이 노출되지 않는다.
- 퀘스트 수락/이동 나레이션은 추상적 분위기보다 현재 목표와 관찰 가능한 변화 중심으로 나온다.
- 관련 서버 테스트, 클라이언트 테스트, 브라우저 확인이 모두 통과한다.
