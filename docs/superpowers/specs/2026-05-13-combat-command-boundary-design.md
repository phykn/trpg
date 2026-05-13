# 전투 command 경계 설계

## 목적

전투 버튼이 최종 게임 행동 JSON을 직접 만들지 않게 한다.

현재 client 전투 버튼은 `attack`, `cast`, `pass`, `move` 같은 engine용 행동 JSON을 만든다. 새 계획에서는 client가 버튼 선택만 보내고, server/Python이 그 선택을 검사한 뒤 게임 행동 JSON을 만든다.

## 범위

이번 작업은 전투 버튼만 다룬다.

포함한다:

- client 전투 버튼 타입을 `GraphAction`에서 전투 command로 바꾸기
- 전투 command를 server로 보내는 API 추가
- server가 전투 command를 기존 게임 행동 JSON으로 바꾸기
- 기존 전투 처리 흐름으로 넘기기
- client/server 테스트 수정

포함하지 않는다:

- 일반 자연어 `classify` 구조 변경
- 모든 shortcut action 구조 변경
- 복합 행동 builder 전체 구현
- roll/confirmation 저장 구조 재설계

## 새 client 입력

client는 전투 중 아래 command만 보낸다.

```ts
type CombatCommand =
  | { command: 'attack'; target_id: string }
  | { command: 'skill'; target_id: string }
  | { command: 'defend' }
  | { command: 'flee' };
```

의미:

- `attack`: 현재 적을 공격한다.
- `skill`: server가 현재 장면에서 쓸 수 있는 기술을 고른다.
- `defend`: 방어한다.
- `flee`: 도주한다.

client는 `verb`, `what`, `to`, `how`를 만들지 않는다.

## Server 처리

server는 새 command를 받은 뒤 현재 전투 상태를 확인한다.

검사:

- 게임이 존재하는가
- `pending_confirmation`이나 `pending_roll`이 없는가
- 전투가 진행 중인가
- `attack`과 `skill`이면 target id가 현재 전투 상대인가
- command가 허용된 값인가

그 다음 Python action builder가 기존 engine용 행동 JSON을 만든다.

매핑:

| command | 게임 행동 JSON |
|---|---|
| `attack` | `{ verb: "attack", what: target_id }` |
| `skill` | `{ verb: "cast", to: target_id, how: "auto" }` |
| `defend` | `{ verb: "pass", how: "defend" }` |
| `flee` | `{ verb: "move", how: "flee" }` |

이 매핑은 client가 아니라 server 코드에 둔다.

## API

새 endpoint를 추가한다.

```text
POST /session/{game_id}/graph/combat
POST /session/{game_id}/graph/combat/stream
```

요청:

```json
{
  "command": "attack",
  "target_id": "enemy_01"
}
```

`defend`와 `flee`는 `target_id`를 보내지 않는다.

응답은 기존 graph action 응답과 같다. streaming도 기존 graph action stream 처리와 같은 이벤트 모양을 쓴다.

## Client 변경

`client/logic/combat/actions.ts`:

- `graphAction` 대신 `combatCommand`를 만든다.
- `attack`과 `skill`은 현재 살아 있는 적 id를 넣는다.
- `defend`와 `flee`는 command만 넣는다.

`client/logic/info-panel/types.ts`:

- `PanelAction`에 `combat_command` 종류를 추가한다.

`client/logic/game/useGame.ts`:

- `onCombatCommand`를 추가한다.
- pending confirmation/roll 중에는 보내지 않는다.
- 요청 중단, narration stream, state 적용은 기존 graph action runner를 재사용한다.

`client/services/api.ts`:

- `sendGraphCombatCommand`를 추가한다.
- stream path와 plain path를 기존 요청 helper에 연결한다.

## Server 변경

`server/src/api/schema.py`:

- combat command 요청 모델을 추가한다.

`server/src/api/routes/session_graph.py`:

- `/graph/combat`
- `/graph/combat/stream`

`server/src/game/runtime/`:

- command를 기존 `Action`으로 바꾸는 작은 builder를 추가한다.
- builder는 전투 상태와 target을 검사한다.
- 만든 `Action`은 기존 `run_graph_action_request` 또는 stream 흐름으로 넘긴다.

## 에러 처리

HTTP 에러:

- 게임 id가 없으면 404
- 요청 모양이 틀리면 422
- pending confirmation/roll 중이면 기존 graph action과 같은 conflict 규칙
- 전투 중이 아니면 422
- target이 현재 전투 상대가 아니면 422

게임 안 실패:

- engine이 처리 중 실패한 행동은 기존 전투 실패 처리와 같은 방식으로 로그와 상태를 만든다.

## 테스트

client:

- `buildCombatActions`가 `combatCommand`를 만든다.
- `sendGraphCombatCommand`가 `/graph/combat/stream`을 먼저 시도한다.
- pending 중에는 `onCombatCommand`가 요청하지 않는다.

server:

- combat command 요청 모델 검증
- `attack`, `skill`, `defend`, `flee`가 기대한 `Action`으로 바뀐다.
- 전투 중이 아니면 거절된다.
- target이 현재 전투 상대가 아니면 거절된다.
- stream endpoint가 기존 graph action stream과 같은 응답 모양을 낸다.

## 성공 기준

- client 전투 버튼 코드에 engine용 `{ verb: ... }` 생성이 남지 않는다.
- combat command를 server가 게임 행동 JSON으로 바꾼다.
- 기존 전투 UI 동작은 유지된다.
- 관련 client/server 테스트가 통과한다.
