# 런타임 결과 구조 정리 설계

## 목적

이번 작업은 새 기능을 추가하지 않는다. 이미 있는 런타임 흐름을 더 읽기 쉬운 결과 구조로 정리한다.

목표는 다음 단계인 나레이션 분리, roll 정리, confirmation 정리를 쉽게 만드는 것이다.

## 현재 문제

지금은 `GraphActionRequestResult`와 `GraphActionDispatchResult`가 이미 있지만, 역할이 조금 섞여 보인다.

- request 결과는 client/API가 보는 상태다.
- dispatch 결과는 engine이 실제 행동을 처리한 결과다.
- 실패, query, roll, confirmation, executed가 여러 함수 안에서 흩어져 만들어진다.

동작은 돌아가지만, 다음 작업을 붙일 때 어느 단계가 무엇을 결정하는지 읽기 어렵다.

## 정리 방향

큰 동작은 바꾸지 않는다.

대신 결과를 아래처럼 이름으로 구분한다.

| 결과 | 뜻 |
|---|---|
| `executed` | 행동이 실행되고 상태가 바뀜 |
| `rejected` | 행동이 불가능해서 실패 문장을 남김 |
| `answered` | query처럼 정보만 답하고 상태를 바꾸지 않음 |
| `roll_required` | 주사위 대기를 저장하고 멈춤 |
| `confirmation_required` | 확인 대기를 저장하고 멈춤 |
| `cancelled` | 확인 취소로 대기만 제거됨 |

이 값은 API로 나가는 status와 맞아야 한다.

## 코드 경계

`dispatch.py`는 engine 처리 결과만 맡는다.

- 어떤 행동 종류인지
- graph 변경이 몇 개 적용됐는지
- 어떤 node/edge가 바뀌었는지
- 전투 결과가 있는지

`confirmation.py`는 request 전체 결과를 맡는다.

- pending이 있으면 새 입력을 막기
- query를 바로 답하기
- roll 필요 시 pending roll 저장하기
- confirmation 필요 시 pending confirmation 저장하기
- 실행 결과를 API 응답 모양으로 감싸기

`turn.py`는 실행된 행동을 저장하고 이야기까지 붙이는 흐름을 맡는다.

## 이번 구현 범위

이번 단계에서 할 일:

1. request status 타입과 helper를 더 명확한 위치로 정리한다.
2. request 결과를 만드는 코드를 작은 helper로 빼서 중복을 줄인다.
3. 기존 API 응답 모양은 바꾸지 않는다.
4. 기존 테스트는 통과해야 한다.
5. 결과 구조를 보장하는 작은 테스트를 추가한다.

이번 단계에서 하지 않을 일:

- 나레이션 호출 분리
- roll 판정 규칙 변경
- confirmation UI 변경
- classify 구조 변경
- GraphChange 저장 구조 대개편

## 성공 기준

- 기존 client/server 테스트가 모두 통과한다.
- `GraphActionRequestResult.status`가 위 표의 값만 가진다.
- query, roll, confirmation, 실행, 취소 흐름이 기존과 같은 응답을 낸다.
- 다음 작업자가 `confirmation.py`를 읽었을 때 request 결과가 어디서 만들어지는지 바로 찾을 수 있다.
