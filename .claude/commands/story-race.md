---
description: 시나리오에 새 race (종족) 한 개 시드를 추가한다
argument-hint: <scenario> [한 줄 힌트]
allowed-tools: Read, Glob, Write
---

# Story — Race Writer

너는 TRPG 시나리오의 새 종족 시드를 만드는 작가다. 아래 순서를 그대로 따른다.

## 1. 인자 파싱

`$ARGUMENTS` 의 첫 토큰 = `<scenario>` (시나리오 디렉터리 이름, 예: `default`).
나머지 토큰 = 새 종족에 대한 한 줄 힌트 (선택, 비어 있을 수 있음).

`<scenario>` 가 비어 있으면 즉시 멈추고 "scenario 인자가 필요합니다 (예: `/story-race default 달빛에 활동하는 종족`)" 라고만 보고.

## 2. 컨텍스트 수집

다음을 읽는다 — 한 번에 병렬로:

- `scenarios/<scenario>/world.md` — 톤·세계관
- Glob `scenarios/<scenario>/races/*.json` 으로 기존 race 파일 목록 받고 각각 Read

`world.md` 가 없거나 `races/` 가 비어 있어도 진행은 가능하지만, 결과 보고에 한 번 알린다.

## 3. race 한 개 설계

스키마:

```json
{
  "id": "<ASCII snake_case>",
  "name": "<한국어 종족명>",
  "description": "<한국어 한두 문장>",
  "racial_skills": []
}
```

규칙 (어기면 안 됨):

- `id` — `^[a-z][a-z0-9_]{1,30}$`. 보통 영어 단어 하나. **기존 race id 와 절대 겹치지 않게.**
- `name` — 한국어. 영문 음차 금지 ("휴먼" 안 됨, "인간" OK).
- `description` — 한국어 한두 문장. 기존 races 의 description 과 같은 톤·길이.
- `racial_skills` — 빈 리스트 `[]` (기존 races 가 모두 비어 있어서, 첫 단계에서 skill 합성은 미루기).
- 톤·시대·갈등은 `world.md` 와 어울리고, 역할·뉘앙스는 기존 races 와 의미적으로 겹치지 않게.
- 힌트가 비어 있으면 `world.md` + 기존 races 만으로 자체 판단해서 한 종족 만든다.

## 4. 디스크 쓰기

`scenarios/<scenario>/races/<id>.json` 으로 Write.

- `indent=2`, 키 순서는 위 스키마 그대로 (`id, name, description, racial_skills`).
- 한국어는 그대로 둔다 (`\uXXXX` escape 금지).
- 같은 경로 파일이 이미 있으면 덮어쓰지 말 것 — `<id>` 를 다른 단어로 바꿔 한 번만 재시도. 그래도 충돌이면 멈추고 보고.

## 5. 보고

성공 시 한 단락으로:
- 저장한 파일 경로
- 만든 race 의 `name` — `description`
- (있으면) world/races 누락에 대한 알림
