# 월드 모델

이 파일은 게임 안에 어떤 물건들이 있는지 설명한다.

전투, 성장, 휴식, 퀘스트 진행 규칙은 `04-gameplay.md`가 맡는다.

## 제일 중요한 원칙

게임의 사실은 `graph`에 저장한다.
graph는 node와 edge로 이루어진다.

- node는 캐릭터, 아이템, 장소, 퀘스트, 기술 같은 대상이다.
- edge는 대상 사이의 관계다. 예: 위치, 소유, 장착, 동료, 퀘스트 목표, 보상.
- HP/MP, 4-stat, 퀘스트 상태 같은 값은 node나 edge의 속성이다.

`state`는 graph와 현재 턴, 확인 대기, 판정 대기, 전투 임시 상태, locale을 담는 저장 봉투다.

graph를 바꿀 때는 engine이 `GraphChange`를 만든다. LLM 초안은 검사를 통과하기 전까지 graph가 아니다.

## 아이템

아이템은 graph의 node다. 위치와 소유자는 edge로 표현한다.

LLM이 할 수 있는 일:

- 이름 만들기
- 외형 설명하기
- 짧은 단서 문장 쓰기

engine이 정하는 일:

- 누가 가지고 있는지 나타내는 edge
- 얼마인지
- 어떤 효과인지
- 장착할 수 있는지
- 퀘스트 보상인지

아이템 node의 속성:

| 필드 | 쉬운 뜻 |
|---|---|
| `id` | 아이템 node를 찾기 위한 고정 이름 |
| `kind` | 퀘스트 아이템, 소모품, 무기, 방어구 같은 종류 |
| `name`, `description` | 플레이어에게 보이는 이름과 설명 |
| `weight`, `value` | 무게와 값어치 |
| `requirements` | 쓰거나 장착하기 위한 조건 |
| `effects` | 썼을 때 생기는 규칙 효과 |
| `tags` | 분류용 꼬리표 |

설명문에 “상처를 치료한다”라고만 쓰면 안 된다. 실제 회복 효과는 `effects`에 있어야 한다.

## 아이템 초안

LLM이 새 아이템을 만들 때는 초안만 만든다.

LLM이 채울 수 있는 것:

- 이름
- 짧은 설명
- 분위기 tag
- 효과를 플레이어에게 보여줄 문장

LLM이 만들 수 없는 것:

- 가격
- 장착 슬롯
- 피해량
- 회복량
- 임의 효과

## 아이템 위치

아이템은 항상 한 곳에만 연결된다.

| edge | 뜻 |
|---|---|
| `carries` | 캐릭터가 들고 있음 |
| `equips` | 캐릭터가 장착 중 |
| `located_at` | 장소에 놓임 |
| `hidden_at` | 수색 뒤 드러나는 상태로 장소에 놓임 |
| `reward_of` | 퀘스트 완료 전까지 예약된 아이템 보상 |

아이템이나 돈이 움직이면 `transfer` 행동으로 처리한다.

| 방식 | 뜻 |
|---|---|
| `free` | 줍기, 주기, 받기, 버리기, 장착 |
| `buy` | 사기 |
| `sell` | 팔기 |
| `steal` | 훔치기 |

훔치기는 확인창 뒤에 판정으로 간다. 확인 전에는 소유자나 관계가 바뀌지 않는다.

## 아이템 사용

`use`는 아이템이나 장치를 쓰는 행동이다.

허용 효과:

| 효과 | 뜻 |
|---|---|
| `heal` | HP 회복 |
| `mp_restore` | MP 회복 |
| `damage` | 피해 |
| `buff` | 일정 시간 유지되는 효과 |
| `unlock` | 문, 상자, 통로 열기 |
| `trigger` | 퀘스트나 사건 진행 |

위험하거나 되돌릴 수 없는 사용은 먼저 확인창을 띄운다.

## 캐릭터

플레이어, NPC, 몬스터는 모두 character node다.

몬스터를 완전히 다른 종류로 만들지 않는다. `kind`와 `role_tags`로 구분한다.

| 필드 | 쉬운 뜻 |
|---|---|
| `id` | character node를 찾기 위한 고정 이름 |
| `kind` | player, npc, monster |
| `role_tags` | 의뢰자, 상인, 적, 동료 후보 같은 역할 |
| `name`, `description`, `tone` | 이름, 설명, 말투 |
| `located_at` edge | 현재 위치 |
| `stats`, `resources` | 능력치, HP, MP 같은 node 속성 |
| `carries`, `equips` edge | 들고 있는 것과 장착한 것 |
| relation edge | 다른 캐릭터와의 관계 |
| `combat_profile` | 전투에 들어갈 수 있는지와 전투 성향 |

LLM이 할 수 있는 일:

- 이름 만들기
- 외형 설명하기
- 말투 정하기
- 짧은 동기 쓰기
- 소문 한 줄 쓰기

engine이 정하는 일:

- HP, MP, 4-stat
- 위치 edge
- 소지품과 장비 edge
- 관계 edge의 수치
- 전투 결과
- 보상

## 캐릭터 초안

새 캐릭터 node를 만들 때 engine이 먼저 정하는 것:

| 값 | 왜 필요한가 |
|---|---|
| `kind` | NPC인지 몬스터인지 정해야 함 |
| `role_tags` | 의뢰자, 적, 상인 같은 쓰임을 정해야 함 |
| `located_at` | 실제 장소에 놓아야 함 |
| `level_band` | 너무 강하거나 약하지 않게 해야 함 |
| `combat_template` | 전투 수치를 engine이 만들 수 있어야 함 |
| `carried_item_template` | 들고 있을 수 있는 아이템을 제한해야 함 |
| `relation_seed` | 시작 관계 범위를 정해야 함 |

LLM은 표현만 채운다. 수치와 보상은 만들지 않는다.

## Stat과 Resource

캐릭터 stat은 4개다.

| stat | 쉬운 뜻 |
|---|---|
| `body` | 몸으로 버티고 싸우는 힘 |
| `agility` | 빠르게 움직이고 피하는 힘 |
| `mind` | 보고, 알고, 집중하는 힘 |
| `presence` | 말과 태도로 밀어붙이는 힘 |

HP/MP는 숫자로 저장하지만, LLM에게는 상태 말도 같이 준다.

| resource | 상태 |
|---|---|
| HP | `healthy`, `hurt`, `critical`, `downed` |
| MP | `ready`, `strained`, `drained` |

상태 말은 engine이 숫자에서 계산한다.

## 관계와 동료

관계는 한 캐릭터가 다른 캐릭터를 어떻게 보는지 나타내는 edge다.

| 필드 | 쉬운 뜻 |
|---|---|
| `from`, `to` | 어떤 캐릭터 node 사이의 관계인지 |
| `affinity` | engine이 쓰는 내부 관계 수치 |
| `band` | 플레이어에게 보이는 관계 단계 |
| `flags` | 은혜, 배신, 계약 같은 특수 상태 |

LLM은 관계 숫자를 직접 쓰지 않는다. “호감이 올랐다” 같은 의도만 제안하고, 실제 변화량은 engine이 정한다.

동료는 별도 종류가 아니다. player node와 `has_companion` edge로 연결된 character node다.

동료 합류:

```text
동료 제안
  -> 확인창
  -> 보이는 캐릭터인지 검사
  -> 살아 있는지 검사
  -> 동료 후보인지 검사
  -> 관계, 퀘스트, 파티 수 검사
  -> 필요하면 설득 판정
  -> `has_companion` edge 추가
```

자동 생성은 동료 후보를 만들 수 있다. 하지만 자동 합류는 하지 않는다.

## 장소

장소는 캐릭터와 아이템이 연결되는 location node다.

| 필드 | 쉬운 뜻 |
|---|---|
| `id` | location node를 찾기 위한 고정 이름 |
| `name`, `description` | 플레이어에게 보이는 이름과 설명 |
| `tags` | 숲, 마을, 던전, 상점 같은 분류 |
| `connects_to` edge | 이어진 장소와 이동 조건 |
| `located_at` edge | 바로 보이는 아이템이나 캐릭터 |
| `hidden_at` edge | 수색 뒤 드러나는 아이템이나 캐릭터 |
| `sleep_risk` | 쉬었을 때 위험한 정도 |
| `encounter_tags` | 조우나 퀘스트 후보를 고르는 꼬리표 |

런타임에는 새 장소를 자동 생성하지 않는다. 자동 퀘스트는 기존 장소 안에 NPC, 몬스터, 아이템을 놓는다.

## 이동 연결

장소 이동은 `connects_to` edge로만 가능하다.

| 필드 | 쉬운 뜻 |
|---|---|
| `to` | 도착 장소 |
| `difficulty` | 이동이 쉬운지 어려운지 |
| `key_item` | 필요한 열쇠나 통행증 |
| `condition` | 퀘스트 상태나 시간 같은 조건 |
| `hidden` | 아직 보이지 않는 통로인지 |

양방향 이동이 필요하면 양쪽 장소 사이에 edge를 각각 둔다.

## Graph

`graph`는 게임 데이터의 원천이다. engine, LLM context, 화면 데이터는 모두 graph를 기준으로 만든다.

edge의 정확한 방향은 `01-contract.md`의 Edge 계약을 따른다.

| edge | 뜻 |
|---|---|
| `located_at` | 캐릭터나 아이템이 어느 장소에 있는지 |
| `hidden_at` | 아직 보이지 않는 대상이 어디에 숨겨져 있는지 |
| `carries` | 캐릭터가 무엇을 들고 있는지 |
| `equips` | 캐릭터가 무엇을 장착했는지 |
| `has_companion` | player와 동료 연결 |
| `knows_skill` | 캐릭터가 알고 있는 기술 |
| `belongs_to_race` | 캐릭터의 종족 |
| `grants_skill` | 종족이 기본으로 주는 기술 |
| `connects_to` | 장소 사이 이동 연결 |
| `gives_quest` | 누가 퀘스트를 주는지 |
| `target_of` | 무엇이 퀘스트 목표인지 |
| `required_by` | 어떤 아이템이나 단서가 필요한지 |
| `reward_of` | 어떤 아이템이 퀘스트 보상인지 |
| `part_of_chapter` | 퀘스트가 속한 챕터 |
| `relation` | 캐릭터 사이 관계 |

LLM에게 전체 graph를 주지 않는다. 지금 장면에 필요한 부분만 잘라서 준다.

| view | 쉬운 뜻 |
|---|---|
| `surroundings` | 지금 보이는 장소, NPC, 아이템, 출구 |
| `target_view` | 한 node 주변 정보 |
| `story_graph` | 플레이어에게 보여줄 graph 일부 |

숨겨진 아이템, 숨겨진 통로, 미공개 퀘스트 정보는 공개 view에 넣지 않는다.

## Seed

seed는 새 게임을 시작할 때 graph로 바꾸는 원본 파일이다.

이미 시작된 저장 파일은 seed를 고쳐도 자동으로 바뀌지 않는다.

| 경로 | 역할 |
|---|---|
| `profile.json` | profile id, 표시 이름, 지원 언어 |
| `world.md` | 세계관, 분위기, 금지 전개 |
| `start.json` | 시작 장소와 시작 퀘스트 |
| `player_template.json` | player 기본 stat, HP/MP, 시작 아이템 규칙 |
| `races/` | 선택 가능한 종족 |
| `characters/` | NPC, 몬스터, 동료 후보 |
| `locations/` | 장소와 연결 |
| `items/` | 아이템과 효과 |
| `quests/` | 퀘스트와 보상 |
| `chapters/` | 진행 묶음 |
| `skills/` | 기술 |

## Seed에서 Graph 만들기

seed 파일을 읽을 때는 먼저 node를 만들고, 그 다음 edge를 만든다.

| seed | graph 변환 |
|---|---|
| `races/` | race node |
| `characters/` | character node |
| `locations/` | location node |
| `items/` | item node |
| `quests/` | quest node |
| `chapters/` | chapter node |
| `skills/` | skill node |
| `start.json` | 시작 위치, 시작 퀘스트, 처음 보이는 대상 edge |

파일 안의 id 참조가 두 대상의 관계를 뜻하면 property로 남기지 않고 edge로 바꾼다.

예:

```text
character.location -> located_at edge
character.race -> belongs_to_race edge
character.items -> carries edge
character.skills -> knows_skill edge
race.racial_skills -> grants_skill edge
location.connections -> connects_to edge
quest.giver -> gives_quest edge
quest.targets -> target_of edge
quest.required -> required_by edge
quest.item_rewards -> reward_of edge
chapter.quests -> part_of_chapter edge
```

`profile.json`과 `world.md`는 graph 밖의 profile 설정으로 둔다. LLM context에는 들어갈 수 있지만, 캐릭터나 아이템처럼 게임 중 움직이는 node는 아니다.

## Seed 검사

새 게임 시작 전에 검사할 것:

- id가 겹치지 않는다.
- 참조하는 대상이 실제로 있다.
- player는 시작 장소로 향하는 `located_at` edge가 있다.
- 배치된 캐릭터는 `located_at` edge 하나를 가진다.
- 배치된 아이템은 `located_at`, `hidden_at`, `carries`, `equips`, `reward_of` 중 하나의 edge만 가진다.
- 보상 전용 아이템은 장소에 보이지 않는다.
- 숨겨진 아이템과 숨겨진 `connects_to` edge는 처음부터 보이지 않는다.
- 처치 목표 캐릭터는 전투 정보가 있다.
- 퀘스트는 목표, 필요 조건, 보상 edge와 engine이 읽는 완료 조건을 가진다.
- 시작 퀘스트 상태는 `locked` 또는 `active`만 가능하다.

seed, LLM 초안, 저장 파일은 같은 기본 검사를 통과해야 한다.
