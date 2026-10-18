# 구현 계획 (코드)

[plan.md](plan.md)의 설계를 코드로 옮기는 계획입니다. 무엇을 왜 만드는지는 plan.md를 따르고, 이 문서는 파일, 타입, 알고리즘, 테스트, 작업 순서를 정합니다.

## 0. 출발점

- **브랜치**: `main`에서 `engine` 브랜치를 만듭니다. `main`의 서버는 2.7천 줄로 작고 원자 저장, 영수증, revision, Basic 인증, 모바일 한 화면이 이미 있습니다.
- **남기는 것** (그대로 또는 조금 고쳐서): `server/src/store.py`, `env.py`(새 `config.py`에 합침), `api.py`의 인증 부분, `client/`의 디자인 토큰, `components/ui/*`, `services/storage.ts`, 개발 스크립트
- **지우는 것**: `server/src/game/`, `view.py`, `content.py`, `locale/ko.py`, `scenarios/harbor/adventure.json`, 클라이언트 `screens/*`, `logic/useGame.ts`. `main`의 `content.py`는 항구 id(`square`, `guard` 등)를 코드에 박아 두었습니다. 새 엔진에서 없애야 하는 바로 그 모양입니다.
- **`llm-local-restore`에서 가져오는 지식**: Kev 응답 정규화(`src/llm/decision.py`), mlx-vlm의 `enable_thinking` 최상위 플래그와 `auto` 모델 id 해석(`src/llm/client.py`, `providers/local.py`). 코드는 새로 짧게 씁니다.
- **의존성**: `pydantic`, `fastapi`, `uvicorn[standard]`, `httpx`, `python-dotenv`. `openai` 패키지는 쓰지 않고 httpx로 스트림을 직접 읽습니다.
- **`.gitignore`**: `scenarios/*`는 계속 무시하고 `!scenarios/_template/`, `!scenarios/harbor/`만 엽니다.

## 1. 파일과 줄 예산

`server/src` 상한은 4,000줄입니다. 테스트와 스크립트는 셈하지 않습니다. 오른쪽 숫자는 처음 잡은 예산 → 구현한 줄 수입니다(합계 3,800 → 3,426).

```
server/
  run_api.py                         앱 조립, --local 기본값, 원고 검증
  src/
    api.py                 150 → 132  라우트, 요청·응답 스키마, 오류 매핑
    service.py             180 → 198  잠금, revision, 영수증, 한 턴 조립
    store.py                90 →  75  스냅샷 원자 저장 (main 것)
    config.py               60 →  63  env 읽기 (main env.py 포함)
    content/
      schema.py            260 → 243  원고 pydantic 모델, 엔진 어휘
      load.py               80 → 109  폴더 읽기, 그래프 초기화, 새 게임
      validate.py          200 → 260  참조, 해법 수, 도달 가능성
      __main__.py           40 →  32  validate CLI
    world/
      graph.py             130 →  82  노드·간선, 간선 추가·삭제
      query.py             100 →  65  위치, 소지품, 관계, 아는 것
      state.py               - → 173  저장 상태, 해석 단계, 턴 기록
    rules/
      dsl.py               180 → 267  조건, 상태 연산(태그 포함), 효과
      candidates.py        160 →  83  지금 가능한 행동 id
      check.py             140 →  87  2d6, 보정, 효과, 확률
      resolve.py           280 → 192  한 턴 실행, 연쇄, 버튼 id 풀기
      costs.py             100 →  70  위험도 표로 대가 고르기
      talk.py              150 →  87  화제, 태도, 주장, 기억
      chapter.py           130 → 103  다 찬 장애물, 복잡화, 쓰러짐, 퀘스트, 장, 결말, 성장, 막힘
      recommend.py         110 →  29  추천 버튼 3개
    scene/
      build.py             140 → 127  플레이어가 아는 것만 추출
      render.py            120 → 109  Kev 상태 문장, Qwen 사실 목록, 기록 줄
      view.py              120 → 177  클라이언트 GameView, 확인 카드
    interpret.py           240 → 193  Kev 질문 만들기, 답 조립, 되묻기
    narrate.py             220 → 133  Qwen 프롬프트, 스트림 필터, Kev 검사, 다시 쓰기
    models/
      kev.py                80 →  65  /v1/systemone
      qwen.py              120 →  69  chat completions 스트림
    locale/ko.py           120 → 203  엔진 문구 (원고 문구 아님)
  scripts/
    bench_kev.py                      질문 수별 Kev 지연 측정
    eval_interpret.py                 해석 평가
    play.py                           터미널에서 실제 모델로 플레이
    check_relational_ssot.sh          간선 탐색이 world 밖에 없는지 검사
  tests/
scenarios/
  _template/  scenario.json, world.md, README.md
  harbor/     scenario.json, world.md, evals/interpret.jsonl, evals/states/*.json
```

`tags.py`는 따로 두지 않고 태그 연산을 `rules/dsl.py`에 넣었습니다. 상태를 바꾸는 코드를 한 파일에 모으기 위해서입니다.

의존 방향은 한쪽입니다: `api → service → (interpret, narrate) → (scene, rules) → (world, content)`. `models`는 `interpret`, `narrate`, 그리고 시작 확인을 하는 `service`만 부릅니다. `rules`, `world`, `scene`에는 입출력이 없고, `content`에서는 `load.py`만 파일을 읽습니다. `tests/test_boundaries.py`가 import를 검사합니다.

## 2. 엔진 어휘

엔진에 고정된 id입니다. 원고는 표시 이름만 바꿉니다.

```python
Approach = Literal["force", "finesse", "wits", "charm"]          # 힘, 재주, 꾀, 말솜씨
Attitude = Literal["polite", "empathy", "persuade", "threaten", "deceive"]
Risk = Literal["low", "normal", "high"]
Plausibility = Literal["natural", "stretch", "impossible"]
Purpose = Literal["overcome", "setup", "clear"]                    # 넘기, 유리한 상황 만들기, 불리한 상황 없애기
Grade = Literal["hit", "mixed", "miss"]                            # 10+, 7~9, 6 이하
TagKind = Literal["edge", "snag"]                                  # 유리, 불리
TagLife = Literal["scene", "chapter"]
Trace = Literal["wanted", "suspicion", "reputation"]               # 흔적: 재주 −1, 말솜씨 −1, 말솜씨 +1
```

## 3. 원고 형식 (`content/schema.py`)

`scenario.json` 하나와 `world.md`입니다. 모든 모델은 `extra="forbid"`입니다.

```python
class Labels(Model):            # 표시 이름, 모두 선택
    approaches: dict[Approach, str] = {}   # 기본: 힘, 재주, 꾀, 말솜씨
    wound: str = "부상"
    gold: str = "돈"

class Creation(Model):
    choose: bool = False                   # False면 아래 값을 그대로 씀
    approaches: dict[Approach, int]        # 합 4, 값 0~2
    traits: list[str]                      # 특성 id 2개

class Trait(Model): id: str; name: str; text: str

class Exit(Model): to: str; open: bool = True

class Place(Model):
    name: str; text: str; chapter: str
    senses: list[str]                      # 3~5개
    exits: list[Exit]

class Character(Model):
    name: str; role: str; place: str
    desire: str; fear: str; contradiction: str; voice: str; boundary: str
    knows: list[str] = []                  # 지식 id
    relation: int = 0                      # −3~+3
    companion: bool = False
    gifts: dict[str, list[Effect]] = {}    # 물건 id → 받았을 때 효과

class Item(Model):
    name: str; text: str
    place: str | None = None; holder: str | None = None
    reveals: str | None = None             # 살피면 얻는 지식 id

class Knowledge(Model): title: str; summary: str

class Topic(Model):
    id: str; character: str; knowledge: str; title: str
    free_when: list[list[Condition]]       # 하나라도 다 맞으면 판정 없이 공개. 2개 이상
    mods: dict[Attitude, int] = {}         # 태도별 판정 보정

class Cost(Model):
    kind: Literal["snag", "gold", "item", "wound"]
    value: int = 1                         # gold 액수, wound 칸
    item: str | None = None

class Solution(Model):
    label: str                             # 버튼 문장. 예: "기름통을 쓰러뜨린다"
    approach: Approach
    risk: Risk = "normal"
    requires: list[Condition] = []

class Obstacle(Model):
    name: str; place: str
    boxes: int                             # 2~6
    fits: list[Approach]; clashes: list[Approach] = []
    costs: list[Cost]
    on_full: list[Effect]
    solutions: list[Solution]              # 2개 이상
    foe: bool = False                      # 전투 상대
    hidden: bool = False                   # 효과 reveal로 드러남
    guards: list[str] = []                 # 다 차기 전까지 집을 수 없는 물건

class Danger(Model):
    name: str
    boxes: int                             # 6~8
    tick_every: int | None = None          # n턴마다 +1 (시한). 무작위 없음
    on_full: list[Effect]                  # 복잡화

class Chapter(Model):
    id: str; title: str
    place: str = ""                         # 장에 들어설 때 옮겨 갈 장소
    danger: Danger
    goal: list[Condition]                  # 다 맞으면 장이 끝남
    next: str = ""

class Quest(Model): title: str; text: str; chapter: str; done_when: list[Condition]

class SceneAction(Model):                  # 원고 행동 (선택)
    id: str; label: str; place: str
    show: list[Condition] = []; requires: list[Condition] = []
    check: Solution | None = None
    hit: list[Effect]; miss: list[Effect] = []
    once: bool = True

class Ending(Model): id: str; title: str; when: list[Condition]; text: str

class Start(Model):
    place: str; chapter: str
    items: list[str] = []; knows: list[str] = []; skills: list[str] = []; gold: int = 0

class Story(Model):
    id: str; version: int; title: str; synopsis: str; intro: str
    labels: Labels = Labels()
    creation: Creation
    traits: list[Trait]                    # 6개
    start: Start
    places: dict[str, Place]
    characters: dict[str, Character]
    items: dict[str, Item]
    knowledge: dict[str, Knowledge]
    skills: dict[str, Skill] = {}          # name, text, approach
    topics: list[Topic]
    obstacles: dict[str, Obstacle]
    chapters: list[Chapter]
    quests: dict[str, Quest] = {}
    actions: list[SceneAction] = []
    downed: list[Effect]                   # 부상이 다 찼을 때
    endings: list[Ending]
```

**조건·효과 DSL**: `main`의 `Condition(kind, target, source, key, value, op, negate)`와 `Effect(kind, target, source, key, value)` 모양을 이어받고 종류를 늘립니다.

| | 종류 |
|---|---|
| 조건 | `at`, `knows`, `carries`, `relation`, `flag`, `progress`(장애물 칸 ≥ value, `full`), `trace`, `quest`, `turn`, `chapter`, `gold` |
| 효과 | `flag`, `flag_add`, `learn`, `give`, `take`, `move`(대상 ""이면 떠남), `companion`, `relation`, `open`, `close`(출구), `tag`(`key`: edge·snag·흔적, `value`: 이름), `reveal`(숨은 장애물), `progress`, `danger`(+n), `gold`, `chapter`(다음 장), `ending` |

`flag`는 원고가 쓰는 자유 상태입니다(예: 항구의 `rescued`, `violence`). 엔진은 그 이름을 모릅니다.

## 4. 게임 상태 (`world/graph.py`, `service.py`)

```python
NodeType = Literal["place", "character", "item", "knowledge", "quest", "skill"]
EdgeType = Literal["at", "connects", "carries", "knows", "relation", "companion", "claimed"]
# relation.properties = {"value": int, "memories": [Memory]}   최대 5개, 오래된 것부터 버림
# connects.properties = {"open": bool}
# claimed.properties  = {"text": str, "turn": int, "exposed": bool}
# 관계가 아닌 장면 상태는 타입이 있는 GameState 필드에 둡니다(아래):
#   obstacles: {id: Progress(value, known, revealed, fired)}, tags: {place: [Tag]}, traces: [Tag], player: Sheet

class Tag(Model):
    id: str; kind: TagKind; target: str | None; life: TagLife
    trace: Trace | None = None
    name: str = ""                          # Qwen이 지은 표시 이름. 비면 locale 기본 이름
    turn: int

class Memory(Model): turn: int; kind: Literal["claim", "threat", "help", "exposed", "promise"]; text: str

class Uses(Model): tag: str | None = None; thing: str | None = None; trait: str | None = None

class ActionStep(Model):                     # 후보 id 하나 (버튼, 되묻기 선택 포함)
    kind: Literal["action"] = "action"; action_id: str

class ImproviseStep(Model):
    kind: Literal["improvise"] = "improvise"
    purpose: Purpose; target: str | None; approach: Approach
    risk: Risk; plausibility: Plausibility; check: bool; uses: Uses

class TalkStep(Model):
    kind: Literal["talk"] = "talk"
    character: str; topic: str                # 화제 id 또는 "chat"
    attitude: Attitude; claim: bool; touch: Literal["desire", "fear", "none"]
    contradicts: str | None; uses: Uses       # 입력 문장은 TurnRecord.input에서 받음

Step = Annotated[ActionStep | ImproviseStep | TalkStep, Field(discriminator="kind")]

class Roll(Model): dice: tuple[int, int]; modifier: int; total: int; grade: Grade
class Button(Model): id: str; label: str; enabled: bool = True

class Change(Model):                         # 바뀐 것 하나. 화면 기록, 서술, 검사가 모두 이것을 씀
    kind: Literal["progress", "danger", "tag_add", "tag_use", "tag_drop", "relation", "learn",
                  "gain", "lose", "gold", "wound", "move", "open", "close", "quest", "complication",
                  "downed", "claim", "exposed", "chapter", "ending", "flag", "reveal", "companion",
                  "inspect", "grow"]
    target: str = ""; before: int | str | None = None; after: int | str | None = None

class StepResult(Model):
    kind: Literal["move", "inspect", "take", "give", "act", "improvise", "talk", "flavor"]
    label: str                                # 엔진이 만든 짧은 설명
    roll: Roll | None = None                  # dice, modifier, total, grade
    effect: int = 0
    changes: list[Change]

class TurnRecord(Model):
    n: int; input: str
    steps: list[StepResult]
    changes: list[Change] = []                # 단계 밖에서 일어난 것: 다 찬 장애물의 효과, 복잡화, 시한
    notable: list[str] = []                   # 되돌아보기 후보
    hint: str | None = None                   # 막힘 힌트 대상 id
    recap: bool = False                       # 장이 끝난 턴
    narration: str | None = None              # 검사를 통과한 서술 캐시
    tag_names: dict[str, str] = {}

class Pending(Model):                         # 확인 카드 또는 성장 선택
    id: str; kind: Literal["confirm", "growth"]
    steps: list[Step] = []                    # 확인을 기다리는 해석 결과
    input: str = ""

class GameState(Model):
    schema_version: Literal[1] = 1
    game_id: str; story_id: str; story_version: int
    revision: int = 0; seed: int; turn: int = 0
    graph: Graph
    player: Sheet                             # approaches, traits, skills, wounds, gold, trait_used
    chapter: str; danger: int = 0; complicated: bool = False
    obstacles: dict[str, Progress] = {}       # value, known(살펴서 아는 방식), revealed, fired
    tags: dict[str, list[Tag]] = {}           # 장소별 장면 태그
    traces: list[Tag] = []                    # 장 끝까지 남는 흔적
    flags: dict[str, int | bool | str] = {}
    quests_done: list[str] = []; actions_done: list[str] = []
    stall: int = 0
    ending: str | None = None
    pending: Pending | None = None
    turns: list[TurnRecord] = []
    receipts: dict[str, Receipt] = {}         # 최근 50개만 유지
```

## 5. 규칙

### 5.1 후보 (`rules/candidates.py`)

`candidates(story, state) -> dict[str, Candidate]`. id 형식이 행동 종류를 정합니다.

| id | 조건 |
|---|---|
| `move:<place>` | `connects`가 있고 `open` |
| `inspect:<id>` | 지금 장소의 인물, 물건, 드러난 장애물 |
| `talk:<character>` | 지금 장소의 인물 |
| `take:<item>` | 장소에 있고 지키는 장애물이 다 찼거나 없음 |
| `give:<character>:<item>` | 지닌 물건 × 장소의 인물 |
| `act:<scene action>` | `show` 조건이 맞음. `requires`가 안 맞으면 비활성 |
| `solve:<obstacle>:<n>` | 원고 해법. `requires`가 맞음. 버튼 전용 |
| `use_tag:<tag>` | 장소의 유리한 태그. 버튼 전용 |
| `improvise` | 항상 |

`solve`와 `use_tag`는 Kev 선택지에 넣지 않습니다. 문장 입력은 같은 일을 `improvise`로 합니다.

### 5.2 판정 (`rules/check.py`)

```python
def modifier(scene, step) -> int:
    m = approach_value
    m += 1 if step.uses.tag in edge_tags_for(step.target) else 0
    m -= min(2, len(snags_for(step.target)))
    m += 1 if step.uses.trait and step.uses.trait not in trait_used else 0
    m += 1 if step.uses.thing else 0                  # 지닌 물건, 아는 지식, 기술
    m += trace_mods(step.approach)                    # 수배 −1 재주, 의심 −1 말솜씨, 평판 +1 말솜씨
    m += relation_mod(step) if step.kind == "talk"    # 관계 ≥2 → +1, ≤−2 → −1
    return clamp(m, approach_value - 3, approach_value + 3)

def grade(total) -> Grade: return "hit" if total >= 10 else "mixed" if total >= 7 else "miss"

def effect(step, obstacle) -> int:                    # hit와 mixed만
    return min(3, 1 + (step.approach in obstacle.fits) + (step.uses.tag is not None))

def risk(step, obstacle) -> Risk:                     # Kev의 위험도에서 출발
    r = step.risk
    if step.approach in obstacle.clashes: r = up(r)
    if step.plausibility == "stretch": r = "high"
    return r

def odds(modifier) -> tuple[float, float, float]:     # 확인 카드용, 2d6 분포에서 계산
```

난수는 `random.Random(hash((state.seed, state.turn, step_index)))`입니다. 같은 저장에서 같은 턴을 다시 실행하면 같은 결과가 나옵니다.

### 5.3 대가 (`rules/costs.py`)

plan.md의 위험도 표를 그대로 코드로 둡니다.

```python
TABLE = {
    ("low", "mixed"):    [("danger", 1)],
    ("low", "miss"):     [("danger", 1)],
    ("normal", "mixed"): [("danger", 1), ("snag",)],
    ("normal", "miss"):  [("danger", 1), ("snag_or_loss",)],
    ("high", "mixed"):   [("danger", 1), ("loss",)],
    ("high", "miss"):    [("danger", 2), ("wound_or_loss",)],
}
```

`snag`는 장애물을 대상으로 장면 태그를 붙입니다. `loss`는 장애물의 `costs` 중 지금 낼 수 있는 것(돈이 있음, 물건을 지님)을 난수로 하나 고릅니다. 낼 수 있는 게 없으면 위험 +1로 바꿉니다. 대화의 대가는 관계 −1 또는 위험 +1입니다.

### 5.4 한 턴 실행 (`rules/resolve.py`)

```python
def resolve(story, state, steps: list[Step], input: str) -> tuple[GameState, TurnRecord]:
    s = state.model_copy(deep=True); s.turn += 1; s.revision += 1
    record = TurnRecord(n=s.turn, input=input, steps=[])
    for i, step in enumerate(steps[:3]):
        if not still_possible(story, s, step): break        # 앞 단계가 장소를 바꿨을 수 있음
        result = run_step(story, s, step, rng(s, i))        # 종류별 함수
        record.steps.append(result)
        after_step(story, s, record)                        # 퀘스트, 장애물 다 참, 위험 다 참, 부상 다 참, 장 목표, 결말
        if result.roll and result.roll.grade == "miss": break
        if s.ending or s.pending: break
    after_turn(story, s, record)                            # tick_every, 막힘 카운터와 힌트, 특성 사용 기록
    return s, record
```

- 종류별 함수: `run_move`, `run_inspect`, `run_take`, `run_give`, `run_act`, `run_improvise`, `run_talk`(5.6), `run_flavor`.
- `run_improvise`는 목적에 따라 다릅니다.
  - `overcome`: 진행도 += 효과
  - `setup`: 유리한 태그 1개를 붙임
  - `clear`: 대상인 불리한 태그 1개를 없앰
  - 대상이 없고 `check`가 아니면 `flavor`: 판정도 변화도 없고 서술만 합니다.
- 모든 변경은 `Change`로 남기고, 상태를 직접 바꾸는 코드는 `rules/dsl.py`의 연산과 `world/graph.py` 두 곳뿐입니다.
- 장소를 떠나면 그 장소의 `life="scene"` 태그를 지웁니다.
- 예외가 나면 `s`를 버립니다. 원래 `state`는 그대로입니다.

### 5.5 태그 (`rules/dsl.py`)

- `add_tag(s, kind, target, out, life=, trace=, name=) -> Tag`: id는 `t{turn}_{n}`이고, 이름은 원고가 주지 않으면 비워 둡니다. 흔적(`trace`)은 장 끝까지 남고 같은 흔적은 하나만 둡니다.
- `drop_tag(s, tag_id, out, used=True)`: 유리한 태그는 판정에 쓰면 사라집니다.
- 장면당 태그는 6개까지입니다. 넘치면 가장 오래된 장면 태그를 지웁니다.

### 5.6 대화 (`rules/talk.py`)

```python
def run_talk(story, s, step: TalkStep, rng) -> StepResult:
    if step.claim: record_claim(s, step.character, text)                # claimed 간선, 기억 "claim"
    if step.contradicts and (step.claim or step.attitude == "deceive"):  # Kev가 고른 모순 지식
        roll = check(charm − 2)
        if roll.grade == "miss": expose(s, step.character)              # 관계 −2, 흔적 suspicion, 기억 "exposed"
    if step.topic == "chat":
        relation_from_touch(s, step)                                    # 욕망 +1, 두려움 −1 (공감이면 +1)
        return StepResult(kind="talk", changes=...)                     # 판정 없음
    topic = topics[step.topic]
    if any(all(holds(c) for c in alt) for alt in topic.free_when): learn(topic.knowledge)
    else:
        approach = "force" if step.attitude == "threaten" else "charm"
        roll = check(approach, mods=topic.mods.get(step.attitude, 0) + relation_mod)
        hit/mixed → learn; mixed → 대화 대가; miss → 관계 −1 또는 위험 +1
    if step.attitude == "threaten": relation −1, 기억 "threat"
    relation_from_touch(s, step)
```

`expose`는 모순 지식을 아는 인물만 할 수 있습니다. Kev 질문의 선택지가 그 인물이 아는 지식뿐이기 때문입니다.

### 5.7 장 (`rules/chapter.py`)

- **위험 다 참**: `danger.on_full`을 한 번 실행하고 `complicated=True`로 둡니다. 위험은 더 오르지 않습니다.
- **부상 다 참**(3): `story.downed`를 한 번 실행하고 부상을 1로 되돌립니다. 게임은 끝나지 않습니다.
- **장 목표**: `chapter.goal`이 맞으면 `record.recap=True`로 두고 `Pending(kind="growth")`을 만듭니다. 그다음 효과 `chapter`가 다음 장으로 넘어가면서 `life="chapter"` 태그를 지우고 위험을 0으로 되돌립니다.
- **성장**: `grow:approach:<a>`(최대 +3) 또는 `grow:trait:<old>:<new>`
- **결말**: 매 단계 뒤에 `endings`를 순서대로 보고 처음 맞는 것을 고릅니다.
- **막힘**: 진행도가 오르지 않은 턴마다 `stall += 1`입니다. 3이 되면 `record.hint`를 정하고 0으로 되돌립니다. 힌트 대상은 이 장소에서 다 차지 않은 장애물 중 진행 비율이 가장 높은 것이고, 비율이 같으면 원고 순서를 따릅니다.

### 5.8 추천 (`rules/recommend.py`)

```python
def recommend(story, state) -> list[Button]:          # 최대 3개, 서로 다른 칸에서
    a = use_tag 버튼 (유리한 태그가 있을 때) or 다 차지 않은 장애물의 첫 해법(solve:)
    b = 장소 인물의 아직 공개되지 않은 화제 → "talk:<c>" + topic 미리 채움
    c = 진행 중인 퀘스트와 관련된 출구 or 아직 안 간 출구
```

문장은 `locale/ko.py` 틀에 조사 함수 `josa(word, "을/를")`를 써서 만듭니다. 화제 버튼은 Kev를 거치지 않는 `TalkStep`(태도 `polite`)으로 바로 실행됩니다.

## 6. Scene과 화면 (`scene/`)

- `build(story, state) -> Scene`
  - 지금 장소, 감각 단서, 열린 출구
  - 장소의 인물(이름, 역할, 관계, 기억), 보이는 물건, 드러난 장애물(진행도, 살펴서 알게 된 어울리는 방식), 태그
  - 위험, 플레이어 시트, 진행 중인 퀘스트, 동료
  - 아는 지식, 인물별 아직 공개되지 않은 화제 제목
- Scene에 없는 것은 해석, 서술, 화면 어디에도 나가지 않습니다. 숨은 장애물, 인물이 숨기는 지식의 내용, 다른 장의 장소가 그 예입니다.
- `render.kev_state(scene, text)`: Kev 상태 문장입니다. 라벨 붙은 짧은 줄로 쓰고 마지막 줄은 `플레이어 입력: …`입니다. 1,500토큰 이하입니다.
- `render.facts(scene, record)`: Qwen과 Kev 검사가 함께 쓰는 사실 목록입니다. 각 줄은 `- 장소: …`, `- 바뀜: 부두 경비 1→3/3`처럼 씁니다.
- `view.game_view(story, state) -> GameView`: 클라이언트 응답입니다(8.2).

## 7. 모델

### 7.1 Kev (`models/kev.py`)

```python
class KevClient:
    async def decide(self, state: str, questions: dict[str, Question]) -> dict[str, Answer]
    async def ping(self) -> None                 # 시작 확인: noul 질문 하나
class Answer(Model):
    type: Literal["choice", "noul"]; answer: str | bool
    confidence: float; probabilities: dict[str, float] = {}
```

정규화는 `llm-local-restore`의 `normalize_answer`와 같습니다. HTTP 오류, 시간 초과, 형식 오류는 모두 `ModelUnavailable`입니다.

### 7.2 Qwen (`models/qwen.py`)

```python
class QwenClient:
    async def resolve_model(self) -> str          # /v1/models 에서 loaded=true, 시작 때 한 번
    async def stream(self, messages, max_tokens=400) -> AsyncIterator[str]
```

요청 본문:

```json
{"model": "<resolved>", "messages": [...], "stream": true, "max_tokens": 400,
 "enable_thinking": false, "chat_template_kwargs": {"enable_thinking": false},
 "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5}
```

`data:` 줄을 읽고 `[DONE]`에서 끝냅니다. thinking을 켜는 경로는 코드에 없습니다.

### 7.3 설정 (`config.py`)

```
KEV_BASE_URL=http://127.0.0.1:8081
KEV_MIN_CONFIDENCE=0.5
KEV_TARGET_MASS=0.6            # 되묻기 판단 (8.1)
QWEN_BASE_URL=http://127.0.0.1:8082/v1
QWEN_MODEL=auto
SCENARIO_DIR=../scenarios
SAVE_DIR=../saves
BASIC_AUTH_USER=… BASIC_AUTH_PASS=… CORS_ORIGINS=…
```

빠진 키는 시작할 때 `KeyError`입니다. 모델을 끄는 설정은 없습니다.

### 7.4 시작 (`api.py` lifespan)

1. `SCENARIO_DIR`의 모든 원고를 읽고 검증합니다. 하나라도 틀리면 오류 목록을 찍고 종료합니다. `_template`도 검증하되 목록에는 넣지 않습니다.
2. `kev.ping()`, `qwen.resolve_model()`. 실패하면 종료합니다.

## 8. 해석 (`interpret.py`)

### 8.1 질문

한 번의 `decide` 호출로 보냅니다. 상태 문장은 한 번만 읽힙니다.

| 질문 id | 형식 | 선택지 |
|---|---|---|
| `s1`, `s2`, `s3` | choice | 후보 id(Kev용) + `improvise` + `none` |
| `s{i}.purpose` | choice | overcome, setup, clear |
| `s{i}.target` | choice | 드러난 장애물 + 장소의 불리한 태그 + `none` |
| `s{i}.approach` | choice | 방식 4개 (원고 표시 이름으로 설명) |
| `s{i}.risk` | choice | low, normal, high |
| `s{i}.plausible` | choice | natural, stretch, impossible |
| `s{i}.check` | noul | 실패할 수 있고 결과가 중요한가 |
| `s{i}.uses.tag` | choice | 장소의 유리한 태그 + `none` |
| `s{i}.uses.thing` | choice | 지닌 물건, 아는 지식, 기술 + `none` |
| `s{i}.uses.trait` | choice | 특성 2개 + `none` |
| `talk.topic` | choice | 대화 상대의 공개되지 않은 화제 + `chat` |
| `talk.attitude` | choice | 태도 5개 |
| `talk.claim` | noul | 자신의 신분·자격·경력을 주장하는가 |
| `talk.touch` | choice | desire, fear, none |
| `talk.contradicts` | choice | 상대가 아는 지식 + `none` |
| `why_not` | choice | 그런 대상이 없음, 능력 밖, 세계의 규칙에 어긋남 |

선택지 수가 1개인 질문은 보내지 않습니다. 대화 질문은 단계 중 처음 나오는 `talk:` 후보의 상대에 대해서만 만듭니다. 한 턴에 대화는 한 단계까지입니다.

질문은 최대 35개입니다. 해석 단계(14절 2단계)의 첫 작업은 `scripts/bench_kev.py`로 10, 20, 35개 질문의 지연을 재는 것입니다. 35개가 1초를 넘으면 두 번에 나눕니다. 첫 호출에는 `s1~s3`, `s1.*`, `talk.*`를 넣고, 둘째 호출은 2·3단계가 즉흥 행동일 때만 `s2.*`, `s3.*`로 합니다. 어느 쪽이든 `interpret()`의 반환은 같습니다.

### 8.2 조립과 되묻기

```python
async def interpret(kev, story, scene, cands, text) -> Interpretation:
    answers = await kev.decide(render.kev_state(scene, text), questions(scene, cands))
    s1 = answers["s1"]
    if s1.answer == "none":                                  return Rejected(reason=ko.NOT_ACTION)
    if s1.low_confidence:
        verb, mass = top_verb(s1.probabilities)              # "move:a"+"move:b" 확률을 동사별로 합침
        if mass >= KEV_TARGET_MASS and verb != "improvise":  return Clarify(options=top3(s1, verb))
        s1 = improvise                                       # 행동이 애매하면 즉흥 행동으로
    steps = [step_from(answers, i) for i in 1..3 if s{i} not in (none, low-confidence)]
    if steps[0].plausibility == "impossible":                 return Rejected(reason=ko.WHY_NOT[answers["why_not"]])
    return Steps(steps)
```

- 2·3단계 답의 확신이 낮으면 그 단계부터 버립니다.
- 세부 답(대상, 방식, 위험, 태도 등)은 닫힌 목록이라 확신과 상관없이 가장 높은 답을 씁니다. 질문을 보내지 않았으면 기본값입니다: 대상 `none`, 방식은 플레이어 최고 방식, 위험 `normal`.
- 대화 화제와 모순 지식은 고른 상대의 것일 때만 받습니다. 아니면 잡담, 모순 없음으로 바꿉니다.
- 거절과 되묻기는 상태를 바꾸지 않고 턴도 쓰지 않습니다.

## 9. 서술 (`narrate.py`)

### 9.1 프롬프트

- **system**: `locale/ko.py`의 서술 규칙(plan.md "서술 규칙"의 문장들, 합니다체, `당신`) + 원고의 `world.md`
- **user**
  ```
  [사실]
  {render.facts(scene, record)}
  [바뀐 것]
  {Change 줄들}
  [결과] 대가 있는 성공 / 효과 2
  [인물] 이름 · 말투 · 기억 3개
  [직전 서술] {직전 턴 서술 300자}
  [플레이어 입력] {record.input}
  [힌트] {record.hint가 있으면: 장애물 이름과 어울리는 방식 하나를 동료나 장면이 짚게}
  [되돌아보기] {record.recap이면: notable 5개}
  [이름 짓기] 새 태그 t12_1(불리, 대상: 부두 경비)… 서술 끝에 한 줄씩 "@t12_1 이름" 형식으로 적으십시오.
  3~6문장. 마지막 문장은 지금 상황입니다. 선택지를 나열하지 마십시오.
  ```

### 9.2 스트림과 검사

```python
async def narrate(game, n) -> AsyncIterator[Event]:
    if record.narration: yield Done(record.narration, record.tag_names); return
    for attempt in range(3):                       # 첫 시도 + 다시 쓰기 2회
        text, names = "", {}
        async for chunk in qwen.stream(messages):
            visible, names = tag_filter.feed(chunk)   # 줄 첫 글자가 "@"면 그 줄은 화면에 내보내지 않음
            text += visible; yield Delta(visible)
        verdict = await kev.decide(check_state(facts, text), CHECK_QUESTIONS)   # contradicts, invents
        if verdict.ok:
            await service.save_narration(game, n, text, valid(names))           # 잠금 안에서, 그 턴만 고침
            yield Done(text, names); return
        yield Reset(); messages = with_feedback(messages, verdict)
    yield Error(retry=True)
```

- 태그 이름은 1~12자, 한 줄이어야 합니다. 틀리면 버리고 locale 기본 이름을 씁니다.
- 같은 게임의 서술 생성은 게임별 잠금 하나로 줄 세웁니다. 뒤에 온 요청은 앞의 결과를 캐시에서 받습니다.
- `Reset` 비율을 기록합니다. 서술 단계(14절 3단계) 끝에 5%를 넘으면 첫 문장을 검사한 뒤에 내보내는 방식을 검토합니다.
- 턴 0(새 게임)도 같은 경로입니다. 입력은 원고의 `intro`이고 바뀐 것은 없습니다.

## 10. 서버 경계

### 10.1 서비스 (`service.py`)

```python
async def act(game_id, body: ActRequest) -> ActResult:
    async with store.lock(game_id):
        state = await store.load(game_id); check_version(state)
        if (r := state.receipts.get(body.request_id)): return replay(r, body, state)   # 같은 요청은 같은 결과
        if body.revision != state.revision: raise Stale
        scene, cands = scene.build(story, state), candidates(story, state)
        match body:
            case {"text": t}:      it = await interpret(kev, story, scene, cands, t)
            case {"action_id": a}: it = from_action(story, state, a)      # 버튼, 되묻기 선택, grow:
            case {"confirm": c}:   it = state.pending.steps if accept else cancel
        if isinstance(it, Rejected | Clarify): return ActResult(kind=…, view=view(state))
        if needs_confirm(story, state, it) and not body.confirm:
            state.pending = Pending(kind="confirm", steps=it.steps, input=…); state.revision += 1
            await store.save(state); return ActResult(kind="confirm", card=confirm_card(…))
        new, record = resolve(story, state, it.steps, input)
        new.turns.append(record); new.receipts[body.request_id] = Receipt(…)
        await store.save(new)
        return ActResult(kind="turn", turn=record.n, view=view(new))
```

- 확인이 필요한 경우: 어떤 단계든 위험이 `high`이면 연쇄 전체를 실행 전에 한 번 확인합니다.
- 확인 카드: 단계 설명, `odds()`의 세 확률, 대가 표의 해당 줄을 보여 줍니다.
- 해석 중 `ModelUnavailable`이 나면 503을 돌려주고 상태는 저장하지 않습니다.

### 10.2 API (`api.py`)

| 경로 | 요청 | 응답 |
|---|---|---|
| `GET /health` | | `{"ok": true, "mode": "engine"}` (인증 없음) |
| `GET /catalog` | | `[{id, title, synopsis, creation: {choose, traits}}]` |
| `POST /games` | `{story, approaches?, traits?}` | `GameView` |
| `GET /games/{id}` | | `GameView` |
| `POST /games/{id}/act` | `{revision, request_id}` + `{text}` 1~200자 \| `{action_id}` \| `{confirm, accept}` | `ActResult` |
| `GET /games/{id}/turns/{n}/narration` | | NDJSON: `delta`, `reset`, `done`, `error` |

```ts
type ActResult = {
  kind: 'turn' | 'confirm' | 'clarify' | 'rejected' | 'cancelled';
  view: GameView; turn?: number;
  card?: { id: string; steps: string[]; odds: [number, number, number]; costs: string[] };
  options?: Button[]; reason?: string;
};
type GameView = {
  game_id: string; revision: number; title: string; chapter: string;
  place: { name: string; senses: string[] }; exits: Button[];
  characters: { id: string; name: string; role: string; mood: string }[];
  obstacles: { id: string; name: string; progress: number; boxes: number; fits: string[] }[];
  danger: { name: string; value: number; boxes: number };
  tags: { id: string; name: string; kind: 'edge' | 'snag'; target: string | null }[];
  player: { approaches: Record<string, number>; traits: NamedText[]; wounds: number; gold: number;
            items: NamedText[]; knowledge: NamedText[]; traces: string[] };
  buttons: Button[];                                     // 추천 3개
  journal: { n: number; input: string; lines: string[]; narration: string | null }[];
  pending: { kind: 'confirm' | 'growth'; card?: …; options?: Button[] } | null;
  ending: { title: string; text: string } | null;
};
```

오류는 404(없는 게임), 409(revision·버전 불일치), 422(잘못된 요청), 503(모델 또는 저장 실패)입니다. 본문은 `locale/ko.py` 문구입니다.

## 11. 클라이언트

```
client/
  app/index.tsx              GameScreen
  screens/GameScreen.tsx     프레임, 머리글, 오류 복구, 당신·기록 대화상자
  screens/Start.tsx          이야기 고르기, 원고가 허용하면 방식(+2와 0)과 특성 2개
  screens/Play.tsx           진행도·태그, 서술, 아래 칸(버튼과 입력 / 확인 카드 / 되묻기 / 성장 / 결말)
  components/game/
    SceneHeader.tsx          장소, 장 이름, 위험 칸
    Meters.tsx, Boxes.tsx    장애물 진행도 칸, 태그 칩(유리·불리 색)
    Narration.tsx            스트림 표시(끝 700자), 끝나면 Reader로 서술 + 바뀐 것 줄
    CommandBar.tsx           추천 버튼 3개, 문장 입력(200자)
    ConfirmCard.tsx          확률 3개와 대가, 감수 / 그만둠
    Choices.tsx              되묻기 후보, 성장 선택
    Sheet.tsx, Journal.tsx   당신(방식·특성·물건·지식·사람·할 일), 지난 턴
  logic/useGame.ts           act → 뷰 갱신 → 서술 스트림, request_id, revision, 재시도
  services/api.ts            fetch(15초), NDJSON 서술 스트림(expo/fetch, 30초 무응답이면 끊음)
  services/types.ts          10.2의 타입
  services/storage.ts        trpg.game_id
  locale/ko.ts               클라이언트 라벨
```

- 입력은 서술이 `done` 또는 `error`일 때 다시 켜집니다. `error`면 "다시 쓰기" 버튼을 보여 줍니다.
- 바뀐 것 줄은 서술 뒤에 붙여 같은 Reader에서 넘겨 봅니다. 320×568에서도 서술 칸이 남게 하기 위해서입니다.
- 원고 문구는 모두 서버 응답에서 옵니다. 클라이언트에는 이야기 문자열이 없습니다.
- React Native의 기본 `fetch`는 응답 스트림을 읽지 못하므로 Expo 54의 `expo/fetch`를 씁니다.
- 웹 개발 포트는 8090입니다. 8081은 Kev가 씁니다.

## 12. 테스트

가짜 모델과 본보기 원고만 씁니다. 실제 모델은 스크립트로 따로 돌립니다.

| 파일 | 확인하는 것 |
|---|---|
| `tests/conftest.py` | `_template` 로드, `FakeKev(answers)`, `FakeQwen(texts)`, 고정 seed 상태 |
| `test_content.py` | 모든 원고 폴더 검증, 스키마 오류, 해법 1개짜리 장애물, 없는 id, 도달 불가 결말, 창작 규칙 |
| `test_rules.py` | 조건·효과, 태그 상한, 후보와 버튼 전용 id, 판정 보정과 효과·위험, 대가 표, 연쇄, 즉흥 행동 세 목적, 태그 소비, 대화와 들통, 특성 1회 |
| `test_chapter.py` | 복잡화 한 번, 쓰러짐, 결말 순서, 시한, 막힘 힌트, 성장과 다음 장 |
| `test_flows.py` | `_template`을 버튼만으로 두 경로 끝까지, 위험이 다 차는 경로 |
| `test_interpret.py` | 질문 생략, 되묻기와 즉흥 전환, 거절, 연쇄 2단계의 낮은 확신 버림, 대화 단계 검증 |
| `test_narrate.py` | `@` 줄 필터, 검사 실패 시 reset 후 다시 쓰기, 3회 실패 error, 낮은 확신 통과, 첫 장면 |
| `test_models.py` | Kev 정규화와 실패, Qwen `auto` 해석과 non-thinking 본문, 실패 |
| `test_service.py` | 영수증 재생, revision 불일치, 버튼 거절, 모델 끊김 시 저장 안 함, 확인 대기와 취소, 서술 저장과 캐시, 태그 이름 |
| `test_api.py` | 라우트별 정상과 오류 코드, 인증, 두 모델 필수, 깨진 원고로 시작 거부 |
| `test_boundaries.py` | `rules`·`world`·`scene`이 `models`·`httpx`·파일 입출력을 import하지 않음. 모든 원고의 id와 이름(2자 이상)이 `server/src`의 문자열(독스트링 제외)에 나오지 않음 |

명령:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check server/
cd server && ../.venv/bin/python -m src.content validate ../scenarios/harbor
find server/src -name '*.py' | xargs wc -l | tail -1
cd client && npx tsc --noEmit && npm run lint && npm test -- --runInBand
```

## 13. 평가와 스크립트

- **해석 평가 세트**: `scenarios/<name>/evals/interpret.jsonl`. 평가는 원고마다 다르므로 원고 폴더에 둡니다.
  ```json
  {"state": "pier_after_guard", "text": "횃불을 떨어뜨린 척 경비를 끌어낸다",
   "expect": [{"kind": "improvise", "target": "dock_guard", "approach": "wits"}], "tags": ["creative"]}
  ```
  `state`는 `evals/states/<name>.json`에 담긴 행동 id 목록입니다. 새 게임에서 그 행동들을 실행해 상태를 만들기 때문에, 원고가 바뀌어도 다시 만들 수 있습니다.
- `scripts/eval_interpret.py --story harbor`: 실제 Kev로 정확도, 되묻기 비율, 잘못 확정한 비율, 즉흥 행동 비율, 가능성 일치율, 지연 p50/p95를 찍습니다.
- `scripts/bench_kev.py`: 질문 수별 지연(8.1).
- `scripts/play.py --story harbor`: 터미널에서 실제 두 모델로 플레이하고 `qa_test/agency/<run>/transcript.jsonl`에 턴마다 입력, 해석, 판정, 서술, 지연을 남깁니다.

## 14. 작업 순서

plan.md "순서"의 단계를 코드 작업으로 나눈 것입니다. 번호는 plan.md와 같고, 0단계만 더했습니다. 각 단계는 테스트와 린트가 통과하고 줄 예산 안일 때 끝납니다.

**진행 상황 (2026-10-18, `engine` 브랜치)**

| 단계 | 코드 | 확인된 것 | 남은 것 |
|---|---|---|---|
| 0 준비 | 완료 | 경계 테스트 | - |
| 1 뼈대 | 완료 | 템플릿 버튼 두 경로와 위험 경로 테스트, 항구 버튼 두 경로를 규칙으로 끝까지(조용한 결말, 공개 결말), 412×915·320×568 화면 | 웹에서 사람이 항구를 끝까지 |
| 2 해석 | 완료 | 가짜 Kev로 조립·되묻기·거절 테스트, 항구 평가 58개(창의·복합·엉뚱 45%) | 실제 Kev로 `bench_kev.py`, `eval_interpret.py` |
| 3 서술 | 완료 | 가짜 Qwen으로 필터·검사·다시 쓰기·캐시 테스트, 화면 스트림 | 실제 Qwen으로 `play.py` 20턴 |
| 4 대화 | 완료 | 무료 공개, 위협, 주장과 들통 테스트 | 실제 모델로 인물이 이전 턴을 되짚는 장면 |
| 5 전투와 성장 | 완료 | 쓰러짐, 성장과 다음 장 테스트 | 전투 평가 항목, 성장 화면 실제 확인 |
| 6 관찰 | - | - | 5명 플레이, 둘째 원고 |

실제 모델 확인은 두 모델이 떠 있을 때 13절 스크립트로 합니다.

0. **준비**
   - `engine` 브랜치, 지우기와 남기기(0절), `.gitignore`, 의존성
   - `conftest.py`, `test_boundaries.py`
1. **뼈대**
   - `content`(스키마, 로드, 검증, CLI), `_template` 원고와 README
   - `world`, `rules` 전부(대화 제외), `scene`, `store`, `service`, `api`
   - 화면: 버튼, 진행도, 태그, 바뀐 것 줄
   - 항구 원고를 새 형식으로 다시 씁니다. 장애물 4~5개, 위험 "경계", 시한은 `tick_every`
   - 끝: `test_flows.py`, 항구 validate 통과, 웹에서 버튼만으로 항구 첫 장 두 경로
2. **해석**
   - `models/kev.py`, `bench_kev.py`로 질문 나누기 결정, `interpret.py`
   - `render.kev_state`, 시작 확인, 확인 카드와 되묻기 화면
   - 항구 평가 50개 이상(엉뚱하거나 복합적인 것 30% 이상)
   - 끝: `eval_interpret.py` 결과를 `qa_test/agency/<run>/`에 기록, 잘못 확정한 비율 5% 이하
3. **서술**
   - `models/qwen.py`, `narrate.py`, 스트림 라우트
   - 클라이언트 `Narration`, 태그 이름, 막힘 힌트
   - 끝: `play.py`로 20턴, 검사 통과율, 첫 글자 지연, 서술 끊김 뒤 다시 요청
4. **대화**
   - `rules/talk.py`, 대화 질문, 기억, 주장과 들통, 인물의 질문(서술 규칙)
   - 항구 화제와 공개 조건
   - 끝: 같은 지식을 다른 태도로 얻는 테스트, 들통 테스트, `play.py`에서 인물이 이전 턴을 되짚는 장면
5. **전투와 성장**
   - `foe` 장애물, 부상과 쓰러짐, 성장 선택 화면, 되돌아보기 서술
   - 끝: 전투를 즉흥 행동으로 피하거나 끝내는 평가 항목, 장 넘김 흐름 테스트
6. **관찰과 둘째 원고**
   - 5명 플레이 기록, plan.md 재미 지표 집계
   - `_template` README만 보고 흰섬 붉은섬 장을 새 형식으로 씁니다.
   - 끝: 둘째 원고가 코드 수정 없이 validate와 `play.py`를 통과합니다. 코드를 고쳤다면 그 diff를 엔진 구멍 목록으로 남깁니다.

## 15. 정할 것

- **질문 나누기**: 8.1의 측정 결과로 정합니다.
- **`Reset` 처리**: 스트림을 지우고 다시 쓰는 것이 어색하면 첫 문장 검사 방식으로 바꿉니다(9.2). 서술 단계의 플레이 기록으로 정합니다.
- **저장 크기**: 턴 기록을 모두 남깁니다. 200턴에서 1MB를 넘으면 서술만 따로 파일로 뺍니다.
