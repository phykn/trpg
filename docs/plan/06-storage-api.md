# 저장과 API

이 파일은 저장소, HTTP API, 에러, 코드 책임, 테스트 기준을 설명한다.

## 저장 방식

전용 graph DB는 쓰지 않는다. Supabase Postgres에 graph를 저장한다.

저장 원천은 node 행과 edge 행이다. node와 edge의 자세한 값은 `properties` JSON에 둔다.

| table | 역할 |
|---|---|
| `game_progress` | 현재 턴, 활성 퀘스트, 확인 대기, 주사위 대기, 전투 임시 상태 |
| `graph_nodes` | graph node 저장 |
| `graph_edges` | graph edge 저장 |
| `log_entries` | 플레이어에게 보인 로그 |
| `history_entries` | LLM 후보 목록에 넣을 수 있는 최근 요약 |
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

이 방식은 graph 구조를 유지하면서도 운영을 단순하게 만든다. node와 edge는 DB에서 직접 찾을 수 있고, 세부 속성은 JSON으로 바꿔 가며 실험할 수 있다.

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
| `POST` | `/session/{id}/graph/roll` | 주사위 결과 제출 |
| `POST` | `/session/{id}/graph/confirm` | 확인/취소 처리 |
| `GET` | `/session/{id}/graph/level_up/options` | 레벨업 선택지 조회 |
| `POST` | `/session/{id}/graph/level_up` | 레벨업 처리 |

`/session/{id}/graph/confirm`에는 확인 id와 `confirm` 또는 `cancel`만 보낸다.

`/session/{id}/graph/level_up/options`는 레벨업 UI에 보여줄 성장 선택지를 돌려준다. 가능한 자원 성장 선택지를 포함하고, 스킬 슬롯이 남아 있으면 LLM이 만든 새 기술 후보를 `growth.skill`에 담아 돌려준다. LLM 후보 생성이 실패하면 engine fallback 후보를 쓴다.

`/session/{id}/graph/level_up`에는 아래처럼 성장 선택지를 하나 보낸다.

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
| context | LLM에게 보여줄 후보 목록 만들기 |
| action builder | LLM이 고른 값을 게임 행동 JSON으로 바꾸기 |
| graph | graph 관리 |
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
| 의도 선택 | 없는 id, 후보 밖 대상, 섞인 `query` |
| 게임 행동 JSON | 잘못된 행동 모양 |
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
