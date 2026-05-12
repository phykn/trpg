# 인터페이스

이 파일은 LLM, server, client가 서로 무엇을 주고받는지 설명한다.

## 제일 중요한 원칙

client와 LLM은 게임 규칙을 다시 만들지 않는다.
server가 graph를 검사하고, server가 화면에 보여줄 데이터를 만든다.

## LLM 호출

| 호출 | 쉬운 뜻 | `GraphChange` |
|---|---|---|
| `classify` | 플레이어 입력을 `Action`으로 바꿈 | 없음 |
| `graph_intro` | 새 게임 첫 장면을 씀 | 없음 |
| `graph_narrate` | 이미 처리된 행동 결과를 이야기로 씀 | 없음 |
| `combat_narrate` | 전투 한 교환을 이야기로 씀 | 없음 |
| `summon` | 휴식 중 적 후보의 표현만 만듦 | 없음 |
| `recommend` | 레벨업 기술 후보를 만듦 | 없음 |

LLM은 결과를 바꾸지 않는다. 결과는 engine이 먼저 정하고, LLM은 그 결과를 플레이어가 읽을 수 있게 말한다.

## classify

`classify`는 플레이어 입력을 engine이 읽을 수 있는 `Action`으로 바꾼다.

하면 안 되는 일:

- 확인 대기 만들기
- 주사위 대기 만들기
- 난이도 정하기
- 성공/실패 정하기
- id 지어내기
- graph 바꾸기

현재 정보 질문은 `query` 하나로만 보낸다.

## graph_intro

`graph_intro`는 새 게임을 만들고 난 뒤 첫 장면을 쓴다.

하면 안 되는 일:

- JSON 붙이기
- graph 바꾸기
- 시작 위치, NPC, 퀘스트를 바꾸기

실패하거나 늦으면 server가 짧은 fallback 문장을 넣는다.

## graph_narrate

`graph_narrate`는 engine 결과를 플레이어에게 보이는 이야기로 쓴다.

하면 안 되는 일:

- JSON 붙이기
- graph 바꾸기
- engine이 처리하지 않은 이동, 획득, 전투 결과를 말하기

상태를 바꾸는 일은 이 호출에 맡기지 않는다.

## combat_narrate

`combat_narrate`는 전투 한 교환을 이야기로 쓴다.

받는 것:

- 이미 정해진 전투 결과
- 플레이어 행동
- 공개 가능한 전투 하트 상태
- 플레이어 HP/MP 상태 말

하면 안 되는 일:

- HP 숫자 말하기
- 피해량 말하기
- 승패 바꾸기
- 없던 죽음, 항복, 도주 만들기

전투 이야기 입력에는 HP 숫자와 피해량 필드를 넣지 않는다. 전투 진행 판단에는 `player_hearts`, `enemy_hearts`, `round`, `trace`를 쓴다. NPC와 몬스터는 HP/MP 대신 하트와 패배 상태로 표현한다.

## summon

`summon`은 휴식 중 적 후보가 부족할 때 쓴다.

LLM이 만들 수 있는 것:

- 이름
- 외형
- 설명
- 말투
- 동기
- 소문 한 줄

LLM이 만들 수 없는 것:

- stat
- HP
- 피해량
- loot
- 보상
- 전투 규칙

## recommend

`recommend`는 레벨업 때 보여줄 기술 후보를 만든다.

하면 안 되는 일:

- 기술을 바로 배우게 하기
- 레벨업 가능 여부 판단하기
- 기존 기술과 중복 확정하기
- 피해량, 회복량, MP 비용 만들기

## LLM 실행 규칙

JSON처럼 정해진 모양으로 답해야 하는 호출은 검사에 실패하면 다시 고치게 할 수 있다.

자유문 이야기 호출은 정해진 JSON이 아니므로, 실패하면 짧은 fallback 문장을 쓸 수 있어야 한다.

LLM route는 호출 이름별로 고른다.

| 호출 | env |
|---|---|
| `classify` | `LLM_ROUTE_CLASSIFY` |
| `graph_intro` | `LLM_ROUTE_GRAPH_INTRO` |
| `graph_narrate` | `LLM_ROUTE_GRAPH_NARRATE` |
| `combat_narrate` | `LLM_ROUTE_COMBAT_NARRATE` |
| `summon` | `LLM_ROUTE_SUMMON` |
| `recommend` | `LLM_ROUTE_RECOMMEND` |

없으면 `LLM_ROUTE_DEFAULT`를 쓴다.

## 화면용 상태

client는 저장된 graph를 직접 해석하지 않는다. server가 화면에 보여줄 모양으로 바꿔서 보낸다.

| 칸 | 쉬운 뜻 |
|---|---|
| `hero` | 플레이어 상태 요약 |
| `quest` | 진행 중인 퀘스트 |
| `questOffers` | 시작 가능한 퀘스트 제안 |
| `place` | 현재 장소 정보 |
| `combat` | 전투 상태 |
| `log` | 최근 로그 |
| `pendingConfirmation` | 확인 대기 |
| `pendingRoll` | 주사위 판정 대기 |

client로 보내면 안 되는 것:

- 숨겨진 아이템
- 숨겨진 통로
- 아직 공개되지 않은 퀘스트 내용
- 내부 관계 수치
- 보상 예산
- raw `Action`
- raw `NarrateAction`
- 저장용 변경 목록

## hero

`hero`는 플레이어가 자주 보는 상태다.

| 필드 | 쉬운 뜻 |
|---|---|
| `stats` | `body`, `agility`, `mind`, `presence` 값과 표시 이름 |
| `resources.hp` | 현재 HP, 최대 HP, 상태 말, 표시 이름 |
| `resources.mp` | 현재 MP, 최대 MP, 상태 말, 표시 이름 |

client는 HP/MP 상태 말을 직접 계산하지 않는다. server가 준 값을 보여준다.

## place

`place.targets`의 NPC와 적은 HP/MP를 갖지 않는다. client는 `alive`와 `status`로 표시와 추천 행동을 정하고, 전투 내구도는 `combat.enemyHearts`만 사용한다.

## quest

퀘스트는 진행 중인 것과 시작 가능한 것을 나눠 보낸다.

| 필드 | 쉬운 뜻 |
|---|---|
| `quest` | 이미 수락한 퀘스트. 없으면 `null` |
| `questOffers` | 아직 시작하지 않은 퀘스트 제안 |

제안 퀘스트는 진행 중인 퀘스트처럼 보이면 안 된다. 시작하려면 확인창을 거쳐야 한다.

## pendingConfirmation

확인 대기는 raw `Action`을 client에 보내지 않는다.

| 필드 | 쉬운 뜻 |
|---|---|
| `id` | server가 저장한 확인 id |
| `kind` | 퀘스트 수락, 공격, 절도 같은 종류 |
| `title` | 확인창 제목 |
| `body` | 확인하면 바뀌는 일 |
| `confirm_label` | 확인 버튼 |
| `cancel_label` | 취소 버튼 |
| `target_label` | 대상 이름 |

확인하면 server가 저장해 둔 원래 행동을 다시 처리한다.

## pendingRoll

주사위 대기는 raw `Action`을 client에 보내지 않는다.

| 필드 | 쉬운 뜻 |
|---|---|
| `id` | server가 저장한 주사위 대기 id |
| `kind` | 판정 종류 |
| `title` | 판정 제목 |
| `body` | 왜 굴려야 하는지 |
| `stat` | 판정에 쓰는 능력 key |
| `stat_label` | 화면에 보일 능력 이름 |
| `required_roll` | 성공에 필요한 d20 눈 |

client는 이 값으로 1부터 20까지의 주사위 칸을 그린다. 저장된 원래 행동은 `GameProgress.pending_roll` 안에만 둔다.

## combat

전투 화면은 미니게임이 아니다. 전투 중에는 일반 입력창 대신 전투 패널을 보여준다.

| 필드 | 쉬운 뜻 |
|---|---|
| `round` | 몇 번째 교환인지 |
| `playerHearts` | 플레이어 전투 하트의 현재값과 최대값 |
| `enemyHearts` | 적 전투 하트의 현재값과 최대값 |
| `activeEnemyId` | 현재 상대하는 적 |
| `participants` | 전투 참여자 |
| `outcome` | 진행 중, 승리, 패배, 도주 |

전투 버튼은 `Action`을 보낼 수 있지만, 성공/실패와 상태 변경은 server가 정한다.
공격은 `{ verb: "attack", what: enemy_id }`, 방어는 `{ verb: "pass", how: "defend" }`, 도주는 `{ verb: "move", how: "flee" }`로 보낸다. 스킬이나 아이템 보조는 `with`에 해당 id를 넣는다.
`participants`의 HP/MP는 플레이어에게만 있다. 적/NPC 참가자는 하트와 `outcome`으로만 전투 상태를 드러낸다.

## Client 입력 우선순위

| 우선순위 | 상태 | 화면 동작 |
|---|---|---|
| 1 | `pendingConfirmation` | 확인/취소만 받음 |
| 2 | `pendingRoll` | 주사위 패널만 받음 |
| 3 | `combat` | 전투 패널만 받음 |
| 4 | `suggestions` | 행동 제안으로만 보여줌 |

확인이나 주사위가 필요한 행동에서는 먼저 이야기를 보내기 시작하지 않는다. 이야기가 먼저 나오면 플레이어는 행동이 이미 실행됐다고 느낀다.

## Graph REST 응답

server는 한 요청이 끝난 뒤 확정된 화면 상태를 JSON으로 보낸다.

| 필드 | 쉬운 뜻 |
|---|---|
| `game_id` | 게임 id |
| `state` | graph에서 만든 화면용 데이터 |
| `status` | 실행됨, 확인 필요, 취소됨 같은 처리 상태 |
| `message` | 질문형 요청처럼 상태 변경 없이 돌려줄 짧은 답 |

확인창이 필요한 입력은 `status="confirmation_required"`와 `state.pendingConfirmation`을 돌려준다.

주사위가 필요한 입력은 `status="roll_required"`와 `state.pendingRoll`을 돌려준다. 주사위를 굴리면 `/session/{game_id}/graph/roll`이 저장된 대기를 지우고 새 `state`를 돌려준다.

취소하면 `pendingConfirmation`이 사라진 상태를 돌려준다.

확인하면 저장된 원래 행동을 이어서 처리한 뒤 새 `state`를 돌려준다.

## 저장 방식

전용 graph DB는 쓰지 않는다. Supabase Postgres에 graph를 저장한다.

저장 원천은 node 행과 edge 행이다. node와 edge의 자세한 값은 `properties` JSON에 둔다.

| table | 역할 |
|---|---|
| `game_progress` | 현재 턴, 활성 퀘스트, 확인 대기, 주사위 대기, 전투 임시 상태 |
| `graph_nodes` | graph node 저장 |
| `graph_edges` | graph edge 저장 |
| `log_entries` | 플레이어에게 보인 로그 |
| `history_entries` | LLM context용 최근 요약 |
| `dialogue_entries` | 최근 대화 |

`graph_nodes`:

| column | 뜻 |
|---|---|
| `game_id` | 저장 파일 id |
| `node_id` | graph 안의 node id |
| `node_type` | character, item, location, quest, skill, race, chapter |
| `properties` | node 속성 JSON |

`graph_edges`:

| column | 뜻 |
|---|---|
| `game_id` | 저장 파일 id |
| `edge_id` | graph 안의 edge id |
| `edge_type` | located_at, carries, gives_quest 같은 edge 종류 |
| `from_node_id` | 시작 node |
| `to_node_id` | 도착 node |
| `properties` | edge 속성 JSON |

기본 키:

- `graph_nodes`: `(game_id, node_id)`
- `graph_edges`: `(game_id, edge_id)`
- `game_progress`: `game_id`

기본 인덱스:

- `graph_nodes(game_id, node_type)`
- `graph_edges(game_id, edge_type)`
- `graph_edges(game_id, from_node_id, edge_type)`
- `graph_edges(game_id, to_node_id, edge_type)`

저장 규칙:

- `GraphChange` 묶음은 한 transaction 안에서 적용한다. 모두 성공하거나 모두 실패해야 한다.
- edge의 `from_node_id`와 `to_node_id`는 같은 `game_id`의 node여야 한다.
- `node_type`과 `edge_type`은 계약에 있는 값만 허용한다.
- `properties` JSON은 아무 값이나 받지 않는다. server의 데이터 schema가 검사한다.
- 한 턴을 처리할 때는 처음에는 해당 게임의 graph를 통째로 읽어도 된다.
- graph가 커지면 필요한 주변 node와 edge만 읽는 방식으로 바꾼다.
- `log_entries`, `history_entries`, `dialogue_entries`는 뒤에 계속 추가되는 기록이다. 게임 사실의 원천은 아니다.

이 방식은 ontology 구조를 유지하면서도 운영을 단순하게 만든다. node와 edge는 DB에서 직접 찾을 수 있고, 세부 속성은 JSON으로 바꿔 가며 실험할 수 있다.

## HTTP API

게임 행동은 자연어 입력 하나로 들어간다.

장비 장착, 구매, 기술 사용, 퀘스트 수락을 각각 다른 API 주소로 만들지 않는다.

| method | path | 쉬운 뜻 |
|---|---|---|
| `GET` | `/health` | server 상태 확인 |
| `GET` | `/profiles` | 시작 가능한 profile 조회 |
| `POST` | `/session/graph/init` | 새 graph 게임 시작 |
| `GET` | `/session/{id}/graph/state` | 화면 데이터 복원 |
| `POST` | `/session/{id}/graph/input` | 자연어 입력 처리 |
| `POST` | `/session/{id}/graph/turn` | 이미 만든 `Action` 처리 |
| `POST` | `/session/{id}/graph/confirm` | 확인/취소 처리 |
| `POST` | `/session/{id}/graph/level_up` | 레벨업 처리 |

`/graph/confirm`에는 확인 id와 `confirm` 또는 `cancel`만 보낸다.

`/graph/level_up/options`는 레벨업 UI에 보여줄 성장 선택지를 돌려준다. 가능한 자원 성장 선택지를 포함하고, 스킬 슬롯이 남아 있으면 LLM이 만든 새 스킬 후보를 `growth.skill`에 담아 돌려준다. LLM 후보 생성이 실패하면 engine fallback 후보를 쓴다.

`/graph/level_up`에는 아래처럼 성장 선택지를 하나 보낸다.

```json
{"growth":{"kind":"max_hp"},"think":false}
```

가능한 `growth.kind`는 `max_hp`, `max_mp`, `learn_skill`, `upgrade_skill`이다. 기술 관련 선택지는 `skill_id`를 함께 보낸다.

## 에러

요청 모양이 틀리면 HTTP 에러를 낸다. 게임 안에서 불가능한 행동은 가능하면 게임 로그로 알려준다.

| 상황 | 처리 |
|---|---|
| 시작 요청이 잘못됨 | HTTP 422 |
| 게임 id가 없음 | HTTP 404 |
| 확인 대기와 다른 요청 | HTTP 409 또는 422 |
| LLM JSON이 계속 틀림 | HTTP 422 |
| engine 검사 실패 | `GraphChange` 없이 로그 |
| 저장 실패 | HTTP 500 계열 |

client는 에러 규칙을 다시 만들지 않는다. server가 준 문장과 상태를 보여준다.

## 코드 책임

파일명은 바뀔 수 있지만 책임은 이렇게 나눈다.

| 영역 | 책임 |
|---|---|
| domain / rules | 데이터 모양과 순수 규칙 |
| engine | 검사와 `GraphChange` 적용 |
| llm agents | LLM 호출 |
| context | LLM에게 보여줄 정보 만들기 |
| graph | 온톨로지 graph 관리 |
| flow | 한 요청의 처리 순서 |
| persistence | 저장소 |
| wire / mapping | 화면용 상태 만들기 |
| api | HTTP |
| client | 받은 데이터 보여주고 입력 보내기 |

engine은 LLM, HTTP, client, storage를 몰라야 한다.

## 테스트

테스트는 LLM이 글을 잘 쓰는지보다 계약이 깨지지 않는지를 본다.

| 영역 | 막는 것 |
|---|---|
| Action 모양 | 잘못된 행동 모양 |
| classify 후처리 | 없는 id, 잘못된 `how`, 섞인 `query` |
| engine 검사 | 불가능한 `GraphChange` |
| draft 검사 | 깨진 퀘스트 묶음 |
| seed 검사 | 시작 전에 깨진 profile |
| graph | graph를 거치지 않는 데이터 접근 |
| 화면 데이터 | 숨겨진 정보 노출 |
| graph REST 응답 | 확정 상태 누락 |
| 저장 복원 | reload 뒤 상태 복원 실패 |
| 확인창 | 확인 전 `GraphChange` 적용 |
| 전투 | 하트 감소, 방어 회복, 도주, 패배 시 실제 HP 손실 |

live LLM 테스트는 “진짜 LLM이 호출되는지만 보는 짧은 확인”으로만 둔다. 기준은 데이터 모양 검사와 engine 규칙이다.
