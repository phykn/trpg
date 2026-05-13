# 계획 문서 읽는 순서

이 폴더는 TRPG 런타임을 어떻게 나눌지 정리한다.

`simple_plan` 병합 뒤에는 이 폴더가 최신 계획의 기준이다.

먼저 `00-llm-pipeline.md`를 읽고, 필요한 부분을 아래 문서에서 자세히 본다.

| 순서 | 파일 | 맡는 내용 |
|---|---|---|
| 1 | `00-llm-pipeline.md` | 전체 LLM 파이프라인 |
| 2 | `01-contract.md` | 누가 무엇을 결정하는지 |
| 3 | `02-runtime.md` | 입력 하나가 처리되는 순서 |
| 4 | `03-world-model.md` | graph에 들어가는 대상 |
| 5 | `04-gameplay.md` | 전투, 성장, 휴식, 퀘스트 규칙 |
| 6 | `05-interfaces.md` | LLM 호출과 client 화면 데이터 |
| 7 | `06-storage-api.md` | 저장소, HTTP API, 에러, 테스트 |

## 작성 원칙

- 쉬운 한국어로 쓴다.
- 한 문서는 한 역할만 맡는다.
- `00`은 전체 그림만 설명한다.
- 세부 규칙은 `01`부터 `06`에 둔다.
- LLM, Python, engine, client의 책임을 섞어 쓰지 않는다.

## 폴더 밖으로 뺀 문서

UI 스타일과 예전 세션 기록은 계획 계약과 성격이 달라서 `docs/ui/`로 옮겼다.

- `docs/ui/client-product-style.md`
- `docs/ui/ui-session-notes.md`
