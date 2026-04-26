---
description: 시나리오에 새 entity (race / location / item / character / quest / chapter) 한 개 시드를 추가한다
argument-hint: <kind> <scenario> [한 줄 힌트]
allowed-tools: Read, Glob, Write
---

# Story — Entity Writer

너는 TRPG 시나리오의 새 entity 시드를 만드는 작가다. 아래 순서를 그대로 따른다.

## 1. 인자 파싱

`$ARGUMENTS` 의 토큰을 순서대로:

- 첫 번째 = `<kind>` ∈ `{race, location, item, character, quest, chapter}`
- 두 번째 = `<scenario>` (시나리오 디렉터리 이름, 예: `default`)
- 나머지 = 한 줄 힌트 (선택)

`<kind>` 가 위 6 종이 아니거나 `<scenario>` 가 비어 있으면 즉시 멈추고 사용법 보고:

```
사용법: /story-write <kind> <scenario> [hint]
  kind: race | location | item | character | quest | chapter
  예: /story-write character default 은퇴한 노검사
```

## 2. 컨텍스트 수집 (병렬 Read)

`<kind>` → `<sub_dir>` 매핑:
- race → races, location → locations, item → items, character → characters, quest → quests, chapter → chapters

다음을 한 번에 모두 Read:

- `agency/story/agents/_base.md` — 공통 규칙
- `agency/story/agents/<kind>.md` — 그 entity 의 도메인 규칙
- `scenarios/<scenario>/world.md` — 톤·세계관
- Glob `scenarios/<scenario>/<sub_dir>/*.json` 으로 그 종류의 기존 instance 모두
- `<kind>` 가 참조하는 다른 종류도 Glob+Read:
  - location → locations (자기 종류, 위에서 이미)
  - character → races, locations, items, characters
  - quest → characters, locations, items, quests
  - chapter → quests
  - race·item → 다른 종류 컨텍스트 불필요

## 3. entity 한 개 설계

`<kind>.md` 의 스키마·규칙을 따른다. 위에 `_base.md` 의 공통 규칙:

- JSON **객체 한 개만** 머리 속에서 만듦 (실제 파일 출력은 5단계).
- 한국어 단일, 영문 음차 금지.
- `id` 는 `^[a-z][a-z0-9_]{1,30}$`, 기존 instance 와 절대 중복 X.
- 모든 참조 (race_id / location_id / giver_id / triggers[*].target_id / quest_ids 등) 는 시나리오에 실재하는 id 만 사용.

## 4. 자체 검증

작성한 JSON 을 머리속에서 한 번 검토:

- Pydantic 스키마 어긋남 없음 — 필수 필드, 타입, enum 값.
- `id` 패턴 OK, 기존과 안 겹침.
- 모든 참조 id 가 시나리오 안에 실재함.
- 톤·세계관 일치 (기존 instance 의 어휘·길이 패턴).

어긋나면 다시 짜기 (한 번 재시도).

## 5. 디스크 쓰기

`scenarios/<scenario>/<sub_dir>/<id>.json` 으로 Write — `indent=2`, 한국어는 escape 없이 그대로 (`\\uXXXX` 금지).

같은 경로 파일이 이미 있으면 `<id>` 를 다른 단어/번호로 바꿔 한 번 재시도. 두 번 충돌이면 멈추고 보고.

## 6. 보고

성공 시 한 단락:

- 저장한 파일 경로
- entity 의 핵심 한 줄 (예: race 면 `name — description`, character 면 `name (race · job) — role`, quest 면 `title (giver · difficulty)`)
- (있으면) 누락 컨텍스트 알림 (예: `world.md` 가 없어 톤 추정에 한계)
