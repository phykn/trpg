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

각 phase 결과를 임시 JSON으로 짜서 `scenarios/<name>/.decomp/{setup,cast,arc}.json`에 쓴다.
검사:
```bash
.venv/bin/python -m agency.story.tool decompose-setup scenarios/<name>/.decomp/setup.json
.venv/bin/python -m agency.story.tool decompose-cast  scenarios/<name>/.decomp/setup.json scenarios/<name>/.decomp/cast.json
.venv/bin/python -m agency.story.tool decompose-arc   scenarios/<name>/.decomp/setup.json scenarios/<name>/.decomp/cast.json scenarios/<name>/.decomp/arc.json
```

`.decomp/`는 빌드 중 `check-entity --decomp`가 참조하는 임시 계획 파일이다. 최종 `sweep`와 `runtime-smoke`가 통과하면 삭제한다.

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
- 이름은 임시 RPG 기능명이 아니라 세계관 안에서 배웠거나 몸에 밴 기술처럼 쓴다. 예: `임기응변`, `고른 숨`, `기본 공격`, `방어 자세` 금지. `행간 읽기`, `마음 가누기`처럼 장면과 행동 방식이 보이는 이름.
- 설명은 “판정을 보조합니다” 같은 시스템 설명보다, 어떤 상황에서 무엇을 포착하거나 버티는지 한 문장으로 쓴다.
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
- `guidance`: 해당 장 전용 운영 지침. 여러 지침이면 문자열 하나에 이어 쓰지 말고 문자열 배열로 나눈다.
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

도입부 품질 기준:
- 첫 문장은 정보 요약이 아니라 감각 hook 또는 이상한 압력으로 시작한다.
- `당신은 <장소>에 서 있습니다`, `<NPC>가 규칙을 설명합니다` 같은 상태 설명형 시작 금지.
- 시작 위치의 규칙·목표·동행자 이름을 한 번에 설명하지 않는다. 물건, 소리, 시선, 막힌 길처럼 플레이어가 “왜?”를 묻게 만드는 이미지부터 둔다.
- 그래도 정보는 누락하지 않는다. 규칙과 이유는 시작 NPC, 공개 `knowledge`, 장소 `traits`에서 곧 얻을 수 있게 배치한다.

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

성공 후 `scenarios/<name>/.decomp/`를 삭제한다. `.decomp/`는 런타임 seed가 아니며 publish 대상도 아니다.

### 15. publish

브라우저 QA를 먼저 권장한다. `sweep`와 `runtime-smoke`는 seed와 graph init 검증이고, 실제 플레이 흐름·버튼·로그·엔딩 가능성은 `agency/qa/SKILL.md`로 확인한다.

release Supabase Storage에 publish. 사용자에게 한 번 확인을 받은 뒤 실행:
```bash
APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload scenarios/<name>/
```

`APP_ENV=release`는 release bucket에 직접 쓴다. 올리는 순간 release 서버에서 읽을 수 있다. 로컬에서 지운 파일은 bucket에서 안 지워지니, 시나리오 이름이나 ID를 바꿨으면 dashboard에서 직접 청소한다.

## 엔티티 카드 (작성 규칙 요약)

(각 카드는 시나리오 JSON 레코드 기준입니다. 런타임은 graph seed builder가 이 레코드를 읽어 그래프 노드와 엣지로 변환합니다.)

## 나레이션 품질용 시드 작성 팁

시드는 나레이션 LLM의 재료다. 필드가 섞이면 나레이션도 섞인다. 작성할 때는 seed 자체는 정보 70%, 장면 재료 30%를 목표로 한다. 실제 출력 나레이션은 담백한 플레이 로그체, 장면 70%, 상태 정보 30%가 되도록, seed에는 관찰 가능한 물건·자세·반응과 분명한 상태 근거를 함께 둔다.

### 작업 기준

- `.decomp/`는 최종 시드가 아니다. 빌드 중 검사용 임시 계획으로만 쓰고, 최종 `sweep`와 `runtime-smoke` 통과 뒤 삭제한다. 최종 수정은 실제 `scenarios/<name>/*.json` 기준으로 한다.
- 플레이어에게 보이는 장소/캐릭터/퀘스트 설명은 스포일러 없이 충분해야 한다. “동행자”처럼 정보가 거의 없는 명사만 두지 말고, 역할과 현재 의미를 한 줄로 드러낸다.

### 공개 정보와 지식

- 정보형 질문에 답해야 하는 튜토리얼·초반부는 공개 `knowledge`를 먼저 준비한다. `인간`, `동행 이유`, `항구 규칙`처럼 플레이어가 실제로 물을 단어를 title에 넣고, summary는 한 문장 사실로 쓴다.
- `knowledge.summary`는 지식이다. 은유, 감상, 나레이션 문장보다 `혼자 탄 배는 내보내지 않는다`, `동행자는 노 젓기와 안개 확인을 나눈다`처럼 간단명료하게 쓴다.
- 플레이어가 특정 NPC에게 물을 법한 핵심 쟁점은 `knowledge`에 답변 재료를 쪼개 둔다. 예: `한 일`, `하지 않은 일`, `환불 이유`처럼 질문 단위로 나누면 NPC가 은유나 되묻기로 빠지지 않는다.
- 가능 여부나 조건을 묻는 질문에 필요한 seed는 조건의 존재가 아니라 조건 자체를 담아야 한다. `규칙이 있다`보다 `붉은섬행 배는 두 사람이 마주 앉아 양쪽 노를 맞춰 잡아야 한다`처럼 쓴다.
- 플레이어가 아직 모르는 단어를 질문해야만 정보가 나오는 구조를 만들지 않는다. 예: 동행자가 필요하다는 단서가 아직 없는데 `왜 동행자가 필요한지`를 물어야만 진행된다면 실패다. 먼저 출항 명부, 빈자리, 두 개의 노, 기다리는 사람처럼 질문의 전제를 화면에 놓는다.
- 현재 장소의 정체성은 `knowledge`가 아니라 `locations.name`과 `locations.description`이 먼저 맡는다. 플레이어가 "여기가 어디인지" 물을 초반 장면은 장소 이름이 정확히 답될 수 있게, 넓은 세계 지식보다 현재 장소명을 선명하게 둔다.
- 넓은 세계 지식의 title이 현재 장소 답변처럼 읽히면 LLM이 위치를 혼동한다. 예: 현재 장소가 `안개 항구`인데 공개 지식 title을 `안개 바다와 섬들`로 두면 "여긴 안개 바다"라고 답할 수 있다. 이런 경우 `바다 너머 섬들`, `항구 앞바다`처럼 현재 장소와 범위를 분리한다.
- 동행이 필요한 이유처럼 세계 규칙에 가까운 정보는 캐릭터 대사에만 기대지 말고 `knowledge`로 둔다. 캐릭터는 그 지식을 말하는 통로이고, 지식 자체는 seed에 분리한다.
- `chapter.guidance`는 장 운영 규칙이다. 해당 장에서 질문을 받았을 때 공개할 범위, 금지할 스포일러, 정보와 장면 재료의 비율을 리스트로 쓴다. 전역 `world.md`에 특정 튜토리얼 내용을 몰아넣지 않는다.

### 퀘스트와 진행 경계

- `quest.description`은 현재 목표다. 이미 일어난 행동처럼 쓰지 않는다. 예: 선착장에 막 도착하는 퀘스트라면 `노를 잡고 출항한다`보다 `선착장에서 출항을 확정한다`가 낫다.
- 튜토리얼 퀘스트 설명은 플레이어가 실제로 확인해야 할 보이는 대상을 넣는다. `두 자리 배를 보면 준비가 끝난다`보다 `엘리와 두 자리 배를 보면 준비가 끝난다`처럼 목표 대상이 빠지지 않게 쓴다.
- 튜토리얼의 필수 출구는 `social_check` 성공에 걸지 않는다. 규칙 설명, 신뢰, 추가 힌트는 대화와 판정으로 열어도 되지만, 다음 장소로 넘어가는 필수 준비는 `location_enter`나 관찰 가능한 확인처럼 실패하지 않는 trigger에 둔다.

### 이동과 장소 경계

- 되돌릴 수 없는 이동은 일반 이동과 다르게 설계한다. connection에 역방향이 없고 quest gate가 걸린 이동은 장소명과 `travel_text`가 그 결정을 분명히 보여야 한다.
- 중요한 이동의 출발지와 도착지는 모호하지 않게 쓴다. 출발 장소 이름에 목적지를 너무 앞세우면 이미 떠난 것처럼 나레이션될 수 있으니, `안개 항구 선착장`처럼 현재 위치를 이름에 두고 목적지는 description/connection/travel_text에 둔다. 실제 도착 장소는 `붉은섬 광장`처럼 명확히 이름 붙인다.
- `location.description`은 현재 장소의 보이는 상태다. 출항 전 선착장에는 `배가 밧줄에 묶여 기다린다`처럼 쓰고, 아직 타지 않은 배 위 장면을 쓰지 않는다.
- 필수 동행자나 핵심 사물이 현재 장소에 있다면 description에서 바로 보이게 쓴다. traits에만 숨기면 이동 도착 로그에서 빠질 수 있다. 예: `엘리가 밧줄 옆에 서 있는 선착장`.
- 선착장, 문 앞, 입구 같은 준비 장소는 다음 장소가 아니다. 해당 location에는 `배가 묶여 있다`, `문이 닫혀 있다`, `입구가 보인다`처럼 현재 상태를 쓰고, 출항·입장·도착 장면은 connection의 `travel_text`나 실제 도착 location에 둔다.
- 이동 후 장면에서 행동할 인물은 새 location에 실제로 있는 character여야 한다. 직전 대화 상대가 따라오지 않는다면, 그 인물의 손짓·표정·대사를 이동 후 location 설명이나 guidance에 기대지 않는다.
- 직전 NPC가 다음 장소에 없는데 LLM이 계속 데려오면, 새 location의 traits에 현재 인물 경계를 짧게 둔다. 이때 absent NPC 이름을 주어로 세우지 않는다. 예: `출항 명부는 안개 항구에 남아 있고, 이곳에는 엘리와 묶인 배만 기다린다`.
- 이동용 seed는 직전 대화 내용을 다시 설명하게 만들지 않는다. 새 location의 description/traits에는 현재 보이는 상태와 다음 선택만 두고, 이전 NPC의 답변 요약은 넣지 않는다.
- seed를 고쳐도 이동 로그가 계속 직전 대화를 잇는다면, seed 문제가 아니라 narration brief에 이전 대화 맥락이 들어가는 구조 문제일 수 있다.
- 이동 narration은 현재 location의 `description`/`traits`를 근거로 삼는다. 선착장처럼 경계가 중요한 장소는 보이는 물건, 함께 있는 인물, 아직 일어나지 않은 도착을 명확히 갈라 쓴다.
- 섬 이름과 실제 장소 이름을 구분한다. 챕터가 `붉은섬`이면 도착 장소는 `붉은섬 광장`처럼 섬+장소가 함께 보이게 하고, 출발지는 `안개 항구 선착장`처럼 현재 장소가 먼저 보이게 해 분류기와 나레이션이 출발지/도착지를 헷갈리지 않게 한다.

### 캐릭터 필드 분리

- `appearance`는 외형, `traits`는 반복 행동, `background`는 과거/상황, `knowledge`는 알고 있는 사실이다. 한 필드에 다른 필드의 역할을 섞지 않는다.
- `appearance`는 복장만 쓰지 않는다. 체형, 얼굴, 손, 눈매, 수염, 자세, 눈에 띄는 장신구처럼 나레이션에서 바로 잡을 수 있는 시각 단서를 섞는다.
- 캐릭터 생동감은 새 필드가 아니라 필드 분리에서 나온다. `desire`, `fear`, `contradiction`, `personal_boundary`, `traits`가 서로 다른 말을 해야 한다.
- 대립 장면의 두 NPC는 역할을 반대로 읽을 수 없게 쓴다. `A는 요구자`, `B는 빈손의 수행자`처럼 chapter guidance와 각 character knowledge에 같은 경계를 짧게 반복한다.

### 문체 재료

- 담백한 플레이 로그체를 유도한다. 멋있는 문장보다 짧은 동작, 거리, 자세, 반응을 seed 재료로 둔다.
- 문체 재료는 `물러남`, `비틀거림`, `붙잡음`, `놓침`, `팔을 듦`, `빈손`, `벽에 닿음`처럼 보이는 행동이어야 한다.
- `기묘한`, `알 수 없는`, `운명`, `공기가 무거움`, `기세가 번짐` 같은 추상어는 seed에 넣지 않는다. 이런 단어는 LLM을 문학 흉내 쪽으로 끌고 간다.
- 스킬은 임시 RPG 기능명이 아니라 소유자와 세계관에 붙은 기술명이어야 한다. `기본 공격`, `방어 자세`, `임기응변`처럼 아무에게나 붙는 이름을 피한다.
- 아이템 description은 나레이션 문장이 아니라 명사형 설명을 우선한다. 기능과 물성, 연결된 단서가 드러나면 충분하다.
- UI에 노출되지만 나레이션 본문이 아닌 설명은 존댓말로 늘이지 않는다. `~다`, 명사형, 짧은 문구를 우선한다.
- 초반 로그가 설명문처럼 느껴지면 start intro를 늘리기보다, 시작 NPC와 주변 장소의 공개 지식을 보강한다. 첫 장면은 hook, 질문 응답은 정보 전달을 맡긴다.
- 단, 플레이어가 알아야만 자연스럽게 질문할 수 있는 필수 전제는 start intro에 관찰 가능한 형태로 둔다. 예: 출항 명부 첫 줄, 빈자리, 두 개의 노처럼 읽거나 볼 수 있는 단서.
- QA에서 어색한 문구가 나오면 먼저 어느 필드가 그 말을 유도했는지 찾는다. 단어 하나가 소유나 완료처럼 오해될 수 있으면 `몫`, `이미`, `잡고` 같은 단어를 더 중립적인 표현으로 바꾼다.

### race
- 필수: `id`, `name`, `description`, `is_humanoid`, `racial_skills` (≥1, 평민 종족도 `barter` 같은 일상 능력 1개 필요 — NPC 시드는 ≥1 스킬 invariant 때문)
- 톤: 한국어 두세 문장. 외래어 음역(`엘프 (Elf)`) 금지.

### location
- 필수: `id`, `name`, `description`, `connections`, `items`
- self-loop 금지 (`connections`에 자기 자신 ID).
- 권장: `mood`, `traits`. 런타임 narration이 장소의 장면 재료와 행동 단서를 잡는 데 쓴다.
- `connections` 항목은 `{ "target": "<location_id>" }`이며, 필요한 경우 `difficulty` 같은 이동 속성을 connection 안에 둔다. location 루트에 `difficulty`를 두지 않는다.
- 캐릭터가 상호작용할 정적 환경 요소는 `traits`나 설명에 넣는다. `props`는 정적 content로 보존되지만 필수 필드는 아니다.
- 공개 단서는 `knowledge`에 `knowledge.json` id를 연결한다.

### character
- 기본: `id`, `name`, `race`, `gender`, `mbti`, `role`, `background`, `appearance`, `desire`, `fear`, `contradiction`, `traits`, `level`, `location`, `alive`, `inventory`, `equipment`, `learned_skills`, `relations`, `xp_reward`, `protected`, `gold`, `active_buffs`, `memories`
- NPC와 적은 HP/MP, stats, job을 쓰지 않는다. 강함은 `level`, 말투와 태도는 `mbti`, `traits`로 표현한다.
- NPC `equipment`에는 아이템을 넣지 않는다. 서버 그래프의 `equips` edge는 player 전용이므로, NPC의 갑옷·무기성 소지품은 `inventory`에만 둔다.
- `secrets`는 비공개 seed 정보다. 플레이어에게 바로 보일 성격·단서는 `traits`, `background`, 공개 `knowledge`로 둔다.
- `background`는 과거/상황, `appearance`는 외형 단서, `traits`는 반복 행동·말버릇이다.
- `desire`는 지금 원하는 것, `fear`는 피하고 싶은 것, `contradiction`은 말과 행동이 어긋나는 지점이다. 셋은 캐릭터의 내적 엔진으로 쓰고 `traits`에 섞지 않는다.
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
- 이름은 소유자와 세계관에 붙은 구체 기술명. placeholder(`임기응변`, `고른 숨`, `기본 공격`, `방어 자세`) 금지.
- 설명은 UI/메타 문구면 `~다` 또는 명사형, 실제 나레이션 문구가 아니면 존댓말로 늘이지 않는다.

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
- 선택: `guidance` 문자열 배열. 해당 장에서만 필요한 나레이션/운영 지침을 항목별로 쓴다. 전역 `world.md`에 특정 장 튜토리얼이나 사건 해결 지시를 넣지 않는다.
- `guidance`가 2개 이상의 규칙을 담으면 반드시 리스트로 나눈다. 한 항목에는 한 지침만 둔다.
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

이 규칙은 빌드 중 `.decomp/`가 남아 있을 때만 적용한다. 최종 검증 뒤 삭제한 시나리오는 실제 seed 파일을 기준으로 수정한다.

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
