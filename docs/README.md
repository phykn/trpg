# TRPG docs

이 문서는 지금 코드 설명서가 아니다. 앞으로 만들 게임이 어떤 규칙으로 움직여야 하는지 적은 설계서다.

## 제일 중요한 원칙

이 게임은 온톨로지 기반 게임이다.
모든 게임 데이터의 원천은 `graph`다.

LLM은 이야기를 말한다.
engine은 게임에서 실제로 일어난 일을 정한다.

여기서 engine은 “게임 규칙을 검사하고 graph를 바꾸는 코드”를 뜻한다.

## 자주 나오는 말

| 말 | 쉬운 뜻 |
|---|---|
| `graph` | 게임의 모든 사실을 담는 관계망 |
| node | graph 안의 대상. 캐릭터, 아이템, 장소, 퀘스트, 기술 |
| edge | node와 node 사이의 관계. 위치, 소유, 장착, 목표, 보상 |
| `state` | graph와 현재 턴, 확인 대기, 판정 대기 같은 진행 상태를 담는 저장 봉투 |
| `Action` | 플레이어가 하려는 행동을 정리한 값 |
| `draft` | LLM이 만든 초안. 아직 게임에 들어간 사실은 아님 |
| `client` | 플레이어가 보는 앱 화면 |
| `server` | 규칙을 검사하고 저장하는 쪽 |

## 읽는 순서

| 순서 | 파일 | 내용 |
|---|---|---|
| 1 | `01-contract.md` | LLM과 engine이 각각 무엇을 해도 되는지 |
| 2 | `02-runtime.md` | 플레이어 입력 하나가 처리되는 순서 |
| 3 | `03-world-model.md` | 아이템, 캐릭터, 장소 같은 게임 물건 |
| 4 | `04-gameplay.md` | 전투, 성장, 휴식, 퀘스트 |
| 5 | `05-interfaces.md` | LLM 호출, 화면 데이터, API, 테스트 |

## 참고 문서

| 파일 | 내용 |
|---|---|
| `client-product-style.md` | TRPG client UI의 제품 스타일 기준 |
| `ui-session-notes.md` | 2026-05-10 UI 방향 결정과 구현 메모 |
| `qa-report.md` | 2026-05-11 graph/LLM context QA 결과 |

## 구현 시작 순서

처음부터 모든 게임 기능을 만들지 않는다. graph가 원천이라는 약속부터 코드로 고정한다.

1. `Graph`, `Node`, `Edge`, `GraphChange` 모양을 만든다.
2. Supabase에 `graph_nodes`, `graph_edges`, `game_progress` 저장 방식을 만든다.
3. seed 파일을 graph로 바꾸고, seed 검사를 통과하지 못하면 시작을 막는다.
4. `Action`을 검사해서 `GraphChange`를 만드는 engine 함수를 만든다.
5. graph에서 LLM context와 화면용 상태를 만든다.
6. 자동 퀘스트, 전투, 성장 같은 기능은 위 다섯 가지가 동작한 뒤 붙인다.

## 문서 쓰는 규칙

- 같은 규칙은 한 곳에만 자세히 쓴다.
- 어려운 단어는 처음 나올 때 쉬운 뜻을 붙인다.
- LLM이 해도 되는 일과 하면 안 되는 일을 나눠 쓴다.
- 한국어 문체 예시는 `ko` locale의 예시일 뿐이다. 게임은 여러 언어를 지원할 수 있어야 한다.
