---
description: 줄글 한 편으로 시나리오 한 벌 (world.md + 6 entity 디렉터리 + 메타 3 파일) 생성
argument-hint: <new_scenario_name> <prose-path>
allowed-tools: Read, Glob, Write, Bash
---

# Story — Scenario Builder

너는 한국어 산문 줄글을 받아 TRPG 시나리오 한 벌을 만드는 작가다. 단계 파이프라인을 그대로 따른다.

## 0. 인자 파싱

`$ARGUMENTS` 의 첫 토큰 = `<new_scenario_name>` (예: `default_claude`).
두 번째 토큰 = `<prose-path>` (예: `agency/story/sources/default.md`).

`<new_scenario_name>` 또는 `<prose-path>` 가 비어 있으면 멈추고 사용법 보고:

```
사용법: /story-scenario <new_scenario_name> <prose-path>
  예: /story-scenario default_claude agency/story/sources/default.md
```

`scenarios/<new_scenario_name>/` 가 이미 존재하면 멈추고 보고 (덮어쓰지 않음).

## 1. 분해 단계

`agency/story/agents/_decompose.md` 와 `<prose-path>` 를 Read.

`_decompose.md` 의 스키마·규칙을 따라 줄글을 분해한 결과를 머릿속에 만든다 (`Decomposition` 객체):

- `world_md` (markdown 한두 단락)
- `profile_name`, `profile_description`
- `races[]`, `locations[]`, `items[]`, `characters[]`, `quests[]`, `chapters[]` 명단 — 각 entry 가 `id` + `role` (+ kind/is_enemy/trigger 정보 등)
- `start_location_id`, `start_subject_id`, `start_quest_id`

분해 일관성을 자체 검증:
- 모든 id 가 `^[a-z][a-z0-9_]{1,30}$`, 종류 안에서 unique
- `start_*` 셋이 자기 종류 명단 안에 실재
- `quests[*].target_id` 가 `trigger_kind` 따라 적절한 명단 안에 (`character_death` → characters, `location_enter` → locations, `item_use` → items)
- `chapters` 가 1 개 이상

어긋나면 다시 분해 (한 번 재시도).

## 2. 디렉터리 + world.md

`mkdir -p scenarios/<new_scenario_name>` (Bash 로). 그 안의 entity 디렉터리는 entity 파일 Write 시 자동 생성됨.

`scenarios/<new_scenario_name>/world.md` 에 분해 결과의 `world_md` 본문을 Write.

## 3. entity 단계 (race → location → item → character → quest → chapter)

각 단계에서 분해 명단의 entry 마다 한 개씩 entity JSON 을 만들어 Write. 각 entity 의 도메인 규칙은 `agency/story/agents/<kind>.md` (race/location/item/character/quest/chapter) + `agency/story/agents/_base.md` 가 정의 — 각 단계 시작 전 한 번씩 Read.

**핵심 강제**:
- entity 의 `id` 는 분해 명단의 id 와 정확히 일치해야 한다 (자유 변경 X).
- 모든 참조 (race_id / location_id / inventory_ids / equipment / giver_id / triggers[*].target_id / quest_ids) 는 시나리오에 실재하는 id 만 사용 — 그 단계 시점에 이미 디스크에 박혀 있는 entity 의 id 만 가능. 단계 순서가 그래서 정해져 있음.
- 톤·세계관은 `world.md` 와 일치, 같은 종류 entity 끼리 어휘·길이 일관.

**단계별 디테일**:

- **race**: `racial_skills: []`. 분해 명단 순서대로.
- **location**: `connections[*].target_id` 는 이 단계 안에서 이미 만들어진 다른 location 만 가리킴 (먼저 만들어진 것만 참조 가능, 또는 양방향 안 박고 한쪽만). 자기 자신 금지.
- **item**: 분해 명단의 `kind` 에 따라 `effects` 모양 결정 (weapon/armor/consumable/key — `key` 는 `consumable: true, on_use: "<용도>"` 정도).
- **character**: `race_id` 는 races/, `location_id` 는 locations/, `inventory_ids`/`equipment` 슬롯 값은 items/. `is_enemy: true` 였던 entry 는 `combat_behavior` 박기, `aggressive` 70~100. 비적대는 50± 근처.
- **quest**: 분해 명단의 `trigger_kind` + `target_id` 를 그대로 `triggers[0]` 에 박기. `start_quest_id` 와 일치하는 quest 만 `status: "active"`, 나머지는 `"locked"`. `giver_id` 는 분해 단계에서 명시 안 됐으면 의뢰 맥락에서 고른 character (의뢰자 역할).
- **chapter**: `quest_ids` 에 분해 명단의 모든 quest id 를 박는다. 첫 chapter 만 `status: "active"`, 나머지는 `"locked"`.

각 entity 를 만들 때 "JSON 객체 한 개만, 한국어 단일, id ASCII snake_case" 등 `_base.md` 의 공통 규칙을 따른다. 결과는 `scenarios/<new_scenario_name>/<sub_dir>/<id>.json` 에 indent=2 로 Write.

## 4. 메타 파일 3 개

- `scenarios/<new_scenario_name>/profile.json`:
  ```json
  {"id": "<new_scenario_name>", "name": "<profile_name>", "description": "<profile_description>"}
  ```
- `scenarios/<new_scenario_name>/start.json`:
  ```json
  {"start_location_id": "...", "active_subject_id": "...", "active_quest_id": "...", "world_time": "0001-01-01T09:00:00"}
  ```
- `scenarios/<new_scenario_name>/player_template.json`:
  ```json
  {"id": "player_01", "equipment": {}, "inventory_ids": []}
  ```

모두 `indent=2`, 한국어 escape 없이.

## 5. 보고

성공 시:
- 만든 디렉터리 경로
- entity 수 (race N · location N · item N · character N · quest N · chapter N)
- start 위치·subject·quest 한 줄

실패한 단계가 있으면 어느 entity 의 무슨 검증이 실패했는지, 무엇으로 교정했는지 한 줄.
