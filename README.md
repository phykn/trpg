# 말과 주사위

플레이어가 한국어 문장으로 무엇이든 시도하면, 규칙이 결과를 정하고 로컬 모델이 장면을 쓰는 웹 TRPG 엔진입니다. 이야기는 `scenarios/`의 원고 데이터이고, 코드는 어떤 원고든 돌립니다.

- **결정 모델**(`:8081`, `malkuth` 또는 `kev`)이 문장을 닫힌 선택지(지금 할 수 있는 행동, 또는 즉흥)로 해석합니다. 아무것도 지어내지 않습니다.
- **규칙**이 2d6과 보정의 합이 목표 수(위험에 따라 7·8·9)에 닿는지, 진행 칸, 위험 시계, 태그, 대가를 계산하고 저장합니다.
- **서술 모델**(`:8082`, `gemma4`, `qwen` 또는 `minicpm`, 늘 non-thinking)이 바뀐 것만 장면으로 쓰고, 결정 모델이 사실과 어긋나지 않는지 검사합니다(다시 쓰기 2번까지).

설계는 [docs/](docs/)에 있습니다: 세계([ontology.md](docs/ontology.md)), 원고 형식([story.md](docs/story.md)), 규칙([rule.md](docs/rule.md)), 엔진([engine.md](docs/engine.md)), [api.md](docs/api.md), 화면([ui.md](docs/ui.md)), 재미([fun.md](docs/fun.md)).

## 준비

두 모델은 필수이고 이 저장소 밖에서 돌아갑니다([local-models](https://github.com/phykn/local-models)). 엔진은 모델을 띄우거나 바꾸지 않습니다. 서버는 시작할 때 두 서버가 설정한 모델을 돌리는지 확인하고, 아니면 시작하지 않습니다.

저장소 루트에서 한 번 설치합니다(Python 3.13과 Node로 개발하고 검증합니다).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
(cd client && npm i)
```

## 로컬 실행

```bash
.venv/bin/python server/run_api.py --local
```

```bash
cd client && npm run web
```

두 명령은 각각 다른 터미널의 저장소 루트에서 실행하고, 브라우저에서 **http://localhost:8090**을 엽니다. `--local`은 개인 환경 파일 없이 `127.0.0.1:8000`, 인증 `local/local`, 결정 모델 `malkuth`(`:8081`), 서술 모델 `gemma4`(`:8082`)를 씁니다. 다른 모델은 `DECISION_MODEL`, `LLM_MODEL`로 고릅니다([server/README.md](server/README.md)). 서버가 돌리는 모델과 설정이 다르면 시작 오류가 지금 올라 있는 모델 이름을 알려 줍니다. 웹 포트가 8090인 이유는 8081을 결정 모델이 쓰기 때문입니다.

## 플레이

1. 타이틀에서 이야기를 고르고, 이름, 능력치, 특성을 정합니다.
2. 행동은 입력줄에 문장으로 씁니다. 장면 줄의 이름을 누르면 문장이 시작됩니다: 갈 곳은 "…로 간다"가 통째로, 인물과 물건과 장애물은 앞부분이 채워지고, 막힌 갈 곳은 막고 있는 장애물로 시작합니다. 한 문장에 세 단계까지 이어 쓸 수 있습니다.
3. 굴리는 행동은 굴림 카드를 엽니다. 목표 수, 보정, 기댈 것이 보이고, 주사위를 눌렀다 놓으면 굴립니다.
4. 장애물의 칸을 채우면 길이 열리고, 위험 시계가 다 차면 상황이 나빠집니다. 결말은 원고의 조건이 정합니다.

모든 턴은 서술을 기다리지 않고 먼저 저장됩니다. 서술이 끊기면 다시 쓰기만 요청합니다.

## 새 이야기 쓰기

[docs/story.md](docs/story.md)의 형식으로 `scenarios/<폴더>/story.yaml`을 씁니다. 예는 [scenarios/skeleton/story.yaml](scenarios/skeleton/story.yaml) 하나입니다. 코드는 고치지 않습니다. 서버가 시작할 때 모든 이야기를 검증하고 하나라도 실패하면 서지 않으며, 미리 검증할 수도 있습니다.

```bash
cd server && ../.venv/bin/python -m src.story ../scenarios/<폴더>
```

## 어디를 고치나요?

| 목적 | 위치 |
|---|---|
| 이야기, 인물, 장애물, 결말 | `scenarios/<폴더>/story.yaml` ([docs/story.md](docs/story.md)) |
| 판정, 대가, 태그, 대화 규칙 | [server/src/rules/](server/src/rules/) |
| 문장 해석 | [server/src/interpret.py](server/src/interpret.py) |
| 서술과 검사 | [server/src/narrate.py](server/src/narrate.py) |
| API, 저장, 한 턴의 순서 | [docs/api.md](docs/api.md), [docs/engine.md](docs/engine.md) 7절 |
| 화면 | [client/screens/](client/screens/), [client/components/](client/components/) ([docs/ui.md](docs/ui.md)) |

## 검증

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check server/
cd client && npm test -- --runInBand && npx tsc --noEmit && npm run lint
```

자동 테스트 통과를 재미의 증거로 삼지 않습니다. 실제 화면 확인은 [docs/ui.md](docs/ui.md) 6.2절을 따릅니다.

## 저장

`saves/engine/g_<id>.json` 한 파일에 세계, 턴 기록, 서술 캐시, 난수 시드, 요청 영수증을 원자적으로 저장합니다. 브라우저에는 `trpg.game_id`와 대화 내역만 보관합니다. 파일 저장은 단일 서버 프로세스용입니다.
