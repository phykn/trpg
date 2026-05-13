# LLM과 화면 인터페이스

이 파일은 LLM 호출, 화면 상태, graph 응답 모양을 설명한다.

## 제일 중요한 원칙

client와 LLM은 게임 규칙을 다시 만들지 않는다.
server가 graph를 검사하고, server가 화면에 보여줄 데이터를 만든다.

## LLM 호출

| 호출 | 쉬운 뜻 | `GraphChange` |
|---|---|---|
| `classify` | 플레이어 입력에서 의도와 대상 id를 고름 | 없음 |
| `graph_intro` | 새 게임 첫 장면을 씀 | 없음 |
| `graph_narrate` | 이미 처리된 행동 결과를 이야기로 씀 | 없음 |
| `combat_narrate` | 전투 한 교환을 이야기로 씀 | 없음 |
| `summon` | 휴식 중 적 후보의 표현만 만듦 | 없음 |
| `recommend` | 레벨업 기술 후보를 만듦 | 없음 |

LLM은 결과를 바꾸지 않는다. 결과는 engine이 먼저 정하고, LLM은 그 결과를 플레이어가 읽을 수 있게 말한다.

## classify 호출

`classify`는 플레이어 입력에서 intent와 대상 id를 고른다.

받는 것:

- 플레이어 입력
- server가 만든 후보 목록
- 최근 로그와 대화 중 필요한 부분

내보내는 것:

- intent
- 후보 목록 안에 있는 대상 id

최종 게임 행동 JSON은 Python이 만든다.

하면 안 되는 일:

- 후보 목록 만들기
- 최종 게임 행동 JSON 만들기
- 확인 대기 만들기
- 주사위 대기 만들기
- 난이도 정하기
- 성공/실패 정하기
- id 지어내기
- graph 바꾸기

현재 정보 질문은 `query` 하나로만 보낸다.

후보 목록에 없는 id를 쓰면 server는 그 값을 믿지 않는다.

## graph_intro 호출

`graph_intro`는 새 게임을 만들고 난 뒤 첫 장면을 쓴다.

하면 안 되는 일:

- JSON 붙이기
- graph 바꾸기
- 시작 위치, NPC, 퀘스트를 바꾸기

실패하거나 늦으면 server가 짧은 fallback 문장을 넣는다.

## graph_narrate 호출

`graph_narrate`는 engine 결과를 플레이어에게 보이는 이야기로 쓴다.

하면 안 되는 일:

- JSON 붙이기
- graph 바꾸기
- engine이 처리하지 않은 이동, 획득, 전투 결과를 말하기

상태를 바꾸는 일은 이 호출에 맡기지 않는다.

## combat_narrate 호출

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

## summon 호출

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

## recommend 호출

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
- raw 게임 행동 JSON
- 저장된 확인/roll 행동 원본
- 저장용 변경 목록

## hero 화면 상태

`hero`는 플레이어가 자주 보는 상태다.

| 필드 | 쉬운 뜻 |
|---|---|
| `stats` | `body`, `agility`, `mind`, `presence` 값과 표시 이름 |
| `resources.hp` | 현재 HP, 최대 HP, 상태 말, 표시 이름 |
| `resources.mp` | 현재 MP, 최대 MP, 상태 말, 표시 이름 |

client는 HP/MP 상태 말을 직접 계산하지 않는다. server가 준 값을 보여준다.

## place 화면 상태

`place.targets`의 NPC와 적은 HP/MP를 갖지 않는다. server는 표시 가능한 상태와 행동을 정해 보내고, client는 받은 값을 보여준다. 전투 내구도는 `combat.enemyHearts`만 사용한다.

## quest 화면 상태

퀘스트는 진행 중인 것과 시작 가능한 것을 나눠 보낸다.

| 필드 | 쉬운 뜻 |
|---|---|
| `quest` | 이미 수락한 퀘스트. 없으면 `null` |
| `questOffers` | 아직 시작하지 않은 퀘스트 제안 |

제안 퀘스트는 진행 중인 퀘스트처럼 보이면 안 된다. 시작하려면 확인창을 거쳐야 한다.

## 확인 대기

확인 대기는 raw 게임 행동 JSON을 client에 보내지 않는다.

| 필드 | 쉬운 뜻 |
|---|---|
| `id` | server가 저장한 확인 id |
| `kind` | 퀘스트 수락, 공격, 절도 같은 종류 |
| `title` | 확인창 제목 |
| `body` | 확인하면 바뀌는 일 |
| `confirm_label` | 확인 버튼 |
| `cancel_label` | 취소 버튼 |
| `target_label` | 대상 이름 |

확인하면 server가 저장해 둔 원래 게임 행동 JSON을 다시 처리한다.

## 주사위 대기

주사위 대기는 raw 게임 행동 JSON을 client에 보내지 않는다.

| 필드 | 쉬운 뜻 |
|---|---|
| `id` | server가 저장한 주사위 대기 id |
| `kind` | 판정 종류 |
| `title` | 판정 제목 |
| `body` | 왜 굴려야 하는지 |
| `stat` | 판정에 쓰는 능력 key |
| `stat_label` | 화면에 보일 능력 이름 |
| `required_roll` | 성공에 필요한 d20 눈 |

client는 이 값으로 1부터 20까지의 주사위 칸을 그린다. 저장된 원래 게임 행동 JSON은 `GameProgress.pending_roll` 안에만 둔다.

## 전투 화면 상태

전투 화면은 미니게임이 아니다. 전투 중에는 일반 입력창 대신 전투 패널을 보여준다.

| 필드 | 쉬운 뜻 |
|---|---|
| `round` | 몇 번째 교환인지 |
| `playerHearts` | 플레이어 전투 하트의 현재값과 최대값 |
| `enemyHearts` | 적 전투 하트의 현재값과 최대값 |
| `activeEnemyId` | 현재 상대하는 적 |
| `participants` | 전투 참여자 |
| `outcome` | 진행 중, 승리, 패배, 도주 |
| `lastRoll` | 직전 전투 교환의 d20 눈. 아직 교환이 없으면 `null` |
| `lastDc` | 직전 전투 교환의 성공 기준. 아직 교환이 없으면 `null` |

전투 버튼은 command/choice intent를 보낸다. 최종 게임 행동 JSON은 server의 Python action builder가 만든다.
전투 패널의 기본 버튼은 `공격 / 기술 / 방어 / 도주` 순서다. 공격은 `attack`, 기술은 `skill`, 방어는 `defend`, 도주는 `flee`를 보낸다. 대상, 기술, 아이템을 직접 고를 때는 필요한 id를 함께 보낸다.
`participants`의 HP/MP는 플레이어에게만 있다. 적/NPC 참가자는 하트와 `outcome`으로만 전투 상태를 드러낸다.

## client 입력 우선순위

| 우선순위 | 상태 | 화면 동작 |
|---|---|---|
| 1 | `pendingConfirmation` | 확인/취소만 받음 |
| 2 | `pendingRoll` | 주사위 패널만 받음 |
| 3 | `combat` | 전투 패널만 받음 |
| 4 | `suggestions` | 행동 제안으로만 보여줌 |

확인이나 주사위가 필요한 행동에서는 먼저 이야기를 보내기 시작하지 않는다. 이야기가 먼저 나오면 플레이어는 행동이 이미 실행됐다고 느낀다.

## graph 응답

server는 처리 단계마다 client가 그릴 수 있는 상태를 보낸다.

한 행동은 두 번 나갈 수 있다.

1. 결과 상태
2. 이야기 상태

| 필드 | 쉬운 뜻 |
|---|---|
| `game_id` | 게임 id |
| `state` | graph에서 만든 화면용 데이터 |
| `status` | 실행됨, 확인 필요, 취소됨 같은 처리 상태 |
| `message` | 질문형 요청처럼 상태 변경 없이 돌려줄 짧은 답 |
| `event_kind` | 결과인지 이야기인지 구분 |

확인창이 필요한 입력은 `status="confirmation_required"`와 `state.pendingConfirmation`을 돌려준다.

주사위가 필요한 입력은 `status="roll_required"`와 `state.pendingRoll`을 돌려준다. 주사위를 굴리면 `/session/{game_id}/graph/roll`이 저장된 대기를 지우고 새 `state`를 돌려준다.

취소하면 `pendingConfirmation`이 사라진 상태를 돌려준다.

확인하면 저장된 원래 게임 행동 JSON을 이어서 처리한 뒤 새 `state`를 돌려준다.

