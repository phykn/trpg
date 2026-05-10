# 런타임

이 파일은 플레이어 입력 하나가 어떤 순서로 처리되는지 설명한다.

## 제일 중요한 원칙

flow는 순서를 맡는다.
engine은 `GraphChange` 생성과 적용을 맡는다.
LLM은 입력 정리와 이야기 쓰기를 맡는다.

## 전체 흐름

```text
저장된 graph와 진행 상태 읽기
  -> LLM에게 보여줄 context 만들기
  -> 플레이어 입력을 Action으로 바꾸기
  -> Action 모양 정리
  -> 처리 경로 고르기
  -> 필요하면 확인창 또는 주사위 대기
  -> engine이 검사하고 적용
  -> 이어질 일 처리
  -> LLM이 결과 이야기 쓰기
  -> 저장
  -> 화면용 상태 보내기
```

## Context

`context`는 LLM에게 보여주는 자료다.

들어갈 수 있는 것:

- 현재 장소
- 보이는 NPC와 아이템
- 갈 수 있는 출구
- 최근 대화와 로그
- 지금 장면에 필요한 시나리오 정보

`context`는 참고 자료일 뿐이다. engine이 믿는 사실은 저장된 `graph`와 engine 검사를 통과한 변경뿐이다.

## Classify

`classify`는 플레이어 입력을 `Action`으로 바꾸는 LLM 호출이다.

후처리가 해도 되는 일:

- 대상을 하나로 알 수 있으면 id를 채우기
- 칸이 명확히 잘못 들어갔으면 옮기기
- `query`가 다른 행동과 섞였으면 `query`만 남기거나 거절하기
- 없는 id나 잘못된 행동은 거절하기

후처리가 하면 안 되는 일:

- 성공/실패 정하기
- 난이도 정하기
- graph 바꾸기
- 없는 대상을 새로 만들기

## Dispatch

dispatch는 “이 행동을 어디로 보낼지” 고르는 단계다. 여기서 실행하지 않는다.

| 경로 | 쓰는 경우 | 결과 |
|---|---|---|
| formatter | `query` | 공개 정보만 읽어 답함 |
| confirmation | 확인이 필요한 행동 | 확인 대기 상태 저장 |
| roll | 주사위가 필요한 행동 | 판정 대기 상태 저장 |
| engine | 바로 적용 가능한 행동 | 검사 뒤 `GraphChange` 적용 |
| narrate | 단순 대화나 관찰 | 이야기로 처리하고 작은 변화만 허용 |
| dedicated flow | 전투, 휴식, 자동 퀘스트 | 전용 순서로 처리 |

`query`는 여기서 끝난다. `query`는 graph, 시간, 대기 상태, 이야기를 바꾸지 않는다.

전투 중이면 `query`를 뺀 대부분의 행동은 전투 교환으로 처리한다.

## Pending 상태

pending은 “지금 다른 입력을 받기 전에 먼저 끝내야 하는 일”이다.

한 번에 하나만 있을 수 있다.

| pending | 플레이어가 해야 할 일 |
|---|---|
| `pending_confirmation` | 확인 또는 취소 |
| `pending_roll` | 주사위 굴림 |

`pending_confirmation`이 있으면 일반 입력과 주사위 입력을 막는다.
`pending_roll`이 있으면 일반 입력과 확인 입력을 막는다.

## Confirmation

confirmation은 확인창이다.

```text
확인이 필요한 Action
  -> 원래 Action 저장
  -> 확인창을 화면에 보냄
  -> 멈춤

확인
  -> 저장했던 Action을 다시 처리

취소
  -> 확인 대기만 제거
```

확인은 성공이 아니다. 확인 뒤에도 조건이 안 맞으면 행동은 실패하거나 거절될 수 있다.

## Roll

roll은 주사위 판정 대기다.

flow는 원래 행동을 저장하고 멈춘다. 플레이어가 주사위를 굴리면 저장된 대기를 지우고 결과 로그를 만든다.

복잡한 행동에 판정이 여러 개 필요하면 한 번에 다 굴리지 않는다. 첫 판정 뒤 다음 행동은 다음 입력으로 넘긴다.

## Engine 적용

engine은 현재 graph에서 그 행동이 가능한지 검사하고 `GraphChange`를 만든다.

```text
검사
  -> 안 되면 거절
  -> 되면 GraphChange 만들기
  -> GraphChange 검사 규칙 확인
  -> graph에 적용
  -> 저장할 변경 모으기
  -> 이어질 일 모으기
```

저장할 `GraphChange`와 진행 상태 변경은 `Dirty`라고 부른다. 이어질 일은 `Effect`라고 부른다.

## Effect

`Effect`는 어떤 일이 끝난 뒤 자연스럽게 이어지는 일이다.

| 순서 | Effect | 쉬운 뜻 |
|---|---|---|
| 1 | character defeat / flee | 전투 결과, 처치 상태, loot 정리 |
| 2 | quest completed / failed | 퀘스트 완료/실패와 보상 처리 |
| 3 | level ready | 성장 선택지 열기 |
| 4 | sleep encounter needed | 휴식 중 조우 처리 |
| 5 | quest needed | 할 일이 부족하면 퀘스트 초안 만들기 |

전투 결과가 있으면 일반 이야기 호출 대신 `combat_narrate`를 쓴다.

## 새 콘텐츠 넣기

새 아이템, 캐릭터, 퀘스트는 바로 게임에 넣지 않는다.

```text
새 내용이 필요함
  -> engine이 템플릿과 선택지를 정함
  -> LLM이 짧은 초안을 씀
  -> engine이 전체를 검사함
  -> 통과하면 GraphChange로 graph에 넣음
  -> 실패하면 버림
```

퀘스트 초안은 특히 한 묶음으로 검사한다. 퀘스트, NPC, 몬스터, 아이템, edge, trigger 중 하나라도 이상하면 전체를 버린다.

## 이야기 쓰기

`narrate_body`는 플레이어에게 보이는 이야기를 쓴다. 이 글은 graph를 직접 바꾸지 않는다.

그 뒤 `narrate_extract`가 아래를 만들 수 있다.

| 출력 | 쉬운 뜻 |
|---|---|
| `turn_summary` | 이번 턴 요약 |
| `memory` | 캐릭터가 기억할 내용 |
| `suggestions` | 화면에 보여줄 행동 제안 |
| `NarrateAction` | 허용된 작은 변경 요청 |

`NarrateAction`도 engine 검사를 통과해야 적용된다.

## 저장과 화면 출력

flow는 변경된 graph와 진행 상태를 저장한다.

화면에 보낼 문장과 label은 server가 만든다. client는 받은 내용을 그대로 보여준다. client가 날짜, 상태 이름, 버튼 문구를 새로 조립하지 않는다.
