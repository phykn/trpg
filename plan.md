# 구현 계획

설계([docs/](docs/))를 코드로 옮기는 차례입니다. 단계마다 앞 단계의 결과만 쓰고, 끝난 단계는 테스트로 닫습니다. 설계가 정답이고 이 계획은 차례만 정합니다.

## 0. 옛 코드

기준은 docs/의 설계뿐입니다. 경로(`GET /stories`, `POST /games/{id}/commands`)와 저장(`schema_version: 2`)도 설계대로 쓰고, 옛 저장은 409 `incompatible`로 막힙니다. 옛 서버(`server/src/`, `server/tests/`)와 화면(`client/`)은 참고만 합니다. 쓸 만한 조각(아래 단계에 적은 것)은 설계에 맞춰 옮기고, 단계가 끝날 때 그 단계가 대신하는 옛 파일과 테스트를 지웁니다. 6단계와 7단계가 끝나면 옛 코드는 남지 않습니다.

## 1. 단계

각 단계의 "닫는 검사"는 설계의 성질 표(ontology.md 7절, rule.md 10절, engine.md 9절, ui.md 6절)에서 온 것입니다.

### 1. 세계 `server/src/onto/` (ontology.md)

- `atoms.py`: `Atom`, `State`와 색인, `conforms`(C1~C3), 한도.
- `change.py`: `Delta`, `Work`, 연산 `move set_ reveal tag untag link unlink retire expire assert_ retract clear_spent`.
- `log.py`: `Event`, `matches`, 이력 요약 `h`.
- `cond.py`: 조건 AST 컴파일과 `holds(c, facts, hist)`, 유도 원자 `blocks`.
- `view.py`: `observe → Obs`(E, F, B, M, hᵥ), `fact_rule`, `Seen`과 기억 투영.
- `universe.py`: `Universe`, 엔진 id, `initial(universe, creation)`, 방아쇠 엮기(차례, 발동 플래그).
- `save.py`: 스냅숏 쓰기(원자적), 읽기, 기록에서 다시 만들기.
- `server/src/story/load.py`: YAML(차례를 지키는 로더, 앵커·태그 거부) → `Universe`. `requirements.txt`에 PyYAML을 더함.

닫는 검사: 같은 원고·`creation` → 같은 `S₀`; 연산마다 `conforms`; 예외 시 `Work`만 버려짐; 숨은 원자만 다른 두 상태 → 같은 `Obs`; 저장 → 읽기 → 같은 상태; 뼈대 이야기가 읽힘.

### 2. 규칙 `server/src/rules/` (rule.md)

차례: `acts`(parse/format 왕복) → `roll`(`roll`, `BANDS`, `risk`, `modifiers`, `outcome`, `odds`, `preview`) → `candidates`(`candidates`, `space`, `admits`, `rely` 표) → `costs`(대가 표, `pool`, `settle`) → `schemas`(Δ₀, `scene_end`) → `triggers`(`scan`, 엔진 방아쇠 다섯, `chapter_to`, `end`) → `resolve` → `recommend`.

닫는 검사:
- 뼈대 이야기의 고정 경로: `go:village`, `go:yard`, `try:door:finesse;rely=trait:tinker` (4,3,0) → 후보, 위험 보통, 칩 +2/+1/−1, 합 9 `mixed`, 박자 2→3, 문 0→2, 시계 0→1, `spent tinker`, `due [engine.snag, engine.beat]`.
- rule.md 10절의 표 전부(허용 검사, 진행성, 중립값, 이득 한정, 위험의 독립, 미리보기 = 실행, 인자의 종류, 방아쇠의 끝, 굴림의 전진, 시간의 전진).
- `odds` 경계 6·7·9·10 단위 테스트.

### 3. 검증 `server/src/story/validate.py` (story.md 4~5절)

V1~V4(원고 훑기) → V5(증인 재생, `initial`과 `resolve` 사용) → V6(퍼징: `S ⊨ C`, `K ≠ ∅`, 미리보기 = 실행). 고장 낸 원고 사본마다 오류 하나(영어, 항목 id와 필드).

닫는 검사: 뼈대 이야기 통과; 단계마다 일부러 깬 사본이 그 단계에서 실패. 뼈대 이야기에 숨은 장애물과 플래그가 있어야 V6가 막힘과 플래그 경로를 지남.

### 4. 서비스와 API, 모델 없이 (engine.md 6~7절, api.md)

- `locale/ko.py`: 틀 표 𝔗, 행동 이름 λ, 엔진 대가의 이름, 공통 문장.
- `view.py`: `GameView`, 단계 기록(`total`, `decisive`, `changes` 묶기).
- `cards.py`: 굴림·확인 카드(되묻기는 5단계), 표현층 `P`.
- `service.py`: `command` 7단계(잠금, 영수증, `revision`, 계획, 단계, 저장). 옛 `service.py`·`store.py`의 잠금, 영수증, 원자적 쓰기를 참고함.
- `api.py`: 경로, Basic Auth, 오류 표. 서술 경로는 6단계에서.

이 단계의 명령은 `action`과 `card`만 받습니다(선택자는 모두 같은 자리이므로 버튼으로 전부 시험할 수 있음).

닫는 검사: 같은 `request_id` → 같은 응답; 낡은 `revision` → 409와 `view`; 카드 밖 `pick` → `refused`; 연쇄 둘째 단계가 높음이면 확인 카드; 카드의 `preview`와 `Step`이 같음; 재시작 뒤 같은 `view`.

### 5. 해석 (engine.md 2~3절)

`lang/context.py`(ρ), `interpret.py`(0층 규칙, 1층 부분, 2층 자리, `δ_θ`, `decide`), 되묻기 카드. Kev 호출은 옛 `models/kev.py`를 옮겨 쓰고(옛 `content.schema` 의존은 끊음), 옛 `interpret.py`는 단계별 질문의 참고로만 봅니다.

닫는 검사: 가짜 선택자로 층마다의 전이(받아들임, 되묻기, 거절, `try(player)`); `evals.yaml` 정확도(engine.md "재는 것")를 실제 Kev로 한 번 재서 기록. 뼈대 이야기의 `evals.yaml`을 여기서 씀.

### 6. 서술 (engine.md 5절, api.md 4절)

`narrate.py`: `δ`, 입력 조립, Qwen 생성(`enable_thinking: false`), 규칙 검사·κ·Kev 검사, 다시 쓰기 두 번, 끝맺음, 태그 이름, 되돌아보기, 캐시와 겹친 요청. 옛 `models/qwen.py`를 옮겨 쓰고, 옛 `narrate.py`의 형식 검사와 다시 쓰기는 참고만 함. NDJSON 경로 둘과 시작 시 모델 확인.

닫는 검사: 가짜 모델로 단계 순서(`writing → checking → rewriting → text → done`), 세 번 실패 → `error`, 지운 문장 뒤 `δ` 줄; 실제 모델로 뼈대 이야기 몇 턴을 돌려 길이 한도와 숫자 금지를 확인.

이 단계가 끝나면 옛 서버 코드와 옛 테스트는 모두 지워져 있어야 합니다.

### 7. 화면 `client/` (ui.md)

차례: `services/api.ts`(타입, NDJSON) → `logic/useGame.ts`(상태 기계와 "갈 곳") → `logic/reveal.ts`(`timeline`) → `logic/fit.ts` → 배치(`Play.tsx`와 줄 컴포넌트) → `RollCard`·`Dice`·`NumberLine`·`Chips`·`OddsBar` → 대가·되묻기·확인·성장 카드 → `Ending` → `Start`. 설계에 없는 옛 파일(`paginate.ts`, 쪽 넘김 컴포넌트, `GameScreen.tsx` 등)은 지우고, `design/` 토큰과 NativeWind 설정은 설계에 맞으면 둡니다.

닫는 검사: ui.md 6.1의 자동 테스트, `tsc`, lint, `build:web`.

### 8. 실제 화면과 측정

- ui.md 6.2의 흐름을 320×568, 412×915, 데스크톱 폭에서 직접 하고 `qa_test/agency/<run>/`에 번호 붙인 턴과 스크린숏을 남김.
- fun.md 4절의 지표를 기록에서 계산하는 오프라인 스크립트(F1~F11, F13, F14).

## 2. 나누기

1~3단계는 순수 함수라 모델 없이 끝까지 시험됩니다. 4단계부터 서버가 서고, 6단계가 끝나야 CLAUDE.md의 "모델 없는 모드 없음"을 만족합니다. 7단계는 4단계의 API가 서면 가짜 `api`로 함께 시작할 수 있습니다. 단계마다 커밋 하나 이상, 4·6·7단계의 끝은 실제로 서버와 화면을 띄워 확인합니다.
