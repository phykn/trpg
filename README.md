# LLM TRPG 엔진

플레이어가 한국어 문장으로 무엇이든 시도하면, 규칙이 결과를 정하고 로컬 모델이 장면을 쓰는 웹 TRPG 엔진입니다. 이야기는 `scenarios/`의 원고 데이터이고, 코드는 어떤 원고든 돌립니다.

- **Kev**(결정 모델, `:8081`)가 문장을 후보 행동이나 즉흥 행동으로 해석합니다.
- **규칙**이 2d6 판정, 진행도, 위험, 태그, 대가를 계산하고 저장합니다.
- **Qwen**(서술 모델, `:8082`, non-thinking)이 바뀐 것만 장면으로 쓰고, Kev가 사실과 어긋나지 않는지 검사합니다.

설계는 [docs/](docs/)에 있습니다: 세계([ontology.md](docs/ontology.md)), 원고 형식([story.md](docs/story.md)), 규칙([rule.md](docs/rule.md)), 엔진([engine.md](docs/engine.md)), [api.md](docs/api.md), 화면([ui.md](docs/ui.md)), 재미([fun.md](docs/fun.md)).

## 준비

두 모델은 필수입니다. [local-models](https://github.com/phykn/local-models)로 띄웁니다(`kevctl start kev-0.8b`, `llmctl start qwen3.6-35b-a3b`). 서버는 시작할 때 두 모델의 응답을 확인하고, 하나라도 없으면 시작하지 않습니다.

저장소 루트에서 한 번 설치합니다.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cd client && npm i
```

## 로컬 실행

```bash
.venv/bin/python server/run_api.py --local
```

```bash
cd client && npm run web
```

브라우저에서 **http://localhost:8090**을 엽니다. `--local`은 개인 환경 파일 없이 `127.0.0.1:8000`, 인증 `local/local`, Kev `:8081`, Qwen `:8082`를 씁니다. 웹 포트가 8090인 이유는 8081을 Kev가 쓰기 때문입니다.


## 플레이

1. 이야기를 고르고, 원고가 허용하면 방식과 특성을 고릅니다.
2. 문장으로 행동하거나 추천 버튼 3개 중 하나를 누릅니다. 한 문장에 3단계까지 이어서 쓸 수 있습니다.
3. 위험한 행동은 판정 전에 성공 확률과 대가를 보여 주고 확인을 받습니다.
4. 장애물의 진행도를 채우면 길이 열리고, 위험이 다 차면 상황이 나빠집니다. 결말은 원고의 조건이 정합니다.

모든 턴은 서술을 기다리지 않고 먼저 저장됩니다. 서술이 끊기면 다시 쓰기만 요청합니다.

## 새 이야기 쓰기

[docs/story.md](docs/story.md)의 형식으로 `scenarios/<폴더>/story.yaml`을 씁니다. 가장 작은 예는 [scenarios/skeleton/story.yaml](scenarios/skeleton/story.yaml)입니다. 서버가 시작할 때 모든 이야기를 검증하고 하나라도 실패하면 서지 않습니다. 코드는 고치지 않습니다.

## 어디를 고치나요?

| 목적 | 위치 |
|---|---|
| 이야기, 인물, 장애물, 결말 | `scenarios/<폴더>/story.yaml` ([docs/story.md](docs/story.md)) |
| 판정, 대가, 태그, 대화 규칙 | [server/src/rules/](server/src/rules/) |
| 문장 해석(Kev 질문) | [server/src/interpret.py](server/src/interpret.py) |
| 서술과 검사(Qwen, Kev) | [server/src/narrate.py](server/src/narrate.py) |
| API, 저장, 한 턴의 순서 | [docs/api.md](docs/api.md), [docs/engine.md](docs/engine.md) 7절 |
| 화면 | [client/screens/](client/screens/), [client/components/game/](client/components/game/) |

## 검증

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check server/
cd client && npm test -- --runInBand && npx tsc --noEmit && npm run lint
```

자동 테스트 통과를 재미의 증거로 삼지 않습니다.

## 저장

`saves/engine/g_<id>.json` 한 파일에 그래프, 턴 기록, 서술 캐시, 난수 시드, 요청 영수증을 원자적으로 저장합니다. 브라우저에는 `trpg.game_id`만 보관합니다. 파일 저장은 단일 서버 프로세스용입니다.
