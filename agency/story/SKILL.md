---
name: story-build
description: 한국어 산문(prose) 한 편으로 시나리오 디렉토리 한 개를 빌드. 사용자가 "이 스킬 보고 X.md로 시나리오 만들어줘"라고 지시하면 따른다.
---

# Story Build Skill

이 스킬은 한국어 산문 한 편을 받아 실행 가능한 시나리오 seed를 만드는 절차를 정의한다. Codex 세션 자체가 작성자다 — 외부 LLM 호출 없음. 검사·자동채우기는 `agency.story.tool` CLI에 위임한다.

## 입력

- `<prose-path>`: 한국어 산문 .md 파일 경로
- `<scenario-name>`: 새 시나리오 디렉토리 이름 (예: `default`, `shadowfen`)

## 사전 점검

- `scenarios/<name>/`이 이미 존재하면 사용자에게 묻고 진행 (절대 자동 덮어쓰기 금지)
- 작업 디렉토리: 항상 repo root (`.venv/bin/python`로 실행)

## 워크플로 (15단계, 위에서 아래로)

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

`world.md`는 런타임 나레이션 LLM이 참고하는 시나리오 전체 운영 가이드다. 단순 줄거리 요약만 두지 말고 다음을 짧게 포함한다.

- 시나리오의 핵심 전제와 진행 구조
- 나레이션 톤: 문장 길이, 감정 표현 방식, 동행 NPC의 말투
- 장면 운영 규칙: 이동 순서, 판단 전 정보 공개, 보상/무보상 처리
- 금지선: seed에 없는 인물·장소·규칙 생성 금지, 플레이어 감정 단정 금지, 장르 이탈 금지

구체 NPC/퀘스트 사실을 길게 중복 저장하지 않는다. 그런 사실은 `characters.json`, `locations.json`, `quests.json`, `knowledge.json`에 둔다.

### 3. race

각 race 레코드를 쓴다. `racial_skills`는 decompose 명단의 ID로 채운다 (스킬 파일은 아직 없지만 `--decomp`가 인정).

검사 (race 한 개당):
```bash
.venv/bin/python -m agency.story.tool check-entity race scenarios/<name>/ scenarios/<name>/races/<id>.json --decomp scenarios/<name>/.decomp/
```

### 4. location

`connections`(decomp의 `connections`를 양방향 대칭 폐포로 변환), `items`(decomp items 중 owner_location 매칭)을 채워서 쓴다.

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity location scenarios/<name>/ scenarios/<name>/locations/<id>.json --decomp scenarios/<name>/.decomp/
```

### 5. character

`learned_skills` (decomp), `inventory` (decomp items 중 owner_character 매칭)을 채운다. 종족 기술은 character에 복사하지 않는다 — runtime이 race의 `racial_skills`에서 `grants_skill` edge를 만든다. NPC `equipment`는 `{}`로 둔다. NPC용 기본 옷·갑옷·장신구 같은 장비성 placeholder 아이템은 만들지 않는다.

검사 (skeleton 모드 — items가 아직 없으므로 풀-의존 검사는 sweep까지 미룸):
```bash
.venv/bin/python -m agency.story.tool check-entity character scenarios/<name>/ scenarios/<name>/characters/<id>.json --decomp scenarios/<name>/.decomp/ --skeleton
```

### 6. skill

이 시점에 `characters/`가 디스크에 있다. 각 skill의 owner(race 또는 character)를 race의 `racial_skills` / character의 `learned_skills`에서 역추적해서, owner의 역할·레벨·서사를 보고 이름·설명·판정 보정치를 자연스럽게 맞춘다.

규칙:
- racial 스킬: `level` 항상 1
- 캐릭터 학습 스킬: `level ≤ owner의 character.level` (가장 낮은 owner 레벨에 맞춤)
- `action`은 `"attack"`, `"defend"`, `"flee"`, `"talk"` 중 하나. support catalog를 쓰면 `actions.json`에도 같은 id가 있어야 한다.
- 판정 보정은 `bonus`, MP 비용은 `mp_cost`로 둔다. `special_effect`, `type`, `target`, `primary_stat` 같은 예전 LLM 스키마 필드는 seed에 쓰지 않는다.

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity skill scenarios/<name>/ scenarios/<name>/skills/<id>.json --decomp scenarios/<name>/.decomp/
```

### 7. item

owner character 정보(역할·레벨·서사)를 보고 무기·갑옷의 효과·이름·설명을 맞춘다.

규칙:
- 장비는 `slot`으로 장착 위치를 둔다: `"weapon"`, `"armor"`, `"accessory"`.
- 판정 지원 아이템은 `action` + `bonus` + 선택적 `effect`를 쓴다. 지원 효과는 고정 id(`dc_down`, `dc_up`)만 쓴다.
- 회복 소모품은 `effect="heal"` 또는 `"mp_restore"`와 정수 `amount`를 함께 둔다.
- 시나리오 전용 공개 단서가 있으면 `knowledge`에 `knowledge.json` id를 연결한다.
- `required`, `effects`, `effects.type`, `on_use=null` 같은 예전/빈 필드는 쓰지 않는다.

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity item scenarios/<name>/ scenarios/<name>/items/<id>.json --decomp scenarios/<name>/.decomp/
```

### 8. equip-fill

```bash
.venv/bin/python -m agency.story.tool equip-fill scenarios/<name>/
```

이 시점에 모든 NPC character의 `equipment`가 `{}`로 정규화된다. 서버 그래프는 `equips` edge의 owner를 player로만 허용한다. NPC에게 기본 옷·갑옷·장신구를 보충 생성하지 않는다. 플레이어 장비는 `player.json.equipment`에서만 다룬다.

게이트: 이 단계 뒤에 `characters/*.json`의 `equipment`에는 어떤 item id도 남아 있으면 안 된다. 이 규칙을 어기면 게임 시작 시 서버 그래프 검증에서 `equips owner must be player`로 실패하고, 클라이언트에는 `Failed to fetch`처럼 보일 수 있다.

### 9. quest

각 quest:
- `giver`: decomp 그대로
- `triggers`: 단일 trigger (`type=trigger_kind`, `target=target`)
- `fail_triggers`: 없으면 빈 배열
- `prerequisites`: decomp 그대로
- `status`: prerequisites 비어 있으면 `"active"`, 아니면 `"locked"`
- `required`: decomp 그대로
- `rewards`: 최소 `{ "gold": 0, "exp": 0, "items": [] }`

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity quest scenarios/<name>/ scenarios/<name>/quests/<id>.json --decomp scenarios/<name>/.decomp/
```

### 10. chapter

각 chapter:
- `description`: decomp의 chapter 설명이나 해당 장 요약
- `quests`: decomp 그대로 (퀘스트를 chapters 사이에 분할)
- `prerequisites`: decomp 그대로
- `status`: prerequisites 비어 있으면 `"active"`, 아니면 `"locked"`

검사:
```bash
.venv/bin/python -m agency.story.tool check-entity chapter scenarios/<name>/ scenarios/<name>/chapters/<id>.json --decomp scenarios/<name>/.decomp/
```

### 11. meta files

`profile.json`, `start.json`, `player.json`을 decompose 데이터 보고 직접 작성:

`profile.json`:
```json
{"id": "<scenario-name>", "name": "<decomp.profile_name>", "description": "<decomp.profile_description>"}
```

`start.json`:
```json
{
  "start_location": "<decomp.start_location>",
  "active_subject": "<decomp.start_subject>",
  "active_quest": "<decomp.start_quest>",
  "intro_text": "<플레이어가 처음 읽는 고정 첫 장면 나레이션>"
}
```

`intro_text`는 첫 진입 때 LLM 대신 그대로 출력된다. 시작 위치, 시작 주체, 시작 퀘스트 압력만 근거로 삼고, 아직 플레이어가 선택하지 않은 행동·단서·해결은 쓰지 않는다.

`player.json`:
```json
{
  "id": "player_01",
  "level": 1,
  "equipment": {},
  "inventory": [<decomp.items 중 for_player=true인 id 들>],
  "companions": [],
  "gold": 0,
  "xp_pool": 0
}
```

### 12. support catalog files

현재 런타임은 core entity 외에 support catalog를 읽는다. 고정 catalog는 직접 작성하지 말고 story 템플릿에서 복사한다.

```bash
.venv/bin/python -m agency.story.tool catalog-fill scenarios/<name>/
```

`catalog-fill`은 `actions.json`, `effects.json`, `mbti.json`, `slots.json`을 `agency/story/catalogs/`에서 복사한다. `actions.json`과 `effects.json`은 고정 catalog로 덮어쓰고, 나머지는 이미 있는 시나리오 전용 record를 보존하며 고정 id는 템플릿 값으로 맞춘다.

- `actions.json`: 기본 행동 id(`attack`, `defend`, `flee`, `talk`) 고정 catalog.
- `effects.json`: 기본 효과 id(`heal`, `mp_restore`, `dc_down`, `dc_up`) 고정 catalog.
- `mbti.json`: 16개 MBTI 전체 고정 catalog.
- `slots.json`: `weapon`, `armor`, `accessory` 고정 catalog.
- `knowledge.json`: `location.knowledge`, `item.knowledge`, `character.knowledge`가 가리키는 공개/비공개 지식 레코드다. 런타임 narration에는 `visibility="public"`만 공개 단서로 들어간다.
- `factions.json`: 시나리오 고유 세력만 직접 작성한다.

`dialogue_styles.json`와 `statuses.json`는 생성하지 않는다. character에도 `dialogue_style` 필드를 쓰지 않는다.

### 13. invariant sweep

```bash
.venv/bin/python -m agency.story.tool sweep scenarios/<name>/
```

PASS 안 되면 어디 깨졌는지 메시지 보고 위로 거슬러 올라가 고침. `sweep`는 seed 참조뿐 아니라 시작 퀘스트가 활성 챕터 안에 있는지, 퀘스트가 챕터에 누락·중복 배정되지 않았는지도 확인한다.

### 14. runtime start smoke

publish 전에 실제 서버 시작 경로를 한 번 실행한다. `sweep`는 seed 레코드 검증이고, 이 단계는 graph seed builder와 graph invariant까지 확인한다.

```bash
.venv/bin/python -m agency.story.tool runtime-smoke scenarios/<name>/
```

기본 smoke player는 `name="테스터"`, `gender="female"`이다. race는 `human`이 있으면 `human`, 없으면 첫 race를 자동 선택한다. 특정 race를 확인하려면:

```bash
.venv/bin/python -m agency.story.tool runtime-smoke scenarios/<name>/ --race <race_id>
```

이 명령이 PASS해야 publish 후보로 본다. 실패하면 서버 시작 경로에서 깨지는 것이므로 `sweep` 통과만 믿고 publish하지 않는다.

### 15. publish

브라우저 QA를 먼저 권장한다. `sweep`와 `runtime-smoke`는 seed와 graph init 검증이고, 실제 플레이 흐름·버튼·로그·엔딩 가능성은 `agency/qa/SKILL.md`로 확인한다.

release Supabase Storage에 publish. 사용자에게 한 번 확인을 받은 뒤 실행:
```bash
APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload scenarios/<name>/
```

`APP_ENV=release`는 release bucket에 직접 쓴다. 올리는 순간 release 서버에서 읽을 수 있다. 로컬에서 지운 파일은 bucket에서 안 지워지니, 시나리오 이름이나 ID를 바꿨으면 dashboard에서 직접 청소한다.

## 엔티티 카드 (작성 규칙 요약)

(각 카드는 시나리오 JSON 레코드 기준입니다. 런타임은 graph seed builder가 이 레코드를 읽어 그래프 노드와 엣지로 변환합니다.)

### race
- 필수: `id`, `name`, `description`, `is_humanoid`, `racial_skills` (≥1, 평민 종족도 `barter` 같은 일상 능력 1개 필요 — NPC 시드는 ≥1 스킬 invariant 때문)
- 톤: 한국어 두세 문장. 외래어 음역(`엘프 (Elf)`) 금지.

### location
- 필수: `id`, `name`, `description`, `connections`, `items`
- self-loop 금지 (`connections`에 자기 자신 ID).
- 권장: `mood`, `traits`. 런타임 narration이 장소 분위기와 행동 단서를 잡는 데 쓴다.
- `connections` 항목은 `{ "target": "<location_id>" }`이며, 필요한 경우 `difficulty` 같은 이동 속성을 connection 안에 둔다. location 루트에 `difficulty`를 두지 않는다.
- 캐릭터가 상호작용할 정적 환경 요소는 `traits`나 설명에 넣는다. `props`는 정적 content로 보존되지만 필수 필드는 아니다.
- 공개 단서는 `knowledge`에 `knowledge.json` id를 연결한다.

### character
- 기본: `id`, `name`, `race`, `gender`, `mbti`, `role`, `background`, `appearance`, `traits`, `level`, `location`, `alive`, `inventory`, `equipment`, `learned_skills`, `relations`, `xp_reward`, `protected`, `gold`, `active_buffs`, `memories`
- NPC와 적은 HP/MP, stats, job을 쓰지 않는다. 강함은 `level`, 말투와 태도는 `mbti`, `traits`로 표현한다.
- NPC `equipment`에는 아이템을 넣지 않는다. 서버 그래프의 `equips` edge는 player 전용이므로, NPC의 갑옷·무기성 소지품은 `inventory`에만 둔다.
- `secrets`는 비공개 seed 정보다. 플레이어에게 바로 보일 성격·단서는 `traits`, `background`, 공개 `knowledge`로 둔다.
- `knowledge`는 `knowledge.json` id 목록이다. narration에는 공개 지식만 바로 들어가며, 비공개 지식은 확정 공개용 문장처럼 쓰지 않는다.
- `faction`, `mbti`를 쓰면 각각 support catalog에 id가 있어야 한다. `dialogue_style`은 쓰지 않는다.
- `protected=true` 대상은 공격 전이가 차단된다. 보호 대상이 아니면 친근한 NPC라도 플레이어가 공격할 수 있으니, 죽으면 안 되는 인물은 명시적으로 보호한다.
- `is_enemy`는 decompose 단계의 계획 신호다. raw character에는 필요할 때만 두고, `combat_behavior` 같은 전투 AI 필드는 만들지 않는다.
- 전투 보상은 `xp_reward`로 둔다. 비전투 NPC는 보통 `0`, 전투 대상은 level과 난이도에 맞춰 양수로 둔다.
- 적이면 무기성 아이템을 `inventory`에 가져야 한다. 비전투 NPC에게 겉옷·갑옷 같은 placeholder 장비 아이템을 만들지 않는다.

### skill
- 필수: `id`, `name`, `description`, `level`, `action`
- `action`은 기본 행동 id(`attack`, `defend`, `flee`, `talk`) 또는 `actions.json`의 id를 가리킨다.
- 보정이 있으면 `bonus`, MP 비용이 있으면 `mp_cost`를 둔다.
- `effect`는 현재 전투 스킬 처리 경로에서 쓰지 않는다. 아이템 효과는 item에 둔다.
- racial 스킬은 `level=1` 강제.
- 캐릭터가 학습한 스킬은 `level ≤ owner의 character level`.

### item
- 필수: `id`, `name`, `description`, `price`, `consumable`
- 장비는 `slot`으로 장착 위치를 가리킨다.
- 사용 효과가 있으면 `effect`에 `effects.json`의 id를 넣는다.
- 판정 보정이 있으면 `bonus`를 숫자로 둔다.
- `action`이 있으면 `attack`, `defend`, `flee`, `talk` 중 하나여야 한다.
- `effect`가 `heal` 또는 `mp_restore`이면 `amount`가 필수다.
- `knowledge`는 공개 단서 연결용이다. `knowledge.json`에 없는 id를 쓰지 않는다.

### quest
- 필수: `id`, `title`, `description`, `giver`, `triggers`, `fail_triggers`, `prerequisites`, `status`, `required`, `rewards`
- `giver` 는 비-적대 character만.
- trigger.type은 현재 runtime seed가 받는 값만 쓴다: `location_enter`, `item_use`, `item_obtained`, `character_death`, `character_defeat`, `social_check`.
- `character_death`/`character_defeat`의 target은 적대 character만 (비-적대는 안 죽으므로 영원히 미완 상태).
- `rewards`는 최소 `{ "gold": 0, "exp": 0, "items": [] }` 형태로 둔다.
- prerequisites는 self-loop·cycle 금지.

### chapter
- 필수: `id`, `title`, `description`, `quests`, `prerequisites`, `status`
- quests는 chapters 사이에 정확히 1번씩 등장 (전체 quest 집합 분할).
- 시작 chapter는 `prerequisites=[]`, 시작 quest를 포함, 다른 quest는 prerequisite으로 잠긴 상태.

## 에러 행동 규칙

### 한 레코드가 잘못된 경우

검사 명령이 종료 코드 1을 반환했을 때:
1. stderr 메시지 읽고 어느 레코드·어느 필드·왜 깨졌는지 파악
2. 해당 레코드만 고침
3. 같은 검사 명령 다시 실행
4. 같은 레코드·같은 에러가 2회 연속이면 멈추고 사용자에게 보고. 자동 무한 반복 금지.

### 위쪽 단계 실수가 늦게 드러난 경우

예: quest 단계에서 "trigger의 target이 존재하지 않는 character_id" 발견. 원인은 decompose에서 character 명단을 잘못 만든 것.

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

### 게임 시작이 `Failed to fetch`로 보이는 경우

프론트 메시지만 보지 말고 먼저 runtime start smoke를 실행한다. 서버 traceback에 `equips owner must be player`가 있으면 원인은 NPC `equipment`다. NPC 장비를 새로 만들지 말고, 모든 `characters/*.json`의 `equipment`를 `{}`로 되돌린 뒤 `inventory` 소유만 유지한다. 그 다음 `equip-fill` → `sweep` → runtime start smoke 순서로 다시 검증한다.

## 참고

- 모든 한국어 텍스트는 **2인칭 존댓말 합니다체**(`당신` / `~합니다 / ~ㅂ니다 / ~입니다`).
- 사용자에게 보이는 스킬 이름은 **기술** (`스킬`은 classify 프롬프트에서만 동의어로 받음 — 시드 텍스트는 `기술`).
- 작업 디렉토리는 항상 repo root.
- 환경 변수 부팅: `agency.story.tool`과 `agency.story.tools.storage`가 자체적으로 `server/.env.shared`와 `server/.env.<APP_ENV>`를 로드한다. `APP_ENV` 미지정시 `dev`. publish 단계에서만 `APP_ENV=release` 명시.
