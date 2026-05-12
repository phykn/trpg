# dev_test QA Report

## 실행 개요

- 실행 일시: 2026-05-12 21:31-21:34 KST
- 실행 명령: `.\agency\qa\run_dev_test.ps1`
- 실행 방식: `tester.md` 지침에 따라 백그라운드 서버/클라이언트와 headless Playwright 자동화로 실행
- 로그 경로:
  - `output/tester/server.stdout.log`
  - `output/tester/server.stderr.log`
  - `output/tester/client.stdout.log`
  - `output/tester/client.stderr.log`
  - `output/tester/fun_playtest_transcript.json`

## 시드 검증

통과했습니다.

```text
OK: scenarios\dev_test (0 violations)
```

## Playwright 요약

- 총 4개 테스트 실행
- 통과: 4
- 실패: 0

통과한 테스트:

- `시작, 스트리밍 인트로, 이동, 획득, 장비, 퀘스트`
- `전투, 보조 아이템, 도주, 휴식, 거래`
- `아이템 사용 가드, 판정, 레벨업`
- `재미 플레이테스트 10-15개 플레이어 행동 transcript`

실패한 항목: 없음

## 생성된 게임

확인된 주요 game_id:

- 기능 QA 저장 그래프: `qa_test/dev_graph_saves/games/`
- 재미 플레이테스트: `game_260512_123254_2c1036`
- 재미 플레이테스트 저장 그래프:
  - `qa_test/dev_graph_saves/games/game_260512_123254_2c1036/progress.json`
  - `qa_test/dev_graph_saves/games/game_260512_123254_2c1036/graph/nodes.json`
  - `qa_test/dev_graph_saves/games/game_260512_123254_2c1036/graph/edges.json`

## 재미 플레이테스트

실행 방식: Playwright spec에서 API와 stream endpoint를 사용해 한 캐릭터로 자동 진행했습니다. UI 수동 클릭이나 브라우저 수동 조작은 사용하지 않았습니다.

game_id: `game_260512_123254_2c1036`

Transcript 요약:

| 턴 | 입력 또는 payload | 핵심 GM 반응 | 상태 변화 |
| --- | --- | --- | --- |
| 0 | intro | 테스트 허브와 주요 대상 소개 | HP 5/5, MP 5/5, gold 10 |
| 1 | 테스트 가이드에게 오늘 뭘 하면 좋을지 묻는다 | 허수아비 전투, 레벨업, 보급품 누락 퀘스트 안내 | 변화 없음 |
| 2 | 마을 주민에게 잃어버린 보급품을 묻는다 | 사라진 보급품에 대한 불안한 응답 | 변화 없음 |
| 3 | 보급 표식을 챙긴다 | 보급 표식 획득 처리 | 인벤토리 변화 |
| 4 | 보급 구역으로 이동한다 | 보급 구역 이동 | place: 보급 구역 |
| 5 | 보급 담당자에게 회복 약초 가격을 묻는다 | 상점 회복 약초 가격 안내 | 변화 없음 |
| 6 | 상점 회복 약초를 산다 | 구매 처리 | gold 10 -> 7 |
| 7 | 테스트 허브로 돌아간다 | 테스트 허브 이동 | place: 테스트 허브 |
| 8 | 훈련 일격으로 허수아비를 공격한다 | 공격 확인 필요 | pending confirmation |
| 8-confirm | 공격 시작 확인 | 허수아비 교전 시작 | MP 5/5 -> 3/5, combat ongoing |
| 9 | 마나 시약을 사용한다 | 전투 중 사용 거부 내러티브 | status rejected |
| 10 | 전투에서 빠져나온다 1 | 도주 실패 중 균형을 잃는 묘사 | combat ongoing |
| 11 | 전투에서 빠져나온다 2 | 전투에서 물러남 | combat 해제 |
| 12 | 위험 훈련장으로 이동한다 | 새 의뢰 도착 | place: 위험 훈련장 |
| 13 | 여기서 그냥 잠을 자 본다 | 중장 훈련 골렘 등장 | combat ongoing |
| 14 | 지금 상황을 살피고 다음 행동을 고른다 | 골렘의 자세와 주변 환경 묘사 | combat ongoing |

점수표:

| 항목 | 점수 | 메모 |
| --- | --- | --- |
| 다음 행동 욕구 | 4 | 가이드, 주민, 보급, 위험 훈련장으로 이어지는 다음 행동 후보가 분명했습니다. |
| 세계 반응성 | 4 | 구매, 이동, 위험 지역 휴식, 전투 시작이 상태와 장면에 반영됐습니다. |
| 실패의 맛 | 3 | 마나 시약 거부와 도주 실패는 반응이 있었지만, 거부 이유가 시스템 규칙보다 임의 장면처럼 읽히는 부분이 있습니다. |
| 나레이션 다양성 | 3 | 핵심 장면은 구분되지만 도주 반복 구간은 비슷한 문장이 이어졌습니다. |
| 상태 변화 체감 | 4 | gold, MP, combat 상태 변화가 명확했습니다. |
| 다시 하고 싶은 정도 | 4 | 골렘 전투가 열린 상태로 끝나 다음 행동은 남았습니다. |

## 원인 메모

기능/자동화 메모:

- 기능 QA와 재미 플레이테스트가 모두 통과했습니다.
- `tester.md`와 `agency/qa/dev_test.spec.ts`는 재미 플레이테스트 완료 기준을 전체 transcript row 수가 아니라 10-15개 플레이어 행동으로 맞췄습니다. 인트로와 공격 확인 같은 보조 행은 transcript에 남기되 상한 판정에는 넣지 않습니다.

재미/몰입 개선 메모:

- 전투 중 `마나 시약을 사용한다`의 병뚜껑 연출은 유지합니다. 거부 사유를 시스템 문장으로 노출하는 것보다 장면 안에서 막히는 편이 더 재미있습니다.
- 보급 담당자의 회복 약초 가격 대화는 상점 보유 아이템과 맞게 나왔습니다.
- 이번 재미 플레이테스트는 downed 상태가 나오기 전에 도주가 성공했습니다. downed 뒤 이동 차단과 회복 약초 사용 시 downed 해제는 서버 단위 테스트로 확인했습니다.
