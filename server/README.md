# 서버

FastAPI가 모험의 시작·조회·선택을 처리합니다. 설치와 로컬 실행은 [루트 README](../README.md)를 따릅니다.

## 요청이 처리되는 순서

`run_api.py` → `src/api.py` → `src/service.py` → `src/game/engine.py` → `src/view.py` → `src/store.py` → 응답

- `api.py`: Basic 인증, 입력 검사, HTTP 오류 매핑.
- `service.py`: 게임별 잠금, 요청 영수증과 revision 확인, 규칙 실행과 저장.
- `game/engine.py`: 현재 선택 목록, 조건, 비용, 판정, 사건과 결말. 원본 상태를 복사해 변경합니다.
- `game/graph/`: 관계 질의, `GraphChange` 적용, 그래프 불변식.
- `store.py`: 전체 상태를 임시 파일에 쓰고 원자적으로 교체합니다.
- `view.py`: 플레이어에게 공개할 장면과 선택을 만듭니다. 응답을 준비한 뒤 저장이 성공해야 반환합니다.
- `content.py`, `game/models.py`: 원고 검증과 콘텐츠·저장 형식.

## API

`GET /health`는 공개합니다. 아래 경로에는 Basic 인증이 필요합니다.

| 메서드·경로 | 입력 | 결과 |
|---|---|---|
| `GET /adventure/catalog` | 없음 | 이야기 소개와 시작 성향 |
| `POST /adventure/start` | `{name, role}` | 새 게임 화면 |
| `GET /adventure/{game_id}` | 없음 | 저장된 게임 화면 |
| `POST /adventure/{game_id}/choose` | `{option_id, revision, request_id}` | 선택 후 화면 |

`request_id`는 선택마다 만들고 재시도할 때 그대로 보냅니다. 같은 ID·입력이면 행동을 반복하지 않고 현재 저장 화면을 반환합니다. 같은 ID에 다른 입력, 오래된 revision, 지원하지 않는 저장 버전은 409입니다. 불가능한 선택은 422, 없는 게임은 404, 저장 실패는 503입니다.

## 실행 설정

`--local`은 저장소의 `saves/adventure/`, 포트 8000, 로컬 전용 인증 `local/local`을 사용합니다. 설정 실행은 `server/.env.shared` → `server/.env.<APP_ENV>` 순서로 읽습니다. 기본 `APP_ENV`는 `dev`이며 운영체제 환경변수가 우선합니다.

```dotenv
HOST=127.0.0.1
PORT=8000
BASIC_AUTH_USER=local
BASIC_AUTH_PASS=local
CORS_ORIGINS=http://localhost:8081
ADVENTURE_SAVE_DIR=../saves/adventure
```

```powershell
# 저장소 루트에서 설정 실행
.\.venv\Scripts\python.exe server/run_api.py
```

상대 저장 경로는 `server/` 기준입니다. 파일 잠금은 단일 프로세스 안에서만 유효하므로 여러 worker를 사용하지 않습니다. 공용 Basic 인증은 개별 사용자 계정 격리 기능이 아닙니다.

## 원고 수정

`scenarios/harbor/adventure.json`의 `choices`에서 선택 ID를 찾습니다. 예를 들어 경비병의 보증 대화는 `guard.promise`의 `success.text`에 있습니다. 조건은 `at / knows / carries / property / relation`, 효과는 `set / add / learn / give / move / companion / relation`입니다. 판정 선택에는 실패 결과, 실행 조건에는 잠긴 이유가 필요합니다.

원고를 고치면 서버를 재시작하고 `server/validate_adventure.py`와 `server/tests/test_game.py`를 실행합니다. 저장의 의미가 바뀌는 수정은 콘텐츠 `version`을 올립니다. 서버는 맞지 않는 저장을 덮어쓰지 않습니다. API·저장 변경은 `server/tests/test_api.py`, 그래프 변경은 `server/tests/graph/`로 검증합니다.
