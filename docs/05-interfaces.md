# 인터페이스

이 파일은 LLM, server, client가 서로 무엇을 주고받는지 설명한다.

## 제일 중요한 원칙

client와 LLM은 게임 규칙을 다시 만들지 않는다.
server가 graph를 검사하고, server가 화면에 보여줄 데이터를 만든다.

## LLM 호출

| 호출 | 쉬운 뜻 | `GraphChange` |
|---|---|---|
| `classify` | 플레이어 입력을 `Action`으로 바꿈 | 없음 |
| `narrate_body` | 결과 이야기를 조금씩 보내며 씀 | 없음 |
| `narrate_extract` | 이야기 뒤 요약, 기억, 제안, 작은 변경 요청을 만듦 | 직접 없음 |
| `combat_narrate` | 전투 한 교환을 이야기로 씀 | 없음 |
| `summon` | 휴식 중 적 후보의 표현만 만듦 | 없음 |
| `recommend` | 레벨업 기술 후보를 만듦 | 없음 |

`narrate_body`와 `narrate_extract`는 나눈다. 이미 화면에 보낸 글은 되돌리기 어렵기 때문이다.

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

## narrate_body

`narrate_body`는 engine 결과를 플레이어에게 보이는 이야기로 쓴다.

하면 안 되는 일:

- JSON 붙이기
- graph 바꾸기
- engine이 처리하지 않은 이동, 획득, 전투 결과를 말하기

글이 한 번 화면에 나가면 되돌리기 어렵다. 그래서 상태를 바꾸는 일은 이 호출에 맡기지 않는다.

## narrate_extract

`narrate_extract`는 이미 나온 이야기를 읽고 뒤처리를 만든다.

만들 수 있는 것:

- 이번 턴 요약
- 캐릭터 기억
- 다음 행동 제안
- 허용된 작은 `NarrateAction`

이야기에 없던 새 사건을 만들면 안 된다.

## combat_narrate

`combat_narrate`는 전투 한 교환을 이야기로 쓴다.

받는 것:

- 이미 정해진 전투 결과
- 플레이어 행동
- 적 반응
- 공개 가능한 전투 상태
- HP/MP 상태 말

하면 안 되는 일:

- HP 숫자 말하기
- 피해량 말하기
- 승패 바꾸기
- 없던 죽음, 항복, 도주 만들기

전투 이야기 입력에는 HP 숫자와 피해량 필드를 넣지 않는다.

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

이야기를 조금씩 보내는 호출은 첫 문장이 나가기 전까지만 안전하게 다시 시도할 수 있다.

LLM route는 호출 이름별로 고른다.

| 호출 | env |
|---|---|
| `classify` | `LLM_ROUTE_CLASSIFY` |
| `narrate_body` | `LLM_ROUTE_NARRATE_BODY` |
| `narrate_extract` | `LLM_ROUTE_NARRATE_EXTRACT` |
| `combat_narrate` | `LLM_ROUTE_COMBAT_NARRATE` |
| `summon` | `LLM_ROUTE_SUMMON` |
| `recommend` | `LLM_ROUTE_RECOMMEND` |

없으면 `LLM_ROUTE_DEFAULT`를 쓴다.

## 화면용 상태

client는 저장된 graph를 직접 해석하지 않는다. server가 화면에 보여줄 모양으로 바꿔서 보낸다.

| 칸 | 쉬운 뜻 |
|---|---|
| `hero` | 플레이어 상태 요약 |
| `subject` | 최근 대상 정보 |
| `quest` | 진행 중인 퀘스트와 시작 가능한 퀘스트 |
| `place` | 현재 장소 정보 |
| `combat` | 전투 상태 |
| `log` | 최근 로그 |
| `pendingCheck` | 주사위 대기 |
| `pendingConfirmation` | 확인 대기 |
| `storyGraph` | 공개 진행 지도 |

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

## quest

퀘스트는 진행 중인 것과 시작 가능한 것을 나눠 보낸다.

| 필드 | 쉬운 뜻 |
|---|---|
| `active` | 이미 수락한 퀘스트 |
| `pinned_id` | 화면에서 강조할 퀘스트 |
| `offers` | 아직 시작하지 않은 퀘스트 제안 |

offer는 active quest처럼 보이면 안 된다. 시작하려면 확인창을 거쳐야 한다.

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

## combat

전투 화면은 미니게임이 아니다. 일반 입력창을 유지하고 전투 상태만 더 잘 보여준다.

| 필드 | 쉬운 뜻 |
|---|---|
| `active` | 전투 중인지 |
| `round` | 몇 번째 교환인지 |
| `participants` | 전투 참여자 |
| `last_exchange` | 직전 교환 요약 |
| `outcome` | 진행 중, 승리, 도주, 항복, 쓰러짐, 실패 |

전투 버튼을 만들 수는 있다. 하지만 버튼은 자연어 입력 후보일 뿐이다. client가 server용 action을 직접 만들지 않는다.

## Client 입력 우선순위

| 우선순위 | 상태 | 화면 동작 |
|---|---|---|
| 1 | `pendingConfirmation` | 확인/취소만 받음 |
| 2 | `pendingCheck` | 주사위만 받음 |
| 3 | `combat` | 전투 상태를 먼저 보여줌 |
| 4 | `suggestions` | 행동 제안으로만 보여줌 |

확인창이 필요한 행동에서는 먼저 이야기를 보내기 시작하지 않는다. 이야기가 먼저 나오면 플레이어는 행동이 이미 실행됐다고 느낀다.

## SSE 이벤트

SSE는 server가 client로 이벤트를 순서대로 보내는 방식이다.

| event | 쉬운 뜻 |
|---|---|
| `narrative_delta` | 이야기 조각 |
| `log_entry` | 짧은 로그 |
| `pending_check` | 주사위 필요 |
| `confirmation_required` | 확인 필요 |
| `roll_result` | 주사위 결과 |
| `combat_start` | 전투 시작 |
| `combat_turn` | 전투 교환 |
| `combat_end` | 전투 종료 |
| `suggestions` | 행동 제안 |
| `state` | 확정된 화면 데이터. 이름은 state지만 내용은 graph에서 만든 화면용 데이터 |
| `error` | 더 진행할 수 없음 |

최종 화면의 기준은 마지막 `state` 이벤트다.

확인창이 필요한 입력은 이렇게 끝난다.

```text
confirmation_required
state(pendingConfirmation 있음)
```

취소하면:

```text
state(pendingConfirmation 없음)
```

확인하면 저장된 원래 행동을 이어서 처리한다.

## 저장 방식

전용 graph DB는 쓰지 않는다. Supabase Postgres에 graph를 저장한다.

저장 원천은 node 행과 edge 행이다. node와 edge의 자세한 값은 `properties` JSON에 둔다.

| table | 역할 |
|---|---|
| `games` | 저장 파일 하나. profile, locale, schema_version, 생성/수정 시간 |
| `graph_nodes` | graph node 저장 |
| `graph_edges` | graph edge 저장 |
| `game_progress` | 현재 턴, 확인 대기, 판정 대기, 전투 임시 상태 |
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
| `POST` | `/session/init` | 새 게임 시작 |
| `GET` | `/session/{id}/state` | 화면 데이터 복원 |
| `POST` | `/session/{id}/intro` | 시작 이야기 |
| `POST` | `/session/{id}/turn` | 자연어 입력 처리 |
| `POST` | `/session/{id}/roll` | 주사위 처리 |
| `POST` | `/session/{id}/confirm` | 확인/취소 처리 |

`/confirm`에는 확인 id와 `confirm` 또는 `cancel`만 보낸다.

## 에러

요청 모양이 틀리면 HTTP 에러를 낸다. 게임 안에서 불가능한 행동은 가능하면 게임 로그로 알려준다.

| 상황 | 처리 |
|---|---|
| 시작 요청이 잘못됨 | HTTP 422 |
| 게임 id가 없음 | HTTP 404 |
| pending 상태와 다른 요청 | SSE `error` |
| LLM JSON이 계속 틀림 | SSE `error` |
| engine 검사 실패 | `GraphChange` 없이 로그 |
| 저장 실패 | SSE `error` |

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
| api | HTTP/SSE |
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
| SSE 순서 | 이벤트 순서 꼬임 |
| 저장 복원 | reload 뒤 상태 복원 실패 |
| 확인창 | 확인 전 `GraphChange` 적용 |
| 전투 | 2-3턴 전투와 4턴 강제 종료 |

live LLM 테스트는 “진짜 LLM이 호출되는지만 보는 짧은 확인”으로만 둔다. 기준은 데이터 모양 검사와 engine 규칙이다.
