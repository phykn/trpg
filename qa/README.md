# QA

테스트 지침과 도구는 여기(git)에, 실행 기록은 `qa_test/runs/<run>/`(git이 무시)에 둡니다. 기록을 지워도 지침과 도구는 남습니다.

| 어디 | 무엇 |
|---|---|
| [findings.md](findings.md) | 아직 열린 문제. 고치면 지우고, 새로 찾으면 근거 기록(`qa_test/runs/<run>` 턴 번호)과 함께 적음 |
| [decision/](decision/) | 결정 모델 벤치. 장르 문장 216개(`data/`)와 따로 둔 120개(`heldout/`). 문항 형식은 [GUIDE.md](decision/GUIDE.md) |
| [misread/](misread/) | 선택지에 답이 없을 때의 오독 벤치, 선택지 문구 비교, 상태를 정해 문장 하나씩 보는 `probe.py` |
| [narration/](narration/) | 서술 벤치(정해진 대본을 실제 모델로), 지표 비교, 블라인드 비교 묶음 |

## 실제 UI 확인

화면을 바꾸면 [docs/ui.md](../docs/ui.md) 6.2의 흐름을 320×568, 412×915, 데스크톱 폭에서 직접 해 보고, 번호를 붙인 턴과 스크린숏을 `qa_test/runs/<run>/turns.md`에 남깁니다. 결과를 말할 때는 턴 번호를 댑니다.

## 벤치 실행

모두 저장소 루트의 `.venv`로, 두 모델이 떠 있을 때 돌립니다. 기록은 `qa_test/runs/`의 아래 이름으로 갑니다.

```bash
.venv/bin/python qa/decision/bench.py run malkuth          # → qa_test/runs/decision-1/results/malkuth/
.venv/bin/python qa/decision/bench.py score
.venv/bin/python qa/decision/analyze.py                     # 기록만 읽음
.venv/bin/python qa/misread/bench.py record                 # → qa_test/runs/misread-1/answers.jsonl
.venv/bin/python qa/misread/bench.py score
.venv/bin/python qa/narration/run.py after --runs 3         # → qa_test/runs/narr-2/after.json
.venv/bin/python qa/narration/compare.py qa_test/runs/narr-2/before.json qa_test/runs/narr-2/after.json
cd server && ../.venv/bin/python -m src.story.evals ../scenarios/skeleton --out ../qa_test/runs/<run>
```

통과한 테스트와 벤치 점수는 재미를 보여 주지 않습니다. 재미는 [docs/fun.md](../docs/fun.md)의 지표(`python -m src.fun`)로 봅니다.
