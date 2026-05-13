# 계약

이 파일은 “누가 무엇을 결정하는가”를 정한다.

## 큰 원칙

- LLM은 플레이어 말뜻을 고르고, 결과 이야기를 쓴다.
- engine은 게임 규칙을 검사하고, graph를 바꾼다.
- graph가 게임 데이터의 원천이다.
- Python은 LLM이 고른 값을 검사하고 게임 행동 JSON을 만든다.
- LLM이 쓴 문장은 graph를 바꾸지 않는다.
- 플레이어에게 보이는 문장은 locale 정책을 따른다. 한국어만 강제하지 않는다.

## 한 턴은 이렇게 돈다

```text
플레이어 입력
  -> pending_roll / pending_confirmation 확인
  -> server가 후보 목록 만들기
  -> LLM이 의도와 대상 id 고르기
  -> Python이 게임 행동 JSON 만들기
  -> engine이 가능한 행동인지 검사
  -> 바로 처리 / 행동 불가 / query / roll 필요 / 확인 필요로 나누기
  -> 결과를 저장하고 화면에 먼저 보냄
  -> LLM이 결과를 이야기로 씀
  -> 이야기 저장하고 화면에 보냄
```

## 기본 용어

| 말 | 쉬운 뜻 |
|---|---|
| `graph` | 게임의 모든 사실을 담는 관계망 |
| node | graph 안의 대상. 캐릭터, 아이템, 장소, 퀘스트, 기술 |
| edge | node와 node 사이의 관계. 위치, 소유, 장착, 목표, 보상 |
| property | node나 edge에 붙는 값. 이름, HP, 퀘스트 상태, 관계 수치 |
| `GraphChange` | engine이 graph에 적용하는 변경 |
| `state` | graph와 현재 턴, 확인 대기, 판정 대기 같은 진행 상태를 담는 저장 봉투 |
| 게임 행동 JSON | Python이 만든, engine이 읽을 행동 |
| 후보 목록 | LLM에게 보여주는 현재 가능한 대상 목록 |
| `ContentDraft` | 새 아이템, NPC, 퀘스트 초안 |
| `Effect` | 어떤 일이 끝난 뒤 이어서 처리할 일 |
| `query` | graph를 바꾸지 않는 질문 |

## graph 계약

`graph`는 게임의 원본 데이터다. engine, LLM 후보 목록, 화면 데이터는 모두 graph를 기준으로 만든다.

graph는 node, edge, property로 이루어진다.

```text
Graph
  -> Node[]
  -> Edge[]
```

기본 모양:

```text
Node
  id
  type
  properties

Edge
  id
  type
  from
  to
  properties
```

`from`과 `to`에는 node id가 들어간다. node나 edge의 자세한 값은 `properties`에 둔다.

### node

node는 게임 안의 대상이다.

| node type | 예 |
|---|---|
| `character` | player, NPC, 몬스터, 동료 후보 |
| `item` | 장비, 소모품, 단서, 보상 |
| `location` | 마을, 숲, 던전 방, 상점 |
| `quest` | 수락 가능하거나 진행 중인 할 일 |
| `skill` | 캐릭터가 배워서 쓰는 기술 |
| `race` | 캐릭터 종족 |
| `chapter` | 퀘스트 묶음 |

node의 `id`는 graph 안에서 안정적이어야 한다. 같은 게임 안에서 같은 `id`가 다른 node를 가리키면 안 된다.

### edge

edge는 node와 node 사이의 관계다.

| edge type | from | to | 뜻 |
|---|---|---|---|
| `located_at` | 캐릭터나 아이템 | 장소 | 대상이 장소에 있음 |
| `hidden_at` | 캐릭터, 아이템 | 장소 | 대상이 아직 공개되지 않은 채 장소에 숨겨져 있음 |
| `carries` | 캐릭터 | 아이템 | 캐릭터가 아이템을 들고 있음 |
| `equips` | 캐릭터 | 아이템 | 캐릭터가 아이템을 장착함 |
| `connects_to` | 장소 | 장소 | 한 장소에서 다른 장소로 이동 가능함 |
| `has_companion` | player | 캐릭터 | player와 동료가 함께 움직임 |
| `knows_skill` | 캐릭터 | 기술 | 캐릭터가 기술을 알고 있음 |
| `belongs_to_race` | 캐릭터 | 종족 | 캐릭터의 종족 |
| `grants_skill` | 종족 | 기술 | 종족이 기본으로 주는 기술 |
| `gives_quest` | NPC, 장소 | 퀘스트 | 대상이 퀘스트를 제공함 |
| `target_of` | 캐릭터, 아이템, 장소 | 퀘스트 | 대상이 퀘스트 목표임 |
| `required_by` | 아이템, 단서 | 퀘스트 | 대상이 퀘스트 진행에 필요함 |
| `reward_of` | 아이템 | 퀘스트 | 아이템이 퀘스트 보상임 |
| `part_of_chapter` | 퀘스트 | 챕터 | 퀘스트가 챕터에 속함 |
| `relation` | 캐릭터 | 캐릭터 | from 캐릭터가 to 캐릭터를 어떻게 보는지 |

위치, 소유, 장착, 종족, 기술 습득, 동료, 퀘스트 목표, 아이템 보상은 property가 아니라 edge가 원본이다.

### property

property는 node나 edge에 붙는 값이다.

| 붙는 곳 | 예 |
|---|---|
| character node | 이름, 설명, 4-stat, HP/MP, 전투 정보 |
| item node | 이름, 설명, 효과, 가격, 무게 |
| location node | 이름, 설명, 휴식 위험도 |
| quest node | 제목, 목표 문장, 상태 |
| skill node | 이름, 설명, 비용, 효과 템플릿 |
| relation edge | 관계 수치, 관계 단계, 은혜나 배신 같은 flag |
| connects_to edge | 이동 난이도, 열쇠 조건, 숨김 여부 |

property는 edge로 표현해야 할 관계를 대신하면 안 된다. 예를 들어 character node에 `location_id`를 두지 않고 `located_at` edge를 둔다.

## graph 변경 계약

`GraphChange`는 engine이 graph에 적용하는 변경이다. LLM은 `GraphChange`를 직접 만들지 않는다.

허용되는 변경:

| change | 뜻 |
|---|---|
| `add_node` | 새 node 추가 |
| `set_node_property` | node property 변경 |
| `add_edge` | 새 edge 추가 |
| `set_edge_property` | edge property 변경 |
| `remove_edge` | edge 제거 |

기본 모양:

```text
add_node
  node

set_node_property
  node_id
  path
  value

add_edge
  edge

set_edge_property
  edge_id
  path
  value

remove_edge
  edge_id
```

`path`는 `properties` 안에서 바꿀 값의 위치다. 한 `GraphChange`는 한 가지 일만 한다.

node는 기본적으로 삭제하지 않는다. 게임 중 사라진 대상은 node를 지우는 대신 `status` 같은 property를 바꾸거나, 보이는 edge를 제거한다. 완전 삭제가 필요하면 별도 저장소 정리 규칙에서만 다룬다.

engine은 `GraphChange`를 적용하기 전에 검사 규칙을 확인한다.

기본 검사 규칙:

- edge 양끝 node가 존재해야 한다.
- 아이템은 위치/소유/장착/보상 edge 중 하나만 가진다.
- 캐릭터는 동시에 하나의 현재 위치만 가진다.
- `connects_to`가 없으면 이동할 수 없다.
- 퀘스트는 제공자, 목표, 보상, 완료 조건을 graph에서 찾을 수 있어야 한다.
- 플레이어 선택 없이 새 퀘스트가 `active`가 되면 안 된다.
- LLM이 만든 draft는 통과 전까지 graph가 아니다.

`state`에 저장되는 확인 대기, 판정 대기, 전투 임시 상태, locale은 graph 자체가 아니다. 이것들은 graph를 해석하고 다음 요청을 이어가기 위한 진행 상태다.

## 게임 행동 JSON

게임 행동 JSON은 플레이어가 하려는 일을 정리한 값이다.

게임 행동 JSON에는 성공 여부가 들어가지 않는다. “고블린을 공격한다”는 들어가지만, “공격이 성공했다”는 들어가지 않는다.

게임 행동 JSON은 graph를 직접 바꾸지 않는다. engine이 검사한 뒤 필요한 `GraphChange`를 만든다.

LLM은 이 JSON을 만들지 않는다. LLM은 의도와 대상 id만 고르고, Python이 이 JSON을 만든다.

복합 행동은 게임 행동 JSON 하나이거나, 순서가 있는 게임 행동 JSON 목록일 수 있다.

기본 모양:

| key | 뜻 |
|---|---|
| `verb` | 어떤 행동인지 |
| `what` | 무엇을 대상으로 하는지 |
| `from` | 어디서 가져오는지 |
| `to` | 어디로 가거나 누구에게 주는지 |
| `with` | 어떤 도구나 기술을 쓰는지 |
| `how` | 어떤 방식으로 하는지 |
| `note` | 위 칸에 넣기 어려운 짧은 정보 |

허용 행동:

| `verb` | 쉬운 뜻 |
|---|---|
| `move` | 장소 이동 |
| `transfer` | 아이템, 장비, 돈 이동 |
| `use` | 아이템이나 장치 사용 |
| `attack` | 공격하거나 전투 시작 |
| `cast` | 배운 기술 사용 |
| `speak` | NPC와 말하기 |
| `perceive` | 보기, 찾기, 기억하기, 추적하기 |
| `query` | 지금 보이는 정보 묻기 |
| `rest` | 쉬기 |
| `pass` | 아무것도 하지 않거나 게임 밖 요청 거절 |

`how`는 행동 안에서만 의미가 있다. `steal`은 `transfer`에서만 훔치기라는 뜻이고, `search`는 `perceive`에서만 수색이라는 뜻이다.

## 확인창

확인창은 “정말 하시겠습니까?”를 묻는 단계다. 성공 판정이 아니다.

확인창이 필요한 일:

- 퀘스트 수락
- 퀘스트 포기
- 동료 합류
- 동료 이탈
- 새 전투를 여는 공격
- 절도
- 위험한 아이템 사용
- 위험한 곳에서 휴식

확인 전에는 graph와 진행 상태가 바뀌지 않는다. 확인하면 저장된 게임 행동 JSON을 다시 처리한다. 취소하면 확인 대기만 사라진다.

## 이야기

LLM이 쓴 이야기는 graph를 바꾸지 않는다.

이야기는 이미 확정된 결과를 플레이어가 읽는 문장으로 바꾼다. 성공, 실패, 보상, 이동, 피해, 회복은 이야기 쓰기 전에 engine이 정한다.

이야기 단계에서 저장할 수 있는 것은 요약, 기억, 다음 행동 제안 같은 보조 정보다.

## 새 내용 초안

`ContentDraft`는 LLM이 새 내용을 만들 때 쓰는 초안이다.

예를 들어 자동 퀘스트를 만들 때 LLM은 제목, 의뢰 문장, NPC 말투 같은 빈칸을 채울 수 있다. 하지만 그 퀘스트가 실제로 게임에 들어갈지는 engine이 검사한다.

약한 LLM을 기준으로 한다.

- engine이 먼저 템플릿을 고른다.
- engine이 가능한 id, 보상 한도, 목표 종류를 정한다.
- LLM은 짧은 이름과 설명을 채운다.
- 숫자, 보상, 완료 조건, 전투 수치는 engine이 정한다.

기본 모양:

```text
ContentDraft
  draft_type
  template_id
  locked
  text
```

| 칸 | 뜻 |
|---|---|
| `draft_type` | item, character, quest_bundle 같은 초안 종류 |
| `template_id` | engine이 고른 틀 |
| `locked` | engine이 미리 정한 id, 목표 종류, 보상 한도, 연결 대상 |
| `text` | LLM이 채운 이름, 설명, 대사, hook |

LLM 출력은 `locked`를 바꾸면 안 된다.

검사 중 하나라도 실패하면 초안 전체를 버린다.

검사를 통과한 `ContentDraft`만 node와 edge로 바뀐다.

## 질문

`query`는 플레이어 질문이다. 캐릭터 행동이 아니다.

예:

- “지금 보이는 출구가 뭐야?” -> `query`
- “경비병에게 길을 묻는다” -> `speak`

`query`는 아래를 바꾸면 안 된다.

- `graph`
- 시간
- 확인 대기
- 판정 대기
- 게임 결과

## 능력치와 자원

판정용 stat은 4개만 둔다.

| stat | 쉬운 뜻 |
|---|---|
| `body` | 힘, 버티기, 근접 싸움 |
| `agility` | 피하기, 숨기, 빠르게 움직이기 |
| `mind` | 살피기, 지식, 집중, 마법 제어 |
| `presence` | 설득, 위협, 의지, 분위기 장악 |

HP와 MP는 stat이 아니다. HP와 MP는 줄고 회복되는 자원이다.

engine은 HP/MP 숫자를 저장할 수 있다. 하지만 LLM에게는 보통 숫자보다 상태 말을 준다.

| resource | LLM에게 주는 상태 |
|---|---|
| HP | `healthy`, `hurt`, `critical`, `downed` |
| MP | `ready`, `strained`, `drained` |

LLM은 HP 숫자, 피해량, 회복량, MP 비용을 만들지 않는다.

## 언어와 문장

플레이어에게 보이는 문장은 현재 저장 봉투의 `locale`을 따른다.

`ko` locale 예시:

- 플레이어를 `당신`으로 부른다.
- 게임 이야기는 2인칭 존댓말 합니다체를 쓴다.
- `skill`은 `기술`로 보여준다.

다른 언어에서는 같은 뜻을 그 언어의 문체로 보여준다.

## 언어별 문장

플레이어에게 보이는 글은 언어별로 담는다.

```text
LocalizedText = { locale: text }
```

게임 시작 요청의 locale이 profile이 지원하는 언어가 아니면 시작을 거부한다. 조용히 다른 언어로 바꾸지 않는다.
