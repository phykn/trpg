---
name: story-build
description: 한국어 산문(prose) 한 편으로 시나리오 디렉토리 한 개를 빌드. 사용자가 "이 스킬 보고 X.md로 시나리오 만들어줘"라고 지시하면 따른다.
---

# Story Build Skill

이 스킬은 한국어 산문 한 편을 받아 `scenarios/<name>/` 디렉토리 전체(world.md + 7 entity dirs + 3 meta files)를 만드는 절차를 정의한다. Codex 세션 자체가 작성자다 — 외부 LLM 호출 없음. 검사·자동채우기는 `agency.story.tool` CLI에 위임한다.

## 입력

- `<prose-path>`: 한국어 산문 .md 파일 경로
- `<scenario-name>`: 새 시나리오 디렉토리 이름 (예: `default`, `shadowfen`)

## 사전 점검

- `scenarios/<name>/`이 이미 존재하면 사용자에게 묻고 진행 (절대 자동 덮어쓰기 금지)
- 작업 디렉토리: 항상 repo root (`.venv/bin/python`로 실행)

## 워크플로 (13단계, 위에서 아래로)

### 1. decompose (3-phase)

prose를 읽고 다음을 결정:
- 세계관 한 단락 + 시나리오 이름·설명 (Phase A)
- race·skill·location 명단 + 시작 위치 (Phase A)
- character·item 명단 + 시작 주체 (Phase B)
- quest·chapter 명단 + 시작 퀘스트 (Phase C)

각 phase 결과를 JSON으로 짜서 `scenarios/<name>/.decomp/{setup,cast,arc}.json`에 쓴다.
검사:
```bash
.venv/bin/python -m agency.story.tool decompose-setup scenarios/<name>/.decomp/setup.json
.venv/bin/python -m agency.story.tool decompose-cast  scenarios/<name>/.decomp/setup.json scenarios/<name>/.decomp/cast.json
.venv/bin/python -m agency.story.tool decompose-arc   scenarios/<name>/.decomp/setup.json scenarios/<name>/.decomp/cast.json scenarios/<name>/.decomp/arc.json
```

`.decomp/` 는 빌드 끝나도 남겨둔다 — `check-entity --decomp`가 참조하고, 회귀 시 진단용이다.

### 2. world.md

decompose의 `world_md` 본문을 `scenarios/<name>/world.md`에 쓴다.

### 3. race × N

각 race를 `scenarios/<name>/races/<id>.json`로 쓴다. `racial_skill_ids`는 decompose 명단의 ID로 채운다 (스킬 파일은 아직 없지만 `--decomp`가 인정).

검사 (race 한 개당):
```bash
.venv/bin/python -m agency.story.tool check-entity race scenarios/<name>/ scenarios/<name>/races/<id>.json --decomp scenarios/<name>/.decomp/
```

### 4. location × N

`connections`(decomp의 `connection_ids`를 양방향 대칭 폐포로 변환), `item_ids`(decomp items 중 owner_location_id 매칭)을 채워서 쓴다.

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity location scenarios/<name>/ scenarios/<name>/locations/<id>.json --decomp scenarios/<name>/.decomp/
```

### 5. character × N

`racial_skill_ids` (race 상속), `learned_skill_ids` (decomp), `inventory_ids` (decomp items 중 owner_character_id 매칭)을 채운다. `equipment` 슬롯은 비운 상태로 둔다 (Step 8에서 채움).

검사 (skeleton 모드 — items가 아직 없으므로 풀-의존 검사는 sweep까지 미룸):
```bash
.venv/bin/python -m agency.story.tool check-entity character scenarios/<name>/ scenarios/<name>/characters/<id>.json --decomp scenarios/<name>/.decomp/ --skeleton
```

### 6. skill × N

이 시점에 `characters/`가 디스크에 있다. 각 skill의 owner(race 또는 character)를 `racial_skill_ids` / `learned_skill_ids`에서 역추적해서, owner의 직업·레벨·역할을 보고 이름·설명·special_effect를 자연스럽게 맞춘다.

규칙:
- racial 스킬: `level` 항상 1
- 캐릭터 학습 스킬: `level ≤ owner의 character.level` (가장 낮은 owner 레벨에 맞춤)

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity skill scenarios/<name>/ scenarios/<name>/skills/<id>.json --decomp scenarios/<name>/.decomp/
```

### 7. item × N

owner character 정보(직업·레벨·역할)를 보고 무기·갑옷의 효과·이름·설명을 맞춘다.

규칙:
- seed item은 `required` 항상 `null`.
- decomp `kind`가 `"weapon"`이면 `effects.type="weapon"`, `"armor"`면 `effects.type="armor"`, `"consumable"`이면 `effects.type="consumable"`, `"key"`이면 `effects=null`

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity item scenarios/<name>/ scenarios/<name>/items/<id>.json --decomp scenarios/<name>/.decomp/
```

### 8. equip-fill

```bash
.venv/bin/python -m agency.story.tool equip-fill scenarios/<name>/
```

이 시점에 모든 character의 `equipment` 슬롯이 inventory의 effect 보고 자동 배치된다 (검 → weapon, 갑옷 → armor, 둘 다 차면 다음 갑옷은 accessory).

### 9. quest × N

각 quest:
- `giver_id`: decomp 그대로
- `triggers`: 단일 trigger (`type=trigger_kind`, `target_id=target_id`)
- `prerequisite_ids`: decomp 그대로
- `status`: prerequisite_ids 비어 있으면 `"active"`, 아니면 `"locked"`
- `required`: decomp 그대로

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity quest scenarios/<name>/ scenarios/<name>/quests/<id>.json
```

### 10. chapter × N

각 chapter:
- `quest_ids`: decomp 그대로 (퀘스트를 chapters 사이에 분할)
- `prerequisite_ids`: decomp 그대로
- `status`: prerequisite_ids 비어 있으면 `"active"`, 아니면 `"locked"`

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity chapter scenarios/<name>/ scenarios/<name>/chapters/<id>.json
```

### 11. meta files

`profile.json`, `start.json`, `player_template.json`을 decompose 데이터 보고 직접 작성:

`profile.json`:
```json
{"id": "<scenario-name>", "name": "<decomp.profile_name>", "description": "<decomp.profile_description>"}
```

`start.json`:
```json
{
  "start_location_id": "<decomp.start_location_id>",
  "active_subject_id": "<decomp.start_subject_id>",
  "active_quest_id": "<decomp.start_quest_id>"
}
```

`player_template.json`:
```json
{
  "id": "player_01",
  "equipment": {},
  "inventory_ids": [<decomp.items 중 for_player_template=true인 id 들>]
}
```

### 12. invariant sweep

```bash
.venv/bin/python -m agency.story.tool sweep scenarios/<name>/
```

PASS 안 되면 어디 깨졌는지 메시지 보고 위로 거슬러 올라가 고침.

### 13. publish

release Supabase Storage에 publish. 사용자에게 한 번 확인을 받은 뒤 실행:
```bash
APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload scenarios/<name>/
```

`APP_ENV=release`는 release bucket에 직접 쓴다. 올리는 순간 release 서버에서 읽을 수 있다. 로컬에서 지운 파일은 bucket에서 안 지워지니, 시나리오 이름이나 ID를 바꿨으면 dashboard에서 직접 청소한다.

## 엔티티 카드 (작성 규칙 요약)

(각 카드는 시나리오 JSON 레코드 기준입니다. 런타임은 graph seed builder가 이 레코드를 읽어 그래프 노드와 엣지로 변환합니다.)

### race
- 필수: `id`, `name`, `description`, `is_humanoid`, `racial_skill_ids` (≥1, 평민 종족도 `barter` 같은 일상 능력 1개 필요 — NPC 시드는 ≥1 스킬 invariant 때문)
- 톤: 한국어 두세 문장. 외래어 음역(`엘프 (Elf)`) 금지.

### location
- 필수: `id`, `name`, `description`, `connections`, `item_ids`, `props`
- self-loop 금지 (`connections`에 자기 자신 ID).
- props는 캐릭터가 상호작용할 만한 정적 환경 요소 (등불, 우물, 벤치 등).

### character
- 필수: `id`, `name`, `description`, `race_id`, `location_id`, `level`, `stats`, `racial_skill_ids`, `learned_skill_ids`, `inventory_ids`, `equipment`, `job`, `gender`, `alive`, `memorable`, `memories`, `relations`, `disposition`, `is_enemy`, `xp_reward`
- NPC와 적은 HP/MP를 쓰지 않는다. 플레이어 HP/MP는 `player_template.json`에서 engine이 계산한다.
- `stats`는 `body`, `agility`, `mind`, `presence`만 사용한다.
- `is_enemy=true`이면 `combat_behavior` 필수 (`{attack_priority}`), `xp_reward > 0` (level 1: 40~80, level 3: 100~200, level 5+: 250+).
- `is_enemy=false`이면 `combat_behavior` 생략, `xp_reward=0`.
- 인간형 race는 갑옷 1개 이상 필수, 적이면 무기도 필수.

### skill
- 필수: `id`, `name`, `description`, `type`(attack/heal/buff/debuff), `primary_stat`, `level`, `mp_cost`, `cooldown`, `target`, `special_effect`
- `primary_stat`은 `body`, `agility`, `mind`, `presence` 중 하나.
- racial 스킬은 `level=1` 강제.
- 캐릭터가 학습한 스킬은 `level ≤ owner의 character level`.

### item
- 필수: `id`, `name`, `description`, `weight`, `effects`, `required`
- `required` 항상 `null` (seed에서). 부분 명시도 금지.
- effects shape: weapon → `{type, weapon_dice, ...}`; armor → `{type, defense, ...}`; consumable → `{type, ...}`; key → `null`.

### quest
- 필수: `id`, `title`, `description`, `giver_id`, `triggers`, `fail_triggers`, `prerequisite_ids`, `status`, `required`, `rewards`
- `giver_id` 는 비-적대 character만.
- trigger.type=`character_death`의 target은 적대 character만 (비-적대는 안 죽으므로 영원히 미완 상태).
- prerequisite_ids는 self-loop·cycle 금지.

### chapter
- 필수: `id`, `title`, `description`, `quest_ids`, `prerequisite_ids`, `status`
- quest_ids는 chapters 사이에 정확히 1번씩 등장 (전체 quest 집합 분할).
- 시작 chapter는 `prerequisite_ids=[]`, 시작 quest를 포함, 다른 quest는 prerequisite으로 잠긴 상태.

## 에러 행동 규칙

### 한 파일이 잘못된 경우

검사 명령이 종료 코드 1을 반환했을 때:
1. stderr 메시지 읽고 어느 파일·어느 필드·왜 깨졌는지 파악
2. 해당 파일 한 개만 고침
3. 같은 검사 명령 다시 실행
4. 같은 파일·같은 에러가 2회 연속이면 멈추고 사용자에게 보고. 자동 무한 반복 금지.

### 위쪽 단계 실수가 늦게 드러난 경우

예: quest 단계에서 "trigger의 target_id가 존재하지 않는 character_id" 발견. 원인은 decompose에서 character 명단을 잘못 만든 것.

→ `.decomp/cast.json`부터 고치고 영향받는 character·item·quest 파일들 다시 검사.

가짜 character를 만들어서 quest를 통과시키는 식의 우회 금지. 시나리오 전체 일관성을 깨뜨림.

흔한 우회 패턴 (절대 금지):
- 존재하지 않는 ID를 가리키는 ref를 빈 문자열·placeholder로 바꿈
- 검사 통과를 위해 의미 없는 enemy character를 추가
- prerequisite cycle을 끊기 위해 임의로 prereq 제거 (퀘스트 순서가 망가짐)

### 빌드 중간에 멈춘 경우

세션 종료, 네트워크 오류, 사용자 중단으로 시나리오 디렉토리에 파일이 일부만 있는 상태.

→ 자동 이어가기 금지. 사용자에게 두 선택지를 보여줌:
- (a) 디렉토리 통째로 지우고 처음부터
- (b) 어디까지 됐는지 사람이 검사하고 다음 단계부터 수동

자동으로 이어가면 어디까지 일관성 있는지 판정이 어려워서 잘못 publish될 위험이 큼.

## 참고

- 모든 한국어 텍스트는 **2인칭 존댓말 합니다체**(`당신` / `~합니다 / ~ㅂ니다 / ~입니다`).
- 사용자에게 보이는 스킬 이름은 **기술** (`스킬`은 classify 프롬프트에서만 동의어로 받음 — 시드 텍스트는 `기술`).
- 작업 디렉토리는 항상 repo root.
- 환경 변수 부팅: `agency.story.tool`과 `agency.story.tools.storage`가 자체적으로 `server/.env.<APP_ENV>`를 로드한다. `APP_ENV` 미지정시 `dev`. publish 단계에서만 `APP_ENV=release` 명시.
